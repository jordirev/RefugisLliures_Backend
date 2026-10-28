#!/usr/bin/env bash
# E2E del chunk 10 (procediment únic d'esborrat d'usuari, D42): un usuari amb contingut a tots els dominis s'esborra i
# no en queda res (excepte les anonimitzacions documentades), el compte de Firebase desapareix, la mateixa petició és
# idempotent (204 sense perfil), un mitjà ocult només per les seves denúncies torna a la cua (denúncia automàtica),
# permisos (401/403) i R2 inabastable (500, tot desfet, compte conservat).
#
# Requisits: els de e2e_chunk3.sh (BD migrada fins al chunk 9, Firebase Auth Emulator) i
#   PSQL_E2E='docker exec -i rl-postgres psql -U postgres -d refugisdb_e2e -q'
# R2 és fictici. Cossos ASCII (Git Bash de Windows malmet els arguments no ASCII de curl). Cap credencial real.
set -uo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
AUTH_EMULATOR="${AUTH_EMULATOR:-http://localhost:9099}"
PASSWORD="e2e-pass-123"   # només per a l'emulador
IDT="$AUTH_EMULATOR/identitytoolkit.googleapis.com/v1"
API="$BASE_URL/api"
fails=0
[ -n "${PSQL_E2E:-}" ] || { echo "Cal PSQL_E2E" >&2; exit 2; }

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
sql() { echo "$1" | $PSQL_E2E -tA; }
check_sql() {
  local got
  got=$(sql "$2")
  [ "$got" = "$3" ] && ok "$1" || fail "$1: '$got' (esperat '$3')"
}
day() { python3 -c "import datetime, zoneinfo; print(datetime.datetime.now(zoneinfo.ZoneInfo('Europe/Madrid')).date() + datetime.timedelta(days=$1))"; }

suffix="$(date +%s)"
declare -A EMAIL UID_
for who in U C N F; do
  EMAIL[$who]="d-$(echo "$who" | tr 'A-Z' 'a-z')-$suffix@e2e.test"
  UID_[$who]=$(ensure_user "${EMAIL[$who]}")
  [ -n "${UID_[$who]}" ] || { echo "No s'ha pogut crear $who a l'emulador" >&2; exit 2; }
done
tok() { auth_call accounts:signInWithPassword "$1" | json_field idToken; }
for who in U C N F; do declare -a "H_$who=(-H 'Authorization: Bearer $(tok "${EMAIL[$who]}")')"; done
J=(-H 'Content-Type: application/json')
for who in U C F; do
  declare -n H="H_$who"
  curl -s -o /dev/null "${H[@]}" "${J[@]}" -X POST "$API/users/" -d '{"username":"E2E","birth_date":"1990-01-01"}'
done
# N no crea perfil (només compte de Firebase)

R=$(curl -s -m 30 "$API/refuges/" | python3 -c "import sys, json; r = json.load(sys.stdin)['results']; print(r[($suffix + 17) % len(r)]['id'])")
[ -n "$R" ] || { echo "No hi ha refugis carregats" >&2; exit 2; }
U="${UID_[U]}"

# --- Contingut de U a tots els dominis
curl -s -o /dev/null "${H_U[@]}" "${J[@]}" -X POST -d "{\"refuge_id\":\"$R\"}" "$API/users/$U/favorite-refuges/"
curl -s -o /dev/null "${H_U[@]}" "${J[@]}" -X POST "$API/refuges/$R/visits/$(day 4)/" -d '{"num_visitors":2}'
curl -s -o /dev/null "${H_U[@]}" "${J[@]}" -X POST "$API/renovations/" \
  -d "$(printf '{"refuge_id":"%s","ini_date":"%s","fin_date":"%s","description":"Reforma e2e","materials_needed":"fusta","group_link":"https://t.me/e2e%s"}' "$R" "$(day 10)" "$(day 12)" "$suffix")"
curl -s -o /dev/null "${H_U[@]}" "${J[@]}" -X POST "$API/doubts/" -d "{\"refuge_id\":\"$R\",\"message\":\"Hi ha aigua?\"}"
curl -s -o /dev/null "${H_U[@]}" "${J[@]}" -X POST "$API/experiences/" -d "{\"refuge_id\":\"$R\",\"comment\":\"Molt be\",\"condition\":2}"
PID=$(curl -s -m 30 "${H_U[@]}" "${J[@]}" -X POST "$API/refuges-proposals/" \
  -d "{\"action\":\"update\",\"refuge_id\":\"$R\",\"payload\":{\"places\":9},\"comment\":\"Comentari personal de U\"}" | json_field id)
[ -n "$PID" ] && ok "U té contingut a preferits, visites, reformes, dubtes, experiències i propostes" || fail "no s'ha pogut crear la proposta de U"
# Mitjà de C ocult només per una denúncia de U (motiu greu: ocultació immediata)
MC="refugis-lliures/$R/e2e-del-$suffix.webp"
sql "INSERT INTO refuges.refuge_media (key, refuge_id, creator_uid, media_type, content_type, rights_confirmed_at) VALUES ('$MC', '$R', '${UID_[C]}', 'image', 'image/webp', now());" >/dev/null
check_json "U denuncia el mitjà de C (my_image) -> ocult" "d['media_hidden'] is True" \
  "${H_U[@]}" "${J[@]}" -X POST "$API/media/reports/" -d "{\"refuge_id\":\"$R\",\"media_key\":\"$MC\",\"reason\":\"my_image\"}"
count_u() {
  sql "SELECT (SELECT count(*) FROM users.user_favourite_refuges WHERE user_uid = '$U')
            + (SELECT count(*) FROM activity.refuge_visit_participants WHERE user_uid = '$U')
            + (SELECT count(*) FROM activity.renovations WHERE creator_uid = '$U')
            + (SELECT count(*) FROM activity.doubts WHERE creator_uid = '$U')
            + (SELECT count(*) FROM activity.experiences WHERE creator_uid = '$U')
            + (SELECT count(*) FROM proposals.refuge_proposals WHERE creator_uid = '$U')
            + (SELECT count(*) FROM moderation.media_reports WHERE reporter_uid = '$U')
            + (SELECT count(*) FROM audit.audit_logs WHERE actor_uid = '$U' OR subject_uid = '$U')
            + (SELECT count(*) FROM users.users WHERE uid = '$U');"
}
before=$(count_u)
[ "${before:-0}" -ge 8 ] && ok "files de U abans d'esborrar: $before" || fail "massa poques files de U: $before"
deleted_before=$(sql "SELECT count(*) FROM audit.audit_logs WHERE action = 'user.deleted';")

# --- Permisos
check "DELETE sense token -> 401" 401 -X DELETE "$API/users/$U/"
check "DELETE d'un altre usuari -> 403" 403 "${H_C[@]}" -X DELETE "$API/users/$U/"

# --- Esborrat
check "DELETE propi -> 204" 204 "${H_U[@]}" -X DELETE "$API/users/$U/"
[ "$(count_u)" = "0" ] && ok "no queda cap fila que porti l'UID de U" || fail "queden $(count_u) files de U"
check_sql "la proposta es conserva anònima i sense comentari" \
  "SELECT creator_uid IS NULL AND comment IS NULL FROM proposals.refuge_proposals WHERE id = '$PID';" "t"
check_sql "una sola entrada user.deleted nova, sense identificadors" \
  "SELECT count(*) FROM audit.audit_logs WHERE action = 'user.deleted' AND actor_uid IS NULL AND subject_uid IS NULL AND target_id IS NULL AND metadata = '{}'::jsonb;" \
  "$((deleted_before + 1))"
check_sql "el mitjà de C torna a la cua: denúncia automàtica reporter_account_deleted" \
  "SELECT count(*) FROM moderation.media_reports WHERE media_key = '$MC' AND source = 'automatic' AND status = 'pending' AND details = 'reporter_account_deleted' AND reporter_uid IS NULL;" "1"
check_sql "el mitjà de C continua ocult" "SELECT status FROM refuges.refuge_media WHERE key = '$MC';" "hidden_pending_review"
code=$(auth_call accounts:signInWithPassword "${EMAIL[U]}" | python3 -c "import sys, json; print(json.load(sys.stdin).get('error', {}).get('message', 'OK'))")
[ "$code" = "EMAIL_NOT_FOUND" ] && ok "el compte de Firebase de U ja no existeix" || fail "login de U després d'esborrar: $code"
check "repetir el DELETE amb el mateix token -> 204 (idempotent)" 204 "${H_U[@]}" -X DELETE "$API/users/$U/"
check_sql "la repetició no escriu cap user.deleted més" \
  "SELECT count(*) FROM audit.audit_logs WHERE action = 'user.deleted';" "$((deleted_before + 1))"

# --- Compte de Firebase sense perfil: DELETE propi -> 204 i el compte desapareix
check "N sense perfil: DELETE propi -> 204" 204 "${H_N[@]}" -X DELETE "$API/users/${UID_[N]}/"
code=$(auth_call accounts:signInWithPassword "${EMAIL[N]}" | python3 -c "import sys, json; print(json.load(sys.stdin).get('error', {}).get('message', 'OK'))")
[ "$code" = "EMAIL_NOT_FOUND" ] && ok "el compte de Firebase de N ja no existeix" || fail "login de N: $code"
check "N sense perfil: GET del perfil -> 403" 403 "${H_N[@]}" "$API/users/${UID_[N]}/"

# --- R2 inabastable: F té un mitjà propi -> 500 i res esborrat
MF="refugis-lliures/$R/e2e-del-f-$suffix.webp"
sql "INSERT INTO refuges.refuge_media (key, refuge_id, creator_uid, media_type, content_type, rights_confirmed_at) VALUES ('$MF', '$R', '${UID_[F]}', 'image', 'image/webp', now());" >/dev/null
check_json "F amb un mitjà i R2 inabastable -> 500 {error, error_id}" "set(d) == {'error', 'error_id'}" "${H_F[@]}" -X DELETE "$API/users/${UID_[F]}/"
check_sql "després del 500: F i el seu mitjà continuen" \
  "SELECT (SELECT count(*) FROM users.users WHERE uid = '${UID_[F]}') + (SELECT count(*) FROM refuges.refuge_media WHERE key = '$MF');" "2"
code=$(auth_call accounts:signInWithPassword "${EMAIL[F]}" | python3 -c "import sys, json; print(json.load(sys.stdin).get('error', {}).get('message', 'OK'))")
[ "$code" = "OK" ] && ok "després del 500: el compte de Firebase de F es conserva" || fail "login de F: $code"

# Neteja
sql "DELETE FROM refuges.refuge_media WHERE key IN ('$MC', '$MF');" >/dev/null

echo
if [ "$fails" -eq 0 ]; then echo "E2E chunk 10: tot correcte"; else echo "$fails cas(os) fallats"; exit 1; fi
