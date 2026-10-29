"""
Selectors i services de `apps/visits` (chunk 4). Substitueixen `RefugeVisitController`/`RefugeVisitDAO` de Firestore.

Contracte (`apps/visits/selectors.py`):
- `VisitSummary`: objecte lleuger (dataclass/NamedTuple) amb els atributs `date` (`datetime.date`), `refuge_id` (`UUID`),
  `total_visitors` (`int`, de la vista `refuge_visit_totals`, 0 si no hi ha participants), `is_visitor` (`bool`) i
  `num_visitors` (`int`, 0 si no hi participa) **respecte a l'usuari `uid`**. Mai porta participants d'altres.
- `list_refuge_visits(refuge_id: UUID, uid) -> list[VisitSummary]`: visites amb `visit_date >= get_madrid_today()` d'un
  refugi, ordenades per data ascendent (**1 consulta**). Les visites sense participants s'hi inclouen (total 0), com avui.
- `list_user_visits(uid) -> list[VisitSummary]`: totes les visites on participa `uid` (passades i futures), ordre
  `(date DESC, refuge_id)` (**1 consulta**; index `(user_uid) INCLUDE …`, B5).

Contracte (`apps/visits/services.py`; `visit_date` es un `datetime.date`; cap tupla, nomes excepcions de domini):
- excepcions: `RefugeNotFound` (refugi inexistent o id que no es UUID), `VisitNotFound`, `VisitDateInPast`,
  `AlreadyRegistered`, `NotRegistered`;
- `get_refuge_visits(uid, refuge_id) -> list[VisitSummary]` (llanca `RefugeNotFound`) i `get_user_visits(uid)`;
- `create_visit(uid, refuge_id, visit_date, num_visitors) -> VisitSummary`: `RefugeNotFound`, `VisitDateInPast`
  (`visit_date < get_madrid_today()`), `AlreadyRegistered`; la visita es crea amb `INSERT … ON CONFLICT DO NOTHING` (M4);
- `update_visit(uid, refuge_id, visit_date, num_visitors) -> VisitSummary`: `VisitNotFound` (visita o refugi
  inexistents, **sense** comprovar la data), `NotRegistered`;
- `remove_visitor(uid, refuge_id, visit_date) -> None`: `VisitNotFound`, `NotRegistered`; la visita es conserva
  i, si era l'últim participant, la visita s'esborra (trigger `participants_drop_empty_visit`, vegeu
  `test_empty_visit_trigger.py`);
- `process_yesterday_visits() -> dict` i `purge_old_visits() -> int`: vegeu `test_process_yesterday_visits.py`.
Les funcions s'executen dins el context de RLS de la peticio (`rls_context(uid=…)` als tests).
"""
import uuid
from datetime import timedelta

import pytest

from apps.core.rls import rls_context
from apps.visits.tests.helpers import (
    add_participant, day, make_refuge, make_user, make_visit, participant_rows, visit_dates, visit_rows,
    visit_selectors, visit_services)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.integration, pytest.mark.real_permissions]


@pytest.fixture
def S():
    return visit_services()


@pytest.fixture
def SEL():
    return visit_selectors()


def attrs(v):
    return (v.date, v.refuge_id, v.total_visitors, v.is_visitor, v.num_visitors)


@pytest.fixture
def scene():
    for u in ('u1', 'u2', 'u3'):
        make_user(u)
    return make_refuge(name='R1'), make_refuge(name='R2', lat=43)


# ---------- selectors ----------

def test_list_refuge_visits_nomes_actuals_i_futures_ordenades(SEL, scene):
    r1, r2 = scene
    make_visit(r1, day(-1), {'u1': 1})
    make_visit(r1, day(3), {'u1': 2, 'u2': 4})
    make_visit(r1, day(0), {'u2': 5})
    make_visit(r2, day(1), {'u1': 9})
    with rls_context(uid='u1'):
        rows = SEL.list_refuge_visits(r1.pk, 'u1')
    assert [attrs(v) for v in rows] == [(day(0), r1.pk, 5, False, 0), (day(3), r1.pk, 6, True, 2)]


def test_list_refuge_visits_inclou_les_visites_buides_amb_total_0(SEL, scene):
    r1, _ = scene
    make_visit(r1, day(1))
    with rls_context(uid='u1'):
        assert [attrs(v) for v in SEL.list_refuge_visits(r1.pk, 'u1')] == [(day(1), r1.pk, 0, False, 0)]


def test_list_user_visits_nomes_les_seves_passades_i_futures_en_ordre_descendent(SEL, scene):
    r1, r2 = scene
    make_visit(r1, day(-10), {'u1': 1})
    make_visit(r1, day(5), {'u1': 2, 'u2': 3})
    make_visit(r2, day(2), {'u2': 7})                          # no hi participa
    make_visit(r2, day(-3), {'u1': 4})
    with rls_context(uid='u1'):
        rows = SEL.list_user_visits('u1')
    assert [attrs(v) for v in rows] == [(day(5), r1.pk, 5, True, 2), (day(-3), r2.pk, 4, True, 4),
                                        (day(-10), r1.pk, 1, True, 1)]


def test_list_user_visits_buit(SEL, scene):
    with rls_context(uid='u3'):
        assert SEL.list_user_visits('u3') == []


def test_els_selectors_no_exposen_participants_alienes(SEL, scene):
    r1, _ = scene
    make_visit(r1, day(1), {'u1': 1, 'u2': 2})
    with rls_context(uid='u1'):
        text = repr(SEL.list_refuge_visits(r1.pk, 'u1'))
    assert 'u2' not in text


# ---------- create_visit ----------

def test_create_visit_crea_la_visita_i_el_participant(S, scene):
    r1, _ = scene
    with rls_context(uid='u1'):
        v = S.create_visit('u1', r1.pk, day(2), 3)
    assert attrs(v) == (day(2), r1.pk, 3, True, 3)
    assert len(visit_rows(r1)) == 1
    assert participant_rows(visit_rows(r1)[0][0]) == {'u1': 3}


def test_create_visit_accepta_el_refuge_id_com_a_text(S, scene):
    r1, _ = scene
    with rls_context(uid='u1'):
        assert S.create_visit('u1', str(r1.pk), day(0), 1).refuge_id == r1.pk


def test_create_visit_afegeix_un_segon_usuari_a_la_mateixa_visita(S, scene):
    r1, _ = scene
    make_visit(r1, day(2), {'u1': 3})
    with rls_context(uid='u2'):
        v = S.create_visit('u2', r1.pk, day(2), 2)
    assert attrs(v) == (day(2), r1.pk, 5, True, 2)
    assert len(visit_rows(r1)) == 1                              # M4: una sola visita per (refugi, data)
    assert participant_rows(visit_rows(r1)[0][0]) == {'u1': 3, 'u2': 2}


def test_create_visit_avui_es_valid_i_ahir_no(S, scene):
    r1, _ = scene
    with rls_context(uid='u1'):
        S.create_visit('u1', r1.pk, day(0), 1)
        with pytest.raises(S.VisitDateInPast):
            S.create_visit('u1', r1.pk, day(-1), 1)
    assert visit_dates(r1) == [day(0)]


def test_create_visit_ja_registrat(S, scene):
    r1, _ = scene
    make_visit(r1, day(2), {'u1': 3})
    with rls_context(uid='u1'):
        with pytest.raises(S.AlreadyRegistered):
            S.create_visit('u1', r1.pk, day(2), 1)
    assert participant_rows(visit_rows(r1)[0][0]) == {'u1': 3}


@pytest.mark.parametrize('rid', [uuid.uuid4(), 'id-antic-de-firestore', '', 'x\x00y'])
def test_create_visit_refugi_inexistent_o_no_uuid(S, scene, rid):
    with rls_context(uid='u1'):
        with pytest.raises(S.RefugeNotFound):
            S.create_visit('u1', rid, day(2), 1)
    assert visit_rows() == []


def test_create_visit_refugi_inexistent_te_prioritat_sobre_la_data_passada(S, scene):
    with rls_context(uid='u1'):
        with pytest.raises(S.RefugeNotFound):
            S.create_visit('u1', uuid.uuid4(), day(-5), 1)


def test_create_visit_no_deixa_visita_orfena_si_falla_el_participant(S, scene):
    """Atomic: ja registrat -> cap fila nova."""
    r1, _ = scene
    make_visit(r1, day(2), {'u1': 1})
    before = visit_rows()
    with rls_context(uid='u1'):
        with pytest.raises(S.AlreadyRegistered):
            S.create_visit('u1', r1.pk, day(2), 4)
    assert visit_rows() == before


# ---------- update_visit ----------

def test_update_visit_canvia_nomes_la_fila_de_l_usuari(S, scene):
    r1, _ = scene
    vid = make_visit(r1, day(2), {'u1': 3, 'u2': 2})
    with rls_context(uid='u1'):
        v = S.update_visit('u1', r1.pk, day(2), 6)
    assert attrs(v) == (day(2), r1.pk, 8, True, 6)
    assert participant_rows(vid) == {'u1': 6, 'u2': 2}


def test_update_visit_no_comprova_la_data_comportament_actual(S, scene):
    r1, _ = scene
    make_visit(r1, day(-2), {'u1': 3})
    with rls_context(uid='u1'):
        assert S.update_visit('u1', r1.pk, day(-2), 4).num_visitors == 4


def test_update_visit_no_registrat(S, scene):
    r1, _ = scene
    vid = make_visit(r1, day(2), {'u2': 2})
    with rls_context(uid='u1'):
        with pytest.raises(S.NotRegistered):
            S.update_visit('u1', r1.pk, day(2), 6)
    assert participant_rows(vid) == {'u2': 2}


@pytest.mark.parametrize('rid', [uuid.uuid4(), 'no-uuid'])
def test_update_visit_inexistent(S, scene, rid):
    r1, _ = scene
    with rls_context(uid='u1'):
        with pytest.raises(S.VisitNotFound):
            S.update_visit('u1', rid, day(2), 1)
        with pytest.raises(S.VisitNotFound):
            S.update_visit('u1', r1.pk, day(9), 1)               # el refugi existeix, la visita no


# ---------- remove_visitor ----------

def test_remove_visitor_treu_nomes_l_usuari(S, scene):
    r1, _ = scene
    vid = make_visit(r1, day(2), {'u1': 3, 'u2': 2})
    with rls_context(uid='u1'):
        assert S.remove_visitor('u1', r1.pk, day(2)) is None
    assert participant_rows(vid) == {'u2': 2}


def test_remove_visitor_l_ultim_esborra_la_visita(S, scene):
    r1, _ = scene
    vid = make_visit(r1, day(2), {'u1': 3})
    with rls_context(uid='u1'):
        S.remove_visitor('u1', r1.pk, day(2))
    assert participant_rows(vid) == {} and visit_rows(r1) == []


def test_remove_visitor_errors(S, scene):
    r1, _ = scene
    make_visit(r1, day(2), {'u2': 2})
    with rls_context(uid='u1'):
        with pytest.raises(S.NotRegistered):
            S.remove_visitor('u1', r1.pk, day(2))
        with pytest.raises(S.VisitNotFound):
            S.remove_visitor('u1', r1.pk, day(7))
        with pytest.raises(S.VisitNotFound):
            S.remove_visitor('u1', 'no-uuid', day(2))


def test_remove_visitor_no_toca_les_files_dels_altres_encara_que_la_rls_no_les_veu(S, scene):
    r1, _ = scene
    vid = make_visit(r1, day(2), {'u2': 2, 'u3': 1})
    with rls_context(uid='u1'):
        with pytest.raises(S.NotRegistered):
            S.remove_visitor('u1', r1.pk, day(2))
    assert participant_rows(vid) == {'u2': 2, 'u3': 1}


# ---------- get_refuge_visits / get_user_visits ----------

def test_get_refuge_visits_refugi_inexistent(S, scene):
    with rls_context(uid='u1'):
        with pytest.raises(S.RefugeNotFound):
            S.get_refuge_visits('u1', uuid.uuid4())
        with pytest.raises(S.RefugeNotFound):
            S.get_refuge_visits('u1', 'no-uuid')


def test_get_refuge_visits_refugi_sense_visites_es_llista_buida(S, scene):
    r1, _ = scene
    with rls_context(uid='u1'):
        assert S.get_refuge_visits('u1', r1.pk) == []


def test_get_user_visits_i_get_refuge_visits_retornen_visit_summary(S, scene):
    r1, _ = scene
    make_visit(r1, day(1), {'u1': 2})
    with rls_context(uid='u1'):
        assert [attrs(v) for v in S.get_refuge_visits('u1', r1.pk)] == [(day(1), r1.pk, 2, True, 2)]
        assert [attrs(v) for v in S.get_user_visits('u1')] == [(day(1), r1.pk, 2, True, 2)]


def test_avui_es_el_de_madrid_i_no_el_d_utc(S, scene):
    """A les 00:30 de Madrid (23:30 UTC del dia abans) «avui» ja es el dia nou: ahir (UTC) es del passat."""
    from datetime import datetime, timezone as dt_tz
    from unittest import mock
    r1, _ = scene
    instant = datetime(2026, 3, 10, 23, 30, tzinfo=dt_tz.utc)               # 11/03 00:30 a Madrid (CET)
    with mock.patch('django.utils.timezone.now', return_value=instant), rls_context(uid='u1'):
        with pytest.raises(S.VisitDateInPast):
            S.create_visit('u1', r1.pk, instant.date(), 1)                  # 10/03: avui UTC, ahir a Madrid
        assert S.create_visit('u1', r1.pk, instant.date() + timedelta(days=1), 1).date.isoformat() == '2026-03-11'
