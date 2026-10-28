"""
Concurrència de l'aprovació (C2, §2.18): `SELECT … FOR UPDATE` amb `status = 'pending'` dins una sola transacció.
La doble aprovació és impossible a la BD (ja no depèn d'una cache), i aprovar contra rebutjar, o aprovar un `delete`
contra un `update` del mateix refugi, deixa sempre un estat coherent i cap `IntegrityError` en brut.

Cada fil usa la seva pròpia connexió `app` (`rls_context` d'un admin); les dades es comprometen de debò amb la connexió
`migrator` (fixture `commit_world`, que les esborra abans i després; les propostes primer: un `SET NULL` sobre una
proposta pendent violaria el `CHECK`).
"""
import json
import threading

import pytest
from django.db import connections

from apps.core.rls import rls_context

pytestmark = [pytest.mark.db_infra, pytest.mark.integration, pytest.mark.slow, pytest.mark.real_permissions]

PAYLOAD = {'name': 'Concurrent', 'coord': {'lat': 42.0, 'long': 2.0}}


@pytest.fixture
def commit_world(migrator_db):
    def wipe():
        with migrator_db.cursor() as cur:
            cur.execute('DELETE FROM proposals.refuge_proposals')
            cur.execute('DELETE FROM users.users')
            cur.execute('DELETE FROM refuges.refuges')

    class World:
        def __init__(self):
            with migrator_db.cursor() as cur:
                for uid in ('adm', 'adm2', 'c0', 'c1'):
                    cur.execute('INSERT INTO users.users (uid) VALUES (%s)', [uid])
                    cur.execute('INSERT INTO users.user_public_profiles (uid) VALUES (%s)', [uid])

        def refuge(self, name='Concurrent', links=()):
            with migrator_db.cursor() as cur:
                cur.execute("INSERT INTO refuges.refuges (name, coord, places) VALUES "
                            "(%s, ST_GeogFromText('SRID=4326;POINT(1.5 42.5)'), 10) RETURNING id", [name])
                rid = cur.fetchone()[0]
                cur.execute('INSERT INTO refuges.refuge_amenities (refuge_id) VALUES (%s)', [rid])
                for i, url in enumerate(links):
                    cur.execute('INSERT INTO refuges.refuge_links (url, refuge_id, position) VALUES (%s, %s, %s)',
                                [url, rid, i])
            return rid

        def proposal(self, action='create', rid=None, payload=None):
            payload = PAYLOAD if (payload is None and action == 'create') else payload
            snap = None if action == 'create' else json.dumps({'id': str(rid), 'name': 'Concurrent'})
            with migrator_db.cursor() as cur:
                cur.execute('INSERT INTO proposals.refuge_proposals (refuge_id, action, payload, refuge_snapshot, '
                            "creator_uid) VALUES (%s, %s, %s::jsonb, %s::jsonb, 'c0') RETURNING id",
                            [rid, action, json.dumps(payload) if payload is not None else None, snap])
                return str(cur.fetchone()[0])

        def row(self, pid):
            with migrator_db.cursor() as cur:
                cur.execute('SELECT status, reviewer_uid, rejection_reason, refuge_id FROM proposals.refuge_proposals '
                            'WHERE id = %s', [pid])
                return cur.fetchone()

        def count(self, table='refuges.refuges'):
            with migrator_db.cursor() as cur:
                cur.execute(f'SELECT count(*) FROM {table}')
                return cur.fetchone()[0]

        def state(self, rid):
            with migrator_db.cursor() as cur:
                cur.execute('SELECT condition, num_contributed_conditions FROM refuges.refuges WHERE id = %s', [rid])
                return cur.fetchone()

    wipe()
    yield World()
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


def approve_job(services, pid, uid='adm'):
    def job():
        with rls_context(uid=uid, is_admin=True):
            return services.approve_proposal(proposal_id=pid, reviewer_uid=uid)
    return job


def reject_job(services, pid, uid='adm2'):
    def job():
        with rls_context(uid=uid, is_admin=True):
            return services.reject_proposal(proposal_id=pid, reviewer_uid=uid, reason='no')
    return job


def kinds(results):
    return sorted(r[0] if r[0] == 'ok' else type(r[1]).__name__ for r in results)


def test_dues_aprovacions_simultanies_nomes_en_prospera_una(commit_world, services, django_db_blocker):
    pid = commit_world.proposal()
    results = run_parallel(django_db_blocker, [approve_job(services, pid, 'adm'), approve_job(services, pid, 'adm2')])
    assert kinds(results) == ['ProposalAlreadyReviewed', 'ok'], results
    assert commit_world.count() == 1                                       # un sol refugi (C2: abans es duplicava)
    status, reviewer, _, rid = commit_world.row(pid)
    assert status == 'approved' and reviewer in ('adm', 'adm2') and rid is not None
    assert commit_world.count('refuges.refuge_amenities') == 1


def test_sis_aprovacions_simultanies_nomes_en_prospera_una(commit_world, services, django_db_blocker):
    pid = commit_world.proposal()
    results = run_parallel(django_db_blocker, [approve_job(services, pid, ('adm', 'adm2')[i % 2]) for i in range(6)])
    assert kinds(results) == ['ProposalAlreadyReviewed'] * 5 + ['ok'], results
    assert commit_world.count() == 1


def test_aprovar_i_rebutjar_a_la_vegada_deixa_un_estat_coherent(commit_world, services, django_db_blocker):
    pid = commit_world.proposal()
    results = run_parallel(django_db_blocker, [approve_job(services, pid), reject_job(services, pid)])
    assert kinds(results) == ['ProposalAlreadyReviewed', 'ok'], results
    status, reviewer, reason, rid = commit_world.row(pid)
    if status == 'approved':
        assert commit_world.count() == 1 and rid is not None and reason is None
    else:
        assert status == 'rejected' and commit_world.count() == 0 and rid is None and reviewer == 'adm2'


def test_dues_aprovacions_d_un_update_amb_condition_no_comptabilitzen_dues_vegades(commit_world, services,
                                                                                  django_db_blocker):
    rid = commit_world.refuge()
    pid = commit_world.proposal('update', rid, {'condition': 3})
    results = run_parallel(django_db_blocker, [approve_job(services, pid, 'adm'), approve_job(services, pid, 'adm2')])
    assert kinds(results) == ['ProposalAlreadyReviewed', 'ok'], results
    assert commit_world.state(rid) == (3.0, 1)


def test_aprovar_un_delete_i_un_update_del_mateix_refugi_a_la_vegada(commit_world, services, django_db_blocker):
    rid = commit_world.refuge()
    delete = commit_world.proposal('delete', rid)
    update = commit_world.proposal('update', rid, {'places': 99})
    results = run_parallel(django_db_blocker, [approve_job(services, delete, 'adm'), approve_job(services, update, 'adm2')])
    names = kinds(results)
    assert names.count('ok') >= 1 and set(names) <= {'ok', 'ProposalAlreadyReviewed'}, results     # cap IntegrityError
    assert commit_world.count() == 0                                         # el refugi ha desaparegut en tot cas
    statuses = {commit_world.row(delete)[0], commit_world.row(update)[0]}
    assert 'pending' not in statuses and commit_world.row(delete)[0] == 'approved'
    assert commit_world.row(update)[0] in ('approved', 'rejected')
    if commit_world.row(update)[0] == 'rejected':
        assert commit_world.row(update)[2] == 'refuge has been deleted' and commit_world.row(update)[1] is None


def test_dos_creates_amb_el_mateix_enllac_a_la_vegada_nomes_en_prospera_un(commit_world, services, django_db_blocker):
    payload = {**PAYLOAD, 'links': ['https://a.test/shared']}
    a, b = commit_world.proposal(payload=payload), commit_world.proposal(payload=payload)
    results = run_parallel(django_db_blocker, [approve_job(services, a, 'adm'), approve_job(services, b, 'adm2')])
    assert kinds(results) == ['LinkAlreadyUsed', 'ok'], results                 # no un IntegrityError en brut
    assert commit_world.count() == 1 and sorted([commit_world.row(a)[0], commit_world.row(b)[0]]) == ['approved', 'pending']


def test_reinici_de_la_mitjana_contra_un_vot_d_experiencia_a_la_vegada(commit_world, django_db_blocker, services):
    """El *trigger* d'experiències i l'aprovació bloquegen la fila del refugi: o bé el vot va abans del reinici
    (`c = 3, n = 1`) o bé després (`c = (3 + v) / 2, n = 2`); mai un estat intermedi."""
    from apps.experiences import services as exp_services
    rid = commit_world.refuge()
    pid = commit_world.proposal('update', rid, {'condition': 3})

    def vote():
        with rls_context(uid='c1'):
            return exp_services.create_experience(refuge_id=rid, creator_uid='c1', comment='x', condition=0)

    results = run_parallel(django_db_blocker, [approve_job(services, pid), vote])
    assert [r[0] for r in results] == ['ok', 'ok'], results
    assert commit_world.state(rid) in {(3.0, 1), (1.5, 2)}
