"""
Contracte HTTP del domini refugi contra Postgres real (rol `app`, RLS activa): `GET /api/refuges/`,
`GET /api/refuges/{id}/`, `GET /api/refuges/{id}/media/` i `DELETE /api/refuges/{id}/media/{key}/`.

La forma JSON és la d'avui (IDs string, `coord: {lat, long}`, `info_comp` com a enters 0/1…): el frontend no canvia.
Les vistes viuen a `apps/refuges/views.py`; no hi ha cap accés a Firestore (el conftest el bloqueja).
"""
import uuid

import pytest

from apps.refuges.tests.helpers import (
    AMENITY_FIELDS, BASE_KEYS, MEDIA_ITEM_KEYS, admin_claims, api_delete, api_get, make_media, make_refuge,
    make_user, user_claims)
from apps.core.rls import rls_context

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration]

URL = '/api/refuges/'


def detail(r):
    return f'{URL}{r.pk}/'


@pytest.fixture
def refuge(RM):
    return make_refuge(
        name='Refugi de Colomers', lat=42.6321, long=0.9984, surname='Colomers', altitude=2135, places=12,
        type='fermée', description='Un refugi', region='Pirineus', departement='Lleida',
        modified_at='2024-05-17', condition=1.5, num_contributed_conditions=3,
        amenities={'eau': True, 'poele': True, 'lits': True},
        links=['https://www.refuges.info/a', 'https://example.org/b'])


# ============ Detall ============

def test_detall_anonim_forma_exacta(client, refuge):
    r = api_get(client, detail(refuge))
    assert r.status_code == 200
    data = r.json()
    assert set(data) == BASE_KEYS, 'anònim: sense visitors ni images_metadata ni surname'
    assert data['id'] == str(refuge.pk) and uuid.UUID(data['id']).version == 7
    assert data['name'] == 'Refugi de Colomers'
    assert data['coord'] == pytest.approx({'lat': 42.6321, 'long': 0.9984})
    assert (data['altitude'], data['places'], data['type']) == (2135, 12, 'fermée')
    assert data['description'] == 'Un refugi' and 'remarque' not in data           # S-6: ja no s'emet
    assert (data['region'], data['departement']) == ('Pirineus', 'Lleida')
    assert data['modified_at'] == '2024-05-17'
    assert data['links'] == ['https://www.refuges.info/a', 'https://example.org/b']


def test_detall_info_comp_son_enters_0_1(client, refuge):
    ic = api_get(client, detail(refuge)).json()['info_comp']
    assert set(ic) == set(AMENITY_FIELDS)
    assert all(type(v) is int for v in ic.values())
    assert (ic['eau'], ic['poele'], ic['lits'], ic['couvertures']) == (1, 1, 1, 0)


def test_detall_condition_arrodonida_half_to_even(client, RM):
    for cond, shown in ((1.5, 2), (2.5, 2), (0.5, 0), (2.6, 3), (None, None)):
        r = make_refuge(name=f'c{cond}', lat=42 + (cond or 0) / 100, condition=cond,
                        num_contributed_conditions=0 if cond is None else 1)
        assert api_get(client, detail(r)).json()['condition'] == shown


def test_detall_camps_nuls(client, RM):
    r = make_refuge(name='Buit')
    d = api_get(client, detail(r)).json()
    assert (d['altitude'], d['places'], d['region'], d['departement'], d['modified_at'], d['condition']) == \
        (None, None, None, None, None, None)
    assert (d['description'], d['links']) == ('', [])
    assert all(v == 0 for v in d['info_comp'].values())


def test_detall_refugi_sense_fila_d_amenities_torna_tot_a_zero(client, RM):
    """Invariant «tot refugi té amenities» no forçat per la BD: la lectura fa LEFT JOIN (§2.6)."""
    from django.contrib.gis.geos import Point
    from apps.refuges.tests.helpers import as_owner
    with as_owner():
        r = RM.Refuge.objects.create(name='Sense amenities', coord=Point(1, 42, srid=4326))
    d = api_get(client, detail(r)).json()
    assert d['info_comp'] == {f: 0 for f in AMENITY_FIELDS}


def test_detall_autenticat_afegeix_images_metadata(client, refuge):
    make_user('u1')
    make_media(refuge, 'u1', key=f'refugis-lliures/{refuge.pk}/a.webp', minutes=1, width=800, height=600,
               blurhash='LEHV6n', thumb_key=f'refugis-lliures/{refuge.pk}/a_thumb.webp')
    d = api_get(client, detail(refuge), user_claims('u2')).json()
    assert set(d) == BASE_KEYS | {'images_metadata'}
    (item,) = d['images_metadata']
    assert set(item) == MEDIA_ITEM_KEYS
    assert item['key'].endswith('a.webp') and item['url'].startswith('https://r2.test/')
    assert item['thumb_url'].endswith('a_thumb.webp?sig=1')
    assert (item['media_type'], item['width'], item['height'], item['blurhash']) == ('image', 800, 600, 'LEHV6n')
    assert item['creator_uid'] == 'u1' and item['experience_id'] is None and item['taken_at'] is None
    assert item['uploaded_at'] is not None


def test_detall_anonim_no_veu_els_mitjans(client, refuge):
    make_user('u1')
    make_media(refuge, 'u1')
    assert 'images_metadata' not in api_get(client, detail(refuge)).json()


def test_detall_visitors_nomes_admin(client, refuge):
    """Decisió 5: `visitors` només per a admins. Fins al chunk 3 (`user_visited_refuges`) és sempre buit."""
    admin = api_get(client, detail(refuge), admin_claims()).json()
    assert admin['visitors'] == []
    normal = api_get(client, detail(refuge), user_claims('u1')).json()
    assert normal.get('visitors', []) == []


def test_detall_mitjans_ocults_nomes_per_autor_i_admin(client, refuge):
    make_user('u1')
    make_user('u2')
    make_media(refuge, 'u1', key='k/vis.webp', minutes=1)
    make_media(refuge, 'u1', key='k/hid.webp', status='hidden_pending_review', minutes=2)
    make_media(refuge, 'u1', key='k/rem.webp', status='removed', minutes=3)

    def keys(claims):
        return [m['key'] for m in api_get(client, detail(refuge), claims).json()['images_metadata']]
    assert keys(user_claims('u2')) == ['k/vis.webp']
    assert keys(user_claims('u1')) == ['k/vis.webp', 'k/hid.webp', 'k/rem.webp']
    assert keys(admin_claims()) == ['k/vis.webp', 'k/hid.webp', 'k/rem.webp']


def test_detall_inexistent_404(client, RM):
    r = api_get(client, f'{URL}{uuid.uuid4()}/')
    assert r.status_code == 404 and 'error' in r.json()


@pytest.mark.parametrize('bad', ['no-es-un-uuid', '123', 'abc%20def', '0190a1b2'])
def test_detall_amb_id_mal_format_es_404_no_500(client, RM, bad):
    r = api_get(client, f'{URL}{bad}/')
    assert r.status_code == 404


def test_detall_id_antic_de_firestore_es_404(client, RM):
    assert api_get(client, f'{URL}aB3dE5fG7hI9jK1lM2nO/').status_code == 404


def test_detall_no_filtra_dades_internes(client, refuge):
    body = api_get(client, detail(refuge)).content.decode()
    for needle in ('surname', 'num_contributed_conditions', 'condition_reset_at', 'created_at'):
        assert needle not in body
    assert body.count('Colomers') == 1, "l'àlies (surname) no s'emet: només el nom"


# ============ Llista sense filtres: refuge_map ============

def test_llista_sense_filtres_forma_i_ordre(client, RM):
    make_refuge(name='Zeta', lat=42.1, long=1.1, surname='Alias')
    make_refuge(name='Alfa', lat=42.2, long=1.2)
    r = api_get(client, URL)
    assert r.status_code == 200
    data = r.json()
    assert set(data) == {'count', 'results'} and data['count'] == 2
    assert [x['name'] for x in data['results']] == ['Alfa', 'Zeta']
    for x in data['results']:
        assert set(x) == {'id', 'name', 'coord', 'geohash'}, 'ja no porta surname'
        assert set(x['coord']) == {'lat', 'long'}
        assert isinstance(x['id'], str) and len(x['geohash']) == 5
    assert data['results'][0]['coord'] == pytest.approx({'lat': 42.2, 'long': 1.2})


def test_llista_buida(client, RM):
    assert api_get(client, URL).json() == {'count': 0, 'results': []}


def test_filtres_buits_equivalen_a_sense_filtres(client, RM):
    make_refuge()
    d = api_get(client, URL + '?name=&type=&condition=').json()
    assert set(d) == {'count', 'results'} and d['count'] == 1
    assert set(d['results'][0]) == {'id', 'name', 'coord', 'geohash'}, 'filtres buits = llista de coordenades'


def test_llista_identica_per_a_autenticats(client, RM):
    make_refuge()
    assert api_get(client, URL, user_claims('u1')).json() == api_get(client, URL).json()


def test_llista_ignora_la_rls_d_altres_taules_i_veu_tots_els_punts(client, RM):
    for i in range(5):
        make_refuge(name=f'r{i}', lat=42 + i / 10)
    assert api_get(client, URL).json()['count'] == 5


# ============ Llista amb filtres: refugis complets ============

def test_llista_amb_filtres_retorna_refugis_complets(client, refuge):
    d = api_get(client, URL + '?type=fermée').json()
    assert set(d) == {'count', 'results'} and d['count'] == 1
    assert set(d['results'][0]) == BASE_KEYS
    assert d['results'][0]['id'] == str(refuge.pk)


def test_llista_amb_filtres_autenticat_afegeix_images_metadata(client, refuge):
    make_user('u1')
    make_media(refuge, 'u1')
    anon = api_get(client, URL + '?type=fermée').json()['results'][0]
    auth = api_get(client, URL + '?type=fermée', user_claims('u2')).json()['results'][0]
    assert 'images_metadata' not in anon
    assert len(auth['images_metadata']) == 1 and set(auth['images_metadata'][0]) == MEDIA_ITEM_KEYS


@pytest.mark.parametrize('qs', [
    'condition=4', 'condition=-1', 'condition=x', 'type=garde', 'places_min=5&places_max=2',
    'altitude_min=3000&altitude_max=100', 'altitude_max=9000', 'places_min=-3'])
def test_parametres_invalids_400(client, RM, qs):
    r = api_get(client, f'{URL}?{qs}')
    assert r.status_code == 400
    body = r.json()
    assert body['error'] == 'Invalid query parameters' and 'details' in body


# ============ Mitjans: GET /refuges/{id}/media/ ============

def test_media_list_requereix_autenticacio(client, refuge):
    assert api_get(client, f'{detail(refuge)}media/').status_code == 401


def test_media_list_forma_i_ordre(client, refuge):
    make_user('u1')
    make_media(refuge, 'u1', key='k/b.webp', minutes=5)
    make_media(refuge, 'u1', key='k/a.webp', minutes=10)
    make_media(refuge, 'u1', key='k/c.mp4', minutes=1, media_type='video', content_type='video/mp4')
    r = api_get(client, f'{detail(refuge)}media/', user_claims('u2'))
    assert r.status_code == 200
    media = r.json()['media']
    assert [m['key'] for m in media] == ['k/c.mp4', 'k/b.webp', 'k/a.webp']      # (uploaded_at, key)
    assert all(set(m) == MEDIA_ITEM_KEYS for m in media)
    assert media[0]['media_type'] == 'video'


def test_media_list_refugi_inexistent_404(client, RM):
    assert api_get(client, f'{URL}{uuid.uuid4()}/media/', user_claims('u1')).status_code == 404


def test_media_list_ocults_nomes_autor_i_admin(client, refuge):
    make_user('u1')
    make_media(refuge, 'u1', key='k/h.webp', status='hidden_pending_review')
    n = lambda claims: len(api_get(client, f'{detail(refuge)}media/', claims).json()['media'])
    assert (n(user_claims('u2')), n(user_claims('u1')), n(admin_claims())) == (0, 1, 1)


def test_media_list_no_barreja_refugis(client, refuge, RM):
    make_user('u1')
    other = make_refuge(name='altre', lat=43)
    make_media(refuge, 'u1', key='k/mine.webp')
    make_media(other, 'u1', key='k/other.webp')
    keys = [m['key'] for m in api_get(client, f'{detail(refuge)}media/', user_claims('u1')).json()['media']]
    assert keys == ['k/mine.webp']


# ============ Mitjans: DELETE /refuges/{id}/media/{key}/ ============

def mkey(refuge, name='a.webp'):
    return f'refugis-lliures/{refuge.pk}/{name}'


def del_url(refuge, key):
    return f'{detail(refuge)}media/{key}/'


@pytest.mark.parametrize('claims,status', [(user_claims('u1'), 200), (admin_claims(), 200)])
def test_delete_media_autor_o_admin(client, refuge, RM, claims, status):
    make_user('u1')
    key = mkey(refuge)
    make_media(refuge, 'u1', key=key)
    r = api_delete(client, del_url(refuge, key), claims)
    assert r.status_code == status
    assert r.json() == {'success': True, 'message': 'Mitjà eliminat correctament', 'key': key}
    with rls_context(system=True):
        assert not RM.RefugeMedia.objects.filter(pk=key).exists()


def test_delete_media_no_autor_403_i_no_esborra(client, refuge, RM):
    make_user('u1')
    key = mkey(refuge)
    make_media(refuge, 'u1', key=key)
    assert api_delete(client, del_url(refuge, key), user_claims('u2')).status_code == 403
    with rls_context(system=True):
        assert RM.RefugeMedia.objects.filter(pk=key).exists()


def test_delete_media_anonim_401(client, refuge):
    make_user('u1')
    key = mkey(refuge)
    make_media(refuge, 'u1', key=key)
    assert api_delete(client, del_url(refuge, key)).status_code == 401


def test_delete_media_inexistent(client, refuge):
    """Comportament actual (`IsMediaUploader`): un no-admin rep 403 si el mitjà no existeix; un admin, 404."""
    key = mkey(refuge, 'fantasma.webp')
    assert api_delete(client, del_url(refuge, key), user_claims('u1')).status_code == 403
    r = api_delete(client, del_url(refuge, key), admin_claims())
    assert r.status_code == 404 and 'error' in r.json()


def test_delete_media_d_un_altre_refugi_no_funciona(client, refuge, RM):
    """La clau és del refugi A; amb l'id del refugi B no s'esborra."""
    make_user('u1')
    other = make_refuge(name='B', lat=43)
    key = mkey(refuge)
    make_media(refuge, 'u1', key=key)
    r = api_delete(client, del_url(other, key), admin_claims())
    assert r.status_code == 404
    with rls_context(system=True):
        assert RM.RefugeMedia.objects.filter(pk=key).exists()


def test_delete_media_amb_clau_amb_barres_i_punts(client, refuge, RM):
    make_user('u1')
    key = f'refugis-lliures/{refuge.pk}/0190a1b2-c3d4-7e5f-8a9b-0c1d2e3f4a5b.v1.webp'
    make_media(refuge, 'u1', key=key)
    assert api_delete(client, del_url(refuge, key), user_claims('u1')).status_code == 200


def test_delete_media_r2_que_falla_no_deixa_la_fila_esborrada(client, refuge, RM):
    """`R2MediaService.delete_file` retorna False (no llança): si l'objecte no s'esborra, la BD no es perd."""
    from unittest.mock import patch
    from apps.uploads.media.r2_media_service import R2MediaService
    make_user('u1')
    key = mkey(refuge)
    make_media(refuge, 'u1', key=key)
    with patch.object(R2MediaService, 'delete_file', lambda self, k: False):
        r = api_delete(client, del_url(refuge, key), user_claims('u1'))
    assert r.status_code == 500
    assert r.json()['error'] == 'Error en esborrar el fitxer a R2' and 'error_id' in r.json()
    with rls_context(system=True):
        assert RM.RefugeMedia.objects.filter(pk=key).exists()


# ============ Cap accés a Firestore ni a la cache ============

def test_el_domini_refugi_no_depen_de_firestore_ni_de_cache(client, refuge):
    """Cap client de Firestore ni lectura/escriptura a la cache de Django: la lectura funciona igualment."""
    from unittest.mock import patch
    with patch('google.cloud.firestore.Client', side_effect=AssertionError('Firestore!')),             patch('django.core.cache.cache.get', side_effect=AssertionError('cache de dades')),             patch('django.core.cache.cache.set', side_effect=AssertionError('cache de dades')):
        assert api_get(client, detail(refuge)).status_code == 200
        assert api_get(client, URL).status_code == 200
        assert api_get(client, URL + '?type=fermée').status_code == 200
