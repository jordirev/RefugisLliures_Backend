"""
RLS de `moderation.media_reports`, `moderation_notices` i `moderation_hash_blocklist` amb el rol `app` (§2.20–§2.22,
§7.5): anònim, propi, aliè, admin i sistema.

- `media_reports`: SELECT denunciant/admin/sistema; INSERT `reporter_uid = {U}` + `source='user'` + `status='pending'`
  o sistema (automàtiques); UPDATE (resolució) admin/sistema; DELETE només sistema (purga).
- `moderation_notices`: SELECT l'afectat/admin/sistema; INSERT admin/sistema (un usuari no es pot escriure avisos);
  DELETE només sistema; cap UPDATE.
- `moderation_hash_blocklist`: res per a `app`, ni el sistema; només `fn_hash_match`.
Un `INSERT` denegat per la RLS llança error; un `SELECT`/`UPDATE`/`DELETE` denegat afecta 0 files.
"""
import pytest
from django.db import DatabaseError, connection, transaction

from apps.core.rls import rls_context
from apps.moderation.tests.helpers import (
    count_reports, make_hash, make_notice, make_report, notice_rows, report_row, sql)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.rls, pytest.mark.integration,
              pytest.mark.real_permissions]

ANON = {}
OWN = {'uid': 'u2'}              # denunciant
OTHER = {'uid': 'u3'}
ADMIN = {'uid': 'adm', 'is_admin': True}
SYSTEM = {'system': True}
ALL_CTX = {'anon': ANON, 'own': OWN, 'other': OTHER, 'admin': ADMIN, 'system': SYSTEM}
KEY = 'refugis-lliures/x/m1.webp'


def _run(ctx, statement, params=None):
    with rls_context(**ALL_CTX[ctx]):
        with connection.cursor() as cur:
            cur.execute(statement, params)
            return cur.fetchall() if cur.description else cur.rowcount


def _denied(fn):
    with pytest.raises(DatabaseError):
        with transaction.atomic():
            fn()


def _no_privilege(fn):
    """Denegat per falta de privilegi (`insufficient_privilege`, 42501), no per qualsevol altre error."""
    with pytest.raises(DatabaseError) as err:
        with transaction.atomic():
            fn()
    assert getattr(err.value.__cause__, 'sqlstate', None) == '42501', err.value


# =================================== media_reports ===================================

@pytest.mark.parametrize('ctx,sees', [('anon', False), ('own', True), ('other', False), ('admin', True),
                                      ('system', True)])
def test_select_de_denuncies(world, ctx, sees):
    make_report(world[0], KEY, 'u2')
    rows = _run(ctx, 'SELECT id FROM moderation.media_reports')
    assert (len(rows) == 1) is sees


def test_select_nomes_veu_les_pròpies_del_denunciant(world):
    make_report(world[0], KEY, 'u2')
    make_report(world[0], KEY, 'u3')
    assert len(_run('own', 'SELECT id FROM moderation.media_reports')) == 1
    assert len(_run('admin', 'SELECT id FROM moderation.media_reports')) == 2


INSERT_REPORT = ("INSERT INTO moderation.media_reports (refuge_id, media_key, reporter_uid, reason, {extra}) "
                 "VALUES (%s, %s, %s, 'hate_speech', {marks}) RETURNING id")


@pytest.mark.parametrize('ctx,ok', [('anon', False), ('own', True), ('other', False), ('admin', False),
                                    ('system', True)])
def test_insert_de_denuncia_com_a_u2(world, ctx, ok):
    stmt = INSERT_REPORT.format(extra="source", marks="'user'")
    if ok:
        assert len(_run(ctx, stmt, [world[0].pk, KEY, 'u2'])) == 1
    else:
        _denied(lambda: _run(ctx, stmt, [world[0].pk, KEY, 'u2']))
    assert count_reports() == (1 if ok else 0)


def test_insert_no_pot_posar_estat_resolt_ni_source_automatic_un_usuari(world):
    _denied(lambda: _run('own', "INSERT INTO moderation.media_reports (refuge_id, media_key, reporter_uid, reason, "
                                "source, status, resolved_at, action, statement) VALUES (%s, %s, 'u2', 'hate_speech', "
                                "'user', 'resolved', now(), 'remove', 'x')", [world[0].pk, KEY]))
    _denied(lambda: _run('own', "INSERT INTO moderation.media_reports (refuge_id, media_key, reason, source) "
                                "VALUES (%s, %s, 'child_sexual_abuse', 'automatic')", [world[0].pk, KEY]))
    assert count_reports() == 0


def test_el_sistema_pot_crear_automatiques(world):
    _run('system', "INSERT INTO moderation.media_reports (refuge_id, media_key, reason, source, legal_hold) "
                   "VALUES (%s, 'moderation-hold/a', 'child_sexual_abuse', 'automatic', true)", [world[0].pk])
    assert count_reports() == 1


UPDATE_REPORT = ("UPDATE moderation.media_reports SET status = 'resolved', resolved_at = now(), action = 'remove', "
                 "statement = 'x' WHERE id = %s")


@pytest.mark.parametrize('ctx,ok', [('anon', False), ('own', False), ('other', False), ('admin', True),
                                    ('system', True)])
def test_update_de_resolucio_nomes_admin_o_sistema(world, ctx, ok):
    rid = make_report(world[0], KEY, 'u2')
    assert _run(ctx, UPDATE_REPORT, [rid]) == (1 if ok else 0)
    assert (report_row(rid)['status'] == 'resolved') is ok


@pytest.mark.parametrize('ctx,ok', [('anon', False), ('own', False), ('other', False), ('admin', False),
                                    ('system', True)])
def test_delete_de_denuncia_nomes_sistema(world, ctx, ok):
    rid = make_report(world[0], KEY, 'u2')
    assert _run(ctx, 'DELETE FROM moderation.media_reports WHERE id = %s', [rid]) == (1 if ok else 0)
    assert (report_row(rid) is None) is ok


# =================================== moderation_notices ===================================

@pytest.mark.parametrize('ctx,sees', [('anon', False), ('own', False), ('other', False), ('admin', True),
                                      ('system', True)])
def test_select_d_avisos_d_u1(world, ctx, sees):
    make_notice('u1')
    assert (len(_run(ctx, 'SELECT id FROM moderation.moderation_notices')) == 1) is sees


def test_l_afectat_veu_els_seus_avisos_i_no_els_dels_altres(world):
    make_notice('u1')
    make_notice('u2')
    assert [r[0] for r in _run('own', 'SELECT user_uid FROM moderation.moderation_notices')] == ['u2']


INSERT_NOTICE = ("INSERT INTO moderation.moderation_notices (user_uid, type, statement) "
                 "VALUES ('u1', 'content_removed', 'x')")


@pytest.mark.parametrize('ctx,ok', [('anon', False), ('own', False), ('other', False), ('admin', True),
                                    ('system', True)])
def test_insert_d_avisos_nomes_admin_o_sistema(world, ctx, ok):
    if ok:
        _run(ctx, INSERT_NOTICE)
    else:
        _denied(lambda: _run(ctx, INSERT_NOTICE))
    assert len(notice_rows()) == (1 if ok else 0)


def test_un_usuari_no_es_pot_escriure_un_avis_a_si_mateix(world):
    _denied(lambda: _run('own', "INSERT INTO moderation.moderation_notices (user_uid, type, statement) "
                                "VALUES ('u2', 'content_restored', 'x')"))


@pytest.mark.parametrize('ctx,ok', [('anon', False), ('own', False), ('other', False), ('admin', False),
                                    ('system', True)])
def test_delete_d_avisos_nomes_sistema(world, ctx, ok):
    nid = make_notice('u2')
    assert _run(ctx, 'DELETE FROM moderation.moderation_notices WHERE id = %s', [nid]) == (1 if ok else 0)


@pytest.mark.parametrize('ctx', ['own', 'admin', 'system'])
def test_cap_update_d_avisos_ni_el_sistema(world, ctx):
    """Sense privilegi `UPDATE` (§7.2): l'avís és immutable."""
    nid = make_notice('u2')
    _no_privilege(lambda: _run(ctx, "UPDATE moderation.moderation_notices SET statement = 'canviat' WHERE id = %s", [nid]))


# =================================== moderation_hash_blocklist ===================================

@pytest.mark.parametrize('ctx', list(ALL_CTX))
def test_la_llista_de_hashes_es_il_legible_per_a_tots_els_contextos(world, ctx):
    make_hash(sha256='a' * 64)
    _no_privilege(lambda: _run(ctx, 'SELECT * FROM moderation.moderation_hash_blocklist'))


@pytest.mark.parametrize('ctx', list(ALL_CTX))
def test_la_llista_de_hashes_no_es_pot_escriure(world, ctx):
    _no_privilege(lambda: _run(ctx, "INSERT INTO moderation.moderation_hash_blocklist (sha256, source) VALUES (%s, 'x')",
                               ['b' * 64]))
    _no_privilege(lambda: _run(ctx, 'DELETE FROM moderation.moderation_hash_blocklist'))


@pytest.mark.parametrize('ctx', list(ALL_CTX))
def test_fn_hash_match_es_cridable_des_de_qualsevol_context(world, ctx):
    make_hash(sha256='c' * 64)
    rows = _run(ctx, 'SELECT entry_id, category, match_type FROM moderation.fn_hash_match(%s, NULL)', ['c' * 64])
    assert [(r[1], r[2]) for r in rows] == [('csam', 'sha256')]


# =================================== cascades amb el rol app (inferència de §2) ===================================

def test_esborrar_l_usuari_amb_el_seu_context_no_el_bloqueja_la_rls_de_les_taules_de_moderacio(world):
    """§7.5.2: `DELETE FROM users.users` amb el rol `app` cascadeja avisos i denúncies del denunciant."""
    make_report(world[0], KEY, 'u2')
    make_notice('u2')
    keep = make_report(world[0], KEY, 'u3')
    make_notice('u3')
    with rls_context(uid='u2'):
        with connection.cursor() as cur:
            cur.execute('DELETE FROM users.users WHERE uid = %s', ['u2'])
    assert [n['user_uid'] for n in notice_rows()] == ['u3']
    assert [str(r[0]) for r in sql('SELECT id FROM moderation.media_reports')] == [keep]
