"""
Conftest arrel del projecte per configurar l'entorn de tests.
Les variables d'entorn s'han de configurar AQUÍ perquè
pytest carrega aquest fitxer ABANS que qualsevol altre conftest
i abans que els fitxers de test s'importin.
"""
import os

# Configurar variables d'entorn TESTING i R2 abans de qualsevol import
os.environ['TESTING'] = 'true'
os.environ['R2_ACCESS_KEY_ID'] = 'test_access_key'
os.environ['R2_SECRET_ACCESS_KEY'] = 'test_secret_key'
os.environ['R2_ENDPOINT'] = 'https://test.r2.cloudflarestorage.com'
os.environ['R2_BUCKET_NAME'] = 'test-bucket'


def pytest_configure(config):
    """
    Hook que s'executa molt aviat durant la configuració de pytest.
    Assegura que les variables d'entorn estiguin configurades.
    """
    os.environ.setdefault('TESTING', 'true')
    os.environ.setdefault('R2_ACCESS_KEY_ID', 'test_access_key')
    os.environ.setdefault('R2_SECRET_ACCESS_KEY', 'test_secret_key')
    os.environ.setdefault('R2_ENDPOINT', 'https://test.r2.cloudflarestorage.com')
    os.environ.setdefault('R2_BUCKET_NAME', 'test-bucket')


import pytest  # noqa: E402
from unittest.mock import patch  # noqa: E402


# ============= AÏLLAMENT (compartit per api/tests i apps/*/tests) =============
# 1) Cap test pot inicialitzar Firebase real (env/ pot contenir credencials de producció).
# 2) El registre d'auditoria es mocka per defecte (marker `real_audit_log` per provar-lo).
# 3) Les comprovacions HasProfile / IsNotBlocked / IsAgeConfirmed retornen un usuari confirmat i no
#    bloquejat per defecte (sense consultar PostgreSQL) (marker `real_permissions` per provar-les).

@pytest.fixture(autouse=True)
def _block_real_firestore():
    from api.services.firestore_service import FirestoreService

    def _forbidden(self):
        raise RuntimeError("Els tests no poden connectar-se a Firestore real: mocka FirestoreService")

    with patch.object(FirestoreService, '_initialize_firebase', _forbidden), \
            patch('firebase_admin.get_app', side_effect=ValueError('no app')):
        FirestoreService._db = None
        yield


@pytest.fixture(autouse=True)
def _restore_view_policies():
    """Els tests antics muten `view.cls.permission_classes = []` i `authentication_classes = []` sense restaurar-ho
    (GOTCHAS #11): la mutació es filtrava als tests de permisos (p. ex. `apps/accounts/tests`) segons l'ordre.
    Es restauren aquests atributs a cada vista després de cada test."""
    from rest_framework.views import APIView

    def subclasses(cls):
        for sub in cls.__subclasses__():
            yield sub
            yield from subclasses(sub)

    attrs = ('permission_classes', 'authentication_classes')
    views = set(subclasses(APIView))
    snapshot = {(cls, a): cls.__dict__.get(a, None) for cls in views for a in attrs}
    yield
    for (cls, attr), value in snapshot.items():
        if value is None:
            if attr in cls.__dict__:
                delattr(cls, attr)
        elif cls.__dict__.get(attr) is not value:
            setattr(cls, attr, value)


@pytest.fixture(autouse=True)
def firebase_accounts():
    """Firebase Auth de l'Admin SDK (U7) mockat per a tots els tests: `get_user` troba el compte i `delete_user`
    l'esborra. Es fa fallar amb `firebase_accounts.get_user.side_effect = ...` o `firebase_accounts.delete_user...`."""
    with patch('apps.accounts.services.firebase_auth.get_user') as get_user, \
            patch('apps.accounts.services.firebase_auth.delete_user') as delete_user:
        yield type('FirebaseAccounts', (), {'get_user': get_user, 'delete_user': delete_user})


@pytest.fixture(autouse=True)
def _mock_audit_log(request):
    if request.node.get_closest_marker('real_audit_log'):
        yield None
        return
    # Chunk 9: el servei d'auditoria passa a `apps.audit.services` (PostgreSQL); mentre no existeixi es mocka el legacy.
    import importlib.util
    try:
        has_new = importlib.util.find_spec('apps.audit.services') is not None
    except ModuleNotFoundError:
        has_new = False
    target = ('apps.audit.services.AuditLogService.log' if has_new
              else 'api.services.audit_log_service.AuditLogService.log')
    with patch(target, return_value=True) as mock_log:
        yield mock_log


@pytest.fixture(autouse=True)
def _mock_permission_user_lookup(request):
    if request.node.get_closest_marker('real_permissions'):
        yield None
        return
    from datetime import datetime, timezone
    from apps.accounts.models import UserAccount
    user = UserAccount(uid='perm_user', age_confirmed_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                       age_threshold=16, is_blocked=False)
    with patch('api.permissions.get_user_for_permissions', return_value=user) as mock_lookup:
        yield mock_lookup


# ============= INFRAESTRUCTURA POSTGRES (chunk 1) =============
# Els tests marcats `db_infra` necessiten el Postgres local (scripts/dev/setup_local_postgres.sh) i
# les variables TEST_DATABASE_URL_APP / TEST_DATABASE_URL_MIGRATOR. Només se salten si falten.
# Contracte per a l'implementador:
#   - alias `default` = rol `app` (ATOMIC_REQUESTS=True) i alias `migrator` = rol `migrator`;
#   - la fixture `django_db_setup` (pytest-django) s'ha de sobreescriure perquè apliqui les migracions amb
#     `migrator` sobre la BD de proves i deixi la connexió `default` com a `app` (sense crear `test_*`).

_PG_ENV_VARS = ('TEST_DATABASE_URL_APP', 'TEST_DATABASE_URL_MIGRATOR')


def pytest_collection_modifyitems(config, items):
    missing = [v for v in _PG_ENV_VARS if not os.environ.get(v)]
    if not missing:
        return
    skip = pytest.mark.skip(
        reason=f"Postgres local no configurat: falta {', '.join(missing)} "
               f"(executa scripts/dev/setup_local_postgres.sh i exporta les URLs)")
    for item in items:
        if item.get_closest_marker('db_infra'):
            item.add_marker(skip)


@pytest.fixture
def app_db(django_db_setup, django_db_blocker):
    """Connexió Django `default` (rol app) en autocommit, fora de la transacció de pytest-django.

    Cal per provar el context RLS local a la transacció: dins d'un `django_db` normal tot el test és
    una sola transacció i `set_config(..., true)` no moriria en sortir d'un `atomic()` intern.
    """
    from django.db import connections
    with django_db_blocker.unblock():
        conn = connections['default']
        assert conn.vendor == 'postgresql', f"`default` ha de ser Postgres, és {conn.vendor}"
        assert not conn.in_atomic_block
        yield conn


@pytest.fixture
def migrator_db(django_db_setup, django_db_blocker):
    """Connexió Django `migrator` (propietària dels objectes de domini), en autocommit."""
    from django.db import connections
    with django_db_blocker.unblock():
        if 'migrator' not in connections.databases:
            pytest.fail("L'alias de BD `migrator` no està definit a settings.DATABASES")
        yield connections['migrator']


@pytest.fixture(scope='session')
def django_db_setup(django_test_environment, django_db_blocker):
    """Sobreescriu la fixture de pytest-django (§6.5, §7 del disseny).

    Amb el Postgres local configurat (`TEST_DATABASE_URL_*`) no es crea cap `test_*`: s'apliquen les migracions
    amb el rol `migrator` sobre la BD de proves (idempotent) i la connexió `default` es manté com a `app`,
    de manera que la RLS s'aplica als tests. Sense Postgres es manté el comportament per defecte (SQLite).
    """
    from django.conf import settings
    from django.core.management import call_command
    from django.db import connections

    if 'migrator' in settings.DATABASES:
        # Els grants de sota només són per a la BD efímera de proves: mai contra un Postgres remot (p. ex. Neon).
        from refugis_lliures.settings import _LOCAL_DB_HOSTS
        host = settings.DATABASES['migrator'].get('HOST') or ''
        if host not in _LOCAL_DB_HOSTS and not host.endswith('.localhost'):
            pytest.exit(f'Els tests només poden córrer contra un Postgres local (HOST={host!r}).', returncode=2)
        with django_db_blocker.unblock():
            call_command('migrate', database='migrator', interactive=False, verbosity=0)
            # Només per als tests: alguns creen un `django.contrib.auth.User` per a `force_authenticate`. Aquestes
            # taules de Django (a `public`, del migrator) no formen part del disseny de domini ni dels grants de
            # producció (§7.2): el rol `app` hi accedeix només a la BD de proves.
            with connections['migrator'].cursor() as cur:
                cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tableowner = current_user")
                for (table,) in cur.fetchall():
                    cur.execute(f'GRANT SELECT, INSERT, UPDATE, DELETE ON public."{table}" TO app')
                cur.execute("SELECT sequencename FROM pg_sequences WHERE schemaname = 'public' "
                            "AND sequenceowner = current_user")
                for (seq,) in cur.fetchall():
                    cur.execute(f'GRANT USAGE, SELECT ON SEQUENCE public."{seq}" TO app')
        yield
        with django_db_blocker.unblock():
            connections.close_all()
    else:
        from django.test.utils import setup_databases, teardown_databases
        with django_db_blocker.unblock():
            db_cfg = setup_databases(verbosity=0, interactive=False)
        yield
        with django_db_blocker.unblock():
            teardown_databases(db_cfg, verbosity=0)


@pytest.fixture(autouse=True)
def _rls_hook_sense_bd(request):
    """Els tests sense BD (vistes amb controllers mockejats) no poden executar el `set_config` del hook de RLS.

    El hook té els seus propis tests (marker `rls`) i els de BD (`django_db`, `db_infra`) l'executen de debò.
    """
    if any(request.node.get_closest_marker(m) for m in ('rls', 'django_db', 'db_infra')):
        yield
        return
    with patch('api.rls_hook.apply_context'):
        yield
