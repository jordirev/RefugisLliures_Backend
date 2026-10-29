#!/usr/bin/env bash
# E2E del chunk 4 (visites a PostgreSQL): inscripció (ON CONFLICT), totals per la vista sense exposar participants,
# PATCH/DELETE propis, /users/{uid}/visits/, límits de data (passada, > 12 mesos D36, format estricte), num_visitors
# (1..100, D27), bloqueig i edat a POST/PATCH, l'esborrat de la visita en sortir l'últim participant (trigger, visits.0002) i el job diari (process_yesterday_visits, D28) si hi ha `EMANAGE`.
#
# Requisits: els de e2e_chunk3.sh (BD migrada amb `visits.0002` i el catàleg, Firebase Auth Emulator).
#   PSQL_E2E='docker exec -i rl-postgres psql -U postgres -d refugisdb_e2e -q'  (bloqueig i visita d'ahir; si no, se salta)
#   EMANAGE='<ordre que executa manage.py contra la BD e2e>'                   (job diari; si no, se salta)
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
day() { python3 -c "import datetime, zoneinfo; print(datetime.datetime.now(zoneinfo.ZoneInfo('Europe/Madrid')).date() + datetime.timedelta(days=$1))"; }

suffix="$(date +%s)"
U_EMAIL="v-user-$suffix@e2e.test"; O_EMAIL="v-other-$suffix@e2e.test"; Y_EMAIL="v-young-$suffix@e2e.test"
U_UID=$(ensure_user "$U_EMAIL"); O_UID=$(ensure_user "$O_EMAIL"); Y_UID=$(ensure_user "$Y_EMAIL")
[ -n "$U_UID" ] && [ -n "$O_UID" ] || { echo "No s'han pogut crear els usuaris a l'emulador" >&2; exit 2; }
tok() { auth_call accounts:signInWithPassword "$1" | json_field idToken; }
U=(-H "Authorization: Bearer $(tok "$U_EMAIL")"); O=(-H "Authorization: Bearer $(tok "$O_EMAIL")")
Y=(-H "Authorization: Bearer $(tok "$Y_EMAIL")")
J=(-H 'Content-Type: application/json')
for who in U O; do
  declare -n H=$who
  curl -s -o /dev/null "${H[@]}" "${J[@]}" -X POST "$API/users/" -d '{"username":"E2E","birth_date":"1990-01-01"}'
done
curl -s -o /dev/null "${Y[@]}" "${J[@]}" -X POST "$API/users/" -d '{"username":"Sense edat"}'

R1=$(curl -s -m 30 "$API/refuges/" | python3 -c "import sys, json; print(json.load(sys.stdin)['results'][2]['id'])")
[ -n "$R1" ] || { echo "No hi ha refugis carregats" >&2; exit 2; }
BAD_REF="00000000-0000-7000-8000-000000000000"
D1=$(day 3); V="$API/refuges/$R1/visits"
FAR=$(python3 -c "
import datetime, zoneinfo
t = datetime.datetime.now(zoneinfo.ZoneInfo('Europe/Madrid')).date()
y, m = divmod(t.year * 12 + t.month - 1 + 12, 12); m += 1
import calendar; print(datetime.date(y, m, min(t.day, calendar.monthrange(y, m)[1])))")
FAR1=$(python3 -c "import datetime; print(datetime.date.fromisoformat('$FAR') + datetime.timedelta(days=1))")

# --- Autenticació, validació i límits
check "GET sense token -> 401" 401 "$V/"
check "GET refugi inexistent -> 404" 404 "${U[@]}" "$API/refuges/$BAD_REF/visits/"
check "POST data passada -> 400" 400 "${U[@]}" "${J[@]}" -X POST "$V/$(day -1)/" -d '{"num_visitors":1}'
check "POST data laxa (20301231) -> 400" 400 "${U[@]}" "${J[@]}" -X POST "$V/20301231/" -d '{"num_visitors":1}'
check "POST a mes de 12 mesos vista -> 400 (D36)" 400 "${U[@]}" "${J[@]}" -X POST "$V/$FAR1/" -d '{"num_visitors":1}'
check "POST num_visitors 0 -> 400" 400 "${U[@]}" "${J[@]}" -X POST "$V/$D1/" -d '{"num_visitors":0}'
check "POST num_visitors 101 -> 400 (D27)" 400 "${U[@]}" "${J[@]}" -X POST "$V/$D1/" -d '{"num_visitors":101}'
check "POST sense edat confirmada -> 403" 403 "${Y[@]}" "${J[@]}" -X POST "$V/$D1/" -d '{"num_visitors":1}'
check "POST refugi inexistent -> 404" 404 "${U[@]}" "${J[@]}" -X POST "$API/refuges/$BAD_REF/visits/$D1/" -d '{"num_visitors":1}'

# --- Inscripció i totals
check_json "POST U amb 3 -> visita amb total 3" "d['visit']['total_visitors'] == 3 and d['visit']['num_visitors'] == 3 and d['visit']['is_visitor']" \
  "${U[@]}" "${J[@]}" -X POST "$V/$D1/" -d '{"num_visitors":3}'
check "POST U de nou -> 400 ja registrat" 400 "${U[@]}" "${J[@]}" -X POST "$V/$D1/" -d '{"num_visitors":1}'
check_json "POST O amb 2 -> total 5" "d['visit']['total_visitors'] == 5 and d['visit']['num_visitors'] == 2" \
  "${O[@]}" "${J[@]}" -X POST "$V/$D1/" -d '{"num_visitors":2}'
check "POST al limit de 12 mesos -> 201" 201 "${U[@]}" "${J[@]}" -X POST "$V/$FAR/" -d '{"num_visitors":1}'
check_json "GET (U): total 5, els seus 3, sense participants" \
  "[x for x in d['result'] if x['date'] == '$D1'][0] == {'date': '$D1', 'refuge_id': '$R1', 'total_visitors': 5, 'is_visitor': True, 'num_visitors': 3}" \
  "${U[@]}" "$V/"
check_json "GET (Y sense visita): is_visitor false, num 0" \
  "[x for x in d['result'] if x['date'] == '$D1'][0]['is_visitor'] is False and [x for x in d['result'] if x['date'] == '$D1'][0]['num_visitors'] == 0" \
  "${Y[@]}" "$V/"
check "GET visites d'un altre usuari -> 403" 403 "${O[@]}" "$API/users/$U_UID/visits/"
check_json "GET /users/U/visits/: 2 visites ordenades per data desc" \
  "[x['date'] for x in d['result']] == ['$FAR', '$D1']" "${U[@]}" "$API/users/$U_UID/visits/"

# --- PATCH i DELETE propis
check_json "PATCH U a 4 -> total 6" "d['visit']['total_visitors'] == 6 and d['visit']['num_visitors'] == 4" \
  "${U[@]}" "${J[@]}" -X PATCH "$V/$D1/" -d '{"num_visitors":4}'
check "PATCH sense edat confirmada (Y) -> 403" 403 "${Y[@]}" "${J[@]}" -X PATCH "$V/$D1/" -d '{"num_visitors":1}'
check "PATCH data sense visita -> 404" 404 "${U[@]}" "${J[@]}" -X PATCH "$V/$(day 9)/" -d '{"num_visitors":1}'
check "DELETE O -> 200" 200 "${O[@]}" -X DELETE "$V/$D1/"
check_json "després del DELETE de O: total 4" "[x for x in d['result'] if x['date'] == '$D1'][0]['total_visitors'] == 4" "${U[@]}" "$V/"
check "DELETE O de nou -> 400 no registrat" 400 "${O[@]}" -X DELETE "$V/$D1/"
check "PATCH sense estar-hi (O) -> 400" 400 "${O[@]}" "${J[@]}" -X PATCH "$V/$D1/" -d '{"num_visitors":1}'

# --- Visita buida: en sortir l'últim participant la visita s'esborra (trigger de la BD, visits.0002)
D7=$(day 7)
check "POST O a una visita nova -> 201" 201 "${O[@]}" "${J[@]}" -X POST "$V/$D7/" -d '{"num_visitors":2}'
check "DELETE O (l'últim) -> 200" 200 "${O[@]}" -X DELETE "$V/$D7/"
check_json "GET: la visita sense participants ja no surt" "all(x['date'] != '$D7' for x in d['result'])" "${U[@]}" "$V/"
check_json "GET /users/O/visits/: no en queda cap" "d['result'] == []" "${O[@]}" "$API/users/$O_UID/visits/"
check "DELETE de la visita ja esborrada -> 404" 404 "${O[@]}" -X DELETE "$V/$D7/"
check_json "tornar-hi: es recrea amb total 1" "d['visit']['total_visitors'] == 1" "${O[@]}" "${J[@]}" -X POST "$V/$D7/" -d '{"num_visitors":1}'
check "DELETE O -> 200 (deixa la visita buida)" 200 "${O[@]}" -X DELETE "$V/$D7/"
if [ -n "${PSQL_E2E:-}" ]; then
  n=$(echo "SELECT count(*) FROM activity.refuge_visits WHERE refuge_id = '$R1' AND visit_date = '$D7';" | $PSQL_E2E -At)
  [ "$n" = "0" ] && ok "BD: la visita sense participants no existeix a activity.refuge_visits" || fail "BD: la visita buida existeix encara ($n files)"
fi

# --- Bloqueig: no escriu, sí llegeix i surt
if [ -n "${PSQL_E2E:-}" ]; then
  echo "SELECT set_config('app.is_system','true',false); UPDATE users.users SET is_blocked = true, blocked_reason = 'strikes', blocked_at = now() WHERE uid = '$U_UID';" | $PSQL_E2E >/dev/null
  code=$(curl -s "${U[@]}" "${J[@]}" -X PATCH "$V/$D1/" -d '{"num_visitors":2}' | json_field code)
  [ "$code" = "user_blocked" ] && ok "bloquejat: PATCH -> code user_blocked" || fail "bloquejat: PATCH -> code '$code'"
  check "bloquejat: POST -> 403" 403 "${U[@]}" "${J[@]}" -X POST "$V/$(day 5)/" -d '{"num_visitors":1}'
  check "bloquejat: GET -> 200" 200 "${U[@]}" "$V/"
  check "bloquejat: DELETE propi -> 200" 200 "${U[@]}" -X DELETE "$V/$D1/"
  n=$(echo "SELECT count(*) FROM activity.refuge_visits WHERE refuge_id = '$R1' AND visit_date = '$D1';" | $PSQL_E2E -At)
  [ "$n" = "0" ] && ok "BD: D1 s'ha quedat sense participants i s'ha esborrat" || fail "BD: D1 buida existeix encara ($n files)"
else
  echo "SALTAT bloqueig (sense PSQL_E2E)"
fi

# --- Job diari: la visita d'ahir passa a user_visited_refuges
if [ -n "${PSQL_E2E:-}" ] && [ -n "${EMANAGE:-}" ]; then
  Y1=$(day -1)
  echo "SELECT set_config('app.is_system','true',false);
        INSERT INTO activity.refuge_visits (refuge_id, visit_date) VALUES ('$R1', '$Y1') ON CONFLICT DO NOTHING;
        INSERT INTO activity.refuge_visit_participants (visit_id, user_uid, num_visitors)
          SELECT id, '$O_UID', 2 FROM activity.refuge_visits WHERE refuge_id = '$R1' AND visit_date = '$Y1';" | $PSQL_E2E >/dev/null
  if $EMANAGE process_yesterday_visits >/dev/null 2>&1; then ok "job diari surt amb codi 0"; else fail "job diari ha fallat"; fi
  check_json "després del job: O té el refugi a visitats" "'$R1' in d['visited_refuges']" "${O[@]}" "$API/users/$O_UID/"
else
  echo "SALTAT job diari (sense PSQL_E2E/EMANAGE)"
fi

echo
if [ "$fails" -eq 0 ]; then echo "E2E chunk 4: tot correcte"; else echo "$fails cas(os) fallats"; exit 1; fi
