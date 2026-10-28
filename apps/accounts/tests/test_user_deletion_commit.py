"""
Esborrat d'usuari amb COMMIT real i concurrència (chunk 10; D42). Marcats `slow`.

Les dades es comprometen de debò amb `migrator` (fixture `committed`, que les esborra abans i després) i les comprovacions
es fan des d'una **altra connexió** (`migrator`), de manera que només veuen el que s'ha comprometit:
- Firebase Auth es crida DESPRÉS del COMMIT (la fila ja no hi és vista des d'una altra connexió);
- si Firebase falla: 500 `{error, error_id}` i les dades segueixen esborrades (ferm); si falla R2: tot desfet;
- bloqueig `FOR UPDATE` de la fila d'usuari: una inserció concurrent de contingut d'aquell usuari espera i, quan
  l'esborrat comprometi, falla (cap fitxer orfe a R2); dos esborrats alhora no es bloquegen mútuament i acaben bé.

`delete_user(uid)` es crida directament des dels fils (ha de ser autosuficient: transacció i context de RLS propis).
"""
import threading

import pytest
from django.db import connections, transaction

from apps.accounts import services
from apps.accounts.tests.helpers import VERIFY
from unittest.mock import patch

pytestmark = [pytest.mark.db_infra, pytest.mark.integration, pytest.mark.slow, pytest.mark.real_permissions,
              pytest.mark.real_audit_log]


@pytest.fixture
def committed(migrator_db):
    def wipe():
        with migrator_db.cursor() as cur:
            cur.execute('DELETE FROM moderation.media_reports')
            cur.execute('DELETE FROM audit.audit_logs')
            cur.execute('DELETE FROM users.users')
            cur.execute('DELETE FROM refuges.refuges')

    class World:
        def __init__(self):
            self.db = migrator_db
            with migrator_db.cursor() as cur:
                for uid in ('u1',):
                    cur.execute('INSERT INTO users.users (uid) VALUES (%s)', [uid])
                    cur.execute('INSERT INTO users.user_public_profiles (uid) VALUES (%s)', [uid])
                cur.execute("INSERT INTO refuges.refuges (name, coord, places) VALUES "
                            "('Conc', ST_GeogFromText('SRID=4326;POINT(1.5 42.5)'), 10) RETURNING id")
                self.refuge = str(cur.fetchone()[0])
                cur.execute('INSERT INTO refuges.refuge_amenities (refuge_id) VALUES (%s)', [self.refuge])
            self.add_media('u1', 'k/u1.webp')

        def add_media(self, uid, key):
            with transaction.atomic(using='migrator'):
                # `connections['migrator']` (local al fil) i no `migrator_db`: es crida des d'un fil secundari
                with connections['migrator'].cursor() as cur:
                    cur.execute("INSERT INTO refuges.refuge_media (key, refuge_id, creator_uid, media_type, content_type,"
                                " status, rights_confirmed_at) VALUES (%s, %s, %s, 'image', 'image/webp', 'visible', now())",
                                [key, self.refuge, uid])

        def one(self, sql, params=()):
            with migrator_db.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchone()

        def user_exists(self, uid):
            return self.one('SELECT count(*) FROM users.users WHERE uid = %s', [uid])[0] == 1

        def media_keys(self):
            with migrator_db.cursor() as cur:
                cur.execute('SELECT key FROM refuges.refuge_media ORDER BY key')
                return [r[0] for r in cur.fetchall()]

    wipe()
    yield World()
    wipe()


def http_delete(client, uid, django_db_blocker):
    with django_db_blocker.unblock():
        with patch(VERIFY, return_value={'uid': uid, 'role': 'user'}):
            return client.delete(f'/api/users/{uid}/', HTTP_AUTHORIZATION='Bearer tok')


# =================================== Firebase després del COMMIT ===================================

def test_firebase_es_crida_despres_del_commit_real(committed, client, firebase_accounts, django_db_blocker):
    seen = {}

    def spy(uid):
        seen['user_visible_from_other_connection'] = committed.user_exists(uid)
        seen['media'] = committed.media_keys()
    firebase_accounts.delete_user.side_effect = spy
    resp = http_delete(client, 'u1', django_db_blocker)
    assert resp.status_code == 204, resp.content
    firebase_accounts.delete_user.assert_called_once_with('u1')
    assert seen == {'user_visible_from_other_connection': False, 'media': []}
    connections.close_all()


def test_firebase_falla_500_amb_error_id_i_les_dades_segueixen_esborrades(committed, client, firebase_accounts,
                                                                          django_db_blocker):
    firebase_accounts.delete_user.side_effect = RuntimeError('firebase caigut amb detalls')
    resp = http_delete(client, 'u1', django_db_blocker)
    assert resp.status_code == 500 and set(resp.json()) == {'error', 'error_id'}
    assert 'firebase caigut' not in resp.content.decode()
    assert not committed.user_exists('u1') and committed.media_keys() == []
    # reintent amb el mateix token: ja no hi ha fila → només Firebase → 204
    firebase_accounts.delete_user.side_effect = None
    firebase_accounts.delete_user.reset_mock()
    assert http_delete(client, 'u1', django_db_blocker).status_code == 204
    firebase_accounts.delete_user.assert_called_once_with('u1')
    connections.close_all()


def test_si_falla_r2_res_no_es_compromet_i_firebase_no_es_toca(committed, client, r2, firebase_accounts,
                                                                django_db_blocker):
    r2.delete_files.side_effect = lambda keys: {'deleted': [], 'failed': list(keys)}
    r2.delete_file.return_value = False
    resp = http_delete(client, 'u1', django_db_blocker)
    assert resp.status_code == 500 and set(resp.json()) == {'error', 'error_id'}
    assert committed.user_exists('u1') and committed.media_keys() == ['k/u1.webp']
    assert committed.one("SELECT count(*) FROM audit.audit_logs WHERE action = 'user.deleted'")[0] == 0
    firebase_accounts.delete_user.assert_not_called()
    connections.close_all()


def test_l_entrada_d_auditoria_es_compromet_amb_l_esborrat(committed, client, django_db_blocker):
    assert http_delete(client, 'u1', django_db_blocker).status_code == 204
    row = committed.one("SELECT actor_uid, subject_uid, target_id, metadata::text FROM audit.audit_logs "
                        "WHERE action = 'user.deleted'")
    assert row == (None, None, None, '{}')
    connections.close_all()


# =================================== concurrència ===================================

def test_una_insercio_concurrent_de_contingut_espera_el_bloqueig_i_falla_quan_l_esborrat_compromet(
        committed, r2, django_db_blocker):
    """
    Mentre l'esborrat és a mig fer (fil A, parat dins la crida a R2, ja amb la fila bloquejada), un fil B intenta
    crear un mitjà de l'usuari: ha d'ESPERAR (no pot acabar abans) i fallar quan A comprometi. Així cap fitxer pujat
    després de recollir les claus queda orfe (la seva fila no sobreviu).
    """
    in_r2, release, b_done = threading.Event(), threading.Event(), threading.Event()
    out = {}

    def parked(keys):
        in_r2.set()
        release.wait(timeout=30)
        return {'deleted': list(keys), 'failed': []}
    r2.delete_files.side_effect = parked
    r2.delete_file.side_effect = lambda key: parked([key]) and True

    def a():
        try:
            services.delete_user('u1')
            out['a'] = 'ok'
        except Exception as exc:                                              # noqa: BLE001
            out['a'] = exc
        finally:
            connections.close_all()

    def b():
        try:
            committed.add_media('u1', 'k/late.webp')
            out['b'] = 'inserted'
        except Exception as exc:                                              # noqa: BLE001
            out['b'] = exc
        finally:
            b_done.set()
            connections.close_all()

    with django_db_blocker.unblock():
        ta, tb = threading.Thread(target=a), threading.Thread(target=b)
        ta.start()
        try:
            assert in_r2.wait(timeout=15), "delete_user no ha arribat a R2"
            tb.start()
            assert not b_done.wait(timeout=2), "la inserció concurrent no ha esperat el bloqueig de la fila d'usuari"
        finally:
            release.set()
            ta.join(timeout=30)
            tb.join(timeout=30)
    assert not ta.is_alive() and not tb.is_alive()
    assert out['a'] == 'ok'
    assert out['b'] != 'inserted' and isinstance(out['b'], Exception)
    assert not committed.user_exists('u1') and committed.media_keys() == []
    assert 'k/late.webp' not in str(r2.delete_files.call_args_list)
    assert 'k/u1.webp' in str(r2.delete_files.call_args_list)


def test_dos_esborrats_alhora_del_mateix_usuari_acaben_bé_sense_deadlock(committed, firebase_accounts,
                                                                          django_db_blocker):
    barrier = threading.Barrier(2)
    results = [None, None]

    def worker(i):
        try:
            barrier.wait(timeout=10)
            services.delete_user('u1')
            results[i] = 'ok'
        except Exception as exc:                                              # noqa: BLE001
            results[i] = exc
        finally:
            connections.close_all()

    with django_db_blocker.unblock():
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=40)
    assert not any(t.is_alive() for t in threads), 'deadlock?'
    assert results == ['ok', 'ok']                                            # el perdedor és idempotent (cap 404)
    assert not committed.user_exists('u1') and committed.media_keys() == []
    assert 1 <= firebase_accounts.delete_user.call_count <= 2
    assert committed.one("SELECT count(*) FROM audit.audit_logs WHERE action = 'user.deleted'")[0] == 1


def test_dos_esborrats_simultanis_per_http_un_204_i_l_altre_204_idempotent(committed, firebase_accounts,
                                                                           django_db_blocker):
    from django.test import Client
    barrier = threading.Barrier(2)
    codes = [None, None]

    def worker(i):
        try:
            client = Client()
            barrier.wait(timeout=10)
            codes[i] = client.delete('/api/users/u1/', HTTP_AUTHORIZATION='Bearer tok').status_code
        except Exception as exc:                                              # noqa: BLE001
            codes[i] = exc
        finally:
            connections.close_all()

    with django_db_blocker.unblock(), patch(VERIFY, return_value={'uid': 'u1', 'role': 'user'}):
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=40)
    assert not any(t.is_alive() for t in threads)
    assert codes == [204, 204], codes
    assert not committed.user_exists('u1')
