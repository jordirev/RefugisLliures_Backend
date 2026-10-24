"""
Pressupost de consultes del chunk 3 (§5.3): cap N+1. El recompte exclou `set_config`/punts de desat (QueryCounter).

Convencio: el pressupost del disseny compta la consulta de dades; aqui s'hi suma la lectura de `users` de `HasProfile`
(una sola per peticio, compartida amb IsNotBlocked/IsAgeConfirmed). Les agregacions de Firestore (D19) estan mockejades.
El que es verifica estrictament es que el recompte **no depen del nombre de files** (mateix valor amb 1 i amb 30).
"""
import pytest

from apps.accounts.tests.helpers import (
    FAV, VIS, QueryCounter, add_list_row, admin_claims, api_delete, api_get, api_patch, api_post, make_avatar,
    make_media, make_refuge, make_user, url, user_claims)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration,
              pytest.mark.real_permissions]


def populate(n, kind=None):
    make_user('u1', username='Anna')
    make_user('u2')
    refuges = []
    for i in range(n):
        r = make_refuge(name=f'R{i:03d}', lat=42 + i / 100, long=1 + i / 100, places=5)
        for k in range(2):
            make_media(r, 'u2', key=f'k/{i}/{k}.webp', minutes=k)
        if kind in (FAV, 'all'):
            add_list_row(FAV, 'u1', r, i)
        if kind in (VIS, 'all'):
            add_list_row(VIS, 'u1', r, i)
        refuges.append(r)
    make_avatar('u1')
    make_avatar('u2')
    return refuges


def measure(fn):
    with QueryCounter() as q:
        resp = fn()
    return resp, q.count, q.queries


def counts_for(sizes, make_call, kind=None, expect=200):
    out = []
    for n in sizes:
        populate(n, kind)
        resp, c, queries = measure(make_call)
        assert resp.status_code == expect, resp.content
        out.append(c)
        _wipe()
    return out


def _wipe():
    from apps.accounts.tests.helpers import sql
    sql('DELETE FROM users.users')
    from apps.accounts.tests.helpers import as_owner
    from django.db import connection
    with as_owner():
        with connection.cursor() as cur:
            cur.execute('DELETE FROM refuges.refuges')


# ---------- perfil ----------

@pytest.mark.parametrize('claims_uid,target', [('u1', 'u1'), ('u2', 'u1')])
def test_get_perfil_constant_i_com_a_molt_2_consultes(client, claims_uid, target):
    """Propi: lectura de permis + perfil amb llistes (`ArraySubquery`), cap consulta per refugi."""
    sizes = []
    for n in (1, 30):
        populate(n, 'all')
        _, c, q = measure(lambda: api_get(client, url(target), user_claims(claims_uid)))
        sizes.append(c)
        _wipe()
    assert sizes[0] == sizes[1] and sizes[0] <= 2, sizes


def test_get_perfil_aliè_no_consulta_les_llistes(client):
    populate(5, 'all')
    _, c, queries = measure(lambda: api_get(client, url('u1'), user_claims('u2')))
    assert c <= 2
    assert not any('user_favourite_refuges' in s or 'user_visited_refuges' in s for s in queries), queries


# ---------- llistes ----------

@pytest.mark.parametrize('kind', [FAV, VIS])
def test_llista_constant_i_com_a_molt_3_consultes(client, kind):
    """Permis (1) + llista JOIN refugis (1) + primera imatge de cada refugi amb un sol `Prefetch` (1)."""
    sizes = []
    for n in (1, 30):
        populate(n, kind)
        _, c, _ = measure(lambda: api_get(client, url('u1', kind), user_claims('u1')))
        sizes.append(c)
        _wipe()
    assert sizes[0] == sizes[1] and sizes[0] <= 3, sizes


@pytest.mark.parametrize('kind', [FAV, VIS])
def test_post_constant(client, kind):
    sizes = []
    for n in (1, 30):
        refuges = populate(n, kind)
        extra = make_refuge(name='Extra', lat=44.5)
        _, c, _ = measure(lambda: api_post(client, url('u1', kind), user_claims('u1'), {'refuge_id': str(extra.pk)}))
        sizes.append(c)
        _wipe()
    assert sizes[0] == sizes[1] and sizes[0] <= 6, sizes


@pytest.mark.parametrize('kind', [FAV, VIS])
def test_post_idempotent_no_costa_mes(client, kind):
    refuges = populate(3, kind)
    _, c, _ = measure(lambda: api_post(client, url('u1', kind), user_claims('u1'), {'refuge_id': str(refuges[0].pk)}))
    assert c <= 6


@pytest.mark.parametrize('kind', [FAV, VIS])
def test_delete_constant(client, kind):
    sizes = []
    for n in (2, 30):
        refuges = populate(n, kind)
        resp, c, _ = measure(lambda: api_delete(client, url('u1', kind, refuges[0].pk), user_claims('u1')))
        assert resp.status_code == 204
        sizes.append(c)
        _wipe()
    assert sizes[0] == sizes[1] and sizes[0] <= 4, sizes


# ---------- escriptures d'usuari ----------

def test_patch_constant(client):
    sizes = []
    for n in (1, 30):
        populate(n, 'all')
        _, c, _ = measure(lambda: api_patch(client, url('u1'), user_claims('u1'), {'username': 'Nou', 'language': 'es'}))
        sizes.append(c)
        _wipe()
    assert sizes[0] == sizes[1] and sizes[0] <= 6, sizes


def test_post_users_pocs_viatges(client):
    resp, c, queries = measure(lambda: api_post(client, '/api/users/', user_claims('n1'),
                                                {'username': 'Anna', 'language': 'es'}))
    assert resp.status_code == 201
    # existencia/INSERT users + INSERT perfil + cataleg d'idiomes + lectura del perfil resultant
    assert c <= 6, queries


# ---------- detall de refugi: `visitors` per a admins ----------

def test_detall_de_refugi_admin_com_a_molt_3_consultes_amb_molts_visitants(client):
    r = make_refuge()
    for i in range(30):
        make_user(f'v{i}')
        add_list_row(VIS, f'v{i}', r)
    make_user('adm')
    _, c, queries = measure(lambda: api_get(client, f'/api/refuges/{r.pk}/', admin_claims('adm')))
    assert c <= 3, queries
    visitors_queries = [s for s in queries if 'user_visited_refuges' in s]
    assert len(visitors_queries) == 1
