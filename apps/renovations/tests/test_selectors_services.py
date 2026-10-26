"""
Selectors i serveis de reformes (chunk 5), contra Postgres amb el rol `app`. Els serveis es criden dins
`rls_context(uid=...)`, com ho farien dins una petició.

Contracte de `apps/renovations/selectors.py` (lectures, una consulta per cas d'ús, sense cache):
- `parse_renovation_id(value) -> uuid.UUID | None`: `None` si no és un UUID (inclosos IDs antics de Firestore i valors
  amb un byte NUL).
- `get_renovation(renovation_id) -> Renovation | None`: una consulta; la instància duu `participants_uids` (llista
  ordenada per `created_at, user_id`) i `group_link` (cadena o `None`: la RLS el deixa a `None` a qui no hi té dret).
- `list_active_renovations() -> list[Renovation]`: `fin_date >= get_madrid_today()` ordenades per `(ini_date, id)`.
- `list_refuge_renovations(refuge_id, active_only=False) -> list[Renovation] | None`: del refugi, ordenades per
  `(ini_date, id)`; `None` si el refugi no existeix (o l'id no és un UUID) → la vista respon 404.
- `find_overlapping(refuge_id, ini_date, fin_date, exclude_id=None) -> Renovation | None`.
- `count_renovated_refuges(uid) -> int`: reformes creades + reformes on participa (§4).

Contracte de `apps/renovations/services.py` (escriptures; excepcions de domini en lloc de tuples; tot dins
`transaction.atomic`):
- `create_renovation(uid, *, refuge_id, ini_date, fin_date, description, group_link, materials_needed=None)
  -> Renovation`: crea reforma + enllaç a la mateixa transacció. Errors: `RefugeNotFound` (UUID inexistent o no UUID),
  `OverlappingRenovation` (atribut `.renovation`: la reforma en conflicte, també si la detecta l'`EXCLUDE` de la BD).
- `update_renovation(renovation_id, uid, **fields) -> Renovation`: només camps presents; compara la data nova amb la
  desada (M2); `InvalidDates` si `ini > fin`. Errors: `RenovationNotFound`, `NotRenovationCreator`, `InvalidDates`,
  `OverlappingRenovation`.
- `delete_renovation(renovation_id, uid) -> None`: `RenovationNotFound`, `NotRenovationCreator`.
- `add_participant(renovation_id, uid) -> Renovation`: `RenovationNotFound`, `CreatorCannotJoin`, `UserExpelled`,
  `AlreadyParticipant`.
- `remove_participant(renovation_id, participant_uid, requester_uid) -> Renovation`: el propi participant o el creador;
  si el creador treu un altre, l'expulsa (participants → expulsats, una sola transacció). `RenovationNotFound`,
  `NotAllowed` (ni ell mateix ni el creador), `NotAParticipant`.
"""
import importlib
import uuid

import pytest
from django.db import connection

from apps.core.rls import rls_context
from apps.renovations.tests.helpers import (
    LINK, QueryCounter, day, expelled_of, link_of, make_renovation, missing_uuid, participants_of, renovation_row)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.unit, pytest.mark.integration,
              pytest.mark.real_permissions]


@pytest.fixture
def SEL():
    return importlib.import_module('apps.renovations.selectors')


@pytest.fixture
def SV():
    return importlib.import_module('apps.renovations.services')


# =============================================== selectors ===============================================

@pytest.mark.parametrize('value', ['', 'abc', '12345', 'a' * 40, 'nul\x00byte', None])
def test_parse_renovation_id_invalid(SEL, value):
    assert SEL.parse_renovation_id(value) is None


def test_parse_renovation_id_valid(SEL):
    u = uuid.uuid4()
    assert SEL.parse_renovation_id(str(u)) == u
    assert SEL.parse_renovation_id(u) == u


def test_get_renovation_anotada_en_una_consulta(SEL, world):
    rid = make_renovation(world.refuge, 'u1', participants=['u3', 'u2'], link='https://t.me/x')
    with rls_context(uid='u1'):
        with QueryCounter() as q:
            r = SEL.get_renovation(rid)
    assert q.count == 1
    assert r.pk == rid and r.participants_uids == ['u3', 'u2'] and r.group_link == 'https://t.me/x'


def test_get_renovation_inexistent(SEL, world):
    with rls_context(uid='u1'):
        assert SEL.get_renovation(uuid.uuid4()) is None


@pytest.mark.parametrize('uid,sees', [('u1', True), ('u2', True), ('adm', True), ('u3', False), ('u4', False)])
def test_get_renovation_group_link_segons_la_rls(SEL, world, uid, sees):
    rid = make_renovation(world.refuge, 'u1', participants=['u2'], expelled=['u4'], link='https://t.me/x')
    with rls_context(uid=uid, is_admin=(uid == 'adm')):
        link = SEL.get_renovation(rid).group_link
    assert link == ('https://t.me/x' if sees else None)


def test_list_active_inclou_la_que_acaba_avui_i_exclou_les_acabades(SEL, world):
    ends_today = make_renovation(world.refuge, 'u1', ini=day(-3), fin=day(0))
    make_renovation(world.refuge2, 'u1', ini=day(-9), fin=day(-1))
    future = make_renovation(world.refuge2, 'u1', ini=day(2), fin=day(3))
    with rls_context(uid='u3'):
        ids = [r.pk for r in SEL.list_active_renovations()]
    assert ids == [ends_today, future]


def test_list_active_ordenada_per_data_d_inici(SEL, world):
    late = make_renovation(world.refuge, 'u1', ini=day(20), fin=day(21))
    early = make_renovation(world.refuge2, 'u1', ini=day(3), fin=day(4))
    with rls_context(uid='u3'):
        assert [r.pk for r in SEL.list_active_renovations()] == [early, late]


def test_list_active_una_consulta_i_amb_participants(SEL, world):
    for i in range(5):
        make_renovation(world.refuge if i % 2 else world.refuge2, 'u1', ini=day(i * 3 + 1), fin=day(i * 3 + 2),
                        participants=['u2', 'u3'])
    with rls_context(uid='u2'):
        with QueryCounter() as q:
            rows = SEL.list_active_renovations()
    assert q.count == 1 and len(rows) == 5 and all(r.participants_uids == ['u2', 'u3'] for r in rows)


def test_list_refuge_nomes_les_del_refugi_i_per_defecte_totes(SEL, world):
    past = make_renovation(world.refuge, 'u1', ini=day(-9), fin=day(-5))
    cur = make_renovation(world.refuge, 'u1', ini=day(1), fin=day(2))
    make_renovation(world.refuge2, 'u1', ini=day(1), fin=day(2))
    with rls_context(uid='u3'):
        assert [r.pk for r in SEL.list_refuge_renovations(world.refuge.pk)] == [past, cur]
        assert [r.pk for r in SEL.list_refuge_renovations(world.refuge.pk, active_only=True)] == [cur]
        assert [r.pk for r in SEL.list_refuge_renovations(str(world.refuge.pk), active_only=False)] == [past, cur]


@pytest.mark.parametrize('refuge_id', [str(uuid.uuid4()), 'abc', 'nul\x00'])
def test_list_refuge_inexistent_o_id_invalid_retorna_none(SEL, world, refuge_id):
    with rls_context(uid='u3'):
        assert SEL.list_refuge_renovations(refuge_id) is None


def test_list_refuge_buit_es_llista_buida(SEL, world):
    with rls_context(uid='u3'):
        assert SEL.list_refuge_renovations(world.refuge.pk) == []


def test_find_overlapping(SEL, world):
    a = make_renovation(world.refuge, 'u1', ini=day(5), fin=day(10))
    with rls_context(uid='u3'):
        assert SEL.find_overlapping(world.refuge.pk, day(10), day(12)).pk == a
        assert SEL.find_overlapping(world.refuge.pk, day(11), day(12)) is None
        assert SEL.find_overlapping(world.refuge.pk, day(6), day(7), exclude_id=a) is None
        assert SEL.find_overlapping(world.refuge2.pk, day(6), day(7)) is None


def test_find_overlapping_considera_tambe_les_acabades(SEL, world):
    """L'`EXCLUDE` compta totes les files (§2.12); el cas marginal és editar les dates d'una reforma en curs."""
    a = make_renovation(world.refuge, None, ini=day(-9), fin=day(-5))
    with rls_context(uid='u3'):
        assert SEL.find_overlapping(world.refuge.pk, day(-6), day(-4)).pk == a


def test_count_renovated_refuges_creades_mes_unides(SEL, world):
    make_renovation(world.refuge, 'u1', ini=day(1), fin=day(2))
    make_renovation(world.refuge, 'u1', ini=day(-9), fin=day(-5))                 # passada: també compta
    make_renovation(world.refuge2, 'u3', ini=day(1), fin=day(2), participants=['u1', 'u2'], expelled=['u4'])
    with rls_context(uid='u1'):
        assert SEL.count_renovated_refuges('u1') == 3
        assert SEL.count_renovated_refuges('u2') == 1
        assert SEL.count_renovated_refuges('u4') == 0                             # expulsat: no compta
        assert SEL.count_renovated_refuges('ningu') == 0


# =============================================== services: crear ===============================================

def _create(SV, uid='u1', refuge=None, **over):
    data = dict(refuge_id=refuge, ini_date=day(5), fin_date=day(8), description='Sostre', group_link=LINK)
    data.update(over)
    with rls_context(uid=uid):
        return SV.create_renovation(uid, **data)


def test_create_crea_reforma_i_enllac(SV, world):
    r = _create(SV, refuge=world.refuge.pk, materials_needed='Tauler')
    assert r.pk and r.participants_uids == [] and r.group_link == LINK
    row = renovation_row(r.pk)
    assert row['creator_uid'] == 'u1' and row['materials_needed'] == 'Tauler' and link_of(r.pk) == LINK


def test_create_accepta_el_refugi_com_a_cadena(SV, world):
    assert _create(SV, refuge=str(world.refuge.pk)).pk


@pytest.mark.parametrize('refuge_id', [lambda: str(uuid.uuid4()), lambda: 'abc', lambda: 'nul\x00byte'])
def test_create_refugi_inexistent_o_no_uuid(SV, world, refuge_id):
    with pytest.raises(SV.RefugeNotFound):
        _create(SV, refuge=refuge_id())


def test_create_solapament_duu_la_reforma_en_conflicte(SV, world):
    other = make_renovation(world.refuge, 'u3', ini=day(6), fin=day(7))
    with pytest.raises(SV.OverlappingRenovation) as exc:
        _create(SV, refuge=world.refuge.pk)
    assert exc.value.renovation.pk == other


def test_create_solapament_detectat_per_la_bd_encara_que_la_comprovacio_previa_falli(SV, world):
    """Carrera entre dues creacions: si el SELECT previ no veu res, l'`EXCLUDE` ho atrapa i es tradueix igual."""
    from unittest.mock import patch
    make_renovation(world.refuge, 'u3', ini=day(6), fin=day(7))
    with patch('apps.renovations.services.selectors.find_overlapping', return_value=None):
        with pytest.raises(SV.OverlappingRenovation):
            _create(SV, refuge=world.refuge.pk)
    assert _count() == 1


def test_create_es_atomic_si_falla_l_enllac(SV, world):
    """Si l'enllaç no es pot desar, tampoc queda la reforma (una sola transacció)."""
    def boom(execute, sql, params, many, context):
        if sql.lstrip().upper().startswith('INSERT') and 'renovation_group_links' in sql:
            raise RuntimeError('fallada simulada')
        return execute(sql, params, many, context)

    with connection.execute_wrapper(boom):
        with pytest.raises(Exception):
            _create(SV, refuge=world.refuge.pk)
    assert _count() == 0


def _count():
    with connection.cursor() as cur:
        cur.execute('SELECT count(*) FROM activity.renovations')
        return cur.fetchone()[0]


# =============================================== services: actualitzar ===============================================

def _update(SV, rid, uid='u1', **fields):
    with rls_context(uid=uid):
        return SV.update_renovation(rid, uid, **fields)


def test_update_nomes_canvia_els_camps_presents(SV, world):
    rid = make_renovation(world.refuge, 'u1', materials='abans')
    r = _update(SV, rid, description='Nova')
    row = renovation_row(rid)
    assert r.description == 'Nova' and row['materials_needed'] == 'abans' and link_of(rid) == LINK


def test_update_group_link(SV, world):
    rid = make_renovation(world.refuge, 'u1')
    r = _update(SV, rid, group_link='https://t.me/nou')
    assert r.group_link == 'https://t.me/nou' and link_of(rid) == 'https://t.me/nou'


def test_update_materials_a_nul(SV, world):
    rid = make_renovation(world.refuge, 'u1', materials='abans')
    _update(SV, rid, materials_needed=None)
    assert renovation_row(rid)['materials_needed'] is None


def test_update_sense_camps_no_canvia_res(SV, world):
    rid = make_renovation(world.refuge, 'u1')
    assert _update(SV, rid).pk == rid


def test_update_m2_nomes_ini_date_es_compara_amb_la_fin_desada(SV, world):
    rid = make_renovation(world.refuge, 'u1', ini=day(5), fin=day(10))
    assert _update(SV, rid, ini_date=day(7)).ini_date == day(7)
    with pytest.raises(SV.InvalidDates):
        _update(SV, rid, ini_date=day(12))
    assert renovation_row(rid)['ini_date'] == day(7)


def test_update_m2_nomes_fin_date_es_compara_amb_la_ini_desada(SV, world):
    rid = make_renovation(world.refuge, 'u1', ini=day(5), fin=day(10))
    assert _update(SV, rid, fin_date=day(5)).fin_date == day(5)                    # un dia: vàlid
    with pytest.raises(SV.InvalidDates):
        _update(SV, rid, fin_date=day(4))
    assert renovation_row(rid)['fin_date'] == day(5)


def test_update_dates_a_un_rang_que_se_solapa(SV, world):
    rid = make_renovation(world.refuge, 'u1', ini=day(5), fin=day(10))
    other = make_renovation(world.refuge, 'u1', ini=day(20), fin=day(25))
    with pytest.raises(SV.OverlappingRenovation) as exc:
        _update(SV, rid, fin_date=day(20))
    assert exc.value.renovation.pk == other
    assert renovation_row(rid)['fin_date'] == day(10)


def test_update_no_se_solapa_amb_ella_mateixa(SV, world):
    rid = make_renovation(world.refuge, 'u1', ini=day(5), fin=day(10))
    assert _update(SV, rid, ini_date=day(6), fin_date=day(9)).pk == rid


def test_update_inexistent_i_no_creador(SV, world):
    rid = make_renovation(world.refuge, 'u1', participants=['u2'])
    with pytest.raises(SV.RenovationNotFound):
        _update(SV, uuid.uuid4(), description='x')
    for uid in ('u2', 'u3', 'adm'):
        with pytest.raises(SV.NotRenovationCreator):
            _update(SV, rid, uid=uid, description='x')
    assert renovation_row(rid)['description'] == 'Pintar la cabana'


def test_update_d_una_reforma_anonima_no_es_del_creador(SV, world):
    rid = make_renovation(world.refuge, None, ini=day(-9), fin=day(-5))
    with pytest.raises(SV.NotRenovationCreator):
        _update(SV, rid, uid='u1', description='x')


# =============================================== services: esborrar ===============================================

def test_delete_esborra_amb_cascada(SV, world):
    rid = make_renovation(world.refuge, 'u1', participants=['u2'], expelled=['u4'])
    with rls_context(uid='u1'):
        assert SV.delete_renovation(rid, 'u1') is None
    assert renovation_row(rid) is None and participants_of(rid) == [] and expelled_of(rid) == []
    assert link_of(rid) is None


def test_delete_errors(SV, world):
    rid = make_renovation(world.refuge, 'u1')
    with rls_context(uid='u3'):
        with pytest.raises(SV.NotRenovationCreator):
            SV.delete_renovation(rid, 'u3')
        with pytest.raises(SV.RenovationNotFound):
            SV.delete_renovation(uuid.uuid4(), 'u3')
    assert renovation_row(rid) is not None


# =============================================== services: participants ===============================================

def _join(SV, rid, uid):
    with rls_context(uid=uid):
        return SV.add_participant(rid, uid)


def _leave(SV, rid, participant, requester):
    with rls_context(uid=requester):
        return SV.remove_participant(rid, participant, requester)


def test_add_participant_i_ordre_d_arribada(SV, world):
    """Ordre per `created_at`: el nou participant va l'últim (el de la fila existent és anterior a la transacció)."""
    rid = make_renovation(world.refuge, 'u1', participants=['u3'])
    r = _join(SV, rid, 'u2')
    assert r.participants_uids == ['u3', 'u2'] and r.group_link == LINK
    assert participants_of(rid) == ['u3', 'u2']


def test_add_participant_errors(SV, world):
    rid = make_renovation(world.refuge, 'u1', participants=['u2'], expelled=['u4'])
    with pytest.raises(SV.CreatorCannotJoin):
        _join(SV, rid, 'u1')
    with pytest.raises(SV.UserExpelled):
        _join(SV, rid, 'u4')
    with pytest.raises(SV.AlreadyParticipant):
        _join(SV, rid, 'u2')
    with pytest.raises(SV.RenovationNotFound):
        _join(SV, uuid.uuid4(), 'u3')
    assert participants_of(rid) == ['u2']


def test_add_participant_dues_vegades_deixa_una_sola_fila(SV, world):
    """A3: la PK (no un read-modify-write) garanteix que no hi ha duplicats."""
    rid = make_renovation(world.refuge, 'u1')
    _join(SV, rid, 'u2')
    with pytest.raises(SV.AlreadyParticipant):
        _join(SV, rid, 'u2')
    assert participants_of(rid) == ['u2']


def test_remove_participant_el_propi_surt_sense_ser_expulsat(SV, world):
    rid = make_renovation(world.refuge, 'u1', participants=['u2', 'u3'])
    r = _leave(SV, rid, 'u2', 'u2')
    assert r.participants_uids == ['u3'] and r.group_link is None
    assert expelled_of(rid) == []
    assert _join(SV, rid, 'u2').participants_uids == ['u3', 'u2']                 # pot tornar


def test_remove_participant_el_creador_expulsa(SV, world):
    rid = make_renovation(world.refuge, 'u1', participants=['u2', 'u3'])
    r = _leave(SV, rid, 'u2', 'u1')
    assert r.participants_uids == ['u3'] and r.group_link == LINK                  # el creador veu l'enllaç
    assert participants_of(rid) == ['u3'] and expelled_of(rid) == ['u2']
    with pytest.raises(SV.UserExpelled):
        _join(SV, rid, 'u2')


def test_remove_participant_errors(SV, world):
    rid = make_renovation(world.refuge, 'u1', participants=['u2', 'u3'])
    with pytest.raises(SV.NotAllowed):
        _leave(SV, rid, 'u2', 'u3')                                               # un participant no n'expulsa un altre
    with pytest.raises(SV.NotAllowed):
        _leave(SV, rid, 'u2', 'adm')                                              # tampoc l'admin
    with pytest.raises(SV.NotAParticipant):
        _leave(SV, rid, 'u4', 'u1')                                               # el creador no pot expulsar qui no hi és
    with pytest.raises(SV.NotAParticipant):
        _leave(SV, rid, 'u1', 'u1')                                               # el creador no és participant
    with pytest.raises(SV.RenovationNotFound):
        _leave(SV, uuid.uuid4(), 'u2', 'u2')
    assert participants_of(rid) == ['u2', 'u3'] and expelled_of(rid) == []


def test_remove_participant_que_no_hi_es_no_crea_cap_expulsio(SV, world):
    rid = make_renovation(world.refuge, 'u1')
    with pytest.raises(SV.NotAParticipant):
        _leave(SV, rid, 'u4', 'u1')
    assert expelled_of(rid) == []


def test_expulsio_es_atomica(SV, world):
    """Si la inserció a `expelled` falla, el participant no ha de desaparèixer (una sola transacció)."""
    rid = make_renovation(world.refuge, 'u1', participants=['u2'])

    def boom(execute, sql, params, many, context):
        if sql.lstrip().upper().startswith('INSERT') and 'renovation_expelled' in sql:
            raise RuntimeError('fallada simulada')
        return execute(sql, params, many, context)

    with connection.execute_wrapper(boom):
        with pytest.raises(Exception):
            _leave(SV, rid, 'u2', 'u1')
    assert participants_of(rid) == ['u2'] and expelled_of(rid) == []


def test_serveis_sense_n_mes_1_pel_nombre_de_participants(SV, world):
    small = make_renovation(world.refuge, 'u1', ini=day(1), fin=day(2))
    big = make_renovation(world.refuge2, 'u1', ini=day(1), fin=day(2), participants=['u2', 'u3', 'u4'])
    counts = []
    for rid in (small, big):
        with QueryCounter() as q:
            _join(SV, rid, 'adm')
        counts.append(q.count)
    assert counts[0] == counts[1], counts
