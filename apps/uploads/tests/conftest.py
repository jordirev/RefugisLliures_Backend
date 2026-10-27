"""Fixtures del domini pujades (chunk 7)."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from apps.uploads.tests.helpers import R2Store, make_refuge, make_user, upload_models


@pytest.fixture(autouse=True)
def r2store():
    """Cap test toca R2: el client boto3 és un fals amb un diccionari com a bucket (`r2store.store`)."""
    store = R2Store()
    with patch('api.services.r2_media_service.get_r2_client', return_value=store.client):
        yield store


@pytest.fixture(autouse=True)
def moderation():
    """Hash-blocklist / denúncies / avisos de moderació segueixen a Firestore fins al chunk 9: es mocken.

    `moderation.check` (per defecte `blocked=False`; es pot fer bloquejar amb `moderation.check.return_value =
    ModerationResult(True, ...)`), `moderation.create_report`, `moderation.create_notice`.
    """
    from api.services.moderation_service import ModerationResult
    check = MagicMock(return_value=ModerationResult(False))
    create_report = MagicMock(return_value=(True, None))
    create_notice = MagicMock(return_value=None)
    with patch('api.services.moderation_service.ModerationService.check', check), \
            patch('api.daos.media_report_dao.MediaReportDAO.create_report', create_report), \
            patch('api.daos.moderation_notice_dao.ModerationNoticeDAO.create_notice', create_notice):
        yield SimpleNamespace(check=check, create_report=create_report, create_notice=create_notice)


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
