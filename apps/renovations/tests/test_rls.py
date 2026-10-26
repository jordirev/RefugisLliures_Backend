"""
RLS del chunk 5 amb el rol `app` (§2.12, §2.12.1, §2.13, §2.14, §7.2, §7.5): `renovations`, `renovation_group_links`
(privada: creador, participants, admin, sistema), `renovation_participants` i `renovation_expelled` (l'expulsat només
veu la seva fila, el creador les de la seva reforma, l'admin totes).

Contextos: anònim, creador (`u1`), participant (`u2`), aliè (`u3`), expulsat (`u4`), admin, sistema.
Un `INSERT` denegat per la RLS llança error; un `SELECT`/`UPDATE`/`DELETE` denegat afecta 0 files; una operació sense
*grant* (p. ex. `DELETE` sobre l'enllaç o sobre els expulsats) llança error per a TOTS els contextos, també el de sistema.
"""
import pytest
from django.db import DatabaseError, connection, transaction

from apps.core.rls import rls_context
from apps.renovations.tests.helpers import (
    constraint_name, count_renovations, day, expelled_of, link_of, make_renovation, participants_of, sql)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.rls, pytest.mark.integration,
              pytest.mark.real_permissions]

CTX = {
    'anon': {},
    'creator': {'uid': 'u1'},
    'participant': {'uid': 'u2'},
    'other': {'uid': 'u3'},
    'expelled': {'uid': 'u4'},
    'admin': {'uid': 'adm', 'is_admin': True},
    'system': {'system': True},
}
ALL = list(CTX)


@pytest.fixture
def scene(world):
    """Reforma `A` de `u1` (participant `u2`, expulsat `u4`) i reforma `B` d'`u3` (sense relació amb ningú més)."""
    a = make_renovation(world.refuge, 'u1', ini=day(5), fin=day(9), participants=['u2'], expelled=['u4'],
                        link='https://t.me/A')
    b = make_renovation(world.refuge2, 'u3', ini=day(5), fin=day(9), link='https://t.me/B')
    world.a, world.b = a, b
    return world


def _run(ctx, statement, params=None):
    with rls_context(**CTX[ctx]):
        with connection.cursor() as cur:
            cur.execute(statement, params)
            return cur.fetchall() if cur.description else cur.rowcount


def _denied(ctx, statement, params=None):
    with pytest.raises(DatabaseError):
        with transaction.atomic():
            _run(ctx, statement, params)


# =============================================== activity.renovations ===============================================

@pytest.mark.parametrize('ctx', ALL)
def test_renovations_select_qualsevol_usuari_autenticat_ho_veu_tot(scene, ctx):
    expected = 0 if ctx == 'anon' else 2
    assert _run(ctx, 'SELECT count(*) FROM activity.renovations')[0][0] == expected


@pytest.mark.parametrize('ctx,allowed', [('anon', False), ('creator', True), ('participant', False), ('other', False),
                                         ('expelled', False), ('admin', False), ('system', True)])
def test_renovations_insert_com_a_creador(scene, ctx, allowed):
    stmt = ('INSERT INTO activity.renovations (refuge_id, creator_uid, ini_date, fin_date, description) '
            'VALUES (%s, %s, %s, %s, %s)')
    params = [scene.refuge.pk, 'u1', day(20), day(21), 'x']
    if allowed:
        _run(ctx, stmt, params)
        assert count_renovations() == 3
        sql("DELETE FROM activity.renovations WHERE description = 'x'")      # sense enllaç: no pot quedar viva al final
    else:
        _denied(ctx, stmt, params)
        assert count_renovations() == 2


@pytest.mark.parametrize('ctx', ['other', 'participant', 'admin'])
def test_renovations_no_es_pot_inserir_en_nom_d_un_altre(scene, ctx):
    """`creator_uid = {U}`: ni tan sols l'admin pot crear una reforma amb un altre creador."""
    _denied(ctx, 'INSERT INTO activity.renovations (refuge_id, creator_uid, ini_date, fin_date, description) '
                 'VALUES (%s, %s, %s, %s, %s)', [scene.refuge.pk, 'u1', day(20), day(21), 'x'])


@pytest.mark.parametrize('ctx,rows', [('anon', 0), ('creator', 1), ('participant', 0), ('other', 0), ('expelled', 0),
                                      ('admin', 0), ('system', 1)])
def test_renovations_update_nomes_creador_o_sistema(scene, ctx, rows):
    assert _run(ctx, "UPDATE activity.renovations SET description = 'nova' WHERE id = %s", [scene.a]) == rows
    new = sql('SELECT description FROM activity.renovations WHERE id = %s', [scene.a])[0][0]
    assert (new == 'nova') == bool(rows)


def test_renovations_update_no_permet_passar_la_reforma_a_un_altre_creador(scene):
    """`WITH CHECK (creator_uid = {U} OR {SYS})`: el creador no pot cedir la reforma."""
    _denied('creator', "UPDATE activity.renovations SET creator_uid = 'u3' WHERE id = %s", [scene.a])


@pytest.mark.parametrize('ctx,rows', [('anon', 0), ('creator', 1), ('participant', 0), ('other', 0), ('expelled', 0),
                                      ('admin', 0), ('system', 1)])
def test_renovations_delete_nomes_creador_o_sistema(scene, ctx, rows):
    assert _run(ctx, 'DELETE FROM activity.renovations WHERE id = %s', [scene.a]) == rows
    assert count_renovations() == 2 - rows


# =============================================== activity.renovation_group_links ===============================================

SEES_LINK_A = {'anon': False, 'creator': True, 'participant': True, 'other': False, 'expelled': False,
               'admin': True, 'system': True}


@pytest.mark.parametrize('ctx', ALL)
def test_group_link_select_nomes_creador_participants_admin_i_sistema(scene, ctx):
    rows = _run(ctx, 'SELECT group_link FROM activity.renovation_group_links ORDER BY group_link')
    seen = {r[0] for r in rows}
    assert ('https://t.me/A' in seen) == SEES_LINK_A[ctx]
    # L'aliè (`u3`) només veu l'enllaç de la seva pròpia reforma; l'admin i el sistema, tots.
    assert ('https://t.me/B' in seen) == (ctx in ('other', 'admin', 'system'))


def test_group_link_un_participant_que_surt_deixa_de_veure_l_enllac(scene):
    assert _run('participant', 'SELECT count(*) FROM activity.renovation_group_links WHERE renovation_id = %s',
                [scene.a])[0][0] == 1
    _run('participant', 'DELETE FROM activity.renovation_participants WHERE renovation_id = %s AND user_uid = %s',
         [scene.a, 'u2'])
    assert _run('participant', 'SELECT count(*) FROM activity.renovation_group_links WHERE renovation_id = %s',
                [scene.a])[0][0] == 0


def test_group_link_un_nou_participant_comença_a_veure_l_enllac(scene):
    assert _run('other', 'SELECT count(*) FROM activity.renovation_group_links WHERE renovation_id = %s',
                [scene.a])[0][0] == 0
    _run('other', 'INSERT INTO activity.renovation_participants (renovation_id, user_uid) VALUES (%s, %s)',
         [scene.a, 'u3'])
    assert _run('other', 'SELECT group_link FROM activity.renovation_group_links WHERE renovation_id = %s',
                [scene.a]) == [('https://t.me/A',)]


@pytest.fixture
def no_link(world):
    """Reforma d'`u1` sense fila d'enllaç encara (el *trigger* diferit mai s'executa dins la transacció del test)."""
    world.c = make_renovation(world.refuge, 'u1', link=None)
    yield world
    # El *trigger* diferit exigeix l'enllaç quan Django verifica les restriccions en acabar el test.
    sql('INSERT INTO activity.renovation_group_links (renovation_id, group_link) VALUES (%s, %s) '
        'ON CONFLICT DO NOTHING', [world.c, 'https://t.me/final'])


@pytest.mark.parametrize('ctx,allowed', [('anon', False), ('creator', True), ('participant', False), ('other', False),
                                         ('expelled', False), ('admin', False), ('system', True)])
def test_group_link_insert_nomes_creador_o_sistema(no_link, ctx, allowed):
    stmt = 'INSERT INTO activity.renovation_group_links (renovation_id, group_link) VALUES (%s, %s)'
    if allowed:
        _run(ctx, stmt, [no_link.c, 'https://t.me/C'])
        assert link_of(no_link.c) == 'https://t.me/C'
    else:
        _denied(ctx, stmt, [no_link.c, 'https://t.me/C'])
        assert link_of(no_link.c) is None


@pytest.mark.parametrize('ctx,rows', [('anon', 0), ('creator', 1), ('participant', 0), ('other', 0), ('expelled', 0),
                                      ('admin', 0), ('system', 1)])
def test_group_link_update_nomes_creador_o_sistema(scene, ctx, rows):
    assert _run(ctx, "UPDATE activity.renovation_group_links SET group_link = 'https://t.me/nou' "
                     "WHERE renovation_id = %s", [scene.a]) == rows
    assert (link_of(scene.a) == 'https://t.me/nou') == bool(rows)


@pytest.mark.parametrize('ctx', ALL)
def test_group_link_delete_denegat_a_tothom_sense_grant(scene, ctx):
    """L'enllaç només s'esborra pel *trigger* `SECURITY DEFINER` o per cascada, mai amb `DELETE` d'`app`."""
    _denied(ctx, 'DELETE FROM activity.renovation_group_links WHERE renovation_id = %s', [scene.a])
    assert link_of(scene.a) == 'https://t.me/A'


# =============================================== activity.renovation_participants ===============================================

@pytest.mark.parametrize('ctx', ALL)
def test_participants_select_qualsevol_autenticat(scene, ctx):
    expected = 0 if ctx == 'anon' else 1
    assert _run(ctx, 'SELECT count(*) FROM activity.renovation_participants')[0][0] == expected


@pytest.mark.parametrize('ctx,uid,allowed', [
    ('anon', 'u3', False), ('other', 'u3', True), ('other', 'adm', False), ('creator', 'u3', False),
    ('admin', 'adm', True), ('admin', 'u3', False), ('system', 'u3', True)])
def test_participants_insert_nomes_un_mateix_o_sistema(scene, ctx, uid, allowed):
    stmt = 'INSERT INTO activity.renovation_participants (renovation_id, user_uid) VALUES (%s, %s)'
    if allowed:
        _run(ctx, stmt, [scene.a, uid])
        assert uid in participants_of(scene.a)
    else:
        _denied(ctx, stmt, [scene.a, uid])
        assert uid not in participants_of(scene.a)


@pytest.mark.parametrize('ctx,rows', [('anon', 0), ('creator', 1), ('participant', 1), ('other', 0), ('expelled', 0),
                                      ('admin', 0), ('system', 1)])
def test_participants_delete_el_propi_el_creador_o_sistema(scene, ctx, rows):
    """Sortir un mateix o expulsar el creador de la reforma."""
    assert _run(ctx, 'DELETE FROM activity.renovation_participants WHERE renovation_id = %s AND user_uid = %s',
                [scene.a, 'u2']) == rows
    assert participants_of(scene.a) == ([] if rows else ['u2'])


def test_participants_el_creador_d_una_altra_reforma_no_pot_expulsar(scene):
    """`u3` és creador de `B`, no d'`A`: no pot treure `u2` d'`A`."""
    assert _run('other', 'DELETE FROM activity.renovation_participants WHERE renovation_id = %s', [scene.a]) == 0
    assert participants_of(scene.a) == ['u2']


@pytest.mark.parametrize('ctx', ALL)
def test_participants_update_denegat_sense_grant(scene, ctx):
    _denied(ctx, "UPDATE activity.renovation_participants SET created_at = now() WHERE renovation_id = %s", [scene.a])


# =============================================== activity.renovation_expelled ===============================================

@pytest.mark.parametrize('ctx,rows', [('anon', 0), ('creator', 1), ('participant', 0), ('other', 0), ('expelled', 1),
                                      ('admin', 1), ('system', 1)])
def test_expelled_select_l_expulsat_el_creador_l_admin_i_sistema(scene, ctx, rows):
    assert _run(ctx, 'SELECT count(*) FROM activity.renovation_expelled WHERE renovation_id = %s', [scene.a])[0][0] == rows


def test_expelled_un_expulsat_nomes_veu_la_seva_fila(scene):
    sql('INSERT INTO activity.renovation_expelled (renovation_id, user_uid) VALUES (%s, %s)', [scene.a, 'u3'])
    assert _run('expelled', 'SELECT user_uid FROM activity.renovation_expelled ORDER BY 1') == [('u4',)]
    assert _run('other', 'SELECT user_uid FROM activity.renovation_expelled ORDER BY 1') == [('u3',)]
    assert [r[0] for r in _run('creator', 'SELECT user_uid FROM activity.renovation_expelled ORDER BY 1')] == ['u3', 'u4']


def test_expelled_el_creador_d_una_altra_reforma_no_veu_les_d_aquesta(scene):
    assert _run('other', 'SELECT count(*) FROM activity.renovation_expelled WHERE renovation_id = %s',
                [scene.a])[0][0] == 0


@pytest.mark.parametrize('ctx,allowed', [('anon', False), ('creator', True), ('participant', False), ('other', False),
                                         ('expelled', False), ('admin', False), ('system', True)])
def test_expelled_insert_nomes_el_creador_o_sistema(scene, ctx, allowed):
    stmt = 'INSERT INTO activity.renovation_expelled (renovation_id, user_uid) VALUES (%s, %s)'
    if allowed:
        _run(ctx, stmt, [scene.a, 'u3'])
        assert 'u3' in expelled_of(scene.a)
    else:
        _denied(ctx, stmt, [scene.a, 'u3'])
        assert 'u3' not in expelled_of(scene.a)


@pytest.mark.parametrize('ctx', ALL)
def test_expelled_delete_i_update_denegats_a_tothom(scene, ctx):
    """Una expulsió és definitiva: només es perd per cascada."""
    _denied(ctx, 'DELETE FROM activity.renovation_expelled WHERE renovation_id = %s', [scene.a])
    _denied(ctx, 'UPDATE activity.renovation_expelled SET expelled_at = now() WHERE renovation_id = %s', [scene.a])
    assert expelled_of(scene.a) == ['u4']


# =============================================== el trigger de guarda salta la RLS ===============================================

def test_un_expulsat_que_intenta_unir_se_rep_l_error_del_trigger_encara_que_no_vegi_res_mes(scene):
    """El *trigger* `SECURITY DEFINER` llegeix `renovation_expelled` com a propietari: l'error és el de l'expulsió
    (no un error de RLS) i l'usuari no veu les files dels altres expulsats."""
    sql('INSERT INTO activity.renovation_expelled (renovation_id, user_uid) VALUES (%s, %s)', [scene.a, 'u3'])
    with pytest.raises(DatabaseError) as exc:
        with transaction.atomic():
            _run('expelled', 'INSERT INTO activity.renovation_participants (renovation_id, user_uid) VALUES (%s, %s)',
                 [scene.a, 'u4'])
    assert constraint_name(exc) == 'renovation_participants_not_expelled_ck'
    assert _run('expelled', 'SELECT user_uid FROM activity.renovation_expelled WHERE renovation_id = %s',
                [scene.a]) == [('u4',)]


def test_el_trigger_de_guarda_no_deixa_unir_se_al_creador_tampoc_sota_rls(scene):
    with pytest.raises(DatabaseError) as exc:
        with transaction.atomic():
            _run('creator', 'INSERT INTO activity.renovation_participants (renovation_id, user_uid) VALUES (%s, %s)',
                 [scene.a, 'u1'])
    assert constraint_name(exc) == 'renovation_participants_not_creator_ck'
