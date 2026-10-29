"""
Contracte de `POST /api/media/upload-intents/` (chunk 7): mateixa URL, mateix JSON i mateixos codis que avui, però els
intents es desen a `moderation.upload_intents` (PostgreSQL) en lloc de Firestore.

- 201 `{uploads: [{upload_id, put_url, headers: {Content-Type}, expires_in: 600}]}`; `upload_id` és ara l'UUID v7 de la BD
  i `quarantine_key = quarantine/{upload_id}`; la URL PUT signa `ContentType` i `ContentLength`; `content_type` normalitzat
  (`image/jpg` -> `image/jpeg`); `rights_confirmed_at` = ara; `expire_at` = ara + 1 dia (durada real).
- 400 `{error: 'Dades invàlides', details}` (validació) o `{error: <text>}` per a `refuge_id` que no és el de l'experiència.
- 403 `not_owner` (experiència d'un altre; l'admin hi pot), 404 `{error: 'Refugi not found' | 'Experience not found'}` (també
  id que no és UUID), 500 `{error, error_id}` (política de les features migrades).
- Permisos (es documenta el que ja té la vista d'avui): `IsAuthenticated, HasProfile, IsNotBlocked, IsAgeConfirmed` en
  ordre. **No canvien** respecte d'avui.
"""
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.db import DatabaseError

from apps.experiences.tests.helpers import make_experience
from apps.uploads.tests.helpers import (
    INTENTS, NOT_OWNER_BODY, ZERO_UUID, admin_claims, api_post, at, file_spec, intent_body, intent_ids, intent_row,
    is_uuid, make_user, sql, user_claims)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration,
              pytest.mark.real_permissions]


def post(client, body, claims=None):
    return api_post(client, INTENTS, claims or user_claims('u1'), body)


# =================================== èxit ===================================

def test_refuge_201_forma_i_fila(client, world, r2store):
    r = world[0]
    resp = post(client, intent_body('refuge', r, files=[file_spec('image/jpg', 1234), file_spec('video/mp4', 5000)]))
    assert resp.status_code == 201, resp.content
    body = resp.json()
    assert set(body) == {'uploads'} and len(body['uploads']) == 2
    first, second = body['uploads']
    for up in body['uploads']:
        assert set(up) == {'upload_id', 'put_url', 'headers', 'expires_in'}
        assert is_uuid(up['upload_id']) and up['expires_in'] == 600
        assert f"quarantine/{up['upload_id']}" in up['put_url'] and 'op=put_object' in up['put_url']
    assert first['headers'] == {'Content-Type': 'image/jpeg'} and second['headers'] == {'Content-Type': 'video/mp4'}
    assert sorted(intent_ids('u1')) == sorted(u['upload_id'] for u in body['uploads'])
    row = intent_row(first['upload_id'])
    assert (row['user_uid'], row['target'], row['content_type'], row['size']) == ('u1', 'refuge', 'image/jpeg', 1234)
    assert row['refuge_id'] == str(r.pk) and row['experience_id'] is None
    assert row['quarantine_key'] == f"quarantine/{first['upload_id']}"
    assert (row['status'], row['result_key'], row['failure_reason']) == ('pending', None, None)
    assert row['rights_confirmed_at'] is not None
    assert row['expire_at'] - row['created_at'] == timedelta(days=1)


def test_la_url_put_signa_content_type_i_content_length(client, world, r2store):
    post(client, intent_body('refuge', world[0], files=[file_spec('image/png', 4321)]))
    call = r2store.client.generate_presigned_url.call_args_list[0]
    assert call.args[0] == 'put_object'
    params = call.kwargs['Params']
    assert params['ContentType'] == 'image/png' and params['ContentLength'] == 4321
    assert params['Key'].startswith('quarantine/') and call.kwargs['ExpiresIn'] == 600


def test_experience_target_deriva_el_refugi_de_l_experiencia(client, world):
    e = make_experience(world[0], 'u1')
    resp = post(client, intent_body('experience', experience_id=e))
    assert resp.status_code == 201
    row = intent_row(resp.json()['uploads'][0]['upload_id'])
    assert (row['target'], row['experience_id'], row['refuge_id']) == ('experience', e, str(world[0].pk))


def test_experience_target_amb_el_refuge_id_correcte(client, world):
    e = make_experience(world[0], 'u1')
    assert post(client, intent_body('experience', world[0], experience_id=e)).status_code == 201


def test_experience_target_amb_un_refuge_id_que_no_correspon_400(client, world):
    e = make_experience(world[0], 'u1')
    resp = post(client, intent_body('experience', world[1], experience_id=e))
    assert resp.status_code == 400 and resp.json() == {'error': "refuge_id no correspon a l'experiència"}
    assert intent_ids() == []


def test_avatar_201_sense_refugi_ni_experiencia(client, world):
    resp = post(client, intent_body('avatar', files=[file_spec('image/heic', 10)]))
    assert resp.status_code == 201
    row = intent_row(resp.json()['uploads'][0]['upload_id'])
    assert (row['target'], row['refuge_id'], row['experience_id'], row['content_type']) == ('avatar', None, None,
                                                                                            'image/heic')


def test_avatar_ignora_un_refuge_id_o_experience_id_del_cos(client, world):
    e = make_experience(world[0], 'u1')
    body = {**intent_body('avatar', files=[file_spec('image/png', 10)]), 'refuge_id': str(world[0].pk),
            'experience_id': e}
    resp = post(client, body)
    assert resp.status_code == 201
    row = intent_row(resp.json()['uploads'][0]['upload_id'])
    assert row['refuge_id'] is None and row['experience_id'] is None


def test_refuge_target_ignora_un_experience_id_del_cos(client, world):
    e = make_experience(world[0], 'u1')
    resp = post(client, {**intent_body('refuge', world[0]), 'experience_id': e})
    assert resp.status_code == 201 and intent_row(resp.json()['uploads'][0]['upload_id'])['experience_id'] is None


def test_l_admin_pot_crear_intents_per_a_l_experiencia_d_un_altre(client, world):
    e = make_experience(world[0], 'u1')
    resp = post(client, intent_body('experience', experience_id=e), admin_claims('adm'))
    assert resp.status_code == 201
    assert intent_row(resp.json()['uploads'][0]['upload_id'])['user_uid'] == 'adm'


def test_fins_a_10_fitxers(client, world):
    resp = post(client, intent_body('refuge', world[0], files=[file_spec('image/png', i + 1) for i in range(10)]))
    assert resp.status_code == 201 and len(resp.json()['uploads']) == 10 and len(intent_ids('u1')) == 10


def test_registra_l_auditoria_de_la_creacio(client, world, _mock_audit_log):
    from apps.audit import services as audit
    post(client, intent_body('refuge', world[0]))
    assert any(c.args[1] == audit.ACTION_UPLOAD_INTENT for c in _mock_audit_log.call_args_list)


# =================================== validació (400) ===================================

BAD_BODIES = [
    ('sense rights_confirmed', lambda r: {**intent_body('refuge', r), 'rights_confirmed': False}, 'rights_confirmed'),
    ('rights_confirmed absent', lambda r: {k: v for k, v in intent_body('refuge', r).items() if k != 'rights_confirmed'},
     'rights_confirmed'),
    ('target desconegut', lambda r: {**intent_body('refuge', r), 'target': 'banner'}, 'target'),
    ('refuge sense refuge_id', lambda r: intent_body('refuge'), 'refuge_id'),
    ('experience sense experience_id', lambda r: intent_body('experience', r), 'experience_id'),
    ('sense fitxers', lambda r: intent_body('refuge', r, files=[]), 'files'),
    ('massa fitxers', lambda r: intent_body('refuge', r, files=[file_spec('image/png', 1)] * 11), 'files'),
    ('tipus no permès', lambda r: intent_body('refuge', r, files=[file_spec('application/pdf', 5)]), 'files'),
    ('imatge massa gran', lambda r: intent_body('refuge', r, files=[file_spec('image/jpeg', 15 * 1024 * 1024 + 1)]),
     'files'),
    ('vídeo massa gran', lambda r: intent_body('refuge', r, files=[file_spec('video/mp4', 50 * 1024 * 1024 + 1)]),
     'files'),
    ('mida zero', lambda r: intent_body('refuge', r, files=[file_spec('image/png', 0)]), 'files'),
    ('avatar amb dos fitxers', lambda r: intent_body('avatar', files=[file_spec(), file_spec()]), 'files'),
    ('avatar amb vídeo', lambda r: intent_body('avatar', files=[file_spec('video/mp4', 10)]), 'files'),
]


@pytest.mark.parametrize('name,make_body,field', BAD_BODIES, ids=[b[0] for b in BAD_BODIES])
def test_validacio_400(client, world, name, make_body, field):
    resp = post(client, make_body(world[0]))
    assert resp.status_code == 400, resp.content
    body = resp.json()
    assert body['error'] == 'Dades invàlides' and field in body['details']
    assert intent_ids() == []


def test_cos_buit_400(client, world):
    resp = post(client, {})
    assert resp.status_code == 400 and {'target', 'rights_confirmed', 'files'} <= set(resp.json()['details'])


def test_el_400_va_abans_del_404(client, world):
    resp = post(client, {**intent_body('refuge', ZERO_UUID), 'rights_confirmed': False})
    assert resp.status_code == 400


# =================================== 404 / 403 ===================================

@pytest.mark.parametrize('rid', [ZERO_UUID, 'no-es-uuid', 'refugi_colomers', 'a%00b'])
def test_refugi_inexistent_o_id_no_uuid_404(client, world, rid):
    resp = post(client, intent_body('refuge', rid))
    assert resp.status_code == 404 and resp.json() == {'error': 'Refugi not found'}
    assert intent_ids() == []


@pytest.mark.parametrize('xid', [ZERO_UUID, 'no-es-uuid', 'exp_firestore_1'])
def test_experiencia_inexistent_o_id_no_uuid_404(client, world, xid):
    resp = post(client, intent_body('experience', experience_id=xid))
    assert resp.status_code == 404 and resp.json() == {'error': 'Experience not found'}
    assert intent_ids() == []


def test_experiencia_d_un_altre_403_not_owner(client, world):
    e = make_experience(world[0], 'u2')
    resp = post(client, intent_body('experience', experience_id=e))
    assert resp.status_code == 403 and resp.json() == NOT_OWNER_BODY
    assert intent_ids() == []


def test_no_es_pot_crear_intents_per_a_un_altre_usuari(client, world):
    """El propietari de l'intent és sempre l'usuari del token (no es pot passar `user_uid`/`uid` pel cos)."""
    resp = post(client, {**intent_body('refuge', world[0]), 'user_uid': 'u2', 'uid': 'u2'})
    assert resp.status_code == 201
    assert intent_ids('u2') == [] and len(intent_ids('u1')) == 1


# =================================== permisos (documentats; no canvien) ===================================

def test_anonim_401(client, world):
    assert api_post(client, INTENTS, None, intent_body('refuge', world[0])).status_code == 401


def test_sense_perfil_403_profile_required(client, world):
    for claims in (user_claims('ghost'), admin_claims('ghost')):
        r = post(client, intent_body('refuge', world[0]), claims)
        assert r.status_code == 403 and r.json()['error'] == 'profile_required'


def test_bloquejat_403_user_blocked(client, world):
    make_user('blk', is_blocked=True, blocked_reason='csam_confirmed', blocked_at=at())
    r = post(client, intent_body('refuge', world[0]), user_claims('blk'))
    assert r.status_code == 403 and r.json()['error'] == 'user_blocked' and intent_ids() == []


def test_sense_edat_confirmada_403(client, world):
    make_user('kid', age_confirmed_at=None, age_threshold=None)
    r = post(client, intent_body('refuge', world[0]), user_claims('kid'))
    assert r.status_code == 403 and r.json()['error'] == 'age_not_confirmed' and intent_ids() == []


def test_les_permission_classes_de_la_vista():
    from rest_framework.permissions import IsAuthenticated
    from apps.auth.permissions import HasProfile, IsAgeConfirmed, IsNotBlocked
    from apps.uploads import views
    for cls in (views.UploadIntentsAPIView, views.UploadIntentsConfirmAPIView):
        assert list(cls.permission_classes) == [IsAuthenticated, HasProfile, IsNotBlocked, IsAgeConfirmed]


def test_rutes_i_noms_conservats():
    from django.urls import resolve, reverse
    assert reverse('media_upload_intents') == '/api/media/upload-intents/'
    assert reverse('media_upload_intents_confirm') == '/api/media/upload-intents/confirm/'
    assert resolve('/api/media/upload-intents/').func.cls.__module__ == 'apps.uploads.views'
    assert resolve('/api/media/upload-intents/confirm/').func.cls.__module__ == 'apps.uploads.views'


# =================================== 500 ===================================

def test_error_de_bd_500_amb_error_id_i_sense_filtrar(client, world, caplog):
    import logging
    secret = 'SELECT secret host=db.neon.tech'
    with patch('apps.uploads.services.create_upload_intents', side_effect=DatabaseError(secret)), \
            caplog.at_level(logging.ERROR):
        resp = post(client, intent_body('refuge', world[0]))
    body = resp.json()
    assert resp.status_code == 500 and set(body) == {'error', 'error_id'} and secret not in resp.content.decode()
    assert any(body['error_id'] in r.getMessage() and r.exc_info for r in caplog.records)


def test_r2_no_pot_signar_500_i_no_deixa_files(client, world, r2store):
    r2store.client.generate_presigned_url.side_effect = Exception('r2 caigut: bucket=prod')
    resp = post(client, intent_body('refuge', world[0], files=[file_spec(), file_spec()]))
    assert resp.status_code == 500 and set(resp.json()) == {'error', 'error_id'} and 'prod' not in resp.text
    assert intent_ids() == []                              # tot o res: cap intent orfe sense URL


def test_un_error_a_la_segona_fila_no_deixa_la_primera(client, world, r2store):
    calls = {'n': 0}
    original = r2store.client.generate_presigned_url.side_effect

    def flaky(*a, **k):
        calls['n'] += 1
        if calls['n'] == 2:
            raise Exception('boom')
        return original(*a, **k)

    r2store.client.generate_presigned_url.side_effect = flaky
    resp = post(client, intent_body('refuge', world[0], files=[file_spec(), file_spec()]))
    assert resp.status_code == 500 and intent_ids() == []


def test_get_i_altres_metodes_no_permesos_405(client, world):
    from unittest.mock import patch as p
    from apps.uploads.tests.helpers import VERIFY
    with p(VERIFY, return_value=user_claims('u1')):
        assert client.get(INTENTS, HTTP_AUTHORIZATION='Bearer t').status_code == 405
