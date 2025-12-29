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
