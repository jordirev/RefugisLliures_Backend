#!/usr/bin/env bash
# E2E del chunk 2 (refugis): llista/mapa, cerca, detall, mitjans i errors 500 amb error_id (docs/migration/EQUIP.md).
#
# Requisits (vegeu docs/guides/testing.md, "E2E local"): els mateixos que e2e_chunk1.sh, amb la BD migrada i el
# catàleg carregat (`python manage.py load_refuges`). Opcionals:
#   - E2E_SQL_CMD: ordre que llegeix SQL per stdin com a propietari de la BD (p. ex.
#     "docker exec -i rl-postgres psql -U postgres -d refugisdb_e2e -q"). Si hi és, s'insereix un mitjà de prova
#     per provar l'esborrat amb R2 inabastable (500 + error_id, la fila es conserva) i es neteja al final.
#   - E2E_LOG_CMD: ordre que imprimeix el log del servidor (p. ex. "docker logs rl-e2e-server"), per comprovar que
#     l'error_id de la resposta hi apareix.
# Crea dos usuaris de prova a l'emulador (normal i admin amb claim role=admin). Cap credencial real.
# Surt amb codi 1 si algun cas falla.
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

ensure_user() {  # ensure_user <email> -> localId
  local uid
  uid=$(auth_call accounts:signUp "$1" | json_field localId)
  [ -n "$uid" ] || uid=$(auth_call accounts:signInWithPassword "$1" | json_field localId)
  echo "$uid"
}

ok()   { printf 'OK    %s\n' "$1"; }
fail() { printf 'FALLA %s\n' "$1"; fails=$((fails + 1)); }

check() {  # check <descripció> <codi esperat> [args de curl...]
  local desc="$1" expected="$2" code
  shift 2
  code=$(curl -s -m 30 -o /dev/null -w '%{http_code}' "$@")
  if [ "$code" = "$expected" ]; then ok "$(printf '%-50s %s' "$desc" "$code")"
  else fail "$(printf '%-50s %s (esperat %s)' "$desc" "$code" "$expected")"; fi
}

check_json() {  # check_json <descripció> <expressió python sobre d (cos JSON)> [args de curl...]
  local desc="$1" expr="$2" body
  shift 2
  body=$(curl -s -m 30 "$@")
  if echo "$body" | python3 -c "import sys, json; d = json.load(sys.stdin); sys.exit(0 if ($expr) else 1)" 2>/dev/null; then
    ok "$desc"
  else
    fail "$desc: $(echo "$body" | head -c 300)"
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

# --- Llista sense filtres (mapa: consulta directa a refuges)
check_json "llista: {count, results}, sense has_filters" \
  "set(d) == {'count', 'results'} and d['count'] == len(d['results']) and d['count'] > 0" "$API/refuges/"
check_json "llista: punts {id, name, coord{lat,long}, geohash}" \
  "all(set(r) == {'id', 'name', 'coord', 'geohash'} and set(r['coord']) == {'lat', 'long'} for r in d['results'])" \
  "$API/refuges/"
REFUGE_ID=$(curl -s "$API/refuges/" | python3 -c "import sys, json; print(json.load(sys.stdin)['results'][0]['id'])")

# --- Cerca i filtres (refugis complets)
check_json "cerca: sense accents ni majúscules ('ESTANYOL TARTERES')" \
  "any('Estanyol de Tarter' in r['name'] for r in d['results'])" "$API/refuges/?name=ESTANYOL%20TARTERES"
check_json "cerca: pel surname ('Pleta de les Escaldes' -> Abri de Nescale)" \
  "any(r['name'] == 'Abri de Nescale' for r in d['results'])" "$API/refuges/?name=Pleta%20de%20les%20Escaldes"
check_json "cerca: % no coincideix amb tot" "d['count'] < 50" "$API/refuges/?name=%25"
check_json "cerca: resposta {count, results} sense surname" \
  "set(d) == {'count', 'results'} and d['results'] and all('surname' not in r for r in d['results'])" \
  "$API/refuges/?name=cabane"
check_json "filtre condition=3: totes les condicions són 3" \
  "d['count'] > 0 and all(r['condition'] == 3 for r in d['results'])" "$API/refuges/?condition=3"
check_json "filtre altitude 2000-2100" \
  "d['count'] > 0 and all(2000 <= r['altitude'] <= 2100 for r in d['results'])" \
  "$API/refuges/?altitude_min=2000&altitude_max=2100"
check "filtre invàlid (condition=7)" 400 "$API/refuges/?condition=7"
check "filtre invàlid (altitude_min > max)" 400 "$API/refuges/?altitude_min=3000&altitude_max=1000"

# --- Detall
DETAIL_KEYS="{'id','name','coord','altitude','places','info_comp','description','links','type','modified_at','region','departement','condition'}"   # sense remarque (S-6)
check_json "detall anònim: camps exactes (sense surname, mitjans ni visitors)" \
  "set(d) == $DETAIL_KEYS" "$API/refuges/$REFUGE_ID/"
check_json "detall anònim: condition enter 0-3 o null; info_comp 0/1" \
  "(d['condition'] is None or d['condition'] in (0, 1, 2, 3)) and all(v in (0, 1) for v in d['info_comp'].values())" \
  "$API/refuges/$REFUGE_ID/"
check_json "detall usuari: + images_metadata, sense visitors" \
  "set(d) == $DETAIL_KEYS | {'images_metadata'}" "${U[@]}" "$API/refuges/$REFUGE_ID/"
check_json "detall admin: + images_metadata i visitors == []" \
  "set(d) == $DETAIL_KEYS | {'images_metadata', 'visitors'} and d['visitors'] == []" "${A[@]}" "$API/refuges/$REFUGE_ID/"
check "detall id inexistent (UUID)" 404 "$API/refuges/01a16e20-0000-7000-8000-000000000000/"
check "detall id mal format" 404 "$API/refuges/no-es-un-uuid/"

# --- El catàleg no s'escriu per l'API
check "POST /refuges/ (admin)" 405 -X POST "${A[@]}" -H 'Content-Type: application/json' -d '{}' "$API/refuges/"
check "DELETE /refuges/{id}/ (admin)" 405 -X DELETE "${A[@]}" "$API/refuges/$REFUGE_ID/"

# --- Mitjans
check "media anònim" 401 "$API/refuges/$REFUGE_ID/media/"
check_json "media usuari: {media: []}" "d == {'media': []}" "${U[@]}" "$API/refuges/$REFUGE_ID/media/"
check "media refugi inexistent" 404 "${U[@]}" "$API/refuges/01a16e20-0000-7000-8000-000000000000/media/"
check "DELETE mitjà anònim" 401 -X DELETE "$API/refuges/$REFUGE_ID/media/refuges/x/no-existeix.webp/"
check "DELETE mitjà inexistent (usuari)" 403 -X DELETE "${U[@]}" "$API/refuges/$REFUGE_ID/media/refuges/x/no-existeix.webp/"
check "DELETE mitjà inexistent (admin)" 404 -X DELETE "${A[@]}" "$API/refuges/$REFUGE_ID/media/refuges/x/no-existeix.webp/"

if [ -n "${E2E_SQL_CMD:-}" ]; then
  KEY="refuges/$REFUGE_ID/e2e-$suffix.webp"
  # L'autor ha d'existir a users.users (FK real); fins al chunk 3 cap endpoint crea aquest registre.
  echo "INSERT INTO users.users (uid) VALUES ('$USER_UID') ON CONFLICT DO NOTHING" | $E2E_SQL_CMD
  echo "INSERT INTO refuges.refuge_media (key, refuge_id, creator_uid, media_type, content_type, status, uploaded_at,
        rights_confirmed_at) VALUES ('$KEY', '$REFUGE_ID', '$USER_UID', 'image', 'image/webp', 'visible', now(), now())" \
    | $E2E_SQL_CMD
  check_json "media usuari: veu el mitjà inserit (MediaItem)" \
    "len(d['media']) == 1 and d['media'][0]['key'] == '$KEY' and d['media'][0]['creator_uid'] == '$USER_UID'" \
    "${U[@]}" "$API/refuges/$REFUGE_ID/media/"
  OTHER_EMAIL="other-$suffix@e2e.test"
  ensure_user "$OTHER_EMAIL" >/dev/null
  O=(-H "Authorization: Bearer $(auth_call accounts:signInWithPassword "$OTHER_EMAIL" | json_field idToken)")
  check "DELETE mitjà d'un altre usuari" 403 -X DELETE "${O[@]}" "$API/refuges/$REFUGE_ID/media/$KEY/"
  body=$(curl -s -m 30 -X DELETE "${U[@]}" "$API/refuges/$REFUGE_ID/media/$KEY/")
  error_id=$(echo "$body" | python3 -c "import sys, json; d = json.load(sys.stdin); print(d.get('error_id', ''))" 2>/dev/null)
  if echo "$body" | python3 -c "import sys, json; d = json.load(sys.stdin); sys.exit(0 if set(d) == {'error', 'error_id'} and d['error'] == 'Error en esborrar el fitxer a R2' else 1)" 2>/dev/null; then
    ok "DELETE propi amb R2 inabastable: 500 {error, error_id}"
  else
    fail "DELETE propi amb R2 inabastable: $(echo "$body" | head -c 300)"
  fi
  check_json "després del 500 la fila es conserva" "len(d['media']) == 1" "${U[@]}" "$API/refuges/$REFUGE_ID/media/"
  if [ -n "${E2E_LOG_CMD:-}" ] && [ -n "$error_id" ]; then
    # Primer a una variable: amb `pipefail`, `grep -q` tancaria la canonada abans d'hora i el SIGPIPE faria fallar el cas.
    server_log=$($E2E_LOG_CMD 2>&1)
    if grep -q "$error_id" <<<"$server_log"; then ok "l'error_id apareix al log del servidor"
    else fail "l'error_id $error_id no apareix al log del servidor"; fi
  fi
  echo "DELETE FROM users.users WHERE uid = '$USER_UID'" | $E2E_SQL_CMD   # CASCADE esborra el mitjà
fi

echo
if [ "$fails" -eq 0 ]; then echo "E2E chunk 2: tot correcte"; else echo "E2E chunk 2: $fails casos fallen"; fi
[ "$fails" -eq 0 ]
