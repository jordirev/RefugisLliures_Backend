"""
Concurrència de la moderació (chunk 9, revisió SQL):

- Dos admins resolen alhora la mateixa denúncia (o dues denúncies del mateix mitjà): **exactament un guanya** (l'altre rep
  `AlreadyResolved`), un sol strike i un sol avís.
- Tres denunciants diferents denuncien alhora un mitjà visible: el mitjà queda ocult i l'autor rep **un** sol avís
  (el recompte de denunciants i l'ocultació es serialitzen amb un bloqueig de la fila del mitjà).

Cada fil té la seva connexió `app` (`rls_context` de l'usuari); les dades es comprometen de debò amb `migrator`
(fixture `commit_world`, que les esborra abans i després). Marcats `slow`.
"""
import threading

import pytest
from django.db import connections

from apps.core.rls import rls_context

pytestmark = [pytest.mark.db_infra, pytest.mark.integration, pytest.mark.slow, pytest.mark.real_permissions]

KEY = 'refugis-lliures/conc/m1.webp'


@pytest.fixture
def commit_world(migrator_db):
    def wipe():
        with migrator_db.cursor() as cur:
            cur.execute('DELETE FROM moderation.moderation_notices')
            cur.execute('DELETE FROM moderation.media_reports')
            cur.execute('DELETE FROM users.users')
            cur.execute('DELETE FROM refuges.refuges')

    class World:
        def __init__(self):
            with migrator_db.cursor() as cur:
                for uid in ('author', 'rep1', 'rep2', 'rep3', 'adm', 'adm2'):
                    cur.execute('INSERT INTO users.users (uid, age_confirmed_at, age_threshold) VALUES (%s, now(), 16)',
                                [uid])
                    cur.execute('INSERT INTO users.user_public_profiles (uid) VALUES (%s)', [uid])
                cur.execute("INSERT INTO refuges.refuges (name, coord, places) VALUES "
                            "('Conc', ST_GeogFromText('SRID=4326;POINT(1.5 42.5)'), 10) RETURNING id")
                self.refuge = str(cur.fetchone()[0])
                cur.execute('INSERT INTO refuges.refuge_amenities (refuge_id) VALUES (%s)', [self.refuge])
                cur.execute("INSERT INTO refuges.refuge_media (key, refuge_id, creator_uid, media_type, content_type, "
                            "status, rights_confirmed_at) VALUES (%s, %s, 'author', 'image', 'image/webp', %s, now())",
                            [KEY, self.refuge, 'hidden_pending_review'])

        def report(self, reporter, reason='hate_speech'):
            with migrator_db.cursor() as cur:
                cur.execute("INSERT INTO moderation.media_reports (refuge_id, media_key, reporter_uid, reason, "
                            "media_creator_uid) VALUES (%s, %s, %s, %s, 'author') RETURNING id",
                            [self.refuge, KEY, reporter, reason])
                return str(cur.fetchone()[0])

        def set_media_status(self, status):
            with migrator_db.cursor() as cur:
                cur.execute('UPDATE refuges.refuge_media SET status = %s WHERE key = %s', [status, KEY])

        def one(self, sql, params=()):
            with migrator_db.cursor() as cur:
                cur.execute(sql, params)
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


def resolve_job(services, report_id, admin, action='remove_and_strike'):
    def job():
        with rls_context(uid=admin, is_admin=True):
            return services.resolve_report(report_id=report_id, action=action, statement='motiu', admin_uid=admin)
    return job


def create_job(services, world, reporter, reason='hate_speech'):
    def job():
        with rls_context(uid=reporter):
            return services.create_report(reporter_uid=reporter, refuge_id=world.refuge, media_key=KEY, reason=reason)
    return job


def test_dos_admins_resolen_la_mateixa_denuncia_nomes_un_guanya(commit_world, django_db_blocker, services):
    rid = commit_world.report('rep1')
    results = run_parallel(django_db_blocker, [resolve_job(services, rid, 'adm'), resolve_job(services, rid, 'adm2')])
    oks = [r for kind, r in results if kind == 'ok']
    errs = [r for kind, r in results if kind == 'err']
    assert len(oks) == 1 and len(errs) == 1 and isinstance(errs[0], services.AlreadyResolved), results
    assert commit_world.one('SELECT moderation_strikes FROM users.users WHERE uid = %s', ['author']) == (1,)
    assert commit_world.one('SELECT count(*) FROM moderation.moderation_notices') == (1,)
    status, resolved_by = commit_world.one('SELECT status, resolved_by FROM moderation.media_reports WHERE id = %s', [rid])
    assert status == 'resolved' and resolved_by in ('adm', 'adm2')


def test_dues_denuncies_germanes_resoltes_alhora_nomes_una_decisio(commit_world, django_db_blocker, services):
    a, b = commit_world.report('rep1'), commit_world.report('rep2')
    results = run_parallel(django_db_blocker, [resolve_job(services, a, 'adm'), resolve_job(services, b, 'adm2')])
    assert sorted(kind for kind, _ in results) == ['err', 'ok'], results
    assert commit_world.one('SELECT moderation_strikes FROM users.users WHERE uid = %s', ['author']) == (1,)
    assert commit_world.one("SELECT count(DISTINCT resolved_by) FROM moderation.media_reports WHERE status = 'resolved'") == (1,)
    assert commit_world.one("SELECT count(*) FROM moderation.media_reports WHERE status = 'pending'") == (0,)


def test_tres_denunciants_alhora_oculten_el_mitja_i_avisen_un_sol_cop(commit_world, django_db_blocker, services):
    commit_world.set_media_status('visible')
    jobs = [create_job(services, commit_world, u) for u in ('rep1', 'rep2', 'rep3')]
    results = run_parallel(django_db_blocker, jobs)
    assert all(kind == 'ok' for kind, _ in results), results
    assert commit_world.one('SELECT status FROM refuges.refuge_media WHERE key = %s', [KEY]) == ('hidden_pending_review',)
    assert commit_world.one("SELECT count(*) FROM moderation.moderation_notices WHERE type = 'content_hidden'") == (1,)
    assert sum(1 for _, r in results if r['media_hidden']) == 1


def test_dos_denunciants_greus_alhora_amaguen_i_avisen_un_sol_cop(commit_world, django_db_blocker, services):
    commit_world.set_media_status('visible')
    jobs = [create_job(services, commit_world, u, 'my_image') for u in ('rep1', 'rep2')]
    results = run_parallel(django_db_blocker, jobs)
    assert all(kind == 'ok' for kind, _ in results), results
    assert commit_world.one("SELECT count(*) FROM moderation.moderation_notices WHERE type = 'content_hidden'") == (1,)
    assert sum(1 for _, r in results if r['media_hidden']) == 1


def test_el_mateix_denunciant_alhora_dues_vegades_nomes_n_escriu_una(commit_world, django_db_blocker, services):
    commit_world.set_media_status('visible')
    jobs = [create_job(services, commit_world, 'rep1'), create_job(services, commit_world, 'rep1')]
    results = run_parallel(django_db_blocker, jobs)
    assert sorted(kind for kind, _ in results) == ['err', 'ok'], results
    assert [type(r) for kind, r in results if kind == 'err'] == [services.AlreadyReported]
    assert commit_world.one('SELECT count(*) FROM moderation.media_reports') == (1,)
