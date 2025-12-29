"""
Tests extensos per als permisos personalitzats a api/permissions.py
"""
import pytest
from unittest.mock import MagicMock, patch
from rest_framework import permissions
from api.permissions import (
    is_firebase_admin, IsOwnerOrReadOnly, IsSameUser, SafeMethodsOnly,
    IsFirebaseAdmin, IsExperienceCreator, IsRenovationCreator,
    IsMediaUploader, IsDoubtCreator, IsAnswerCreator
)

class TestPermissionsExtended:
    """Tests per a totes les classes de permisos"""

    def test_is_firebase_admin_helper(self):
        """Test la funció helper is_firebase_admin"""
        # Cas admin a request.user_claims
        request = MagicMock()
        request.user_claims = {'role': 'admin'}
        assert is_firebase_admin(request) is True

        # Cas no admin a request.user_claims
        request.user_claims = {'role': 'user'}
        assert is_firebase_admin(request) is False

        # Cas admin a request.user.claims
        request = MagicMock()
        request.user_claims = {}
        request.user.claims = {'role': 'admin'}
        assert is_firebase_admin(request) is True

        # Cas cap claim
        request.user.claims = {}
        assert is_firebase_admin(request) is False

    def test_is_owner_or_read_only(self):
        """Test IsOwnerOrReadOnly"""
        perm = IsOwnerOrReadOnly()
        view = MagicMock()
        
        # has_permission
        request = MagicMock()
        request.user.is_authenticated = True
        assert perm.has_permission(request, view) is True
        
        request.user.is_authenticated = False
        assert perm.has_permission(request, view) is False

        # has_object_permission
        obj = MagicMock(uid='user_1')
        request.user.uid = 'user_1'
        request.method = 'GET'
        assert perm.has_object_permission(request, view, obj) is True
        
        request.method = 'POST'
        assert perm.has_object_permission(request, view, obj) is True
        
        request.user.uid = 'user_2'
        assert perm.has_object_permission(request, view, obj) is False

    def test_safe_methods_only(self):
        """Test SafeMethodsOnly"""
        perm = SafeMethodsOnly()
        request = MagicMock()
        view = MagicMock()
        
        for method in ['GET', 'HEAD', 'OPTIONS']:
            request.method = method
            assert perm.has_permission(request, view) is True
            
        for method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            request.method = method
            assert perm.has_permission(request, view) is False

    def test_is_firebase_admin_permission(self):
        """Test IsFirebaseAdmin class"""
        perm = IsFirebaseAdmin()
        request = MagicMock()
        view = MagicMock()
        
        request.user.is_authenticated = True
        with patch('api.permissions.is_firebase_admin', return_value=True):
            assert perm.has_permission(request, view) is True
            
        with patch('api.permissions.is_firebase_admin', return_value=False):
            assert perm.has_permission(request, view) is False
            
        request.user.is_authenticated = False
        assert perm.has_permission(request, view) is False

    @patch('api.daos.experience_dao.ExperienceDAO')
    def test_is_experience_creator(self, mock_dao_class):
        """Test IsExperienceCreator"""
        perm = IsExperienceCreator()
        request = MagicMock()
        view = MagicMock()
        obj = MagicMock()
        
        # has_permission
        request.user.is_authenticated = True
        assert perm.has_permission(request, view) is True
        
        # has_object_permission - Admin
        with patch('api.permissions.is_firebase_admin', return_value=True):
            assert perm.has_object_permission(request, view, obj) is True
            
        # has_object_permission - Safe Method
        with patch('api.permissions.is_firebase_admin', return_value=False):
            request.method = 'GET'
            assert perm.has_object_permission(request, view, obj) is True
            
            # Non-safe method, no experience_id (creation)
            request.method = 'POST'
            view.kwargs = {}
            assert perm.has_object_permission(request, view, obj) is True
            
            # Non-safe method, with experience_id
            view.kwargs = {'experience_id': 'exp_1'}
            request.user_uid = 'user_1'
            mock_dao = mock_dao_class.return_value
            mock_dao.get_experience_by_id.return_value = {'creator_uid': 'user_1'}
            assert perm.has_object_permission(request, view, obj) is True
            
            mock_dao.get_experience_by_id.return_value = {'creator_uid': 'user_2'}
            assert perm.has_object_permission(request, view, obj) is False
            
            # No user_uid in request
            request.user_uid = None
            assert perm.has_object_permission(request, view, obj) is False

    @patch('api.daos.renovation_dao.RenovationDAO')
    def test_is_renovation_creator(self, mock_dao_class):
        """Test IsRenovationCreator"""
        perm = IsRenovationCreator()
        request = MagicMock()
        view = MagicMock()
        obj = MagicMock()
        
        # has_permission
        request.user.is_authenticated = True
        assert perm.has_permission(request, view) is True
        
        # has_object_permission - Admin
        with patch('api.permissions.is_firebase_admin', return_value=True):
            assert perm.has_object_permission(request, view, obj) is True
            
        # has_object_permission - Safe Method
        with patch('api.permissions.is_firebase_admin', return_value=False):
            request.method = 'GET'
            assert perm.has_object_permission(request, view, obj) is True
            
            # Non-safe method, no id (creation)
            request.method = 'POST'
            view.kwargs = {}
            assert perm.has_object_permission(request, view, obj) is True
            
            # Non-safe method, with id
            view.kwargs = {'id': 'ren_1'}
            request.user_uid = 'user_1'
            mock_dao = mock_dao_class.return_value
            mock_dao.get_renovation_by_id.return_value = {'creator_uid': 'user_1'}
            assert perm.has_object_permission(request, view, obj) is True
            
            mock_dao.get_renovation_by_id.return_value = {'creator_uid': 'user_2'}
            assert perm.has_object_permission(request, view, obj) is False

    @patch('api.permissions.firestore_service')
    def test_is_media_uploader(self, mock_firestore):
        """Test IsMediaUploader"""
        perm = IsMediaUploader()
        request = MagicMock()
        view = MagicMock()
        
        # Not authenticated
        request.user.is_authenticated = False
        assert perm.has_permission(request, view) is False
        
        # Authenticated, Safe Method
        request.user.is_authenticated = True
        request.method = 'GET'
        assert perm.has_permission(request, view) is True
        
        # Non-safe method, missing params
        request.method = 'DELETE'
        view.kwargs = {}
        assert perm.has_permission(request, view) is True
        
        # Admin
        view.kwargs = {'id': 'ref_1', 'key': 'media_1'}
        request.user.uid = 'admin_1'
        request.user_claims = {'role': 'admin'}
        assert perm.has_permission(request, view) is True
        
        # Owner check
        request.user_claims = {}
        request.user.claims = {}
        request.user.uid = 'user_1'
        
        mock_db = mock_firestore.get_db.return_value
        mock_doc = mock_db.collection.return_value.document.return_value.get.return_value
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            'media_metadata': {
                'media_1': {'creator_uid': 'user_1'}
            }
        }
        assert perm.has_permission(request, view) is True
        
        mock_doc.to_dict.return_value = {
            'media_metadata': {
                'media_1': {'creator_uid': 'user_2'}
            }
        }
        assert perm.has_permission(request, view) is False
        
        # Refugi without media_metadata
        mock_doc.to_dict.return_value = {'media_metadata': {}}
        assert perm.has_permission(request, view) is False
        
        # Media key not in metadata
        mock_doc.to_dict.return_value = {'media_metadata': {'other_media': {}}}
        assert perm.has_permission(request, view) is False
        
        # Exception in IsMediaUploader
        mock_db.collection.side_effect = Exception("DB Error")
        assert perm.has_permission(request, view) is False

    @patch('api.controllers.doubt_controller.DoubtController')
    def test_is_doubt_creator(self, mock_controller_class):
        """Test IsDoubtCreator"""
        perm = IsDoubtCreator()
        request = MagicMock()
        view = MagicMock()
        obj = MagicMock()
        
        # has_permission
        request.user.is_authenticated = True
        assert perm.has_permission(request, view) is True
        
        # has_object_permission - Admin
        with patch('api.permissions.is_firebase_admin', return_value=True):
            assert perm.has_object_permission(request, view, obj) is True
            
        # has_object_permission - Safe Method
        with patch('api.permissions.is_firebase_admin', return_value=False):
            request.method = 'GET'
            assert perm.has_object_permission(request, view, obj) is True
            
            # Non-safe method, no doubt_id
            request.method = 'DELETE'
            view.kwargs = {}
            assert perm.has_object_permission(request, view, obj) is True
            
            # Non-safe method, with doubt_id
            view.kwargs = {'doubt_id': 'doubt_1'}
            request.user_uid = 'user_1'
            mock_controller = mock_controller_class.return_value
            mock_doubt = MagicMock()
            mock_doubt.creator_uid = 'user_1'
            mock_controller.get_doubt_by_id.return_value = mock_doubt
            assert perm.has_object_permission(request, view, obj) is True
            
            mock_doubt.creator_uid = 'user_2'
            assert perm.has_object_permission(request, view, obj) is False
            
            # Doubt not found
            mock_controller.get_doubt_by_id.return_value = None
            assert perm.has_object_permission(request, view, obj) is False
            
            # No user_uid
            request.user_uid = None
            assert perm.has_object_permission(request, view, obj) is False

    @patch('api.controllers.doubt_controller.DoubtController')
    def test_is_answer_creator(self, mock_controller_class):
        """Test IsAnswerCreator"""
        perm = IsAnswerCreator()
        request = MagicMock()
        view = MagicMock()
        obj = MagicMock()
        
        # has_object_permission - Non-safe method, with IDs
        with patch('api.permissions.is_firebase_admin', return_value=False):
            request.method = 'DELETE'
            view.kwargs = {'doubt_id': 'doubt_1', 'answer_id': 'ans_1'}
            request.user_uid = 'user_1'
            mock_controller = mock_controller_class.return_value
            mock_answer = MagicMock()
            mock_answer.creator_uid = 'user_1'
            mock_controller.get_answer_by_id.return_value = mock_answer
            assert perm.has_object_permission(request, view, obj) is True
            
            mock_answer.creator_uid = 'user_2'
            assert perm.has_object_permission(request, view, obj) is False
            
            mock_controller.get_answer_by_id.return_value = None
            assert perm.has_object_permission(request, view, obj) is False
            
            # No user_uid
            request.user_uid = None
            assert perm.has_object_permission(request, view, obj) is False
