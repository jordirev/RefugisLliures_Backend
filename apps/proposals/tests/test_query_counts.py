"""
Pressupost de consultes del chunk 8 (§5.3): cap N+1. El recompte exclou `set_config`/punts de desat (`QueryCounter`) i
inclou la lectura de `users` de `HasProfile` (una per petició).

Pressupost: llistes (admin i meves) <= 2 (perfil + llista, amb les fotos i els payloads com a columnes `jsonb`);
POST create <= 4; POST update/delete <= 5 (perfil, refugi per a la foto, inserció...); reject <= 4. El que es verifica
estrictament és que el recompte **no depèn del nombre de files**: llistes amb 1 i 15 propostes, aprovar un `update` amb
1 i 10 enllaços, aprovar un `delete` amb 0 i 20 propostes pendents més i moltes dades relacionades (la BD cascadeja).
"""
import pytest

from apps.proposals.tests.helpers import (
    MINE, PROPOSALS, QueryCounter, admin_claims, api_get, api_post, approve_url, create_body, delete_body, make_media,
    make_proposal, make_refuge, new_payload, proposal_row, reject_url, sql, update_body, user_claims)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration,
              pytest.mark.real_permissions]


def measure(fn):
    with QueryCounter() as q:
        resp = fn()
    return resp, q


def populate(world, n, tag):
    r1, r2 = world
    base = 100 * len(tag)
    for i in range(n):
        make_proposal(('create', 'update', 'delete')[i % 3], refuge=None if i % 3 == 0 else (r1, r2)[i % 2],
                      creator=('u1', 'u2')[i % 2], minutes=base + i)


def test_llista_d_admin_constant_amb_les_files(client, world):
    counts = []
    populate(world, 1, 'a')
    resp, q = measure(lambda: api_get(client, PROPOSALS, admin_claims('adm')))
    assert resp.status_code == 200 and len(resp.json()) == 1
    counts.append(q.count)
    populate(world, 14, 'bb')
    resp, q = measure(lambda: api_get(client, PROPOSALS, admin_claims('adm')))
    assert resp.status_code == 200 and len(resp.json()) == 15
    counts.append(q.count)
    assert counts[0] == counts[1] <= 2, (counts, q.queries)


def test_llista_d_admin_amb_filtres_i_buida_dins_del_pressupost(client, world):
    resp, q = measure(lambda: api_get(client, PROPOSALS, admin_claims('adm')))
    assert resp.status_code == 200 and q.count <= 2, q.queries
    populate(world, 6, 'c')
    resp, q = measure(lambda: api_get(client, f'{PROPOSALS}?status=pending&refuge-id={world[0].pk}',
                                      admin_claims('adm')))
    assert resp.status_code == 200 and q.count <= 2, q.queries


def test_les_meves_constants_amb_les_files(client, world):
    counts = []
    populate(world, 2, 'a')
    resp, q = measure(lambda: api_get(client, MINE, user_claims('u1')))
    assert resp.status_code == 200
    counts.append(q.count)
    populate(world, 20, 'bb')
    resp, q = measure(lambda: api_get(client, MINE, user_claims('u1')))
    assert resp.status_code == 200 and len(resp.json()) > 5
    counts.append(q.count)
    assert counts[0] == counts[1] <= 2, (counts, q.queries)


def test_post_create(client, world):
    resp, q = measure(lambda: api_post(client, PROPOSALS, user_claims('u1'), create_body()))
    assert resp.status_code == 201 and q.count <= 4, q.queries


def test_post_update_i_delete(client, world):
    r1, r2 = world
    resp, qu = measure(lambda: api_post(client, PROPOSALS, user_claims('u1'), update_body(r1, {'places': 3})))
    assert resp.status_code == 201 and qu.count <= 5, qu.queries
    resp, qd = measure(lambda: api_post(client, PROPOSALS, user_claims('u1'), delete_body(r2)))
    assert resp.status_code == 201 and qd.count <= 5, qd.queries


def test_post_update_constant_amb_la_mida_del_refugi(client, world):
    small = make_refuge(name='Petit', lat=44.0)
    big = make_refuge(name='Gran', lat=44.5, links=[f'https://a.test/{i}' for i in range(30)])
    out = []
    for r in (small, big):
        resp, q = measure(lambda: api_post(client, PROPOSALS, user_claims('u1'), update_body(r, {'places': 3})))
        assert resp.status_code == 201
        out.append(q.count)
    assert out[0] == out[1], out


def test_reject_dins_del_pressupost(client, world):
    pid = make_proposal()
    resp, q = measure(lambda: api_post(client, reject_url(pid), admin_claims('adm'), {'reason': 'x'}))
    assert resp.status_code == 200 and q.count <= 4, q.queries


def test_approve_update_constant_amb_el_nombre_d_enllacos(client, world):
    r1, r2 = world
    out = []
    for r, n in ((r1, 1), (r2, 10)):
        pid = make_proposal('update', refuge=r, payload={'links': [f'https://a.test/{r.pk}/{i}' for i in range(n)],
                                                         'info_comp': {'eau': 1}, 'condition': 2})
        resp, q = measure(lambda: api_post(client, approve_url(pid), admin_claims('adm')))
        assert resp.status_code == 200, resp.content
        out.append(q.count)
    assert out[0] == out[1] <= 15, out


def test_approve_create_constant_amb_el_nombre_d_enllacos(client, world):
    out = []
    for n in (0, 12):
        pid = make_proposal(payload=new_payload(name=f'N{n}', links=[f'https://a.test/c{n}/{i}' for i in range(n)]),
                            minutes=n)
        resp, q = measure(lambda: api_post(client, approve_url(pid), admin_claims('adm')))
        assert resp.status_code == 200, resp.content
        out.append(q.count)
    assert out[0] <= out[1] <= out[0] + 1 and out[1] <= 15, out         # com a molt +1 (enllaços en un sol INSERT)


def test_approve_delete_constant_amb_les_propostes_pendents_i_les_dades_relacionades(client, world):
    from apps.proposals.tests.helpers import make_user
    rs = [make_refuge(name=f'D{i}', lat=45 + i) for i in range(2)]
    make_user('u9')
    for i in range(20):                                                   # moltes pendents del segon refugi
        make_proposal('update', refuge=rs[1], minutes=i)
    for i in range(10):
        make_media(rs[1], 'u9', key=f'k/{i}.webp', minutes=i)
        sql('INSERT INTO activity.doubts (refuge_id, creator_uid, message) VALUES (%s, %s, %s)', [rs[1].pk, 'u9', 'x'])
    out = []
    for r in rs:
        pid = make_proposal('delete', refuge=r, creator='u1', minutes=500)
        resp, q = measure(lambda: api_post(client, approve_url(pid), admin_claims('adm')))
        assert resp.status_code == 200, resp.content
        deletes = [s for s in q.queries if s.upper().startswith('DELETE') and 'refuges"."refuges' in s]
        assert len(deletes) == 1, q.queries                               # UN sol DELETE del refugi: cascada a la BD
        out.append(q.count)
    assert out[0] <= out[1] <= out[0] + 2 and out[1] <= 20, out           # +2: lectura de claus d'R2 i esborrat
    assert proposal_row(pid)['status'] == 'approved'
