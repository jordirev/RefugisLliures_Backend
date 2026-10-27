"""
Concurrència de la mitjana de condició (§2.9): el *trigger* bloqueja la fila del refugi (`SELECT … FOR UPDATE`) i
serialitza els vots, de manera que dos (o més) vots simultanis no es trepitgen (cap *lost update*, la mitjana i `n`
són exactes). No cal `select_for_update` a l'aplicació.

Cada fil usa la seva pròpia connexió `app`; les dades es comprometen de debò amb la connexió `migrator` (fixture
`commit_world`, que les esborra abans i després).
"""
import threading

import pytest
from django.db import connections

from apps.core.rls import rls_context

pytestmark = [pytest.mark.db_infra, pytest.mark.integration, pytest.mark.slow, pytest.mark.real_permissions]


@pytest.fixture
def commit_world(migrator_db):
    def wipe():
        with migrator_db.cursor() as cur:
            cur.execute('DELETE FROM users.users')
            cur.execute('DELETE FROM refuges.refuges')

    def seed(n_users=2):
        uids = [f'c{i}' for i in range(n_users)]
        with migrator_db.cursor() as cur:
            for uid in uids:
                cur.execute('INSERT INTO users.users (uid) VALUES (%s)', [uid])
                cur.execute('INSERT INTO users.user_public_profiles (uid) VALUES (%s)', [uid])
            cur.execute("INSERT INTO refuges.refuges (name, coord, description) VALUES "
                        "('Concurrent', ST_GeogFromText('SRID=4326;POINT(1.5 42.5)'), 'd') RETURNING id")
            rid = cur.fetchone()[0]
        return rid, uids

    wipe()
    yield seed
    wipe()


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


def state(migrator_db, rid):
    with migrator_db.cursor() as cur:
        cur.execute('SELECT condition, num_contributed_conditions FROM refuges.refuges WHERE id = %s', [rid])
        return cur.fetchone()


def test_dos_vots_simultanis_no_es_trepitgen(commit_world, migrator_db, django_db_blocker):
    from apps.experiences import services
    rid, uids = commit_world(2)

    def make_job(uid, value):
        def job():
            with rls_context(uid=uid):
                return services.create_experience(refuge_id=rid, creator_uid=uid, comment='x', condition=value)
        return job

    results = run_parallel(django_db_blocker, [make_job(uids[0], 3), make_job(uids[1], 0)])
    assert [r[0] for r in results] == ['ok', 'ok'], results
    c, n = state(migrator_db, rid)
    assert n == 2 and c == pytest.approx(1.5)


def test_molts_vots_simultanis_donen_la_mitjana_exacta(commit_world, migrator_db, django_db_blocker):
    from apps.experiences import services
    rid, uids = commit_world(10)
    values = [0, 1, 2, 3, 3, 2, 1, 0, 3, 3]

    def make_job(uid, value):
        def job():
            with rls_context(uid=uid):
                return services.create_experience(refuge_id=rid, creator_uid=uid, comment='x', condition=value)
        return job

    results = run_parallel(django_db_blocker, [make_job(u, v) for u, v in zip(uids, values)])
    assert [r[0] for r in results] == ['ok'] * 10, results
    c, n = state(migrator_db, rid)
    assert n == 10 and c == pytest.approx(sum(values) / 10)


def test_patch_i_vot_nou_simultanis(commit_world, migrator_db, django_db_blocker):
    from apps.experiences import services
    rid, uids = commit_world(3)
    with rls_context(uid=uids[0]):
        existing = services.create_experience(refuge_id=rid, creator_uid=uids[0], comment='x', condition=1)

    def patch_job():
        with rls_context(uid=uids[0]):
            return services.update_experience(experience_id=existing.pk, actor_uid=uids[0], condition=3)

    def vote_job(uid, value):
        def job():
            with rls_context(uid=uid):
                return services.create_experience(refuge_id=rid, creator_uid=uid, comment='x', condition=value)
        return job

    results = run_parallel(django_db_blocker, [patch_job, vote_job(uids[1], 0), vote_job(uids[2], 2)])
    assert [r[0] for r in results] == ['ok'] * 3, results
    c, n = state(migrator_db, rid)
    # valors finals: 3 (editat), 0 i 2 -> n = 3, mitjana 5/3 (independent de l'ordre d'execució)
    assert n == 3 and c == pytest.approx(5 / 3)


def test_dos_patch_simultanis_de_la_mateixa_experiencia(commit_world, migrator_db, django_db_blocker):
    from apps.experiences import services
    rid, uids = commit_world(1)
    with rls_context(uid=uids[0]):
        e = services.create_experience(refuge_id=rid, creator_uid=uids[0], comment='x', condition=0)

    def job_for(value):
        def job():
            with rls_context(uid=uids[0]):
                return services.update_experience(experience_id=e.pk, actor_uid=uids[0], condition=value)
        return job

    results = run_parallel(django_db_blocker, [job_for(3), job_for(2)])
    assert [r[0] for r in results] == ['ok', 'ok'], results
    with migrator_db.cursor() as cur:
        cur.execute('SELECT condition FROM activity.experiences WHERE id = %s', [e.pk])
        (final_value,) = cur.fetchone()
    c, n = state(migrator_db, rid)
    assert n == 1 and final_value in (2, 3)
    # la mitjana ha de coincidir amb l'únic valor que ha quedat a la fila (cap deriva per l'ordre dels dos PATCH)
    assert c == pytest.approx(final_value)
