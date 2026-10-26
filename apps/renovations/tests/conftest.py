"""Fixtures del domini reformes (chunk 5)."""
from types import SimpleNamespace

import pytest

from apps.renovations.tests.helpers import make_refuge, make_user, renovation_models


@pytest.fixture
def RN():
    """Mòdul `apps.renovations.models` (falla amb ModuleNotFoundError fins que l'implementador el creï)."""
    return renovation_models()


@pytest.fixture
def world():
    """Usuaris `u1` (creador de la majoria de reformes), `u2`, `u3`, `u4`, l'admin `adm` i dos refugis."""
    for uid in ('u1', 'u2', 'u3', 'u4', 'adm'):
        make_user(uid, username=f'name-{uid}')
    return SimpleNamespace(refuge=make_refuge(name='R1'), refuge2=make_refuge(name='R2', lat=43))
