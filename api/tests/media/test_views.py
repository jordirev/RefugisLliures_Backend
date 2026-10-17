"""
Tests de les vistes de pujada directa, denúncies i moderació (+ permisos IsNotBlocked / IsAgeConfirmed).
"""
from unittest.mock import patch, MagicMock

import pytest
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from api.models.user import User
from api.views.media_views import (
    UploadIntentsAPIView, UploadIntentsConfirmAPIView, MediaReportsAPIView,
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


INTENT_BODY = {
    'target': 'refuge', 'refuge_id': 'ref_1', 'rights_confirmed': True,
    'files': [{'content_type': 'image/jpeg', 'size': 1000}],
}


@pytest.mark.views
class TestUploadIntentsView:
    @patch('api.views.media_views.MediaUploadController')
    def test_created(self, mock_ctrl, factory):
        mock_ctrl.return_value.create_upload_intents.return_value = (
            {'uploads': [{'upload_id': 'u1', 'put_url': 'https://r2/x', 'headers': {'Content-Type': 'image/jpeg'},
                          'expires_in': 600}]}, None)
        response = UploadIntentsAPIView.as_view()(authed(factory.post('/api/media/upload-intents/', INTENT_BODY, format='json')))
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['uploads'][0]['expires_in'] == 600
        kwargs = mock_ctrl.return_value.create_upload_intents.call_args.kwargs
        assert kwargs['uid'] == 'user_1' and kwargs['target'] == 'refuge' and kwargs['refuge_id'] == 'ref_1'
        assert kwargs['files'] == [{'content_type': 'image/jpeg', 'size': 1000}]

    @pytest.mark.parametrize('body', [
        dict(INTENT_BODY, rights_confirmed=False),
        dict(INTENT_BODY, target='planet'),
        {k: v for k, v in INTENT_BODY.items() if k != 'refuge_id'},
        dict(INTENT_BODY, files=[]),
        dict(INTENT_BODY, files=[{'content_type': 'image/jpeg', 'size': 1}] * 11),
        dict(INTENT_BODY, files=[{'content_type': 'application/pdf', 'size': 10}]),
        dict(INTENT_BODY, files=[{'content_type': 'image/gif', 'size': 10}]),
        dict(INTENT_BODY, files=[{'content_type': 'image/jpeg', 'size': 15 * 1024 * 1024 + 1}]),
        dict(INTENT_BODY, files=[{'content_type': 'video/mp4', 'size': 50 * 1024 * 1024 + 1}]),
        dict(INTENT_BODY, files=[{'content_type': 'image/jpeg', 'size': 0}]),
        {'target': 'avatar', 'rights_confirmed': True, 'files': [{'content_type': 'video/mp4', 'size': 10}]},
        {'target': 'avatar', 'rights_confirmed': True, 'files': [{'content_type': 'image/png', 'size': 10}] * 2},
        {'target': 'experience', 'rights_confirmed': True, 'files': [{'content_type': 'image/png', 'size': 10}]},
    ])
    @patch('api.views.media_views.MediaUploadController')
    def test_validation_400(self, mock_ctrl, factory, body):
        response = UploadIntentsAPIView.as_view()(authed(factory.post('/x', body, format='json')))
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        mock_ctrl.return_value.create_upload_intents.assert_not_called()

    @pytest.mark.parametrize('error,code', [
        ('not_owner', 403), ('Refugi not found', 404), ('Experience not found', 404),
        ('invalid: refuge_id no correspon', 400), ('Error intern: x', 500),
    ])
    @patch('api.views.media_views.MediaUploadController')
    def test_controller_errors(self, mock_ctrl, factory, error, code):
        mock_ctrl.return_value.create_upload_intents.return_value = (None, error)
        response = UploadIntentsAPIView.as_view()(authed(factory.post('/x', INTENT_BODY, format='json')))
        assert response.status_code == code
        if code == 403:
            assert response.data['error'] == 'not_owner' and response.data['code'] == 'not_owner'

    @pytest.mark.real_permissions
    @patch('api.views.media_views.MediaUploadController')
    @patch('api.permissions.get_user_for_permissions')
    def test_blocked_user_gets_403_user_blocked(self, mock_lookup, mock_ctrl, factory):
        mock_lookup.return_value = User(uid='user_1', username='u', age_confirmed_at='2025-01-01', is_blocked=True)
        response = UploadIntentsAPIView.as_view()(authed(factory.post('/x', INTENT_BODY, format='json')))
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data['error'] == 'user_blocked'
        assert response.data['code'] == 'user_blocked'
        mock_ctrl.return_value.create_upload_intents.assert_not_called()

    @pytest.mark.real_permissions
    @patch('api.views.media_views.MediaUploadController')
    @patch('api.permissions.get_user_for_permissions')
    def test_age_not_confirmed_gets_403(self, mock_lookup, mock_ctrl, factory):
        mock_lookup.return_value = User(uid='user_1', username='u')
        response = UploadIntentsAPIView.as_view()(authed(factory.post('/x', INTENT_BODY, format='json')))
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data['error'] == 'age_not_confirmed'

    @pytest.mark.real_permissions
    @patch('api.views.media_views.MediaUploadController')
    @patch('api.permissions.get_user_for_permissions')
    def test_missing_user_doc_is_age_not_confirmed(self, mock_lookup, mock_ctrl, factory):
        mock_lookup.return_value = None
        response = UploadIntentsAPIView.as_view()(authed(factory.post('/x', INTENT_BODY, format='json')))
        assert response.data['error'] == 'age_not_confirmed'

    def test_unauthenticated(self, factory):
        response = UploadIntentsAPIView.as_view()(factory.post('/x', INTENT_BODY, format='json'))
        assert response.status_code in (401, 403)


@pytest.mark.views
class TestConfirmView:
    @patch('api.views.media_views.MediaUploadController')
    def test_ok(self, mock_ctrl, factory):
        mock_ctrl.return_value.confirm_upload_intents.return_value = (
            {'uploaded': [], 'failed': [{'upload_id': 'u1', 'reason': 'invalid_type'}]}, None)
        response = UploadIntentsConfirmAPIView.as_view()(authed(factory.post('/x', {'upload_ids': ['u1']}, format='json')))
        assert response.status_code == 200
        assert response.data['failed'] == [{'upload_id': 'u1', 'reason': 'invalid_type'}]
        mock_ctrl.return_value.confirm_upload_intents.assert_called_once_with('user_1', ['u1'])

    @pytest.mark.parametrize('body', [{}, {'upload_ids': []}, {'upload_ids': ['a'] * 11}])
    def test_invalid(self, factory, body):
        response = UploadIntentsConfirmAPIView.as_view()(authed(factory.post('/x', body, format='json')))
        assert response.status_code == 400

    @patch('api.views.media_views.MediaUploadController')
    def test_internal_error(self, mock_ctrl, factory):
        mock_ctrl.return_value.confirm_upload_intents.return_value = (None, 'Error intern')
        response = UploadIntentsConfirmAPIView.as_view()(authed(factory.post('/x', {'upload_ids': ['u']}, format='json')))
        assert response.status_code == 500


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
        mock_lookup.return_value = User(uid='user_1', username='u', age_confirmed_at='x', is_blocked=True)
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
    @patch('api.daos.user_dao.UserDAO.get_user_by_uid')
    def test_lookup_uses_user_dao(self, mock_get):
        from api.permissions import get_user_for_permissions
        mock_get.return_value = 'user'
        assert get_user_for_permissions('u1') == 'user'
        assert get_user_for_permissions(None) is None
