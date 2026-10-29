"""Fixtures del domini usuaris (chunk 3)."""
from unittest.mock import MagicMock, patch

import pytest

from apps.accounts.tests.helpers import account_models, refuge_models

ZERO_COUNTS = {'num_shared_experiences': 0, 'num_renovated_refuges': 0}


@pytest.fixture(autouse=True)
def r2():
    """Cap test toca R2: les URLs prefirmades són deterministes i `delete_file`/`delete_files` queden registrats.

    `r2.delete_file` és un `MagicMock` (es pot fer fallar amb `r2.delete_file.return_value = False`); les crides es
    llegeixen amb `r2.delete_file.call_args_list` (`call(key)`).
    """
    from apps.uploads.r2_media_service import R2MediaService
    mocks = MagicMock()
    mocks.delete_file = MagicMock(return_value=True)
    mocks.delete_files = MagicMock(side_effect=lambda keys: {'deleted': list(keys), 'failed': []})
    with patch.object(R2MediaService, 'generate_presigned_url',
                      lambda self, key, expiration=3600: f'https://r2.test/{key}?sig=1'), \
            patch.object(R2MediaService, 'delete_file', mocks.delete_file), \
            patch.object(R2MediaService, 'delete_files', mocks.delete_files):
        yield mocks


@pytest.fixture(autouse=True)
def legacy_counts(request):
    """D19: `num_shared_experiences` i `num_renovated_refuges` surten de Firestore (agregació `count()`) fins als
    chunks 5 i 7. Els tests no toquen Firestore: el selector que els calcula es mocka (contracte:
    `apps.accounts.selectors.get_legacy_counts(uid) -> {'num_shared_experiences': int, 'num_renovated_refuges': int}`).
    """
    if request.node.get_closest_marker('real_legacy_counts'):
        # Chunk 5: `num_renovated_refuges` ja es calcula a SQL; nomes les experiencies (chunk 7) segueixen a Firestore.
        # Es mocka el `count()` de Firestore: `legacy_counts(collection, field, op, value)` retorna 0 (o el que es vulgui);
        # cap crida pot demanar la col·leccio `renovations`.
        def fake_count(collection, field, op, value):
            assert collection != 'renovations', 'les reformes ja no es compten a Firestore'
            return 0
        with patch('apps.accounts.selectors._firestore_count', create=True, side_effect=fake_count) as mock:
            yield mock
        return
    try:
        import apps.accounts.selectors  # noqa: F401
    except ModuleNotFoundError:           # abans que l'implementador el creï: cada test falla pel seu propi motiu
        yield MagicMock(return_value=dict(ZERO_COUNTS))
        return
    with patch('apps.accounts.selectors.get_legacy_counts', create=True,
               return_value=dict(ZERO_COUNTS)) as mock:
        yield mock


@pytest.fixture
def AM():
    """Mòdul `apps.accounts.models`."""
    return account_models()


@pytest.fixture
def RM():
    """Mòdul `apps.refuges.models`."""
    return refuge_models()
