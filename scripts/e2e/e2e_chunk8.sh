#!/usr/bin/env bash
# E2E del chunk 8 (propostes de refugi a PostgreSQL): permisos (admin per llistar/aprovar/rebutjar), validacions,
# 409 `possible_duplicates` en proposar un refugi a prop d'un altre amb nom semblant, cicle complet create → update →
# reject → delete aprovat per un admin (el refugi apareix, canvia i desapareix; les altres pendents queden rebutjades),
# doble revisió (409), bloqueig i edat en crear, i esborrat d'usuari (creator_uid 'unknown' i comentari NULL).
#
# Requisits: els de e2e_chunk3.sh (BD migrada amb `proposals.0001` i el catàleg, Firebase Auth Emulator). R2 és
# fictici: els refugis creats per l'e2e no tenen mitjans.
#   PSQL_E2E='docker exec -i rl-postgres psql -U postgres -d refugisdb_e2e -q'  (bloqueig)
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
U_EMAIL="p-user-$suffix@e2e.test"; A_EMAIL="p-admin-$suffix@e2e.test"; Y_EMAIL="p-young-$suffix@e2e.test"
Z_EMAIL="p-gone-$suffix@e2e.test"
U_UID=$(ensure_user "$U_EMAIL"); A_UID=$(ensure_user "$A_EMAIL"); Y_UID=$(ensure_user "$Y_EMAIL"); Z_UID=$(ensure_user "$Z_EMAIL")
[ -n "$U_UID" ] && [ -n "$A_UID" ] && [ -n "$Y_UID" ] && [ -n "$Z_UID" ] || { echo "No s'han pogut crear els usuaris a l'emulador" >&2; exit 2; }
curl -s -o /dev/null -X POST "$IDT/projects/$PROJECT_ID/accounts:update" \
  -H 'Authorization: Bearer owner' -H 'Content-Type: application/json' \
  -d "{\"localId\":\"$A_UID\",\"customAttributes\":\"{\\\"role\\\":\\\"admin\\\"}\"}"
tok() { auth_call accounts:signInWithPassword "$1" | json_field idToken; }
U=(-H "Authorization: Bearer $(tok "$U_EMAIL")"); A=(-H "Authorization: Bearer $(tok "$A_EMAIL")")
Y=(-H "Authorization: Bearer $(tok "$Y_EMAIL")"); Z=(-H "Authorization: Bearer $(tok "$Z_EMAIL")")
J=(-H 'Content-Type: application/json')
for who in U A Z; do
  declare -n H=$who
  curl -s -o /dev/null "${H[@]}" "${J[@]}" -X POST "$API/users/" -d '{"username":"E2E","birth_date":"1990-01-01"}'
done
curl -s -o /dev/null "${Y[@]}" "${J[@]}" -X POST "$API/users/" -d '{"username":"Sense edat"}'

P="$API/refuges-proposals"
MINE="$API/my-refuges-proposals/"
BAD_ID="00000000-0000-7000-8000-000000000000"
pid() { python3 -c "import sys, json; print(json.load(sys.stdin).get('id', ''))" 2>/dev/null; }
# Proposta de creació: nom únic per execució i coordenades lluny de qualsevol refugi carregat (Atlàntic)
NEW_NAME="Cabana E2E $suffix"
create_body() {  # $1 nom, $2 long, $3 lat
  printf '{"action":"create","payload":{"name":"%s","coord":{"long":%s,"lat":%s},"altitude":1800,"places":12,"type":"non gardé","info_comp":{"cheminee":1}},"comment":"Proposta e2e"}' "$1" "$2" "$3"
}
proposal() {  # estat de la proposta $1 des del llistat d'admin
  curl -s -m 30 "${A[@]}" "$P/" | python3 -c "
import sys, json
p = [x for x in json.load(sys.stdin) if x['id'] == '$1']
print(json.dumps(p[0]) if p else '{}')"
}
check_proposal() {  # $1 descripció, $2 id, $3 expressió sobre d
  if proposal "$2" | python3 -c "import sys, json; d = json.load(sys.stdin); sys.exit(0 if ($3) else 1)" 2>/dev/null
  then ok "$1"; else fail "$1: $(proposal "$2" | head -c 300)"; fi
}

# --- Autenticació i permisos
check "GET llistat sense token -> 401" 401 "$P/"
check "POST sense token -> 401" 401 "${J[@]}" -X POST "$P/" -d "$(create_body "$NEW_NAME" -30 45)"
check "GET llistat usuari normal -> 403" 403 "${U[@]}" "$P/"
check "GET llistat admin -> 200" 200 "${A[@]}" "$P/"
check "GET llistat status invàlid -> 400" 400 "${A[@]}" "$P/?status=foo"
check "GET pròpies -> 200" 200 "${U[@]}" "$MINE"

# --- Validacions
check "POST action desconeguda -> 400" 400 "${U[@]}" "${J[@]}" -X POST "$P/" -d '{"action":"x","payload":{},"comment":"c"}'
check "POST create sense nom -> 400" 400 "${U[@]}" "${J[@]}" -X POST "$P/" \
  -d '{"action":"create","payload":{"coord":{"long":1,"lat":42}},"comment":"c"}'
check "POST update refugi inexistent -> 400" 400 "${U[@]}" "${J[@]}" -X POST "$P/" \
  -d "{\"action\":\"update\",\"refuge_id\":\"$BAD_ID\",\"payload\":{\"places\":3},\"comment\":\"c\"}"
check "POST sense edat confirmada -> 403" 403 "${Y[@]}" "${J[@]}" -X POST "$P/" -d "$(create_body "$NEW_NAME" -30 45)"

# --- Duplicats: el mateix nom al mateix punt que un refugi existent -> 409 amb el refugi a la llista
read -r R1 R1_NAME R1_LONG R1_LAT < <(curl -s -m 30 "$API/refuges/" | python3 -c "
import sys, json
r = json.load(sys.stdin)['results'][($suffix + 3) % 20]
print(r['id'], json.dumps(r['name']), r['coord']['long'], r['coord']['lat'])")
[ -n "${R1:-}" ] || { echo "No hi ha refugis carregats" >&2; exit 2; }
dup=$(printf '{"action":"create","payload":{"name":%s,"coord":{"long":%s,"lat":%s}},"comment":"Duplicat"}' "$R1_NAME" "$R1_LONG" "$R1_LAT")
check_json "create a sobre d'un refugi amb el mateix nom -> possible_duplicates" \
  "d['code'] == 'possible_duplicates' and '$R1' in [x['id'] for x in d['possible_duplicates']] and all(x['distance_m'] <= 500 for x in d['possible_duplicates'])" \
  "${U[@]}" "${J[@]}" -X POST "$P/" -d "$dup"
check "create al mateix punt però amb nom molt diferent -> 201" 201 "${U[@]}" "${J[@]}" -X POST "$P/" \
  -d "$(printf '{"action":"create","payload":{"name":"Zzqx %s","coord":{"long":%s,"lat":%s}},"comment":"No és duplicat"}' "$suffix" "$R1_LONG" "$R1_LAT")"

# --- Cicle: create aprovat -> el refugi existeix
P1=$(curl -s -m 30 "${U[@]}" "${J[@]}" -X POST "$P/" -d "$(create_body "$NEW_NAME" -30 45)" | pid)
[ -n "$P1" ] && ok "U proposa un refugi nou" || fail "no s'ha pogut crear la proposta"
check_json "la proposta surt a les pròpies de U, pending" "any(x['id'] == '$P1' and x['status'] == 'pending' and x['creator_uid'] == '$U_UID' for x in d)" "${U[@]}" "$MINE"
check "usuari normal aprova -> 403" 403 "${U[@]}" -X POST "$P/$P1/approve/"
check "aprovar inexistent -> 404" 404 "${A[@]}" -X POST "$P/$BAD_ID/approve/"
check "admin aprova el create -> 200" 200 "${A[@]}" -X POST "$P/$P1/approve/"
check "segona aprovació -> 409" 409 "${A[@]}" -X POST "$P/$P1/approve/"
check "rebutjar una aprovada -> 409" 409 "${A[@]}" "${J[@]}" -X POST "$P/$P1/reject/" -d '{}'
NEW_R=$(proposal "$P1" | python3 -c "import sys, json; print(json.load(sys.stdin).get('refuge_id') or '')")
[ -n "$NEW_R" ] && ok "la proposta aprovada apunta al refugi nou" || fail "refuge_id buit després d'aprovar"
check_json "el refugi nou existeix amb les dades proposades" \
  "d['name'] == '$NEW_NAME' and d['places'] == 12 and d['info_comp']['cheminee'] == 1" "$API/refuges/$NEW_R/"
check_json "proposar-lo de nou al mateix lloc -> possible_duplicates" \
  "d['code'] == 'possible_duplicates' and d['possible_duplicates'][0]['id'] == '$NEW_R'" \
  "${U[@]}" "${J[@]}" -X POST "$P/" -d "$(create_body "$NEW_NAME" -30.0001 45.0001)"

# --- Update aprovat i un altre rebutjat
upd() { printf '{"action":"update","refuge_id":"%s","payload":{"places":%s},"comment":"Més places"}' "$NEW_R" "$1"; }
P2=$(curl -s -m 30 "${U[@]}" "${J[@]}" -X POST "$P/" -d "$(upd 33)" | pid)
check_proposal "update desa la foto del refugi" "$P2" "d['refuge_snapshot']['name'] == '$NEW_NAME' and d['refuge_snapshot']['places'] == 12"
check "admin aprova l'update -> 200" 200 "${A[@]}" -X POST "$P/$P2/approve/"
check_json "el refugi té 33 places" "d['places'] == 33" "$API/refuges/$NEW_R/"
P3=$(curl -s -m 30 "${U[@]}" "${J[@]}" -X POST "$P/" -d "$(upd 1)" | pid)
check "rebutjar amb motiu massa llarg -> 400" 400 "${A[@]}" "${J[@]}" -X POST "$P/$P3/reject/" \
  -d "{\"reason\":\"$(python3 -c "print('x' * 2001)")\"}"
check "admin rebutja l'update -> 200" 200 "${A[@]}" "${J[@]}" -X POST "$P/$P3/reject/" -d '{"reason":"Dades incorrectes"}'
check_proposal "rebutjada amb motiu i revisor" "$P3" \
  "d['status'] == 'rejected' and d['rejection_reason'] == 'Dades incorrectes' and d['reviewer_uid'] == '$A_UID'"
check_json "el rebuig no toca el refugi" "d['places'] == 33" "$API/refuges/$NEW_R/"

# --- Bloqueig: no pot proposar, sí veure les seves
if [ -n "${PSQL_E2E:-}" ]; then
  echo "SELECT set_config('app.is_system','true',false); UPDATE users.users SET is_blocked = true, blocked_reason = 'strikes', blocked_at = now() WHERE uid = '$U_UID';" | $PSQL_E2E >/dev/null
  code=$(curl -s "${U[@]}" "${J[@]}" -X POST "$P/" -d "$(upd 2)" | json_field code)
  [ "$code" = "user_blocked" ] && ok "bloquejat: POST -> code user_blocked" || fail "bloquejat: POST -> code '$code'"
  check "bloquejat: GET pròpies -> 200" 200 "${U[@]}" "$MINE"
  echo "SELECT set_config('app.is_system','true',false); UPDATE users.users SET is_blocked = false, blocked_reason = NULL, blocked_at = NULL WHERE uid = '$U_UID';" | $PSQL_E2E >/dev/null
else
  echo "SALTAT bloqueig (sense PSQL_E2E)"
fi

# --- Esborrat d'usuari: la proposta queda amb creator 'unknown' i sense comentari
PZ=$(curl -s -m 30 "${Z[@]}" "${J[@]}" -X POST "$P/" -d "$(upd 7)" | pid)
[ -n "$PZ" ] && ok "Z proposa un canvi" || fail "Z no ha pogut proposar"
check "DELETE /users/Z/ -> 204" 204 "${Z[@]}" -X DELETE "$API/users/$Z_UID/"
check_proposal "la proposta de Z: creator 'unknown' i comentari NULL" "$PZ" \
  "d['creator_uid'] == 'unknown' and d['comment'] is None and d['status'] == 'pending'"

# --- Delete aprovat: el refugi desapareix i les altres pendents queden rebutjades
P4=$(curl -s -m 30 "${U[@]}" "${J[@]}" -X POST "$P/" -d "{\"action\":\"delete\",\"refuge_id\":\"$NEW_R\",\"comment\":\"Ja no existeix\"}" | pid)
[ -n "$P4" ] && ok "U proposa esborrar el refugi" || fail "no s'ha pogut proposar l'esborrat"
check "admin aprova el delete -> 200" 200 "${A[@]}" -X POST "$P/$P4/approve/"
check "el refugi ja no existeix -> 404" 404 "$API/refuges/$NEW_R/"
check_proposal "la proposta de Z queda rebutjada pel delete" "$PZ" \
  "d['status'] == 'rejected' and d['rejection_reason'] == 'refuge has been deleted' and d['reviewer_uid'] is None"
check_proposal "les propostes antigues conserven la foto però perden refuge_id" "$P2" \
  "d['refuge_id'] is None and d['refuge_snapshot']['name'] == '$NEW_NAME'"

echo
if [ "$fails" -eq 0 ]; then echo "E2E chunk 8: tot correcte"; else echo "$fails cas(os) fallats"; exit 1; fi
