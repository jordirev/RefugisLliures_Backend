#!/usr/bin/env bash
# Bootstrap idempotent d'un PostgreSQL local (o d'un servei postgis de GitHub Actions) per als tests.
# Reprodueix el bootstrap de docs/design/postgres-schema.md §1.3 i §7.1:
#   rols `migrator` (propietari dels objectes de domini) i `app` (DML, sotmesa a RLS), BD `refugisdb_test`,
#   extensions creades pel superusuari i atributs/timeouts dels rols.
# Les contrasenyes són d'ús exclusivament local (no secrets). Cap accés a Neon.
#
# Variables d'entorn (totes opcionals):
#   PGHOST (def. /var/run/postgresql -> socket; "localhost" amb servei TCP), PGPORT (def. 5432)
#   PG_SUPERUSER (def. postgres), PGPASSWORD (contrasenya del superusuari si cal, p. ex. CI)
#   TEST_DB_NAME (def. refugisdb_test)
#   MIGRATOR_PASSWORD / APP_PASSWORD (def. valors locals fixos)
#   PG_START_CLUSTER=0 per no intentar arrencar el clúster (CI amb servei)
#   Si s'executa com a root i el superusuari és `postgres` sobre socket, s'usa `runuser -u postgres`.
set -euo pipefail

PGHOST="${PGHOST:-}"
PGPORT="${PGPORT:-5432}"
PG_SUPERUSER="${PG_SUPERUSER:-postgres}"
TEST_DB_NAME="${TEST_DB_NAME:-refugisdb_test}"
MIGRATOR_PASSWORD="${MIGRATOR_PASSWORD:-migrator_local_pw}"
APP_PASSWORD="${APP_PASSWORD:-app_local_pw}"
PG_START_CLUSTER="${PG_START_CLUSTER:-1}"
PG_BIN="${PG_BIN:-$(ls -d /usr/lib/postgresql/*/bin 2>/dev/null | sort -V | tail -1 || true)}"
[ -n "$PG_BIN" ] && export PATH="$PG_BIN:$PATH"

use_su=0
if [ -z "$PGHOST" ] && [ "$(id -u)" = "0" ] && command -v runuser >/dev/null 2>&1 && [ "$PG_SUPERUSER" = "postgres" ]; then
  use_su=1   # socket Unix amb peer auth
fi

# Arrencada del clúster local (apt) si cal
if [ "$PG_START_CLUSTER" = "1" ] && [ -z "$PGHOST" ] && command -v pg_lsclusters >/dev/null 2>&1; then
  if ! pg_isready -q -p "$PGPORT" 2>/dev/null; then
    cl=$(pg_lsclusters --no-header | awk 'NR==1{print $1" "$2}')
    if [ -n "$cl" ]; then
      echo "Arrencant el clúster $cl ..." >&2
      pg_ctlcluster $cl start || true
      for _ in $(seq 1 30); do pg_isready -q -p "$PGPORT" && break; sleep 1; done
    fi
  fi
fi

psql_su() {  # psql_su <db> [args...]  (llegeix SQL de stdin)
  local db="$1"; shift
  if [ "$use_su" = "1" ]; then
    runuser -u postgres -- psql -X -v ON_ERROR_STOP=1 -q -p "$PGPORT" -d "$db" "$@"
  else
    psql -X -v ON_ERROR_STOP=1 -q ${PGHOST:+-h "$PGHOST"} -p "$PGPORT" -U "$PG_SUPERUSER" -d "$db" "$@"
  fi
}
q() { # q <db> <sql>: resultat escalar
  if [ "$use_su" = "1" ]; then
    runuser -u postgres -- psql -X -At -p "$PGPORT" -d "$1" -c "$2"
  else
    psql -X -At ${PGHOST:+-h "$PGHOST"} -p "$PGPORT" -U "$PG_SUPERUSER" -d "$1" -c "$2"
  fi
}

# --- Rols (atributs de §1.3 / §7.1) ---
psql_su postgres <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'migrator') THEN
    CREATE ROLE migrator LOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app') THEN
    CREATE ROLE app LOGIN;
  END IF;
END \$\$;
ALTER ROLE migrator LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD '${MIGRATOR_PASSWORD}';
ALTER ROLE app      LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD '${APP_PASSWORD}';
ALTER ROLE app SET statement_timeout = '20s';
ALTER ROLE app SET lock_timeout = '5s';
ALTER ROLE app SET idle_in_transaction_session_timeout = '30s';
SQL

# --- Base de dades (propietat del superusuari) ---
if [ "$(q postgres "SELECT 1 FROM pg_database WHERE datname='${TEST_DB_NAME}'")" != "1" ]; then
  psql_su postgres -c "CREATE DATABASE ${TEST_DB_NAME}"
fi

# --- Extensions (només el superusuari pot) + grants de BD ---
psql_su "$TEST_DB_NAME" <<SQL
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE EXTENSION IF NOT EXISTS btree_gist;
GRANT CREATE ON DATABASE ${TEST_DB_NAME} TO migrator;
GRANT CONNECT ON DATABASE ${TEST_DB_NAME} TO app;
GRANT CONNECT ON DATABASE ${TEST_DB_NAME} TO migrator;
GRANT USAGE ON SCHEMA public TO app, migrator;
-- PG15+ treu CREATE a PUBLIC: el migrator ha de poder crear django_migrations i les taules de Django a public.
GRANT CREATE ON SCHEMA public TO migrator;
SQL

HOST_URL="${PGHOST:-localhost}"
case "$HOST_URL" in /*) HOST_URL="localhost";; esac
echo "# URLs locals (no secretes) per als tests:"
echo "export TEST_DATABASE_URL_MIGRATOR=postgres://migrator:${MIGRATOR_PASSWORD}@${HOST_URL}:${PGPORT}/${TEST_DB_NAME}"
echo "export TEST_DATABASE_URL_APP=postgres://app:${APP_PASSWORD}@${HOST_URL}:${PGPORT}/${TEST_DB_NAME}"
