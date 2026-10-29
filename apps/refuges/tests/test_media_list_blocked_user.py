"""Un usuari bloquejat pot seguir llistant els mitjans d'un refugi."""
from unittest.mock import MagicMock, patch

import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.accounts.models import UserAccount as User


@pytest.mark.views
class TestMediaListBlockedUser:
    @pytest.mark.real_permissions
    @patch('apps.auth.permissions.get_user_for_permissions')
    @patch('apps.refuges.views.selectors')
    def test_blocked_user_can_still_list(self, mock_selectors, mock_lookup):
        from apps.refuges.views import RefugeMediaListAPIView
        mock_lookup.return_value = User(uid='u1', is_blocked=True)
        mock_selectors.refuge_exists.return_value = True
        mock_selectors.get_refuge_media.return_value = []
        request = APIRequestFactory().get('/x')
        force_authenticate(request, user=MagicMock(is_authenticated=True, uid='u1', claims={}))
        assert RefugeMediaListAPIView.as_view()(request, id='ref_1').status_code == 200
