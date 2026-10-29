"""Fixtures del domini pujades (chunk 7)."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from apps.uploads.tests.helpers import R2Store, make_refuge, make_user, upload_models


@pytest.fixture(autouse=True)
def r2store():
    """Cap test toca R2: el client boto3 és un fals amb un diccionari com a bucket (`r2store.store`)."""
    store = R2Store()
    with patch('apps.uploads.media.r2_media_service.get_r2_client', return_value=store.client):
        yield store


@pytest.fixture(autouse=True)
def moderation():
    """La moderació automàtica (`ModerationService.check`) es mocka: per defecte `blocked=False`; es pot fer bloquejar amb
    `moderation.check.return_value = ModerationResult(True, ...)`. La denúncia, l'avís i l'auditoria del bloqueig són a
    PostgreSQL (`apps.moderation`) i es comproven contra la BD (els tests amb la llista de hashes real són a
    `apps/moderation/tests/test_upload_block.py`)."""
    from apps.moderation.moderation_service import ModerationResult
    check = MagicMock(return_value=ModerationResult(False))
    with patch('apps.moderation.moderation_service.ModerationService.check', check):
        yield SimpleNamespace(check=check)


@pytest.fixture
def UM():
    """Mòdul `apps.uploads.models` (falla amb ModuleNotFoundError fins que l'implementador el creï)."""
    return upload_models()


@pytest.fixture
def services():
    from apps.uploads import services
    return services


@pytest.fixture
def world():
    """Usuaris `u1`, `u2`, `u3`, l'admin `adm` (amb perfil) i dos refugis. Retorna `(refuge_1, refuge_2)`."""
    for uid in ('u1', 'u2', 'u3', 'adm'):
        make_user(uid)
    return make_refuge(name='Refugi A'), make_refuge(name='Refugi B', lat=43.0)
