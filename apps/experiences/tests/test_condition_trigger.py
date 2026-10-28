"""
Mitjana de la condició del refugi per *trigger* (§2.9; `docs/deep-dives/condition-average.md`), amb el rol `app`.

Regles (`activity.fn_experience_condition()`, `SECURITY DEFINER`, bloqueja la fila del refugi `FOR UPDATE`):
- INSERT amb valor `v`: `c = (coalesce(c, 0)·n + v) / (n + 1)`, `n = n + 1`; `condition_counted_at = now()`.
- UPDATE de `condition` `v -> v'` (valor diferent): `c = clamp(c + (v' - v) / n, 0, 3)`, `n` igual.
- UPDATE d'un valor «antic» (`condition_counted_at < refuges.condition_reset_at`) o amb `n = 0`: compta com a vot nou
  (`c = (c·n + v') / (n + 1)`, `n + 1`, `condition_counted_at = now()`).
- UPDATE sense canvi de valor (o d'una altra columna): cap efecte.
- Esborrar l'experiència o el compte: no toca el refugi (el valor no és dada personal).
- Un usuari normal (`app`) no pot fer `UPDATE refuges`; només el trigger (propietari `migrator`) ho fa.
"""
import pytest
from django.db import DatabaseError, connection, transaction

from apps.core.rls import rls_context, system_context
from apps.experiences.tests.helpers import (
    exp_ids, exp_row, make_experience, make_refuge, make_user, refuge_state, set_counted_at, set_refuge_state, sql, utc)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.integration, pytest.mark.models,
              pytest.mark.real_permissions]


@pytest.fixture
def world():
    for uid in ('u1', 'u2', 'u3', 'adm'):
        make_user(uid)
    return make_refuge(name='A'), make_refuge(name='B', lat=43.0)


def update_as(ctx, experience_id, **assignments):
    """`UPDATE activity.experiences SET … WHERE id = …` amb el context de RLS indicat; retorna les files afectades."""
    sets = ', '.join(f'{k} = %s' for k in assignments)
    with rls_context(**ctx):
        with connection.cursor() as cur:
            cur.execute(f'UPDATE activity.experiences SET {sets} WHERE id = %s', [*assignments.values(), experience_id])
            return cur.rowcount


def insert_as(ctx, refuge, creator_uid, condition):
    with rls_context(**ctx):
        with connection.cursor() as cur:
            cur.execute('INSERT INTO activity.experiences (refuge_id, creator_uid, comment, condition) '
                        "VALUES (%s, %s, 'c', %s) RETURNING id", [refuge.pk, creator_uid, condition])
            return str(cur.fetchone()[0])


def assert_state(refuge, c, n):
    got_c, got_n, _ = refuge_state(refuge)
    assert got_n == n
    assert (got_c is None) if c is None else (got_c == pytest.approx(c)), (got_c, got_n)


# =================================== INSERT (POST) ===================================

@pytest.mark.parametrize('v', [0, 1, 2, 3])
def test_primer_vot_sense_condicio_previa_la_fixa(world, v):
    r, _ = world
    assert_state(r, None, 0)
    make_experience(r, 'u1', condition=v)
    assert_state(r, v, 1)


@pytest.mark.parametrize('seed', [0.0, 1.5, 3.0])
def test_condicio_llavor_amb_n_zero_es_ignora(world, seed):
    """§2.9: «el mateix passa amb una `c` llavor i `n = 0`»: el primer vot l'substitueix (la càrrega inicial)."""
    r, _ = world
    set_refuge_state(r, seed, 0)
    make_experience(r, 'u1', condition=1)
    assert_state(r, 1, 1)


def test_mitjana_incremental_de_diversos_vots(world):
    r, _ = world
    for uid, v, expected in (('u1', 3, (3, 1)), ('u2', 1, (2, 2)), ('u3', 2, (2, 3)), ('u1', 0, (1.5, 4))):
        make_experience(r, uid, condition=v)
        assert_state(r, *expected)


def test_la_formula_usa_c_per_n_mes_v_dividit_per_n_mes_1(world):
    r, _ = world
    set_refuge_state(r, 2.4, 5)
    make_experience(r, 'u1', condition=3)
    assert_state(r, (2.4 * 5 + 3) / 6, 6)


def test_el_vot_no_toca_altres_refugis_ni_altres_columnes(world):
    ra, rb = world
    before = sql('SELECT name, altitude, places, type, description FROM refuges.refuges WHERE id = %s', [ra.pk])
    make_experience(ra, 'u1', condition=3)
    assert_state(rb, None, 0)
    assert sql('SELECT name, altitude, places, type, description FROM refuges.refuges WHERE id = %s',
               [ra.pk]) == before
    assert refuge_state(ra)[2] is None                        # un vot no toca `condition_reset_at`


def test_un_usuari_normal_vota_amb_el_trigger_pero_no_pot_modificar_el_refugi(world):
    r, _ = world
    eid = insert_as({'uid': 'u1'}, r, 'u1', 3)
    assert_state(r, 3, 1)
    assert exp_row(eid)['condition'] == 3
    # Des del chunk 8 `app` té el grant d'UPDATE sobre `refuges` (l'aprovació de propostes), però la política només
    # el deixa a admin/sistema: per a un usuari corrent l'UPDATE afecta 0 files (abans fallava per falta de grant).
    with transaction.atomic(), rls_context(uid='u1'), connection.cursor() as cur:
        cur.execute('UPDATE refuges.refuges SET condition = 0, num_contributed_conditions = 9 WHERE id = %s',
                    [r.pk])
        assert cur.rowcount == 0
    assert_state(r, 3, 1)


def test_un_insert_denegat_per_la_rls_no_deixa_cap_vot(world):
    """El trigger es dispara abans del `WITH CHECK`, però tota la sentència es desfà: la mitjana no es mou."""
    r, _ = world
    with pytest.raises(DatabaseError):
        with transaction.atomic():
            insert_as({'uid': 'u2'}, r, 'u1', 3)               # u2 no pot crear experiències en nom d'u1
    assert exp_ids() == []
    assert_state(r, None, 0)


def test_un_insert_amb_condicio_fora_de_rang_no_deixa_cap_vot(world):
    r, _ = world
    make_experience(r, 'u2', condition=1)                      # la taula ha d'existir: si no, el test passaria per error
    with pytest.raises(DatabaseError):
        with transaction.atomic():
            insert_as({'uid': 'u1'}, r, 'u1', 7)
    assert_state(r, 1, 1)


def test_condition_counted_at_es_el_now_de_l_insert(world):
    r, _ = world
    row = exp_row(make_experience(r, 'u1', condition=2))
    assert row['condition_counted_at'] == row['created_at'] or row['condition_counted_at'] >= row['created_at']


# =================================== UPDATE (PATCH) ===================================

def test_patch_de_v_a_v_prima_ajusta_la_mitjana_sense_canviar_n(world):
    r, _ = world
    make_experience(r, 'u1', condition=3)
    e2 = make_experience(r, 'u2', condition=1)
    assert_state(r, 2, 2)
    assert update_as({'uid': 'u2'}, e2, condition=3) == 1
    assert_state(r, 3, 2)                                      # 2 + (3 - 1) / 2
    update_as({'uid': 'u2'}, e2, condition=0)
    assert_state(r, 1.5, 2)                                    # 3 + (0 - 3) / 2


def test_patch_amb_un_sol_vot_fixa_el_valor_nou(world):
    r, _ = world
    e = make_experience(r, 'u1', condition=1)
    update_as({'uid': 'u1'}, e, condition=3)
    assert_state(r, 3, 1)


def test_patch_no_canvia_el_condition_counted_at_si_no_es_recompta(world):
    r, _ = world
    e = make_experience(r, 'u1', condition=1)
    before = exp_row(e)['condition_counted_at']
    update_as({'uid': 'u1'}, e, condition=2)
    assert exp_row(e)['condition_counted_at'] == before


@pytest.mark.parametrize('v', [0, 1, 2, 3])
def test_patch_amb_el_mateix_valor_no_te_cap_efecte(world, v):
    r, _ = world
    make_experience(r, 'u2', condition=2)
    e = make_experience(r, 'u1', condition=v)
    snapshot = (refuge_state(r), exp_row(e)['condition_counted_at'])
    assert update_as({'uid': 'u1'}, e, condition=v) == 1
    assert (refuge_state(r), exp_row(e)['condition_counted_at']) == snapshot


def test_patch_nomes_del_comentari_no_toca_la_mitjana(world):
    r, _ = world
    e = make_experience(r, 'u1', condition=3)
    snapshot = refuge_state(r)
    update_as({'uid': 'u1'}, e, comment='nou comentari')
    assert refuge_state(r) == snapshot and exp_row(e)['comment'] == 'nou comentari'


def test_la_mitjana_es_retalla_a_0_i_3(world):
    r, _ = world
    e = make_experience(r, 'u1', condition=3)
    set_refuge_state(r, 0.2, 1)                                # mitjana incoherent (p. ex. aprovació de proposta)
    update_as({'uid': 'u1'}, e, condition=0)                   # 0.2 + (0 - 3) = -2.8 -> 0
    assert_state(r, 0, 1)
    set_refuge_state(r, 2.9, 1)
    update_as({'uid': 'u1'}, e, condition=3)                   # 2.9 + 3 = 5.9 -> 3
    assert_state(r, 3, 1)


def test_patch_d_un_altre_usuari_no_afecta_ni_la_fila_ni_la_mitjana(world):
    r, _ = world
    e = make_experience(r, 'u1', condition=1)
    snapshot = refuge_state(r)
    assert update_as({'uid': 'u2'}, e, condition=3) == 0       # la RLS l'amaga
    assert refuge_state(r) == snapshot and exp_row(e)['condition'] == 1


def test_l_admin_pot_canviar_la_condicio_d_un_altre_i_la_mitjana_s_ajusta(world):
    r, _ = world
    e = make_experience(r, 'u1', condition=1)
    assert update_as({'uid': 'adm', 'is_admin': True}, e, condition=3) == 1
    assert_state(r, 3, 1)


# =================================== reset i vot antic ===================================

def old_vote_setup(world):
    """Experiència d'`u1` (valor 2) comptada el 2025-01-01 i refugi resetejat el 2025-06-01 amb `c = 2.5`, `n = 1`."""
    r, _ = world
    e = make_experience(r, 'u1', condition=2)
    set_counted_at(e, utc(2025, 1, 1))
    set_refuge_state(r, 2.5, 1, utc(2025, 6, 1))
    return r, e


def test_patch_d_un_valor_anterior_al_reset_compta_com_a_vot_nou(world):
    r, e = old_vote_setup(world)
    update_as({'uid': 'u1'}, e, condition=3)
    assert_state(r, (2.5 * 1 + 3) / 2, 2)                      # 2.75, n + 1
    assert exp_row(e)['condition_counted_at'] > utc(2025, 6, 1)    # ara ja no es «antic»


def test_el_segon_patch_despres_del_reset_ja_no_recompta(world):
    r, e = old_vote_setup(world)
    update_as({'uid': 'u1'}, e, condition=3)
    update_as({'uid': 'u1'}, e, condition=1)
    assert_state(r, 2.75 + (1 - 3) / 2, 2)                     # 1.75, n igual (D2: no es recompta a cada PATCH)


def test_patch_sense_canvi_de_valor_despres_del_reset_no_compta(world):
    r, e = old_vote_setup(world)
    snapshot = refuge_state(r)
    update_as({'uid': 'u1'}, e, condition=2, comment='nomes comentari')
    assert refuge_state(r) == snapshot


def test_instant_igual_al_del_reset_no_es_antic(world):
    """La comparació és estricta: `condition_counted_at < condition_reset_at`."""
    r, _ = world
    e = make_experience(r, 'u1', condition=2)
    set_counted_at(e, utc(2025, 6, 1))
    set_refuge_state(r, 2.0, 1, utc(2025, 6, 1))
    update_as({'uid': 'u1'}, e, condition=0)
    assert_state(r, 0, 1)                                      # 2 + (0 - 2) / 1, n igual


def test_sense_reset_cap_valor_es_antic(world):
    r, _ = world
    e = make_experience(r, 'u1', condition=2)
    set_counted_at(e, utc(2000, 1, 1))
    update_as({'uid': 'u1'}, e, condition=3)
    assert_state(r, 3, 1)


def test_un_vot_posterior_al_reset_no_es_antic(world):
    r, _ = world
    set_refuge_state(r, 2.0, 1, utc(2025, 6, 1))
    e = make_experience(r, 'u1', condition=2)                  # comptat ara (> reset)
    assert_state(r, 2.0, 2)
    update_as({'uid': 'u1'}, e, condition=0)
    assert_state(r, 2.0 + (0 - 2) / 2, 2)


def test_amb_n_zero_el_patch_compta_com_a_vot_nou(world):
    """`n = 0` amb una experiència existent (p. ex. proposta aprovada sense `n`): evita dividir per zero."""
    r, _ = world
    e = make_experience(r, 'u1', condition=2)
    set_refuge_state(r, 1.0, 0)
    update_as({'uid': 'u1'}, e, condition=3)
    assert_state(r, 3, 1)


def test_proposta_aprovada_deixa_c_i_n_1_i_les_experiencies_antigues_recomptes(world):
    """Simula `c = valor, n = 1, condition_reset_at = now()` (codi d'aprovació) i dues experiències antigues."""
    r, _ = world
    e1, e2 = make_experience(r, 'u1', condition=3), make_experience(r, 'u2', condition=1)
    for e in (e1, e2):
        set_counted_at(e, utc(2025, 1, 1))
    set_refuge_state(r, 2.0, 1, utc(2025, 6, 1))
    update_as({'uid': 'u1'}, e1, condition=2)                  # vot nou: (2·1 + 2) / 2
    assert_state(r, 2.0, 2)
    update_as({'uid': 'u2'}, e2, condition=3)                  # vot nou: (2·2 + 3) / 3
    assert_state(r, 7 / 3, 3)


# =================================== esborrats ===================================

def test_esborrar_una_experiencia_no_toca_la_mitjana(world):
    r, _ = world
    make_experience(r, 'u1', condition=3)
    e2 = make_experience(r, 'u2', condition=0)
    snapshot = refuge_state(r)
    with rls_context(uid='u2'), connection.cursor() as cur:
        cur.execute('DELETE FROM activity.experiences WHERE id = %s', [e2])
        assert cur.rowcount == 1
    assert refuge_state(r) == snapshot == refuge_state(r)
    assert_state(r, 1.5, 2)


def test_esborrar_el_compte_no_toca_la_mitjana(world):
    r, _ = world
    make_experience(r, 'u1', condition=3)
    make_experience(r, 'u2', condition=0)
    sql("DELETE FROM users.users WHERE uid = 'u1'")
    assert exp_ids(r) and len(exp_ids(r)) == 1
    assert_state(r, 1.5, 2)


def test_esborrar_totes_les_experiencies_deixa_la_mitjana_i_n(world):
    r, _ = world
    make_experience(r, 'u1', condition=2)
    sql('DELETE FROM activity.experiences')
    assert_state(r, 2, 1)
