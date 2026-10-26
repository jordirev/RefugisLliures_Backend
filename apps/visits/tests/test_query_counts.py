"""
Pressupost de consultes del chunk 4 (§5.3, recepta 6): cap N+1. El recompte exclou `set_config`/punts de desat
(`QueryCounter`) i inclou la lectura d'`users` de `HasProfile` (una per peticio).

Pressupost (maxim) i constancia: el recompte **no pot dependre** del nombre de visites ni de participants.
    GET /refuges/{id}/visits/   <= 3 (permis + existencia del refugi + visites amb total/is_visitor/num_visitors)
    GET /users/{uid}/visits/    <= 2 (permis + visites)         [B5: amb index, sense recorrer la taula]
    POST / PATCH / DELETE       <= 7
    process_yesterday_visits    <= 8 i constant (set-based, recepta 9)
"""
import pytest

from apps.visits.tests.helpers import (
    QueryCounter, api_delete, api_get, api_patch, api_post, day, make_refuge, make_user, make_visit, refuge_visits_url,
    sql, user_claims, user_visits_url, visit_services, visit_url)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration,
              pytest.mark.real_permissions]


def populate(n_visits, n_users):
    """`n_visits` visites futures al refugi i a cadascuna `n_users` participants (+ `me`)."""
    make_user('me')
    users = [f'p{i}' for i in range(n_users)]
    for u in users:
        make_user(u)
    r = make_refuge()
    for i in range(n_visits):
        make_visit(r, day(1 + i), {'me': 1, **{u: 2 for u in users}})
    return r


def wipe():
    sql('DELETE FROM users.users')
    sql('DELETE FROM activity.refuge_visits')
    from django.db import connection
    from apps.visits.tests.helpers import as_owner
    with as_owner():
        with connection.cursor() as cur:
            cur.execute('DELETE FROM refuges.refuges')


def measure(fn):
    with QueryCounter() as q:
        resp = fn()
    return resp, q.count, q.queries


def test_get_visites_del_refugi_constant_i_com_a_molt_3(client):
    counts = []
    for visits, users in ((1, 1), (25, 12)):
        r = populate(visits, users)
        resp, c, queries = measure(lambda: api_get(client, refuge_visits_url(r.pk), user_claims('me')))
        assert resp.status_code == 200 and len(resp.json()['result']) == visits
        counts.append(c)
        wipe()
    assert counts[0] == counts[1] <= 3, counts


def test_get_visites_de_l_usuari_constant_i_com_a_molt_2(client):
    counts = []
    for visits, users in ((1, 1), (25, 12)):
        populate(visits, users)
        resp, c, queries = measure(lambda: api_get(client, user_visits_url('me'), user_claims('me')))
        assert resp.status_code == 200 and len(resp.json()['result']) == visits
        counts.append(c)
        wipe()
    assert counts[0] == counts[1] <= 2, counts


def test_post_constant_i_com_a_molt_7(client):
    counts = []
    for users in (1, 15):
        r = populate(1, users)
        resp, c, _ = measure(lambda: api_post(client, visit_url(r.pk, day(40)), user_claims('me'), {'num_visitors': 3}))
        assert resp.status_code == 201
        counts.append(c)
        wipe()
    assert counts[0] == counts[1] <= 7, counts


def test_patch_i_delete_constants_i_com_a_molt_7(client):
    for fn, expected in ((lambda r: api_patch(client, visit_url(r.pk, day(1)), user_claims('me'), {'num_visitors': 4}), 200),
                         (lambda r: api_delete(client, visit_url(r.pk, day(1)), user_claims('me')), 200)):
        counts = []
        for users in (1, 15):
            r = populate(1, users)
            resp, c, _ = measure(lambda: fn(r))
            assert resp.status_code == expected
            counts.append(c)
            wipe()
        assert counts[0] == counts[1] <= 7, counts


def test_el_job_diari_te_un_recompte_constant(client):
    S = visit_services()
    counts = []
    for visits, users in ((1, 1), (20, 8)):
        make_user('me')
        for i in range(users):
            make_user(f'p{i}')
        for i in range(visits):
            r = make_refuge(name=f'R{i}', lat=42 + i / 100)
            make_visit(r, day(-1), {'me': 1, **{f'p{k}': 2 for k in range(users)}})
        with QueryCounter() as q:
            S.process_yesterday_visits()
        counts.append(q.count)
        wipe()
    assert counts[0] == counts[1] <= 8, counts
