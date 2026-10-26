#!/usr/bin/env bash
# E2E del chunk 3 (usuaris): profile_required, creació amb edat, perfil propi i aliè, PATCH (M1), confirmació
# d'edat, preferits, visitats (+ visitors del refugi per a admins), avatar i esborrat provisional (D21).
#
# Requisits: els mateixos que e2e_chunk2.sh (BD migrada amb el catàleg carregat, Firebase Auth Emulator i,
# per a l'esborrat d'usuari, el Firestore Emulator). Crea tres usuaris de prova a l'emulador (normal, altre i
# admin amb claim role=admin). Cap credencial real. Surt amb codi 1 si algun cas falla.
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
OTHER_EMAIL="other-$suffix@e2e.test"
OTHER_UID=$(ensure_user "$OTHER_EMAIL")
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
OTHER_TOKEN=$(auth_call accounts:signInWithPassword "$OTHER_EMAIL" | json_field idToken)
U=(-H "Authorization: Bearer $USER_TOKEN")
A=(-H "Authorization: Bearer $ADMIN_TOKEN")
O=(-H "Authorization: Bearer $OTHER_TOKEN")
J=(-H 'Content-Type: application/json')


# --- Refugis de prova
REFS=$(curl -s -m 30 "$API/refuges/" | python3 -c "import sys, json; r = json.load(sys.stdin)['results']; print(r[0]['id'], r[1]['id'])")
R1=${REFS% *}; R2=${REFS#* }
[ -n "$R1" ] && [ -n "$R2" ] || { echo "No hi ha refugis carregats" >&2; exit 2; }
BAD_REF="00000000-0000-7000-8000-000000000000"
YEAR=$(date +%Y)

# --- 403 profile_required abans de crear el perfil
check_json "sense perfil: GET propi -> profile_required" "'profile_required' in json.dumps(d)" "${U[@]}" "$API/users/$USER_UID/"
check "sense perfil: GET propi (codi)" 403 "${U[@]}" "$API/users/$USER_UID/"
check "sense perfil: POST preferit -> 403" 403 "${U[@]}" "${J[@]}" -X POST -d "{\"refuge_id\":\"$R1\"}" "$API/users/$USER_UID/favorite-refuges/"
check "lectura pública sense perfil: detall refugi" 200 "$API/refuges/$R1/"

# --- POST /users/
check "POST /users/ sense token -> 401" 401 "${J[@]}" -X POST -d '{}' "$API/users/"
check "POST /users/ idioma fora del catàleg -> 400" 400 "${U[@]}" "${J[@]}" -X POST -d '{"language":"xx"}' "$API/users/"
check "POST /users/ menor d'edat -> 403" 403 "${U[@]}" "${J[@]}" -X POST -d "{\"birth_date\":\"$YEAR-01-01\"}" "$API/users/"
check_json "POST /users/ -> 201 perfil propi" \
  "d['uid'] == '$USER_UID' and d['language'] == 'ca' and d['username'] == 'Usuari E2E' and d['age_confirmed'] is True and d['favourite_refuges'] == [] and d['num_shared_experiences'] == 0" \
  "${U[@]}" "${J[@]}" -X POST -d '{"username":"Usuari E2E","language":"ca","birth_date":"1990-05-01"}' "$API/users/"
check "POST /users/ repetit -> 409" 409 "${U[@]}" "${J[@]}" -X POST -d '{"birth_date":"1990-05-01"}' "$API/users/"
check_json "POST /users/ sense idioma -> 'en' i sense edat" "d['language'] == 'en' and d['age_confirmed'] is False" \
  "${O[@]}" "${J[@]}" -X POST -d '{}' "$API/users/"
check "POST /users/ admin" 201 "${A[@]}" "${J[@]}" -X POST -d '{"username":"Admin"}' "$API/users/"

# --- GET / PATCH
check_json "GET propi: claus del contracte" \
  "set(d) == {'uid','username','avatar_metadata','language','favourite_refuges','visited_refuges','uploaded_photos_keys','num_shared_experiences','num_renovated_refuges','created_at','age_confirmed'}" \
  "${U[@]}" "$API/users/$USER_UID/"
check_json "GET aliè: només {uid, username, avatar_metadata}" "set(d) == {'uid','username','avatar_metadata'}" "${O[@]}" "$API/users/$USER_UID/"
check_json "GET aliè com a admin: també reduït (D23)" "set(d) == {'uid','username','avatar_metadata'}" "${A[@]}" "$API/users/$USER_UID/"
check "GET uid inexistent -> 404" 404 "${U[@]}" "$API/users/no-existeix-$suffix/"
check "GET sense token -> 401" 401 "$API/users/$USER_UID/"
check "PATCH {} -> 400 (M1)" 400 "${U[@]}" "${J[@]}" -X PATCH -d '{}' "$API/users/$USER_UID/"
check "PATCH idioma invàlid -> 400" 400 "${U[@]}" "${J[@]}" -X PATCH -d '{"language":"xx"}' "$API/users/$USER_UID/"
check "PATCH username d'1 caràcter -> 400" 400 "${U[@]}" "${J[@]}" -X PATCH -d '{"username":"a"}' "$API/users/$USER_UID/"
check_json "PATCH idioma i nom -> 200" "d['language'] == 'es' and d['username'] == 'Nou Nom'" \
  "${U[@]}" "${J[@]}" -X PATCH -d '{"language":"es","username":"Nou Nom"}' "$API/users/$USER_UID/"
check "PATCH d'un altre usuari -> 403" 403 "${O[@]}" "${J[@]}" -X PATCH -d '{"username":"Hack"}' "$API/users/$USER_UID/"

# --- Confirmació d'edat
check "age-confirmation menor -> 403" 403 "${O[@]}" "${J[@]}" -X PATCH -d "{\"birth_date\":\"$YEAR-01-01\"}" "$API/users/$OTHER_UID/age-confirmation/"
check "age-confirmation format invàlid -> 400" 400 "${O[@]}" "${J[@]}" -X PATCH -d '{"birth_date":"01/01/1990"}' "$API/users/$OTHER_UID/age-confirmation/"
check_json "age-confirmation adult -> age_confirmed" "d['age_confirmed'] is True" \
  "${O[@]}" "${J[@]}" -X PATCH -d '{"birth_date":"1985-03-03"}' "$API/users/$OTHER_UID/age-confirmation/"

# --- Preferits
FAV="$API/users/$USER_UID/favorite-refuges/"
check "preferit: refugi inexistent -> 404" 404 "${U[@]}" "${J[@]}" -X POST -d "{\"refuge_id\":\"$BAD_REF\"}" "$FAV"
check "preferit: id mal format -> 404" 404 "${U[@]}" "${J[@]}" -X POST -d '{"refuge_id":"no-uuid"}' "$FAV"
check "preferit: sense refuge_id -> 400" 400 "${U[@]}" "${J[@]}" -X POST -d '{}' "$FAV"
check_json "preferit: afegir R1 -> resum del refugi" "d['id'] == '$R1' and {'id','name','region','places','coord','images_metadata'} <= set(d)" \
  "${U[@]}" "${J[@]}" -X POST -d "{\"refuge_id\":\"$R1\"}" "$FAV"
check "preferit: afegir R1 de nou (idempotent)" 200 "${U[@]}" "${J[@]}" -X POST -d "{\"refuge_id\":\"$R1\"}" "$FAV"
check "preferit: afegir R2" 200 "${U[@]}" "${J[@]}" -X POST -d "{\"refuge_id\":\"$R2\"}" "$FAV"
check_json "preferits: llista en ordre d'inserció" "d['count'] == 2 and [r['id'] for r in d['results']] == ['$R1', '$R2']" "${U[@]}" "$FAV"
check_json "perfil: favourite_refuges" "d['favourite_refuges'] == ['$R1', '$R2']" "${U[@]}" "$API/users/$USER_UID/"
check "preferits d'un altre usuari -> 403" 403 "${O[@]}" "$FAV"
check "preferit: DELETE R1 -> 204" 204 "${U[@]}" -X DELETE "$FAV$R1/"
check "preferit: DELETE R1 de nou -> 204 (idempotent)" 204 "${U[@]}" -X DELETE "$FAV$R1/"
check "preferit: DELETE refugi inexistent -> 404" 404 "${U[@]}" -X DELETE "$FAV$BAD_REF/"
check_json "preferits: queda R2" "d['count'] == 1 and d['results'][0]['id'] == '$R2'" "${U[@]}" "$FAV"

# --- Visitats i visitors del refugi
VIS="$API/users/$USER_UID/visited-refuges/"
check "visitat: afegir R1" 200 "${U[@]}" "${J[@]}" -X POST -d "{\"refuge_id\":\"$R1\"}" "$VIS"
check_json "visitats: llista" "d['count'] == 1 and d['results'][0]['id'] == '$R1'" "${U[@]}" "$VIS"
check_json "detall refugi (admin): visitors inclou l'usuari" "'$USER_UID' in d.get('visitors', [])" "${A[@]}" "$API/refuges/$R1/"
check_json "detall refugi (usuari): sense visitors" "'visitors' not in d" "${U[@]}" "$API/refuges/$R1/"
check "visitats d'un altre usuari -> 403" 403 "${O[@]}" "$VIS"
check "visitat: DELETE R1 -> 204" 204 "${U[@]}" -X DELETE "$VIS$R1/"
check_json "detall refugi (admin): l'usuari ja no hi és" "'$USER_UID' not in d.get('visitors', [])" "${A[@]}" "$API/refuges/$R1/"

# --- Avatar
check "avatar: DELETE sense avatar -> 404" 404 "${U[@]}" -X DELETE "$API/users/$USER_UID/avatar/"
check "avatar: DELETE d'un altre -> 403" 403 "${O[@]}" -X DELETE "$API/users/$USER_UID/avatar/"

# --- Esborrat d'usuari (D21)
check "DELETE d'un altre usuari -> 403" 403 "${O[@]}" -X DELETE "$API/users/$USER_UID/"
check "DELETE propi -> 204" 204 "${U[@]}" -X DELETE "$API/users/$USER_UID/"
check "després d'esborrar: GET propi -> 403 profile_required" 403 "${U[@]}" "$API/users/$USER_UID/"
check "després d'esborrar: GET com a altre -> 404" 404 "${O[@]}" "$API/users/$USER_UID/"

# --- U7: el backend esborra el compte de Firebase Auth; el mateix token no pot recrear l'UID
check "després d'esborrar: POST /users/ amb el token -> 401" 401 "${U[@]}" -X POST "$API/users/" \
  -H 'Content-Type: application/json' -d '{"username":"Torno"}'
code=$(curl -s -X POST "${U[@]}" "$API/users/" -H 'Content-Type: application/json' -d '{}' | json_field code)
if [ "$code" = "account_not_found" ]; then ok "POST /users/ -> code account_not_found"
else fail "POST /users/ -> code '$code' (esperat account_not_found)"; fi
relogin=$(auth_call accounts:signInWithPassword "$USER_EMAIL" | json_field localId)
if [ -z "$relogin" ]; then ok "compte de Firebase Auth esborrat (login impossible)"
else fail "el compte de Firebase Auth encara existeix"; fi

echo
if [ "$fails" -eq 0 ]; then echo "Tot correcte"; else echo "$fails cas(os) fallats"; exit 1; fi
