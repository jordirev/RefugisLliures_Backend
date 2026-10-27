"""
Tests de les vistes de pujada directa, denúncies i moderació (+ permisos IsNotBlocked / IsAgeConfirmed).
"""
from unittest.mock import patch, MagicMock

import pytest
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.accounts.models import UserAccount as User
from api.views.media_views import (
    MediaReportsAPIView,
    AdminMediaReportsAPIView, AdminMediaReportDetailAPIView,
)

KEY = 'refugis-lliures/ref_1/abc.webp'


def authed(request, uid='user_1', admin=False):
    claims = {'role': 'admin'} if admin else {}
    user = MagicMock(is_authenticated=True, uid=uid, claims=claims)
    force_authenticate(request, user=user)
    request.user_uid = uid
    request.user_claims = claims
    return request


@pytest.fixture
def factory():
    return APIRequestFactory()


REPORT_BODY = {'refuge_id': 'ref_1', 'media_key': KEY, 'reason': 'my_image'}


@pytest.mark.views
class TestReportView:
    @patch('api.views.media_views.MediaReportController')
    def test_created(self, mock_ctrl, factory):
        mock_ctrl.return_value.create_report.return_value = ({'id': 'r1', 'media_hidden': True}, None)
        response = MediaReportsAPIView.as_view()(authed(factory.post('/x', REPORT_BODY, format='json'), uid='rep'))
        assert response.status_code == 201
        assert mock_ctrl.return_value.create_report.call_args.kwargs['reporter_uid'] == 'rep'

    @patch('api.views.media_views.MediaReportController')
    def test_own_media_403(self, mock_ctrl, factory):
        mock_ctrl.return_value.create_report.return_value = (None, 'own_media')
        response = MediaReportsAPIView.as_view()(authed(factory.post('/x', REPORT_BODY, format='json')))
        assert response.status_code == 403
        assert response.data['error'] == 'own_media'

    @patch('api.views.media_views.MediaReportController')
    def test_duplicate_409(self, mock_ctrl, factory):
        mock_ctrl.return_value.create_report.return_value = (None, 'already_reported')
        response = MediaReportsAPIView.as_view()(authed(factory.post('/x', REPORT_BODY, format='json')))
        assert response.status_code == 409
        assert response.data['error'] == 'already_reported'

    @pytest.mark.parametrize('error,code', [('Media not found', 404), ('Refugi not found', 404),
                                            ('invalid: x', 400), ('Error intern', 500)])
    @patch('api.views.media_views.MediaReportController')
    def test_other_errors(self, mock_ctrl, factory, error, code):
        mock_ctrl.return_value.create_report.return_value = (None, error)
        response = MediaReportsAPIView.as_view()(authed(factory.post('/x', REPORT_BODY, format='json')))
        assert response.status_code == code

    @pytest.mark.parametrize('body', [
        dict(REPORT_BODY, reason='nope'),
        dict(REPORT_BODY, reason='other'),
        dict(REPORT_BODY, reason='other', details='   '),
        dict(REPORT_BODY, details='x' * 1001),
        {'media_key': KEY, 'reason': 'my_image'},
    ])
    def test_validation(self, factory, body):
        response = MediaReportsAPIView.as_view()(authed(factory.post('/x', body, format='json')))
        assert response.status_code == 400

    @pytest.mark.real_permissions
    @patch('api.permissions.get_user_for_permissions')
    def test_blocked_user_cannot_report(self, mock_lookup, factory):
        mock_lookup.return_value = User(uid='user_1', age_confirmed_at='x', is_blocked=True)
        response = MediaReportsAPIView.as_view()(authed(factory.post('/x', REPORT_BODY, format='json')))
        assert response.status_code == 403 and response.data['error'] == 'user_blocked'


@pytest.mark.views
class TestAdminViews:
    @patch('api.views.media_views.MediaReportController')
    def test_list_requires_admin(self, mock_ctrl, factory):
        response = AdminMediaReportsAPIView.as_view()(authed(factory.get('/x')))
        assert response.status_code == 403
        mock_ctrl.return_value.list_reports.assert_not_called()

    @patch('api.views.media_views.MediaReportController')
    def test_list_ok_default_pending(self, mock_ctrl, factory):
        mock_ctrl.return_value.list_reports.return_value = ([{'id': 'r1'}], None)
        response = AdminMediaReportsAPIView.as_view()(authed(factory.get('/x'), uid='admin', admin=True))
        assert response.status_code == 200
        assert response.data == {'count': 1, 'reports': [{'id': 'r1'}]}
        mock_ctrl.return_value.list_reports.assert_called_once_with('pending', 'admin')

    def test_list_invalid_status(self, factory):
        response = AdminMediaReportsAPIView.as_view()(authed(factory.get('/x?status=foo'), admin=True))
        assert response.status_code == 400

    @patch('api.views.media_views.MediaReportController')
    def test_resolve_ok(self, mock_ctrl, factory):
        mock_ctrl.return_value.resolve_report.return_value = ({'user_blocked': True}, None)
        body = {'action': 'remove_and_strike', 'statement': 'Motiu'}
        response = AdminMediaReportDetailAPIView.as_view()(authed(factory.patch('/x', body, format='json'), uid='admin', admin=True), id='r1')
        assert response.status_code == 200
        mock_ctrl.return_value.resolve_report.assert_called_once_with(
            report_id='r1', action='remove_and_strike', statement='Motiu', admin_uid='admin')

    @pytest.mark.parametrize('body', [{'action': 'ban'}, {'action': 'dismiss'}, {'action': 'dismiss', 'statement': ''}])
    def test_resolve_validation(self, factory, body):
        response = AdminMediaReportDetailAPIView.as_view()(authed(factory.patch('/x', body, format='json'), admin=True), id='r1')
        assert response.status_code == 400

    @pytest.mark.parametrize('error,code', [('Report not found', 404), ('already_resolved', 409), ('boom', 500)])
    @patch('api.views.media_views.MediaReportController')
    def test_resolve_errors(self, mock_ctrl, factory, error, code):
        mock_ctrl.return_value.resolve_report.return_value = (None, error)
        body = {'action': 'dismiss', 'statement': 'ok'}
        response = AdminMediaReportDetailAPIView.as_view()(authed(factory.patch('/x', body, format='json'), admin=True), id='r1')
        assert response.status_code == code

    def test_resolve_requires_admin(self, factory):
        body = {'action': 'dismiss', 'statement': 'ok'}
        response = AdminMediaReportDetailAPIView.as_view()(authed(factory.patch('/x', body, format='json')), id='r1')
        assert response.status_code == 403


@pytest.mark.unit
class TestPermissionHelpers:
    @pytest.mark.real_permissions
    @patch('apps.accounts.selectors.get_user')
    def test_lookup_uses_postgres_selector(self, mock_get):
        from api.permissions import get_user_for_permissions
        mock_get.return_value = 'user'
        assert get_user_for_permissions('u1') == 'user'
        assert get_user_for_permissions(None) is None
