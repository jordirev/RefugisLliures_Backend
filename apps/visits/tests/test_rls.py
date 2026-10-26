"""
RLS del chunk 4 amb el rol `app` (§2.10, §2.11, §4.1, §7.5): visites i participants (anonim, propi, alie, admin, sistema).

- `refuge_visits`: SELECT/INSERT per a qualsevol usuari amb `uid` i per al sistema; DELETE nomes `{SYS}`; sense UPDATE.
- `refuge_visit_participants`: cada usuari nomes veu/escriu la SEVA fila; l'admin nomes llegeix; el sistema tot.
- `refuge_visit_totals` (vista del propietari) dona el total complet a qualsevol context: un `SUM` directe sota RLS
  nomes comptaria les files visibles (§2.11 ⚠).

Un `INSERT` denegat per la RLS llanca error; un `SELECT`/`UPDATE`/`DELETE` denegat afecta 0 files.
"""
import pytest
from django.db import DatabaseError, connection, transaction

from apps.core.rls import rls_context
from apps.visits.tests.helpers import (
    PARTS, TOTALS, VISITS, day, make_refuge, make_user, make_visit, participant_rows, sql, visit_rows)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.rls, pytest.mark.integration,
              pytest.mark.real_permissions]

ANON = {}
OWN = {'uid': 'u1'}
OTHER = {'uid': 'u2'}
ADMIN = {'uid': 'adm', 'is_admin': True}
SYSTEM = {'system': True}
ALL_CTX = {'anon': ANON, 'own': OWN, 'other': OTHER, 'admin': ADMIN, 'system': SYSTEM}
LOGGED = {'own', 'other', 'admin', 'system'}


@pytest.fixture
def scene():
    """Una visita amb `u1` (3) i `u2` (2); `u3` existeix sense participar-hi."""
    for u in ('u1', 'u2', 'u3'):
        make_user(u)
    r = make_refuge()
    return r, make_visit(r, day(1), {'u1': 3, 'u2': 2})


def _denied(fn):
    with pytest.raises(DatabaseError):
        with transaction.atomic():
            fn()


def _run(ctx, statement, params=None):
    with rls_context(**ALL_CTX[ctx]):
        with connection.cursor() as cur:
            cur.execute(statement, params)
            return cur.fetchall() if cur.description else cur.rowcount


# ---------- refuge_visits ----------

@pytest.mark.parametrize('ctx', ALL_CTX)
def test_visits_select_qualsevol_usuari_amb_uid_i_el_sistema(scene, ctx):
    n = _run(ctx, f'SELECT count(*) FROM {VISITS}')[0][0]
    assert n == (1 if ctx in LOGGED else 0)


@pytest.mark.parametrize('ctx', ALL_CTX)
def test_visits_insert(scene, ctx):
    r2 = make_refuge(name='R2', lat=43)

    def go():
        _run(ctx, f'INSERT INTO {VISITS} (refuge_id, visit_date) VALUES (%s, %s)', [r2.pk, day(2)])
    if ctx in LOGGED:
        go()
        assert len(visit_rows(r2)) == 1
    else:
        _denied(go)
        assert visit_rows(r2) == []


@pytest.mark.parametrize('ctx', ALL_CTX)
def test_visits_delete_nomes_el_sistema(scene, ctx):
    r, vid = scene
    deleted = _run(ctx, f'DELETE FROM {VISITS} WHERE id = %s', [vid])
    assert deleted == (1 if ctx == 'system' else 0)
    assert len(visit_rows(r)) == (0 if ctx == 'system' else 1)


@pytest.mark.parametrize('ctx', ALL_CTX)
def test_visits_sense_update_per_a_app(scene, ctx):
    _denied(lambda: _run(ctx, f'UPDATE {VISITS} SET visit_date = visit_date'))


def test_visits_insert_on_conflict_do_nothing_amb_returning_com_a_usuari(scene):
    """§7.5 #8: el flux d'alta (`ON CONFLICT DO NOTHING` + `SELECT`) funciona amb el rol `app` d'un usuari."""
    r, vid = scene
    stmt = (f'INSERT INTO {VISITS} (refuge_id, visit_date) VALUES (%s, %s) '
            'ON CONFLICT (refuge_id, visit_date) DO NOTHING RETURNING id')
    assert _run('other', stmt, [r.pk, day(1)]) == []                      # ja existeix: no fa res
    assert [r[0] for r in _run('other', stmt, [r.pk, day(5)])] != []       # nova: la crea
    assert len(visit_rows(r)) == 2


def test_sense_context_tot_es_invisible(scene):
    with connection.cursor() as cur:
        cur.execute("SELECT set_config('app.uid', '', true), set_config('app.is_admin', '', true), "
                    "set_config('app.is_system', '', true)")
        for table in (VISITS, PARTS):
            cur.execute(f'SELECT count(*) FROM {table}')
            assert cur.fetchone()[0] == 0


# ---------- participants ----------

EXPECTED_PARTICIPANTS = {'anon': [], 'own': ['u1'], 'other': ['u2'], 'admin': ['u1', 'u2'], 'system': ['u1', 'u2']}


@pytest.mark.parametrize('ctx', ALL_CTX)
def test_participants_select_segons_context(scene, ctx):
    rows = _run(ctx, f'SELECT user_uid FROM {PARTS} ORDER BY 1')
    assert [r[0] for r in rows] == EXPECTED_PARTICIPANTS[ctx]


@pytest.mark.parametrize('ctx', ALL_CTX)
def test_participants_insert_nomes_la_propia_fila_o_el_sistema(scene, ctx):
    r, vid = scene
    # cap context de la taula es `u3`: nomes el sistema pot inserir la fila de `u3`
    def go():
        _run(ctx, f'INSERT INTO {PARTS} (visit_id, user_uid, num_visitors) VALUES (%s, %s, 1)', [vid, 'u3'])
    if ctx == 'system':
        go()
        assert 'u3' in participant_rows(vid)
    else:
        _denied(go)
        assert 'u3' not in participant_rows(vid)


def test_un_usuari_pot_inserir_la_seva_fila(scene):
    r, vid = scene
    with rls_context(uid='u3'):
        with connection.cursor() as cur:
            cur.execute(f'INSERT INTO {PARTS} (visit_id, user_uid, num_visitors) VALUES (%s, %s, 4)', [vid, 'u3'])
    assert participant_rows(vid)['u3'] == 4


@pytest.mark.parametrize('ctx', ['other', 'admin', 'anon'])
def test_ningu_no_pot_inserir_com_un_altre_usuari_ni_amb_on_conflict(scene, ctx):
    r, vid = scene
    _denied(lambda: _run(ctx, f'INSERT INTO {PARTS} (visit_id, user_uid, num_visitors) VALUES (%s, %s, 9) '
                              'ON CONFLICT (visit_id, user_uid) DO NOTHING', [vid, 'u1']))


@pytest.mark.parametrize('ctx', ALL_CTX)
def test_participants_update_de_la_fila_de_u1(scene, ctx):
    r, vid = scene
    n = _run(ctx, f'UPDATE {PARTS} SET num_visitors = 7 WHERE user_uid = %s', [ 'u1'])
    owner_or_system = ctx in ('own', 'system')
    assert n == (1 if owner_or_system else 0)                       # l'admin NOMES llegeix (vparts_update)
    assert participant_rows(vid)['u1'] == (7 if owner_or_system else 3)


@pytest.mark.parametrize('ctx', ALL_CTX)
def test_participants_delete_de_la_fila_de_u1(scene, ctx):
    r, vid = scene
    n = _run(ctx, f'DELETE FROM {PARTS} WHERE user_uid = %s', ['u1'])
    owner_or_system = ctx in ('own', 'system')
    assert n == (1 if owner_or_system else 0)
    assert ('u1' in participant_rows(vid)) is (not owner_or_system)


def test_un_usuari_no_pot_moure_la_seva_fila_a_nom_d_un_altre_with_check(scene):
    r, vid = scene
    _denied(lambda: _run('own', f'UPDATE {PARTS} SET user_uid = %s WHERE user_uid = %s', ['u3', 'u1']))


# ---------- la vista de totals i el perill del SUM directe ----------

@pytest.mark.parametrize('ctx', ALL_CTX)
def test_la_vista_dona_el_total_complet_a_tots_els_contexts(scene, ctx):
    r, vid = scene
    assert _run(ctx, f'SELECT total_visitors FROM {TOTALS} WHERE visit_id = %s', [vid]) == [(5,)]


def test_un_sum_directe_a_participants_nomes_compta_la_fila_visible():
    """§2.11 ⚠: per aixo els totals passen sempre per la vista."""
    for u in ('u1', 'u2'):
        make_user(u)
    vid = make_visit(make_refuge(), day(1), {'u1': 3, 'u2': 2})
    assert _run('own', f'SELECT sum(num_visitors) FROM {PARTS} WHERE visit_id = %s', [vid]) == [(3,)]
    assert _run('own', f'SELECT total_visitors FROM {TOTALS} WHERE visit_id = %s', [vid]) == [(5,)]


# ---------- cascades amb el rol app ----------

def test_delete_de_l_usuari_com_a_ell_mateix_cascadeja_participants_malgrat_la_rls(scene):
    """La cascada del DDL (propietari) no la talla la RLS, tampoc els participants d'un altre."""
    r, vid = scene
    with rls_context(uid='u1'):
        with connection.cursor() as cur:
            cur.execute('DELETE FROM users.users WHERE uid = %s', ['u1'])
    assert participant_rows(vid) == {'u2': 2}
    assert sql(f'SELECT total_visitors FROM {TOTALS} WHERE visit_id = %s', [vid]) == [(2,)]
