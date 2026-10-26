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
    assert max(r[1].total_visitors for r in results) == 16          # l'ultim veu tothom


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
