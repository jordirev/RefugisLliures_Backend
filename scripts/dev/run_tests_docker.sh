#!/usr/bin/env bash
# Executa pytest dins la imatge `rl-testrunner` (Linux + GDAL) contra el Postgres local `rl-postgres`, des de
# Windows (Git Bash). Pensat per a diversos worktrees en paral·lel: cadascun amb la seva BD de proves.
#
#   scripts/dev/run_tests_docker.sh <nom_bd> [arguments de pytest...]
#   p. ex.: scripts/dev/run_tests_docker.sh refugisdb_test_visites apps/visits -q
#
# - El directori actual (el worktree) es munta a /app.
# - Les URL `TEST_DATABASE_URL_*` es prenen de `env/.env.development` del checkout principal (ENV_REPO), dins el
#   contenidor i sense imprimir-les; `TEST_DATABASE_NAME` hi canvia només el nom de la BD (settings.py).
# - El contenidor comparteix la xarxa de `rl-postgres` (127.0.0.1:5432 és el Postgres local).
# La BD `<nom_bd>` ha d'existir amb les extensions i grants de `setup_local_postgres.sh` (TEST_DB_NAME=<nom_bd>).
set -euo pipefail
db="${1:?cal el nom de la BD de proves}"
shift
ENV_REPO="${ENV_REPO:-/c/Users/jordi/Desktop/UNI/TFG/Backend/RefugisLliures_Backend}"
MSYS_NO_PATHCONV=1 docker run --rm --network container:rl-postgres \
  -e TEST_DATABASE_NAME="$db" \
  -v "$(pwd -W):/app" -v "$(cd "$ENV_REPO/env" && pwd -W):/envsrc:ro" -w /app rl-testrunner \
  bash -c 'set -a; . <(grep -E "^TEST_DATABASE_URL_(APP|MIGRATOR)=" /envsrc/.env.development | tr -d "\r"); set +a; exec python -m pytest -p no:cacheprovider "$@"' _ "$@"
