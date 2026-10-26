"""
Models `Doubt` / `Answer` (chunk 6, §2.16-2.17) i les seves restriccions, amb el rol `app`.

Contracte de models (`apps/doubts/models.py`):
- `Doubt`: `id` (UUID, `db_default=uuidv7()`), `refuge` (FK a `refuges.Refuge`, `db_column='refuge_id'`), `creator` (FK a
  `accounts.UserAccount`, `db_column='creator_uid'`), `message`, `created_at`; `db_table = 'activity"."doubts'`.
- `Answer`: `id`, `doubt` (FK a `Doubt`, `related_name='answers'`), `creator`, `parent_answer` (FK a `self`, nullable,
  `related_name='replies'`, `db_constraint=False`), `message`, `created_at`; `db_table = 'activity"."answers'`.
- Totes les FK son `DO_NOTHING` + `db_constraint=False` (§6.3): les cascades son del DDL.
"""
import uuid

import pytest
from django.db import IntegrityError, connection, models, transaction

from apps.core.rls import rls_context, system_context
from apps.doubts.tests.helpers import (
    QueryCounter, answer_ids, build_tree, doubt_ids, make_answer, make_doubt, make_refuge, make_user, sql)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.models, pytest.mark.integration,
              pytest.mark.real_permissions]


@pytest.fixture
def base():
    make_user('u1')
    make_user('u2')
    return make_refuge()


def _fails(fn):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            fn()


def _check_fks():
    with connection.cursor() as cur:
        cur.execute('SET CONSTRAINTS ALL IMMEDIATE')


def _defer_fks():
    with connection.cursor() as cur:
        cur.execute('SET CONSTRAINTS ALL DEFERRED')


# ---------- metadades ----------

def test_db_table_i_pk_uuid_amb_default_de_la_bd(DM):
    assert DM.Doubt._meta.db_table == 'activity"."doubts'
    assert DM.Answer._meta.db_table == 'activity"."answers'
    for model in (DM.Doubt, DM.Answer):
        pk = model._meta.pk
        assert isinstance(pk, models.UUIDField) and pk.name == 'id'
        assert pk.db_default is not models.NOT_PROVIDED


def test_les_fk_son_do_nothing_sense_constraint_de_django(DM):
    """§6.3: les cascades son del DDL, no de Django."""
    fields = [(DM.Doubt, 'refuge'), (DM.Doubt, 'creator'), (DM.Answer, 'doubt'), (DM.Answer, 'creator'),
              (DM.Answer, 'parent_answer')]
    for model, name in fields:
        f = model._meta.get_field(name)
        assert f.remote_field.on_delete is models.DO_NOTHING and f.db_constraint is False, f'{model.__name__}.{name}'
    assert DM.Doubt._meta.get_field('refuge').column == 'refuge_id'
    assert DM.Doubt._meta.get_field('creator').column == 'creator_uid'
    assert DM.Answer._meta.get_field('doubt').column == 'doubt_id'
    assert DM.Answer._meta.get_field('parent_answer').column == 'parent_answer_id'
    assert DM.Answer._meta.get_field('parent_answer').null is True
    assert DM.Answer._meta.get_field('parent_answer').remote_field.model is DM.Answer


def test_related_names(DM):
    assert DM.Answer._meta.get_field('doubt').remote_field.related_name == 'answers'
    assert DM.Answer._meta.get_field('parent_answer').remote_field.related_name == 'replies'


def test_no_hi_ha_cap_camp_answers_count_desat(DM):
    assert 'answers_count' not in {f.name for f in DM.Doubt._meta.get_fields()}      # §4: es calcula


# ---------- defaults de la BD ----------

def test_crear_un_dubte_usa_uuidv7_i_created_at_de_la_bd(DM, base):
    with system_context():
        d = DM.Doubt.objects.create(refuge_id=base.pk, creator_id='u1', message='Hola')
        assert isinstance(d.pk, uuid.UUID) and d.pk.version == 7
        assert d.created_at is not None


def test_crear_una_resposta_usa_uuidv7(DM, base):
    d = make_doubt(base, 'u1')
    with system_context():
        a = DM.Answer.objects.create(doubt_id=d, creator_id='u2', message='Sí')
        assert a.pk.version == 7 and a.parent_answer_id is None


def test_els_ids_son_monotons(DM, base):
    ids = [make_doubt(base, 'u1', message=f'm{i}', minutes=i) for i in range(5)]
    assert ids == sorted(ids)


# ---------- CHECK del missatge ----------

@pytest.mark.parametrize('message', ['', ' ', '   \n\t ', ' '.replace(' ', ' ')])
def test_doubt_rebutja_missatge_buit_o_nomes_espais(base, message):
    _fails(lambda: make_doubt(base, 'u1', message=message))
    assert doubt_ids() == []


def test_doubt_missatge_de_2000_caracters_val_i_2001_no(base):
    make_doubt(base, 'u1', message='x' * 2000)
    _fails(lambda: make_doubt(base, 'u1', message='x' * 2001))
    assert len(doubt_ids()) == 1


def test_el_limit_compta_caracters_no_bytes(base):
    make_doubt(base, 'u1', message='\U0001F600' * 2000)             # 8000 bytes UTF-8
    _fails(lambda: make_doubt(base, 'u1', message='\U0001F600' * 2001))


@pytest.mark.parametrize('message', ['', '  ', 'x' * 2001])
def test_answer_rebutja_missatge_invalid(base, message):
    d = make_doubt(base, 'u1')
    _fails(lambda: make_answer(d, 'u2', message=message))
    assert answer_ids() == []


def test_answer_missatge_de_2000_val(base):
    d = make_doubt(base, 'u1')
    make_answer(d, 'u2', message='y' * 2000)
    assert len(answer_ids()) == 1


# ---------- arbre de respostes ----------

def test_la_resposta_pot_ser_filla_d_una_del_mateix_dubte(base):
    make_user('u3')
    d, a = build_tree(base)
    assert len(answer_ids(d)) == 5


def test_el_pare_ha_de_ser_del_mateix_dubte(base):
    d1 = make_doubt(base, 'u1')
    d2 = make_doubt(base, 'u1', minutes=1)
    parent = make_answer(d1, 'u2')
    _defer_fks()

    def go():
        make_answer(d2, 'u2', parent=parent)
        _check_fks()
    _fails(go)
    _defer_fks()
    assert answer_ids(d2) == []


def test_el_pare_ha_d_existir(base):
    d = make_doubt(base, 'u1')

    def go():
        make_answer(d, 'u2', parent=str(uuid.uuid4()))
        _check_fks()
    _fails(go)
    _defer_fks()
    assert answer_ids() == []


def test_una_resposta_no_pot_ser_pare_de_si_mateixa(base):
    d = make_doubt(base, 'u1')
    me = str(uuid.uuid4())
    _fails(lambda: make_answer(d, 'u2', parent=me, answer_id=me))
    assert answer_ids() == []


def test_la_pk_de_les_respostes_rebutja_duplicats(base):
    d = make_doubt(base, 'u1')
    aid = make_answer(d, 'u2')
    _fails(lambda: make_answer(d, 'u2', answer_id=aid))             # PK duplicada
    assert answer_ids(d) == [aid]


def test_fk_inexistents_fallen_en_comprovar_les_fk(base):
    _defer_fks()

    def go():
        make_doubt(uuid.uuid4(), 'u1')                                # refugi inexistent
        _check_fks()
    _fails(go)
    _defer_fks()

    def go2():
        make_doubt(base, 'fantasma')                                  # usuari inexistent
        _check_fks()
    _fails(go2)
    _defer_fks()
    sql('DELETE FROM activity.doubts')


# ---------- cascades del DDL amb el rol app (sense que la RLS les talli) ----------

def test_esborrar_un_dubte_cascadeja_totes_les_respostes_amb_un_sol_delete(DM, base):
    make_user('u3')
    d, _ = build_tree(base, 'u1')
    other = make_doubt(base, 'u1', minutes=9)
    make_answer(other, 'u2')
    with rls_context(uid='u1'):
        with QueryCounter() as q:
            DM.Doubt.objects.filter(pk=d).delete()
        assert len([s for s in q.queries if s.upper().startswith('DELETE')]) == 1, q.queries
    assert answer_ids(d) == [] and len(answer_ids(other)) == 1 and doubt_ids() == [other]


def test_esborrar_una_resposta_cascadeja_el_subarbre_i_respecta_la_resta(DM, base):
    make_user('u3')
    d, a = build_tree(base, 'u1')
    with rls_context(uid='u2'):
        with QueryCounter() as q:
            DM.Answer.objects.filter(pk=a['a1']).delete()
        assert len([s for s in q.queries if s.upper().startswith('DELETE')]) == 1
    assert answer_ids(d) == [a['a2']]                           # a1, a1r, a1rr i a1s desapareixen


def test_esborrar_una_fulla_no_toca_res_mes(DM, base):
    make_user('u3')
    d, a = build_tree(base, 'u1')
    with rls_context(uid='u1'):
        DM.Answer.objects.filter(pk=a['a1rr']).delete()
    assert set(answer_ids(d)) == {a['a1'], a['a1r'], a['a1s'], a['a2']}


def test_esborrar_l_usuari_cascadeja_dubtes_i_respostes(DM, base):
    make_user('u3')
    d, a = build_tree(base, 'u1')
    with rls_context(uid='u1'):
        with QueryCounter() as q:
            from apps.accounts.models import UserAccount
            UserAccount.objects.filter(pk='u1').delete()
        assert len([s for s in q.queries if s.upper().startswith('DELETE')]) == 1
    assert doubt_ids() == [] and answer_ids() == []


def test_esborrar_un_refugi_cascadeja_dubtes_i_respostes(RM, base):
    d = make_doubt(base, 'u1')
    make_answer(d, 'u2')
    other_refuge = make_refuge(name='Altre', lat=43.1)
    keep = make_doubt(other_refuge, 'u1', minutes=2)
    from apps.doubts.tests.helpers import as_owner
    with as_owner():
        RM.Refuge.objects.filter(pk=base.pk).delete()
    assert doubt_ids() == [keep] and answer_ids() == []
