"""
Pressupost de consultes del chunk 5 (§5.3): cap N+1. El recompte exclou `set_config`/punts de desat (`QueryCounter`) i
inclou la lectura de `users` de `HasProfile` (una sola per petició).

Pressupost del disseny: `GET /renovations/` i `GET /refuges/{id}/renovations/` = 1 consulta de dades (el segon necessita
una més per distingir «refugi sense reformes» de «refugi inexistent»); el detall, 1. Aquí s'exigeix, a més, que el
recompte **no depengui del nombre de files** (mateix valor amb 2 i amb 25 reformes de 3 participants).
"""
import pytest

from apps.renovations.tests.helpers import (
    QueryCounter, RENOVATIONS, api_delete, api_get, api_patch, api_post, day, make_refuge, make_renovation, make_user,
    new_body, reno_url, refuge_reno_url, sql, user_claims)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration,
              pytest.mark.real_permissions]


def populate(n):
    for uid in ('u1', 'u2', 'u3', 'u4', 'u5'):
        make_user(uid)
    refuge = make_refuge(name='Gran')
    ids = [make_renovation(refuge, 'u1', ini=day(i * 4 + 1), fin=day(i * 4 + 3), participants=['u2', 'u3', 'u4'],
                           expelled=['u5']) for i in range(n)]
    return refuge, ids


def wipe():
    sql('DELETE FROM activity.renovations')
    sql('DELETE FROM users.users')
    from apps.renovations.tests.helpers import as_owner
    from django.db import connection
    with as_owner():
        with connection.cursor() as cur:
            cur.execute('DELETE FROM refuges.refuges')


def counts_for(sizes, call):
    out = []
    for n in sizes:
        refuge, ids = populate(n)
        with QueryCounter() as q:
            resp = call(refuge, ids)
        assert resp.status_code == 200, resp.content
        out.append(q.count)
        wipe()
    return out


def test_llista_global_constant(client):
    c = counts_for([2, 25], lambda r, ids: api_get(client, RENOVATIONS, user_claims('u2')))
    assert c[0] == c[1], c
    assert c[0] <= 2, c                                   # dades + HasProfile


def test_llista_de_refugi_constant(client):
    c = counts_for([2, 25], lambda r, ids: api_get(client, refuge_reno_url(r.pk), user_claims('u2')))
    assert c[0] == c[1], c
    assert c[0] <= 3, c                                   # dades + existència del refugi + HasProfile


def test_llista_de_refugi_amb_active_only_constant(client):
    c = counts_for([2, 25], lambda r, ids: api_get(client, refuge_reno_url(r.pk) + '?active_only=true',
                                                   user_claims('u3')))
    assert c[0] == c[1] and c[0] <= 3, c


def test_detall_constant_amb_el_nombre_de_participants(client):
    c = counts_for([1, 1], lambda r, ids: api_get(client, reno_url(ids[0]), user_claims('u2')))
    assert c[0] <= 2, c
    for extra in (0, 4):
        refuge, ids = populate(1)
        for i in range(extra):
            uid = f'x{i}'
            make_user(uid)
            sql('INSERT INTO activity.renovation_participants (renovation_id, user_uid) VALUES (%s, %s)',
                [ids[0], uid])
        with QueryCounter() as q:
            assert api_get(client, reno_url(ids[0]), user_claims('u2')).status_code == 200
        c.append(q.count)
        wipe()
    assert c[1] == c[2] == c[3], c


def test_unir_se_i_sortir_constants(client):
    out = []
    for n in (2, 25):
        refuge, ids = populate(n)
        make_user('j1')
        with QueryCounter() as qj:
            assert api_post(client, reno_url(ids[-1], 'participants'), user_claims('j1'), None).status_code == 200
        with QueryCounter() as ql:
            assert api_delete(client, reno_url(ids[-1], 'participants', 'j1'), user_claims('j1')).status_code == 200
        with QueryCounter() as qe:
            assert api_delete(client, reno_url(ids[-1], 'participants', 'u2'), user_claims('u1')).status_code == 200
        out.append((qj.count, ql.count, qe.count))
        wipe()
    assert out[0] == out[1], out
    assert all(c <= 8 for c in out[0]), out


def test_crear_i_editar_constants_amb_moltes_reformes_al_refugi(client):
    out = []
    for n in (2, 25):
        refuge, ids = populate(n)
        with QueryCounter() as qc:
            body = new_body(refuge, ini_date=day(500).isoformat(), fin_date=day(502).isoformat())
            assert api_post(client, RENOVATIONS, user_claims('u1'), body).status_code == 201
        with QueryCounter() as qp:
            assert api_patch(client, reno_url(ids[0]), user_claims('u1'),
                             {'description': 'x', 'fin_date': day(3).isoformat()}).status_code == 200
        out.append((qc.count, qp.count))
        wipe()
    assert out[0] == out[1], out
    assert all(c <= 8 for c in out[0]), out
