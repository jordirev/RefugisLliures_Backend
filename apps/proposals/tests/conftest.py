"""Fixtures del domini propostes de refugi (chunk 8)."""
from unittest.mock import MagicMock, patch

import pytest

from apps.proposals.tests.helpers import make_refuge, make_user, proposal_models


@pytest.fixture(autouse=True)
def r2():
    """Cap test toca R2. `r2.delete_file` / `r2.delete_files` són `MagicMock` (es poden fer fallar amb `r2.fail()`) i
    `r2.deleted_keys()` en recull les claus esborrades per qualsevol de les dues vies."""
    from apps.uploads.media.r2_media_service import R2MediaService
    mocks = MagicMock()
    mocks.delete_file = MagicMock(return_value=True)
    mocks.delete_files = MagicMock(side_effect=lambda keys: {'deleted': list(keys), 'failed': []})

    def deleted_keys():
        keys = [c.args[0] for c in mocks.delete_file.call_args_list]
        for c in mocks.delete_files.call_args_list:
            keys += list(c.args[0])
        return set(keys)

    def fail():
        mocks.delete_file.return_value = False
        mocks.delete_files.side_effect = lambda keys: {'deleted': [], 'failed': list(keys)}

    mocks.deleted_keys = deleted_keys
    mocks.fail = fail
    with patch.object(R2MediaService, 'generate_presigned_url',
                      lambda self, key, expiration=3600: f'https://r2.test/{key}?sig=1'), \
            patch.object(R2MediaService, 'delete_file', mocks.delete_file), \
            patch.object(R2MediaService, 'delete_files', mocks.delete_files):
        yield mocks


@pytest.fixture
def PM():
    """Mòdul `apps.proposals.models` (falla amb ModuleNotFoundError fins que l'implementador el creï)."""
    return proposal_models()


@pytest.fixture
def selectors():
    from apps.proposals import selectors
    return selectors


@pytest.fixture
def services():
    from apps.proposals import services
    return services


@pytest.fixture
def world():
    """Usuaris `u1`, `u2`, `u3` i els admins `adm` i `adm2` (tots amb perfil) i dos refugis. Retorna `(r1, r2)`."""
    for uid in ('u1', 'u2', 'u3', 'adm', 'adm2'):
        make_user(uid)
    return make_refuge(name='Refugi A', places=10, altitude=2000), make_refuge(name='Refugi B', lat=43.0)
