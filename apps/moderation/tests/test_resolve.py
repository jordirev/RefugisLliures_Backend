"""
`PATCH /api/admin/media-reports/{id}/` (chunk 9; DSA art. 17; D40): resolució d'una denúncia per un moderador.

Cos `{action: dismiss|remove|remove_and_strike, statement}` (`statement` 1–2000, es retalla). 200:
`{report, resolved_report_ids, media_status, strikes, user_blocked}` (`media_status`: `visible` | `removed` | `held` |
`null`). Resol **totes** les denúncies pendents del mateix mitjà en **una transacció** i crea **un** avís per decisió.

- dismiss: `hidden_pending_review` → `visible` (+ avís `content_restored`); si no estava ocult, `media_status = null` i
  sense avís.
- remove: `removed` (+ avís `content_removed`). remove_and_strike: + 1 strike (avís `strike` amb el recompte); a 3 → bloqueig
  `strikes` (+ avís `account_blocked`).
- CSAM (alguna denúncia relacionada amb `child_sexual_abuse`) amb remove/remove_and_strike: la fila de `refuge_media`
  s'esborra, el fitxer i la miniatura es mouen a `moderation-hold/<clau>` (R2 mock), l'usuari es bloqueja
  `csam_confirmed`, les denúncies relacionades passen a `legal_hold = true` i les files d'auditoria noves de la
  resolució també. Si R2 falla en retenir: 500 `{error, error_id}` i tot desfet (l'evidència no es pot perdre).
- Errors: 400 (cos), 404 `{error: 'Report not found'}` (també id no UUID), 409 `already_resolved`.
Decisió tècnica: l'auditoria és immutable (`app` no té `UPDATE`): no es marquen amb `legal_hold` les files anteriors.
"""
import re
from unittest.mock import patch

import pytest
from django.db import DatabaseError, connection

from apps.moderation.tests.helpers import (
    HIDDEN, REPORT_KEYS, RESOLVE_KEYS, ZERO_UUID, admin_claims, api_patch, audit_rows, is_uuid, make_media,
    make_notice, make_report, media_key_for, media_row, media_status, notice_rows, report_row, report_rows,
    resolve_url, user_claims, user_state, sql)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration,
              pytest.mark.real_permissions]

STATEMENT = 'Incompleix les normes de la comunitat'


@pytest.fixture
def case(world):
    """Mitjà `K` (de `u1`, amb miniatura) ocult, i una denúncia pendent de `u2`. Retorna un diccionari."""
    r = world[0]
    key = media_key_for(r)
    thumb = key.replace('.webp', '_thumb.webp')
    make_media(r, 'u1', key=key, thumb_key=thumb, status=HIDDEN)
    rid = make_report(r, key, 'u2', 'hate_speech', creator='u1')
    return {'r': r, 'key': key, 'thumb': thumb, 'rid': rid}


def add_report(case, reporter, reason='hate_speech', minutes=1, **kw):
    return make_report(case['r'], case['key'], reporter, reason, creator='u1', minutes=minutes, **kw)


def resolve(client, rid, action='remove', statement=STATEMENT, claims=None):
    return api_patch(client, resolve_url(rid), claims or admin_claims('adm'), {'action': action, 'statement': statement})


def put_files(case, r2store):
    r2store.store[case['key']] = b'imatge'
    r2store.store[case['thumb']] = b'miniatura'


# =================================== permisos i validació ===================================

def test_anonim_es_401(client, case):
    assert client.patch(resolve_url(case['rid']), {'action': 'remove', 'statement': 'x'},
                        content_type='application/json').status_code == 401


def test_usuari_normal_es_403_i_no_canvia_res(client, case):
    resp = resolve(client, case['rid'], claims=user_claims('u2'))
    assert resp.status_code == 403
    assert report_row(case['rid'])['status'] == 'pending' and media_status(case['key']) == HIDDEN


def test_admin_sense_perfil_es_403_profile_required(client, case):
    resp = resolve(client, case['rid'], claims=admin_claims('adm_nou'))
    assert resp.status_code == 403 and resp.json()['error'] == 'profile_required'


@pytest.mark.parametrize('payload', [
    {'action': 'ban', 'statement': 'x'}, {'action': 'dismiss'}, {'statement': 'x'}, {'action': 'dismiss', 'statement': ''},
    {'action': 'dismiss', 'statement': '   '}, {'action': 'dismiss', 'statement': 'x' * 2001}, {},
])
def test_cos_invalid_es_400(client, case, payload):
    resp = api_patch(client, resolve_url(case['rid']), admin_claims('adm'), payload)
    assert resp.status_code == 400 and resp.json()['error'] == 'Dades invàlides', resp.content
    assert report_row(case['rid'])['status'] == 'pending'


def test_statement_de_2000_s_accepta_i_es_retalla(client, case):
    resp = resolve(client, case['rid'], 'dismiss', '  ' + 'x' * 1998 + '  ')
    assert resp.status_code == 200 and len(resp.json()['report']['statement']) == 1998


def test_report_inexistent_o_no_uuid_es_404(client, case):
    for rid in (ZERO_UUID, 'no-es-uuid', 'a' * 40):
        resp = resolve(client, rid)
        assert resp.status_code == 404 and resp.json() == {'error': 'Report not found'}, rid


def test_el_400_va_abans_del_404(client, case):
    resp = api_patch(client, resolve_url(ZERO_UUID), admin_claims('adm'), {'action': 'ban', 'statement': 'x'})
    assert resp.status_code == 400


def test_ja_resolta_es_409_already_resolved(client, case):
    assert resolve(client, case['rid'], 'dismiss').status_code == 200
    resp = resolve(client, case['rid'], 'remove')
    assert resp.status_code == 409
    assert resp.json() == {'error': 'already_resolved', 'code': 'already_resolved',
                           'message': 'La denúncia ja està resolta'}
    assert media_status(case['key']) == 'visible'                           # la segona crida no ha tocat res


# =================================== dismiss ===================================

def test_dismiss_torna_el_mitja_a_visible_i_avisa_l_autor(client, case):
    resp = resolve(client, case['rid'], 'dismiss')
    assert resp.status_code == 200, resp.content
    data = resp.json()
    assert set(data) == RESOLVE_KEYS
    assert (data['media_status'], data['strikes'], data['user_blocked']) == ('visible', None, False)
    assert data['resolved_report_ids'] == [case['rid']]
    rep = data['report']
    assert set(rep) == REPORT_KEYS and rep['id'] == case['rid']
    assert (rep['status'], rep['action'], rep['statement'], rep['resolved_by']) == ('resolved', 'dismiss', STATEMENT, 'adm')
    assert re.match(r'^\d{4}-\d{2}-\d{2}T.*\+0[12]:00$', rep['resolved_at'])
    assert media_status(case['key']) == 'visible'
    [n] = notice_rows('u1')
    assert (n['type'], n['action'], n['automated'], n['strikes']) == ('content_restored', 'dismiss', False, None)
    assert (n['statement'], n['report_id'], n['refuge_id'], n['media_key'], n['reason']) == (
        STATEMENT, case['rid'], str(case['r'].pk), case['key'], 'hate_speech')
    assert user_state('u1')['strikes'] == 0


def test_dismiss_d_un_mitja_que_no_estava_ocult_no_canvia_res_ni_avisa(client, world):
    r = world[0]
    key = media_key_for(r, 'vis')
    make_media(r, 'u1', key=key)
    rid = make_report(r, key, 'u2', creator='u1')
    data = resolve(client, rid, 'dismiss').json()
    assert data['media_status'] is None and notice_rows('u1') == []
    assert report_row(rid)['status'] == 'resolved' and media_status(key) == 'visible'


def test_dismiss_no_restaura_un_mitja_retirat(client, world):
    r = world[0]
    key = media_key_for(r, 'rem')
    make_media(r, 'u1', key=key, status='removed')
    rid = make_report(r, key, 'u2', creator='u1')
    assert resolve(client, rid, 'dismiss').json()['media_status'] is None
    assert media_status(key) == 'removed'


# =================================== remove / strike / bloqueig ===================================

def test_remove_retira_el_mitja_i_avisa_sense_strike(client, case):
    resp = resolve(client, case['rid'], 'remove')
    data = resp.json()
    assert resp.status_code == 200
    assert (data['media_status'], data['strikes'], data['user_blocked']) == ('removed', None, False)
    assert media_status(case['key']) == 'removed' and user_state('u1')['strikes'] == 0
    [n] = notice_rows('u1')
    assert (n['type'], n['action'], n['strikes'], n['statement']) == ('content_removed', 'remove', None, STATEMENT)


def test_remove_and_strike_suma_un_strike(client, case):
    data = resolve(client, case['rid'], 'remove_and_strike').json()
    assert (data['media_status'], data['strikes'], data['user_blocked']) == ('removed', 1, False)
    assert user_state('u1') == {'strikes': 1, 'is_blocked': False, 'blocked_reason': None, 'blocked_at': None}
    [n] = notice_rows('u1')
    assert (n['type'], n['action'], n['strikes']) == ('strike', 'remove_and_strike', 1)


def test_el_tercer_strike_bloqueja_l_usuari_amb_motiu_strikes(client, case):
    sql("UPDATE users.users SET moderation_strikes = 2 WHERE uid = 'u1'")
    data = resolve(client, case['rid'], 'remove_and_strike').json()
    assert (data['strikes'], data['user_blocked']) == (3, True)
    st = user_state('u1')
    assert (st['strikes'], st['is_blocked'], st['blocked_reason']) == (3, True, 'strikes') and st['blocked_at']
    notices = notice_rows('u1')
    assert [n['type'] for n in notices] == ['strike', 'account_blocked']
    assert notices[1]['strikes'] == 3 and notices[1]['action'] == 'remove_and_strike' and 'bloquejat' in notices[1]['statement']


def test_amb_dos_strikes_no_es_bloqueja(client, case):
    sql("UPDATE users.users SET moderation_strikes = 1 WHERE uid = 'u1'")
    data = resolve(client, case['rid'], 'remove_and_strike').json()
    assert (data['strikes'], data['user_blocked']) == (2, False) and user_state('u1')['is_blocked'] is False


def test_un_remove_sobre_un_usuari_amb_dos_strikes_no_el_bloqueja(client, case):
    sql("UPDATE users.users SET moderation_strikes = 2 WHERE uid = 'u1'")
    data = resolve(client, case['rid'], 'remove').json()
    assert data['strikes'] is None and data['user_blocked'] is False and user_state('u1')['strikes'] == 2


def test_l_autor_esborrat_no_rep_avis_ni_strike(client, world):
    r = world[0]
    key = media_key_for(r, 'orfe')
    rid = make_report(r, key, 'u2', creator=None)
    data = resolve(client, rid, 'remove_and_strike').json()
    assert data['strikes'] is None and data['user_blocked'] is False
    assert notice_rows() == [] and report_row(rid)['status'] == 'resolved'


# =================================== totes les denúncies del mitjà ===================================

def test_resol_totes_les_pendents_del_mateix_mitja_amb_una_sola_decisio(client, case):
    other = [add_report(case, 'u3', 'fraud_scam_spam', 1), add_report(case, 'u4', 'animal_cruelty', 2)]
    done = make_report(case['r'], case['key'], 'u5', 'hate_speech', creator='u1', status='resolved', action='dismiss',
                       statement='antiga', minutes=3, resolved_by='adm2')
    elsewhere = make_report(case['r'], media_key_for(case['r'], 'altre'), 'u3', creator='u1', minutes=4)
    before_done = report_row(done)
    data = resolve(client, case['rid'], 'remove').json()
    assert sorted(data['resolved_report_ids']) == sorted([case['rid'], *other])
    for rid in (case['rid'], *other):
        row = report_row(rid)
        assert (row['status'], row['action'], row['statement'], row['resolved_by']) == ('resolved', 'remove', STATEMENT, 'adm')
        assert row['resolved_at'] is not None
    assert report_row(done) == before_done                       # ja resolta: no es toca
    assert report_row(elsewhere)['status'] == 'pending'          # altre mitjà: no es toca
    assert len(notice_rows('u1')) == 1                           # un avís per decisió, no un per denúncia


def test_un_sol_strike_encara_que_hi_hagi_diverses_denuncies(client, case):
    add_report(case, 'u3'), add_report(case, 'u4', minutes=2)
    assert resolve(client, case['rid'], 'remove_and_strike').json()['strikes'] == 1
    assert user_state('u1')['strikes'] == 1


def test_les_denuncies_del_mateix_mitja_a_un_altre_refugi_no_es_toquen(client, case, world):
    other_refuge_report = make_report(world[1], case['key'], 'u3', creator='u1', minutes=2)
    resolve(client, case['rid'], 'remove')
    assert report_row(other_refuge_report)['status'] == 'pending'


def test_resoldre_una_germana_ja_resolta_es_409(client, case):
    sib = add_report(case, 'u3')
    resolve(client, case['rid'], 'dismiss')
    assert resolve(client, sib, 'remove').status_code == 409


def test_s_pot_resoldre_per_qualsevol_de_les_denuncies_pendents(client, case):
    sib = add_report(case, 'u3')
    data = resolve(client, sib, 'remove').json()
    assert data['report']['id'] == sib and sorted(data['resolved_report_ids']) == sorted([case['rid'], sib])
    [n] = notice_rows('u1')
    assert n['report_id'] == sib                                 # l'avís apunta a la denúncia que s'ha resolt


# =================================== CSAM ===================================

def csam_case(case, r2store, extra_reason='child_sexual_abuse'):
    put_files(case, r2store)
    return add_report(case, 'u3', extra_reason)


def test_csam_esborra_el_mitja_mou_els_fitxers_a_moderation_hold_i_bloqueja(client, case, r2store):
    csam = csam_case(case, r2store)
    resp = resolve(client, case['rid'], 'remove')
    data = resp.json()
    assert resp.status_code == 200, resp.content
    assert (data['media_status'], data['strikes'], data['user_blocked']) == ('held', None, True)
    assert media_row(case['key']) is None                                          # la fila ja no és a l'app
    store = r2store.store
    assert case['key'] not in store and case['thumb'] not in store
    assert store['moderation-hold/' + case['key']] == b'imatge'
    assert store['moderation-hold/' + case['thumb']] == b'miniatura'
    st = user_state('u1')
    assert (st['is_blocked'], st['blocked_reason'], st['strikes']) == (True, 'csam_confirmed', 0) and st['blocked_at']
    assert [n['type'] for n in notice_rows('u1')] == ['content_removed', 'account_blocked']
    assert 'abús sexual infantil' in notice_rows('u1')[1]['statement']
    assert sorted(data['resolved_report_ids']) == sorted([case['rid'], csam])


def test_csam_marca_legal_hold_totes_les_denuncies_relacionades(client, case, r2store):
    csam = csam_case(case, r2store)
    other_media = make_report(case['r'], media_key_for(case['r'], 'altre'), 'u3', creator='u1', minutes=5)
    resolve(client, case['rid'], 'remove')
    assert report_row(case['rid'])['legal_hold'] is True                           # la no-CSAM també
    assert report_row(csam)['legal_hold'] is True
    assert report_row(other_media)['legal_hold'] is False


def test_csam_resolt_des_de_la_denuncia_csam_tambe_ho_fa(client, case, r2store):
    csam = csam_case(case, r2store)
    assert resolve(client, csam, 'remove').json()['media_status'] == 'held'
    assert report_row(case['rid'])['status'] == 'resolved' and report_row(case['rid'])['legal_hold'] is True


def test_csam_amb_remove_and_strike_suma_strike_i_bloqueja_per_csam(client, case, r2store):
    csam_case(case, r2store)
    data = resolve(client, case['rid'], 'remove_and_strike').json()
    assert (data['strikes'], data['user_blocked'], data['media_status']) == (1, True, 'held')
    assert user_state('u1')['blocked_reason'] == 'csam_confirmed'
    assert [n['type'] for n in notice_rows('u1')] == ['strike', 'account_blocked']


def test_csam_amb_dismiss_es_un_dismiss_normal(client, case, r2store):
    put_files(case, r2store)
    csam = add_report(case, 'u3')
    data = resolve(client, csam, 'dismiss').json()
    assert data['media_status'] == 'visible' and data['user_blocked'] is False
    assert media_row(case['key']) is not None and case['key'] in r2store.store
    assert not r2store.keys('moderation-hold/')


def test_sense_csam_no_es_toca_r2(client, case, r2store):
    put_files(case, r2store)
    resolve(client, case['rid'], 'remove')
    assert r2store.deletes == [] and r2store.puts == [] and not r2store.keys('moderation-hold/')
    assert case['key'] in r2store.store


def test_csam_sense_miniatura(client, world, r2store):
    r = world[0]
    key = media_key_for(r, 'sensethumb')
    make_media(r, 'u1', key=key)
    r2store.store[key] = b'x'
    rid = make_report(r, key, 'u2', 'child_sexual_abuse', creator='u1')
    assert resolve(client, rid, 'remove').json()['media_status'] == 'held'
    assert list(r2store.keys('moderation-hold/')) == ['moderation-hold/' + key]


def test_csam_si_r2_falla_en_retenir_es_500_i_tot_es_desfa(client, case, r2store, caplog):
    import logging
    csam = csam_case(case, r2store)
    with patch('apps.uploads.media.r2_media_service.R2MediaService.copy_object', return_value=False), \
            caplog.at_level(logging.ERROR):
        resp = resolve(client, case['rid'], 'remove')
    assert resp.status_code == 500
    body = resp.json()
    assert set(body) == {'error', 'error_id'} and any(body['error_id'] in r.getMessage() for r in caplog.records)
    assert media_row(case['key']) is not None and media_status(case['key']) == HIDDEN
    assert case['key'] in r2store.store and case['thumb'] in r2store.store
    assert user_state('u1')['is_blocked'] is False and notice_rows() == []
    assert report_row(case['rid'])['status'] == 'pending' and report_row(csam)['status'] == 'pending'
    assert report_row(csam)['legal_hold'] is True                  # el valor del moment de crear-la (motiu CSAM)
    assert report_row(case['rid'])['legal_hold'] is False          # el `legal_hold` de la resolució s'ha desfet


def test_csam_si_falla_la_bd_despres_de_copiar_els_originals_no_s_han_esborrat(client, case, r2store):
    """L'esborrat dels originals és l'últim pas: si la BD falla després de la còpia, la transacció es desfà i el
    fitxer continua on la fila l'espera (si no, la denúncia quedaria irresolible: la còpia fallaria per origen absent)."""
    csam_case(case, r2store)
    with patch('apps.moderation.services.account_services.set_blocked', side_effect=DatabaseError('x')):
        resp = resolve(client, case['rid'], 'remove')
    assert resp.status_code == 500
    assert case['key'] in r2store.store and case['thumb'] in r2store.store
    assert r2store.deletes == []
    assert media_row(case['key']) is not None and report_row(case['rid'])['status'] == 'pending'
    assert resolve(client, case['rid'], 'remove').json()['media_status'] == 'held'     # i es pot tornar a provar


def test_csam_si_nomes_falla_la_copia_de_la_miniatura_tambe_es_desfa(client, case, r2store):
    csam_case(case, r2store)
    real = r2store.client.copy_object.side_effect

    def flaky(Bucket, Key, CopySource):
        if Key.endswith('_thumb.webp'):
            from botocore.exceptions import ClientError
            raise ClientError({'Error': {'Code': '500', 'Message': 'x'}}, 'CopyObject')
        return real(Bucket=Bucket, Key=Key, CopySource=CopySource)

    r2store.client.copy_object.side_effect = flaky
    assert resolve(client, case['rid'], 'remove').status_code == 500
    assert media_row(case['key']) is not None and user_state('u1')['is_blocked'] is False
    assert report_row(case['rid'])['status'] == 'pending'
    # primer es copien tots els fitxers i només després s'esborren els originals: l'evidència no es pot perdre
    assert r2store.store.get(case['key']) == b'imatge' and r2store.store.get(case['thumb']) == b'miniatura'


# =================================== atomicitat ===================================

def test_si_falla_la_creacio_de_l_avis_es_desfa_tot(client, case, caplog):
    import logging
    sql("UPDATE users.users SET moderation_strikes = 1 WHERE uid = 'u1'")
    add_report(case, 'u3')

    def wrapper(execute, sql_, params, many, context):
        if sql_.lstrip().upper().startswith('INSERT') and 'moderation_notices' in sql_:
            raise DatabaseError('fallada simulada: host=db.neon.tech')
        return execute(sql_, params, many, context)

    with connection.execute_wrapper(wrapper), caplog.at_level(logging.ERROR):
        resp = resolve(client, case['rid'], 'remove_and_strike')
    assert resp.status_code == 500 and set(resp.json()) == {'error', 'error_id'}
    assert 'neon' not in resp.content.decode()
    assert user_state('u1')['strikes'] == 1 and media_status(case['key']) == HIDDEN
    assert [r['status'] for r in report_rows()] == ['pending', 'pending']
    assert notice_rows() == []


def test_un_error_de_bd_a_l_actualitzar_el_mitja_es_500_traçat_i_desfet(client, case):
    def wrapper(execute, sql_, params, many, context):
        if sql_.lstrip().upper().startswith('UPDATE') and 'refuge_media' in sql_:
            raise DatabaseError('fallada simulada')
        return execute(sql_, params, many, context)

    with connection.execute_wrapper(wrapper):
        resp = resolve(client, case['rid'], 'dismiss')
    assert resp.status_code == 500 and set(resp.json()) == {'error', 'error_id'}
    assert report_row(case['rid'])['status'] == 'pending' and notice_rows() == []


# =================================== auditoria ===================================

@pytest.mark.real_audit_log
def test_audit_de_la_resolucio_i_del_bloqueig_per_strikes(client, case):
    sql("UPDATE users.users SET moderation_strikes = 2 WHERE uid = 'u1'")
    sib = add_report(case, 'u3')
    resolve(client, case['rid'], 'remove_and_strike')
    [res] = audit_rows('moderation.resolve')
    assert res['actor_uid'] == 'adm' and (res['target_type'], res['target_id']) == ('media', case['key'])
    assert res['metadata']['refuge_id'] == str(case['r'].pk) and res['metadata']['action'] == 'remove_and_strike'
    assert sorted(res['metadata']['report_ids']) == sorted([case['rid'], sib]) and res['metadata']['csam'] is False
    assert res['legal_hold'] is False and 'u1' not in str(res['metadata'])
    [blk] = audit_rows('moderation.user_blocked')
    assert blk['actor_uid'] == 'adm' and blk['subject_uid'] == 'u1' and blk['target_type'] == 'user'
    assert blk['target_id'] is None and blk['metadata'] == {'reason': 'strikes', 'report_id': case['rid']}
    assert blk['legal_hold'] is False


@pytest.mark.real_audit_log
def test_audit_csam_amb_legal_hold_i_sense_uid(client, case, r2store):
    csam_case(case, r2store)
    resolve(client, case['rid'], 'remove')
    [res] = audit_rows('moderation.resolve')
    [blk] = audit_rows('moderation.user_blocked')
    assert res['legal_hold'] is True and res['metadata']['csam'] is True
    assert blk['legal_hold'] is True and blk['subject_uid'] == 'u1' and blk['metadata']['reason'] == 'csam_confirmed'
    for row in (res, blk):
        assert 'u1' not in str(row['metadata']) and row['target_id'] in (None, case['key'])
        assert (row['expire_at'] - row['created_at']).days >= 1825


# =================================== servei (interfície del contracte) ===================================

def test_el_service_exposa_excepcions_de_domini(services):
    for name in ('RefugeNotFound', 'MediaNotFound', 'OwnMedia', 'AlreadyReported', 'ReportNotFound', 'AlreadyResolved'):
        assert issubclass(getattr(services, name), Exception), name
    assert callable(services.create_report) and callable(services.resolve_report)


def test_el_service_resolve_report_llanca_already_resolved_i_not_found(case, services):
    from apps.core.rls import rls_context
    with rls_context(uid='adm', is_admin=True):
        out = services.resolve_report(report_id=case['rid'], action='dismiss', statement='x', admin_uid='adm')
        assert out['media_status'] == 'visible'
        with pytest.raises(services.AlreadyResolved):
            services.resolve_report(report_id=case['rid'], action='remove', statement='x', admin_uid='adm')
        with pytest.raises(services.ReportNotFound):
            services.resolve_report(report_id=ZERO_UUID, action='remove', statement='x', admin_uid='adm')
        with pytest.raises(services.ReportNotFound):
            services.resolve_report(report_id='no-uuid', action='remove', statement='x', admin_uid='adm')
