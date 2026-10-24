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


def enable_rls_sql(table):
    """`ENABLE ROW LEVEL SECURITY` (sense `FORCE`: el propietari `migrator` no hi està subjecte)."""
    return f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY'


def disable_rls_sql(table):
    return f'ALTER TABLE {table} DISABLE ROW LEVEL SECURITY'


__all__ = ['PostgresRunSQL', 'create_policy_sql', 'drop_policy_sql', 'enable_rls_sql', 'disable_rls_sql']
