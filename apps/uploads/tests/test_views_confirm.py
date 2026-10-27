"""
Contracte de `POST /api/media/upload-intents/confirm/` (chunk 7): mateixa URL i JSON que avui; els intents es llegeixen
i s'actualitzen a PostgreSQL i el mitjà confirmat es publica a `refuges.refuge_media` (target `refuge`/`experience`) o a
`users.user_avatars` (target `avatar`) en lloc de Firestore.

Es manté el pipeline de `process_and_publish`: mida real, tipus real (magic bytes + obertura), neteja d'EXIF/GPS,
recodificació a WebP (2048 px) + miniatura (400 px), claus UUID, descarta `quarantine/` en acabar, rollback dels fitxers
si falla la BD o R2, fail-closed si la moderació falla. La hash-blocklist, les denúncies i els avisos segueixen a
Firestore fins al chunk 9 (es mocken a `conftest.py`).

- 200 `{uploaded: [MediaItem], failed: [{upload_id, reason}]}`; `reason` ∈ missing_object | too_large | invalid_type |
  processing_error | moderation_blocked. Un intent aliè, inexistent, caducat o d'id que no és UUID és `missing_object`.
- Idempotent: confirmar dues vegades el mateix `upload_id` retorna el mateix MediaItem sense publicar res de nou.
- 400 `{error: 'Dades invàlides', details}`, 500 `{error, error_id}`.
"""
import io
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from django.db import DatabaseError, connection
from PIL import Image

from api.services.image_processing_service import IMAGE_MAX_BYTES
from api.services.moderation_service import ModerationResult
from apps.experiences.tests.helpers import make_experience
from apps.uploads.tests.helpers import (
    CONFIRM, GPS_IFD, INTENTS, MEDIA_ITEM_KEYS, VERIFY, admin_claims, api_get, api_post, at, avatar_row, file_spec,
    intent_body, intent_row, make_avatar, make_intent, make_jpeg_with_gps, make_png, make_user, refuge_media_rows, sql,
    user_claims)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration,
              pytest.mark.real_permissions]


@contextmanager
def fail_statements(table, verb):
    """Fa fallar (`DatabaseError`) les sentències `verb` sobre `table`, sense dependre de com les emet el service."""
    def wrapper(execute, sql_, params, many, context):
        if sql_.lstrip().upper().startswith(verb) and table in sql_:
            raise DatabaseError('fallada simulada')
        return execute(sql_, params, many, context)
    with connection.execute_wrapper(wrapper):
        yield


def create_intent(client, r2store, data, target='refuge', refuge=None, experience_id=None, claims=None,
                  content_type='image/jpeg', put=True):
    """Crea l'intent per HTTP (com el client real) i, si `put`, «puja» els bytes a `quarantine/`. Retorna l'`upload_id`."""
    resp = api_post(client, INTENTS, claims or user_claims('u1'),
                    intent_body(target, refuge, experience_id, files=[file_spec(content_type, len(data))]))
    assert resp.status_code == 201, resp.content
    upload_id = resp.json()['uploads'][0]['upload_id']
    if put:
        r2store.put_quarantine(upload_id, data)
    return upload_id


def confirm(client, ids, claims=None):
    return api_post(client, CONFIRM, claims or user_claims('u1'), {'upload_ids': ids})


def published_keys(r2store):
    return [k for k in r2store.keys() if not k.startswith(('quarantine/', 'moderation-hold/'))]


def assert_failed(resp, upload_id, reason):
    assert resp.status_code == 200, resp.content
    assert resp.json() == {'uploaded': [], 'failed': [{'upload_id': upload_id, 'reason': reason}]}


# =================================== èxit: refugi ===================================

def test_refuge_publica_a_postgres_i_a_r2(client, world, r2store):
    r = world[0]
    data = make_jpeg_with_gps((1000, 800), orientation=1)
    uid = create_intent(client, r2store, data, 'refuge', r)
    resp = confirm(client, [uid])
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert set(body) == {'uploaded', 'failed'} and body['failed'] == [] and len(body['uploaded']) == 1
    item = body['uploaded'][0]
    assert set(item) == MEDIA_ITEM_KEYS
    assert item['media_type'] == 'image' and item['creator_uid'] == 'u1' and item['experience_id'] is None
    assert item['key'].startswith(f'refugis-lliures/{r.pk}/') and item['key'].endswith('.webp')
    assert uuid.UUID(item['key'].rsplit('/', 1)[1].removesuffix('.webp'))               # clau UUID, no el nom del client
    assert item['url'].startswith('https://r2.test/') and item['thumb_url'] != item['url']
    assert (item['width'], item['height']) == (1000, 800) and item['blurhash'] and item['uploaded_at']
    assert item['taken_at'] == '2024-07-15T10:20:30+02:00'                       # la data EXIF es conserva, el GPS no

    rows = refuge_media_rows(r)
    assert len(rows) == 1
    row = rows[0]
    assert row['key'] == item['key'] and row['creator_uid'] == 'u1' and row['status'] == 'visible'
    assert row['experience_id'] is None and row['media_type'] == 'image' and row['content_type'] == 'image/webp'
    assert row['thumb_key'] == item['key'].removesuffix('.webp') + '_thumb.webp'
    assert row['width'] == item['width'] and row['height'] == item['height'] and row['blurhash'] == item['blurhash']
    assert row['size_bytes'] == len(r2store.store[row['key']])
    assert row['rights_confirmed_at'] == intent_row(uid)['rights_confirmed_at']
    assert row['taken_at'] == datetime(2024, 7, 15, 8, 20, 30, tzinfo=timezone.utc)


def test_refuge_neteja_exif_i_gps_i_recodifica_a_webp(client, world, r2store):
    uid = create_intent(client, r2store, make_jpeg_with_gps((3000, 2000), orientation=1), 'refuge', world[0])
    item = confirm(client, [uid]).json()['uploaded'][0]
    for key in (item['key'], item['key'].removesuffix('.webp') + '_thumb.webp'):
        img = Image.open(io.BytesIO(r2store.store[key]))
        assert img.format == 'WEBP'
        assert dict(img.getexif()) == {} and not img.getexif().get_ifd(GPS_IFD)      # sense cap metadada
        assert max(img.size) == (2048 if not key.endswith('_thumb.webp') else 400)


def test_refuge_descarta_quarantine_i_marca_l_intent_com_a_confirmat(client, world, r2store):
    uid = create_intent(client, r2store, make_png(), 'refuge', world[0], content_type='image/png')
    item = confirm(client, [uid]).json()['uploaded'][0]
    assert f'quarantine/{uid}' not in r2store.store and f'quarantine/{uid}' in r2store.deletes
    row = intent_row(uid)
    assert (row['status'], row['result_key'], row['failure_reason']) == ('confirmed', item['key'], None)


def test_refuge_diverses_pujades_en_una_sola_confirmacio(client, world, r2store):
    ids = [create_intent(client, r2store, make_png((100 + i, 100)), 'refuge', world[0], content_type='image/png')
           for i in range(3)]
    body = confirm(client, ids).json()
    assert [i['key'] for i in body['uploaded']] and len(body['uploaded']) == 3 and body['failed'] == []
    assert len({i['key'] for i in body['uploaded']}) == 3 and len(refuge_media_rows(world[0])) == 3


def test_el_mitja_publicat_surt_a_les_lectures_del_refugi_i_al_perfil(client, world, r2store):
    r = world[0]
    uid = create_intent(client, r2store, make_png(), 'refuge', r, content_type='image/png')
    key = confirm(client, [uid]).json()['uploaded'][0]['key']
    media = api_get(client, f'/api/refuges/{r.pk}/media/', user_claims('u2')).json()
    assert [m['key'] for m in media['media']] == [key]
    profile = api_get(client, '/api/users/u1/', user_claims('u1')).json()
    assert profile['uploaded_photos_keys'] == [key]


def test_confirma_el_registre_d_auditoria(client, world, r2store, _mock_audit_log):
    from api.services import audit_log_service as audit
    uid = create_intent(client, r2store, make_png(), 'refuge', world[0], content_type='image/png')
    confirm(client, [uid])
    assert any(c.args[1] == audit.ACTION_UPLOAD_CONFIRM for c in _mock_audit_log.call_args_list)


# =================================== èxit: experiència ===================================

def test_experience_publica_amb_experience_id(client, world, r2store):
    r = world[0]
    e = make_experience(r, 'u1')
    uid = create_intent(client, r2store, make_png(), 'experience', experience_id=e, content_type='image/png')
    item = confirm(client, [uid]).json()['uploaded'][0]
    assert item['experience_id'] == e and item['key'].startswith(f'refugis-lliures/{r.pk}/')
    row = refuge_media_rows(r)[0]
    assert row['experience_id'] == e and row['creator_uid'] == 'u1' and row['refuge_id'] == str(r.pk)


def test_el_mitja_d_experiencia_surt_a_la_llista_d_experiencies_i_a_les_fotos_del_refugi(client, world, r2store):
    r = world[0]
    e = make_experience(r, 'u1')
    uid = create_intent(client, r2store, make_png(), 'experience', experience_id=e, content_type='image/png')
    key = confirm(client, [uid]).json()['uploaded'][0]['key']
    listing = api_get(client, f'/api/experiences/?refuge_id={r.pk}', user_claims('u2')).json()
    assert [i['key'] for i in listing['experiences'][0]['images_metadata']] == [key]
    media = api_get(client, f'/api/refuges/{r.pk}/media/', user_claims('u2')).json()['media']
    assert [(m['key'], m['experience_id']) for m in media] == [(key, e)]


def test_l_admin_confirma_per_a_l_experiencia_d_un_altre_i_n_es_el_creador_del_mitja(client, world, r2store):
    r = world[0]
    e = make_experience(r, 'u1')
    uid = create_intent(client, r2store, make_png(), 'experience', experience_id=e, claims=admin_claims('adm'),
                        content_type='image/png')
    item = confirm(client, [uid], admin_claims('adm')).json()['uploaded'][0]
    row = refuge_media_rows(r)[0]
    assert row['creator_uid'] == 'adm' and row['experience_id'] == e and item['creator_uid'] == 'adm'


def test_l_experiencia_esborrada_abans_de_confirmar_es_missing_object_i_no_publica_res(client, world, r2store):
    r = world[0]
    e = make_experience(r, 'u1')
    uid = create_intent(client, r2store, make_png(), 'experience', experience_id=e, content_type='image/png')
    sql('DELETE FROM activity.experiences WHERE id = %s', [e])               # la FK cascadeja l'intent
    assert_failed(confirm(client, [uid]), uid, 'missing_object')
    assert refuge_media_rows() == [] and published_keys(r2store) == []


def test_el_refugi_esborrat_abans_de_confirmar_es_missing_object(client, world, r2store):
    from apps.uploads.tests.helpers import as_owner
    uid = create_intent(client, r2store, make_png(), 'refuge', world[0], content_type='image/png')
    with as_owner():
        sql('DELETE FROM refuges.refuges WHERE id = %s', [world[0].pk])
    assert_failed(confirm(client, [uid]), uid, 'missing_object')
    assert published_keys(r2store) == []


# =================================== èxit: avatar ===================================

def test_avatar_publica_a_user_avatars(client, world, r2store):
    uid = create_intent(client, r2store, make_jpeg_with_gps((1500, 1500), orientation=1), 'avatar')
    resp = confirm(client, [uid])
    assert resp.status_code == 200, resp.content
    item = resp.json()['uploaded'][0]
    assert resp.json()['failed'] == [] and set(item) == MEDIA_ITEM_KEYS
    assert item['key'].startswith('users-avatars/u1/') and item['creator_uid'] == 'u1' and item['experience_id'] is None
    row = avatar_row('u1')
    assert row['key'] == item['key'] and row['content_type'] == 'image/webp' and row['blurhash'] == item['blurhash']
    assert row['width'] == item['width'] and row['height'] == item['height']
    assert refuge_media_rows() == []                                     # l'avatar no és un mitjà de refugi
    assert intent_row(uid)['result_key'] == item['key'] and intent_row(uid)['status'] == 'confirmed'
    assert item['width'] == 512 and item['thumb_url'] == item['url']                 # avatar: 512 px i sense miniatura
    img = Image.open(io.BytesIO(r2store.store[item['key']]))
    assert img.format == 'WEBP' and dict(img.getexif()) == {}


def test_avatar_nou_substitueix_l_antic_i_l_esborra_de_r2_despres(client, world, r2store):
    make_avatar('u1', key='users-avatars/u1/old.webp', thumb_key='users-avatars/u1/old_t.webp')
    r2store.store['users-avatars/u1/old.webp'] = b'old'
    r2store.store['users-avatars/u1/old_t.webp'] = b'old-t'
    uid = create_intent(client, r2store, make_png(), 'avatar', content_type='image/png')
    item = confirm(client, [uid]).json()['uploaded'][0]
    assert avatar_row('u1')['key'] == item['key']
    assert sql("SELECT count(*) FROM users.user_avatars WHERE user_uid = 'u1'") == [(1,)]
    assert 'users-avatars/u1/old.webp' not in r2store.store and 'users-avatars/u1/old_t.webp' not in r2store.store
    assert item['key'] in r2store.store


def test_si_falla_la_bd_l_avatar_antic_es_conserva_i_el_nou_es_retira(client, world, r2store):
    make_avatar('u1', key='users-avatars/u1/old.webp')
    r2store.store['users-avatars/u1/old.webp'] = b'old'
    uid = create_intent(client, r2store, make_png(), 'avatar', content_type='image/png')
    with fail_statements('user_avatars', 'INSERT'):
        resp = confirm(client, [uid])
    assert_failed(resp, uid, 'processing_error')
    assert avatar_row('u1')['key'] == 'users-avatars/u1/old.webp'
    assert 'users-avatars/u1/old.webp' in r2store.store
    assert published_keys(r2store) == ['users-avatars/u1/old.webp']          # el nou s'ha retirat (rollback)


# =================================== idempotència ===================================

def test_reconfirmar_retorna_el_mateix_mitja_sense_publicar_res_de_nou(client, world, r2store):
    uid = create_intent(client, r2store, make_png(), 'refuge', world[0], content_type='image/png')
    first = confirm(client, [uid]).json()['uploaded'][0]
    files_before, puts_before = published_keys(r2store), len(r2store.puts)
    again = confirm(client, [uid])
    assert again.status_code == 200 and again.json() == {'uploaded': [first], 'failed': []}
    assert published_keys(r2store) == files_before and len(r2store.puts) == puts_before
    assert len(refuge_media_rows()) == 1


def test_reconfirmar_un_avatar_retorna_el_mateix_item(client, world, r2store):
    uid = create_intent(client, r2store, make_png(), 'avatar', content_type='image/png')
    first = confirm(client, [uid]).json()['uploaded'][0]
    again = confirm(client, [uid]).json()
    assert again['uploaded'] == [first] and again['failed'] == []


def test_reconfirmar_si_el_mitja_ja_s_ha_esborrat_es_missing_object(client, world, r2store):
    uid = create_intent(client, r2store, make_png(), 'refuge', world[0], content_type='image/png')
    key = confirm(client, [uid]).json()['uploaded'][0]['key']
    sql('DELETE FROM refuges.refuge_media WHERE key = %s', [key])
    assert_failed(confirm(client, [uid]), uid, 'missing_object')


def test_ids_repetits_es_processen_una_sola_vegada(client, world, r2store):
    uid = create_intent(client, r2store, make_png(), 'refuge', world[0], content_type='image/png')
    body = confirm(client, [uid, uid, uid]).json()
    assert len(body['uploaded']) == 1 and body['failed'] == [] and len(refuge_media_rows()) == 1


# =================================== fallades per fitxer (200 amb `failed`) ===================================

def test_sense_objecte_a_quarantine_es_missing_object_i_l_intent_segueix_pending(client, world, r2store):
    uid = create_intent(client, r2store, make_png(), 'refuge', world[0], content_type='image/png', put=False)
    assert_failed(confirm(client, [uid]), uid, 'missing_object')
    assert intent_row(uid)['status'] == 'pending'
    r2store.put_quarantine(uid, make_png())                              # el client reintenta el PUT i torna a confirmar
    assert len(confirm(client, [uid]).json()['uploaded']) == 1


@pytest.mark.parametrize('bad', ['00000000-0000-0000-0000-000000000000', 'no-es-uuid', 'a%00b', "x'; DROP TABLE x;--",
                                 'x' * 128])
def test_upload_id_inexistent_o_que_no_es_uuid_es_missing_object_i_mai_500(client, world, bad):
    assert_failed(confirm(client, [bad]), bad, 'missing_object')


def test_l_intent_d_un_altre_usuari_es_missing_object_i_no_es_toca(client, world, r2store):
    uid = create_intent(client, r2store, make_png(), 'refuge', world[0], content_type='image/png')
    assert_failed(confirm(client, [uid], user_claims('u2')), uid, 'missing_object')
    assert intent_row(uid)['status'] == 'pending' and f'quarantine/{uid}' in r2store.store
    assert refuge_media_rows() == [] and published_keys(r2store) == []


def test_l_admin_tampoc_confirma_intents_aliens(client, world, r2store):
    uid = create_intent(client, r2store, make_png(), 'refuge', world[0], content_type='image/png')
    assert_failed(confirm(client, [uid], admin_claims('adm')), uid, 'missing_object')


def test_intent_caducat_es_missing_object(client, world, r2store):
    uid = make_intent('u1', 'refuge', refuge=world[0], created_ago=timedelta(days=2), expires_in=-timedelta(days=1))
    r2store.put_quarantine(uid, make_png())
    assert_failed(confirm(client, [uid]), uid, 'missing_object')
    assert refuge_media_rows() == []


def test_massa_gran_al_bucket_es_too_large_i_es_descarta(client, world, r2store):
    uid = create_intent(client, r2store, make_png(), 'refuge', world[0], content_type='image/png')
    r2store.put_quarantine(uid, b'\0' * (IMAGE_MAX_BYTES + 1))           # el client ha pujat més del que va declarar
    assert_failed(confirm(client, [uid]), uid, 'too_large')
    row = intent_row(uid)
    assert (row['status'], row['failure_reason']) == ('failed', 'too_large')
    assert f'quarantine/{uid}' not in r2store.store and refuge_media_rows() == []
    assert_failed(confirm(client, [uid]), uid, 'too_large')                # un reintent retorna el motiu desat


def test_bytes_que_no_son_una_imatge_son_invalid_type(client, world, r2store):
    uid = create_intent(client, r2store, b'<?php echo 1; ?>' * 10, 'refuge', world[0], content_type='image/jpeg')
    assert_failed(confirm(client, [uid]), uid, 'invalid_type')
    row = intent_row(uid)
    assert (row['status'], row['failure_reason']) == ('failed', 'invalid_type')
    assert f'quarantine/{uid}' not in r2store.store and published_keys(r2store) == [] and refuge_media_rows() == []


def test_un_intent_ja_fallat_retorna_el_motiu_sense_reprocessar(client, world, r2store):
    uid = make_intent('u1', 'refuge', refuge=world[0], status='failed', failure_reason='invalid_type')
    r2store.put_quarantine(uid, make_png())
    assert_failed(confirm(client, [uid]), uid, 'invalid_type')
    assert refuge_media_rows() == []


def test_mixt_alguns_be_i_alguns_malament(client, world, r2store):
    ok = create_intent(client, r2store, make_png(), 'refuge', world[0], content_type='image/png')
    missing = create_intent(client, r2store, make_png(), 'refuge', world[0], content_type='image/png', put=False)
    bad = create_intent(client, r2store, b'no es una imatge', 'refuge', world[0])
    body = confirm(client, [ok, missing, bad]).json()
    assert [u['key'] for u in body['uploaded']] and len(body['uploaded']) == 1
    assert body['failed'] == [{'upload_id': missing, 'reason': 'missing_object'},
                              {'upload_id': bad, 'reason': 'invalid_type'}]
    assert len(refuge_media_rows()) == 1


# =================================== moderació ===================================

def test_coincidencia_amb_la_blocklist_bloqueja_l_usuari_i_no_publica(client, world, r2store, moderation):
    moderation.check.return_value = ModerationResult(True, provider='hash', category='csam', match_type='sha256')
    uid = create_intent(client, r2store, make_png(), 'refuge', world[0], content_type='image/png')
    assert_failed(confirm(client, [uid]), uid, 'moderation_blocked')
    row = intent_row(uid)
    assert (row['status'], row['failure_reason']) == ('failed', 'moderation_blocked')
    assert refuge_media_rows() == [] and published_keys(r2store) == []
    user = sql("SELECT is_blocked, blocked_reason FROM users.users WHERE uid = 'u1'")
    assert user == [(True, 'moderation_hash_match')]
    # l'evidència es conserva a moderation-hold/ i no queda res a quarantine/
    assert f'quarantine/{uid}' not in r2store.store and r2store.keys('moderation-hold/')
    moderation.create_report.assert_called_once()
    moderation.create_notice.assert_called_once()


def test_despres_del_bloqueig_l_usuari_ja_no_pot_confirmar_ni_crear_intents(client, world, r2store, moderation):
    moderation.check.return_value = ModerationResult(True, provider='hash', category='csam', match_type='sha256')
    uid = create_intent(client, r2store, make_png(), 'refuge', world[0], content_type='image/png')
    confirm(client, [uid])
    assert confirm(client, [uid]).status_code == 403
    assert api_post(client, INTENTS, user_claims('u1'), intent_body('refuge', world[0])).status_code == 403


def test_si_la_moderacio_falla_es_fail_closed(client, world, r2store, moderation):
    moderation.check.side_effect = Exception('proveïdor caigut')
    uid = create_intent(client, r2store, make_png(), 'refuge', world[0], content_type='image/png')
    assert_failed(confirm(client, [uid]), uid, 'processing_error')
    assert intent_row(uid)['failure_reason'] == 'processing_error'
    assert refuge_media_rows() == [] and published_keys(r2store) == []
    assert sql("SELECT is_blocked FROM users.users WHERE uid = 'u1'") == [(False,)]


def test_la_moderacio_rep_el_hash_del_contingut_processat(client, world, r2store, moderation):
    uid = create_intent(client, r2store, make_png(), 'refuge', world[0], content_type='image/png')
    confirm(client, [uid])
    inp = moderation.check.call_args.args[0]
    assert inp.sha256 and len(inp.sha256) == 64 and inp.media_type == 'image'


# =================================== rollbacks de R2 / BD ===================================

def test_si_falla_la_pujada_de_la_miniatura_es_retira_tot_i_es_processing_error(client, world, r2store):
    uid = create_intent(client, r2store, make_png(), 'refuge', world[0], content_type='image/png')
    r2store.fail_put_for = ('_thumb.webp',)
    assert_failed(confirm(client, [uid]), uid, 'processing_error')
    assert published_keys(r2store) == [] and refuge_media_rows() == []
    assert intent_row(uid)['status'] == 'failed'


def test_si_falla_l_insert_a_la_bd_es_retiren_els_fitxers_i_l_intent_queda_fallat(client, world, r2store):
    """Un error de BD en publicar no pot ser un 500 ni deixar fitxers orfes: `failed: processing_error`, com avui."""
    uid = create_intent(client, r2store, make_png(), 'refuge', world[0], content_type='image/png')
    with fail_statements('refuge_media', 'INSERT'):
        resp = confirm(client, [uid])
    assert_failed(resp, uid, 'processing_error')
    assert published_keys(r2store) == [] and refuge_media_rows() == []
    assert intent_row(uid)['status'] == 'failed' and intent_row(uid)['failure_reason'] == 'processing_error'


# =================================== validació, permisos, 500 ===================================

@pytest.mark.parametrize('body', [{}, {'upload_ids': []}, {'upload_ids': 'abc'}, {'upload_ids': ['a'] * 11},
                                  {'upload_ids': [['a']]}, {'upload_ids': ['x' * 129]}, {'ids': ['a']}])
def test_validacio_400(client, world, body):
    resp = api_post(client, CONFIRM, user_claims('u1'), body)
    assert resp.status_code == 400 and resp.json()['error'] == 'Dades invàlides' and 'upload_ids' in resp.json()['details']


def test_fins_a_10_ids(client, world):
    ids = [str(uuid.uuid4()) for _ in range(10)]
    resp = confirm(client, ids)
    assert resp.status_code == 200 and len(resp.json()['failed']) == 10


def test_anonim_401_i_sense_perfil_403(client, world):
    assert api_post(client, CONFIRM, None, {'upload_ids': ['a']}).status_code == 401
    r = confirm(client, ['a'], user_claims('ghost'))
    assert r.status_code == 403 and r.json()['error'] == 'profile_required'


def test_bloquejat_i_sense_edat_403(client, world):
    make_user('blk', is_blocked=True, blocked_reason='csam_confirmed', blocked_at=at())
    make_user('kid', age_confirmed_at=None, age_threshold=None)
    assert confirm(client, ['a'], user_claims('blk')).json()['error'] == 'user_blocked'
    assert confirm(client, ['a'], user_claims('kid')).json()['error'] == 'age_not_confirmed'


def test_error_inesperat_500_amb_error_id(client, world, caplog):
    import logging
    secret = 'bucket=prod host=r2.cloudflarestorage.com'
    with patch('apps.uploads.services.confirm_upload_intents', side_effect=RuntimeError(secret)), \
            caplog.at_level(logging.ERROR):
        resp = confirm(client, [str(uuid.uuid4())])
    body = resp.json()
    assert resp.status_code == 500 and set(body) == {'error', 'error_id'} and secret not in resp.content.decode()
    assert any(body['error_id'] in r.getMessage() and r.exc_info for r in caplog.records)


def test_get_405(client, world):
    with patch(VERIFY, return_value=user_claims('u1')):
        assert client.get(CONFIRM, HTTP_AUTHORIZATION='Bearer t').status_code == 405
