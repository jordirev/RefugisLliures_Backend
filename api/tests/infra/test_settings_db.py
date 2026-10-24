"""Configuració de BD: alies `default` (rol app, ATOMIC_REQUESTS) i `migrator`; tests com a `app`."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


def _settings_en_subproces(extra_env, treure=()):
    """Importa settings en un procés net (mai amb credencials reals) i en retorna un resum JSON."""
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(('DATABASE_URL', 'TEST_DATABASE_URL', 'NEON_')) and k not in treure}
    # `settings` també llegeix `env/.env.development` (fora de git); la variable d'entorn, encara que buida, hi té
    # prioritat: així el test no depèn de les URLs de la màquina on s'executa.
    env.update({k: '' for k in ('DATABASE_URL_APP', 'DATABASE_URL_MIGRATOR',
                                'TEST_DATABASE_URL_APP', 'TEST_DATABASE_URL_MIGRATOR')})
    env.update(extra_env)
    env['PYTHONPATH'] = str(ROOT)
    code = (
        "import json, refugis_lliures.settings as s;"
        "d = s.DATABASES;"
        "print(json.dumps({'aliases': sorted(d), 'default': {k: (str(v) if k == 'NAME' else v) for k, v in d['default'].items() if k != 'PASSWORD'},"
        " 'migrator': {k: v for k, v in d.get('migrator', {}).items() if k != 'PASSWORD'},"
        " 'apps': s.INSTALLED_APPS}, default=str))"
    )
    out = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, cwd=str(ROOT), env=env)
    assert out.returncode == 0, out.stderr[-2000:]
    return json.loads(out.stdout.strip().splitlines()[-1])


# ---------- sense BD: compatibilitat amb els tests existents ----------

@pytest.mark.unit
def test_sense_urls_es_manté_sqlite_per_als_tests_amb_mocks():
    r = _settings_en_subproces({})
    assert r['default']['ENGINE'] == 'django.db.backends.sqlite3'


@pytest.mark.unit
def test_apps_de_domini_i_gis_a_installed_apps():
    r = _settings_en_subproces({})
    for app in ('domain.core', 'django.contrib.gis', 'django.contrib.postgres'):
        assert app in r['apps']


# ---------- URLs de test (locals) ----------

@pytest.mark.unit
def test_urls_de_test_locals_sense_ssl():
    r = _settings_en_subproces({
        'TEST_DATABASE_URL_APP': 'postgres://app:pw@localhost:5432/refugisdb_test',
        'TEST_DATABASE_URL_MIGRATOR': 'postgres://migrator:pw@localhost:5432/refugisdb_test'})
    d, m = r['default'], r['migrator']
    assert d['ENGINE'] == 'django.contrib.gis.db.backends.postgis'
    assert d['USER'] == 'app' and m['USER'] == 'migrator'
    assert d['ATOMIC_REQUESTS'] is True
    assert not m.get('ATOMIC_REQUESTS')
    assert 'sslmode' not in d['OPTIONS'] and 'sslmode' not in m['OPTIONS']
    assert d['HOST'] == 'localhost'


# ---------- URLs de runtime (no locals): ssl + opcions de pooler (§1.5) ----------

RUNTIME = {
    'DATABASE_URL_APP': 'postgres://app:pw@ep-demo-pooler.eu-central-1.aws.neon.tech/refugisdb?sslmode=require',
    'DATABASE_URL_MIGRATOR': 'postgres://migrator:pw@ep-demo.eu-central-1.aws.neon.tech/refugisdb',
}


@pytest.mark.unit
def test_runtime_remot_usa_ssl_atomic_requests_i_opcions_de_pooler():
    r = _settings_en_subproces(RUNTIME)
    d, m = r['default'], r['migrator']
    assert d['ENGINE'] == 'django.contrib.gis.db.backends.postgis'
    assert d['USER'] == 'app' and m['USER'] == 'migrator'
    assert d['ATOMIC_REQUESTS'] is True
    assert d['OPTIONS']['sslmode'] == 'require' and m['OPTIONS']['sslmode'] == 'require'
    assert d['DISABLE_SERVER_SIDE_CURSORS'] is True
    assert 'prepare_threshold' in d['OPTIONS'] and d['OPTIONS']['prepare_threshold'] is None
    assert 'options' not in d['OPTIONS'], "el pooler no admet el paràmetre d'arrencada `options` (§1.5)"


@pytest.mark.unit
def test_urls_de_test_tenen_prioritat_sobre_les_de_runtime():
    env = dict(RUNTIME)
    env.update({'TEST_DATABASE_URL_APP': 'postgres://app:pw@localhost:5432/refugisdb_test',
                'TEST_DATABASE_URL_MIGRATOR': 'postgres://migrator:pw@localhost:5432/refugisdb_test'})
    r = _settings_en_subproces(env)
    assert r['default']['HOST'] == 'localhost'
    assert r['migrator']['HOST'] == 'localhost'


# ---------- la sessió de tests (BD real) ----------

@pytest.mark.db_infra
def test_default_es_postgis_amb_rol_app(settings):
    d = settings.DATABASES['default']
    assert d['ENGINE'] == 'django.contrib.gis.db.backends.postgis'
    assert d['USER'] == 'app'
    assert d['ATOMIC_REQUESTS'] is True


@pytest.mark.db_infra
def test_alias_migrator_definit(settings):
    assert settings.DATABASES['migrator']['USER'] == 'migrator'


@pytest.mark.db_infra
def test_les_proves_s_executen_com_a_app(app_db):
    with app_db.cursor() as cur:
        cur.execute('SELECT current_user, current_database()')
        user, db = cur.fetchone()
    assert user == 'app'
    assert db == app_db.settings_dict['NAME']


@pytest.mark.db_infra
def test_postgis_disponible_amb_app(app_db):
    with app_db.cursor() as cur:
        cur.execute("SELECT ST_AsText(ST_SetSRID(ST_MakePoint(1, 2), 4326))")
        assert cur.fetchone()[0] == 'POINT(1 2)'
