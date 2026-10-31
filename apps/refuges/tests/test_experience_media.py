"""
Mitjans d'experiència dins `apps.refuges` (chunk 7; `refuges.0002`, §2.8, §5.2): una imatge d'experiència és una fila de
`refuges.refuge_media` amb `experience_id` (substitueix `experiences.media_keys`), de manera que les lectures del
refugi la mostren com qualsevol altre mitjà:

- `GET /refuges/{id}/` (autenticat) i `GET /refuges/{id}/media/`: `images_metadata`/`media` inclouen els mitjans
  d'experiència, amb `experience_id` = l'id de l'experiència (string UUID); els de fotos del refugi, `null`.
- Mateixa regla de visibilitat per estat (visible per a tothom; la resta, autor i admin) i mateix ordre `(uploaded_at, key)`.
- `GET /refuges/?type=…` (cerca amb filtres, autenticat): `images_metadata` també inclou els mitjans d'experiència.
- `DELETE /refuges/{id}/media/{key}/` d'un mitjà d'experiència: l'autor o un admin; l'experiència es conserva.
- Esborrar el refugi cascadeja experiències i mitjans.
"""
import pytest

from apps.experiences.tests.helpers import make_exp_media, make_experience, sql
from apps.refuges.tests.helpers import (
    MEDIA_ITEM_KEYS, admin_claims, api_delete, api_get, make_media, make_refuge, make_user, user_claims)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration]

URL = '/api/refuges/'


@pytest.fixture
def scene():
    for uid in ('u1', 'u2', 'adm'):
        make_user(uid)
    r = make_refuge(name='Refugi amb experiències')
    e = make_experience(r, 'u1')
    return r, e


def detail(r):
    return f'{URL}{r.pk}/'


def test_la_llista_de_mitjans_inclou_els_d_experiencia_amb_experience_id(client, scene):
    r, e = scene
    make_media(r, 'u2', key='k/foto.webp', minutes=1)
    make_exp_media(r, 'u1', e, key='k/exp.webp', minutes=2, thumb_key='k/exp_t.webp', width=640, height=480)
    resp = api_get(client, f'{detail(r)}media/', user_claims('u2'))
    assert resp.status_code == 200
    items = resp.json()['media']
    assert [(i['key'], i['experience_id']) for i in items] == [('k/exp.webp', e), ('k/foto.webp', None)]
    assert all(set(i) == MEDIA_ITEM_KEYS for i in items)
    exp = items[0]
    assert isinstance(exp['experience_id'], str) and exp['thumb_url'] == 'https://r2.test/k/exp_t.webp?sig=1'
    assert (exp['width'], exp['height'], exp['creator_uid']) == (640, 480, 'u1')


def test_el_detall_autenticat_inclou_els_mitjans_d_experiencia(client, scene):
    r, e = scene
    make_exp_media(r, 'u1', e, key='k/exp.webp', minutes=1)
    make_media(r, 'u2', key='k/foto.webp', minutes=2)
    d = api_get(client, detail(r), user_claims('u2')).json()
    assert [(i['key'], i['experience_id']) for i in d['images_metadata']] == [('k/foto.webp', None), ('k/exp.webp', e)]


def test_el_detall_anonim_continua_sense_mitjans(client, scene):
    r, e = scene
    make_exp_media(r, 'u1', e, key='k/exp.webp')
    assert 'images_metadata' not in api_get(client, detail(r)).json()


@pytest.mark.parametrize('claims,expected', [
    (user_claims('u2'), ['k/vis.webp']),
    (user_claims('u1'), ['k/vis.webp', 'k/hid.webp', 'k/rem.webp']),
    (admin_claims(), ['k/vis.webp', 'k/hid.webp', 'k/rem.webp']),
])
def test_visibilitat_per_estat_dels_mitjans_d_experiencia(client, scene, claims, expected):
    r, e = scene
    make_exp_media(r, 'u1', e, key='k/vis.webp', minutes=1)
    make_exp_media(r, 'u1', e, key='k/hid.webp', status='hidden_pending_review', minutes=2)
    make_exp_media(r, 'u1', e, key='k/rem.webp', status='removed', minutes=3)
    for path in (f'{detail(r)}media/', detail(r)):
        body = api_get(client, path, claims).json()
        assert [i['key'] for i in body.get('media', body.get('images_metadata'))] == expected


def test_la_cerca_amb_filtres_inclou_els_mitjans_d_experiencia_a_images_metadata(client, scene):
    r, e = scene
    make_exp_media(r, 'u1', e, key='k/exp.webp', minutes=1)
    make_media(r, 'u2', key='k/foto.webp', minutes=2)
    data = api_get(client, URL + '?type=non gardé', user_claims('u2')).json()
    (item,) = data['results']
    assert [(i['key'], i['experience_id']) for i in item['images_metadata']] == [('k/foto.webp', None),
                                                                                ('k/exp.webp', e)]


def test_delete_d_un_mitja_d_experiencia_per_l_autor_conserva_l_experiencia(client, scene, RM):
    r, e = scene
    make_exp_media(r, 'u1', e, key='k/exp.webp', thumb_key='k/exp_t.webp')
    resp = api_delete(client, f'{detail(r)}media/k/exp.webp/', user_claims('u1'))
    assert resp.status_code == 200
    assert RM.RefugeMedia.objects.count() == 0
    assert sql('SELECT count(*) FROM activity.experiences WHERE id = %s', [e]) == [(1,)]


def test_delete_d_un_mitja_d_experiencia_per_un_altre_es_403(client, scene, RM):
    r, e = scene
    make_exp_media(r, 'u1', e, key='k/exp.webp')
    assert api_delete(client, f'{detail(r)}media/k/exp.webp/', user_claims('u2')).status_code == 403
    assert RM.RefugeMedia.objects.count() == 1


def test_l_admin_pot_esborrar_un_mitja_d_experiencia(client, scene, RM):
    r, e = scene
    make_exp_media(r, 'u1', e, key='k/exp.webp')
    assert api_delete(client, f'{detail(r)}media/k/exp.webp/', admin_claims()).status_code == 200
    assert RM.RefugeMedia.objects.count() == 0


def test_esborrar_el_refugi_cascadeja_experiencies_i_mitjans(scene, RM):
    from apps.refuges.tests.helpers import as_owner
    r, e = scene
    make_exp_media(r, 'u1', e, key='k/exp.webp')
    other = make_refuge(name='Altre', lat=43)
    make_media(other, 'u1', key='k/altre.webp')
    with as_owner():
        sql('DELETE FROM refuges.refuges WHERE id = %s', [r.pk])
    assert sql('SELECT count(*) FROM activity.experiences') == [(0,)]
    assert list(RM.RefugeMedia.objects.values_list('key', flat=True)) == ['k/altre.webp']


def test_les_lectures_de_mitjans_no_fan_consultes_extra_per_tenir_experiencies(client, scene):
    from apps.refuges.tests.helpers import QueryCounter
    r, e = scene
    sizes = []
    for n in (1, 8):
        for i in range(n):
            make_exp_media(r, 'u1', e, key=f'k/e{n}-{i}.webp', minutes=10 * n + i)
        with QueryCounter() as q:
            resp = api_get(client, f'{detail(r)}media/', user_claims('u2'))
        assert resp.status_code == 200
        sizes.append(q.count)
    assert sizes[0] == sizes[1], sizes
