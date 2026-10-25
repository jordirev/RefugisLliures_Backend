"""
Tests d'utilitats d'edat i dels avisos de moderació d'usuari (que continuen a Firestore).

La resta (creació, edat, moderació, avatar, llistes) és a PostgreSQL: `apps/accounts/tests/` (chunk 3).
"""
from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from api.utils.age_utils import compute_age, is_old_enough
from api.views.user_views import UserModerationNoticesAPIView


@pytest.mark.unit
class TestAgeUtils:
    def test_compute_age(self):
        assert compute_age('2000-05-17', today=date(2016, 5, 16)) == 15
        assert compute_age('2000-05-17', today=date(2016, 5, 17)) == 16
        assert is_old_enough(date(2000, 1, 1), 16, today=date(2016, 1, 1))
        assert not is_old_enough(date(2000, 1, 2), 16, today=date(2016, 1, 1))


def authed(request, uid='u1'):
    force_authenticate(request, user=MagicMock(is_authenticated=True, uid=uid, claims={}))
    request.user_uid = uid
    return request


@pytest.mark.views
class TestModerationNoticesView:
    @patch('api.views.user_views.MediaReportController')
    def test_moderation_notices(self, mock_ctrl):
        notice = {'id': 'n1', 'uid': 'u1', 'type': 'strike', 'statement': 's', 'created_at': 't',
                  'automated': False, 'redress': 'r', 'strikes': 1}
        mock_ctrl.return_value.get_user_notices.return_value = ([notice], None)
        response = UserModerationNoticesAPIView.as_view()(authed(APIRequestFactory().get('/x')), uid='u1')
        assert response.status_code == 200
        assert response.data['notices'][0]['type'] == 'strike'

        response = UserModerationNoticesAPIView.as_view()(authed(APIRequestFactory().get('/x'), uid='other'), uid='u1')
        assert response.status_code == 403

        mock_ctrl.return_value.get_user_notices.return_value = (None, 'boom')
        response = UserModerationNoticesAPIView.as_view()(authed(APIRequestFactory().get('/x')), uid='u1')
        assert response.status_code == 500
