#!/usr/bin/env bash
# E2E del chunk 6 (dubtes i respostes a PostgreSQL): creació, llista amb answers/answers_count, arbre de respostes,
# esborrat del subarbre, C1 (només creador o admin esborren), bloqueig i edat als POST, 404/400/401/403.
#
# Requisits: els de e2e_chunk3.sh (BD migrada amb `doubts.0001` i el catàleg, Firebase Auth Emulator). Per al cas
# d'usuari bloquejat cal `PSQL_BLOCK` (ordre que executa SQL com a superusuari a la BD e2e), p. ex.:
#   PSQL_BLOCK='docker exec -i rl-postgres psql -U postgres -d refugisdb_e2e -q' (si no hi és, se salta).
# Cap credencial real. Surt amb codi 1 si algun cas falla.
set -uo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
AUTH_EMULATOR="${AUTH_EMULATOR:-http://localhost:9099}"
PROJECT_ID="${GCLOUD_PROJECT:-demo-refugis-lliures}"
PASSWORD="e2e-pass-123"   # només per a l'emulador
IDT="$AUTH_EMULATOR/identitytoolkit.googleapis.com/v1"
API="$BASE_URL/api"
fails=0

json_field() { python3 -c "import sys, json; print(json.load(sys.stdin).get('$1', ''))"; }
auth_call() {
  curl -s -X POST "$IDT/$1?key=fake" -H 'Content-Type: application/json' \
    -d "{\"email\":\"$2\",\"password\":\"$PASSWORD\",\"returnSecureToken\":true}"
}
ensure_user() {
  local uid
  uid=$(auth_call accounts:signUp "$1" | json_field localId)
  [ -n "$uid" ] || uid=$(auth_call accounts:signInWithPassword "$1" | json_field localId)
  echo "$uid"
}
ok()   { printf 'OK    %s\n' "$1"; }
fail() { printf 'FALLA %s\n' "$1"; fails=$((fails + 1)); }
check() {
  local desc="$1" expected="$2" code
  shift 2
  code=$(curl -s -m 30 -o /dev/null -w '%{http_code}' "$@")
  if [ "$code" = "$expected" ]; then ok "$(printf '%-55s %s' "$desc" "$code")"
  else fail "$(printf '%-55s %s (esperat %s)' "$desc" "$code" "$expected")"; fi
}
check_json() {
  local desc="$1" expr="$2" body
  shift 2
  body=$(curl -s -m 30 "$@")
  if echo "$body" | python3 -c "import sys, json; d = json.load(sys.stdin); sys.exit(0 if ($expr) else 1)" 2>/dev/null
  then ok "$desc"; else fail "$desc: $(echo "$body" | head -c 300)"; fi
}

suffix="$(date +%s)"
U_EMAIL="d-user-$suffix@e2e.test"; O_EMAIL="d-other-$suffix@e2e.test"
A_EMAIL="d-admin-$suffix@e2e.test"; Y_EMAIL="d-young-$suffix@e2e.test"
U_UID=$(ensure_user "$U_EMAIL"); O_UID=$(ensure_user "$O_EMAIL"); A_UID=$(ensure_user "$A_EMAIL"); Y_UID=$(ensure_user "$Y_EMAIL")
[ -n "$U_UID" ] && [ -n "$A_UID" ] || { echo "No s'han pogut crear els usuaris a l'emulador" >&2; exit 2; }
curl -s -o /dev/null -X POST "$IDT/projects/$PROJECT_ID/accounts:update" \
  -H 'Authorization: Bearer owner' -H 'Content-Type: application/json' \
  -d "{\"localId\":\"$A_UID\",\"customAttributes\":\"{\\\"role\\\":\\\"admin\\\"}\"}"
tok() { auth_call accounts:signInWithPassword "$1" | json_field idToken; }
U=(-H "Authorization: Bearer $(tok "$U_EMAIL")"); O=(-H "Authorization: Bearer $(tok "$O_EMAIL")")
A=(-H "Authorization: Bearer $(tok "$A_EMAIL")"); Y=(-H "Authorization: Bearer $(tok "$Y_EMAIL")")
J=(-H 'Content-Type: application/json')

# Perfils: tres adults amb edat confirmada; un sense data de naixement (edat no confirmada)
for who in U O A; do
  declare -n H=$who
  curl -s -o /dev/null "${H[@]}" "${J[@]}" -X POST "$API/users/" -d '{"username":"E2E","birth_date":"1990-01-01"}'
done
curl -s -o /dev/null "${Y[@]}" "${J[@]}" -X POST "$API/users/" -d '{"username":"Sense edat"}'

R1=$(curl -s -m 30 "$API/refuges/" | python3 -c "import sys, json; print(json.load(sys.stdin)['results'][0]['id'])")
[ -n "$R1" ] || { echo "No hi ha refugis carregats" >&2; exit 2; }
BAD_REF="00000000-0000-7000-8000-000000000000"
D="$API/doubts/"

# --- Autenticació i validació
check "GET sense token -> 401" 401 "$D?refuge_id=$R1"
check "GET sense refuge_id -> 400" 400 "${U[@]}" "$D"
check "GET refugi inexistent -> 404" 404 "${U[@]}" "$D?refuge_id=$BAD_REF"
check "GET refugi no UUID -> 404" 404 "${U[@]}" "$D?refuge_id=no-es-uuid"
check "POST missatge buit -> 400" 400 "${U[@]}" "${J[@]}" -X POST "$D" -d "{\"refuge_id\":\"$R1\",\"message\":\"   \"}"
check "POST refugi inexistent -> 404" 404 "${U[@]}" "${J[@]}" -X POST "$D" -d "{\"refuge_id\":\"$BAD_REF\",\"message\":\"Hola\"}"
check "POST sense edat confirmada -> 403" 403 "${Y[@]}" "${J[@]}" -X POST "$D" -d "{\"refuge_id\":\"$R1\",\"message\":\"Hola\"}"
code=$(curl -s "${Y[@]}" "${J[@]}" -X POST "$D" -d "{\"refuge_id\":\"$R1\",\"message\":\"Hola\"}" | json_field code)
[ "$code" = "age_not_confirmed" ] && ok "POST sense edat -> code age_not_confirmed" || fail "POST sense edat -> code '$code'"

# --- Creació i llista
DOUBT=$(curl -s "${U[@]}" "${J[@]}" -X POST "$D" -d "{\"refuge_id\":\"$R1\",\"message\":\"Hi ha aigua?\"}")
DID=$(echo "$DOUBT" | json_field id)
[ -n "$DID" ] && ok "POST dubte -> 201 amb id" || fail "POST dubte: $DOUBT"
echo "$DOUBT" | python3 -c "import sys, json; d = json.load(sys.stdin); sys.exit(0 if d['answers'] == [] and d['answers_count'] == 0 and d['creator_uid'] == '$U_UID' else 1)" \
  && ok "dubte nou: answers [] i answers_count 0" || fail "forma del dubte nou: $DOUBT"
check_json "llista: el dubte hi és amb answers []" \
  "any(x['id'] == '$DID' and x['answers'] == [] and x['answers_count'] == 0 for x in d)" "${U[@]}" "$D?refuge_id=$R1"

A1=$(curl -s "${O[@]}" "${J[@]}" -X POST "$D$DID/answers/" -d '{"message":"Si, a la font"}' | json_field id)
[ -n "$A1" ] && ok "POST resposta (altre usuari) -> 201" || fail "POST resposta"
A2=$(curl -s "${U[@]}" "${J[@]}" -X POST "$D$DID/answers/$A1/" -d '{"message":"Merci"}' | json_field id)
[ -n "$A2" ] && ok "POST rèplica a la resposta -> 201" || fail "POST rèplica"
A3=$(curl -s "${O[@]}" "${J[@]}" -X POST "$D$DID/answers/$A2/" -d '{"message":"De res"}' | json_field id)
check_json "llista: 3 respostes, arbre amb parent_answer_id" \
  "[x for x in d if x['id'] == '$DID'][0]['answers_count'] == 3 and {a['id']: a['parent_answer_id'] for a in [x for x in d if x['id'] == '$DID'][0]['answers']} == {'$A1': None, '$A2': '$A1', '$A3': '$A2'}" \
  "${U[@]}" "$D?refuge_id=$R1"
check "rèplica a resposta inexistent -> 404" 404 "${U[@]}" "${J[@]}" -X POST "$D$DID/answers/$BAD_REF/" -d '{"message":"x"}'
check "resposta a dubte inexistent -> 404" 404 "${U[@]}" "${J[@]}" -X POST "$D$BAD_REF/answers/" -d '{"message":"x"}'

# Una resposta d'un altre dubte no pot ser pare (IDOR)
D2=$(curl -s "${O[@]}" "${J[@]}" -X POST "$D" -d "{\"refuge_id\":\"$R1\",\"message\":\"Altre dubte\"}" | json_field id)
check "rèplica amb pare d'un altre dubte -> 404" 404 "${U[@]}" "${J[@]}" -X POST "$D$D2/answers/$A1/" -d '{"message":"x"}'
check "esborrar resposta amb doubt_id aliè -> 404" 404 "${O[@]}" -X DELETE "$D$D2/answers/$A1/"

# --- C1: propietat
check "esborrar resposta d'un altre -> 403" 403 "${U[@]}" -X DELETE "$D$DID/answers/$A1/"
code=$(curl -s "${U[@]}" -X DELETE "$D$DID/answers/$A1/" | json_field code)
[ "$code" = "not_owner" ] && ok "esborrar resposta d'un altre -> code not_owner" || fail "code '$code'"
check "esborrar dubte d'un altre -> 403" 403 "${O[@]}" -X DELETE "$D$DID/"
check "esborrar la pròpia resposta A1 (subarbre) -> 204" 204 "${O[@]}" -X DELETE "$D$DID/answers/$A1/"
check_json "subarbre esborrat: 0 respostes" "[x for x in d if x['id'] == '$DID'][0]['answers'] == []" "${U[@]}" "$D?refuge_id=$R1"
check "esborrar resposta ja esborrada -> 404" 404 "${O[@]}" -X DELETE "$D$DID/answers/$A2/"

# --- Bloqueig: no pot escriure, sí llegir i esborrar el seu
if [ -n "${PSQL_BLOCK:-}" ]; then
  echo "SELECT set_config('app.is_system','true',false); UPDATE users.users SET is_blocked = true, blocked_reason = 'strikes', blocked_at = now() WHERE uid = '$U_UID';" | $PSQL_BLOCK >/dev/null
  check "bloquejat: POST dubte -> 403" 403 "${U[@]}" "${J[@]}" -X POST "$D" -d "{\"refuge_id\":\"$R1\",\"message\":\"Hola\"}"
  code=$(curl -s "${U[@]}" "${J[@]}" -X POST "$D$DID/answers/" -d '{"message":"x"}' | json_field code)
  [ "$code" = "user_blocked" ] && ok "bloquejat: POST resposta -> code user_blocked" || fail "code '$code'"
  check "bloquejat: GET -> 200" 200 "${U[@]}" "$D?refuge_id=$R1"
  check "bloquejat: esborra el seu dubte -> 204" 204 "${U[@]}" -X DELETE "$D$DID/"
else
  echo "SALTAT bloqueig (sense PSQL_BLOCK)"
  check "esborrar el propi dubte -> 204" 204 "${U[@]}" -X DELETE "$D$DID/"
fi
check "dubte ja esborrat -> 404" 404 "${O[@]}" -X DELETE "$D$DID/"

# --- Admin
check "admin esborra el dubte d'un altre -> 204" 204 "${A[@]}" -X DELETE "$D$D2/"

echo
if [ "$fails" -eq 0 ]; then echo "E2E chunk 6: tot correcte"; else echo "$fails cas(os) fallats"; exit 1; fi
