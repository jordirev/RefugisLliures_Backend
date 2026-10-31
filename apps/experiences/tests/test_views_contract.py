"""
Contracte HTTP de `/api/experiences/` i `/api/experiences/{id}/` (chunk 7), vistes a `apps/experiences/views.py`
(`ExperienceListAPIView`, `ExperienceDetailAPIView`; mateixos noms de ruta: `experience_list`, `experience_detail`).

Forma i codis d'avui, amb el camp nou `condition` (§5.2) i IDs UUID:
- `GET /api/experiences/?refuge_id=X` -> 200 `{experiences: [Experience]}` per `modified_at DESC, id DESC`; cada una
  `{id, refuge_id, creator_uid, modified_at (ISO Madrid), comment, condition, images_metadata: [MediaItem]}`. Sense `refuge_id`
  400 `{error}`; refugi inexistent o id no UUID 404 `{error: 'Refuge not found'}`.
- `POST /api/experiences/` cos JSON `{refuge_id, comment, condition}` -> 201 `{experience: {...}}`; 400 `{error: 'Dades
  invàlides', details}`; refugi inexistent o no UUID 404 `{error: 'Refuge not found'}`; multipart 415.
- `PATCH /api/experiences/{id}/` cos `{comment?, condition?}` -> 200 `{experience}`; 404 `{error: 'Experience not found'}`
  (també id no UUID); 403 `not_owner` (`{error, code, message}`) si no és el creador ni admin.
- `DELETE /api/experiences/{id}/` -> 200 `{success: true, message: 'Experiència eliminada correctament'}` (NO 204: es
  manté el contracte d'avui); mateixos 404/403.
- Ordre de comprovacions: permisos -> validació del cos (400) -> existència (404) -> propietat (403).
- Els mitjans amagats (`status != visible`) només els veuen el seu autor i els admins.
"""
from datetime import datetime
from unittest.mock import patch

import pytest

from apps.experiences.tests.helpers import (
    EXP_KEYS, EXPERIENCES, MEDIA_ITEM_KEYS, NOT_OWNER, VERIFY, ZERO_UUID, admin_claims, api_delete, api_get, api_patch,
    api_post, deleted_keys, exp_ids, exp_row, exp_url, is_uuid, list_url, make_exp_media, make_experience, make_media,
    make_refuge, make_user, media_keys_of, new_body, refuge_state, user_claims)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration,
              pytest.mark.real_permissions]

NOT_OWNER_BODY = {'error': NOT_OWNER, 'code': NOT_OWNER, 'message': "No ets el creador d'aquesta experiència"}


# =================================== GET ===================================

def test_llista_buida(client, world):
    r = api_get(client, list_url(world[0].pk), user_claims('u1'))
    assert r.status_code == 200 and r.json() == {'experiences': []}


def test_forma_i_ordre_de_la_llista(client, world):
    r1, r2 = world
    old = make_experience(r1, 'u1', comment='antiga', condition=1, minutes=0)
    new = make_experience(r1, 'u2', comment='nova', condition=3, minutes=10)
    make_experience(r2, 'u3', comment='altre refugi', minutes=5)
    resp = api_get(client, list_url(r1.pk), user_claims('u3'))
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {'experiences'}
    assert [e['id'] for e in body['experiences']] == [new, old]                # modified_at DESC
    n, o = body['experiences']
    assert set(n) == EXP_KEYS and set(o) == EXP_KEYS                            # sense media_keys ni created_at
    assert (n['refuge_id'], n['creator_uid'], n['comment'], n['condition']) == (str(r1.pk), 'u2', 'nova', 3)
    assert o['condition'] == 1 and o['images_metadata'] == []
    assert o['modified_at'] == '2025-01-01T11:00:00+01:00'                      # ISO amb desplaçament de Madrid
    assert is_uuid(n['id'])


def test_empat_de_modified_at_es_resol_per_id_descendent(client, world):
    a = make_experience(world[0], 'u1', minutes=5)
    b = make_experience(world[0], 'u2', minutes=5)
    ids = [e['id'] for e in api_get(client, list_url(world[0].pk), user_claims('u1')).json()['experiences']]
    assert ids == sorted([a, b], reverse=True)


def test_la_llista_es_visible_per_a_qualsevol_usuari_amb_perfil_i_admin(client, world):
    make_experience(world[0], 'u1')
    for claims in (user_claims('u2'), user_claims('u1'), admin_claims('adm')):
        r = api_get(client, list_url(world[0].pk), claims)
        assert r.status_code == 200 and len(r.json()['experiences']) == 1


def test_images_metadata_amb_la_forma_de_mediaitem_i_experience_id(client, world):
    r = world[0]
    e = make_experience(r, 'u1')
    make_exp_media(r, 'u1', e, key='k/b.webp', minutes=2, thumb_key='k/b_thumb.webp', width=800, height=600,
                   blurhash='LKO2')
    make_exp_media(r, 'u1', e, key='k/a.webp', minutes=1)
    make_media(r, 'u1', key='k/foto-refugi.webp', minutes=0)                   # sense experiència: no surt aquí
    other = make_experience(r, 'u2', minutes=3)
    make_exp_media(r, 'u2', other, key='k/o.webp')
    resp = api_get(client, list_url(r.pk), user_claims('u3'))
    by_id = {x['id']: x for x in resp.json()['experiences']}
    items = by_id[e]['images_metadata']
    assert [i['key'] for i in items] == ['k/b.webp', 'k/a.webp']                # (uploaded_at DESC, key DESC)
    assert all(set(i) == MEDIA_ITEM_KEYS for i in items)
    assert all(i['experience_id'] == e and i['creator_uid'] == 'u1' for i in items)
    b = items[1]
    assert b['url'] == 'https://r2.test/k/b.webp?sig=1' and b['thumb_url'] == 'https://r2.test/k/b_thumb.webp?sig=1'
    assert (b['width'], b['height'], b['blurhash'], b['media_type']) == (800, 600, 'LKO2', 'image')
    assert items[0]['thumb_url'] == items[0]['url']                             # sense miniatura: thumb_url = url
    assert [i['key'] for i in by_id[other]['images_metadata']] == ['k/o.webp']


@pytest.mark.parametrize('claims,sees', [(user_claims('u3'), False), (user_claims('u1'), True),
                                         (user_claims('u2'), False), (admin_claims('adm'), True)])
def test_mitjans_amagats_nomes_per_a_l_autor_i_els_admins(client, world, claims, sees):
    r = world[0]
    e = make_experience(r, 'u2')
    make_exp_media(r, 'u2', e, key='k/visible.webp', minutes=1)
    make_exp_media(r, 'u1', e, key='k/hidden.webp', status='hidden_pending_review', minutes=2)    # l'autor és u1
    make_exp_media(r, 'u2', e, key='k/removed.webp', status='removed', minutes=3)
    items = api_get(client, list_url(r.pk), claims).json()['experiences'][0]['images_metadata']
    keys = [i['key'] for i in items]
    if claims['uid'] == 'adm':
        assert keys == ['k/visible.webp', 'k/hidden.webp', 'k/removed.webp']
    elif claims['uid'] == 'u2':                          # autor de visible i removed
        assert keys == ['k/visible.webp', 'k/removed.webp']
    elif sees:
        assert keys == ['k/visible.webp', 'k/hidden.webp']
    else:
        assert keys == ['k/visible.webp']


def test_get_sense_refuge_id_400(client, world):
    for path in (EXPERIENCES, EXPERIENCES + '?refuge_id='):
        r = api_get(client, path, user_claims('u1'))
        assert r.status_code == 400
        assert r.json() == {'error': 'El refuge_id és requerit. El path és /api/experiences/?refuge_id=refuge_id'}


@pytest.mark.parametrize('rid', ['no-es-uuid', 'refugi_colomers', 'a%00b', '0' * 200, ZERO_UUID,
                                 "1'%20OR%20'1'='1"])
def test_get_refugi_inexistent_o_id_no_uuid_404(client, world, rid):
    r = api_get(client, list_url(rid), user_claims('u1'))
    assert r.status_code == 404 and r.json() == {'error': 'Refuge not found'}


# =================================== POST ===================================

def test_post_crea_i_retorna_201_amb_la_forma_del_contracte(client, world):
    r = world[0]
    resp = api_post(client, EXPERIENCES, user_claims('u1'), new_body(r, 'Refugi net i amb llenya.', 3))
    assert resp.status_code == 201, resp.content
    body = resp.json()
    assert set(body) == {'experience'}
    e = body['experience']
    assert set(e) == EXP_KEYS
    assert is_uuid(e['id']) and e['refuge_id'] == str(r.pk) and e['creator_uid'] == 'u1'
    assert (e['comment'], e['condition'], e['images_metadata']) == ('Refugi net i amb llenya.', 3, [])
    row = exp_row(e['id'])
    assert row['creator_uid'] == 'u1' and row['condition'] == 3 and row['comment'] == 'Refugi net i amb llenya.'
    assert datetime.fromisoformat(e['modified_at']) == row['modified_at'] and e['modified_at'].endswith(('+01:00', '+02:00'))


def test_post_actualitza_la_mitjana_del_refugi(client, world):
    r = world[0]
    assert refuge_state(r)[:2] == (None, 0)
    api_post(client, EXPERIENCES, user_claims('u1'), new_body(r, condition=3))
    api_post(client, EXPERIENCES, user_claims('u2'), new_body(r, condition=1))
    c, n, _ = refuge_state(r)
    assert n == 2 and c == pytest.approx(2.0)


def test_post_el_creador_es_sempre_l_usuari_del_token(client, world):
    body = {**new_body(world[0]), 'creator_uid': 'u2', 'id': 'x', 'media_keys': ['k'], 'modified_at': '2000-01-01'}
    e = api_post(client, EXPERIENCES, user_claims('u1'), body).json()['experience']
    assert e['creator_uid'] == 'u1' and e['id'] != 'x' and e['images_metadata'] == []
    assert exp_row(e['id'])['modified_at'].year >= 2025


@pytest.mark.parametrize('mutation', [
    {'comment': ''}, {'comment': '   '}, {'comment': 'x' * 2001}, {'refuge_id': ''}, {'condition': 4},
    {'condition': -1}, {'condition': 'molt bo'}, {'condition': None}])
def test_post_dades_invalides_400(client, world, mutation):
    resp = api_post(client, EXPERIENCES, user_claims('u1'), {**new_body(world[0]), **mutation})
    assert resp.status_code == 400
    body = resp.json()
    assert body['error'] == 'Dades invàlides' and set(body['details']) == set(mutation)
    assert exp_ids() == [] and refuge_state(world[0])[:2] == (None, 0)


@pytest.mark.parametrize('missing', ['refuge_id', 'comment', 'condition'])
def test_post_camp_obligatori_absent_400(client, world, missing):
    body = {k: v for k, v in new_body(world[0]).items() if k != missing}
    resp = api_post(client, EXPERIENCES, user_claims('u1'), body)
    assert resp.status_code == 400 and missing in resp.json()['details'] and exp_ids() == []


def test_post_cos_buit_400(client, world):
    resp = api_post(client, EXPERIENCES, user_claims('u1'), {})
    assert resp.status_code == 400 and set(resp.json()['details']) == {'refuge_id', 'comment', 'condition'}


@pytest.mark.parametrize('rid', ['no-es-uuid', 'refugi_colomers', ZERO_UUID, 'a' * 100])
def test_post_refugi_inexistent_o_id_no_uuid_404(client, world, rid):
    resp = api_post(client, EXPERIENCES, user_claims('u1'), {**new_body(world[0]), 'refuge_id': rid})
    assert resp.status_code == 404 and resp.json() == {'error': 'Refuge not found'}
    assert exp_ids() == []


def test_post_el_400_va_abans_del_404(client, world):
    resp = api_post(client, EXPERIENCES, user_claims('u1'), {'refuge_id': ZERO_UUID, 'comment': '', 'condition': 2})
    assert resp.status_code == 400


def test_post_multipart_no_suportat_415(client, world):
    with patch(VERIFY, return_value=user_claims('u1')):
        resp = client.post(EXPERIENCES, data={'refuge_id': str(world[0].pk), 'comment': 'x', 'condition': 1},
                           HTTP_AUTHORIZATION='Bearer tok')
    assert resp.status_code == 415 and exp_ids() == []


def test_post_json_malformat_400(client, world):
    with patch(VERIFY, return_value=user_claims('u1')):
        resp = client.post(EXPERIENCES, data='{no json', content_type='application/json',
                           HTTP_AUTHORIZATION='Bearer tok')
    assert resp.status_code == 400 and exp_ids() == []


def test_el_post_pot_repetir_experiencia_al_mateix_refugi(client, world):
    for _ in range(2):
        assert api_post(client, EXPERIENCES, user_claims('u1'), new_body(world[0])).status_code == 201
    assert len(exp_ids(world[0], 'u1')) == 2


# =================================== PATCH ===================================

def test_patch_del_comentari_200_i_actualitza_modified_at(client, world):
    e = make_experience(world[0], 'u1', comment='antic', condition=2)
    before = exp_row(e)
    resp = api_patch(client, exp_url(e), user_claims('u1'), {'comment': 'Actualització: ja no hi ha llenya.'})
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert set(body) == {'experience'} and set(body['experience']) == EXP_KEYS
    got = body['experience']
    assert got['id'] == e and got['comment'] == 'Actualització: ja no hi ha llenya.' and got['condition'] == 2
    row = exp_row(e)
    assert row['comment'] == got['comment'] and row['modified_at'] > before['modified_at']
    assert row['created_at'] == before['created_at'] and row['creator_uid'] == 'u1'


def test_patch_de_la_condicio_ajusta_la_mitjana(client, world):
    r = world[0]
    e = make_experience(r, 'u1', condition=1)
    make_experience(r, 'u2', condition=3)
    assert refuge_state(r)[:2] == (pytest.approx(2.0), 2)
    resp = api_patch(client, exp_url(e), user_claims('u1'), {'condition': 3})
    assert resp.status_code == 200 and resp.json()['experience']['condition'] == 3
    c, n, _ = refuge_state(r)
    assert n == 2 and c == pytest.approx(3.0)


def test_patch_buit_200_nomes_toca_modified_at(client, world):
    e = make_experience(world[0], 'u1', comment='igual', condition=2)
    before = exp_row(e)
    resp = api_patch(client, exp_url(e), user_claims('u1'), {})
    assert resp.status_code == 200
    row = exp_row(e)
    assert (row['comment'], row['condition']) == ('igual', 2) and row['modified_at'] > before['modified_at']
    assert refuge_state(world[0])[:2] == (pytest.approx(2.0), 1)


def test_patch_retorna_els_mitjans_visibles_per_a_qui_demana(client, world):
    r = world[0]
    e = make_experience(r, 'u1')
    make_exp_media(r, 'u1', e, key='k/v.webp', minutes=1)
    make_exp_media(r, 'u1', e, key='k/h.webp', status='hidden_pending_review', minutes=2)
    items = api_patch(client, exp_url(e), user_claims('u1'), {'comment': 'x'}).json()['experience']['images_metadata']
    assert [i['key'] for i in items] == ['k/v.webp', 'k/h.webp']                # l'autor veu els seus amagats
    items = api_patch(client, exp_url(e), admin_claims('adm'), {'comment': 'moderat'}).json()['experience'][
        'images_metadata']
    assert [i['key'] for i in items] == ['k/v.webp', 'k/h.webp']


def test_patch_no_pot_canviar_refugi_ni_creador(client, world):
    e = make_experience(world[0], 'u1')
    api_patch(client, exp_url(e), user_claims('u1'), {'comment': 'x', 'refuge_id': str(world[1].pk),
                                                       'creator_uid': 'u2'})
    row = exp_row(e)
    assert row['refuge_id'] == str(world[0].pk) and row['creator_uid'] == 'u1'


@pytest.mark.parametrize('body', [{'comment': ''}, {'comment': '  '}, {'comment': 'x' * 2001}, {'condition': 4},
                                  {'condition': -1}, {'condition': 'a'}, {'condition': None}])
def test_patch_dades_invalides_400(client, world, body):
    e = make_experience(world[0], 'u1', comment='igual', condition=2)
    resp = api_patch(client, exp_url(e), user_claims('u1'), body)
    assert resp.status_code == 400 and resp.json()['error'] == 'Dades invàlides'
    assert set(resp.json()['details']) == set(body)
    assert exp_row(e)['comment'] == 'igual' and exp_row(e)['condition'] == 2


def test_patch_el_400_va_abans_del_404_i_del_403(client, world):
    e = make_experience(world[0], 'u1')
    assert api_patch(client, exp_url(ZERO_UUID), user_claims('u2'), {'comment': ''}).status_code == 400
    assert api_patch(client, exp_url(e), user_claims('u2'), {'comment': ''}).status_code == 400


@pytest.mark.parametrize('xid', [ZERO_UUID, 'no-es-uuid', 'exp_firestore_1', 'a%00b'])
def test_patch_experiencia_inexistent_o_id_no_uuid_404(client, world, xid):
    resp = api_patch(client, exp_url(xid), user_claims('u1'), {'comment': 'x'})
    assert resp.status_code == 404 and resp.json() == {'error': 'Experience not found'}


def test_patch_d_un_altre_403_not_owner_i_no_canvia_res(client, world):
    e = make_experience(world[0], 'u1', comment='meu', condition=1)
    state = refuge_state(world[0])
    resp = api_patch(client, exp_url(e), user_claims('u2'), {'comment': 'hackejat', 'condition': 3})
    assert resp.status_code == 403 and resp.json() == NOT_OWNER_BODY
    assert exp_row(e)['comment'] == 'meu' and exp_row(e)['condition'] == 1 and refuge_state(world[0]) == state


def test_patch_l_admin_pot_editar_l_experiencia_d_un_altre(client, world):
    e = make_experience(world[0], 'u1', comment='meu')
    resp = api_patch(client, exp_url(e), admin_claims('adm'), {'comment': 'moderat'})
    assert resp.status_code == 200 and resp.json()['experience']['creator_uid'] == 'u1'
    assert exp_row(e)['comment'] == 'moderat' and exp_row(e)['creator_uid'] == 'u1'


def test_patch_multipart_415(client, world):
    e = make_experience(world[0], 'u1')
    with patch(VERIFY, return_value=user_claims('u1')):
        from django.test.client import BOUNDARY, MULTIPART_CONTENT, encode_multipart
        resp = client.patch(exp_url(e), data=encode_multipart(BOUNDARY, {'comment': 'x'}),
                            content_type=MULTIPART_CONTENT, HTTP_AUTHORIZATION='Bearer tok')
    assert resp.status_code == 415 and exp_row(e)['comment'] == 'Refugi net'


# =================================== DELETE ===================================

def test_delete_200_amb_el_cos_d_avui(client, world):
    e = make_experience(world[0], 'u1')
    resp = api_delete(client, exp_url(e), user_claims('u1'))
    assert resp.status_code == 200
    assert resp.json() == {'success': True, 'message': 'Experiència eliminada correctament'}
    assert exp_ids() == []


def test_delete_esborra_els_mitjans_de_l_experiencia_i_nomes_aquests(client, world, r2):
    r = world[0]
    e, other = make_experience(r, 'u1'), make_experience(r, 'u2')
    make_exp_media(r, 'u1', e, key='k/e1.webp', thumb_key='k/e1_thumb.webp', minutes=1)
    make_exp_media(r, 'u1', e, key='k/e2.webp', minutes=2)
    make_exp_media(r, 'u2', other, key='k/o.webp', minutes=3)
    make_media(r, 'u1', key='k/foto-refugi.webp', minutes=4)
    assert api_delete(client, exp_url(e), user_claims('u1')).status_code == 200
    assert media_keys_of(e) == [] and media_keys_of(other) == ['k/o.webp']
    assert sorted(deleted_keys(r2)) == ['k/e1.webp', 'k/e1_thumb.webp', 'k/e2.webp']        # claus + miniatures


def test_delete_no_toca_la_mitjana_del_refugi(client, world):
    r = world[0]
    e = make_experience(r, 'u1', condition=3)
    make_experience(r, 'u2', condition=1)
    state = refuge_state(r)
    api_delete(client, exp_url(e), user_claims('u1'))
    assert refuge_state(r) == state and state[1] == 2


@pytest.mark.parametrize('xid', [ZERO_UUID, 'no-es-uuid', 'a%00b'])
def test_delete_experiencia_inexistent_o_id_no_uuid_404(client, world, xid):
    resp = api_delete(client, exp_url(xid), user_claims('u1'))
    assert resp.status_code == 404 and resp.json() == {'error': 'Experience not found'}


def test_delete_d_un_altre_403_not_owner(client, world, r2):
    e = make_experience(world[0], 'u1')
    make_exp_media(world[0], 'u1', e, key='k/e.webp')
    resp = api_delete(client, exp_url(e), user_claims('u2'))
    assert resp.status_code == 403 and resp.json() == NOT_OWNER_BODY
    assert exp_ids() == [e] and media_keys_of(e) == ['k/e.webp'] and deleted_keys(r2) == []


def test_delete_l_admin_pot_esborrar_l_experiencia_d_un_altre(client, world):
    e = make_experience(world[0], 'u1')
    assert api_delete(client, exp_url(e), admin_claims('adm')).status_code == 200
    assert exp_ids() == []


def test_delete_dues_vegades_la_segona_es_404(client, world):
    e = make_experience(world[0], 'u1')
    assert api_delete(client, exp_url(e), user_claims('u1')).status_code == 200
    assert api_delete(client, exp_url(e), user_claims('u1')).status_code == 404


# =================================== mètodes no permesos ===================================

def test_metodes_no_definits_donen_405(client, world):
    e = make_experience(world[0], 'u1')
    with patch(VERIFY, return_value=user_claims('u1')):
        h = {'HTTP_AUTHORIZATION': 'Bearer tok'}
        assert client.put(EXPERIENCES, **h).status_code == 405
        assert client.delete(EXPERIENCES, **h).status_code == 405
        assert client.get(exp_url(e), **h).status_code == 405
        assert client.post(exp_url(e), data='{}', content_type='application/json', **h).status_code == 405
        assert client.put(exp_url(e), data='{}', content_type='application/json', **h).status_code == 405
