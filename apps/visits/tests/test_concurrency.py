"""
Concurrencia (M4): les primeres inscripcions simultanees al mateix (refugi, data) han de crear **una sola** visita
(`INSERT … ON CONFLICT (refuge_id, visit_date) DO NOTHING` + `SELECT`) i cap peticio ha de fallar amb un 500/`IntegrityError`.
Dues peticions simultanies del mateix usuari: una te exit i l'altra `AlreadyRegistered` (la PK composta ho garanteix).

Cada fil usa la seva propia connexio `app`; les dades es comprometen de debo amb la connexio `migrator` (fixture
`commit_world`, que les esborra abans i despres).
"""
import threading
from datetime import timedelta

import pytest
from django.db import connections

from apps.core.rls import rls_context
from apps.visits.tests.helpers import today, visit_services

pytestmark = [pytest.mark.db_infra, pytest.mark.integration, pytest.mark.slow, pytest.mark.real_permissions]


def run_parallel(django_db_blocker, jobs):
    """Executa cada `job()` en un fil (barrera d'inici); retorna `[('ok', valor) | ('err', excepcio)]` en ordre."""
    barrier = threading.Barrier(len(jobs))
    results = [None] * len(jobs)

    def worker(i, job):
        try:
            barrier.wait(timeout=10)
            results[i] = ('ok', job())
        except Exception as exc:                                  # noqa: BLE001
            results[i] = ('err', exc)
        finally:
            connections.close_all()

    with django_db_blocker.unblock():
        threads = [threading.Thread(target=worker, args=(i, j)) for i, j in enumerate(jobs)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
    return results


def counts(migrator_db):
    with migrator_db.cursor() as cur:
        cur.execute('SELECT count(*) FROM activity.refuge_visits')
        visits = cur.fetchone()[0]
        cur.execute('SELECT user_uid, num_visitors FROM activity.refuge_visit_participants ORDER BY 1')
        return visits, dict(cur.fetchall())


def test_primeres_inscripcions_simultanees_creen_una_sola_visita(commit_world, migrator_db, django_db_blocker):
    rid, uids = commit_world(8)
    S = visit_services()
    when = today() + timedelta(days=5)

    def make_job(uid):
        def job():
            with rls_context(uid=uid):
                return S.create_visit(uid, rid, when, 2)
        return job

    results = run_parallel(django_db_blocker, [make_job(u) for u in uids])
    assert [r[0] for r in results] == ['ok'] * 8, results
    visits, parts = counts(migrator_db)
    assert visits == 1 and parts == {u: 2 for u in uids}
    # Cada resposta es llegeix abans del seu COMMIT: el total que veu pot no incloure els qui comitegen despres
    # (READ COMMITTED), de manera que «l'ultim veu tothom» no es garantit. El total final si: 8 x 2.
    assert all(2 <= r[1].total_visitors <= 16 for r in results)
    with migrator_db.cursor() as cur:
        cur.execute('SELECT total_visitors FROM activity.refuge_visit_totals')
        assert cur.fetchall() == [(16,)]


def test_mateix_usuari_dues_vegades_nomes_una_te_exit(commit_world, migrator_db, django_db_blocker):
    rid, (uid,) = commit_world(1)
    S = visit_services()
    when = today() + timedelta(days=5)

    def job():
        with rls_context(uid=uid):
            return S.create_visit(uid, rid, when, 3)

    results = run_parallel(django_db_blocker, [job, job, job])
    oks = [r for r in results if r[0] == 'ok']
    errs = [r[1] for r in results if r[0] == 'err']
    assert len(oks) == 1, results
    assert len(errs) == 2 and all(isinstance(e, S.AlreadyRegistered) for e in errs), errs
    assert counts(migrator_db) == (1, {uid: 3})


def test_actualitzacions_simultanees_de_diferents_usuaris_no_es_pisen(commit_world, migrator_db, django_db_blocker):
    """Sense `visitors` reescrit sencer (lost updates de Firestore): el total es la suma de les files."""
    rid, uids = commit_world(6)
    S = visit_services()
    when = today() + timedelta(days=5)
    for u in uids:
        with rls_context(uid=u):
            S.create_visit(u, rid, when, 1)

    def make_job(uid):
        def job():
            with rls_context(uid=uid):
                return S.update_visit(uid, rid, when, 4)
        return job

    results = run_parallel(django_db_blocker, [make_job(u) for u in uids])
    assert [r[0] for r in results] == ['ok'] * 6, results
    assert counts(migrator_db) == (1, {u: 4 for u in uids})


# ---------- visita buida (trigger) contra inscripcions concurrents ----------

def _hold_then_run(django_db_blocker, holder, other, hold_secs=0.7):
    """
    `holder` fa la seva feina dins una transaccio que NO comet fins que `release` s'activa; `other` arrenca mentre
    el primer ja te els bloquejos i ha d'ESPERAR. Retorna `(resultat_holder, resultat_other, other_va_esperar)`.
    """
    import time
    inside, release, other_done = threading.Event(), threading.Event(), threading.Event()
    out = {}

    def a():
        try:
            from django.db import transaction
            with transaction.atomic():
                out['a_val'] = holder()
                inside.set()
                release.wait(timeout=20)
            out['a'] = 'ok'
        except Exception as exc:                                  # noqa: BLE001
            out['a'] = exc
        finally:
            inside.set()
            connections.close_all()

    def b():
        try:
            inside.wait(timeout=20)
            out['b_val'] = other()
            out['b'] = 'ok'
        except Exception as exc:                                  # noqa: BLE001
            out['b'] = exc
        finally:
            other_done.set()
            connections.close_all()

    with django_db_blocker.unblock():
        ta, tb = threading.Thread(target=a), threading.Thread(target=b)
        ta.start()
        tb.start()
        inside.wait(timeout=20)
        time.sleep(hold_secs)
        waited = not other_done.is_set()
        release.set()
        ta.join(timeout=30)
        tb.join(timeout=30)
    return out, waited


def test_apuntar_se_mentre_se_n_va_l_ultim_la_visita_sobreviu_amb_el_nou(commit_world, migrator_db, django_db_blocker):
    """
    A (join) ha inserit la fila pero no ha comes; B treu l'ultim participant. B ha d'esperar el bloqueig de la visita i,
    quan A comet, el trigger veu el nou participant i NO esborra la visita (ni deixa cap participant orfe al `COMMIT`).
    """
    rid, (u0, u1) = commit_world(2)
    S = visit_services()
    when = today() + timedelta(days=5)
    with rls_context(uid=u0):
        S.create_visit(u0, rid, when, 1)

    def join():
        with rls_context(uid=u1):
            return S.create_visit(u1, rid, when, 2)

    def leave():
        with rls_context(uid=u0):
            return S.remove_visitor(u0, rid, when)

    out, waited = _hold_then_run(django_db_blocker, join, leave)
    assert out['a'] == 'ok' and out['b'] == 'ok', out
    assert waited, 'el DELETE de l\'ultim participant havia d\'esperar el bloqueig de qui s\'apunta'
    assert counts(migrator_db) == (1, {u1: 2})


def test_se_n_va_l_ultim_mentre_algu_s_apunta_la_visita_es_torna_a_crear(commit_world, migrator_db, django_db_blocker):
    """
    B (leave) ha esborrat l'ultim participant (i, pel trigger, la visita) sense comes; A (join) ha d'esperar i, quan B
    comet, crear la visita de nou: cap 500 (`IntegrityError` d'FK diferida) ni participant orfe.
    """
    rid, (u0, u1) = commit_world(2)
    S = visit_services()
    when = today() + timedelta(days=5)
    with rls_context(uid=u0):
        S.create_visit(u0, rid, when, 1)

    def leave():
        with rls_context(uid=u0):
            return S.remove_visitor(u0, rid, when)

    def join():
        with rls_context(uid=u1):
            return S.create_visit(u1, rid, when, 2)

    out, waited = _hold_then_run(django_db_blocker, leave, join)
    assert out['a'] == 'ok' and out['b'] == 'ok', out
    assert waited, 'create_visit havia d\'esperar que l\'altra transaccio acabi'
    assert counts(migrator_db) == (1, {u1: 2})
    assert out['b_val'].total_visitors == 2


@pytest.mark.parametrize('round_', range(5))
def test_carrera_lliure_join_i_leave_sense_errors_ni_visites_buides(commit_world, migrator_db, django_db_blocker, round_):
    rid, (u0, u1, u2) = commit_world(3)
    S = visit_services()
    when = today() + timedelta(days=5)
    with rls_context(uid=u0):
        S.create_visit(u0, rid, when, 1)

    def leave():
        with rls_context(uid=u0):
            return S.remove_visitor(u0, rid, when)

    def make_join(uid):
        def job():
            with rls_context(uid=uid):
                return S.create_visit(uid, rid, when, 2)
        return job

    results = run_parallel(django_db_blocker, [leave, make_join(u1), make_join(u2)])
    assert [r[0] for r in results] == ['ok'] * 3, results
    visits, parts = counts(migrator_db)
    assert visits == 1 and parts == {u1: 2, u2: 2}
    with migrator_db.cursor() as cur:
        cur.execute('SELECT count(*) FROM activity.refuge_visits v WHERE NOT EXISTS '
                    '(SELECT 1 FROM activity.refuge_visit_participants p WHERE p.visit_id = v.id)')
        assert cur.fetchone() == (0,)


def test_se_n_va_l_ultim_i_el_mateix_usuari_torna_a_apuntar_no_fa_deadlock(commit_world, migrator_db, django_db_blocker):
    """DELETE i POST del mateix usuari alhora: l'ordre de bloqueig (visita primer, fila despres) evita el deadlock."""
    rid, (u0,) = commit_world(1)
    S = visit_services()
    when = today() + timedelta(days=5)
    with rls_context(uid=u0):
        S.create_visit(u0, rid, when, 1)

    def leave():
        with rls_context(uid=u0):
            return S.remove_visitor(u0, rid, when)

    def join():
        with rls_context(uid=u0):
            return S.create_visit(u0, rid, when, 3)

    results = run_parallel(django_db_blocker, [leave, join])
    for kind, val in results:
        assert kind == 'ok' or isinstance(val, (S.AlreadyRegistered, S.NotRegistered, S.VisitNotFound)), results
    visits, parts = counts(migrator_db)
    assert (visits, parts) in [(0, {}), (1, {u0: 3}), (1, {u0: 1})]


def test_delete_user_de_l_ultim_participant_i_un_join_concurrent(commit_world, migrator_db, django_db_blocker):
    """El trigger tambe es dispara per la cascada d'`users.users`: el mateix bloqueig protegeix el join d'un altre."""
    rid, (u0, u1) = commit_world(2)
    S = visit_services()
    when = today() + timedelta(days=5)
    with rls_context(uid=u0):
        S.create_visit(u0, rid, when, 1)

    def join():
        with rls_context(uid=u1):
            return S.create_visit(u1, rid, when, 2)

    def delete_u0():
        from django.db import transaction
        from apps.core.rls import system_context
        with transaction.atomic(), system_context():
            from django.db import connection
            with connection.cursor() as cur:
                cur.execute('DELETE FROM users.users WHERE uid = %s', [u0])

    out, waited = _hold_then_run(django_db_blocker, join, delete_u0)
    assert out['a'] == 'ok' and out['b'] == 'ok', out
    assert waited
    assert counts(migrator_db) == (1, {u1: 2})
