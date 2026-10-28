"""
Comanda `python manage.py purge_moderation` (chunk 9; §8.3, D40 (2)): retenció de denúncies i avisos.

Contracte:
- Comanda a `apps/moderation/management/commands/purge_moderation.py`; delega en
  `apps.moderation.services.purge_expired(batch_size=5000) -> dict` (`{'reports': n, 'notices': m}`), que s'executa amb
  `system_context()` propi (és un job: no hi ha petició ni context de RLS).
- Denúncies **no** `legal_hold`: s'esborren 24 mesos després de **resoldre's**; les pendents no s'esborren mai.
  Denúncies `legal_hold`: 5 anys després de la resolució (o de la creació si no s'han resolt).
- Avisos: 24 mesos després de crear-se (es creen en resoldre), **excepte** els lligats a una denúncia `legal_hold`
  encara vigent; aquests cauen quan caduca la denúncia (5 anys). `moderation_notices` no té columna `legal_hold`.
- Per lots de `batch_size` (5.000 per defecte); idempotent.
- Sortida: «Denúncies purgades: N» i «Avisos purgats: M». Si falla: `CommandError` (codi de sortida != 0, com D28) amb
  un missatge fix (sense el text de l'excepció) i la traça al log.
- Cap efecte sobre `refuge_media`, R2, `audit_logs` ni usuaris. **No està planificada** (TECH_DEBT R18).
"""
import logging
from datetime import timedelta
from io import StringIO
from unittest import mock

import pytest
from django.core.management import call_command, get_commands
from django.core.management.base import CommandError
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.moderation.tests.helpers import (
    count_reports, make_notice, make_report, notice_rows, now_minus, report_row, sql)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.integration, pytest.mark.real_permissions]

MONTH = timedelta(days=30)


def ago(months):
    return now_minus(days=30 * months)


def run():
    out = StringIO()
    call_command('purge_moderation', stdout=out)
    return out.getvalue()


def resolved(world, key, months, *, hold=False, reporter='u2', reason='hate_speech'):
    created = ago(months + 1)
    return make_report(world[0], key, reporter, reason, creator='u1', status='resolved', created_at=created,
                       resolved_at=ago(months), legal_hold=hold)


def pending(world, key, months, *, hold=False, reporter='u2', reason='hate_speech'):
    return make_report(world[0], key, reporter, reason, creator='u1', created_at=ago(months), legal_hold=hold)


def test_la_comanda_viu_a_apps_moderation():
    assert get_commands()['purge_moderation'] == 'apps.moderation'


def test_denuncies_no_legal_hold_24_mesos_despres_de_resoldre(world):
    old = resolved(world, 'k1', 25)
    recent = resolved(world, 'k2', 23)
    old_pending = pending(world, 'k3', 40)
    out = run()
    assert 'Denúncies purgades: 1' in out
    assert report_row(old) is None
    assert report_row(recent) is not None and report_row(old_pending) is not None      # les pendents no caduquen


def test_denuncies_legal_hold_cinc_anys_despres_de_resoldre_o_de_crear(world):
    kept_resolved = resolved(world, 'k1', 30, hold=True, reason='child_sexual_abuse')
    gone_resolved = resolved(world, 'k2', 62, hold=True, reason='child_sexual_abuse')
    kept_pending = pending(world, 'k3', 40, hold=True, reason='child_sexual_abuse')
    gone_pending = pending(world, 'k4', 62, hold=True, reason='child_sexual_abuse')
    auto_gone = make_report(world[0], 'moderation-hold/a', None, 'child_sexual_abuse', source='automatic',
                            created_at=ago(62), creator='u1')
    out = run()
    assert 'Denúncies purgades: 3' in out
    assert report_row(kept_resolved) is not None and report_row(kept_pending) is not None
    for rid in (gone_resolved, gone_pending, auto_gone):
        assert report_row(rid) is None


def test_una_legal_hold_anonimitzada_es_purga_igual_als_cinc_anys(world):
    rid = make_report(world[0], 'k1', None, 'child_sexual_abuse', created_at=ago(62), anonymized_at=ago(61),
                      legal_hold=True, creator=None)
    run()
    assert report_row(rid) is None


def test_la_resolucio_i_no_la_creacio_marca_el_termini_de_24_mesos(world):
    """Creada fa 30 mesos però resolta fa 5: es conserva."""
    rid = make_report(world[0], 'k1', 'u2', creator='u1', status='resolved', created_at=ago(30), resolved_at=ago(5))
    run()
    assert report_row(rid) is not None


def test_avisos_24_mesos_i_els_lligats_a_legal_hold_cinc_anys(world):
    r = world[0]
    hold_alive = resolved(world, 'k1', 30, hold=True, reason='child_sexual_abuse')
    hold_dead = resolved(world, 'k2', 62, hold=True, reason='child_sexual_abuse')
    plain_dead = resolved(world, 'k3', 25)
    free_old = make_notice('u1', created_at=ago(25))
    free_recent = make_notice('u1', created_at=ago(23))
    of_plain = make_notice('u1', report_id=plain_dead, created_at=ago(25))
    of_hold_alive = make_notice('u1', 'account_blocked', report_id=hold_alive, created_at=ago(30))
    of_hold_dead = make_notice('u1', 'account_blocked', report_id=hold_dead, created_at=ago(62))
    out = run()
    left = {n['id'] for n in notice_rows('u1')}
    assert left == {free_recent, of_hold_alive}, left
    assert 'Avisos purgats: 3' in out and 'Denúncies purgades: 2' in out
    assert report_row(hold_alive) is not None and report_row(hold_dead) is None and report_row(plain_dead) is None


def test_un_avis_ja_desvinculat_d_una_denuncia_purgada_cau_pel_termini_de_24_mesos(world):
    rid = resolved(world, 'k1', 25)
    make_notice('u1', report_id=rid, created_at=ago(25))
    run()
    assert report_row(rid) is None and notice_rows('u1') == []


def test_idempotent_i_sense_res_a_purgar(world):
    resolved(world, 'k1', 25)
    make_notice('u1', created_at=ago(30))
    run()
    out = run()
    assert 'Denúncies purgades: 0' in out and 'Avisos purgats: 0' in out
    assert 'Denúncies purgades: 0' in run()


def test_no_toca_mitjans_ni_usuaris(world):
    from apps.moderation.tests.helpers import make_media
    make_media(world[0], 'u1', key='k1')
    resolved(world, 'k1', 25)
    run()
    assert sql('SELECT count(*) FROM refuges.refuge_media') == [(1,)]
    assert sql('SELECT count(*) FROM users.users') == [(7,)]


def test_esborra_per_lots_de_5000(world):
    sql("INSERT INTO moderation.media_reports (refuge_id, media_key, reporter_uid, reason, status, created_at, "
        "resolved_at, action, statement) SELECT %s, 'k' || g, 'u2', 'hate_speech', 'resolved', now() - interval "
        "'30 months', now() - interval '26 months', 'remove', 'x' FROM generate_series(1, 12000) g", [world[0].pk])
    keep = pending(world, 'kept', 1)
    with CaptureQueriesContext(connection) as q:
        out = run()
    assert 'Denúncies purgades: 12000' in out
    deletes = [x['sql'] for x in q.captured_queries
               if x['sql'].lstrip().upper().startswith('DELETE') and 'media_reports' in x['sql']]
    assert 3 <= len(deletes) <= 4, len(deletes)                                     # 5000 + 5000 + 2000 (+ un lot buit)
    assert report_row(keep) is not None and count_reports() == 1


def test_el_service_accepta_un_batch_size_petit_i_retorna_els_recomptes(world, services):
    for i in range(5):
        resolved(world, f'k{i}', 25)
    make_notice('u1', created_at=ago(30))
    make_notice('u1', created_at=ago(30))
    out = services.purge_expired(batch_size=2)
    assert out == {'reports': 5, 'notices': 2}
    assert services.purge_expired(batch_size=2) == {'reports': 0, 'notices': 0}


def test_funciona_sense_context_de_rls(world):
    resolved(world, 'k1', 25)
    with connection.cursor() as cur:
        cur.execute("SELECT current_setting('app.is_system', true)")
        assert cur.fetchone()[0] in (None, '', 'false')
    assert 'purgades: 1' in run()


def test_surt_amb_error_si_falla(world, caplog):
    with mock.patch('apps.moderation.services.purge_expired', side_effect=RuntimeError('secret de bd')), \
            caplog.at_level(logging.ERROR):
        with pytest.raises(CommandError) as err:
            run()
    assert 'secret' not in str(err.value)
    assert any(r.exc_info for r in caplog.records)


def test_surt_amb_error_si_la_bd_falla_de_debo(world):
    from django.db import DatabaseError

    def boom(execute, sql_, params, many, context):
        if sql_.lstrip().upper().startswith('DELETE'):
            raise DatabaseError('fallada simulada')
        return execute(sql_, params, many, context)

    resolved(world, 'k1', 25)
    with connection.execute_wrapper(boom), pytest.raises(CommandError):
        run()
    assert count_reports() == 1
