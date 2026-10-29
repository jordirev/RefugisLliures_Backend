"""Configuració de CI i tox (chunk 1): postgis, bootstrap, variables TEST_DATABASE_URL_* i branca `migration`."""
import configparser
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[3]


def test_tox_passa_les_variables_de_bd_de_test():
    cp = configparser.ConfigParser()
    cp.read(ROOT / 'tox.ini')
    passenv = cp['testenv'].get('passenv', '')
    for v in ('TEST_DATABASE_URL_APP', 'TEST_DATABASE_URL_MIGRATOR'):
        assert v in passenv


@pytest.fixture(scope='module')
def workflow():
    return yaml.safe_load((ROOT / '.github/workflows/django.yml').read_text())


def test_workflow_s_executa_tambe_a_la_branca_migration(workflow):
    on = workflow.get('on', workflow.get(True))
    assert 'migration' in on['push']['branches']
    assert 'migration' in on['pull_request']['branches']
    assert 'develop' in on['push']['branches'] and 'main' in on['push']['branches']


def test_workflow_te_servei_postgis(workflow):
    services = workflow['jobs']['build'].get('services', {})
    assert any('postgis' in s.get('image', '') for s in services.values())


def test_workflow_instal_la_gdal_i_executa_el_bootstrap():
    text = (ROOT / '.github/workflows/django.yml').read_text()
    assert 'gdal' in text.lower()
    assert 'scripts/dev/setup_local_postgres.sh' in text
    assert 'TEST_DATABASE_URL_APP' in text and 'TEST_DATABASE_URL_MIGRATOR' in text


def test_script_de_bootstrap_existeix_i_es_executable():
    p = ROOT / 'scripts/dev/setup_local_postgres.sh'
    assert p.exists() and p.stat().st_mode & 0o111
