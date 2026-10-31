"""
Contracte HTTP de `GET/POST /users/{uid}/favorite-refuges/` i `visited-refuges/` (+ `DELETE .../{refuge_id}/`), chunk 3.

Forma d'una llista (§5.2): `{count, results: [{id, name, region, places, coord: {lat, long}, images_metadata}]}` amb
`images_metadata` = `[primera foto visible]` o `null`, `places` `null` si no hi ha dada. Ordre: `created_at` (afegit).
Idempotencia: `INSERT ... ON CONFLICT DO NOTHING`. Nomes el propi usuari (IsSameUser, sense bypass d'admin).
"""
import uuid

import pytest

from apps.accounts.tests.helpers import (
    FAV, LIST_ITEM_KEYS, MEDIA_ITEM_KEYS, VIS, add_list_row, admin_claims, api_delete, api_get, api_post, list_rows,
    list_refuge_ids, ensure_profile, make_media, make_refuge, make_user, url, user_claims)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration,
              pytest.mark.real_permissions]

KINDS = [FAV, VIS]


@pytest.fixture
def two():
    make_user('u1')
    make_user('u2')


# =================================== GET ===================================

@pytest.mark.parametrize('kind', KINDS)
def test_llista_buida(client, two, kind):
    r = api_get(client, url('u1', kind), user_claims('u1'))
    assert r.status_code == 200 and r.json() == {'count': 0, 'results': []}


@pytest.mark.parametrize('kind', KINDS)
def test_forma_de_cada_element(client, two, kind):
    r = make_refuge(name='Colomers', lat=42.6, long=1.0, region='Pirineus', places=12)
    add_list_row(kind, 'u1', r)
    resp = api_get(client, url('u1', kind), user_claims('u1'))
    assert resp.status_code == 200
    body = resp.json()
    assert body['count'] == 1 and len(body['results']) == 1
    item = body['results'][0]
    assert set(item) == LIST_ITEM_KEYS
    assert item['id'] == str(r.pk) and item['name'] == 'Colomers'
    assert (item['region'], item['places']) == ('Pirineus', 12)
    assert item['coord'] == pytest.approx({'lat': 42.6, 'long': 1.0})
    assert item['images_metadata'] is None


@pytest.mark.parametrize('kind', KINDS)
def test_places_i_region_nuls_es_retornen_null(client, two, kind):
    """§12 #5: `places` pot ser `null` (abans el mapper posava `0`)."""
    r = make_refuge(name='Sense dades')
    add_list_row(kind, 'u1', r)
    item = api_get(client, url('u1', kind), user_claims('u1')).json()['results'][0]
    assert item['places'] is None and item['region'] is None


@pytest.mark.parametrize('kind', KINDS)
def test_ordre_mes_recent_primer_i_desempat_per_refuge_id(client, two, kind):
    a, b, c, d = (make_refuge(name=n, lat=42 + i / 10) for i, n in enumerate('ABCD'))
    add_list_row(kind, 'u1', c, 1)
    add_list_row(kind, 'u1', a, 3)
    add_list_row(kind, 'u1', b, 2)
    add_list_row(kind, 'u1', d, 2)                      # mateix created_at que `b`: desempat per refuge_id
    ids = [i['id'] for i in api_get(client, url('u1', kind), user_claims('u1')).json()['results']]
    tied = sorted([str(b.pk), str(d.pk)], reverse=True)
    assert ids == [str(a.pk), *tied, str(c.pk)]


@pytest.mark.parametrize('kind', KINDS)
def test_primera_imatge_visible_en_forma_media_item(client, two, kind):
    r = make_refuge()
    add_list_row(kind, 'u1', r)
    make_media(r, 'u2', key='k/hidden.webp', status='hidden_pending_review', minutes=0)
    make_media(r, 'u2', key='k/removed.webp', status='removed', minutes=1)
    make_media(r, 'u2', key='k/second.webp', minutes=2)
    make_media(r, 'u2', key='k/first.webp', minutes=3, thumb_key='k/first_t.webp')
    imgs = api_get(client, url('u1', kind), user_claims('u1')).json()['results'][0]['images_metadata']
    assert isinstance(imgs, list) and len(imgs) == 1                  # nomes la primera
    assert set(imgs[0]) == MEDIA_ITEM_KEYS
    assert imgs[0]['key'] == 'k/first.webp' and imgs[0]['creator_uid'] == 'u2'
    assert imgs[0]['url'] == 'https://r2.test/k/first.webp?sig=1'
    assert imgs[0]['thumb_url'] == 'https://r2.test/k/first_t.webp?sig=1'


@pytest.mark.parametrize('kind', KINDS)
def test_nomes_imatges_ocultes_dona_null(client, two, kind):
    r = make_refuge()
    add_list_row(kind, 'u1', r)
    make_media(r, 'u1', key='k/mine.webp', status='hidden_pending_review')       # ni el propi autor la veu aqui
    assert api_get(client, url('u1', kind), user_claims('u1')).json()['results'][0]['images_metadata'] is None


@pytest.mark.parametrize('kind', KINDS)
def test_nomes_les_files_del_propi_usuari(client, two, kind):
    r1, r2 = make_refuge(name='A'), make_refuge(name='B', lat=43)
    add_list_row(kind, 'u1', r1)
    add_list_row(kind, 'u2', r2)
    names = [i['name'] for i in api_get(client, url('u1', kind), user_claims('u1')).json()['results']]
    assert names == ['A']


@pytest.mark.parametrize('kind', KINDS)
def test_visitats_i_preferits_son_llistes_independents(client, two, kind):
    r = make_refuge()
    add_list_row(kind, 'u1', r)
    other = VIS if kind == FAV else FAV
    assert api_get(client, url('u1', other), user_claims('u1')).json()['count'] == 0


@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('claims', [user_claims('u2'), admin_claims('adm')])
def test_get_d_un_altre_403_tambe_per_a_admin(client, two, kind, claims):
    ensure_profile(claims['uid'])
    add_list_row(kind, 'u1', make_refuge())
    r = api_get(client, url('u1', kind), claims)
    assert r.status_code == 403
    assert 'results' not in r.json()


@pytest.mark.parametrize('kind', KINDS)
def test_get_anonim_401(client, two, kind):
    assert api_get(client, url('u1', kind)).status_code == 401


# =================================== POST ===================================

@pytest.mark.parametrize('kind', KINDS)
def test_post_afegeix_i_retorna_la_info_del_refugi(client, two, kind):
    r = make_refuge(name='Colomers', region='Pirineus', places=8)
    make_media(r, 'u2', key='k/p.webp')
    resp = api_post(client, url('u1', kind), user_claims('u1'), {'refuge_id': str(r.pk)})
    assert resp.status_code == 200, resp.content
    item = resp.json()
    assert set(item) == LIST_ITEM_KEYS
    assert item['id'] == str(r.pk) and item['name'] == 'Colomers' and item['places'] == 8
    assert item['images_metadata'][0]['key'] == 'k/p.webp'
    assert list_refuge_ids(kind, 'u1') == [r.pk]


@pytest.mark.parametrize('kind', KINDS)
def test_post_idempotent_no_duplica_ni_mou_la_posicio(client, two, kind):
    a, b = make_refuge(name='A'), make_refuge(name='B', lat=43)
    for rid in (a.pk, b.pk, a.pk):
        assert api_post(client, url('u1', kind), user_claims('u1'), {'refuge_id': str(rid)}).status_code == 200
    rows = list_rows(kind, 'u1')
    assert len(rows) == 2
    ids = [i['id'] for i in api_get(client, url('u1', kind), user_claims('u1')).json()['results']]
    assert ids == [str(b.pk), str(a.pk)]                                  # `a` conserva la data original


@pytest.mark.parametrize('kind', KINDS)
def test_post_no_afegeix_a_l_altra_llista(client, two, kind):
    r = make_refuge()
    api_post(client, url('u1', kind), user_claims('u1'), {'refuge_id': str(r.pk)})
    assert list_rows(VIS if kind == FAV else FAV, 'u1') == []


@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('bad', [str(uuid.uuid4()), 'abc', '1', '../x'])
def test_post_refugi_inexistent_o_mal_format_404(client, two, kind, bad):
    resp = api_post(client, url('u1', kind), user_claims('u1'), {'refuge_id': bad})
    assert resp.status_code == 404 and 'no trobat' in resp.json()['error']
    assert list_rows(kind, 'u1') == []


@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('body', [{}, {'refuge_id': ''}, {'refuge_id': None}, {'refuge_id': 'x' * 256}, {'altre': 1}])
def test_post_dades_invalides_400(client, two, kind, body):
    resp = api_post(client, url('u1', kind), user_claims('u1'), body)
    assert resp.status_code == 400
    assert resp.json()['error'] == 'Dades invàlides' and 'refuge_id' in resp.json()['details']


@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('claims', [user_claims('u2'), admin_claims('adm')])
def test_post_en_nom_d_un_altre_403(client, two, kind, claims):
    ensure_profile(claims['uid'])
    r = make_refuge()
    assert api_post(client, url('u1', kind), claims, {'refuge_id': str(r.pk)}).status_code == 403
    assert list_rows(kind) == []


@pytest.mark.parametrize('kind', KINDS)
def test_post_anonim_401(client, two, kind):
    r = make_refuge()
    assert api_post(client, url('u1', kind), None, {'refuge_id': str(r.pk)}).status_code == 401


# =================================== DELETE ===================================

@pytest.mark.parametrize('kind', KINDS)
def test_delete_204_i_nomes_treu_la_fila_propia(client, two, kind):
    r = make_refuge()
    add_list_row(kind, 'u1', r)
    add_list_row(kind, 'u2', r)
    resp = api_delete(client, url('u1', kind, r.pk), user_claims('u1'))
    assert resp.status_code == 204 and resp.content == b''
    assert list_refuge_ids(kind, 'u1') == [] and list_refuge_ids(kind, 'u2') == [r.pk]


@pytest.mark.parametrize('kind', KINDS)
def test_delete_d_un_refugi_que_no_hi_es_es_idempotent_204(client, two, kind):
    r = make_refuge()
    assert api_delete(client, url('u1', kind, r.pk), user_claims('u1')).status_code == 204


@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('bad', [str(uuid.uuid4()), 'abc'])
def test_delete_refugi_inexistent_o_mal_format_404(client, two, kind, bad):
    resp = api_delete(client, url('u1', kind, bad), user_claims('u1'))
    assert resp.status_code == 404 and 'no trobat' in resp.json()['error']


@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('claims', [user_claims('u2'), admin_claims('adm')])
def test_delete_d_un_altre_403(client, two, kind, claims):
    ensure_profile(claims['uid'])
    r = make_refuge()
    add_list_row(kind, 'u1', r)
    assert api_delete(client, url('u1', kind, r.pk), claims).status_code == 403
    assert list_refuge_ids(kind, 'u1') == [r.pk]


@pytest.mark.parametrize('kind', KINDS)
def test_delete_anonim_401(client, two, kind):
    r = make_refuge()
    assert api_delete(client, url('u1', kind, r.pk)).status_code == 401


@pytest.mark.parametrize('kind', KINDS)
def test_esborrar_i_tornar_a_afegir_posa_la_data_nova_al_principi(client, two, kind):
    a, b = make_refuge(name='A'), make_refuge(name='B', lat=43)
    add_list_row(kind, 'u1', a, 0)
    add_list_row(kind, 'u1', b, 1)
    api_delete(client, url('u1', kind, a.pk), user_claims('u1'))
    api_post(client, url('u1', kind), user_claims('u1'), {'refuge_id': str(a.pk)})
    ids = [i['id'] for i in api_get(client, url('u1', kind), user_claims('u1')).json()['results']]
    assert ids == [str(a.pk), str(b.pk)]
