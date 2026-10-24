"""
RLS del chunk 3 amb el rol `app` (§2.3, §2.4, §7.5): preferits i visitats (anonim, propi, alie, admin, sistema) i
els fluxos d'escriptura (`ON CONFLICT`, `RETURNING`, moderacio dins `system_context()`).

Un `INSERT` denegat per la RLS llança error; un `SELECT`/`DELETE` denegat afecta 0 files.
"""
import pytest
from django.db import DatabaseError, connection, transaction

from apps.accounts.tests.helpers import (
    FAV, TABLES, VIS, add_list_row, list_rows, make_refuge, make_user, sql)
from apps.core.rls import rls_context, system_context

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.rls, pytest.mark.integration,
              pytest.mark.real_permissions]

ANON = {}
OWN = {'uid': 'u1'}
OTHER = {'uid': 'u2'}
ADMIN = {'uid': 'adm', 'is_admin': True}
SYSTEM = {'system': True}
ALL_CTX = {'anon': ANON, 'own': OWN, 'other': OTHER, 'admin': ADMIN, 'system': SYSTEM}

# Qui veu les files de `u1` (SELECT): preferits = propi o sistema; visitats = propi, admin o sistema (§2.3, §2.4).
SEES = {
    FAV: {'anon': False, 'own': True, 'other': False, 'admin': False, 'system': True},
    VIS: {'anon': False, 'own': True, 'other': False, 'admin': True, 'system': True},
}
EXPECTED_ROWS = {
    FAV: {'anon': [], 'own': ['u1'], 'other': ['u2'], 'admin': [], 'system': ['u1', 'u2']},
    VIS: {'anon': [], 'own': ['u1'], 'other': ['u2'], 'admin': ['u1', 'u2'], 'system': ['u1', 'u2']},
}
WRITES = {'anon': False, 'own': True, 'other': False, 'admin': False, 'system': True}      # INSERT/DELETE de `u1`


@pytest.fixture
def world():
    make_user('u1')
    make_user('u2')
    return make_refuge(name='R1'), make_refuge(name='R2', lat=43)


def _denied(fn):
    with pytest.raises(DatabaseError):
        with transaction.atomic():
            fn()


def _run(ctx, statement, params=None):
    with rls_context(**ALL_CTX[ctx]):
        with connection.cursor() as cur:
            cur.execute(statement, params)
            return cur.fetchall() if cur.description else cur.rowcount


@pytest.mark.parametrize('kind', [FAV, VIS])
@pytest.mark.parametrize('ctx', ALL_CTX)
def test_select_segons_context(world, kind, ctx):
    r1, r2 = world
    add_list_row(kind, 'u1', r1)
    add_list_row(kind, 'u2', r2)
    rows = _run(ctx, f'SELECT user_uid FROM {TABLES[kind]} ORDER BY 1')
    expected = EXPECTED_ROWS[kind][ctx]
    assert [r[0] for r in rows] == expected


def test_l_admin_no_veu_els_preferits_pero_si_els_visitats(world):
    r1, _ = world
    add_list_row(FAV, 'u1', r1)
    add_list_row(VIS, 'u1', r1)
    assert _run('admin', f'SELECT count(*) FROM {TABLES[FAV]}')[0][0] == 0
    assert _run('admin', f'SELECT count(*) FROM {TABLES[VIS]}')[0][0] == 1


@pytest.mark.parametrize('kind', [FAV, VIS])
@pytest.mark.parametrize('ctx', ALL_CTX)
def test_insert_de_files_de_u1(world, kind, ctx):
    r1, _ = world

    def go():
        _run(ctx, f'INSERT INTO {TABLES[kind]} (user_uid, refuge_id) VALUES (%s, %s)', ['u1', r1.pk])
    if WRITES[ctx]:
        go()
        assert len(list_rows(kind, 'u1')) == 1
    else:
        _denied(go)
        assert list_rows(kind, 'u1') == []


@pytest.mark.parametrize('kind', [FAV, VIS])
def test_un_usuari_no_pot_inserir_files_d_un_altre_ni_amb_on_conflict(world, kind):
    r1, _ = world
    _denied(lambda: _run('other', f'INSERT INTO {TABLES[kind]} (user_uid, refuge_id) VALUES (%s, %s) '
                                  'ON CONFLICT (user_uid, refuge_id) DO NOTHING', ['u1', r1.pk]))


@pytest.mark.parametrize('kind', [FAV, VIS])
@pytest.mark.parametrize('ctx', ALL_CTX)
def test_delete_de_files_de_u1(world, kind, ctx):
    r1, _ = world
    add_list_row(kind, 'u1', r1)
    deleted = _run(ctx, f'DELETE FROM {TABLES[kind]} WHERE user_uid = %s', ['u1'])
    assert deleted == (1 if WRITES[ctx] else 0)
    assert len(list_rows(kind, 'u1')) == (0 if WRITES[ctx] else 1)


@pytest.mark.parametrize('kind', [FAV, VIS])
@pytest.mark.parametrize('ctx', ALL_CTX)
def test_app_no_te_update(world, kind, ctx):
    """§7.2: sense `UPDATE` (el grant no existeix: error de permisos, no 0 files)."""
    r1, _ = world
    add_list_row(kind, 'u1', r1)
    _denied(lambda: _run(ctx, f'UPDATE {TABLES[kind]} SET created_at = now()'))


@pytest.mark.parametrize('kind', [FAV, VIS])
def test_sense_context_tot_es_invisible(world, kind):
    r1, _ = world
    add_list_row(kind, 'u1', r1)
    with connection.cursor() as cur:
        cur.execute("SELECT set_config('app.uid', '', true), set_config('app.is_admin', '', true), "
                    "set_config('app.is_system', '', true)")
        cur.execute(f'SELECT count(*) FROM {TABLES[kind]}')
        assert cur.fetchone()[0] == 0


@pytest.mark.parametrize('kind', [FAV, VIS])
def test_on_conflict_do_nothing_amb_returning_sota_rls_per_al_propi(world, kind):
    """§7.5 #8: el flux d'escriptura real (`POST .../favorite-refuges/`) funciona amb el rol `app`."""
    r1, _ = world
    stmt = (f'INSERT INTO {TABLES[kind]} (user_uid, refuge_id) VALUES (%s, %s) '
            'ON CONFLICT (user_uid, refuge_id) DO NOTHING RETURNING refuge_id')
    assert _run('own', stmt, ['u1', r1.pk]) == [(r1.pk,)]
    assert _run('own', stmt, ['u1', r1.pk]) == []                      # idempotent
    assert len(list_rows(kind, 'u1')) == 1


def test_el_job_diari_insereix_visitats_de_molts_usuaris_amb_sistema(world):
    r1, r2 = world
    with rls_context(system=True):
        with connection.cursor() as cur:
            cur.execute(f'INSERT INTO {TABLES[VIS]} (user_uid, refuge_id) VALUES (%s, %s), (%s, %s), (%s, %s) '
                        'ON CONFLICT (user_uid, refuge_id) DO NOTHING',
                        ['u1', r1.pk, 'u2', r1.pk, 'u1', r2.pk])
    assert len(list_rows(VIS)) == 3


# ---------- Cascades amb el rol app: l'usuari i el refugi s'esborren sense que la RLS talli la cascada ----------

@pytest.mark.parametrize('kind', [FAV, VIS])
def test_esborrar_l_usuari_amb_el_seu_context_cascadeja_les_seves_llistes(world, kind):
    r1, _ = world
    add_list_row(kind, 'u1', r1)
    add_list_row(kind, 'u2', r1)
    with rls_context(uid='u1'):
        with connection.cursor() as cur:
            cur.execute('DELETE FROM users.users WHERE uid = %s', ['u1'])
    assert [r[0] for r in list_rows(kind)] == ['u2']


# ---------- Moderacio dins system_context (D20) i trigger fn_users_guard ----------

def test_un_usuari_no_pot_canviar_la_moderacio_pero_el_sistema_si(world):
    _denied(lambda: _run('own', 'UPDATE users.users SET moderation_strikes = 3 WHERE uid = %s', ['u1']))
    _denied(lambda: _run('own', "UPDATE users.users SET is_blocked = true, blocked_reason = 'strikes', "
                                'blocked_at = now() WHERE uid = %s', ['u1']))
    assert _run('system', 'UPDATE users.users SET moderation_strikes = moderation_strikes + 1 WHERE uid = %s',
                ['u1']) == 1
    assert sql('SELECT moderation_strikes FROM users.users WHERE uid = %s', ['u1']) == [(1,)]


def test_un_sistema_dins_d_un_context_d_usuari_no_deixa_privilegis_en_sortir(world):
    """`system_context()` niat dins la peticio d'un usuari: en sortir, el guard torna a actuar."""
    with rls_context(uid='u2'):
        with system_context():
            with connection.cursor() as cur:
                cur.execute('UPDATE users.users SET moderation_strikes = 2 WHERE uid = %s', ['u1'])
        with pytest.raises(DatabaseError):
            with transaction.atomic():
                with connection.cursor() as cur:
                    cur.execute('UPDATE users.users SET moderation_strikes = 9 WHERE uid = %s', ['u2'])
    assert sql('SELECT moderation_strikes FROM users.users WHERE uid = %s', ['u1']) == [(2,)]


def test_l_admin_pot_canviar_la_moderacio_d_un_altre_per_la_politica_update(world):
    assert _run('admin', 'UPDATE users.users SET moderation_strikes = 1 WHERE uid = %s', ['u2']) == 1
