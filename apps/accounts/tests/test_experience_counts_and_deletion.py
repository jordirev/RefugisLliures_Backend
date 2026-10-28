"""
Experiències dins `accounts` (chunk 7): `num_shared_experiences` del perfil propi (D19 superat, §4) i esborrat d'usuari
(`DELETE /users/{uid}/`, §8.4, D21). Rol `app` + RLS reals.

Contracte:
- `num_shared_experiences` = `count(*)` d'`activity.experiences` amb `creator_uid = uid` (SQL); **cap** `count()` de
  Firestore: `apps.accounts.selectors._firestore_count` desapareix (o, com a mínim, no es crida mai; el marker
  `real_legacy_counts` el substitueix per un mock que ho registra).
- El pressupost de consultes del perfil propi no creix respecte d'abans: el comptador d'experiències no afegeix cap
  consulta nova (es calcula amb el de reformes / a la consulta del perfil).
- L'esborrat d'usuari no toca Firestore (la cascada de la FK `experiences.creator_uid -> users.users` i
  `refuge_media.experience_id` ho fa; D42).
"""
from unittest.mock import patch

import pytest

from apps.accounts.tests.helpers import QueryCounter, api_delete, api_get, make_refuge, sql, url, user_claims
from apps.experiences.tests.helpers import exp_ids, make_experience, make_user
from apps.renovations.tests.helpers import make_renovation

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration,
              pytest.mark.real_permissions, pytest.mark.real_legacy_counts]


@pytest.fixture
def world():
    for uid in ('u1', 'u2', 'u3'):
        make_user(uid, username=uid)
    return make_refuge(name='R1'), make_refuge(name='R2', lat=43), make_refuge(name='R3', lat=44)


def own_profile(client, uid):
    resp = api_get(client, url(uid), user_claims(uid))
    assert resp.status_code == 200, resp.content
    return resp.json()


def test_zero_sense_experiencies(client, world):
    assert own_profile(client, 'u1')['num_shared_experiences'] == 0


def test_compta_totes_les_experiencies_de_l_usuari_inclosos_diversos_refugis_i_repetits(client, world):
    r1, r2, _ = world
    make_experience(r1, 'u1')
    make_experience(r1, 'u1', minutes=1)                      # mateix refugi: compta igualment
    make_experience(r2, 'u1', minutes=2)
    make_experience(r1, 'u2', minutes=3)
    assert own_profile(client, 'u1')['num_shared_experiences'] == 3
    assert own_profile(client, 'u2')['num_shared_experiences'] == 1
    assert own_profile(client, 'u3')['num_shared_experiences'] == 0


def test_el_flux_http_actualitza_el_comptador(client, world):
    from apps.experiences.tests.helpers import EXPERIENCES, api_post, new_body, exp_url
    created = api_post(client, EXPERIENCES, user_claims('u1'), new_body(world[0]))
    assert created.status_code == 201
    assert own_profile(client, 'u1')['num_shared_experiences'] == 1
    api_post(client, EXPERIENCES, user_claims('u1'), new_body(world[1]))
    assert own_profile(client, 'u1')['num_shared_experiences'] == 2
    assert api_delete(client, exp_url(created.json()['experience']['id']), user_claims('u1')).status_code == 200
    assert own_profile(client, 'u1')['num_shared_experiences'] == 1


def test_el_comptador_i_el_de_reformes_conviuen(client, world):
    make_experience(world[0], 'u1')
    make_renovation(world[1], 'u1')
    profile = own_profile(client, 'u1')
    assert (profile['num_shared_experiences'], profile['num_renovated_refuges']) == (1, 1)


def test_no_es_demana_res_a_firestore(client, world, legacy_counts):
    make_experience(world[0], 'u1')
    assert own_profile(client, 'u1')['num_shared_experiences'] == 1
    legacy_counts.assert_not_called()                          # ni per a experiències ni per a reformes


def test_el_perfil_propi_no_depen_de_firestore_ni_si_cau(client, world, legacy_counts):
    legacy_counts.side_effect = RuntimeError('firestore caigut')
    make_experience(world[0], 'u1')
    assert own_profile(client, 'u1')['num_shared_experiences'] == 1


def test_el_comptador_d_experiencies_es_independent_del_que_diu_un_altre_usuari(client, world):
    make_experience(world[0], 'u2')
    assert own_profile(client, 'u1')['num_shared_experiences'] == 0


def test_uploaded_photos_keys_inclou_els_mitjans_d_experiencia_propis(client, world):
    from apps.accounts.tests.helpers import make_media
    from apps.experiences.tests.helpers import make_exp_media
    r = world[0]
    e = make_experience(r, 'u1')
    make_media(r, 'u1', key='k/foto.webp', minutes=1)
    make_exp_media(r, 'u1', e, key='k/exp.webp', minutes=2)
    make_exp_media(r, 'u2', e, key='k/altre.webp', minutes=3)                 # d'un altre usuari: no surt
    assert own_profile(client, 'u1')['uploaded_photos_keys'] == ['k/foto.webp', 'k/exp.webp']


def test_perfil_alie_no_te_comptadors(client, world):
    make_experience(world[0], 'u2')
    resp = api_get(client, url('u2'), user_claims('u1'))
    assert resp.status_code == 200 and set(resp.json()) == {'uid', 'username', 'avatar_metadata'}


def test_selector_get_legacy_counts_directe(world):
    from apps.accounts import selectors
    from apps.core.rls import rls_context
    make_experience(world[0], 'u1')
    make_experience(world[1], 'u1', minutes=1)
    with rls_context(uid='u1'):
        counts = selectors.get_legacy_counts('u1')
    assert counts == {'num_shared_experiences': 2, 'num_renovated_refuges': 0}


def test_el_pressupost_de_consultes_del_perfil_no_creix_amb_les_experiencies(client, world):
    """Mateix nombre de consultes amb 0 i amb 25 experiències (cap N+1 ni consulta de més per tenir-ne)."""
    sizes = []
    for n in (0, 25):
        for i in range(n):
            make_experience(world[i % 3], 'u1', minutes=i)
        with QueryCounter() as q:
            resp = api_get(client, url('u1'), user_claims('u1'))
        assert resp.status_code == 200 and resp.json()['num_shared_experiences'] == n
        sizes.append(q.count)
    assert sizes[0] == sizes[1] <= 3, (sizes, q.queries)


def test_el_comptador_no_afegeix_cap_consulta_respecte_d_un_perfil_sense_comptador_d_experiencies(client, world):
    """Només hi ha una consulta que mira `activity.experiences` i és la mateixa que ja calculava els comptadors
    (no una `SELECT count(*)` addicional per al comptador d'experiències)."""
    make_experience(world[0], 'u1')
    with QueryCounter() as q:
        own_profile(client, 'u1')
    exp_queries = [s for s in q.queries if 'experiences' in s]
    assert len(exp_queries) <= 1, exp_queries


# =============================================== esborrat d'usuari ===============================================

def test_delete_esborra_les_experiencies_pel_cascade_i_conserva_les_dels_altres(client, world):
    make_experience(world[0], 'u1')
    make_experience(world[1], 'u1', minutes=1)
    other = make_experience(world[0], 'u2', minutes=2)
    assert api_delete(client, url('u1'), user_claims('u1')).status_code == 204
    assert exp_ids() == [other]
    assert own_profile(client, 'u2')['num_shared_experiences'] == 1
    assert sql("SELECT count(*) FROM users.users WHERE uid = 'u1'") == [(0,)]
