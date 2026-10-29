"""Fixtures del domini refugis (chunk 2)."""
from unittest.mock import patch

import pytest

from apps.refuges.tests.helpers import refuge_models


@pytest.fixture(autouse=True)
def r2_sense_xarxa():
    """Cap test toca R2: les URLs prefirmades són deterministes i els esborrats «funcionen»."""
    from apps.uploads.r2_media_service import R2MediaService
    with patch.object(R2MediaService, 'generate_presigned_url',
                      lambda self, key, expiration=3600: f'https://r2.test/{key}?sig=1'), \
            patch.object(R2MediaService, 'delete_file', lambda self, key: True), \
            patch.object(R2MediaService, 'delete_files',
                         lambda self, keys: {'deleted': list(keys), 'failed': []}):
        yield


@pytest.fixture
def RM():
    """Mòdul `apps.refuges.models` (falla amb ModuleNotFoundError fins que l'implementador el creï)."""
    return refuge_models()


@pytest.fixture
def wipe_catalog(migrator_db):
    """Esborra (amb el propietari, que salta la RLS) el catàleg i els usuaris abans i després del test.

    Per als tests que fan `COMMIT` de debò (comanda de càrrega, connexió `migrator`), que no els aïlla pytest-django.
    """
    def wipe():
        with migrator_db.cursor() as cur:
            cur.execute('DELETE FROM refuges.refuges')
            cur.execute('DELETE FROM users.users')
    wipe()
    yield migrator_db
    wipe()
