"""
Comanda `python manage.py purge_audit_logs` (chunk 9; §2.24, §8.3, D40 (2)): retenció d'`audit.audit_logs`.

Contracte:
- Comanda a `apps/audit/management/commands/purge_audit_logs.py`; delega en
  `apps.audit.services.purge_expired(batch_size=5000) -> int` (files esborrades), amb `system_context()` propi (job: no hi
  ha petició ni context de RLS).
- Esborra les files amb `expire_at < now()` en lots de 5.000 fins que no en queden. Les `legal_hold` porten
  `expire_at = created_at + 5 anys`, de manera que **mai** s'esborren abans dels 5 anys i sí quan caduquen.
- Sortida: «Entrades d'auditoria purgades: N». Si falla: `CommandError` (codi != 0, D28), missatge fix i traça al log.
- **No està planificada** (TECH_DEBT R18). Cap efecte sobre altres taules.
"""
import logging
from io import StringIO
from unittest import mock

import pytest
from django.core.management import call_command, get_commands
from django.core.management.base import CommandError
from django.db import DatabaseError, connection
from django.test.utils import CaptureQueriesContext

from apps.moderation.tests.helpers import sql

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.integration, pytest.mark.real_permissions]


def run():
    out = StringIO()
    call_command('purge_audit_logs', stdout=out)
    return out.getvalue()


def seed(created_days_ago, expire_days_ahead, *, hold=False, actor='u1', action='media.list'):
    rows = sql("INSERT INTO audit.audit_logs (actor_uid, action, legal_hold, created_at, expire_at) "
               "VALUES (%s, %s, %s, now() - make_interval(days => %s), now() + make_interval(days => %s)) RETURNING id",
               [actor, action, hold, created_days_ago, expire_days_ahead])
    return str(rows[0][0])


def ids():
    return {str(r[0]) for r in sql('SELECT id FROM audit.audit_logs')}


def test_la_comanda_viu_a_apps_audit():
    assert get_commands()['purge_audit_logs'] == 'apps.audit'


def test_esborra_els_caducats_i_conserva_la_resta(world):
    old = [seed(400, -35), seed(366, -1, action='media.report')]
    fresh = [seed(10, 355), seed(364, 1)]
    out = run()
    assert "Entrades d'auditoria purgades: 2" in out
    assert ids() == set(fresh)
    assert not set(old) & ids()


def test_legal_hold_no_s_esborra_abans_dels_cinc_anys_i_si_despres(world):
    young_hold = seed(400, 1426, hold=True, action='moderation.hash_block')          # 400 d + 1426 d = 5 anys
    old_hold = seed(1830, -4, hold=True, action='moderation.hash_block')
    normal_expired = seed(500, -135)
    run()
    assert ids() == {young_hold}
    assert old_hold not in ids() and normal_expired not in ids()


def test_files_de_sistema_sense_actor_tambe_es_purguen(world):
    gone = seed(400, -35, actor=None, action='moderation.auto_hide')
    run()
    assert gone not in ids()


def test_idempotent_i_sense_res_a_purgar(world):
    seed(400, -35)
    run()
    assert "purgades: 0" in run()
    assert "purgades: 0" in run()


def test_esborra_per_lots_de_5000(world):
    sql("INSERT INTO audit.audit_logs (actor_uid, action, created_at, expire_at) "
        "SELECT 'u1', 'media.list', now() - interval '400 days', now() - interval '35 days' FROM generate_series(1, 12000)")
    keep = seed(1, 364)
    with CaptureQueriesContext(connection) as q:
        out = run()
    assert "Entrades d'auditoria purgades: 12000" in out
    deletes = [x['sql'] for x in q.captured_queries if x['sql'].lstrip().upper().startswith('DELETE')]
    assert 3 <= len(deletes) <= 4, len(deletes)                                   # 5000 + 5000 + 2000 (+ un lot buit)
    assert ids() == {keep}


def test_el_service_retorna_el_nombre_d_esborrats_amb_lots_petits(world, audit):
    for _ in range(5):
        seed(400, -35)
    assert audit.purge_expired(batch_size=2) == 5
    assert audit.purge_expired(batch_size=2) == 0


def test_funciona_sense_context_de_rls(world):
    seed(400, -35)
    with connection.cursor() as cur:
        cur.execute("SELECT current_setting('app.is_system', true)")
        assert cur.fetchone()[0] in (None, '', 'false')
    assert 'purgades: 1' in run()


def test_no_toca_altres_taules(world):
    seed(400, -35)
    run()
    assert sql('SELECT count(*) FROM users.users') == [(4,)]


def test_surt_amb_error_si_falla(world, caplog):
    with mock.patch('apps.audit.services.purge_expired', side_effect=RuntimeError('secret de bd')), \
            caplog.at_level(logging.ERROR):
        with pytest.raises(CommandError) as err:
            run()
    assert 'secret' not in str(err.value)
    assert any(r.exc_info for r in caplog.records)


def test_surt_amb_error_si_la_bd_falla_de_debo(world):
    def boom(execute, sql_, params, many, context):
        if sql_.lstrip().upper().startswith('DELETE'):
            raise DatabaseError('fallada simulada')
        return execute(sql_, params, many, context)

    keep = seed(400, -35)
    with connection.execute_wrapper(boom), pytest.raises(CommandError):
        run()
    assert ids() == {keep}
