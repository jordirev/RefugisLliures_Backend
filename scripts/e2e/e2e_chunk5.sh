#!/usr/bin/env bash
# E2E del chunk 5 (reformes a PostgreSQL): creació amb enllaç del grup, validacions, solapament (EXCLUDE → 409),
# reformes d'un dia, group_link només per a creador i participants, unir-se / sortir / expulsar, PATCH amb dates
# combinades (M2), ?active_only (D32), bloqueig i edat a l'escriptura (D35) i esborrat d'usuari (vigents fora).
#
# Requisits: els de e2e_chunk3.sh (BD migrada amb `renovations.0001` i el catàleg, Firebase Auth Emulator).
#   PSQL_E2E='docker exec -i rl-postgres psql -U postgres -d refugisdb_e2e -q'  (bloqueig; si no, se salta)
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
day() { python3 -c "import datetime, zoneinfo; print(datetime.datetime.now(zoneinfo.ZoneInfo('Europe/Madrid')).date() + datetime.timedelta(days=$1))"; }
body() {  # body <refuge> <ini> <fin> [group_link]
  printf '{"refuge_id":"%s","ini_date":"%s","fin_date":"%s","description":"Reforma e2e","materials_needed":"fusta","group_link":"%s"}' \
    "$1" "$2" "$3" "${4:-https://t.me/e2e}"
}

suffix="$(date +%s)"
U_EMAIL="r-user-$suffix@e2e.test"; O_EMAIL="r-other-$suffix@e2e.test"; Y_EMAIL="r-young-$suffix@e2e.test"
Z_EMAIL="r-gone-$suffix@e2e.test"
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

# Un refugi diferent a cada execució (el solapament compta també les reformes d'execucions anteriors)
R1=$(curl -s -m 30 "$API/refuges/" | python3 -c "import sys, json; r = json.load(sys.stdin)['results']; print(r[$suffix % len(r)]['id'])")
[ -n "$R1" ] || { echo "No hi ha refugis carregats" >&2; exit 2; }
BAD_ID="00000000-0000-7000-8000-000000000000"
RN="$API/renovations"
D10=$(day 10); D12=$(day 12); D13=$(day 13); D11=$(day 11); D20=$(day 20)

# --- Autenticació i validació
check "GET /renovations/ sense token -> 401" 401 "$RN/"
check "POST sense group_link -> 400" 400 "${U[@]}" "${J[@]}" -X POST "$RN/" \
  -d "{\"refuge_id\":\"$R1\",\"ini_date\":\"$D10\",\"fin_date\":\"$D12\",\"description\":\"x\"}"
check "POST ini > fin -> 400" 400 "${U[@]}" "${J[@]}" -X POST "$RN/" -d "$(body "$R1" "$D12" "$D10")"
check "POST ini passada -> 400" 400 "${U[@]}" "${J[@]}" -X POST "$RN/" -d "$(body "$R1" "$(day -1)" "$D10")"
check "POST group_link ftp -> 400" 400 "${U[@]}" "${J[@]}" -X POST "$RN/" -d "$(body "$R1" "$D10" "$D12" "ftp://x.y")"
check "POST refugi inexistent -> 404" 404 "${U[@]}" "${J[@]}" -X POST "$RN/" -d "$(body "$BAD_ID" "$D10" "$D12")"
check "POST sense edat confirmada -> 403" 403 "${Y[@]}" "${J[@]}" -X POST "$RN/" -d "$(body "$R1" "$D10" "$D12")"

# --- Creació, solapament i reforma d'un dia
created=$(curl -s -m 30 "${U[@]}" "${J[@]}" -X POST "$RN/" -d "$(body "$R1" "$D10" "$D12")")
RID=$(echo "$created" | json_field id)
if echo "$created" | python3 -c "import sys, json; d = json.load(sys.stdin); sys.exit(0 if d['group_link'] == 'https://t.me/e2e' and d['participants_uids'] == [] and d['creator_uid'] == '$U_UID' else 1)" 2>/dev/null
then ok "POST U -> 201 amb group_link i sense participants"; else fail "POST U: $(echo "$created" | head -c 300)"; fi
check_json "POST solapat (límit inclòs) -> 409 amb la reforma en conflicte" "d['overlapping_renovation']['id'] == '$RID'" \
  "${O[@]}" "${J[@]}" -X POST "$RN/" -d "$(body "$R1" "$D12" "$D20")"
check "POST reforma d'un dia -> 201" 201 "${O[@]}" "${J[@]}" -X POST "$RN/" -d "$(body "$R1" "$D20" "$D20")"

# --- group_link només per a creador i participants
check_json "GET (O, no participant): sense clau group_link" "'group_link' not in d and d['id'] == '$RID'" "${O[@]}" "$RN/$RID/"
check_json "GET (U, creador): amb group_link" "d.get('group_link') == 'https://t.me/e2e'" "${U[@]}" "$RN/$RID/"
check "GET id no UUID -> 404" 404 "${U[@]}" "$RN/abc123/"
check "GET id inexistent -> 404" 404 "${U[@]}" "$RN/$BAD_ID/"

# --- Unir-se
check "unir-se sense edat confirmada (Y) -> 403" 403 "${Y[@]}" -X POST "$RN/$RID/participants/"
check "el creador s'hi uneix -> 400" 400 "${U[@]}" -X POST "$RN/$RID/participants/"
check_json "O s'hi uneix -> 200, participant i veu el group_link" \
  "d['participants_uids'] == ['$O_UID'] and d.get('group_link') == 'https://t.me/e2e'" "${O[@]}" -X POST "$RN/$RID/participants/"
check "O s'hi torna a unir -> 409" 409 "${O[@]}" -X POST "$RN/$RID/participants/"
check_json "llista vigent del refugi (?active_only=true) té les 2" "len(d) == 2" "${U[@]}" "$API/refuges/$R1/renovations/?active_only=true"

# --- PATCH
check "PATCH per O (no creador) -> 403" 403 "${O[@]}" "${J[@]}" -X PATCH "$RN/$RID/" -d '{"description":"no"}'
check "PATCH ini_date posterior a la fin desada -> 400 (M2)" 400 "${U[@]}" "${J[@]}" -X PATCH "$RN/$RID/" -d "{\"ini_date\":\"$D13\"}"
check_json "PATCH U description i fin -> 200" "d['description'] == 'Nova descripcio' and d['fin_date'] == '$D13'" \
  "${U[@]}" "${J[@]}" -X PATCH "$RN/$RID/" -d "{\"description\":\"Nova descripcio\",\"fin_date\":\"$D13\"}"
check_json "PATCH que solapa la reforma d'un dia -> 409" "'overlapping_renovation' in d" \
  "${U[@]}" "${J[@]}" -X PATCH "$RN/$RID/" -d "{\"fin_date\":\"$D20\"}"

# --- Sortir, expulsar
check "O treu un tercer (U) -> 403" 403 "${O[@]}" -X DELETE "$RN/$RID/participants/$U_UID/"
check_json "O surt -> 200 sense participants" "d['participants_uids'] == []" "${O[@]}" -X DELETE "$RN/$RID/participants/$O_UID/"
check "O torna a entrar -> 200" 200 "${O[@]}" -X POST "$RN/$RID/participants/"
check_json "U expulsa O -> 200" "d['participants_uids'] == []" "${U[@]}" -X DELETE "$RN/$RID/participants/$O_UID/"
check "O expulsat intenta tornar -> 403" 403 "${O[@]}" -X POST "$RN/$RID/participants/"
check "U expulsa O de nou (no participant) -> 403" 403 "${U[@]}" -X DELETE "$RN/$RID/participants/$O_UID/"

# --- Bloqueig: no escriu, sí llegeix i esborra el seu
if [ -n "${PSQL_E2E:-}" ]; then
  echo "SELECT set_config('app.is_system','true',false); UPDATE users.users SET is_blocked = true, blocked_reason = 'strikes', blocked_at = now() WHERE uid = '$U_UID';" | $PSQL_E2E >/dev/null
  code=$(curl -s "${U[@]}" "${J[@]}" -X PATCH "$RN/$RID/" -d '{"description":"bloquejat"}' | json_field code)
  [ "$code" = "user_blocked" ] && ok "bloquejat: PATCH -> code user_blocked" || fail "bloquejat: PATCH -> code '$code'"
  check "bloquejat: POST -> 403" 403 "${U[@]}" "${J[@]}" -X POST "$RN/" -d "$(body "$R1" "$(day 40)" "$(day 41)")"
  check "bloquejat: GET -> 200" 200 "${U[@]}" "$RN/$RID/"
  check "bloquejat: DELETE de la seva -> 204" 204 "${U[@]}" -X DELETE "$RN/$RID/"
  check "després del DELETE: 404" 404 "${O[@]}" "$RN/$RID/"
else
  echo "SALTAT bloqueig (sense PSQL_E2E)"
  check "DELETE per O (no creador) -> 403" 403 "${O[@]}" -X DELETE "$RN/$RID/"
  check "DELETE U -> 204" 204 "${U[@]}" -X DELETE "$RN/$RID/"
fi

# --- Esborrat d'usuari: la seva reforma vigent desapareix
ZR=$(curl -s -m 30 "${Z[@]}" "${J[@]}" -X POST "$RN/" -d "$(body "$R1" "$(day 30)" "$(day 31)")" | json_field id)
[ -n "$ZR" ] && ok "Z crea una reforma vigent" || fail "Z no ha pogut crear la reforma"
check "DELETE /users/Z/ -> 204" 204 "${Z[@]}" -X DELETE "$API/users/$Z_UID/"
check "la reforma vigent de Z ja no hi és -> 404" 404 "${O[@]}" "$RN/$ZR/"

# Neteja: la reforma d'un dia d'O
for id in $(curl -s "${O[@]}" "$API/refuges/$R1/renovations/" | python3 -c "import sys, json; print(' '.join(x['id'] for x in json.load(sys.stdin) if x['creator_uid'] == '$O_UID'))"); do
  curl -s -o /dev/null "${O[@]}" -X DELETE "$RN/$id/"
done

echo
if [ "$fails" -eq 0 ]; then echo "E2E chunk 5: tot correcte"; else echo "$fails cas(os) fallats"; exit 1; fi
