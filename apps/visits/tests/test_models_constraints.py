"""
Models de `apps/visits/models.py` (chunk 4, §2.10, §2.11, §4.1, §6.3) i les seves restriccions, amb el rol `app`.

Contracte de models:
- `RefugeVisit`: `id` (UUIDField pk, `db_default=Func(function='uuidv7')`), `refuge` (FK a `refuges.Refuge`,
  `db_column='refuge_id'`), `visit_date` (DateField), `created_at` (`db_default=Now()`);
  `db_table = 'activity"."refuge_visits'`; `UniqueConstraint(refuge, visit_date, name='visits_refuge_date_uq')`.
- `VisitParticipant`: `pk = CompositePrimaryKey('visit', 'user')` (sense `id`); `visit` (FK a `RefugeVisit`,
  `db_column='visit_id'`), `user` (FK a `accounts.UserAccount`, `db_column='user_uid'`), `num_visitors` (enter),
  `created_at` (`db_default=Now()`); `db_table = 'activity"."refuge_visit_participants'`.
- `VisitTotal`: model `managed = False` de la vista `activity.refuge_visit_totals`; `visit = OneToOneField(RefugeVisit,
  primary_key=True, db_column='visit_id', related_name='totals', on_delete=DO_NOTHING)` i `total_visitors`.
- Totes les FK son `DO_NOTHING` amb `db_constraint=False` (les cascades son del DDL, §6.3).
"""
import uuid

import pytest
from django.db import IntegrityError, connection, models, transaction

from apps.core.rls import rls_context, system_context
from apps.visits.tests.helpers import (
    PARTS, VISITS, add_participant, day, make_refuge, make_user, make_visit, participant_rows, sql, total_of,
    visit_rows)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.models, pytest.mark.integration,
              pytest.mark.real_permissions]


def test_db_table_dels_models(VM):
    assert VM.RefugeVisit._meta.db_table == 'activity"."refuge_visits'
    assert VM.VisitParticipant._meta.db_table == 'activity"."refuge_visit_participants'
    assert VM.VisitTotal._meta.db_table == 'activity"."refuge_visit_totals'


def test_la_vista_es_un_model_no_gestionat_amb_visit_com_a_pk(VM):
    meta = VM.VisitTotal._meta
    assert meta.managed is False
    f = meta.get_field('visit')
    assert isinstance(f, models.OneToOneField) and f.primary_key
    assert f.column == 'visit_id' and f.remote_field.related_name == 'totals'
    assert f.remote_field.on_delete is models.DO_NOTHING


def test_participants_amb_pk_composta_sense_id(VM):
    pk = VM.VisitParticipant._meta.pk
    assert isinstance(pk, models.CompositePrimaryKey)
    assert tuple(pk.field_names) == ('visit', 'user')
    assert 'id' not in {f.name for f in VM.VisitParticipant._meta.get_fields()}


def test_les_fk_son_do_nothing_sense_constraint_de_django(VM):
    """§6.3: les cascades son del DDL, no de Django."""
    for model, field, column in ((VM.RefugeVisit, 'refuge', 'refuge_id'), (VM.VisitParticipant, 'visit', 'visit_id'),
                                 (VM.VisitParticipant, 'user', 'user_uid')):
        f = model._meta.get_field(field)
        assert f.remote_field.on_delete is models.DO_NOTHING and f.db_constraint is False, f'{model.__name__}.{field}'
        assert f.column == column


def test_constraint_unique_amb_el_nom_del_disseny(VM):
    names = {c.name: c for c in VM.RefugeVisit._meta.constraints}
    assert 'visits_refuge_date_uq' in names
    assert tuple(names['visits_refuge_date_uq'].fields) == ('refuge', 'visit_date')


def test_crear_una_visita_usa_uuidv7_i_now_de_la_bd(VM):
    make_user('u1')
    r = make_refuge()
    with rls_context(uid='u1'):
        v = VM.RefugeVisit.objects.create(refuge_id=r.pk, visit_date=day(1))
    assert isinstance(v.pk, uuid.UUID) and v.pk.version == 7          # el genera la BD (RETURNING), no Python
    assert v.created_at is not None


def test_duplicat_refuge_data_es_rebutja(VM):
    r = make_refuge()
    make_visit(r, day(1))
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            make_visit(r, day(1))
    assert len(visit_rows(r)) == 1


def test_mateixa_data_a_dos_refugis_i_dos_dies_al_mateix_refugi_es_permet():
    r1, r2 = make_refuge(name='A'), make_refuge(name='B', lat=43)
    for r, d in ((r1, day(1)), (r2, day(1)), (r1, day(2))):
        make_visit(r, d)
    assert len(visit_rows()) == 3


def test_insert_on_conflict_do_nothing_per_refuge_data_m4(VM):
    """M4: el «comprova i crea» passa a `INSERT ... ON CONFLICT DO NOTHING` (+ `SELECT`), sota RLS d'usuari."""
    make_user('u1')
    r = make_refuge()
    first = make_visit(r, day(1))
    with rls_context(uid='u1'):
        VM.RefugeVisit.objects.bulk_create([VM.RefugeVisit(refuge_id=r.pk, visit_date=day(1))], ignore_conflicts=True)
        assert VM.RefugeVisit.objects.get(refuge_id=r.pk, visit_date=day(1)).pk == first
    assert len(visit_rows(r)) == 1


def test_participant_duplicat_per_pk_composta_es_rebutja(VM):
    make_user('u1')
    r = make_refuge()
    vid = make_visit(r, day(1), {'u1': 2})
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            add_participant(vid, 'u1', 5)
    assert participant_rows(vid) == {'u1': 2}


@pytest.mark.parametrize('bad', [0, -1])
def test_num_visitors_ha_de_ser_com_a_minim_1(bad):
    make_user('u1')
    r = make_refuge()
    vid = make_visit(r, day(1))
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            add_participant(vid, 'u1', bad)
    assert participant_rows(vid) == {}


def test_fk_inexistents_fallen_en_comprovar_les_fk():
    make_user('u1')
    r = make_refuge()
    vid = make_visit(r, day(1))
    for stmt, params in ((f'INSERT INTO {PARTS} (visit_id, user_uid, num_visitors) VALUES (%s, %s, 1)',
                          [vid, 'fantasma']),
                         (f'INSERT INTO {PARTS} (visit_id, user_uid, num_visitors) VALUES (%s, %s, 1)',
                          [uuid.uuid4(), 'u1']),
                         (f'INSERT INTO {VISITS} (refuge_id, visit_date) VALUES (%s, %s)', [uuid.uuid4(), day(1)])):
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                sql(stmt, params)
                with connection.cursor() as cur:
                    cur.execute('SET CONSTRAINTS ALL IMMEDIATE')
        with connection.cursor() as cur:
            cur.execute('SET CONSTRAINTS ALL DEFERRED')


# ---------- La vista de totals ----------

def test_total_visitors_suma_num_visitors_de_tots_els_participants(VM):
    for u in ('u1', 'u2', 'u3'):
        make_user(u)
    r = make_refuge()
    vid = make_visit(r, day(1), {'u1': 3, 'u2': 2, 'u3': 4})
    assert total_of(vid) == 9
    # un usuari qualsevol (que no hi participa) veu el total complet a traves del model de la vista
    with rls_context(uid='u1'):
        assert VM.VisitTotal.objects.get(pk=vid).total_visitors == 9
    with rls_context(uid='ningu'):
        assert VM.VisitTotal.objects.get(pk=vid).total_visitors == 9


def test_visita_sense_participants_no_te_fila_a_la_vista(VM):
    r = make_refuge()
    vid = make_visit(r, day(1))
    with system_context():
        assert not VM.VisitTotal.objects.filter(pk=vid).exists()
    assert total_of(vid) == 0


def test_totals_via_select_related(VM):
    make_user('u1')
    r = make_refuge()
    make_visit(r, day(1), {'u1': 2})
    with rls_context(uid='u1'):
        v = VM.RefugeVisit.objects.select_related('totals').get(refuge_id=r.pk)
        assert v.totals.total_visitors == 2


def test_la_vista_no_admet_escriptures_per_a_app():
    """`app` nomes te `SELECT` a la vista (no es pot inserir/actualitzar)."""
    make_user('u1')
    r = make_refuge()
    vid = make_visit(r, day(1), {'u1': 1})
    for stmt in ('INSERT INTO activity.refuge_visit_totals (visit_id, total_visitors) VALUES (%s, 5)',
                 'UPDATE activity.refuge_visit_totals SET total_visitors = 5 WHERE visit_id = %s',
                 'DELETE FROM activity.refuge_visit_totals WHERE visit_id = %s'):
        with pytest.raises(Exception):
            with transaction.atomic():
                sql(stmt, [vid])
    assert total_of(vid) == 1


# ---------- Cascades del DDL amb el rol app (sense que la RLS les talli) ----------

def test_esborrar_la_visita_cascadeja_els_participants():
    make_user('u1')
    vid = make_visit(make_refuge(), day(1), {'u1': 2})
    sql(f'DELETE FROM {VISITS} WHERE id = %s', [vid])
    assert participant_rows() == {}


def test_esborrar_el_refugi_cascadeja_visites_i_participants():
    make_user('u1')
    r = make_refuge()
    make_visit(r, day(1), {'u1': 2})
    with connection.cursor() as cur:
        cur.execute('SET ROLE test_fixtures')
        cur.execute('DELETE FROM refuges.refuges WHERE id = %s', [r.pk])
        cur.execute('RESET ROLE')
    assert visit_rows() == [] and participant_rows() == {}


def test_esborrar_l_usuari_cascadeja_els_seus_participants_i_conserva_la_visita_i_els_altres(VM):
    make_user('u1')
    make_user('u2')
    vid = make_visit(make_refuge(), day(1), {'u1': 3, 'u2': 2})
    assert total_of(vid) == 5
    with system_context():
        from apps.accounts.models import UserAccount
        UserAccount.objects.filter(pk='u1').delete()                 # un sol DELETE; la BD fa la resta
    assert participant_rows(vid) == {'u2': 2}
    assert total_of(vid) == 2                                        # M3: resta num_visitors (3), no 1
    assert len(visit_rows()) == 1
