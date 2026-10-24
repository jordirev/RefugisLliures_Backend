"""Helpers per a les migracions de domini (docs/design/postgres-schema.md §6.5)."""
from django.db import migrations

from .rls import create_policy_sql, drop_policy_sql


class PostgresRunSQL(migrations.RunSQL):
    """`RunSQL` que només s'executa a PostgreSQL (a la resta de motors, p. ex. el SQLite dels tests amb mocks, no fa res)."""

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        if schema_editor.connection.vendor == 'postgresql':
            super().database_forwards(app_label, schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        if schema_editor.connection.vendor == 'postgresql':
            super().database_backwards(app_label, schema_editor, from_state, to_state)


class DropDjangoLikeIndexes(PostgresRunSQL):
    """Esborra els índexs `*_like` (`varchar/text_pattern_ops`) que Django crea a cada PK o camp únic de text.

    Cap consulta del domini fa cerques per prefix (`LIKE 'x%'`) sobre aquestes columnes (decisió del PO).
    Django crea aquests índexs al `deferred_sql` del schema editor (al final de la migració), de manera que un
    `RunSQL` normal a la mateixa migració encara no els troba: aquí el `DROP` s'encua al final del `deferred_sql`.
    `indexes`: tuples `(schema, nom de l'índex, taula, columna, opclass)`; els noms són els deterministes de Django
    (si canviessin, el `DROP` falla en veu alta i el test de l'esquema ho detecta).
    """

    def __init__(self, indexes):
        self.indexes = list(indexes)
        super().__init__(
            sql=[f'DROP INDEX {schema}.{name}' for schema, name, _, _, _ in self.indexes],
            reverse_sql=[f'CREATE INDEX {name} ON {schema}.{table} ({column} {opclass})'
                         for schema, name, table, column, opclass in self.indexes],
        )

    def deconstruct(self):
        return self.__class__.__name__, [self.indexes], {}

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        if schema_editor.connection.vendor == 'postgresql':
            schema_editor.deferred_sql.extend(self.sql)


def enable_rls_sql(table):
    """`ENABLE ROW LEVEL SECURITY` (sense `FORCE`: el propietari `migrator` no hi està subjecte)."""
    return f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY'


def disable_rls_sql(table):
    return f'ALTER TABLE {table} DISABLE ROW LEVEL SECURITY'


__all__ = ['PostgresRunSQL', 'DropDjangoLikeIndexes', 'create_policy_sql', 'drop_policy_sql', 'enable_rls_sql', 'disable_rls_sql']
