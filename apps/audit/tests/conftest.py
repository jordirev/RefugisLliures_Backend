"""Fixtures del domini auditoria (chunk 9)."""
from unittest.mock import patch

import pytest

from apps.moderation.tests.helpers import R2Store, make_refuge, make_user


@pytest.fixture(autouse=True)
def r2store():
    """Cap test toca R2 (l'esborrat d'usuari esborra l'avatar i les fotos): client boto3 fals."""
    store = R2Store()
    with patch('apps.uploads.r2_media_service.get_r2_client', return_value=store.client):
        yield store


@pytest.fixture
def audit():
    """Mòdul `apps.audit.services` (falla amb ModuleNotFoundError fins que l'implementador el creï)."""
    from apps.audit import services
    return services


@pytest.fixture
def world():
    """Usuaris `u1`, `u2`, `u3` i l'admin `adm` (amb perfil) i un refugi."""
    for uid in ('u1', 'u2', 'u3', 'adm'):
        make_user(uid)
    return make_refuge(name='Refugi A')
