"""
`POST /api/media/reports/` (chunk 9; DSA art. 16, D40 (4)(5)): contracte HTTP d'avui amb la BD PostgreSQL.

Permisos (com avui): `IsAuthenticated, HasProfile, IsNotBlocked, IsAgeConfirmed` (en aquest ordre).
Cos: `{refuge_id, media_key, reason, details?}`; 201 `{id, refuge_id, media_key, reason, details, status, priority,
created_at, media_hidden}` amb `id` UUID opac (ja no el SHA-256 determinista).
Errors: 400 `{error: 'Dades invàlides', details}`; 404 `{error: 'Refugi not found' | 'Media not found'}`; 403
`own_media`; 409 `already_reported` (de la restricció `UNIQUE`, traduïda per `constraint_name`).

Decisions tècniques (a confirmar): un mitjà `removed` o un `media_key` de `moderation-hold/` → 404 `Media not found`
(no són públics); un mitjà ja ocult (`hidden_pending_review`) sí que es pot denunciar (hi pot haver més denunciants).
"""
import re

import pytest

from apps.moderation.tests.helpers import (
    AUTO_HIDE, CREATE_RESPONSE_KEYS, HIDDEN, REASONS, REPORTS, ZERO_UUID, admin_claims, api_post,
    audit_rows, count_reports, is_uuid, make_exp_media, make_experience, make_media, make_report,
    make_user, media_key_for, media_status, notice_rows, report_row, report_rows, sql, user_claims)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration,
              pytest.mark.real_permissions]

ISO_MADRID = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?\+0[12]:00$')


@pytest.fixture
def media(world):
    """Mitjà visible `K` de `u1` al refugi A. Retorna `(refugi, clau)`."""
    r = world[0]
    key = media_key_for(r)
    make_media(r, 'u1', key=key, thumb_key=key.replace('.webp', '_thumb.webp'))
    return r, key


def body(media, reason='hate_speech', **extra):
    r, key = media
    return {'refuge_id': str(r.pk), 'media_key': key, 'reason': reason, **extra}


def report(client, media, uid='u2', reason='hate_speech', **extra):
    return api_post(client, REPORTS, user_claims(uid), body(media, reason, **extra))


# =================================== èxit i forma ===================================

def test_crea_la_denuncia_i_respon_amb_el_contracte(client, media):
    r, key = media
    resp = report(client, media, 'u2', 'hate_speech', details='Insults al peu de foto')
    assert resp.status_code == 201, resp.content
    data = resp.json()
    assert set(data) == CREATE_RESPONSE_KEYS
    assert is_uuid(data['id']) and len(data['id']) == 36                    # UUID opac, no el SHA-256 d'abans
    assert (data['refuge_id'], data['media_key'], data['reason']) == (str(r.pk), key, 'hate_speech')
    assert data['details'] == 'Insults al peu de foto' and data['status'] == 'pending'
    assert data['priority'] == 'normal' and data['media_hidden'] is False
    assert ISO_MADRID.match(data['created_at']), data['created_at']
    row = report_row(data['id'])
    assert (row['reporter_uid'], row['media_creator_uid'], row['source'], row['status']) == ('u2', 'u1', 'user', 'pending')
    assert row['refuge_id'] == str(r.pk) and row['legal_hold'] is False and row['anonymized_at'] is None
    assert media_status(key) == 'visible'


def test_details_es_retalla_i_buit_es_null(client, media):
    resp = report(client, media, 'u2', 'hate_speech', details='  amb espais  ')
    assert resp.json()['details'] == 'amb espais'
    resp = report(client, media, 'u3', 'hate_speech', details='   ')
    assert resp.status_code == 201 and resp.json()['details'] is None
    assert report_row(resp.json()['id'])['details'] is None
    resp = report(client, media, 'u4', 'hate_speech', details=None)
    assert resp.status_code == 201 and resp.json()['details'] is None


@pytest.mark.parametrize('reason', REASONS)
def test_els_setze_motius_s_accepten(client, media, reason):
    extra = {'details': 'cal una descripció'} if reason == 'other' else {}
    resp = report(client, media, 'u2', reason, **extra)
    assert resp.status_code == 201, resp.content
    assert resp.json()['priority'] == ('high' if reason in AUTO_HIDE else 'normal')


def test_dos_ids_diferents_per_a_dues_denuncies(client, media):
    a = report(client, media, 'u2').json()['id']
    b = report(client, media, 'u3').json()['id']
    assert a != b and is_uuid(a) and is_uuid(b)


def test_csam_marca_legal_hold_a_la_denuncia(client, media):
    resp = report(client, media, 'u2', 'child_sexual_abuse')
    assert resp.status_code == 201
    assert report_row(resp.json()['id'])['legal_hold'] is True
    resp = report(client, media, 'u3', 'hate_speech')
    assert report_row(resp.json()['id'])['legal_hold'] is False


def test_mitjans_d_experiencia_es_poden_denunciar(client, world):
    r = world[0]
    e = make_experience(r, 'u1')
    key = media_key_for(r, 'exp1')
    make_exp_media(r, 'u1', e, key=key)
    resp = api_post(client, REPORTS, user_claims('u2'), {'refuge_id': str(r.pk), 'media_key': key, 'reason': 'my_image'})
    assert resp.status_code == 201, resp.content
    assert resp.json()['media_hidden'] is True and media_status(key) == HIDDEN
    assert report_row(resp.json()['id'])['media_creator_uid'] == 'u1'


def test_un_admin_tambe_pot_denunciar(client, media):
    make_user('adm_rep')
    assert api_post(client, REPORTS, admin_claims('adm_rep'), body(media)).status_code == 201


# =================================== validació (400) ===================================

@pytest.mark.parametrize('payload', [
    {'media_key': 'k', 'reason': 'my_image'},                                  # falta refuge_id
    {'refuge_id': ZERO_UUID, 'reason': 'my_image'},                            # falta media_key
    {'refuge_id': ZERO_UUID, 'media_key': 'k'},                                # falta reason
    {'refuge_id': ZERO_UUID, 'media_key': 'k', 'reason': 'nope'},              # motiu desconegut
    {'refuge_id': ZERO_UUID, 'media_key': 'k', 'reason': 'other'},             # other sense details
    {'refuge_id': ZERO_UUID, 'media_key': 'k', 'reason': 'other', 'details': '   '},
    {'refuge_id': ZERO_UUID, 'media_key': 'k', 'reason': 'hate_speech', 'details': 'x' * 1001},
    {'refuge_id': ZERO_UUID, 'media_key': 'k' * 501, 'reason': 'hate_speech'},
])
def test_dades_invalides_son_400_i_no_escriuen(client, world, payload):
    resp = api_post(client, REPORTS, user_claims('u2'), payload)
    assert resp.status_code == 400, resp.content
    assert resp.json()['error'] == 'Dades invàlides' and 'details' in resp.json()
    assert count_reports() == 0


def test_details_de_1000_caracters_s_accepta(client, media):
    assert report(client, media, 'u2', 'hate_speech', details='x' * 1000).status_code == 201


def test_other_amb_details_s_accepta(client, media):
    resp = report(client, media, 'u2', 'other', details='Cal revisar-ho')
    assert resp.status_code == 201 and resp.json()['details'] == 'Cal revisar-ho'


def test_el_400_va_abans_dels_404(client, world):
    resp = api_post(client, REPORTS, user_claims('u2'), {'refuge_id': ZERO_UUID, 'media_key': 'k', 'reason': 'nope'})
    assert resp.status_code == 400


# =================================== 404 ===================================

def test_refugi_inexistent_o_no_uuid_es_404_refugi_not_found(client, world):
    for rid in (ZERO_UUID, 'ref_1', 'no-es-uuid'):
        resp = api_post(client, REPORTS, user_claims('u2'), {'refuge_id': rid, 'media_key': 'k', 'reason': 'my_image'})
        assert resp.status_code == 404 and resp.json() == {'error': 'Refugi not found'}, rid


def test_mitja_inexistent_es_404_media_not_found(client, media):
    r, _ = media
    resp = api_post(client, REPORTS, user_claims('u2'),
                    {'refuge_id': str(r.pk), 'media_key': 'refugis-lliures/x/no-hi-es.webp', 'reason': 'my_image'})
    assert resp.status_code == 404 and resp.json() == {'error': 'Media not found'}
    assert count_reports() == 0


def test_mitja_d_un_altre_refugi_es_404(client, media, world):
    _, key = media
    resp = api_post(client, REPORTS, user_claims('u2'), {'refuge_id': str(world[1].pk), 'media_key': key,
                                                         'reason': 'my_image'})
    assert resp.status_code == 404 and resp.json() == {'error': 'Media not found'}


def test_un_mitja_retingut_a_moderation_hold_o_retirat_es_404(client, world):
    r = world[0]
    removed = media_key_for(r, 'removed')
    make_media(r, 'u1', key=removed, status='removed')
    for key in (removed, 'moderation-hold/' + media_key_for(r, 'held')):
        resp = api_post(client, REPORTS, user_claims('u2'), {'refuge_id': str(r.pk), 'media_key': key,
                                                             'reason': 'hate_speech'})
        assert resp.status_code == 404 and resp.json() == {'error': 'Media not found'}, key


def test_un_mitja_ja_ocult_per_un_altre_es_pot_denunciar(client, world):
    """La RLS amagaria el mitjà ocult a qui denuncia: el service el llegeix amb `system_context()` acotat (§2.20)."""
    r = world[0]
    key = media_key_for(r, 'hid')
    make_media(r, 'u1', key=key, status=HIDDEN)
    resp = api_post(client, REPORTS, user_claims('u3'), {'refuge_id': str(r.pk), 'media_key': key,
                                                         'reason': 'hate_speech'})
    assert resp.status_code == 201 and resp.json()['media_hidden'] is False
    assert media_status(key) == HIDDEN


# =================================== 403 own_media / 409 already_reported ===================================

def test_l_autor_no_pot_denunciar_el_seu_mitja(client, media):
    resp = report(client, media, 'u1', 'hate_speech')
    assert resp.status_code == 403
    assert resp.json() == {'error': 'own_media', 'code': 'own_media',
                           'message': 'No pots denunciar un contingut que has publicat tu'}
    assert count_reports() == 0 and media_status(media[1]) == 'visible'


def test_ja_denunciat_es_409_i_no_afegeix_res(client, media):
    assert report(client, media, 'u2', 'hate_speech').status_code == 201
    resp = report(client, media, 'u2', 'animal_cruelty')                       # fins i tot amb un altre motiu
    assert resp.status_code == 409
    assert resp.json() == {'error': 'already_reported', 'code': 'already_reported',
                           'message': 'Ja has denunciat aquest contingut'}
    assert count_reports() == 1 and report_rows()[0]['reason'] == 'hate_speech'


def test_el_409_no_trenca_la_transaccio_ni_amaga_ni_avisa(client, media):
    r, key = media
    assert report(client, media, 'u2', 'my_image').status_code == 201            # amaga i avisa un cop
    notices = len(notice_rows('u1'))
    resp = report(client, media, 'u2', 'my_image')
    assert resp.status_code == 409 and len(notice_rows('u1')) == notices == 1


def test_dos_usuaris_poden_denunciar_el_mateix_mitja(client, media):
    assert report(client, media, 'u2').status_code == 201
    assert report(client, media, 'u3').status_code == 201
    assert count_reports() == 2


# =================================== autoocultació ===================================

@pytest.mark.parametrize('reason', AUTO_HIDE)
def test_motius_greus_oculten_de_seguida_amb_prioritat_alta_i_avisen_l_autor(client, media, reason):
    r, key = media
    resp = report(client, media, 'u2', reason)
    assert resp.status_code == 201
    data = resp.json()
    assert data['media_hidden'] is True and data['priority'] == 'high'
    assert media_status(key) == HIDDEN
    [notice] = notice_rows('u1')
    assert (notice['type'], notice['action'], notice['automated']) == ('content_hidden', 'auto_hide', True)
    assert (notice['report_id'], notice['refuge_id'], notice['media_key'], notice['reason']) == (
        data['id'], str(r.pk), key, reason)
    assert notice['strikes'] is None and 'cautelar' in notice['statement']


def test_la_resta_de_motius_no_oculten_amb_una_o_dues_denuncies(client, media):
    for uid in ('u2', 'u3'):
        resp = report(client, media, uid, 'hate_speech')
        assert resp.json()['media_hidden'] is False
    assert media_status(media[1]) == 'visible' and notice_rows('u1') == []


def test_la_tercera_denuncia_de_denunciants_diferents_oculta(client, media):
    for uid in ('u2', 'u3'):
        report(client, media, uid, 'fraud_scam_spam')
    resp = report(client, media, 'u4', 'harassment_bullying')
    assert resp.json()['media_hidden'] is True and resp.json()['priority'] == 'normal'
    assert media_status(media[1]) == HIDDEN
    assert [n['type'] for n in notice_rows('u1')] == ['content_hidden']


def test_les_denuncies_ja_resoltes_no_compten_per_al_llindar(client, media):
    r, key = media
    for uid in ('u3', 'u4'):
        make_report(r, key, uid, 'hate_speech', creator='u1', status='resolved', action='dismiss')
    resp = report(client, media, 'u2', 'hate_speech')
    assert resp.json()['media_hidden'] is False and media_status(key) == 'visible'


def test_el_llindar_compta_denunciants_diferents_pendents_d_altres_usuaris(client, media):
    """La RLS només deixaria veure les pròpies: el recompte ha de veure les dels altres (system_context acotat)."""
    r, key = media
    for uid in ('u3', 'u4'):
        make_report(r, key, uid, 'hate_speech', creator='u1')
    resp = report(client, media, 'u2', 'hate_speech')
    assert resp.json()['media_hidden'] is True and media_status(key) == HIDDEN


def test_un_mitja_ja_ocult_no_es_torna_a_ocultar_ni_a_avisar(client, media):
    r, key = media
    first = report(client, media, 'u2', 'my_image')
    assert first.json()['media_hidden'] is True
    second = report(client, media, 'u3', 'child_endangerment')
    assert second.status_code == 201 and second.json()['media_hidden'] is False
    assert len(notice_rows('u1')) == 1 and media_status(key) == HIDDEN


def test_un_mitja_retirat_mentrestant_no_torna_a_ocultar(client, media):
    """`UPDATE … WHERE status = 'visible'`: un mitjà que un admin ha retirat mentrestant no torna a `hidden`."""
    r, key = media
    sql("UPDATE refuges.refuge_media SET status = 'removed' WHERE key = %s", [key])
    resp = report(client, media, 'u2', 'my_image')
    assert resp.status_code == 404                                              # retirat: no es pot denunciar (D-tècnica)
    assert media_status(key) == 'removed'


# =================================== permisos ===================================

def test_anonim_es_401(client, media):
    assert client.post(REPORTS, body(media), content_type='application/json').status_code == 401


def test_sense_perfil_es_403_profile_required(client, media):
    resp = api_post(client, REPORTS, user_claims('sense_perfil'), body(media))
    assert resp.status_code == 403 and resp.json()['error'] == 'profile_required'


def test_usuari_bloquejat_es_403_user_blocked(client, media):
    make_user('blk', is_blocked=True, blocked_reason='strikes', blocked_at=sql('SELECT now()')[0][0])
    resp = api_post(client, REPORTS, user_claims('blk'), body(media))
    assert resp.status_code == 403 and resp.json()['error'] == 'user_blocked'
    assert count_reports() == 0


def test_edat_sense_confirmar_es_403_age_not_confirmed(client, media):
    make_user('minor', age_confirmed_at=None, age_threshold=None)
    resp = api_post(client, REPORTS, user_claims('minor'), body(media))
    assert resp.status_code == 403 and resp.json()['error'] == 'age_not_confirmed'
    assert count_reports() == 0


# =================================== auditoria ===================================

@pytest.mark.real_audit_log
def test_registra_media_report_i_auto_hide_sense_dades_personals(client, media):
    r, key = media
    resp = report(client, media, 'u2', 'my_image')
    rid = resp.json()['id']
    [rep] = audit_rows('media.report')
    assert rep['actor_uid'] == 'u2' and (rep['target_type'], rep['target_id']) == ('media', key)
    assert rep['metadata'] == {'refuge_id': str(r.pk), 'reason': 'my_image', 'report_id': rid}
    assert rep['legal_hold'] is False
    [hide] = audit_rows('moderation.auto_hide')
    assert hide['actor_uid'] is None and (hide['target_type'], hide['target_id']) == ('media', key)
    assert hide['metadata']['refuge_id'] == str(r.pk) and 'u1' not in str(hide) and 'u2' not in str(hide['metadata'])


@pytest.mark.real_audit_log
def test_una_denuncia_csam_es_registra_amb_legal_hold(client, media):
    report(client, media, 'u2', 'child_sexual_abuse')
    [rep] = audit_rows('media.report')
    assert rep['legal_hold'] is True
    assert (rep['expire_at'] - rep['created_at']).days >= 1825
