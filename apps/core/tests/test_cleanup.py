"""
Neteja de Firestore i Redis (chunk 11, D43): el codi, les dependències, les rutes i la configuració d'ambdós
han desaparegut; Firebase Auth (`firebase-admin`) es queda.
"""
import ast
import logging
import os
import subprocess
import sys
from pathlib import Path

import pytest
from django.conf import settings

ROOT = Path(__file__).resolve().parents[3]

FORBIDDEN_MODULES = (
    'google.cloud.firestore', 'firebase_admin.firestore', 'api.services.firestore_service',
    'api.services.cache_service', 'django_redis', 'redis',
)
FORBIDDEN_NAMES = {'firestore_service', 'cache_service', 'cache_result', 'FirestoreService', 'firestore'}

REMOVED_PATHS = (
    'api/services/cache_service.py', 'api/services/firestore_service.py', 'api/daos', 'api/controllers',
    'api/mappers', 'api/models/refugi_lliure.py', 'api/serializers/refugi_lliure_serializer.py',
    'api/views/cache_views.py',
)


def _production_files():
    for base in ('api', 'apps'):
        for f in (ROOT / base).rglob('*.py'):
            rel = f.relative_to(ROOT).parts
            if 'tests' in rel or f.name == 'conftest.py' or '__pycache__' in rel or 'migrations' in rel:
                continue
            yield f
    yield ROOT / 'refugis_lliures' / 'settings.py'


def _offending_imports(path):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ''
            mods = [base] + [f'{base}.{a.name}'.strip('.') for a in node.names]
            if any(a.name in FORBIDDEN_NAMES for a in node.names):
                found.append(f'from {"." * node.level}{base} import {[a.name for a in node.names]}')
        else:
            continue
        for m in mods:
            if any(m == bad or m.startswith(bad + '.') for bad in FORBIDDEN_MODULES) \
                    or m.split('.')[-1] in ('firestore_service', 'cache_service'):
                found.append(m)
    return found


def test_cap_modul_de_produccio_importa_firestore_ni_redis():
    errors = {str(f.relative_to(ROOT)): bad for f in _production_files() if (bad := _offending_imports(f))}
    assert not errors, errors


@pytest.mark.parametrize('rel', REMOVED_PATHS)
def test_els_fitxers_i_directoris_morts_no_existeixen(rel):
    assert not (ROOT / rel).exists(), rel


def test_cap_test_legacy_de_refugis_ni_de_cache_no_queda():
    for rel in ('api/tests/refugi_lliure', 'api/tests/test_cache_views.py', 'api/tests/media/test_daos.py'):
        assert not (ROOT / rel).exists(), rel


def test_requirements_sense_redis_i_amb_firebase_admin():
    lines = [l.strip().lower() for l in (ROOT / 'requirements.txt').read_text(encoding='utf-8').splitlines()
             if l.strip() and not l.strip().startswith('#')]
    names = [l.split('==')[0].split('>=')[0].split('<')[0].strip() for l in lines]
    assert 'redis' not in names and 'django-redis' not in names
    assert 'firebase-admin' in names


def test_la_cache_es_locmem_i_no_hi_ha_redis_url():
    assert settings.CACHES['default']['BACKEND'] == 'django.core.cache.backends.locmem.LocMemCache'
    assert not hasattr(settings, 'REDIS_URL')
    assert 'redis' not in str(settings.CACHES).lower()


def test_els_nivells_de_log_propis_no_estan_registrats():
    for level in (21, 22, 23):
        assert logging.getLevelName(level) == f'Level {level}'
    for attr in ('CACHE_LEVEL', 'FIRESTORE_LEVEL', 'DAO_LEVEL'):
        assert not hasattr(settings, attr)
    loggers = settings.LOGGING.get('loggers', {})
    for name in ('api.services.cache_service', 'api.services.firestore_service', 'api.daos'):
        assert name not in loggers


@pytest.mark.parametrize('path', ['/api/cache/stats/', '/api/cache/clear/', '/api/cache/invalidate/'])
def test_les_rutes_de_cache_ja_no_existeixen(path):
    """Es comprova el resolver (el middleware d'auth respondria 401 a una ruta desconeguda sense token)."""
    from django.urls import Resolver404, resolve
    with pytest.raises(Resolver404):
        resolve(path)


@pytest.mark.parametrize('path', ['/api/cache/stats/', '/api/cache/clear/', '/api/cache/invalidate/'])
def test_les_rutes_de_cache_responen_404_o_no_autoritzat_mai_200(client, path):
    assert client.get(path).status_code in (401, 404)


def test_carregar_les_urls_no_importa_firestore_ni_redis():
    """Procés net: ni `api.urls` ni la inicialització de Django arrosseguen Firestore o Redis."""
    code = (
        "import django, sys; django.setup(); import api.urls, refugis_lliures.urls; "
        "bad = [m for m in ('google.cloud.firestore', 'firebase_admin.firestore', 'redis', 'django_redis') "
        "if m in sys.modules]; print('BAD:' + ','.join(bad))"
    )
    env = {**os.environ, 'DJANGO_SETTINGS_MODULE': 'refugis_lliures.settings', 'TESTING': 'true'}
    out = subprocess.run([sys.executable, '-c', code], cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr[-2000:]
    assert out.stdout.strip().splitlines()[-1] == 'BAD:'


def test_firebase_admin_segueix_disponible_per_a_auth():
    import firebase_admin
    from firebase_admin import auth
    assert hasattr(firebase_admin, 'get_app') and hasattr(auth, 'verify_id_token')
    assert (ROOT / 'api' / 'firebase_config.py').exists()


def test_l_esquema_swagger_segueix_generant_se_sense_cache_ni_camps_de_firestore():
    from drf_yasg import openapi
    from drf_yasg.generators import OpenAPISchemaGenerator
    schema = OpenAPISchemaGenerator(openapi.Info(title='t', default_version='v1')).get_schema(request=None, public=True)
    assert '/health/' in schema['paths']
    assert not any(p.startswith('/cache/') for p in schema['paths'])
    props = schema['definitions'].get('HealthCheckResponse', {}).get('properties', {})
    assert 'collections_count' not in props and 'firestore' not in props
