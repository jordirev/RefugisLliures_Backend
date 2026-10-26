"""
Selectors i services de `apps.doubts` (chunk 6). Contracte proposat pels tests (l'implementador pot renomenar-lo
justificant-ho). Les vistes han d'accedir-hi com a `selectors.x(...)` / `services.x(...)` (mòdul, no `from ... import x`)
perquè els tests de 500 puguin fer `patch('apps.doubts.services.x')`.

selectors (lectures; sense cache; la RLS és pública)
- `get_doubt(doubt_id) -> Doubt | None`            1 consulta; un id no UUID dona `None`
- `get_answer(doubt_id, answer_id) -> Answer | None`  1 consulta; `None` si la resposta és d'un altre dubte o l'id no és UUID
- `list_doubts(refuge_id) -> list[Doubt]`          2 consultes (dubtes amb `answers_count` anotat + `Prefetch('answers')`),
      dubtes per `(created_at DESC, id DESC)`; `doubt.answers.all()` (prefetch) per `(created_at ASC, id ASC)` sense
      consultes noves; refugi inexistent o id no UUID -> `[]`

services (escriptures; excepcions de domini, cap tupla; propietat comprovada ABANS de la RLS)
- excepcions: `RefugeNotFound`, `DoubtNotFound`, `AnswerNotFound`, `NotOwner`
- `create_doubt(*, refuge_id, creator_uid, message) -> Doubt`            `RefugeNotFound` (també id no UUID)
- `create_answer(*, doubt_id, creator_uid, message, parent_answer_id=None) -> Answer`
      `DoubtNotFound`; `AnswerNotFound` si el pare no existeix o és d'un altre dubte
- `delete_doubt(*, doubt_id, actor_uid, is_admin=False) -> None`         `DoubtNotFound`, `NotOwner`; 1 sol `DELETE`
- `delete_answer(*, doubt_id, answer_id, actor_uid, is_admin=False) -> None`
      `DoubtNotFound`, `AnswerNotFound` (també si és d'un altre dubte), `NotOwner`; 1 sol `DELETE` (la BD esborra el subarbre)
"""
import uuid
from datetime import timedelta

import pytest

from apps.core.rls import rls_context, system_context
from apps.doubts.tests.helpers import (
    QueryCounter, answer_ids, answer_rows, build_tree, doubt_ids, doubt_rows, make_answer, make_doubt, make_refuge,
    make_user)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.integration, pytest.mark.real_permissions]

BAD_IDS = ['no-es-uuid', '', '0' * 40, 'a\x00b', "1'; DROP TABLE activity.doubts;--"]


# =================================== selectors ===================================

def test_get_doubt(selectors, world):
    d = make_doubt(world[0], 'u1', message='Hola')
    with rls_context(uid='u2'):
        found = selectors.get_doubt(d)
        assert str(found.pk) == d and found.creator_id == 'u1' and found.message == 'Hola'
        assert selectors.get_doubt(str(uuid.uuid4())) is None


@pytest.mark.parametrize('bad', BAD_IDS)
def test_get_doubt_amb_id_invalid_es_none(selectors, world, bad):
    with rls_context(uid='u1'):
        assert selectors.get_doubt(bad) is None


def test_get_doubt_1_consulta(selectors, world):
    d = make_doubt(world[0], 'u1')
    with rls_context(uid='u1'):
        with QueryCounter() as q:
            selectors.get_doubt(d)
    assert q.count == 1


def test_get_answer_ha_de_ser_del_dubte(selectors, world):
    r1, _ = world
    d1, d2 = make_doubt(r1, 'u1'), make_doubt(r1, 'u1', minutes=1)
    a = make_answer(d1, 'u2')
    with rls_context(uid='u1'):
        assert str(selectors.get_answer(d1, a).pk) == a
        assert selectors.get_answer(d2, a) is None
        assert selectors.get_answer(d1, str(uuid.uuid4())) is None
        with QueryCounter() as q:
            selectors.get_answer(d1, a)
        assert q.count == 1


@pytest.mark.parametrize('bad', BAD_IDS)
def test_get_answer_amb_ids_invalids_es_none(selectors, world, bad):
    d = make_doubt(world[0], 'u1')
    with rls_context(uid='u1'):
        assert selectors.get_answer(d, bad) is None
        assert selectors.get_answer(bad, str(uuid.uuid4())) is None


def test_list_doubts_ordre_comptadors_i_respostes(selectors, world):
    r1, r2 = world
    old = make_doubt(r1, 'u1', message='antic', minutes=0)
    new = make_doubt(r1, 'u2', message='nou', minutes=10)
    empty = make_doubt(r1, 'u3', message='sense respostes', minutes=5)
    make_doubt(r2, 'u1', message='altre refugi', minutes=20)
    a2 = make_answer(old, 'u2', 'segona', minutes=2)
    a1 = make_answer(old, 'u3', 'primera', minutes=1)
    a3 = make_answer(old, 'u1', 'filla', parent=a1, minutes=3)
    with rls_context(uid='u1'):
        doubts = selectors.list_doubts(r1.pk)
        assert [str(d.pk) for d in doubts] == [new, empty, old]                  # created_at DESC
        by_id = {str(d.pk): d for d in doubts}
        assert [by_id[new].answers_count, by_id[empty].answers_count, by_id[old].answers_count] == [0, 0, 3]
        with QueryCounter() as q:                                                  # prefetch: cap consulta nova
            assert [str(a.pk) for a in by_id[old].answers.all()] == [a1, a2, a3]  # created_at ASC
            assert list(by_id[new].answers.all()) == []
        assert q.count == 0


def test_list_doubts_desempata_per_id(selectors, world):
    r1, _ = world
    ids = [make_doubt(r1, 'u1', message=f'm{i}', minutes=0) for i in range(3)]   # mateix created_at
    d = make_doubt(r1, 'u1', message='amb respostes', minutes=1)
    ans = [make_answer(d, 'u2', f'r{i}', minutes=0) for i in range(3)]
    with rls_context(uid='u1'):
        doubts = selectors.list_doubts(r1.pk)
        assert [str(x.pk) for x in doubts] == [d] + sorted(ids, reverse=True)      # id DESC
        assert [str(a.pk) for a in doubts[0].answers.all()] == sorted(ans)         # id ASC


def test_list_doubts_2_consultes_amb_qualsevol_nombre_de_files(selectors, world):
    r1, _ = world
    counts = []
    for n in (1, 12):
        for i in range(n):
            d = make_doubt(r1, 'u1', message=f'd{n}-{i}', minutes=100 * n + i)
            for k in range(3):
                make_answer(d, 'u2', f'a{k}', minutes=100 * n + i + k)
        with rls_context(uid='u1'):
            with QueryCounter() as q:
                doubts = selectors.list_doubts(r1.pk)
                for d in doubts:
                    list(d.answers.all())
                    d.answers_count
        counts.append(q.count)
    assert counts[0] == counts[1] == 2, counts


@pytest.mark.parametrize('bad', ['no-es-uuid', '', 'a\x00b'])
def test_list_doubts_refugi_invalid_o_inexistent_es_buit(selectors, world, bad):
    with rls_context(uid='u1'):
        assert selectors.list_doubts(bad) == []
        assert selectors.list_doubts(str(uuid.uuid4())) == []


def test_list_doubts_es_visible_per_a_l_anonim(selectors, world):
    make_doubt(world[0], 'u1')
    with rls_context():
        assert len(selectors.list_doubts(world[0].pk)) == 1


# =================================== services: create ===================================

def test_create_doubt(services, world):
    r1, _ = world
    with rls_context(uid='u1'):
        doubt = services.create_doubt(refuge_id=str(r1.pk), creator_uid='u1', message='Hi ha llenya?')
    assert doubt.message == 'Hi ha llenya?' and doubt.creator_id == 'u1' and str(doubt.refuge_id) == str(r1.pk)
    rows = doubt_rows()
    assert len(rows) == 1 and rows[0][0] == str(doubt.pk) and rows[0][4] == doubt.created_at     # un sol rellotge (BD)


@pytest.mark.parametrize('bad', ['no-es-uuid', 'a\x00b', str(uuid.uuid4())])
def test_create_doubt_refugi_inexistent(services, world, bad):
    with rls_context(uid='u1'):
        with pytest.raises(services.RefugeNotFound):
            services.create_doubt(refuge_id=bad, creator_uid='u1', message='x')
    assert doubt_ids() == []


def test_create_doubt_no_pot_crear_en_nom_d_un_altre_amb_la_rls(services, world):
    """Defensa en profunditat: la RLS impedeix `creator_uid != uid` fins i tot si el service s'invoca malament."""
    from django.db import DatabaseError
    with rls_context(uid='u2'):
        with pytest.raises(DatabaseError):
            services.create_doubt(refuge_id=str(world[0].pk), creator_uid='u1', message='x')


def test_create_answer_directa_i_resposta_a_resposta(services, world):
    d = make_doubt(world[0], 'u1')
    with rls_context(uid='u2'):
        a = services.create_answer(doubt_id=d, creator_uid='u2', message='Sí')
    assert a.parent_answer_id is None and a.creator_id == 'u2' and str(a.doubt_id) == d
    with rls_context(uid='u3'):
        r = services.create_answer(doubt_id=d, creator_uid='u3', message='Gràcies', parent_answer_id=str(a.pk))
    assert str(r.parent_answer_id) == str(a.pk)
    assert answer_ids(d) == [str(a.pk), str(r.pk)]


def test_create_answer_dubte_inexistent(services, world):
    with rls_context(uid='u2'):
        for bad in ('no-es-uuid', str(uuid.uuid4())):
            with pytest.raises(services.DoubtNotFound):
                services.create_answer(doubt_id=bad, creator_uid='u2', message='x')


def test_create_answer_pare_inexistent_o_d_un_altre_dubte(services, world):
    r1, _ = world
    d1, d2 = make_doubt(r1, 'u1'), make_doubt(r1, 'u1', minutes=1)
    foreign = make_answer(d2, 'u3')
    with rls_context(uid='u2'):
        for parent in (str(uuid.uuid4()), 'no-es-uuid', foreign):
            with pytest.raises(services.AnswerNotFound):
                services.create_answer(doubt_id=d1, creator_uid='u2', message='x', parent_answer_id=parent)
    assert answer_ids(d1) == []


# =================================== services: delete ===================================

def test_delete_doubt_propi_esborra_dubte_i_respostes(services, world):
    make_user('u9')
    d, _ = build_tree(world[0], 'u1')
    other = make_doubt(world[0], 'u2', minutes=9)
    with rls_context(uid='u1'):
        with QueryCounter() as q:
            assert services.delete_doubt(doubt_id=d, actor_uid='u1') is None
    assert len([s for s in q.queries if s.upper().startswith('DELETE')]) == 1, q.queries
    assert doubt_ids() == [other] and answer_ids(d) == []


def test_delete_doubt_d_un_altre_es_not_owner_i_no_esborra(services, world):
    d = make_doubt(world[0], 'u1')
    with rls_context(uid='u2'):
        with pytest.raises(services.NotOwner):
            services.delete_doubt(doubt_id=d, actor_uid='u2')
    assert doubt_ids() == [d]


def test_la_propietat_es_comprova_al_service_no_nomes_a_la_rls(services, world):
    """Amb el context de sistema la RLS ho deixaria passar: el service ha de dir `NotOwner` igualment (C1)."""
    d = make_doubt(world[0], 'u1')
    a = make_answer(d, 'u1')
    with system_context():
        with pytest.raises(services.NotOwner):
            services.delete_doubt(doubt_id=d, actor_uid='u2')
        with pytest.raises(services.NotOwner):
            services.delete_answer(doubt_id=d, answer_id=a, actor_uid='u2')
    assert doubt_ids() == [d] and answer_ids(d) == [a]


def test_delete_doubt_admin_pot_esborrar_el_d_un_altre(services, world):
    d = make_doubt(world[0], 'u1')
    make_answer(d, 'u2')
    with rls_context(uid='adm', is_admin=True):
        services.delete_doubt(doubt_id=d, actor_uid='adm', is_admin=True)
    assert doubt_ids() == [] and answer_ids() == []


def test_delete_doubt_inexistent(services, world):
    with rls_context(uid='u1'):
        for bad in ('no-es-uuid', str(uuid.uuid4()), 'a\x00b'):
            with pytest.raises(services.DoubtNotFound):
                services.delete_doubt(doubt_id=bad, actor_uid='u1')


def test_delete_answer_propia_esborra_el_subarbre_amb_un_sol_delete(services, world):
    d, a = build_tree(world[0], 'u1')
    with rls_context(uid='u2'):
        with QueryCounter() as q:
            services.delete_answer(doubt_id=d, answer_id=a['a1'], actor_uid='u2')
    assert len([s for s in q.queries if s.upper().startswith('DELETE')]) == 1, q.queries
    assert answer_ids(d) == [a['a2']] and doubt_ids() == [d]


def test_delete_answer_d_un_altre_es_not_owner_tambe_per_al_creador_del_dubte(services, world):
    d, a = build_tree(world[0], 'u1')
    with rls_context(uid='u1'):
        with pytest.raises(services.NotOwner):
            services.delete_answer(doubt_id=d, answer_id=a['a1'], actor_uid='u1')      # u1 és el creador del dubte
    assert len(answer_ids(d)) == 5


def test_delete_answer_admin(services, world):
    d, a = build_tree(world[0], 'u1')
    with rls_context(uid='adm', is_admin=True):
        services.delete_answer(doubt_id=d, answer_id=a['a1r'], actor_uid='adm', is_admin=True)
    assert set(answer_ids(d)) == {a['a1'], a['a1s'], a['a2']}                         # a1r i a1rr fora


def test_delete_answer_inexistents(services, world):
    r1, _ = world
    d1, d2 = make_doubt(r1, 'u1'), make_doubt(r1, 'u1', minutes=1)
    a = make_answer(d2, 'u1')
    with rls_context(uid='u1'):
        with pytest.raises(services.DoubtNotFound):
            services.delete_answer(doubt_id=str(uuid.uuid4()), answer_id=a, actor_uid='u1')
        with pytest.raises(services.DoubtNotFound):
            services.delete_answer(doubt_id='no-es-uuid', answer_id=a, actor_uid='u1')
        for bad in (str(uuid.uuid4()), 'no-es-uuid', a):                    # `a` és de d2, no de d1
            with pytest.raises(services.AnswerNotFound):
                services.delete_answer(doubt_id=d1, answer_id=bad, actor_uid='u1')
    assert answer_ids(d2) == [a]


def test_les_excepcions_de_domini_son_diferents(services):
    classes = {services.RefugeNotFound, services.DoubtNotFound, services.AnswerNotFound, services.NotOwner}
    assert len(classes) == 4 and all(issubclass(c, Exception) for c in classes)
