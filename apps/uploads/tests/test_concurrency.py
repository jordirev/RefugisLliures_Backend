"""
Concurrència dels intents de pujada (revisió SQL del chunk 7).

- La purga (`FOR UPDATE SKIP LOCKED`) no s'espera ni trepitja un intent caducat que una altra transacció té bloquejat.
- `confirm_upload_intents` bloqueja tots els intents de la petició alhora i en ordre de PK (cap *deadlock* entre
  `[a, b]` i `[b, a]`).

Cada fil té la seva connexió `app`; les dades es comprometen de debò amb `migrator` i s'esborren abans i després.
"""
import threading

import pytest
from django.db import connection, connections
from django.test.utils import CaptureQueriesContext

from apps.core.rls import rls_context
from apps.uploads import services
from apps.uploads.models import UploadIntent

pytestmark = [pytest.mark.db_infra, pytest.mark.integration, pytest.mark.slow, pytest.mark.real_permissions]


@pytest.fixture
def committed(migrator_db):
    def wipe():
        with migrator_db.cursor() as cur:
            cur.execute('DELETE FROM users.users')

    def seed(n_expired=2):
        with migrator_db.cursor() as cur:
            cur.execute("INSERT INTO users.users (uid) VALUES ('p0')")
            cur.execute("INSERT INTO users.user_public_profiles (uid) VALUES ('p0')")
            ids = []
            for i in range(n_expired):
                cur.execute(
                    "INSERT INTO moderation.upload_intents (user_uid, target, content_type, size, quarantine_key, "
                    "rights_confirmed_at, created_at, expire_at) VALUES ('p0', 'avatar', 'image/png', 10, %s, now(), "
                    "now() - interval '3 days', now() - interval '2 days') RETURNING id", [f'quarantine/p{i}'])
                ids.append(cur.fetchone()[0])
        return ids

    wipe()
    yield seed
    wipe()


def test_la_purga_salta_els_intents_bloquejats(committed, django_db_blocker):
    locked, free = committed(2)
    holding, release, outcome = threading.Event(), threading.Event(), {}

    def holder():
        try:
            with rls_context(uid='p0'):
                list(UploadIntent.objects.select_for_update().filter(pk=locked).values_list('pk', flat=True))
                holding.set()
                release.wait(timeout=20)
        finally:
            connections.close_all()

    with django_db_blocker.unblock():
        t = threading.Thread(target=holder)
        t.start()
        try:
            assert holding.wait(timeout=10)
            outcome['purged'] = services.purge_expired_intents()          # no s'espera: salta el bloquejat
        finally:
            release.set()
            t.join(timeout=20)
        remaining = services.purge_expired_intents()
    assert outcome['purged'] == 1                                         # només `free`
    assert remaining == 1                                                 # alliberat: la segona passada l'esborra
    connections.close_all()


def test_la_confirmacio_bloqueja_els_intents_en_ordre_de_pk_en_una_consulta(committed, django_db_blocker):
    a, b = committed(2)
    with django_db_blocker.unblock():
        with rls_context(uid='p0'):
            with CaptureQueriesContext(connection) as ctx:
                services._lock_intents('p0', [str(b), str(a), str(a), 'no-es-uuid'])
        locks = [q['sql'] for q in ctx.captured_queries if 'FOR UPDATE' in q['sql']]
    assert len(locks) == 1 and 'ORDER BY' in locks[0]
    connections.close_all()
