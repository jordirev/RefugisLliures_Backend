"""
`core.0001`: schemas de domini, funcions de `core` i grants base (docs/design/postgres-schema.md §2.0, §7.1).

S'executa amb el rol `migrator` (propietari de tots els objectes). Requereix el *bootstrap* previ del
propietari de la BD (§1.3): extensions `postgis`, `pg_trgm`, `unaccent`, `btree_gist` i `GRANT CREATE ON DATABASE`.
"""
from django.db import migrations

from domain.core.migration_utils import PostgresRunSQL

SCHEMAS = ('core', 'refuges', 'users', 'activity', 'proposals', 'moderation', 'audit')

CORE_FUNCTION_SIGNATURES = (
    'core.uid()',
    'core.is_admin()',
    'core.is_system()',
    'core.immutable_unaccent(text)',
    'core.norm_name(text)',
    'core.round_half_even(double precision)',
)

FORWARD = [
    # Les funcions SECURITY DEFINER (i qualsevol funció futura del migrator) no són cridables per PUBLIC.
    'ALTER DEFAULT PRIVILEGES FOR ROLE migrator REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC',
    *[f'CREATE SCHEMA IF NOT EXISTS {schema}' for schema in SCHEMAS],

    # --- Context de la petició (valors que posa l'aplicació amb set_config(..., true), §7.3) ---
    """CREATE FUNCTION core.uid() RETURNS text LANGUAGE sql STABLE PARALLEL SAFE
  AS $$ SELECT NULLIF(current_setting('app.uid', true), '') $$""",
    """CREATE FUNCTION core.is_admin() RETURNS boolean LANGUAGE sql STABLE PARALLEL SAFE
  AS $$ SELECT COALESCE(current_setting('app.is_admin', true), '') = 'true' $$""",
    """CREATE FUNCTION core.is_system() RETURNS boolean LANGUAGE sql STABLE PARALLEL SAFE
  AS $$ SELECT COALESCE(current_setting('app.is_system', true), '') = 'true' $$""",

    # --- unaccent IMMUTABLE amb el diccionari fixat (permet índexs d'expressió) ---
    """CREATE FUNCTION core.immutable_unaccent(text) RETURNS text
  LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT
  AS $$ SELECT public.unaccent('public.unaccent'::regdictionary, $1) $$""",
    """CREATE FUNCTION core.norm_name(text) RETURNS text
  LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT
  AS $$ SELECT core.immutable_unaccent(lower($1)) $$""",

    # --- Arrodoniment half-to-even (== round() de Python 3) ---
    """CREATE FUNCTION core.round_half_even(double precision) RETURNS integer
  LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT
  AS $$ SELECT CASE WHEN $1 - floor($1) = 0.5 THEN (2 * round(($1 / 2)::numeric))::integer
                    ELSE round($1::numeric)::integer END $$""",

    # --- Grants base per a `app` ---
    'REVOKE ALL ON FUNCTION ' + ', '.join(CORE_FUNCTION_SIGNATURES) + ' FROM PUBLIC',
    'GRANT USAGE ON SCHEMA ' + ', '.join(SCHEMAS) + ' TO app',
    'GRANT USAGE ON SCHEMA public TO app',
    'GRANT EXECUTE ON FUNCTION ' + ', '.join(CORE_FUNCTION_SIGNATURES) + ' TO app',
]

REVERSE = [
    'REVOKE EXECUTE ON FUNCTION ' + ', '.join(CORE_FUNCTION_SIGNATURES) + ' FROM app',
    'REVOKE USAGE ON SCHEMA ' + ', '.join(SCHEMAS) + ' FROM app',
    'DROP FUNCTION core.round_half_even(double precision)',
    'DROP FUNCTION core.norm_name(text)',
    'DROP FUNCTION core.immutable_unaccent(text)',
    'DROP FUNCTION core.is_system()',
    'DROP FUNCTION core.is_admin()',
    'DROP FUNCTION core.uid()',
    # RESTRICT: si hi ha objectes d'altres apps, cal revertir-les abans (ordre de §6.2).
    *[f'DROP SCHEMA IF EXISTS {schema}' for schema in reversed(SCHEMAS)],
    'ALTER DEFAULT PRIVILEGES FOR ROLE migrator GRANT EXECUTE ON FUNCTIONS TO PUBLIC',
]


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        PostgresRunSQL(sql=FORWARD, reverse_sql=REVERSE),
    ]
