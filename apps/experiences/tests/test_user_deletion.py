"""
Esborrat d'usuari i experiències (chunk 7; §8.4, §8.5, D21/D22).

- El pas «experiències» de `apps.accounts.services._firestore_steps` desapareix: ho fan les FK
  `experiences.creator_uid -> users.users ON DELETE CASCADE` i `refuge_media.experience_id -> experiences ON DELETE CASCADE`.
- L'esborrat **no toca** la mitjana del refugi (el valor no és dada personal, §2.9).
- RGPD (D22): abans del `DELETE` s'esborren a R2 els fitxers (clau i miniatura) dels mitjans de l'usuari **i** dels mitjans
  de les seves experiències encara que els hagi pujat un altre (p. ex. un admin): les files cauen per cascada i, sense
  aquest pas, els fitxers quedarien orfes fins al worker de la cua d'R2 (chunk 9).
- Si Firebase falla, es desfà tot (experiències incloses) i l'usuari pot reintentar.
- Cap crida a Firestore per a experiències (`ExperienceController` ja no existeix o no es toca).
"""
from unittest.mock import patch

import pytest

from apps.experiences.tests.helpers import (
    admin_claims, all_media_keys, api_delete, api_get, deleted_keys, exp_ids, make_exp_media, make_experience,
    make_media, refuge_state, sql, user_claims)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration,
              pytest.mark.real_permissions]


@pytest.fixture
def no_firestore_steps():
    with patch('apps.accounts.services._firestore_steps', return_value=[]):
        yield


def test_el_pas_d_experiencies_ja_no_es_a_l_esborrat_provisional(world):
    from apps.accounts import services
    names = [name for name, _ in services._firestore_steps('u1')]
    assert 'experiències' not in names


def test_el_controller_de_firestore_d_experiencies_ja_no_existeix():
    with pytest.raises(ImportError):
        from api.controllers import experience_controller  # noqa: F401


def test_delete_user_cascadeja_experiencies_i_mitjans_i_respecta_les_dels_altres(client, world, no_firestore_steps):
    r1, r2 = world
    e1, e2 = make_experience(r1, 'u1'), make_experience(r2, 'u1', minutes=1)
    other = make_experience(r1, 'u2', minutes=2)
    make_exp_media(r1, 'u1', e1, key='k/e1.webp')
    make_exp_media(r2, 'u1', e2, key='k/e2.webp')
    make_exp_media(r1, 'u2', other, key='k/other.webp')
    make_media(r1, 'u1', key='k/foto-u1.webp', minutes=5)
    resp = api_delete(client, '/api/users/u1/', user_claims('u1'))
    assert resp.status_code == 204, resp.content
    assert exp_ids() == [other]
    assert all_media_keys() == ['k/other.webp']


def test_delete_user_no_toca_la_mitjana_del_refugi(client, world, no_firestore_steps):
    r = world[0]
    make_experience(r, 'u1', condition=3)
    make_experience(r, 'u2', condition=0)
    state = refuge_state(r)
    assert api_delete(client, '/api/users/u1/', user_claims('u1')).status_code == 204
    assert refuge_state(r) == state and state[1] == 2


def test_delete_user_esborra_a_r2_claus_i_miniatures_dels_seus_mitjans(client, world, r2, no_firestore_steps):
    r = world[0]
    e = make_experience(r, 'u1')
    make_exp_media(r, 'u1', e, key='k/e.webp', thumb_key='k/e_t.webp')
    make_media(r, 'u1', key='k/foto.webp', thumb_key='k/foto_t.webp', minutes=3)
    other = make_experience(r, 'u2', minutes=4)
    make_exp_media(r, 'u2', other, key='k/other.webp', minutes=5)
    assert api_delete(client, '/api/users/u1/', user_claims('u1')).status_code == 204
    assert sorted(deleted_keys(r2)) == ['k/e.webp', 'k/e_t.webp', 'k/foto.webp', 'k/foto_t.webp']


def test_delete_user_esborra_a_r2_els_mitjans_d_admin_a_les_seves_experiencies(client, world, r2, no_firestore_steps):
    """Fitxers pujats per un altre (admin) a l'experiència d'`u1`: la fila cau per cascada, el fitxer no ha de quedar orfe."""
    r = world[0]
    e = make_experience(r, 'u1')
    make_exp_media(r, 'adm', e, key='k/adm-photo.webp', thumb_key='k/adm-photo_t.webp')
    assert api_delete(client, '/api/users/u1/', user_claims('u1')).status_code == 204
    assert all_media_keys() == []
    assert sorted(deleted_keys(r2)) == ['k/adm-photo.webp', 'k/adm-photo_t.webp']


def test_delete_user_r2_caigut_es_500_i_es_conserva_tot(client, world, r2, no_firestore_steps):
    r = world[0]
    e = make_experience(r, 'u1')
    make_exp_media(r, 'u1', e, key='k/e.webp')
    r2.delete_files.side_effect = lambda keys: {'deleted': [], 'failed': list(keys)}
    r2.delete_file.return_value = False
    resp = api_delete(client, '/api/users/u1/', user_claims('u1'))
    assert resp.status_code == 500 and exp_ids() == [e] and all_media_keys() == ['k/e.webp']


def test_delete_user_es_desfa_si_firebase_falla(client, world, no_firestore_steps, firebase_accounts):
    r = world[0]
    e = make_experience(r, 'u1')
    make_exp_media(r, 'u1', e, key='k/e.webp')
    firebase_accounts.delete_user.side_effect = RuntimeError('firebase caigut')
    resp = api_delete(client, '/api/users/u1/', user_claims('u1'))
    assert resp.status_code == 500 and set(resp.json()) == {'error', 'error_id'}
    assert exp_ids() == [e] and all_media_keys() == ['k/e.webp']


def test_delete_user_sense_experiencies_204(client, world, no_firestore_steps):
    assert api_delete(client, '/api/users/u3/', user_claims('u3')).status_code == 204


def test_delete_user_cap_orfe_a_la_bd(client, world, no_firestore_steps):
    r = world[0]
    for uid in ('u1', 'u2'):
        e = make_experience(r, uid)
        make_exp_media(r, uid, e, key=f'k/{uid}.webp')
    api_delete(client, '/api/users/u1/', user_claims('u1'))
    assert sql("SELECT count(*) FROM activity.experiences e WHERE NOT EXISTS "
               "(SELECT 1 FROM users.users u WHERE u.uid = e.creator_uid)") == [(0,)]
    assert sql("SELECT count(*) FROM refuges.refuge_media m WHERE m.experience_id IS NOT NULL AND NOT EXISTS "
               "(SELECT 1 FROM activity.experiences e WHERE e.id = m.experience_id)") == [(0,)]


def test_delete_refugi_cascadeja_experiencies_i_mitjans(world):
    from apps.experiences.tests.helpers import as_owner
    r1, r2_ = world
    e1, e2 = make_experience(r1, 'u1'), make_experience(r2_, 'u2')
    make_exp_media(r1, 'u1', e1, key='k/a.webp')
    make_exp_media(r2_, 'u2', e2, key='k/b.webp')
    with as_owner():
        sql('DELETE FROM refuges.refuges WHERE id = %s', [r1.pk])
    assert exp_ids() == [e2] and all_media_keys() == ['k/b.webp']
