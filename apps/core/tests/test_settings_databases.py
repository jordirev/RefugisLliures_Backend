"""
Tria de la BD a `settings.py` (D37): les `TEST_DATABASE_URL_*` (Postgres local de proves) només s'usen dins pytest o
amb `USE_TEST_DATABASE=1`. Fora d'aquí (`runserver`, `migrate`, jobs) mana `DATABASE_URL_*`, encara que les `TEST_*`
siguin a l'entorn: abans `runserver` anava en silenci al Docker local i, si estava aturat, fallava amb un timeout.

Cada cas importa `settings` en un subprocés amb un entorn controlat (URL inventades, cap credencial real).
"""
import json
import os
import subprocess
import sys

import pytest
from django.conf import settings

ENV = {
    'DATABASE_URL_APP': 'postgres://app:x@neon-app.example.com:5432/neondb',
    'DATABASE_URL_MIGRATOR': 'postgres://migrator:x@neon-mig.example.com:5432/neondb',
    'TEST_DATABASE_URL_APP': 'postgres://app:x@localhost:5432/refugisdb_test',
    'TEST_DATABASE_URL_MIGRATOR': 'postgres://migrator:x@localhost:5432/refugisdb_test',
}
SNIPPET = ("import json, refugis_lliures.settings as s; d = s.DATABASES; "
           "print(json.dumps([d['default']['HOST'], d['migrator']['HOST'], d['default']['NAME']]))")


def _hosts(**extra):
    env = {k: v for k, v in os.environ.items() if k not in ('PYTEST_VERSION', 'USE_TEST_DATABASE', 'TEST_DATABASE_NAME')}
    env.update(ENV, USE_TEST_DATABASE='0')
    env.update(extra)
    out = subprocess.run([sys.executable, '-c', SNIPPET], cwd=settings.BASE_DIR, env=env, capture_output=True,
                         text=True, timeout=120, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_fora_de_pytest_les_test_s_ignoren_i_mana_neon():
    assert _hosts() == ['neon-app.example.com', 'neon-mig.example.com', 'neondb']


def test_use_test_database_activa_el_postgres_local():
    assert _hosts(USE_TEST_DATABASE='1') == ['localhost', 'localhost', 'refugisdb_test']


def test_dins_pytest_el_postgres_local_te_prioritat():
    assert _hosts(PYTEST_VERSION='8.4.2') == ['localhost', 'localhost', 'refugisdb_test']


def test_test_database_name_nomes_canvia_les_url_test():
    assert _hosts(PYTEST_VERSION='8.4.2', TEST_DATABASE_NAME='refugisdb_test_x')[2] == 'refugisdb_test_x'
    assert _hosts(TEST_DATABASE_NAME='refugisdb_test_x')[2] == 'neondb'


@pytest.mark.parametrize('value', ['', 'false', '0', 'no'])
def test_use_test_database_fals_no_activa_res(value):
    assert _hosts(USE_TEST_DATABASE=value)[0] == 'neon-app.example.com'
