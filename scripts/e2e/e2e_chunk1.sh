#!/usr/bin/env bash
# E2E del chunk 1 (infraestructura): health, autenticació/permisos i context RLS (docs/migration/EQUIP.md, D3).
#
# Requisits (vegeu docs/guides/testing.md, "E2E local"):
#   - Firebase Auth Emulator (i Firestore Emulator) en marxa: AUTH_EMULATOR (def. http://localhost:9099).
#   - Servidor Django en marxa a BASE_URL (def. http://localhost:8000) amb FIREBASE_AUTH_EMULATOR_HOST apuntant al
#     mateix emulador i DATABASE_URL_APP/MIGRATOR cap al Postgres a provar (local o Neon `dev`), migrat amb
#     `python manage.py migrate --database=migrator`.
# Crea dos usuaris de prova a l'emulador (normal i admin amb claim role=admin). Cap credencial real.
# Surt amb codi 1 si algun cas no retorna el codi HTTP esperat.
set -uo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
AUTH_EMULATOR="${AUTH_EMULATOR:-http://localhost:9099}"
PROJECT_ID="${GCLOUD_PROJECT:-demo-refugis-lliures}"
PASSWORD="e2e-pass-123"   # només per a l'emulador
IDT="$AUTH_EMULATOR/identitytoolkit.googleapis.com/v1"
API="$BASE_URL/api"
fails=0

json_field() { python3 -c "import sys, json; print(json.load(sys.stdin).get('$1', ''))"; }

auth_call() {  # auth_call <endpoint> <email>
  curl -s -X POST "$IDT/$1?key=fake" -H 'Content-Type: application/json' \
    -d "{\"email\":\"$2\",\"password\":\"$PASSWORD\",\"returnSecureToken\":true}"
}

ensure_user() {  # ensure_user <email> -> localId (crea l'usuari si no existeix)
  local uid
  uid=$(auth_call accounts:signUp "$1" | json_field localId)
  [ -n "$uid" ] || uid=$(auth_call accounts:signInWithPassword "$1" | json_field localId)
  echo "$uid"
}

check() {  # check <descripció> <codi esperat> [args de curl...]
  local desc="$1" expected="$2" code
  shift 2
  code=$(curl -s -m 30 -o /dev/null -w '%{http_code}' "$@")
  if [ "$code" = "$expected" ]; then
    printf 'OK    %-45s %s\n' "$desc" "$code"
  else
    printf 'FALLA %-45s %s (esperat %s)\n' "$desc" "$code" "$expected"
    fails=$((fails + 1))
  fi
}

suffix="$(date +%s)"
USER_EMAIL="user-$suffix@e2e.test"
ADMIN_EMAIL="admin-$suffix@e2e.test"
USER_UID=$(ensure_user "$USER_EMAIL")
ADMIN_UID=$(ensure_user "$ADMIN_EMAIL")
if [ -z "$USER_UID" ] || [ -z "$ADMIN_UID" ]; then
  echo "No s'han pogut crear els usuaris a l'emulador ($AUTH_EMULATOR)" >&2
  exit 2
fi
curl -s -o /dev/null -X POST "$IDT/projects/$PROJECT_ID/accounts:update" \
  -H 'Authorization: Bearer owner' -H 'Content-Type: application/json' \
  -d "{\"localId\":\"$ADMIN_UID\",\"customAttributes\":\"{\\\"role\\\":\\\"admin\\\"}\"}"
USER_TOKEN=$(auth_call accounts:signInWithPassword "$USER_EMAIL" | json_field idToken)
ADMIN_TOKEN=$(auth_call accounts:signInWithPassword "$ADMIN_EMAIL" | json_field idToken)
U=(-H "Authorization: Bearer $USER_TOKEN")
A=(-H "Authorization: Bearer $ADMIN_TOKEN")

# Health amb Postgres (camp `database`)
check "health (anònim)" 200 "$API/health/"
body=$(curl -s -m 30 "$API/health/")
if echo "$body" | python3 -c "import sys, json; sys.exit(0 if json.load(sys.stdin).get('database') is True else 1)"; then
  echo "OK    health.database == true"
else
  echo "FALLA health.database no és true: $body"; fails=$((fails + 1))
fi

# Autenticació i permisos (el hook de RLS s'executa a totes les vistes, també @api_view)
check "cache/stats sense token" 401 "$API/cache/stats/"
check "cache/stats token invàlid" 401 -H 'Authorization: Bearer x.y.z' "$API/cache/stats/"
check "cache/stats usuari normal" 403 "${U[@]}" "$API/cache/stats/"
check "cache/stats admin" 200 "${A[@]}" "$API/cache/stats/"
check "users/{propi} sense perfil (profile_required, chunk 3)" 403 "${U[@]}" "$API/users/$USER_UID/"
# Des del chunk 3 tot endpoint autenticat exigeix perfil: es crea el de l'admin
check "POST /users/ admin" 201 -X POST "${A[@]}" -H 'Content-Type: application/json' -d '{}' "$API/users/"
check "users/{propi} sense token" 401 "$API/users/$USER_UID/"
check "users/{aliè} PATCH" 403 -X PATCH "${U[@]}" -H 'Content-Type: application/json' \
  -d '{"language":"en"}' "$API/users/$ADMIN_UID/"
check "admin/media-reports usuari normal" 403 "${U[@]}" "$API/admin/media-reports/"
check "admin/media-reports admin" 200 "${A[@]}" "$API/admin/media-reports/"
check "refuges (públic)" 200 "$API/refuges/?limit=1"

echo
if [ "$fails" -eq 0 ]; then echo "E2E chunk 1: tot correcte"; else echo "E2E chunk 1: $fails casos fallen"; fi
[ "$fails" -eq 0 ]
