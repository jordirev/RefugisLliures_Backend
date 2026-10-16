"""
Tests de la feature images per a experiències: control de propietat (403 not_owner),
creació en JSON sense fitxers i MediaItems amb filtre de status.
"""
from unittest.mock import MagicMock, patch

import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from api.controllers.experience_controller import ExperienceController, ERROR_NOT_OWNER
from api.models.experience import Experience
from api.views.experience_views import ExperienceListAPIView, ExperienceDetailAPIView
from api.tests.media.helpers import fake_r2_service


def experience(creator='owner', keys=None):
    return Experience(id='exp_1', refuge_id='ref_1', creator_uid=creator, modified_at='2025', comment='c',
                      media_keys=keys or [])


@pytest.fixture
def ctrl():
    with patch('api.controllers.experience_controller.ExperienceDAO'), \
            patch('api.controllers.experience_controller.RefugiLliureDAO'), \
            patch('api.controllers.experience_controller.RefugiLliureController'), \
            patch('api.controllers.experience_controller.UserDAO'):
        controller = ExperienceController()
        controller.media_service = fake_r2_service()
        yield controller


@pytest.mark.controllers
class TestExperienceOwnership:
    def test_update_by_non_owner_is_rejected(self, ctrl):
        ctrl.experience_dao.get_experience_by_id.return_value = experience()
        result, upload, error = ctrl.update_experience('exp_1', comment='hack', requester_uid='intruder')
        assert result is None and error == ERROR_NOT_OWNER
        ctrl.experience_dao.update_experience.assert_not_called()

    def test_update_by_owner_and_admin(self, ctrl):
        ctrl.experience_dao.get_experience_by_id.return_value = experience()
        ctrl.experience_dao.update_experience.return_value = (True, None)
        ctrl.refugi_dao.get_raw_media_metadata.return_value = {}
        assert ctrl.update_experience('exp_1', comment='ok', requester_uid='owner')[2] is None
        assert ctrl.update_experience('exp_1', comment='ok', requester_uid='admin', is_admin=True)[2] is None

    def test_delete_by_non_owner_is_rejected(self, ctrl):
        ctrl.experience_dao.get_experience_by_id.return_value = experience(keys=['k'])
        success, error = ctrl.delete_experience('exp_1', requester_uid='intruder')
        assert success is False and error == ERROR_NOT_OWNER
        ctrl.refugi_controller.delete_multiple_refugi_media.assert_not_called()
        ctrl.experience_dao.delete_experience.assert_not_called()

    def test_delete_by_admin(self, ctrl):
        ctrl.experience_dao.get_experience_by_id.return_value = experience()
        ctrl.experience_dao.delete_experience.return_value = (True, None)
        assert ctrl.delete_experience('exp_1', requester_uid='admin', is_admin=True) == (True, None)


@pytest.mark.controllers
class TestExperienceMediaItems:
    def test_items_from_refuge_metadata_and_hidden_filtered(self, ctrl):
        exp = experience(keys=['k_ok.webp', 'k_hidden.webp', 'k_gone.webp'])
        ctrl.refugi_dao.refugi_exists.return_value = True
        ctrl.experience_dao.get_experiences_by_refuge_id.return_value = [exp]
        ctrl.refugi_dao.get_raw_media_metadata.return_value = {
            'k_ok.webp': {'creator_uid': 'owner', 'thumb_key': 'k_ok_thumb.webp', 'width': 10, 'experience_id': 'exp_1'},
            'k_hidden.webp': {'creator_uid': 'owner', 'status': 'hidden_pending_review', 'experience_id': 'exp_1'},
        }

        experiences, error = ctrl.get_experiences_by_refuge('ref_1', viewer_uid='someone')

        assert error is None
        items = [i.to_dict() for i in experiences[0].images_metadata]
        assert [i['key'] for i in items] == ['k_ok.webp']
        assert 'k_ok_thumb.webp' in items[0]['thumb_url'] and items[0]['width'] == 10
        assert items[0]['experience_id'] == 'exp_1'

        experiences, _ = ctrl.get_experiences_by_refuge('ref_1', viewer_uid='owner')
        assert [i.key for i in experiences[0].images_metadata] == ['k_ok.webp', 'k_hidden.webp']


def authed(request, uid='intruder', admin=False):
    claims = {'role': 'admin'} if admin else {}
    force_authenticate(request, user=MagicMock(is_authenticated=True, uid=uid, claims=claims))
    request.user_uid = uid
    request.user_claims = claims
    return request


@pytest.mark.views
class TestExperienceViewsOwnership:
    @patch('api.views.experience_views.ExperienceController')
    def test_patch_non_owner_403(self, mock_ctrl):
        mock_ctrl.return_value.update_experience.return_value = (None, None, ERROR_NOT_OWNER)
        request = authed(APIRequestFactory().patch('/api/experiences/exp_1/', {'comment': 'x'}, format='json'))
        response = ExperienceDetailAPIView.as_view()(request, experience_id='exp_1')
        assert response.status_code == 403
        assert response.data['error'] == 'not_owner'
        kwargs = mock_ctrl.return_value.update_experience.call_args.kwargs
        assert kwargs['requester_uid'] == 'intruder' and kwargs['is_admin'] is False

    @patch('api.views.experience_views.ExperienceController')
    def test_delete_non_owner_403(self, mock_ctrl):
        mock_ctrl.return_value.delete_experience.return_value = (False, ERROR_NOT_OWNER)
        request = authed(APIRequestFactory().delete('/api/experiences/exp_1/'))
        response = ExperienceDetailAPIView.as_view()(request, experience_id='exp_1')
        assert response.status_code == 403
        assert response.data['code'] == 'not_owner'

    @patch('api.views.experience_views.ExperienceController')
    def test_delete_admin_passes_flag(self, mock_ctrl):
        mock_ctrl.return_value.delete_experience.return_value = (True, None)
        request = authed(APIRequestFactory().delete('/api/experiences/exp_1/'), uid='adm', admin=True)
        response = ExperienceDetailAPIView.as_view()(request, experience_id='exp_1')
        assert response.status_code == 200
        mock_ctrl.return_value.delete_experience.assert_called_once_with('exp_1', requester_uid='adm', is_admin=True)

    @patch('api.views.experience_views.ExperienceController')
    def test_create_with_json_without_files(self, mock_ctrl):
        mock_ctrl.return_value.create_experience.return_value = (experience(creator='intruder'), None, None)
        request = authed(APIRequestFactory().post('/api/experiences/', {'refuge_id': 'ref_1', 'comment': 'Molt bé'}, format='json'))
        response = ExperienceListAPIView.as_view()(request)
        assert response.status_code == 201
        kwargs = mock_ctrl.return_value.create_experience.call_args.kwargs
        assert kwargs['files'] is None and kwargs['comment'] == 'Molt bé'
        assert response.data['uploaded_files'] == []

    @patch('api.views.experience_views.ExperienceController')
    def test_patch_with_json(self, mock_ctrl):
        mock_ctrl.return_value.update_experience.return_value = (experience(creator='intruder'), None, None)
        request = authed(APIRequestFactory().patch('/api/experiences/exp_1/', {'comment': 'nou'}, format='json'))
        response = ExperienceDetailAPIView.as_view()(request, experience_id='exp_1')
        assert response.status_code == 200
        assert mock_ctrl.return_value.update_experience.call_args.kwargs['comment'] == 'nou'

    @pytest.mark.real_permissions
    @patch('api.permissions.get_user_for_permissions')
    @patch('api.views.experience_views.ExperienceController')
    def test_blocked_user_cannot_create(self, mock_ctrl, mock_lookup):
        from api.models.user import User
        mock_lookup.return_value = User(uid='intruder', username='u', is_blocked=True)
        request = authed(APIRequestFactory().post('/api/experiences/', {'refuge_id': 'ref_1', 'comment': 'x'}, format='json'))
        response = ExperienceListAPIView.as_view()(request)
        assert response.status_code == 403 and response.data['error'] == 'user_blocked'

    @patch('api.views.experience_views.ExperienceController')
    def test_get_passes_viewer(self, mock_ctrl):
        mock_ctrl.return_value.get_experiences_by_refuge.return_value = ([], None)
        request = authed(APIRequestFactory().get('/api/experiences/?refuge_id=ref_1'), uid='v')
        response = ExperienceListAPIView.as_view()(request)
        assert response.status_code == 200
        mock_ctrl.return_value.get_experiences_by_refuge.assert_called_once_with('ref_1', viewer_uid='v', is_admin=False)
