#!/usr/bin/env bash
# E2E del chunk 7 (experiències i intents de pujada a PostgreSQL): creació amb `condition` obligatòria, mitjana del
# refugi pel trigger (primer vot, segon vot, PATCH), llista per refugi, propietat (not_owner), validacions, bloqueig i
# edat a POST/PATCH (no a DELETE), comptador del perfil per SQL, esborrat d'usuari i intents de pujada (creació,
# validacions, confirm d'un objecte que no s'ha pujat → missing_object).
#
# Requisits: els de e2e_chunk3.sh (BD migrada amb `experiences.0001`, `uploads.0001`, `refuges.0002` i el catàleg,
# Firebase Auth Emulator). R2 és fictici: no es puja cap fitxer real.
#   PSQL_E2E='docker exec -i rl-postgres psql -U postgres -d refugisdb_e2e -q'  (bloqueig i lectura de la mitjana)
# Cap credencial real. Surt amb codi 1 si algun cas falla.
set -uo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
AUTH_EMULATOR="${AUTH_EMULATOR:-http://localhost:9099}"
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
avg() {  # mitjana desada del refugi (sense arrodonir) i n
  echo "SELECT coalesce(condition::text,'null') || ' ' || num_contributed_conditions FROM refuges.refuges WHERE id = '$1';" \
    | $PSQL_E2E -tA
}

suffix="$(date +%s)"
U_EMAIL="x-user-$suffix@e2e.test"; O_EMAIL="x-other-$suffix@e2e.test"; Y_EMAIL="x-young-$suffix@e2e.test"
Z_EMAIL="x-gone-$suffix@e2e.test"
U_UID=$(ensure_user "$U_EMAIL"); O_UID=$(ensure_user "$O_EMAIL"); Y_UID=$(ensure_user "$Y_EMAIL"); Z_UID=$(ensure_user "$Z_EMAIL")
[ -n "$U_UID" ] && [ -n "$O_UID" ] && [ -n "$Z_UID" ] || { echo "No s'han pogut crear els usuaris a l'emulador" >&2; exit 2; }
tok() { auth_call accounts:signInWithPassword "$1" | json_field idToken; }
U=(-H "Authorization: Bearer $(tok "$U_EMAIL")"); O=(-H "Authorization: Bearer $(tok "$O_EMAIL")")
Y=(-H "Authorization: Bearer $(tok "$Y_EMAIL")"); Z=(-H "Authorization: Bearer $(tok "$Z_EMAIL")")
J=(-H 'Content-Type: application/json')
for who in U O Z; do
  declare -n H=$who
  curl -s -o /dev/null "${H[@]}" "${J[@]}" -X POST "$API/users/" -d '{"username":"E2E","birth_date":"1990-01-01"}'
done
curl -s -o /dev/null "${Y[@]}" "${J[@]}" -X POST "$API/users/" -d '{"username":"Sense edat"}'

# Un refugi diferent a cada execució (la mitjana acumula els vots d'execucions anteriors)
R1=$(curl -s -m 30 "$API/refuges/" | python3 -c "import sys, json; r = json.load(sys.stdin)['results']; print(r[($suffix + 7) % len(r)]['id'])")
[ -n "$R1" ] || { echo "No hi ha refugis carregats" >&2; exit 2; }
BAD_ID="00000000-0000-7000-8000-000000000000"
EX="$API/experiences"
body() { printf '{"refuge_id":"%s","comment":"%s","condition":%s}' "$1" "$2" "$3"; }

# --- Autenticació i validació
check "GET sense token -> 401" 401 "$EX/?refuge_id=$R1"
check "GET sense refuge_id -> 400" 400 "${U[@]}" "$EX/"
check "GET refugi inexistent -> 404" 404 "${U[@]}" "$EX/?refuge_id=$BAD_ID"
check "POST sense condition -> 400" 400 "${U[@]}" "${J[@]}" -X POST "$EX/" -d "{\"refuge_id\":\"$R1\",\"comment\":\"Bon refugi\"}"
check "POST condition 4 -> 400" 400 "${U[@]}" "${J[@]}" -X POST "$EX/" -d "$(body "$R1" "Bon refugi" 4)"
check "POST comentari en blanc -> 400" 400 "${U[@]}" "${J[@]}" -X POST "$EX/" -d "$(body "$R1" "   " 2)"
check "POST refugi inexistent -> 404" 404 "${U[@]}" "${J[@]}" -X POST "$EX/" -d "$(body "$BAD_ID" "Bon refugi" 2)"
code=$(curl -s "${Y[@]}" "${J[@]}" -X POST "$EX/" -d "$(body "$R1" "Bon refugi" 2)" | json_field code)
[ "$code" = "age_not_confirmed" ] && ok "POST sense edat confirmada -> code age_not_confirmed" || fail "POST sense edat: code '$code'"

# --- Creació i mitjana del refugi (trigger)
before=$(avg "$R1")
created=$(curl -s -m 30 "${U[@]}" "${J[@]}" -X POST "$EX/" -d "$(body "$R1" "Primera visita" 3)")
EID=$(echo "$created" | python3 -c "import sys, json; print(json.load(sys.stdin)['experience']['id'])" 2>/dev/null)
[ -n "$EID" ] && ok "POST U amb condition 3 -> 201" || fail "POST U: $(echo "$created" | head -c 300)"
if echo "$created" | python3 -c "import sys, json; d = json.load(sys.stdin)['experience']; sys.exit(0 if d['condition'] == 3 and d['creator_uid'] == '$U_UID' else 1)" 2>/dev/null
then ok "resposta del POST porta condition i creator_uid"; else fail "resposta del POST: $(echo "$created" | head -c 300)"; fi
after1=$(avg "$R1")
python3 - "$before" "$after1" <<'PY' && ok "primer vot: n+1 i mitjana c=(c*n+3)/(n+1) ($after1)" || fail "primer vot: abans '$before' després '$after1'"
import sys
c0, n0 = sys.argv[1].split(); c1, n1 = sys.argv[2].split()
n0, n1 = int(n0), int(n1); c0 = 0.0 if c0 == 'null' else float(c0)
sys.exit(0 if n1 == n0 + 1 and abs(float(c1) - (c0 * n0 + 3) / (n0 + 1)) < 1e-9 else 1)
PY
O_EID=$(curl -s -m 30 "${O[@]}" "${J[@]}" -X POST "$EX/" -d "$(body "$R1" "Segona visita" 1)" | python3 -c "import sys, json; print(json.load(sys.stdin)['experience']['id'])" 2>/dev/null)
[ -n "$O_EID" ] && ok "POST O amb condition 1 -> 201" || fail "POST O no creat"
after2=$(avg "$R1")
check_json "GET llista del refugi: 2 experiències amb condition" \
  "sorted(x['condition'] for x in d['experiences'] if x['id'] in ('$EID', '$O_EID')) == [1, 3]" "${U[@]}" "$EX/?refuge_id=$R1"

# --- PATCH, propietat
check_json "PATCH U condition 3 -> 1 i comentari" "d['experience']['condition'] == 1 and d['experience']['comment'] == 'Editada'" \
  "${U[@]}" "${J[@]}" -X PATCH "$EX/$EID/" -d '{"comment":"Editada","condition":1}'
after3=$(avg "$R1")
python3 - "$after2" "$after3" <<'PY' && ok "PATCH v->v': n igual i c=c+(1-3)/n ($after3)" || fail "PATCH: abans '$after2' després '$after3'"
import sys
c0, n0 = sys.argv[1].split(); c1, n1 = sys.argv[2].split()
sys.exit(0 if n1 == n0 and abs(float(c1) - max(0.0, min(3.0, float(c0) + (1 - 3) / int(n0)))) < 1e-9 else 1)
PY
check "PATCH comentari en blanc -> 400" 400 "${U[@]}" "${J[@]}" -X PATCH "$EX/$EID/" -d '{"comment":""}'
code=$(curl -s "${O[@]}" "${J[@]}" -X PATCH "$EX/$EID/" -d '{"comment":"No meva"}' | json_field code)
[ "$code" = "not_owner" ] && ok "PATCH d'un altre -> code not_owner" || fail "PATCH d'un altre: code '$code'"
check "DELETE d'un altre -> 403" 403 "${O[@]}" -X DELETE "$EX/$EID/"
check "PATCH id no UUID -> 404" 404 "${U[@]}" "${J[@]}" -X PATCH "$EX/abc/" -d '{"comment":"x"}'
check "PATCH id inexistent -> 404" 404 "${U[@]}" "${J[@]}" -X PATCH "$EX/$BAD_ID/" -d '{"comment":"x"}'

# --- Comptador del perfil (SQL)
check_json "perfil propi de U: num_shared_experiences 1" "d['num_shared_experiences'] == 1" "${U[@]}" "$API/users/$U_UID/"

# --- Bloqueig: no escriu, sí llegeix i esborra el seu; esborrar no toca la mitjana
if [ -n "${PSQL_E2E:-}" ]; then
  echo "SELECT set_config('app.is_system','true',false); UPDATE users.users SET is_blocked = true, blocked_reason = 'strikes', blocked_at = now() WHERE uid = '$U_UID';" | $PSQL_E2E >/dev/null
  code=$(curl -s "${U[@]}" "${J[@]}" -X PATCH "$EX/$EID/" -d '{"comment":"bloquejat"}' | json_field code)
  [ "$code" = "user_blocked" ] && ok "bloquejat: PATCH -> code user_blocked" || fail "bloquejat: PATCH -> code '$code'"
  check "bloquejat: POST -> 403" 403 "${U[@]}" "${J[@]}" -X POST "$EX/" -d "$(body "$R1" "Una altra" 2)"
  check "bloquejat: GET -> 200" 200 "${U[@]}" "$EX/?refuge_id=$R1"
  before_del=$(avg "$R1")
  check "bloquejat: DELETE de la seva -> 200" 200 "${U[@]}" -X DELETE "$EX/$EID/"
  [ "$(avg "$R1")" = "$before_del" ] && ok "esborrar una experiència no toca la mitjana" || fail "la mitjana ha canviat en esborrar"
  check "després del DELETE: PATCH -> 404" 404 "${O[@]}" "${J[@]}" -X PATCH "$EX/$EID/" -d '{"comment":"x"}'
else
  echo "SALTAT bloqueig i mitjana (sense PSQL_E2E)"
fi

# --- Esborrat d'usuari: les seves experiències desapareixen
ZE=$(curl -s -m 30 "${Z[@]}" "${J[@]}" -X POST "$EX/" -d "$(body "$R1" "De Z" 2)" | python3 -c "import sys, json; print(json.load(sys.stdin)['experience']['id'])" 2>/dev/null)
[ -n "$ZE" ] && ok "Z crea una experiència" || fail "Z no ha pogut crear l'experiència"
check "DELETE /users/Z/ -> 204" 204 "${Z[@]}" -X DELETE "$API/users/$Z_UID/"
check_json "l'experiència de Z ja no surt a la llista" "'$ZE' not in [x['id'] for x in d['experiences']]" "${O[@]}" "$EX/?refuge_id=$R1"

# --- Intents de pujada (R2 fictici: només la part que no puja bytes)
UI="$API/media/upload-intents"
check "intents sense token -> 401" 401 "${J[@]}" -X POST "$UI/" -d '{}'
check "intents cos buit -> 400" 400 "${O[@]}" "${J[@]}" -X POST "$UI/" -d '{}'
intent=$(curl -s -m 30 "${O[@]}" "${J[@]}" -X POST "$UI/" -d "{\"target\":\"experience\",\"refuge_id\":\"$R1\",\"experience_id\":\"$O_EID\",\"rights_confirmed\":true,\"files\":[{\"content_type\":\"image/jpeg\",\"size\":1000}]}")
UPID=$(echo "$intent" | python3 -c "import sys, json; print(json.load(sys.stdin)['uploads'][0]['upload_id'])" 2>/dev/null)
[ -n "$UPID" ] && ok "intent per a la seva experiència -> upload_id" || fail "intent: $(echo "$intent" | head -c 300)"
code=$(curl -s -m 30 -o /dev/null -w '%{http_code}' "${Y[@]}" "${J[@]}" -X POST "$UI/" -d "{\"target\":\"refuge\",\"refuge_id\":\"$R1\",\"rights_confirmed\":true,\"files\":[{\"content_type\":\"image/jpeg\",\"size\":1000}]}")
[ "$code" = 403 ] && ok "intent sense edat confirmada -> 403" || fail "intent sense edat: $code"
check_json "confirm d'un id inexistent -> failed missing_object" \
  "d['failed'] == [{'upload_id': '$BAD_ID', 'reason': 'missing_object'}]" \
  "${O[@]}" "${J[@]}" -X POST "$UI/confirm/" -d "{\"upload_ids\":[\"$BAD_ID\"]}"
if [ -n "$UPID" ]; then
  # R2 és fictici i inabastable: el `head_object` de la quarantena falla → 500 `{error, error_id}`, mai `str(e)`
  check_json "confirm amb R2 inabastable -> 500 {error, error_id} sense detalls" \
    "set(d) == {'error', 'error_id'} and '127.0.0.1' not in d['error']" \
    "${O[@]}" "${J[@]}" -X POST "$UI/confirm/" -d "{\"upload_ids\":[\"$UPID\"]}"
fi

# Neteja: l'experiència d'O
curl -s -o /dev/null "${O[@]}" -X DELETE "$EX/$O_EID/"

echo
if [ "$fails" -eq 0 ]; then echo "E2E chunk 7: tot correcte"; else echo "$fails cas(os) fallats"; exit 1; fi
