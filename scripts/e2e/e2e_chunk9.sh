#!/usr/bin/env bash
# E2E del chunk 9 (moderació i auditoria a PostgreSQL): denúncies (validacions, 404, own_media, already_reported,
# ocultació per tres denunciants diferents i immediata per motius greus), avisos a l'autor, llistat i resolució d'admin
# (dismiss, remove_and_strike, already_resolved), CSAM amb R2 inabastable (500 i tot desfet), esborrat d'usuari
# (denúncies normals fora, CSAM anonimitzada conservant `details`), auditoria a `audit.audit_logs` i, opcionalment,
# `load_hash_blocklist`.
#
# Requisits: els de e2e_chunk3.sh (BD migrada amb `audit.0001` i `moderation.0001`, Firebase Auth Emulator) i
#   PSQL_E2E='docker exec -i rl-postgres psql -U postgres -d refugisdb_e2e -q'  (crea els mitjans i llegeix l'estat)
#   E2E_CONTAINER=rl-e2e-moderacio   (opcional: prova `load_hash_blocklist` dins el contenidor del servidor)
# R2 és fictici. Els cossos són ASCII (Git Bash de Windows malmet els arguments no ASCII de curl). Cap credencial real.
set -uo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
AUTH_EMULATOR="${AUTH_EMULATOR:-http://localhost:9099}"
PROJECT_ID="${GCLOUD_PROJECT:-demo-refugis-lliures}"
PASSWORD="e2e-pass-123"   # només per a l'emulador
IDT="$AUTH_EMULATOR/identitytoolkit.googleapis.com/v1"
API="$BASE_URL/api"
fails=0
[ -n "${PSQL_E2E:-}" ] || { echo "Cal PSQL_E2E (crea els mitjans de prova)" >&2; exit 2; }

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
check_sql() {  # $1 descripció, $2 consulta, $3 valor esperat
  local got
  got=$(sql "$2")
  [ "$got" = "$3" ] && ok "$1" || fail "$1: '$got' (esperat '$3')"
}

suffix="$(date +%s)"
declare -A EMAIL UID_
for who in C R1 R2 R3 A Y; do
  EMAIL[$who]="m-$(echo "$who" | tr 'A-Z' 'a-z')-$suffix@e2e.test"
  UID_[$who]=$(ensure_user "${EMAIL[$who]}")
  [ -n "${UID_[$who]}" ] || { echo "No s'ha pogut crear $who a l'emulador" >&2; exit 2; }
done
curl -s -o /dev/null -X POST "$IDT/projects/$PROJECT_ID/accounts:update" \
  -H 'Authorization: Bearer owner' -H 'Content-Type: application/json' \
  -d "{\"localId\":\"${UID_[A]}\",\"customAttributes\":\"{\\\"role\\\":\\\"admin\\\"}\"}"
tok() { auth_call accounts:signInWithPassword "$1" | json_field idToken; }
for who in C R1 R2 R3 A Y; do declare -a "H_$who=(-H 'Authorization: Bearer $(tok "${EMAIL[$who]}")')"; done
J=(-H 'Content-Type: application/json')
for who in C R1 R2 R3 A; do
  declare -n H="H_$who"
  curl -s -o /dev/null "${H[@]}" "${J[@]}" -X POST "$API/users/" -d '{"username":"E2E","birth_date":"1990-01-01"}'
done
curl -s -o /dev/null "${H_Y[@]}" "${J[@]}" -X POST "$API/users/" -d '{"username":"Sense edat"}'

R=$(curl -s -m 30 "$API/refuges/" | python3 -c "import sys, json; r = json.load(sys.stdin)['results']; print(r[($suffix + 11) % len(r)]['id'])")
[ -n "$R" ] || { echo "No hi ha refugis carregats" >&2; exit 2; }
BAD_ID="00000000-0000-7000-8000-000000000000"
M1="refugis-lliures/$R/e2e-$suffix-1.webp"; M2="refugis-lliures/$R/e2e-$suffix-2.webp"; M3="refugis-lliures/$R/e2e-$suffix-3.webp"
for k in "$M1" "$M2" "$M3"; do
  sql "INSERT INTO refuges.refuge_media (key, refuge_id, creator_uid, media_type, content_type, rights_confirmed_at) VALUES ('$k', '$R', '${UID_[C]}', 'image', 'image/webp', now());" >/dev/null
done
media_status() { sql "SELECT status FROM refuges.refuge_media WHERE key = '$1';"; }
REP="$API/media/reports/"
ADM="$API/admin/media-reports"
rep() { printf '{"refuge_id":"%s","media_key":"%s","reason":"%s"%s}' "$1" "$2" "$3" "${4:+,\"details\":\"$4\"}"; }
report_id() { python3 -c "import sys, json; print(json.load(sys.stdin).get('id', ''))" 2>/dev/null; }

# --- Validacions i permisos de la denúncia
check "denúncia sense token -> 401" 401 "${J[@]}" -X POST "$REP" -d "$(rep "$R" "$M1" fraud_scam_spam)"
check "motiu desconegut -> 400" 400 "${H_R1[@]}" "${J[@]}" -X POST "$REP" -d "$(rep "$R" "$M1" nope)"
check "motiu other sense details -> 400" 400 "${H_R1[@]}" "${J[@]}" -X POST "$REP" -d "$(rep "$R" "$M1" other)"
check "refugi inexistent -> 404" 404 "${H_R1[@]}" "${J[@]}" -X POST "$REP" -d "$(rep "$BAD_ID" "$M1" fraud_scam_spam)"
check "mitjà inexistent -> 404" 404 "${H_R1[@]}" "${J[@]}" -X POST "$REP" -d "$(rep "$R" "refugis-lliures/$R/no.webp" fraud_scam_spam)"
check_json "denunciar el propi -> own_media" "d['code'] == 'own_media'" "${H_C[@]}" "${J[@]}" -X POST "$REP" -d "$(rep "$R" "$M1" fraud_scam_spam)"
check "sense edat confirmada -> 403" 403 "${H_Y[@]}" "${J[@]}" -X POST "$REP" -d "$(rep "$R" "$M1" fraud_scam_spam)"

# --- Tres denunciants diferents oculten el mitjà
check_json "R1 denuncia M1 (spam) -> 201, normal, no ocult, id UUID" \
  "d['priority'] == 'normal' and d['media_hidden'] is False and len(d['id']) == 36 and d['status'] == 'pending'" \
  "${H_R1[@]}" "${J[@]}" -X POST "$REP" -d "$(rep "$R" "$M1" fraud_scam_spam)"
check_json "R1 torna a denunciar M1 -> already_reported" "d['code'] == 'already_reported'" \
  "${H_R1[@]}" "${J[@]}" -X POST "$REP" -d "$(rep "$R" "$M1" hate_speech)"
check_json "R2 denuncia M1 -> encara visible" "d['media_hidden'] is False" \
  "${H_R2[@]}" "${J[@]}" -X POST "$REP" -d "$(rep "$R" "$M1" misleading_irrelevant)"
check_json "R3 denuncia M1 -> ocult (3 denunciants)" "d['media_hidden'] is True" \
  "${H_R3[@]}" "${J[@]}" -X POST "$REP" -d "$(rep "$R" "$M1" other "No correspon")"
[ "$(media_status "$M1")" = "hidden_pending_review" ] && ok "M1 ocult a refuge_media" || fail "M1: $(media_status "$M1")"
check_json "M1 ja no surt a la llista pública de mitjans" "'$M1' not in json.dumps(d)" "$API/refuges/$R/media/"
check_json "C rep l'avís content_hidden" "any(n['type'] == 'content_hidden' and n['media_key'] == '$M1' for n in d['notices'])" \
  "${H_C[@]}" "$API/users/${UID_[C]}/moderation-notices/"
check "avisos de C demanats per R1 -> 403" 403 "${H_R1[@]}" "$API/users/${UID_[C]}/moderation-notices/"

# --- Llistat d'admin
check "llistat d'admin com a usuari -> 403" 403 "${H_R1[@]}" "$ADM/"
check "llistat amb status invàlid -> 400" 400 "${H_A[@]}" "$ADM/?status=foo"
check_json "llistat d'admin: les 3 denúncies de M1 amb previsualització" \
  "sum(1 for r in d['reports'] if r['media_key'] == '$M1') == 3 and all(r['media'] for r in d['reports'] if r['media_key'] == '$M1') and d['count'] == len(d['reports'])" \
  "${H_A[@]}" "$ADM/"

# --- Dismiss: torna a ser visible i es resolen totes les del mitjà
RID1=$(sql "SELECT id FROM moderation.media_reports WHERE media_key = '$M1' ORDER BY created_at LIMIT 1;")
check "resolve amb acció invàlida -> 400" 400 "${H_A[@]}" "${J[@]}" -X PATCH "$ADM/$RID1/" -d '{"action":"x","statement":"s"}'
check "resolve d'un id inexistent -> 404" 404 "${H_A[@]}" "${J[@]}" -X PATCH "$ADM/$BAD_ID/" -d '{"action":"dismiss","statement":"s"}'
check "resolve com a usuari -> 403" 403 "${H_R1[@]}" "${J[@]}" -X PATCH "$ADM/$RID1/" -d '{"action":"dismiss","statement":"s"}'
check_json "dismiss -> 3 resoltes i mitjà visible" "len(d['resolved_report_ids']) == 3 and d['media_status'] == 'visible'" \
  "${H_A[@]}" "${J[@]}" -X PATCH "$ADM/$RID1/" -d '{"action":"dismiss","statement":"No infringeix les normes"}'
[ "$(media_status "$M1")" = "visible" ] && ok "M1 torna a ser visible" || fail "M1: $(media_status "$M1")"
check_json "segona resolució -> already_resolved" "d['code'] == 'already_resolved'" \
  "${H_A[@]}" "${J[@]}" -X PATCH "$ADM/$RID1/" -d '{"action":"remove","statement":"x"}'

# --- remove_and_strike
RID3=$(curl -s -m 30 "${H_R1[@]}" "${J[@]}" -X POST "$REP" -d "$(rep "$R" "$M3" violence_gore)" | report_id)
[ -n "$RID3" ] && ok "R1 denuncia M3" || fail "no s'ha pogut denunciar M3"
check_json "remove_and_strike -> strike 1, removed, no bloquejat" \
  "d['strikes'] == 1 and d['media_status'] == 'removed' and d['user_blocked'] is False" \
  "${H_A[@]}" "${J[@]}" -X PATCH "$ADM/$RID3/" -d '{"action":"remove_and_strike","statement":"Contingut violent"}'
check_sql "C té 1 strike" "SELECT moderation_strikes FROM users.users WHERE uid = '${UID_[C]}';" "1"
check "denunciar un mitjà retirat -> 404" 404 "${H_R2[@]}" "${J[@]}" -X POST "$REP" -d "$(rep "$R" "$M3" fraud_scam_spam)"
check_json "C rep l'avís strike" "any(n['type'] == 'strike' and n['strikes'] == 1 for n in d['notices'])" \
  "${H_C[@]}" "$API/users/${UID_[C]}/moderation-notices/"

# --- CSAM: alta prioritat, ocultació immediata; R2 inabastable en retenir -> 500 i res canviat
CSAM=$(curl -s -m 30 "${H_R2[@]}" "${J[@]}" -X POST "$REP" -d "$(rep "$R" "$M2" child_sexual_abuse "Detalls del denunciant")")
RID2=$(echo "$CSAM" | report_id)
echo "$CSAM" | python3 -c "import sys, json; d = json.load(sys.stdin); sys.exit(0 if d['priority'] == 'high' and d['media_hidden'] else 1)" \
  && ok "CSAM -> prioritat alta i ocult" || fail "CSAM: $(echo "$CSAM" | head -c 300)"
check_sql "la denúncia CSAM porta legal_hold" "SELECT legal_hold FROM moderation.media_reports WHERE id = '$RID2';" "t"
check_json "llistat d'admin: la CSAM surt primer" "d['reports'][0]['id'] == '$RID2'" "${H_A[@]}" "$ADM/"
check_json "retenir CSAM amb R2 inabastable -> 500 {error, error_id}" "set(d) == {'error', 'error_id'}" \
  "${H_A[@]}" "${J[@]}" -X PATCH "$ADM/$RID2/" -d '{"action":"remove","statement":"CSAM confirmat"}'
check_sql "després del 500: denúncia pendent" "SELECT status FROM moderation.media_reports WHERE id = '$RID2';" "pending"
check_sql "després del 500: mitjà encara a refuge_media" "SELECT count(*) FROM refuges.refuge_media WHERE key = '$M2';" "1"
check_sql "després del 500: C no bloquejat" "SELECT is_blocked FROM users.users WHERE uid = '${UID_[C]}';" "f"

# --- Auditoria
check_sql "auditoria: la denúncia CSAM és legal_hold i no porta l'UID a metadata" \
  "SELECT count(*) FROM audit.audit_logs WHERE action = 'media.report' AND actor_uid = '${UID_[R2]}' AND legal_hold AND metadata::text NOT LIKE '%${UID_[R2]}%';" "1"
check_sql "auditoria: auto_hide del sistema (actor NULL)" \
  "SELECT count(*) > 0 FROM audit.audit_logs WHERE action = 'moderation.auto_hide' AND actor_uid IS NULL AND target_id = '$M1';" "t"

# --- Esborrat d'usuari
check "DELETE /users/R3/ -> 204" 204 "${H_R3[@]}" -X DELETE "$API/users/${UID_[R3]}/"
check_sql "les denúncies de R3 (no CSAM) desapareixen" "SELECT count(*) FROM moderation.media_reports WHERE reporter_uid = '${UID_[R3]}';" "0"
check "DELETE /users/R2/ -> 204" 204 "${H_R2[@]}" -X DELETE "$API/users/${UID_[R2]}/"
check_sql "la CSAM de R2 es conserva anonimitzada amb details" \
  "SELECT reporter_uid IS NULL AND anonymized_at IS NOT NULL AND details = 'Detalls del denunciant' FROM moderation.media_reports WHERE id = '$RID2';" "t"
check_sql "l'auditoria CSAM de R2 es conserva desvinculada" \
  "SELECT count(*) FROM audit.audit_logs WHERE action = 'media.report' AND legal_hold AND actor_uid IS NULL AND target_id = '$M2';" "1"
check_json "llistat d'admin: reporter_uid 'unknown' a la CSAM anonimitzada" \
  "any(r['id'] == '$RID2' and r['reporter_uid'] == 'unknown' for r in d['reports'])" "${H_A[@]}" "$ADM/"

# --- load_hash_blocklist (opcional, dins el contenidor del servidor, rol migrator)
if [ -n "${E2E_CONTAINER:-}" ]; then
  H1=$(python3 -c "import hashlib; print(hashlib.sha256(b'e2e-$suffix').hexdigest())")
  printf 'sha256,phash,category,source\n%s,,csam,e2e\n' "$H1" | MSYS_NO_PATHCONV=1 docker exec -i "$E2E_CONTAINER" sh -c 'cat > /tmp/hb.csv'
  out=$(MSYS_NO_PATHCONV=1 docker exec "$E2E_CONTAINER" python manage.py load_hash_blocklist /tmp/hb.csv 2>&1)
  echo "$out" | grep -q "Entrades afegides: 1" && ok "load_hash_blocklist afegeix 1 entrada" || fail "load_hash_blocklist: $out"
  out=$(MSYS_NO_PATHCONV=1 docker exec "$E2E_CONTAINER" python manage.py load_hash_blocklist /tmp/hb.csv 2>&1)
  echo "$out" | grep -q "Ja existents: 1" && ok "load_hash_blocklist és idempotent" || fail "load_hash_blocklist (2a): $out"
else
  echo "SALTAT load_hash_blocklist (sense E2E_CONTAINER)"
fi

# Neteja: els mitjans de prova que quedin
sql "DELETE FROM refuges.refuge_media WHERE key IN ('$M1', '$M2', '$M3');" >/dev/null

echo
if [ "$fails" -eq 0 ]; then echo "E2E chunk 9: tot correcte"; else echo "$fails cas(os) fallats"; exit 1; fi
