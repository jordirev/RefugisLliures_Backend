"""
RLS amb el rol `app` (§2.18, §2.5-2.7, §7.5): anònim, propi, aliè, admin i sistema.

- `proposals.refuge_proposals`: `SELECT` propi/admin/sistema; `INSERT` només `creator_uid = {U}` i `pending` (o sistema);
  `UPDATE` només admin/sistema (aprovar, rebutjar, rebuig automàtic); cap `DELETE` (ni grant): l'historial no s'esborra.
- Catàleg (`refuges`, `refuge_amenities`, `refuge_links`): escriptura només admin/sistema; un usuari normal no hi escriu
  (tampoc `condition`/`num_contributed_conditions`, que només toca el *trigger* d'experiències i l'aprovació).

Un `INSERT` denegat per la RLS llança error; un `UPDATE`/`DELETE` denegat afecta 0 files; sense grant, error.
"""
import pytest
from django.db import DatabaseError, connection, transaction

from apps.core.rls import rls_context
from apps.proposals.tests.helpers import (
    as_owner, make_proposal, make_refuge, make_user, new_payload, proposal_row, refuge_state, sql)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.rls, pytest.mark.integration,
              pytest.mark.real_permissions]

ANON = {}
OWN = {'uid': 'u1'}
OTHER = {'uid': 'u2'}
ADMIN = {'uid': 'adm', 'is_admin': True}
SYSTEM = {'system': True}
ALL_CTX = {'anon': ANON, 'own': OWN, 'other': OTHER, 'admin': ADMIN, 'system': SYSTEM}
WRITERS = {'admin', 'system'}
INSERT_AS_U1 = {'anon': False, 'own': True, 'other': False, 'admin': False, 'system': True}
POINT = "ST_GeogFromText('SRID=4326;POINT(1.7 42.7)')"


@pytest.fixture
def refuge(world):
    return world[0]


def _run(ctx, statement, params=None):
    with rls_context(**ALL_CTX[ctx]):
        with connection.cursor() as cur:
            cur.execute(statement, params)
            return cur.fetchall() if cur.description else cur.rowcount


def _denied(fn):
    with pytest.raises(DatabaseError):
        with transaction.atomic():
            fn()


# =================================== proposals: SELECT ===================================

@pytest.mark.parametrize('ctx,sees', [('anon', 0), ('own', 1), ('other', 0), ('admin', 1), ('system', 1)])
def test_select_de_la_proposta_d_u1(world, ctx, sees):
    make_proposal(creator='u1')
    assert _run(ctx, 'SELECT count(*) FROM proposals.refuge_proposals')[0][0] == sees


def test_cada_usuari_nomes_veu_les_seves(world):
    make_proposal(creator='u1')
    make_proposal(creator='u2', minutes=1)
    assert _run('own', 'SELECT creator_uid FROM proposals.refuge_proposals') == [('u1',)]
    assert _run('other', 'SELECT creator_uid FROM proposals.refuge_proposals') == [('u2',)]
    assert _run('admin', 'SELECT count(*) FROM proposals.refuge_proposals')[0][0] == 2


def test_proposta_anonima_nomes_la_veuen_admin_i_sistema(world):
    pid = make_proposal(creator=None)
    assert _run('own', 'SELECT count(*) FROM proposals.refuge_proposals WHERE id = %s', [pid])[0][0] == 0
    assert _run('admin', 'SELECT count(*) FROM proposals.refuge_proposals WHERE id = %s', [pid])[0][0] == 1


def test_sense_context_no_es_veu_res_fail_closed(world):
    make_proposal(creator='u1')
    with connection.cursor() as cur:
        cur.execute('SELECT count(*) FROM proposals.refuge_proposals')
        assert cur.fetchone() == (0,)


# =================================== proposals: INSERT ===================================

INSERT = ("INSERT INTO proposals.refuge_proposals (action, status, payload, creator_uid) "
          "VALUES ('create', %s, %s::jsonb, %s)")
PAYLOAD = '{"name": "x", "coord": {"lat": 1, "long": 1}}'


@pytest.mark.parametrize('ctx', ALL_CTX)
def test_insert_amb_creator_u1(world, ctx):
    def go():
        _run(ctx, INSERT, ['pending', PAYLOAD, 'u1'])
    if INSERT_AS_U1[ctx]:
        go()
        assert sql('SELECT count(*) FROM proposals.refuge_proposals') == [(1,)]
    else:
        _denied(go)
        assert sql('SELECT count(*) FROM proposals.refuge_proposals') == [(0,)]


def test_l_admin_pot_proposar_en_nom_propi(world):
    _run('admin', INSERT, ['pending', PAYLOAD, 'adm'])


def test_un_usuari_no_pot_inserir_una_proposta_ja_aprovada(world):
    _denied(lambda: _run('own', "INSERT INTO proposals.refuge_proposals (action, status, payload, creator_uid, "
                                "reviewer_uid, reviewed_at) VALUES ('create', 'approved', %s::jsonb, 'u1', 'u1', now())",
                         [PAYLOAD]))


def test_insert_amb_returning_sota_rls(world):
    rows = _run('own', INSERT + ' RETURNING id, created_at', ['pending', PAYLOAD, 'u1'])
    assert len(rows) == 1 and rows[0][0] is not None


# =================================== proposals: UPDATE / DELETE ===================================

@pytest.mark.parametrize('ctx', ALL_CTX)
def test_update_nomes_admin_o_sistema(world, ctx):
    pid = make_proposal(creator='u1')
    n = _run(ctx, "UPDATE proposals.refuge_proposals SET status = 'rejected', reviewed_at = now(), "
                  "reviewer_uid = NULL WHERE id = %s", [pid])
    if ctx in WRITERS:
        assert n == 1 and proposal_row(pid)['status'] == 'rejected'
    else:
        assert n == 0 and proposal_row(pid)['status'] == 'pending'


def test_el_creador_no_pot_aprovar_la_seva_proposta(world):
    pid = make_proposal(creator='u1')
    assert _run('own', "UPDATE proposals.refuge_proposals SET status = 'approved', reviewer_uid = 'u1', "
                       "reviewed_at = now() WHERE id = %s", [pid]) == 0


@pytest.mark.parametrize('ctx', ALL_CTX)
def test_cap_delete_ni_per_a_admin_ni_sistema(world, ctx):
    pid = make_proposal(creator='u1')
    _denied(lambda: _run(ctx, 'DELETE FROM proposals.refuge_proposals WHERE id = %s', [pid]))
    assert proposal_row(pid) is not None


# =================================== catàleg: escriptura ===================================

@pytest.mark.parametrize('ctx', ALL_CTX)
def test_insert_de_refugi_nomes_admin_o_sistema(world, ctx):
    def go():
        _run(ctx, f'INSERT INTO refuges.refuges (name, coord) VALUES (%s, {POINT})', ['Nou'])
    if ctx in WRITERS:
        go()
        assert sql("SELECT count(*) FROM refuges.refuges WHERE name = 'Nou'") == [(1,)]
    else:
        _denied(go)
        assert sql("SELECT count(*) FROM refuges.refuges WHERE name = 'Nou'") == [(0,)]


@pytest.mark.parametrize('ctx', ALL_CTX)
def test_update_de_refugi_incloent_la_condicio_nomes_admin_o_sistema(refuge, ctx):
    n = _run(ctx, 'UPDATE refuges.refuges SET altitude = 1234, condition = 3, num_contributed_conditions = 9 '
                  'WHERE id = %s', [refuge.pk])
    state = refuge_state(refuge.pk)
    if ctx in WRITERS:
        assert n == 1 and (state['altitude'], state['condition'], state['n']) == (1234, 3, 9)
    else:
        assert n == 0 and (state['altitude'], state['condition'], state['n']) == (2000, None, 0)


@pytest.mark.parametrize('ctx', ALL_CTX)
def test_delete_de_refugi_nomes_admin_o_sistema(refuge, ctx):
    n = _run(ctx, 'DELETE FROM refuges.refuges WHERE id = %s', [refuge.pk])
    assert n == (1 if ctx in WRITERS else 0)
    assert (refuge_state(refuge.pk) is None) == (ctx in WRITERS)


@pytest.mark.parametrize('ctx', ALL_CTX)
def test_serveis_i_enllacos_nomes_admin_o_sistema(world, ctx):
    r = make_refuge(name='Amb enllaç', lat=44, links=['https://a.test/1'])
    upd = _run(ctx, 'UPDATE refuges.refuge_amenities SET eau = true WHERE refuge_id = %s', [r.pk])
    lupd = _run(ctx, 'UPDATE refuges.refuge_links SET position = 5 WHERE refuge_id = %s', [r.pk])
    assert (upd, lupd) == ((1, 1) if ctx in WRITERS else (0, 0))

    def add_link():
        _run(ctx, "INSERT INTO refuges.refuge_links (url, refuge_id, position) VALUES ('https://a.test/2', %s, 9)",
             [r.pk])
    if ctx in WRITERS:
        add_link()
    else:
        _denied(add_link)
    ldel = _run(ctx, 'DELETE FROM refuges.refuge_links WHERE refuge_id = %s', [r.pk])
    adel = _run(ctx, 'DELETE FROM refuges.refuge_amenities WHERE refuge_id = %s', [r.pk])
    assert (ldel, adel) == ((2, 1) if ctx in WRITERS else (0, 0))


def test_insert_de_serveis_nomes_admin_o_sistema(world):
    r = make_refuge(name='Sense serveis', lat=44.5)
    with as_owner():
        with connection.cursor() as cur:
            cur.execute('DELETE FROM refuges.refuge_amenities WHERE refuge_id = %s', [r.pk])
    for ctx in ('anon', 'own', 'other'):
        _denied(lambda ctx=ctx: _run(ctx, 'INSERT INTO refuges.refuge_amenities (refuge_id) VALUES (%s)', [r.pk]))
    _run('admin', 'INSERT INTO refuges.refuge_amenities (refuge_id) VALUES (%s)', [r.pk])


def test_el_cataleg_de_tipus_continua_sense_escriptura(world):
    for ctx in ALL_CTX:
        _denied(lambda ctx=ctx: _run(ctx, "INSERT INTO refuges.refuge_types (code) VALUES ('nou')"))
