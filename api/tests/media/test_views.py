"""
Tests dels permisos auxiliars de les vistes de mitjans (les vistes de denúncies són a `apps/moderation/tests/`).
"""
from unittest.mock import patch

import pytest


@pytest.mark.unit
class TestPermissionHelpers:
    @pytest.mark.real_permissions
    @patch('apps.accounts.selectors.get_user')
    def test_lookup_uses_postgres_selector(self, mock_get):
        from api.permissions import get_user_for_permissions
        mock_get.return_value = 'user'
        assert get_user_for_permissions('u1') == 'user'
        assert get_user_for_permissions(None) is None
