"""
Tests d'edat mínima (16) i d'avisos de moderació a nivell d'usuari.
La data de naixement NO s'ha de desar mai.
"""
from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from api.controllers.user_controller import UserController, ERROR_UNDERAGE
from api.models.user import User
from api.serializers.user_serializer import UserCreateSerializer, AgeConfirmationSerializer, UserSerializer
from api.utils.age_utils import compute_age, is_old_enough
from api.utils.timezone_utils import get_madrid_today
from api.views.user_views import UsersCollectionAPIView, UserAgeConfirmationAPIView, UserModerationNoticesAPIView


def years_ago(years, days_offset=0):
    today = get_madrid_today()          # com `is_old_enough`: avui a Madrid (prop de mitjanit, UTC és un altre dia)
    try:
        d = today.replace(year=today.year - years)
    except ValueError:  # 29 de febrer
        d = today.replace(year=today.year - years, day=28)
    from datetime import timedelta
    return d + timedelta(days=days_offset)


@pytest.mark.unit
class TestAgeUtils:
    def test_compute_age(self):
        assert compute_age('2000-05-17', today=date(2016, 5, 16)) == 15
        assert compute_age('2000-05-17', today=date(2016, 5, 17)) == 16
        assert is_old_enough(date(2000, 1, 1), 16, today=date(2016, 1, 1))
        assert not is_old_enough(date(2000, 1, 2), 16, today=date(2016, 1, 1))


@pytest.mark.serializers
@pytest.mark.legacy_firestore_users  # chunk 3: substituït per apps/accounts/tests
class TestAgeSerializers:
    def test_create_accepts_optional_birth_date(self):
        assert UserCreateSerializer(data={'username': 'joan'}).is_valid()
        s = UserCreateSerializer(data={'username': 'joan', 'birth_date': '2000-05-17'})
        assert s.is_valid(), s.errors
        assert s.validated_data['birth_date'] == date(2000, 5, 17)

    @pytest.mark.parametrize('value', ['17/05/2000', '2999-01-01', '1850-01-01', 'abc'])
    def test_invalid_birth_dates(self, value):
        assert not AgeConfirmationSerializer(data={'birth_date': value}).is_valid()
        assert not UserCreateSerializer(data={'birth_date': value}).is_valid()

    def test_user_serializer_exposes_age_confirmed_only(self):
        data = UserSerializer(User(uid='u', username='n', age_confirmed_at='2025', age_threshold=16)).data
        assert data['age_confirmed'] is True
        assert 'age_confirmed_at' not in data and 'birth_date' not in data
        assert 'is_blocked' not in data and 'moderation_strikes' not in data
        assert UserSerializer(User(uid='u', username='n')).data['age_confirmed'] is False


@pytest.mark.controllers
class TestAgeController:
    @patch('api.controllers.user_controller.RefugiLliureDAO')
    @patch('api.controllers.user_controller.UserDAO')
    def test_create_underage_rejected_and_nothing_stored(self, mock_dao_class, _):
        mock_dao = mock_dao_class.return_value
        mock_dao.get_user_by_uid.return_value = None
        success, user, error = UserController().create_user({'username': 'kid', 'birth_date': years_ago(16, days_offset=1)}, 'uid_kid')
        assert success is False and error == ERROR_UNDERAGE
        mock_dao.create_user.assert_not_called()

    @patch('api.controllers.user_controller.RefugiLliureDAO')
    @patch('api.controllers.user_controller.UserDAO')
    def test_create_adult_birth_date_not_persisted(self, mock_dao_class, _):
        mock_dao = mock_dao_class.return_value
        mock_dao.get_user_by_uid.return_value = None
        mock_dao.create_user.side_effect = lambda data, uid: User.from_dict(data)
        payload = {'username': 'adult', 'birth_date': years_ago(16)}

        success, user, error = UserController().create_user(payload, 'uid_adult')

        assert success is True and error is None
        stored = mock_dao.create_user.call_args.args[0]
        assert 'birth_date' not in stored
        assert all(str(years_ago(16)) not in str(v) for v in stored.values())
        assert stored['age_threshold'] == 16 and stored['age_confirmed_at']
        assert stored['is_blocked'] is False and stored['moderation_strikes'] == 0
        assert 'birth_date' in payload  # el diccionari original no es muta
        assert user.age_confirmed is True

    @patch('api.controllers.user_controller.RefugiLliureDAO')
    @patch('api.controllers.user_controller.UserDAO')
    def test_create_without_birth_date_is_not_confirmed(self, mock_dao_class, _):
        mock_dao = mock_dao_class.return_value
        mock_dao.get_user_by_uid.return_value = None
        mock_dao.create_user.side_effect = lambda data, uid: User.from_dict(data)
        success, user, _ = UserController().create_user({'username': 'g'}, 'uid_g')
        assert success and user.age_confirmed is False
        assert 'age_confirmed_at' not in mock_dao.create_user.call_args.args[0]

    @patch('api.controllers.user_controller.RefugiLliureDAO')
    @patch('api.controllers.user_controller.UserDAO')
    def test_confirm_age(self, mock_dao_class, _):
        mock_dao = mock_dao_class.return_value
        mock_dao.user_exists.return_value = True
        mock_dao.set_age_confirmed.return_value = True
        mock_dao.get_user_by_uid.return_value = User(uid='u', username='n', age_confirmed_at='x')
        ctrl = UserController()

        assert ctrl.confirm_age('u', years_ago(15))[2] == ERROR_UNDERAGE
        mock_dao.set_age_confirmed.assert_not_called()

        success, user, error = ctrl.confirm_age('u', years_ago(30))
        assert success and error is None
        uid, confirmed_at, threshold = mock_dao.set_age_confirmed.call_args.args
        assert uid == 'u' and threshold == 16 and confirmed_at

        mock_dao.user_exists.return_value = False
        assert 'no trobat' in ctrl.confirm_age('u', years_ago(30))[2]

    @patch('api.controllers.user_controller.RefugiLliureDAO')
    @patch('api.controllers.user_controller.UserDAO')
    def test_moderation_notices(self, mock_dao_class, _):
        with patch('api.controllers.media_report_controller.MediaReportController.get_user_notices',
                   return_value=([{'id': 'n'}], None)):
            assert UserController().get_moderation_notices('u') == (True, [{'id': 'n'}], None)


@pytest.mark.daos
@pytest.mark.legacy_firestore_users  # chunk 3: substituït per apps/accounts/tests
class TestUserDaoModeration:
    @patch('api.daos.user_dao.cache_service')
    @patch('api.daos.user_dao.FirestoreService')
    def test_set_age_confirmed_stores_only_confirmation(self, mock_fs, mock_cache):
        from api.daos.user_dao import UserDAO
        doc_ref = mock_fs.return_value.get_db.return_value.collection.return_value.document.return_value
        doc_ref.get.return_value.exists = True
        assert UserDAO().set_age_confirmed('u', '2025-01-01T00:00:00', 16) is True
        doc_ref.update.assert_called_once_with({'age_confirmed_at': '2025-01-01T00:00:00', 'age_threshold': 16})

    @patch('api.daos.user_dao.cache_service')
    @patch('api.daos.user_dao.FirestoreService')
    def test_strikes_and_block(self, mock_fs, mock_cache):
        from google.cloud.firestore_v1.transforms import Increment
        from api.daos.user_dao import UserDAO
        doc_ref = mock_fs.return_value.get_db.return_value.collection.return_value.document.return_value
        doc_ref.get.return_value.exists = True
        doc_ref.get.return_value.to_dict.return_value = {'moderation_strikes': 3}
        dao = UserDAO()
        assert dao.increment_moderation_strikes('u') == 3
        doc_ref.update.assert_called_with({'moderation_strikes': Increment(1)})
        assert dao.set_blocked('u', True, reason='strikes', blocked_at='t') is True
        doc_ref.update.assert_called_with({'is_blocked': True, 'blocked_reason': 'strikes', 'blocked_at': 't'})
        doc_ref.get.return_value.exists = False
        assert dao.increment_moderation_strikes('u') is None
        assert dao.set_blocked('u') is False
        assert dao.set_age_confirmed('u', 't', 16) is False


def authed(request, uid='u1'):
    force_authenticate(request, user=MagicMock(is_authenticated=True, uid=uid, claims={}))
    request.user_uid = uid
    return request


@pytest.mark.views
class TestAgeViews:
    @patch('api.views.user_views.UserController')
    def test_create_underage_403(self, mock_ctrl):
        mock_ctrl.return_value.create_user.return_value = (False, None, 'underage')
        request = authed(APIRequestFactory().post('/api/users/', {'username': 'kid', 'birth_date': str(years_ago(10))}, format='json'))
        response = UsersCollectionAPIView.as_view()(request)
        assert response.status_code == 403
        assert response.data['error'] == 'underage' and response.data['code'] == 'underage'

    @patch('api.views.user_views.UserController')
    def test_age_confirmation_ok_and_underage(self, mock_ctrl):
        mock_ctrl.return_value.confirm_age.return_value = (True, User(uid='u1', username='n', age_confirmed_at='x'), None)
        request = authed(APIRequestFactory().patch('/api/users/u1/age-confirmation/', {'birth_date': '2000-01-01'}, format='json'))
        response = UserAgeConfirmationAPIView.as_view()(request, uid='u1')
        assert response.status_code == 200 and response.data['age_confirmed'] is True
        assert mock_ctrl.return_value.confirm_age.call_args.args == ('u1', date(2000, 1, 1))

        mock_ctrl.return_value.confirm_age.return_value = (False, None, 'underage')
        request = authed(APIRequestFactory().patch('/x', {'birth_date': str(years_ago(12))}, format='json'))
        response = UserAgeConfirmationAPIView.as_view()(request, uid='u1')
        assert response.status_code == 403 and response.data['error'] == 'underage'

    @pytest.mark.parametrize('result,code', [((False, None, 'Usuari amb UID u1 no trobat'), 404),
                                             ((False, None, 'boom'), 500)])
    @patch('api.views.user_views.UserController')
    def test_age_confirmation_errors(self, mock_ctrl, result, code):
        mock_ctrl.return_value.confirm_age.return_value = result
        request = authed(APIRequestFactory().patch('/x', {'birth_date': '2000-01-01'}, format='json'))
        assert UserAgeConfirmationAPIView.as_view()(request, uid='u1').status_code == code

    def test_age_confirmation_invalid_birth_date_error_is_string(self):
        for payload in ({'birth_date': 'no-es-data'}, {}):
            request = authed(APIRequestFactory().patch('/x', payload, format='json'))
            response = UserAgeConfirmationAPIView.as_view()(request, uid='u1')
            assert response.status_code == 400
            assert response.data['error'] == 'Dades invàlides'
            assert 'birth_date' in response.data['details']

    def test_create_user_invalid_data_error_is_string(self):
        request = authed(APIRequestFactory().post('/api/users/', {'birth_date': 'xx'}, format='json'))
        response = UsersCollectionAPIView.as_view()(request)
        assert response.status_code == 400
        assert response.data['error'] == 'Dades invàlides'
        assert isinstance(response.data['details'], dict)

    def test_age_confirmation_validation_and_same_user(self):
        request = authed(APIRequestFactory().patch('/x', {}, format='json'))
        assert UserAgeConfirmationAPIView.as_view()(request, uid='u1').status_code == 400
        request = authed(APIRequestFactory().patch('/x', {'birth_date': '2000-01-01'}, format='json'), uid='other')
        assert UserAgeConfirmationAPIView.as_view()(request, uid='u1').status_code == 403

    @patch('api.views.user_views.UserController')
    def test_moderation_notices(self, mock_ctrl):
        notice = {'id': 'n1', 'uid': 'u1', 'type': 'strike', 'statement': 's', 'created_at': 't',
                  'automated': False, 'redress': 'r', 'strikes': 1}
        mock_ctrl.return_value.get_moderation_notices.return_value = (True, [notice], None)
        response = UserModerationNoticesAPIView.as_view()(authed(APIRequestFactory().get('/x')), uid='u1')
        assert response.status_code == 200
        assert response.data['notices'][0]['type'] == 'strike'

        response = UserModerationNoticesAPIView.as_view()(authed(APIRequestFactory().get('/x'), uid='other'), uid='u1')
        assert response.status_code == 403

        mock_ctrl.return_value.get_moderation_notices.return_value = (False, None, 'boom')
        response = UserModerationNoticesAPIView.as_view()(authed(APIRequestFactory().get('/x')), uid='u1')
        assert response.status_code == 500
