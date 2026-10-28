"""Fixtures del domini moderació (chunk 9)."""
from unittest.mock import patch

import pytest

from apps.moderation.tests.helpers import R2Store, make_refuge, make_user


@pytest.fixture(autouse=True)
def r2store():
    """Cap test toca R2: el client boto3 és un fals amb un diccionari com a bucket (`r2store.store`).

    Les URL prefirmades són deterministes (`https://r2.test/<clau>?...`); `copy_object`/`delete_object` operen sobre el
    diccionari (retenció a `moderation-hold/`)."""
    store = R2Store()
    with patch('api.services.r2_media_service.get_r2_client', return_value=store.client):
        yield store


@pytest.fixture
def MM():
    """Mòdul `apps.moderation.models` (falla amb ModuleNotFoundError fins que l'implementador el creï)."""
    from apps.moderation import models
    return models


@pytest.fixture
def selectors():
    from apps.moderation import selectors
    return selectors


@pytest.fixture
def services():
    from apps.moderation import services
    return services


@pytest.fixture
def world():
    """Usuaris `u1` (autor del mitjà), `u2`, `u3`, `u4`, `u5` (denunciants), els admins `adm` i `adm2` (amb perfil) i dos
    refugis. Retorna `(refuge_1, refuge_2)`."""
    for uid in ('u1', 'u2', 'u3', 'u4', 'u5', 'adm', 'adm2'):
        make_user(uid)
    return make_refuge(name='Refugi A'), make_refuge(name='Refugi B', lat=43.0)
