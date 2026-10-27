"""
Comanda `python manage.py purge_upload_intents` (chunk 7; §2.19, §8.3: retenció d'1 dia, purga horària).

Contracte:
- Comanda a `apps/uploads/management/commands/purge_upload_intents.py`; delega en
  `apps.uploads.services.purge_expired_intents(batch_size=1000) -> int` (intents esborrats), que s'executa amb
  `system_context()` propi (no hi ha usuari: es pot cridar sense cap context de RLS).
- Esborra els intents amb `expire_at < now()` (qualsevol estat) en lots de 1.000 (`DELETE … WHERE id IN (SELECT … LIMIT
  1000)`), fins que no en queda cap; conserva els no caducats.
- Sortida: «Intents de pujada purgats: N».
- Si falla: `CommandError` (codi de sortida != 0, com D28) amb un missatge fix (sense el text de l'excepció), traça al log.
- No toca R2 (el lifecycle de `quarantine/` ja l'esborra al cap d'1 dia) ni cap altra taula.
"""
from datetime import timedelta
from io import StringIO
from unittest import mock

import pytest
from django.core.management import call_command, get_commands
from django.core.management.base import CommandError
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.experiences.tests.helpers import make_experience
from apps.uploads.tests.helpers import intent_ids, make_intent, sql

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.integration, pytest.mark.real_permissions]

EXPIRED = dict(created_ago=timedelta(days=3), expires_in=-timedelta(days=1))


def run():
    out = StringIO()
    call_command('purge_upload_intents', stdout=out)
    return out.getvalue()


def test_la_comanda_viu_a_apps_uploads():
    assert get_commands()['purge_upload_intents'] == 'apps.uploads'


def test_esborra_els_caducats_de_qualsevol_estat_i_conserva_la_resta(world):
    old = [make_intent('u1', 'avatar', **EXPIRED),
           make_intent('u1', 'avatar', status='confirmed', result_key='k/a.webp', **EXPIRED),
           make_intent('u2', 'avatar', status='failed', failure_reason='too_large', **EXPIRED)]
    fresh = [make_intent('u1', 'avatar'), make_intent('u2', 'avatar', expires_in=timedelta(minutes=1))]
    out = run()
    assert 'Intents de pujada purgats: 3' in out
    assert sorted(intent_ids()) == sorted(fresh) and not set(old) & set(intent_ids())


def test_no_esborra_un_intent_que_caduca_en_el_futur_proper(world):
    keep = make_intent('u1', 'avatar', created_ago=timedelta(hours=23), expires_in=timedelta(seconds=30))
    run()
    assert intent_ids() == [keep]


def test_sense_res_a_purgar(world):
    assert 'Intents de pujada purgats: 0' in run()


def test_idempotent(world):
    make_intent('u1', 'avatar', **EXPIRED)
    run()
    assert 'Intents de pujada purgats: 0' in run()


def test_esborra_per_lots_de_1000(world):
    sql("INSERT INTO moderation.upload_intents (user_uid, target, content_type, size, quarantine_key, "
        "rights_confirmed_at, created_at, expire_at) "
        "SELECT 'u1', 'avatar', 'image/png', 5, 'quarantine/bulk-' || g, now(), now() - interval '3 days', "
        "now() - interval '1 day' FROM generate_series(1, 2500) g")
    keep = make_intent('u2', 'avatar')
    with CaptureQueriesContext(connection) as q:
        out = run()
    assert 'Intents de pujada purgats: 2500' in out
    deletes = [x['sql'] for x in q.captured_queries if x['sql'].lstrip().upper().startswith('DELETE')]
    assert 3 <= len(deletes) <= 4, len(deletes)                                   # 1000 + 1000 + 500 (+ un lot buit)
    assert intent_ids() == [keep]


def test_funciona_sense_context_de_rls(world):
    """És un job: no hi ha petició ni hook; ha de posar el seu `system_context()` (si no, la RLS no deixaria esborrar)."""
    make_intent('u1', 'avatar', **EXPIRED)
    with connection.cursor() as cur:
        cur.execute("SELECT current_setting('app.is_system', true)")
        assert cur.fetchone()[0] in (None, '', 'false')
    assert 'purgats: 1' in run()


def test_no_toca_r2_ni_altres_taules(world, r2store):
    r = world[0]
    e = make_experience(r, 'u1')
    make_intent('u1', 'experience', refuge=r, experience_id=e, **EXPIRED)
    run()
    assert r2store.deletes == [] and sql('SELECT count(*) FROM activity.experiences') == [(1,)]


def test_surt_amb_error_si_falla(world, caplog):
    import logging
    with mock.patch('apps.uploads.services.purge_expired_intents', side_effect=RuntimeError('secret de bd')), \
            caplog.at_level(logging.ERROR):
        with pytest.raises(CommandError) as err:
            run()
    assert 'secret' not in str(err.value)
    assert any(r.exc_info for r in caplog.records)                               # la traça va al log


def test_surt_amb_error_si_la_bd_falla_de_debo(world):
    from django.db import DatabaseError

    def boom(execute, sql_, params, many, context):
        if sql_.lstrip().upper().startswith('DELETE'):
            raise DatabaseError('fallada simulada')
        return execute(sql_, params, many, context)

    make_intent('u1', 'avatar', **EXPIRED)
    with connection.execute_wrapper(boom), pytest.raises(CommandError):
        run()
    assert len(intent_ids()) == 1


def test_el_service_retorna_el_nombre_d_esborrats(world, services):
    make_intent('u1', 'avatar', **EXPIRED)
    make_intent('u1', 'avatar', **EXPIRED)
    assert services.purge_expired_intents() == 2
    assert services.purge_expired_intents() == 0


def test_el_service_accepta_un_batch_size_petit(world, services):
    for _ in range(5):
        make_intent('u1', 'avatar', **EXPIRED)
    assert services.purge_expired_intents(batch_size=2) == 5 and intent_ids() == []
