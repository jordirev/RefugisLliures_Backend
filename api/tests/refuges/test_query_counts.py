"""
Pressupost de consultes (§5.3, «Pressupost de consultes per endpoint»): cap N+1.

No es compten `set_config` (context RLS) ni els `SAVEPOINT` de la transacció de la petició. Els comptatges són
constants: no depenen del nombre de refugis, enllaços o mitjans.
"""
import pytest

from api.tests.refuges.helpers import (
    QueryCounter, admin_claims, api_delete, api_get, make_media, make_refuge, make_user, user_claims)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration]

URL = '/api/refuges/'


def populate(n, media_per_refuge=2, links=3):
    make_user('u1')
    refuges = []
    for i in range(n):
        r = make_refuge(name=f'Refugi {i:03d}', lat=42 + i / 100, long=1 + i / 100, type='orri', places=5 + i,
                        altitude=1000 + i, condition=(i % 4) * 0.75, num_contributed_conditions=1,
                        amenities={'eau': True}, links=[f'https://x.org/{i}/{k}' for k in range(links)])
        for k in range(media_per_refuge):
            make_media(r, 'u1', key=f'k/{i}/{k}.webp', minutes=k)
        refuges.append(r)
    return refuges


def count(client, path, claims=None):
    with QueryCounter() as q:
        r = api_get(client, path, claims)
    assert r.status_code == 200, r.content
    return q.count, q.queries


# ---------- Llista sense filtres ----------

@pytest.mark.parametrize('n', [1, 30])
def test_llista_sense_filtres_1_consulta(client, RM, n):
    populate(n)
    assert count(client, URL)[0] == 1
    assert count(client, URL, user_claims('u2'))[0] == 1


# ---------- Llista amb filtres ----------

@pytest.mark.parametrize('n', [1, 30])
def test_llista_amb_filtres_1_consulta_anonim_i_2_autenticat(client, RM, n):
    populate(n)
    assert count(client, URL + '?type=orri')[0] == 1
    assert count(client, URL + '?type=orri', user_claims('u2'))[0] == 2          # + mitjans en bloc (Prefetch)


def test_llista_amb_filtres_de_nom_i_condicio_continua_sent_1_consulta(client, RM):
    populate(10)
    assert count(client, URL + '?name=refugi&condition=0,1,2,3&places_min=1&altitude_max=5000')[0] == 1


def test_el_nombre_de_consultes_no_creix_amb_els_resultats(client, RM):
    populate(5)
    small = count(client, URL + '?type=orri', user_claims('u2'))[0]
    populate_more = [make_refuge(name=f'Extra {i}', lat=44 + i / 100, type='orri', links=['https://y.org/1'])
                     for i in range(25)]
    for r in populate_more:
        make_media(r, 'u1', key=f'extra/{r.pk}.webp')
    assert count(client, URL + '?type=orri', user_claims('u2'))[0] == small


# ---------- Detall ----------

def test_detall_1_consulta_anonim_2_autenticat_i_com_a_molt_3_admin(client, RM):
    (r, *_) = populate(3, media_per_refuge=5, links=4)
    path = f'{URL}{r.pk}/'
    assert count(client, path)[0] == 1
    assert count(client, path, user_claims('u2'))[0] == 2
    assert count(client, path, admin_claims())[0] <= 3          # +1 `visitors` quan existeixi (chunk 3)


def test_detall_no_depen_del_nombre_d_enllacos_ni_mitjans(client, RM):
    (a,) = populate(1, media_per_refuge=0, links=0)
    b = make_refuge(name='Gran', lat=43, links=[f'https://z.org/{k}' for k in range(10)])
    for k in range(20):
        make_media(b, 'u1', key=f'g/{k}.webp', minutes=k)
    assert count(client, f'{URL}{a.pk}/', user_claims('u2'))[0] == count(client, f'{URL}{b.pk}/', user_claims('u2'))[0]


# ---------- Mitjans ----------

def test_llista_de_mitjans_com_a_molt_2_consultes(client, RM):
    (r, *_) = populate(2, media_per_refuge=15)
    n, _ = count(client, f'{URL}{r.pk}/media/', user_claims('u2'))
    assert n <= 2                                              # existència del refugi + mitjans


def test_esborrar_un_mitja_no_fa_consultes_per_mitja(client, RM):
    (r, *_) = populate(1, media_per_refuge=1)
    with QueryCounter() as q:
        resp = api_delete(client, f'{URL}{r.pk}/media/k/0/0.webp/', user_claims('u1'))
    assert resp.status_code == 200
    assert q.count <= 4, q.queries
