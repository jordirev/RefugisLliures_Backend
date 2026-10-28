"""
Job diari `python manage.py process_yesterday_visits` (chunk 4; recepta 9 i §8.3 del disseny; guia daily-visits-process).

Contracte:
- Comanda a `apps/visits/management/commands/process_yesterday_visits.py` (la de `api/management/commands` desapareix);
  delega en `apps.visits.services`:
    `process_yesterday_visits() -> dict` amb `processed_visits`, `deleted_visits`, `updated_refuges`,
    `total_visitors_added` (mateixes claus que avui) i `purge_old_visits() -> int` (visites purgades).
  Tots dos s'executen amb `system_context()` propi: es poden cridar sense cap context de RLS (no hi ha usuari).
- «Ahir» es la data de Madrid (`get_madrid_today() - 1 dia`), mai la d'UTC ni `CURRENT_DATE`.
- Per a cada participant de les visites d'ahir: `INSERT INTO users.user_visited_refuges … ON CONFLICT DO NOTHING`
  (idempotent: conserva el `created_at` original; equivalent a `apps.accounts.services.add_visited`). No toca Firestore.
- Les visites d'ahir **buides** (sense participants) s'esborren; les que tenen participants **no** (decisio 13).
- Purga (§8.3, decisio 13): visites amb `visit_date < avui − 12 mesos` (els participants cauen en cascada); la data
  exactament de fa 12 mesos es conserva. `user_visited_refuges` no es purga mai. La fa la mateixa comanda diaria.
- Sortida de la comanda (mateixes linies que avui, mes la purga):
      Visites d'ahir processades correctament
      Visites processades: N / Visites buides eliminades: N / Refugis actualitzats: N / Total visitants afegits: N
      Visites antigues purgades: N
  `updated_refuges` = visites d'ahir amb participants; `total_visitors_added` = nombre de participants d'aquestes visites.
"""
from datetime import datetime, timedelta, timezone as dt_tz
from io import StringIO
from unittest import mock

import pytest
from django.core.management import call_command
from django.db import connection

from apps.core.rls import rls_context
from apps.visits.tests.helpers import (
    PARTS, day, make_refuge, make_user, make_visit, months_ago, participant_rows, sql, today, visit_dates,
    visit_rows, visit_services, visited_ids)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.integration, pytest.mark.real_permissions]


def run():
    out = StringIO()
    call_command('process_yesterday_visits', stdout=out)
    return out.getvalue()


@pytest.fixture
def scene():
    for u in ('u1', 'u2', 'u3'):
        make_user(u)
    return make_refuge(name='R1'), make_refuge(name='R2', lat=43), make_refuge(name='R3', lat=44)


def test_la_comanda_viu_a_apps_visits_i_no_a_api():
    from django.core.management import get_commands
    assert get_commands()['process_yesterday_visits'] == 'apps.visits'


def test_afegeix_els_visitants_d_ahir_als_visitats(scene):
    r1, r2, _ = scene
    make_visit(r1, day(-1), {'u1': 3, 'u2': 1})
    make_visit(r2, day(-1), {'u1': 2})
    run()
    assert sorted(visited_ids('u1')) == sorted([r1.pk, r2.pk])
    assert visited_ids('u2') == [r1.pk] and visited_ids('u3') == []


def test_nomes_processa_ahir_ni_avui_ni_dies_anteriors_ni_futurs(scene):
    r1, r2, r3 = scene
    make_visit(r1, day(-2), {'u1': 1})
    make_visit(r2, day(0), {'u1': 1})
    make_visit(r3, day(1), {'u1': 1})
    run()
    assert visited_ids('u1') == []


def test_es_idempotent_i_conserva_el_created_at_original(scene):
    r1, _, _ = scene
    make_visit(r1, day(-1), {'u1': 3})
    sql('INSERT INTO users.user_visited_refuges (user_uid, refuge_id, created_at) VALUES (%s, %s, %s)',
        ['u1', r1.pk, datetime(2020, 1, 1, tzinfo=dt_tz.utc)])
    run()
    run()
    rows = sql('SELECT created_at FROM users.user_visited_refuges WHERE user_uid = %s', ['u1'])
    assert rows == [(datetime(2020, 1, 1, tzinfo=dt_tz.utc),)]


def test_les_visites_amb_participants_no_s_esborren_i_les_buides_si(scene):
    r1, r2, _ = scene
    full = make_visit(r1, day(-1), {'u1': 3})
    make_visit(r2, day(-1))                                    # buida
    out = run()
    assert [r[0] for r in visit_rows()] == [full]
    assert participant_rows(full) == {'u1': 3}
    assert 'Visites processades: 2' in out and 'Visites buides eliminades: 1' in out


def test_no_esborra_les_visites_buides_d_altres_dies(scene):
    r1, r2, r3 = scene
    make_visit(r1, day(0))
    make_visit(r2, day(1))
    make_visit(r3, day(-2))
    run()
    assert len(visit_rows()) == 3


def test_estadistiques_del_servei(scene):
    r1, r2, r3 = scene
    make_visit(r1, day(-1), {'u1': 3, 'u2': 1})
    make_visit(r2, day(-1), {'u3': 2})
    make_visit(r3, day(-1))
    stats = visit_services().process_yesterday_visits()
    assert stats['processed_visits'] == 3 and stats['deleted_visits'] == 1
    assert stats['updated_refuges'] == 2 and stats['total_visitors_added'] == 3


def test_sortida_de_la_comanda(scene):
    r1, _, _ = scene
    make_visit(r1, day(-1), {'u1': 3})
    out = run()
    for line in ("Visites d'ahir processades correctament", 'Visites processades: 1', 'Visites buides eliminades: 0',
                 'Refugis actualitzats: 1', 'Total visitants afegits: 1', 'Visites antigues purgades: 0'):
        assert line in out, out


def test_sense_visites_d_ahir_no_fa_res(scene):
    out = run()
    assert 'Visites processades: 0' in out and visit_rows() == []


def test_no_toca_firestore(scene):
    """Firestore ja no existeix al codi (D43): cap client se'n pot crear."""
    r1, _, _ = scene
    make_visit(r1, day(-1), {'u1': 3})
    with mock.patch('google.cloud.firestore.Client', side_effect=AssertionError('Firestore!')):
        run()
    assert visited_ids('u1') == [r1.pk]


def test_funciona_sense_context_de_rls_i_no_el_deixa_en_mode_sistema(scene):
    r1, _, _ = scene
    make_visit(r1, day(-1), {'u1': 3})
    with connection.cursor() as cur:
        cur.execute("SELECT set_config('app.uid', '', true), set_config('app.is_admin', '', true), "
                    "set_config('app.is_system', '', true)")
    run()
    assert visited_ids('u1') == [r1.pk]
    with connection.cursor() as cur:
        cur.execute("SELECT coalesce(current_setting('app.is_system', true), '')")
        assert cur.fetchone()[0] in ('', 'false')


def test_els_visitats_es_desen_amb_el_rol_app_sota_rls_com_a_sistema(scene):
    """Un participant es de `u1` pero el job no es `u1`: nomes `{SYS}` ho pot escriure a `user_visited_refuges`."""
    r1, _, _ = scene
    make_visit(r1, day(-1), {'u1': 3, 'u2': 1})
    with rls_context(uid='u3'):                                  # context d'un usuari aliè en curs
        run()
    assert visited_ids('u1') == [r1.pk] and visited_ids('u2') == [r1.pk]


def test_ahir_es_el_de_madrid_i_no_el_d_utc(scene):
    """23:30 UTC del 10/03 = 00:30 de l'11/03 a Madrid: ahir = 10/03 (a UTC seria el 09/03)."""
    r1, r2, _ = scene
    instant = datetime(2026, 3, 10, 23, 30, tzinfo=dt_tz.utc)
    make_visit(r1, instant.date(), {'u1': 1})                    # 10/03: ahir a Madrid
    make_visit(r2, instant.date() - timedelta(days=1), {'u2': 1})  # 09/03: ahir segons UTC
    with mock.patch('django.utils.timezone.now', return_value=instant):
        run()
    assert visited_ids('u1') == [r1.pk] and visited_ids('u2') == []


# ---------- Purga de 12 mesos (§8.3) ----------

def test_purga_visites_de_mes_de_12_mesos_i_cascadeja_els_participants(scene):
    r1, r2, r3 = scene
    limit = months_ago(today(), 12)
    old = make_visit(r1, limit - timedelta(days=1), {'u1': 2})
    edge = make_visit(r2, limit, {'u2': 1})
    recent = make_visit(r3, day(-30), {'u3': 1})
    n = visit_services().purge_old_visits()
    assert n == 1
    assert sorted(r[0] for r in visit_rows()) == sorted([edge, recent])
    assert participant_rows(old) == {} and participant_rows(edge) == {'u2': 1}


def test_la_comanda_purga_i_informa(scene):
    r1, _, _ = scene
    make_visit(r1, months_ago(today(), 13), {'u1': 2})
    out = run()
    assert visit_rows() == [] and 'Visites antigues purgades: 1' in out


def test_la_purga_no_toca_els_visitats_mai(scene):
    r1, _, _ = scene
    make_visit(r1, months_ago(today(), 24), {'u1': 2})
    sql('INSERT INTO users.user_visited_refuges (user_uid, refuge_id) VALUES (%s, %s)', ['u1', r1.pk])
    visit_services().purge_old_visits()
    assert visited_ids('u1') == [r1.pk]


def test_la_purga_es_idempotent_i_no_toca_visites_futures(scene):
    r1, r2, _ = scene
    make_visit(r1, day(40), {'u1': 1})
    make_visit(r2, months_ago(today(), 14), {'u1': 1})
    s = visit_services()
    assert s.purge_old_visits() == 1 and s.purge_old_visits() == 0
    assert visit_dates() == [day(40)]


def test_les_purgues_i_el_processament_no_depenen_de_l_ordre(scene):
    """Una visita d'ahir no es purga mai (nomes les de >12 mesos)."""
    r1, _, _ = scene
    make_visit(r1, day(-1), {'u1': 1})
    run()
    assert len(visit_rows()) == 1 and visited_ids('u1') == [r1.pk]


# ---------- Errors (D28) ----------

@pytest.mark.parametrize('target', ['process_yesterday_visits', 'purge_old_visits'])
def test_la_comanda_surt_amb_error_si_falla(scene, target):
    """D28: `CommandError` (codi de sortida != 0) perque el job de GitHub Actions detecti la fallada."""
    from django.core.management.base import CommandError
    with mock.patch(f'apps.visits.services.{target}', side_effect=RuntimeError('secret de bd')):
        with pytest.raises(CommandError) as err:
            run()
    assert 'secret' not in str(err.value)
