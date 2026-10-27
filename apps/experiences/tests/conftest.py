"""Fixtures del domini experiències (chunk 7)."""
from unittest.mock import MagicMock, patch

import pytest

from apps.experiences.tests.helpers import experience_models, make_refuge, make_user


@pytest.fixture(autouse=True)
def r2():
    """Cap test toca R2: les URLs prefirmades són deterministes i els esborrats queden registrats.

    `r2.delete_file` / `r2.delete_files` són `MagicMock` (es poden fer fallar amb `fail_r2(r2)`); vegeu
    `deleted_keys(r2)` per saber què s'ha demanat esborrar.
    """
    from api.services.r2_media_service import R2MediaService
    mocks = MagicMock()
    mocks.delete_file = MagicMock(return_value=True)
    mocks.delete_files = MagicMock(side_effect=lambda keys: {'deleted': list(keys), 'failed': []})
    with patch.object(R2MediaService, 'generate_presigned_url',
                      lambda self, key, expiration=3600: f'https://r2.test/{key}?sig=1'), \
            patch.object(R2MediaService, 'delete_file', mocks.delete_file), \
            patch.object(R2MediaService, 'delete_files', mocks.delete_files):
        yield mocks


@pytest.fixture
def EM():
    """Mòdul `apps.experiences.models` (falla amb ModuleNotFoundError fins que l'implementador el creï)."""
    return experience_models()


@pytest.fixture
def RM():
    """Mòdul `apps.refuges.models`."""
    from apps.refuges import models
    return models


@pytest.fixture
def selectors():
    from apps.experiences import selectors
    return selectors


@pytest.fixture
def services():
    from apps.experiences import services
    return services


@pytest.fixture
def world():
    """Tres usuaris (`u1`, `u2`, `u3`), l'admin `adm` (amb perfil) i dos refugis. Retorna `(refuge_1, refuge_2)`."""
    for uid in ('u1', 'u2', 'u3', 'adm'):
        make_user(uid)
    return make_refuge(name='Refugi A'), make_refuge(name='Refugi B', lat=43.0)
