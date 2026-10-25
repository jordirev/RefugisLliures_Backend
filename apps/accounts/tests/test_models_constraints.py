"""
Models `FavouriteRefuge` / `VisitedRefuge` (chunk 3, §2.3-2.4) i les seves restriccions, amb el rol `app`.

Contracte de models (apps/accounts/models.py): `FavouriteRefuge` i `VisitedRefuge` amb `user` (FK a `UserAccount`,
`db_column='user_uid'`), `refuge` (FK a `refuges.Refuge`, `db_column='refuge_id'`), `created_at` (`db_default=Now()`) i
`pk = models.CompositePrimaryKey('user', 'refuge')` (Django 5.2; sense `id`).
"""
import uuid

import pytest
from django.db import IntegrityError, connection, models, transaction

from apps.accounts.tests.helpers import (
    FAV, VIS, QueryCounter, add_list_row, at, list_rows, make_refuge, make_user, sql)
from apps.core.rls import rls_context, system_context

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.models, pytest.mark.integration,
              pytest.mark.real_permissions]

MODELS = [('FavouriteRefuge', FAV, 'users"."user_favourite_refuges'),
          ('VisitedRefuge', VIS, 'users"."user_visited_refuges')]


def _model(AM, name):
    return getattr(AM, name)


@pytest.mark.parametrize('name,kind,table', MODELS)
def test_db_table_i_pk_composta(AM, name, kind, table):
    m = _model(AM, name)
    assert m._meta.db_table == table
    pk = m._meta.pk
    assert isinstance(pk, models.CompositePrimaryKey)
    assert tuple(pk.field_names) == ('user', 'refuge')
    assert 'id' not in {f.name for f in m._meta.get_fields()}          # sense `id` (decisio S-3)


@pytest.mark.parametrize('name,kind,table', MODELS)
def test_les_fk_son_do_nothing_sense_constraint_de_django(AM, name, kind, table):
    """§6.3: les cascades son del DDL, no de Django."""
    m = _model(AM, name)
    for field in ('user', 'refuge'):
        f = m._meta.get_field(field)
        assert f.remote_field.on_delete is models.DO_NOTHING and f.db_constraint is False, f'{name}.{field}'
    assert m._meta.get_field('user').column == 'user_uid'
    assert m._meta.get_field('refuge').column == 'refuge_id'


@pytest.mark.parametrize('name,kind,table', MODELS)
def test_crear_una_fila_usa_el_default_now_de_la_bd(AM, name, kind, table):
    make_user('u1')
    r = make_refuge()
    with system_context():
        row = _model(AM, name).objects.create(user_id='u1', refuge_id=r.pk)
        assert row.created_at is not None
        assert _model(AM, name).objects.filter(user_id='u1', refuge_id=r.pk).count() == 1


@pytest.mark.parametrize('name,kind,table', MODELS)
def test_la_pk_composta_rebutja_duplicats(AM, name, kind, table):
    make_user('u1')
    r = make_refuge()
    add_list_row(kind, 'u1', r, 0)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            add_list_row(kind, 'u1', r, 1)
    assert [row[2] for row in list_rows(kind, 'u1')] == [at(0)]


@pytest.mark.parametrize('name,kind,table', MODELS)
def test_el_mateix_refugi_a_dos_usuaris_i_dos_refugis_al_mateix_usuari_es_permet(AM, name, kind, table):
    make_user('u1')
    make_user('u2')
    r1, r2 = make_refuge(name='A'), make_refuge(name='B', lat=43)
    for uid, r in (('u1', r1), ('u2', r1), ('u1', r2)):
        add_list_row(kind, uid, r)
    assert len(list_rows(kind)) == 3


@pytest.mark.parametrize('name,kind,table', MODELS)
def test_insert_idempotent_amb_on_conflict_do_nothing_conserva_l_original(AM, name, kind, table):
    make_user('u1')
    r = make_refuge()
    add_list_row(kind, 'u1', r, 0)
    n = sql(f'INSERT INTO {table.replace(chr(34), "")} (user_uid, refuge_id, created_at) VALUES (%s, %s, %s) '
            'ON CONFLICT (user_uid, refuge_id) DO NOTHING RETURNING 1', ['u1', r.pk, at(99)])
    assert n == []
    assert [row[2] for row in list_rows(kind, 'u1')] == [at(0)]


@pytest.mark.parametrize('name,kind,table', MODELS)
def test_fk_inexistents_fallen_en_comprovar_les_fk(AM, name, kind, table):
    make_user('u1')
    orphan = uuid.uuid4()
    add_list_row(kind, 'u1', orphan)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            with connection.cursor() as cur:
                cur.execute('SET CONSTRAINTS ALL IMMEDIATE')
    with connection.cursor() as cur:
        cur.execute('SET CONSTRAINTS ALL DEFERRED')
    sql(f'DELETE FROM {table.replace(chr(34), "")}')             # perque el teardown no falli

    make_refuge()
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            add_list_row(kind, 'fantasma', make_refuge(name='Z', lat=44))
            with connection.cursor() as cur:
                cur.execute('SET CONSTRAINTS ALL IMMEDIATE')
    with connection.cursor() as cur:
        cur.execute('SET CONSTRAINTS ALL DEFERRED')
    sql(f'DELETE FROM {table.replace(chr(34), "")}')


# ---------- cascades del DDL amb el rol app (sense que la RLS les talli) ----------

@pytest.mark.parametrize('name,kind,table', MODELS)
def test_esborrar_l_usuari_cascadeja_les_llistes_amb_un_sol_delete(AM, name, kind, table):
    make_user('u1')
    make_user('u2')
    r = make_refuge()
    add_list_row(kind, 'u1', r)
    add_list_row(kind, 'u2', r)
    with rls_context(uid='u1'):
        with QueryCounter() as q:
            AM.UserAccount.objects.filter(pk='u1').delete()
        assert len([s for s in q.queries if s.upper().startswith('DELETE')]) == 1, q.queries
    assert [row[0] for row in list_rows(kind)] == ['u2']


@pytest.mark.parametrize('name,kind,table', MODELS)
def test_esborrar_un_refugi_cascadeja_les_llistes(AM, RM, name, kind, table):
    make_user('u1')
    r, other = make_refuge(name='A'), make_refuge(name='B', lat=43)
    add_list_row(kind, 'u1', r)
    add_list_row(kind, 'u1', other)
    with as_owner_ctx():
        RM.Refuge.objects.filter(pk=r.pk).delete()
    assert [row[1] for row in list_rows(kind, 'u1')] == [other.pk]


def as_owner_ctx():
    from apps.accounts.tests.helpers import as_owner
    return as_owner()


def test_les_dues_llistes_son_independents(AM):
    make_user('u1')
    r = make_refuge()
    add_list_row(FAV, 'u1', r)
    assert list_rows(VIS, 'u1') == []
