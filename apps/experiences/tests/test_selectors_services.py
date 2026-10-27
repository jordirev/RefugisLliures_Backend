"""
`apps.experiences.selectors` i `apps.experiences.services` (chunk 7; substitueixen `ExperienceDAO`/`ExperienceController`).

Contracte (HackSoft, igual que `apps.doubts`):
- `selectors.parse_id(value) -> UUID | None`.
- `selectors.get_experience(experience_id) -> Experience | None` (1 consulta; `None` si no existeix o no és UUID).
- `selectors.list_experiences(refuge_id, viewer_uid=None, is_admin=False) -> [Experience]` per `(modified_at, id)`
  descendent, amb `experience.media_list` = mitjans visibles per a qui mira (`status = 'visible'` o autor o admin) per
  `(uploaded_at, key)`; 2 consultes amb qualsevol nombre de files. Refugi inexistent o no UUID: llista buida.
- `services.create_experience(*, refuge_id, creator_uid, comment, condition) -> Experience`; `RefugeNotFound`.
- `services.update_experience(*, experience_id, actor_uid, is_admin=False, comment=None, condition=None) -> Experience`;
  `ExperienceNotFound`, `NotOwner`. Sempre actualitza `modified_at`.
- `services.delete_experience(*, experience_id, actor_uid, is_admin=False, media_service=None) -> None`;
  `ExperienceNotFound`, `NotOwner`, `MediaStorageError` (R2 no ha esborrat un fitxer: es desfà l'esborrat, com
  `apps.refuges.services.delete_media`).
La propietat es comprova al service (a més de la RLS); les cascades són de la BD.
"""
import uuid

import pytest

from apps.core.rls import rls_context
from apps.experiences.tests.helpers import (
    ZERO_UUID, deleted_keys, exp_ids, exp_row, fail_r2, make_exp_media, make_experience, make_media, media_keys_of,
    refuge_state, set_counted_at, set_refuge_state, sql, utc)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.integration, pytest.mark.real_permissions]


# =================================== selectors ===================================

@pytest.mark.parametrize('value', ['x', '', None, 'a' * 100, 'a\x00b', 12, '0190aaaa-bbbb'])
def test_parse_id_invalid(selectors, value):
    assert selectors.parse_id(value) is None


def test_parse_id_valid(selectors):
    u = uuid.uuid4()
    assert selectors.parse_id(str(u)) == u and selectors.parse_id(u) == u


def test_get_experience(selectors, world):
    e = make_experience(world[0], 'u1')
    with rls_context(uid='u2'):
        got = selectors.get_experience(e)
        assert got is not None and str(got.pk) == e and got.creator_id == 'u1'
        assert selectors.get_experience(ZERO_UUID) is None and selectors.get_experience('no-uuid') is None


def test_list_experiences_ordre_i_filtre_per_refugi(selectors, world):
    r1, r2 = world
    a, b, c = (make_experience(r1, 'u1', minutes=1), make_experience(r1, 'u2', minutes=3),
               make_experience(r1, 'u3', minutes=2))
    make_experience(r2, 'u1', minutes=9)
    with rls_context(uid='u1'):
        assert [str(e.pk) for e in selectors.list_experiences(r1.pk, 'u1')] == [b, c, a]
        assert selectors.list_experiences('no-uuid', 'u1') == [] and selectors.list_experiences(ZERO_UUID, 'u1') == []


def test_list_experiences_carrega_els_mitjans_visibles_per_a_qui_mira(selectors, world):
    r = world[0]
    e = make_experience(r, 'u1')
    make_exp_media(r, 'u1', e, key='k/v.webp', minutes=1)
    make_exp_media(r, 'u1', e, key='k/h.webp', status='hidden_pending_review', minutes=2)
    make_media(r, 'u1', key='k/foto.webp', minutes=3)
    for viewer, admin, expected in (('u2', False, ['k/v.webp']), ('u1', False, ['k/v.webp', 'k/h.webp']),
                                    ('adm', True, ['k/v.webp', 'k/h.webp']), (None, False, ['k/v.webp'])):
        with rls_context(uid=viewer or '', is_admin=admin):
            got = selectors.list_experiences(r.pk, viewer, admin)
            assert [m.key for m in got[0].media_list] == expected, (viewer, admin)


# =================================== services: create ===================================

def test_create_experience_desa_i_vota(services, world):
    r = world[0]
    with rls_context(uid='u1'):
        e = services.create_experience(refuge_id=r.pk, creator_uid='u1', comment='Bon refugi', condition=3)
    assert str(e.pk) in exp_ids(r) and e.creator_id == 'u1' and e.condition == 3
    assert refuge_state(r)[:2] == (pytest.approx(3.0), 1)


def test_create_experience_accepta_el_refuge_id_com_a_text(services, world):
    with rls_context(uid='u1'):
        e = services.create_experience(refuge_id=str(world[0].pk), creator_uid='u1', comment='x', condition=0)
    assert exp_row(str(e.pk))['condition'] == 0


@pytest.mark.parametrize('rid', [ZERO_UUID, 'no-uuid', 'refugi_colomers'])
def test_create_refugi_inexistent(services, world, rid):
    with rls_context(uid='u1'), pytest.raises(services.RefugeNotFound):
        services.create_experience(refuge_id=rid, creator_uid='u1', comment='x', condition=1)
    assert exp_ids() == []


def test_create_a_un_refugi_esborrat_alhora_es_not_found_i_no_deixa_fila(services, world):
    """FK diferida: el refugi desapareix entre la lectura i l'`INSERT` -> `RefugeNotFound`, no un 500 al COMMIT."""
    from unittest.mock import patch
    from apps.experiences.tests.helpers import as_owner
    refuge = world[0]
    with patch('apps.experiences.services.refuge_selectors.refuge_exists', return_value=True):
        with as_owner():
            sql('DELETE FROM refuges.refuges WHERE id = %s', [refuge.pk])
        with rls_context(uid='u1'), pytest.raises(services.RefugeNotFound):
            services.create_experience(refuge_id=refuge.pk, creator_uid='u1', comment='x', condition=1)
    assert exp_ids() == []


def test_create_no_pot_crear_en_nom_d_un_altre(services, world):
    from django.db import DatabaseError
    with rls_context(uid='u2'), pytest.raises(DatabaseError):
        services.create_experience(refuge_id=world[0].pk, creator_uid='u1', comment='x', condition=1)
    assert exp_ids() == []


# =================================== services: update ===================================

def test_update_comentari_i_condicio(services, world):
    r = world[0]
    e = make_experience(r, 'u1', comment='antic', condition=1)
    before = exp_row(e)['modified_at']
    with rls_context(uid='u1'):
        got = services.update_experience(experience_id=e, actor_uid='u1', comment='nou', condition=3)
    assert (got.comment, got.condition) == ('nou', 3)
    row = exp_row(e)
    assert (row['comment'], row['condition']) == ('nou', 3) and row['modified_at'] > before
    assert refuge_state(r)[:2] == (pytest.approx(3.0), 1)


def test_update_sense_camps_nomes_toca_modified_at(services, world):
    e = make_experience(world[0], 'u1', comment='igual', condition=2)
    before = exp_row(e)
    with rls_context(uid='u1'):
        services.update_experience(experience_id=e, actor_uid='u1')
    row = exp_row(e)
    assert (row['comment'], row['condition']) == ('igual', 2) and row['modified_at'] > before['modified_at']
    assert refuge_state(world[0])[:2] == (pytest.approx(2.0), 1)


def test_update_condicio_zero_no_es_confon_amb_absent(services, world):
    """`condition=0` és un valor vàlid; només `None` vol dir «no tocar»."""
    e = make_experience(world[0], 'u1', condition=3)
    with rls_context(uid='u1'):
        services.update_experience(experience_id=e, actor_uid='u1', condition=0)
    assert exp_row(e)['condition'] == 0 and refuge_state(world[0])[0] == pytest.approx(0.0)


def test_update_despres_del_reset_compta_com_a_vot_nou(services, world):
    r = world[0]
    e = make_experience(r, 'u1', condition=2)
    set_counted_at(e, utc(2025, 1, 1))
    set_refuge_state(r, 2.5, 1, utc(2025, 6, 1))
    with rls_context(uid='u1'):
        services.update_experience(experience_id=e, actor_uid='u1', condition=3)
    assert refuge_state(r)[:2] == (pytest.approx(2.75), 2)


@pytest.mark.parametrize('xid', [ZERO_UUID, 'no-uuid'])
def test_update_experiencia_inexistent(services, world, xid):
    with rls_context(uid='u1'), pytest.raises(services.ExperienceNotFound):
        services.update_experience(experience_id=xid, actor_uid='u1', comment='x')


def test_update_not_owner_i_admin(services, world):
    e = make_experience(world[0], 'u1', comment='meu')
    with rls_context(uid='u2'), pytest.raises(services.NotOwner):
        services.update_experience(experience_id=e, actor_uid='u2', comment='x')
    assert exp_row(e)['comment'] == 'meu'
    with rls_context(uid='adm', is_admin=True):
        services.update_experience(experience_id=e, actor_uid='adm', is_admin=True, comment='moderat')
    assert exp_row(e)['comment'] == 'moderat'


def test_update_sense_actor_no_es_admin(services, world):
    e = make_experience(world[0], 'u1')
    with rls_context(uid='u1'), pytest.raises(services.NotOwner):
        services.update_experience(experience_id=e, actor_uid=None, comment='x')


# =================================== services: delete ===================================

def test_delete_esborra_files_i_demana_a_r2_claus_i_miniatures(services, world, r2):
    r = world[0]
    e = make_experience(r, 'u1')
    make_exp_media(r, 'u1', e, key='k/a.webp', thumb_key='k/a_t.webp', minutes=1)
    make_exp_media(r, 'adm', e, key='k/b.webp', minutes=2)                      # pujat per l'admin: també és de l'experiència
    make_media(r, 'u1', key='k/foto.webp', minutes=3)
    with rls_context(uid='u1'):
        services.delete_experience(experience_id=e, actor_uid='u1')
    assert exp_ids() == [] and media_keys_of(e) == []
    assert sorted(deleted_keys(r2)) == ['k/a.webp', 'k/a_t.webp', 'k/b.webp']
    assert sql('SELECT key FROM refuges.refuge_media') == [('k/foto.webp',)]


def test_delete_no_toca_la_mitjana(services, world):
    e = make_experience(world[0], 'u1', condition=3)
    state = refuge_state(world[0])
    with rls_context(uid='u1'):
        services.delete_experience(experience_id=e, actor_uid='u1')
    assert refuge_state(world[0]) == state


def test_delete_r2_cau_i_es_desfa_tot(services, world, r2):
    e = make_experience(world[0], 'u1')
    make_exp_media(world[0], 'u1', e, key='k/a.webp')
    fail_r2(r2)
    with rls_context(uid='u1'):
        with pytest.raises(services.MediaStorageError):
            services.delete_experience(experience_id=e, actor_uid='u1')
        assert exp_ids() == [e] and media_keys_of(e) == ['k/a.webp']


@pytest.mark.parametrize('xid', [ZERO_UUID, 'no-uuid'])
def test_delete_experiencia_inexistent(services, world, xid):
    with rls_context(uid='u1'), pytest.raises(services.ExperienceNotFound):
        services.delete_experience(experience_id=xid, actor_uid='u1')


def test_delete_not_owner_no_toca_r2_ni_la_fila(services, world, r2):
    e = make_experience(world[0], 'u1')
    make_exp_media(world[0], 'u1', e, key='k/a.webp')
    with rls_context(uid='u2'), pytest.raises(services.NotOwner):
        services.delete_experience(experience_id=e, actor_uid='u2')
    assert exp_ids() == [e] and deleted_keys(r2) == []


def test_delete_admin(services, world):
    e = make_experience(world[0], 'u1')
    with rls_context(uid='adm', is_admin=True):
        services.delete_experience(experience_id=e, actor_uid='adm', is_admin=True)
    assert exp_ids() == []


def test_delete_concurrent_ja_esborrada_es_not_found(services, selectors, world):
    from unittest.mock import patch
    e = make_experience(world[0], 'u1')
    with rls_context(uid='u1'):
        stale = selectors.get_experience(e)
        sql('DELETE FROM activity.experiences WHERE id = %s', [e])
        with patch.object(selectors, 'get_experience', return_value=stale), \
                pytest.raises(services.ExperienceNotFound):
            services.delete_experience(experience_id=e, actor_uid='u1')
