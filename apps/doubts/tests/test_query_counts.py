"""
Pressupost de consultes del chunk 6 (§5.3): cap N+1. El recompte exclou `set_config`/punts de desat (QueryCounter) i
inclou la lectura de `users` de `HasProfile` (una per petició).

Pressupost: GET llista <= 4 (perfil, existència del refugi, dubtes amb `answers_count`, respostes); POST dubte <= 4;
POST resposta <= 5; DELETE dubte <= 4; DELETE resposta <= 4. El que es verifica estrictament és que el recompte
**no depèn del nombre de files** (mateix valor amb 1 i amb 15 dubtes, o amb un arbre petit i un de gran), i que
cada esborrat és UN `DELETE` (la BD cascadeja).
"""
import pytest

from apps.doubts.tests.helpers import (
    DOUBTS, QueryCounter, answers_url, answer_url, api_delete, api_get, api_post, doubt_url, list_url, make_answer,
    make_doubt, user_claims)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration,
              pytest.mark.real_permissions]


def measure(fn):
    with QueryCounter() as q:
        resp = fn()
    return resp, q


def populate(refuge, n, answers=3, tag=''):
    base = 1000 * len(tag) + 10 * n
    for i in range(n):
        d = make_doubt(refuge, 'u1', message=f'{tag}d{i}', minutes=base + i)
        parent = None
        for k in range(answers):
            parent = make_answer(d, 'u2' if k % 2 else 'u3', f'a{k}', parent=parent if k % 2 else None,
                                 minutes=base + i + k)


def test_llista_de_dubtes_amb_respostes_i_comptadors_sense_n_mes_1(client, world):
    r1, _ = world
    counts = []
    populate(r1, 1, tag='a')
    resp, q = measure(lambda: api_get(client, list_url(r1.pk), user_claims('u1')))
    assert resp.status_code == 200 and len(resp.json()) == 1
    counts.append(q.count)
    populate(r1, 14, tag='bb')
    resp, q = measure(lambda: api_get(client, list_url(r1.pk), user_claims('u1')))
    assert resp.status_code == 200 and len(resp.json()) == 15
    assert all(d['answers_count'] == 3 and len(d['answers']) == 3 for d in resp.json())
    counts.append(q.count)
    assert counts[0] == counts[1] <= 4, (counts, q.queries)


def test_llista_buida_dins_del_pressupost(client, world):
    resp, q = measure(lambda: api_get(client, list_url(world[0].pk), user_claims('u1')))
    assert resp.status_code == 200 and q.count <= 4, q.queries


def test_post_dubte(client, world):
    resp, q = measure(lambda: api_post(client, DOUBTS, user_claims('u1'),
                                       {'refuge_id': str(world[0].pk), 'message': 'x'}))
    assert resp.status_code == 201 and q.count <= 4, q.queries


def test_post_resposta_i_replica_constants_amb_la_mida_de_l_arbre(client, world):
    r1, _ = world
    small = make_doubt(r1, 'u1')
    big = make_doubt(r1, 'u1', minutes=1)
    populate_answers = [make_answer(big, 'u3', f'a{i}', minutes=2 + i) for i in range(40)]
    parent_small = make_answer(small, 'u3')
    out = []
    for d, parent in ((small, parent_small), (big, populate_answers[-1])):
        resp, qa = measure(lambda: api_post(client, answers_url(d), user_claims('u2'), {'message': 'x'}))
        assert resp.status_code == 201
        resp, qb = measure(lambda: api_post(client, answer_url(d, parent), user_claims('u2'), {'message': 'y'}))
        assert resp.status_code == 201
        out.append((qa.count, qb.count))
        assert qa.count <= 5 and qb.count <= 5, (qa.queries, qb.queries)
    assert out[0] == out[1], out


def test_delete_dubte_un_sol_delete_independentment_de_les_respostes(client, world):
    r1, _ = world
    results = []
    for n in (1, 30):
        d = make_doubt(r1, 'u1', minutes=n)
        prev = None
        for i in range(n):
            prev = make_answer(d, 'u2', f'a{i}', parent=prev, minutes=n + i)      # cadena profunda
        resp, q = measure(lambda: api_delete(client, doubt_url(d), user_claims('u1')))
        assert resp.status_code == 204
        deletes = [s for s in q.queries if s.upper().startswith('DELETE')]
        assert len(deletes) == 1 and q.count <= 4, q.queries
        results.append(q.count)
    assert results[0] == results[1]


def test_delete_resposta_un_sol_delete_per_a_un_subarbre_gran(client, world):
    r1, _ = world
    d = make_doubt(r1, 'u1')
    root = make_answer(d, 'u2', 'root', minutes=1)
    prev = root
    for i in range(30):
        prev = make_answer(d, 'u3', f'n{i}', parent=prev, minutes=2 + i)
    resp, q = measure(lambda: api_delete(client, answer_url(d, root), user_claims('u2')))
    assert resp.status_code == 204
    assert len([s for s in q.queries if s.upper().startswith('DELETE')]) == 1 and q.count <= 4, q.queries
