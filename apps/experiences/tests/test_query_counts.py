"""
Pressupost de consultes del chunk 7 (§5.3): cap N+1. El recompte exclou `set_config`/punts de desat (QueryCounter) i
inclou la lectura de `users` de `HasProfile` (una per petició).

Pressupost: `GET /experiences/?refuge_id=` <= 4 (perfil, existència del refugi, experiències, mitjans amb `Prefetch`:
la recepta del disseny diu «2» sense comptar el perfil ni l'existència); POST <= 5; PATCH <= 5; DELETE <= 5. El que
es verifica estrictament és que el recompte **no depèn del nombre de files** (mateix valor amb 1 i amb molts
experiències/mitjans) i que esborrar és UN `DELETE` (la BD cascadeja els mitjans).
"""
import pytest

from apps.experiences.tests.helpers import (
    EXPERIENCES, QueryCounter, api_delete, api_get, api_patch, api_post, exp_ids, exp_url, list_url, make_exp_media,
    make_experience, new_body, user_claims)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration,
              pytest.mark.real_permissions]


def measure(fn):
    with QueryCounter() as q:
        resp = fn()
    return resp, q


def populate(refuge, n, images=3, tag=''):
    base = 1000 * len(tag) + 10 * n
    for i in range(n):
        e = make_experience(refuge, 'u1' if i % 2 else 'u2', comment=f'{tag}e{i}', minutes=base + i)
        for k in range(images):
            make_exp_media(refuge, 'u1' if i % 2 else 'u2', e, key=f'k/{tag}{i}-{k}.webp',
                           thumb_key=f'k/{tag}{i}-{k}_t.webp', minutes=base + i * 10 + k)


def test_llista_amb_imatges_sense_n_mes_1(client, world):
    r1, _ = world
    counts = []
    populate(r1, 1, tag='a')
    resp, q = measure(lambda: api_get(client, list_url(r1.pk), user_claims('u3')))
    assert resp.status_code == 200 and len(resp.json()['experiences']) == 1
    counts.append(q.count)
    populate(r1, 14, tag='bb')
    resp, q = measure(lambda: api_get(client, list_url(r1.pk), user_claims('u3')))
    experiences = resp.json()['experiences']
    assert resp.status_code == 200 and len(experiences) == 15
    assert all(len(e['images_metadata']) == 3 for e in experiences)
    counts.append(q.count)
    assert counts[0] == counts[1] <= 4, (counts, q.queries)


def test_llista_buida_dins_del_pressupost(client, world):
    resp, q = measure(lambda: api_get(client, list_url(world[0].pk), user_claims('u1')))
    assert resp.status_code == 200 and q.count <= 4, q.queries


def test_la_llista_fa_exactament_dues_consultes_de_domini(client, world):
    """Experiències + mitjans (el recompte total inclou el perfil de `HasProfile` i l'existència del refugi)."""
    populate(world[0], 5, tag='x')
    resp, q = measure(lambda: api_get(client, list_url(world[0].pk), user_claims('u3')))
    assert resp.status_code == 200
    on_experiences = [s for s in q.queries if 'activity"."experiences' in s or 'activity.experiences' in s]
    on_media = [s for s in q.queries if 'refuge_media' in s]
    assert len(on_experiences) == 1 and len(on_media) == 1, q.queries


def test_llista_d_admin_no_cost_mes(client, world):
    from apps.experiences.tests.helpers import admin_claims
    populate(world[0], 6, tag='y')
    _, q_user = measure(lambda: api_get(client, list_url(world[0].pk), user_claims('u3')))
    _, q_admin = measure(lambda: api_get(client, list_url(world[0].pk), admin_claims('adm')))
    assert q_admin.count == q_user.count


def test_post(client, world):
    resp, q = measure(lambda: api_post(client, EXPERIENCES, user_claims('u1'), new_body(world[0])))
    assert resp.status_code == 201 and q.count <= 5, q.queries


def test_post_constant_amb_moltes_experiencies_al_refugi(client, world):
    sizes = []
    for n in (1, 12):
        populate(world[0], n, images=1, tag=f'p{n}')
        resp, q = measure(lambda: api_post(client, EXPERIENCES, user_claims('u1'), new_body(world[0])))
        assert resp.status_code == 201
        sizes.append(q.count)
    assert sizes[0] == sizes[1] <= 5, sizes


def test_patch_constant_amb_molts_mitjans(client, world):
    sizes = []
    for images in (0, 10):
        e = make_experience(world[0], 'u1', minutes=2000 + images)
        for k in range(images):
            make_exp_media(world[0], 'u1', e, key=f'k/p{images}-{k}.webp', minutes=3000 + k)
        resp, q = measure(lambda: api_patch(client, exp_url(e), user_claims('u1'), {'comment': 'x', 'condition': 3}))
        assert resp.status_code == 200 and len(resp.json()['experience']['images_metadata']) == images
        sizes.append(q.count)
    assert sizes[0] == sizes[1] <= 5, sizes


def test_delete_constant_i_un_sol_delete(client, world):
    sizes, deletes = [], []
    for images in (0, 10):
        e = make_experience(world[0], 'u1', minutes=2000 + images)
        for k in range(images):
            make_exp_media(world[0], 'u1', e, key=f'k/d{images}-{k}.webp', thumb_key=f'k/d{images}-{k}_t.webp',
                           minutes=3000 + k)
        resp, q = measure(lambda: api_delete(client, exp_url(e), user_claims('u1')))
        assert resp.status_code == 200
        sizes.append(q.count)
        deletes.append([s for s in q.queries if s.lstrip().upper().startswith('DELETE')])
    assert sizes[0] == sizes[1] <= 5, sizes
    assert all(len(d) == 1 and 'experiences' in d[0] for d in deletes), deletes   # els mitjans cauen per la FK
    assert exp_ids() == []
