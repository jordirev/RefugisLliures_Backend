"""Fixtures del domini dubtes (chunk 6)."""
import pytest

from apps.doubts.tests.helpers import doubt_models, make_refuge, make_user


@pytest.fixture
def DM():
    """Mòdul `apps.doubts.models` (falla amb ModuleNotFoundError fins que l'implementador el creï)."""
    return doubt_models()


@pytest.fixture
def selectors():
    from apps.doubts import selectors
    return selectors


@pytest.fixture
def services():
    from apps.doubts import services
    return services


@pytest.fixture
def world():
    """Tres usuaris (`u1`, `u2`, `u3`), l'admin `adm` (amb perfil) i dos refugis. Retorna `(refuge_1, refuge_2)`."""
    for uid in ('u1', 'u2', 'u3', 'adm'):
        make_user(uid)
    return make_refuge(name='Refugi A'), make_refuge(name='Refugi B', lat=43.0)
