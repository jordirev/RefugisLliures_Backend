"""
Tests per a les vistes de dubtes
"""
import pytest
from unittest.mock import MagicMock, patch
from rest_framework.test import APIRequestFactory
from rest_framework import status
from api.views.doubt_views import DoubtListAPIView, DoubtDetailAPIView, AnswerListAPIView, AnswerReplyAPIView
from api.models.doubt import Doubt, Answer

@pytest.mark.views
class TestDoubtViews:
    """Tests per a les vistes de dubtes"""
    
    @pytest.fixture
    def factory(self):
        return APIRequestFactory()

    @patch('api.views.doubt_views.DoubtController')
    def test_get_doubts_list_success(self, mock_controller_class, factory):
        """Test llistar dubtes amb èxit"""
        mock_controller = mock_controller_class.return_value
        mock_doubt = MagicMock(spec=Doubt)
        mock_doubt.to_dict.return_value = {
            'id': 'doubt_1',
            'refuge_id': 'ref_1',
            'creator_uid': 'user_1',
            'message': 'Test',
            'created_at': '2024-01-01',
            'answers_count': 0,
            'answers': []
        }
        mock_controller.get_doubts_by_refuge.return_value = ([mock_doubt], None)
        
        view = DoubtListAPIView.as_view()
        request = factory.get('/api/doubts/?refuge_id=ref_1')
        request.user_uid = 'user_1'
        
        with patch.object(DoubtListAPIView, 'get_permissions', return_value=[]):
            response = view(request)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1

    @patch('api.views.doubt_views.DoubtController')
    def test_create_doubt_success(self, mock_controller_class, factory):
        """Test crear dubte amb èxit"""
        mock_controller = mock_controller_class.return_value
        mock_doubt = MagicMock(spec=Doubt)
        mock_doubt.to_dict.return_value = {
            'id': 'doubt_1',
            'refuge_id': 'ref_1',
            'creator_uid': 'user_1',
            'message': 'Test',
            'created_at': '2024-01-01',
            'answers_count': 0
        }
        mock_controller.create_doubt.return_value = (mock_doubt, None)
        
        view = DoubtListAPIView.as_view()
        data = {'refuge_id': 'ref_1', 'message': 'Test'}
        request = factory.post('/api/doubts/', data, format='json')
        request.user_uid = 'user_1'
        
        with patch.object(DoubtListAPIView, 'get_permissions', return_value=[]):
            response = view(request)
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['id'] == 'doubt_1'

    @patch('api.views.doubt_views.DoubtController')
    def test_delete_doubt_success(self, mock_controller_class, factory):
        """Test eliminar dubte amb èxit"""
        mock_controller = mock_controller_class.return_value
        mock_controller.delete_doubt.return_value = (True, None)
        
        view = DoubtDetailAPIView.as_view()
        request = factory.delete('/api/doubts/doubt_1/')
        request.user_uid = 'user_1'
        
        with patch.object(DoubtDetailAPIView, 'get_permissions', return_value=[]):
            response = view(request, doubt_id='doubt_1')
        
        assert response.status_code == status.HTTP_204_NO_CONTENT

    @patch('api.views.doubt_views.DoubtController')
    def test_create_answer_success(self, mock_controller_class, factory):
        """Test crear resposta amb èxit"""
        mock_controller = mock_controller_class.return_value
        mock_answer = MagicMock(spec=Answer)
        mock_answer.to_dict.return_value = {
            'id': 'ans_1',
            'creator_uid': 'user_1',
            'message': 'Reply',
            'created_at': '2024-01-01',
            'parent_answer_id': None
        }
        mock_controller.create_answer.return_value = (mock_answer, None)
        
        view = AnswerListAPIView.as_view()
        data = {'message': 'Reply'}
        request = factory.post('/api/doubts/doubt_1/answers/', data, format='json')
        request.user_uid = 'user_1'
        
        with patch.object(AnswerListAPIView, 'get_permissions', return_value=[]):
            response = view(request, doubt_id='doubt_1')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['id'] == 'ans_1'

    @patch('api.views.doubt_views.DoubtController')
    def test_delete_answer_success(self, mock_controller_class, factory):
        """Test eliminar resposta amb èxit"""
        mock_controller = mock_controller_class.return_value
        mock_controller.delete_answer.return_value = (True, None)
        
        view = AnswerReplyAPIView.as_view()
        request = factory.delete('/api/doubts/doubt_1/answers/ans_1/')
        request.user_uid = 'user_1'
        
        with patch.object(AnswerReplyAPIView, 'get_permissions', return_value=[]):
            response = view(request, doubt_id='doubt_1', answer_id='ans_1')
        
        assert response.status_code == status.HTTP_204_NO_CONTENT

    # ===== TESTS D'ERROR PER MILLORAR COVERAGE =====

    @patch('api.views.doubt_views.DoubtController')
    def test_get_doubts_list_missing_refuge_id(self, mock_controller_class, factory):
        """Test llistar dubtes sense refuge_id (400)"""
        view = DoubtListAPIView.as_view()
        request = factory.get('/api/doubts/')
        request.user_uid = 'user_1'
        
        with patch.object(DoubtListAPIView, 'get_permissions', return_value=[]):
            response = view(request)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'refuge_id' in str(response.data['error']).lower()

    @patch('api.views.doubt_views.DoubtController')
    def test_get_doubts_list_not_found(self, mock_controller_class, factory):
        """Test llistar dubtes amb error not found (404)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.get_doubts_by_refuge.return_value = (None, "Refuge not found")
        
        view = DoubtListAPIView.as_view()
        request = factory.get('/api/doubts/?refuge_id=nonexistent')
        request.user_uid = 'user_1'
        
        with patch.object(DoubtListAPIView, 'get_permissions', return_value=[]):
            response = view(request)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch('api.views.doubt_views.DoubtController')
    def test_get_doubts_list_server_error(self, mock_controller_class, factory):
        """Test llistar dubtes amb error del servidor (500)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.get_doubts_by_refuge.return_value = (None, "Internal error")
        
        view = DoubtListAPIView.as_view()
        request = factory.get('/api/doubts/?refuge_id=ref_1')
        request.user_uid = 'user_1'
        
        with patch.object(DoubtListAPIView, 'get_permissions', return_value=[]):
            response = view(request)
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @patch('api.views.doubt_views.DoubtController')
    def test_get_doubts_list_exception(self, mock_controller_class, factory):
        """Test llistar dubtes amb excepció (500)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.get_doubts_by_refuge.side_effect = Exception("Error inesperat")
        
        view = DoubtListAPIView.as_view()
        request = factory.get('/api/doubts/?refuge_id=ref_1')
        request.user_uid = 'user_1'
        
        with patch.object(DoubtListAPIView, 'get_permissions', return_value=[]):
            response = view(request)
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @patch('api.views.doubt_views.DoubtController')
    def test_create_doubt_invalid_data(self, mock_controller_class, factory):
        """Test crear dubte amb dades invàlides (400)"""
        view = DoubtListAPIView.as_view()
        data = {'refuge_id': 'ref_1'}  # Falta message
        request = factory.post('/api/doubts/', data, format='json')
        request.user_uid = 'user_1'
        
        with patch.object(DoubtListAPIView, 'get_permissions', return_value=[]):
            response = view(request)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @patch('api.views.doubt_views.DoubtController')
    def test_create_doubt_no_uid(self, mock_controller_class, factory):
        """Test crear dubte sense UID (401)"""
        view = DoubtListAPIView.as_view()
        data = {'refuge_id': 'ref_1', 'message': 'Test'}
        request = factory.post('/api/doubts/', data, format='json')
        # No establim request.user_uid
        
        with patch.object(DoubtListAPIView, 'get_permissions', return_value=[]):
            response = view(request)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @patch('api.views.doubt_views.DoubtController')
    def test_create_doubt_not_found(self, mock_controller_class, factory):
        """Test crear dubte en refugi no trobat (404)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.create_doubt.return_value = (None, "Refuge not found")
        
        view = DoubtListAPIView.as_view()
        data = {'refuge_id': 'nonexistent', 'message': 'Test'}
        request = factory.post('/api/doubts/', data, format='json')
        request.user_uid = 'user_1'
        
        with patch.object(DoubtListAPIView, 'get_permissions', return_value=[]):
            response = view(request)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch('api.views.doubt_views.DoubtController')
    def test_create_doubt_server_error(self, mock_controller_class, factory):
        """Test crear dubte amb error del servidor (500)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.create_doubt.return_value = (None, "Database error")
        
        view = DoubtListAPIView.as_view()
        data = {'refuge_id': 'ref_1', 'message': 'Test'}
        request = factory.post('/api/doubts/', data, format='json')
        request.user_uid = 'user_1'
        
        with patch.object(DoubtListAPIView, 'get_permissions', return_value=[]):
            response = view(request)
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @patch('api.views.doubt_views.DoubtController')
    def test_create_doubt_exception(self, mock_controller_class, factory):
        """Test crear dubte amb excepció (500)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.create_doubt.side_effect = Exception("Error inesperat")
        
        view = DoubtListAPIView.as_view()
        data = {'refuge_id': 'ref_1', 'message': 'Test'}
        request = factory.post('/api/doubts/', data, format='json')
        request.user_uid = 'user_1'
        
        with patch.object(DoubtListAPIView, 'get_permissions', return_value=[]):
            response = view(request)
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @patch('api.views.doubt_views.DoubtController')
    def test_delete_doubt_no_uid(self, mock_controller_class, factory):
        """Test eliminar dubte sense UID (401)"""
        view = DoubtDetailAPIView.as_view()
        request = factory.delete('/api/doubts/doubt_1/')
        # No establim request.user_uid
        
        with patch.object(DoubtDetailAPIView, 'get_permissions', return_value=[]):
            response = view(request, doubt_id='doubt_1')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @patch('api.views.doubt_views.DoubtController')
    def test_delete_doubt_not_found(self, mock_controller_class, factory):
        """Test eliminar dubte no trobat (404)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.delete_doubt.return_value = (False, "Doubt not found")
        
        view = DoubtDetailAPIView.as_view()
        request = factory.delete('/api/doubts/doubt_1/')
        request.user_uid = 'user_1'
        
        with patch.object(DoubtDetailAPIView, 'get_permissions', return_value=[]):
            response = view(request, doubt_id='doubt_1')
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch('api.views.doubt_views.DoubtController')
    def test_delete_doubt_server_error(self, mock_controller_class, factory):
        """Test eliminar dubte amb error del servidor (500)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.delete_doubt.return_value = (False, "Database error")
        
        view = DoubtDetailAPIView.as_view()
        request = factory.delete('/api/doubts/doubt_1/')
        request.user_uid = 'user_1'
        
        with patch.object(DoubtDetailAPIView, 'get_permissions', return_value=[]):
            response = view(request, doubt_id='doubt_1')
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @patch('api.views.doubt_views.DoubtController')
    def test_delete_doubt_returns_false(self, mock_controller_class, factory):
        """Test eliminar dubte retorna False (500)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.delete_doubt.return_value = (False, None)
        
        view = DoubtDetailAPIView.as_view()
        request = factory.delete('/api/doubts/doubt_1/')
        request.user_uid = 'user_1'
        
        with patch.object(DoubtDetailAPIView, 'get_permissions', return_value=[]):
            response = view(request, doubt_id='doubt_1')
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @patch('api.views.doubt_views.DoubtController')
    def test_delete_doubt_exception(self, mock_controller_class, factory):
        """Test eliminar dubte amb excepció (500)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.delete_doubt.side_effect = Exception("Error inesperat")
        
        view = DoubtDetailAPIView.as_view()
        request = factory.delete('/api/doubts/doubt_1/')
        request.user_uid = 'user_1'
        
        with patch.object(DoubtDetailAPIView, 'get_permissions', return_value=[]):
            response = view(request, doubt_id='doubt_1')
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @patch('api.views.doubt_views.DoubtController')
    def test_create_answer_invalid_data(self, mock_controller_class, factory):
        """Test crear resposta amb dades invàlides (400)"""
        view = AnswerListAPIView.as_view()
        data = {}  # Falta message
        request = factory.post('/api/doubts/doubt_1/answers/', data, format='json')
        request.user_uid = 'user_1'
        
        with patch.object(AnswerListAPIView, 'get_permissions', return_value=[]):
            response = view(request, doubt_id='doubt_1')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @patch('api.views.doubt_views.DoubtController')
    def test_create_answer_no_uid(self, mock_controller_class, factory):
        """Test crear resposta sense UID (401)"""
        view = AnswerListAPIView.as_view()
        data = {'message': 'Reply'}
        request = factory.post('/api/doubts/doubt_1/answers/', data, format='json')
        # No establim request.user_uid
        
        with patch.object(AnswerListAPIView, 'get_permissions', return_value=[]):
            response = view(request, doubt_id='doubt_1')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @patch('api.views.doubt_views.DoubtController')
    def test_create_answer_doubt_not_found(self, mock_controller_class, factory):
        """Test crear resposta a dubte no trobat (404)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.create_answer.return_value = (None, "Doubt not found")
        
        view = AnswerListAPIView.as_view()
        data = {'message': 'Reply'}
        request = factory.post('/api/doubts/doubt_1/answers/', data, format='json')
        request.user_uid = 'user_1'
        
        with patch.object(AnswerListAPIView, 'get_permissions', return_value=[]):
            response = view(request, doubt_id='doubt_1')
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch('api.views.doubt_views.DoubtController')
    def test_create_answer_server_error(self, mock_controller_class, factory):
        """Test crear resposta amb error del servidor (500)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.create_answer.return_value = (None, "Database error")
        
        view = AnswerListAPIView.as_view()
        data = {'message': 'Reply'}
        request = factory.post('/api/doubts/doubt_1/answers/', data, format='json')
        request.user_uid = 'user_1'
        
        with patch.object(AnswerListAPIView, 'get_permissions', return_value=[]):
            response = view(request, doubt_id='doubt_1')
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @patch('api.views.doubt_views.DoubtController')
    def test_create_answer_exception(self, mock_controller_class, factory):
        """Test crear resposta amb excepció (500)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.create_answer.side_effect = Exception("Error inesperat")
        
        view = AnswerListAPIView.as_view()
        data = {'message': 'Reply'}
        request = factory.post('/api/doubts/doubt_1/answers/', data, format='json')
        request.user_uid = 'user_1'
        
        with patch.object(AnswerListAPIView, 'get_permissions', return_value=[]):
            response = view(request, doubt_id='doubt_1')
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @patch('api.views.doubt_views.DoubtController')
    def test_delete_answer_no_uid(self, mock_controller_class, factory):
        """Test eliminar resposta sense UID (401)"""
        view = AnswerReplyAPIView.as_view()
        request = factory.delete('/api/doubts/doubt_1/answers/ans_1/')
        # No establim request.user_uid
        
        with patch.object(AnswerReplyAPIView, 'get_permissions', return_value=[]):
            response = view(request, doubt_id='doubt_1', answer_id='ans_1')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @patch('api.views.doubt_views.DoubtController')
    def test_delete_answer_not_found(self, mock_controller_class, factory):
        """Test eliminar resposta no trobada (404)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.delete_answer.return_value = (False, "Answer not found")
        
        view = AnswerReplyAPIView.as_view()
        request = factory.delete('/api/doubts/doubt_1/answers/ans_1/')
        request.user_uid = 'user_1'
        
        with patch.object(AnswerReplyAPIView, 'get_permissions', return_value=[]):
            response = view(request, doubt_id='doubt_1', answer_id='ans_1')
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch('api.views.doubt_views.DoubtController')
    def test_delete_answer_server_error(self, mock_controller_class, factory):
        """Test eliminar resposta amb error del servidor (500)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.delete_answer.return_value = (False, "Database error")
        
        view = AnswerReplyAPIView.as_view()
        request = factory.delete('/api/doubts/doubt_1/answers/ans_1/')
        request.user_uid = 'user_1'
        
        with patch.object(AnswerReplyAPIView, 'get_permissions', return_value=[]):
            response = view(request, doubt_id='doubt_1', answer_id='ans_1')
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @patch('api.views.doubt_views.DoubtController')
    def test_delete_answer_exception(self, mock_controller_class, factory):
        """Test eliminar resposta amb excepció (500)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.delete_answer.side_effect = Exception("Error inesperat")
        
        view = AnswerReplyAPIView.as_view()
        request = factory.delete('/api/doubts/doubt_1/answers/ans_1/')
        request.user_uid = 'user_1'
        
        with patch.object(AnswerReplyAPIView, 'get_permissions', return_value=[]):
            response = view(request, doubt_id='doubt_1', answer_id='ans_1')
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    # ===== TESTS PER AnswerReplyAPIView.post (respostes a respostes) =====

    @patch('api.views.doubt_views.DoubtController')
    def test_post_reply_to_answer_success(self, mock_controller_class, factory):
        """Test crear resposta a una resposta amb èxit"""
        mock_controller = mock_controller_class.return_value
        mock_answer = MagicMock(spec=Answer)
        mock_answer.to_dict.return_value = {
            'id': 'reply_1',
            'creator_uid': 'user_1',
            'message': 'Nested reply',
            'created_at': '2024-01-01',
            'parent_answer_id': 'ans_1'
        }
        mock_controller.create_answer.return_value = (mock_answer, None)
        
        view = AnswerReplyAPIView.as_view()
        data = {'message': 'Nested reply'}
        request = factory.post('/api/doubts/doubt_1/answers/ans_1/', data, format='json')
        request.user_uid = 'user_1'
        
        with patch.object(AnswerReplyAPIView, 'get_permissions', return_value=[]):
            response = view(request, doubt_id='doubt_1', answer_id='ans_1')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['id'] == 'reply_1'
        assert response.data['parent_answer_id'] == 'ans_1'

    @patch('api.views.doubt_views.DoubtController')
    def test_post_reply_to_answer_invalid_data(self, mock_controller_class, factory):
        """Test crear resposta a una resposta amb dades invàlides (400)"""
        view = AnswerReplyAPIView.as_view()
        data = {}  # Falta message
        request = factory.post('/api/doubts/doubt_1/answers/ans_1/', data, format='json')
        request.user_uid = 'user_1'
        
        with patch.object(AnswerReplyAPIView, 'get_permissions', return_value=[]):
            response = view(request, doubt_id='doubt_1', answer_id='ans_1')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data

    @patch('api.views.doubt_views.DoubtController')
    def test_post_reply_to_answer_no_uid(self, mock_controller_class, factory):
        """Test crear resposta a una resposta sense UID (401)"""
        view = AnswerReplyAPIView.as_view()
        data = {'message': 'Reply'}
        request = factory.post('/api/doubts/doubt_1/answers/ans_1/', data, format='json')
        # No establim request.user_uid
        
        with patch.object(AnswerReplyAPIView, 'get_permissions', return_value=[]):
            response = view(request, doubt_id='doubt_1', answer_id='ans_1')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @patch('api.views.doubt_views.DoubtController')
    def test_post_reply_to_answer_not_found(self, mock_controller_class, factory):
        """Test crear resposta quan el dubte no existeix (404)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.create_answer.return_value = (None, "Doubt not found")
        
        view = AnswerReplyAPIView.as_view()
        data = {'message': 'Reply'}
        request = factory.post('/api/doubts/doubt_1/answers/ans_1/', data, format='json')
        request.user_uid = 'user_1'
        
        with patch.object(AnswerReplyAPIView, 'get_permissions', return_value=[]):
            response = view(request, doubt_id='doubt_1', answer_id='ans_1')
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch('api.views.doubt_views.DoubtController')
    def test_post_reply_to_answer_server_error(self, mock_controller_class, factory):
        """Test crear resposta amb error del servidor (500)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.create_answer.return_value = (None, "Database error")
        
        view = AnswerReplyAPIView.as_view()
        data = {'message': 'Reply'}
        request = factory.post('/api/doubts/doubt_1/answers/ans_1/', data, format='json')
        request.user_uid = 'user_1'
        
        with patch.object(AnswerReplyAPIView, 'get_permissions', return_value=[]):
            response = view(request, doubt_id='doubt_1', answer_id='ans_1')
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @patch('api.views.doubt_views.DoubtController')
    def test_post_reply_to_answer_exception(self, mock_controller_class, factory):
        """Test crear resposta amb excepció (500)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.create_answer.side_effect = Exception("Error inesperat")
        
        view = AnswerReplyAPIView.as_view()
        data = {'message': 'Reply'}
        request = factory.post('/api/doubts/doubt_1/answers/ans_1/', data, format='json')
        request.user_uid = 'user_1'
        
        with patch.object(AnswerReplyAPIView, 'get_permissions', return_value=[]):
            response = view(request, doubt_id='doubt_1', answer_id='ans_1')
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @patch('api.views.doubt_views.DoubtController')
    def test_delete_reply_answer_returns_false_no_error(self, mock_controller_class, factory):
        """Test eliminar resposta retorna False sense error (500)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.delete_answer.return_value = (False, None)
        
        view = AnswerReplyAPIView.as_view()
        request = factory.delete('/api/doubts/doubt_1/answers/ans_1/')
        request.user_uid = 'user_1'
        
        with patch.object(AnswerReplyAPIView, 'get_permissions', return_value=[]):
            response = view(request, doubt_id='doubt_1', answer_id='ans_1')
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    # ===== TESTS PER get_permissions de AnswerReplyAPIView =====

    def test_answer_reply_get_permissions_post(self, factory):
        """Test permisos per POST en AnswerReplyAPIView"""
        view = AnswerReplyAPIView()
        view.request = factory.post('/api/doubts/doubt_1/answers/ans_1/')
        permissions = view.get_permissions()
        assert len(permissions) == 1

    def test_answer_reply_get_permissions_delete(self, factory):
        """Test permisos per DELETE en AnswerReplyAPIView"""
        view = AnswerReplyAPIView()
        view.request = factory.delete('/api/doubts/doubt_1/answers/ans_1/')
        permissions = view.get_permissions()
        # DELETE requereix IsAuthenticated i IsAnswerCreator
        assert len(permissions) == 2

    def test_answer_reply_get_permissions_other(self, factory):
        """Test permisos per altres mètodes en AnswerReplyAPIView"""
        view = AnswerReplyAPIView()
        view.request = factory.get('/api/doubts/doubt_1/answers/ans_1/')
        permissions = view.get_permissions()
        assert len(permissions) == 1
