"""
Tests d'integració per a usuaris.
Aquests tests proven el flux complet de Controller -> DAO -> Model.
"""

import pytest
from unittest.mock import patch
from api.controllers.user_controller import UserController
from api.controllers.refugi_lliure_controller import RefugiLliureController
from api.models.user import User
from api.models.refugi_lliure import Refugi, Coordinates, InfoComplementaria
from api.utils.timezone_utils import get_madrid_now


@pytest.mark.integration
class TestUserIntegration:
    """Tests d'integració per usuaris"""

    @patch('api.controllers.user_controller.UserDAO')
    def test_create_user_complete_flow(self, mock_dao_class):
        """Test flux complet: Controller -> DAO per crear usuari"""
        # Preparar dades
        user_data = {
            'uid': 'user_001',
            'username': 'testuser',
            'email': 'test@example.com',
            'language': 'ca',
            'avatar': 'https://example.com/avatar.jpg'
        }
        
        created_user_data = {
            **user_data,
            'favourite_refuges': [],
            'visited_refuges': [],
            'num_uploaded_photos': 0,
            'num_shared_experiences': 0,
            'num_renovated_refuges': 0,
            'created_at': get_madrid_now().isoformat()
        }
        
        # Configurar mock DAO
        mock_dao = mock_dao_class.return_value
        mock_dao.get_user_by_uid.return_value = None  # L'usuari no existeix
        mock_dao.user_exists_by_email.return_value = False
        mock_dao.create_user.return_value = User.from_dict(created_user_data)
        
        # Executar a través del controller
        controller = UserController()
        success, user, error = controller.create_user(user_data, 'user_001')
        
        # Verificar resposta
        assert success is True
        assert error is None
        assert user is not None
        assert user.uid == 'user_001'
        assert user.username == 'testuser'
        assert user.email == 'test@example.com'
        
        # Verificar crides al DAO
        mock_dao.get_user_by_uid.assert_called_once_with('user_001')
        mock_dao.create_user.assert_called_once()

    @patch('api.controllers.user_controller.UserDAO')
    def test_get_user_detail_complete_flow(self, mock_dao_class):
        """Test flux complet: Controller -> DAO per obtenir usuari"""
        # Preparar dades
        user_data = {
            'uid': 'user_001',
            'username': 'testuser',
            'email': 'test@example.com',
            'language': 'ca',
            'avatar': 'https://example.com/avatar.jpg',
            'favourite_refuges': ['refugi_001', 'refugi_002'],
            'visited_refuges': ['refugi_003'],
            'num_uploaded_photos': 5,
            'num_shared_experiences': 3,
            'num_renovated_refuges': 1,
            'created_at': get_madrid_now().isoformat()
        }
        
        # Configurar mock DAO
        mock_dao = mock_dao_class.return_value
        mock_dao.get_user_by_uid.return_value = User.from_dict(user_data)
        
        # Executar a través del controller
        controller = UserController()
        success, user, error = controller.get_user_by_uid('user_001')
        
        # Verificar resposta
        assert success is True
        assert error is None
        assert user is not None
        assert user.uid == 'user_001'
        assert user.username == 'testuser'
        assert len(user.favourite_refuges) == 2
        assert len(user.visited_refuges) == 1
        assert user.num_uploaded_photos == 5
        
        # Verificar crida al DAO
        mock_dao.get_user_by_uid.assert_called_once_with('user_001')

    @patch('api.controllers.user_controller.UserDAO')
    def test_update_user_complete_flow(self, mock_dao_class):
        """Test flux complet: Controller -> DAO per actualitzar usuari"""
        # Dades originals
        original_data = {
            'uid': 'user_001',
            'username': 'oldname',
            'email': 'test@example.com',
            'language': 'ca',
            'favourite_refuges': [],
            'visited_refuges': [],
            'num_uploaded_photos': 0,
            'num_shared_experiences': 0,
            'num_renovated_refuges': 0,
            'created_at': get_madrid_now().isoformat()
        }
        
        # Dades actualitzades
        update_data = {
            'username': 'newname',
            'language': 'es'
        }
        
        updated_data = {
            **original_data,
            'username': 'newname',
            'language': 'es'
        }
        
        # Configurar mock DAO
        mock_dao = mock_dao_class.return_value
        mock_dao.user_exists.return_value = True
        mock_dao.update_user.return_value = True
        mock_dao.get_user_by_uid.return_value = User.from_dict(updated_data)
        
        # Executar a través del controller
        controller = UserController()
        success, user, error = controller.update_user('user_001', update_data)
        
        # Verificar resposta
        assert success is True
        assert error is None
        assert user.username == 'newname'
        assert user.language == 'es'
        
        # Verificar crides al DAO
        mock_dao.user_exists.assert_called()
        mock_dao.update_user.assert_called_once()

    @patch('api.controllers.user_controller.UserDAO')
    def test_delete_user_complete_flow(self, mock_dao_class):
        """Test flux complet: Controller -> DAO per eliminar usuari"""
        # Preparar dades
        user_data = {
            'uid': 'user_001',
            'username': 'testuser',
            'email': 'test@example.com',
            'language': 'ca',
            'favourite_refuges': [],
            'visited_refuges': [],
            'num_uploaded_photos': 0,
            'num_shared_experiences': 0,
            'num_renovated_refuges': 0,
            'created_at': get_madrid_now().isoformat()
        }
        
        # Configurar mock DAO
        mock_dao = mock_dao_class.return_value
        mock_dao.user_exists.return_value = True
        mock_dao.delete_user.return_value = True
        
        # Executar a través del controller
        controller = UserController()
        success, error = controller.delete_user('user_001')
        
        # Verificar resposta
        assert success is True
        assert error is None
        
        # Verificar crides al DAO
        mock_dao.user_exists.assert_called_once_with('user_001')
        mock_dao.delete_user.assert_called_once_with('user_001')

    @patch('api.controllers.refugi_lliure_controller.RefugiLliureDAO')
    @patch('api.controllers.user_controller.UserDAO')
    def test_add_favourite_refuge_complete_flow(self, mock_user_dao_class, mock_refugi_dao_class):
        """Test flux complet: Controller -> DAO per afegir refugi favorit"""
        # Preparar dades
        user_data = {
            'uid': 'user_001',
            'username': 'testuser',
            'email': 'test@example.com',
            'language': 'ca',
            'favourite_refuges': [],
            'visited_refuges': [],
            'num_uploaded_photos': 0,
            'num_shared_experiences': 0,
            'num_renovated_refuges': 0,
            'created_at': get_madrid_now().isoformat()
        }
        
        refugi_model = Refugi(
            id='refugi_001',
            name='Refugi Test',
            departement='Ariège',
            coord=Coordinates(long=1.5, lat=42.5),
            places=10,
            altitude=2000,
            info_comp=InfoComplementaria(),
            visitors=[]
        )
        
        updated_user_data = {
            **user_data,
            'favourite_refuges': ['refugi_001']
        }
        
        # Configurar mocks
        mock_user_dao = mock_user_dao_class.return_value
        mock_user_dao.user_exists.return_value = True
        mock_user_dao.user_exists_by_email.return_value = False
        mock_user_dao.update_user.return_value = True
        mock_user_dao.get_user_by_uid.return_value = User.from_dict(updated_user_data)
        
        mock_refugi_dao = mock_refugi_dao_class.return_value
        mock_refugi_dao.get_by_id.return_value = refugi_model
        
        # Executar a través del controller
        user_controller = UserController()
        refugi_controller = RefugiLliureController()
        
        # Verificar que el refugi existeix
        refugi, refugi_error = refugi_controller.get_refugi_by_id('refugi_001')
        assert refugi is not None
        
        # Afegir refugi als favorits
        user_data['favourite_refuges'].append('refugi_001')
        success, updated_user, error = user_controller.update_user('user_001', user_data)
        
        # Verificar resposta
        assert success is True
        assert 'refugi_001' in updated_user.favourite_refuges

    @patch('api.controllers.user_controller.UserDAO')
    def test_remove_favourite_refuge_complete_flow(self, mock_dao_class):
        """Test flux complet: Controller -> DAO per eliminar refugi favorit"""
        # Preparar dades
        user_data = {
            'uid': 'user_001',
            'username': 'testuser',
            'email': 'test@example.com',
            'language': 'ca',
            'favourite_refuges': ['refugi_001', 'refugi_002'],
            'visited_refuges': [],
            'num_uploaded_photos': 0,
            'num_shared_experiences': 0,
            'num_renovated_refuges': 0,
            'created_at': get_madrid_now().isoformat()
        }
        
        updated_user_data = {
            **user_data,
            'favourite_refuges': ['refugi_002']
        }
        
        # Configurar mock
        mock_dao = mock_dao_class.return_value
        mock_dao.user_exists.return_value = True
        mock_dao.user_exists_by_email.return_value = False
        mock_dao.update_user.return_value = True
        mock_dao.get_user_by_uid.return_value = User.from_dict(updated_user_data)
        
        # Executar a través del controller
        controller = UserController()
        
        # Eliminar refugi dels favorits
        user_data['favourite_refuges'].remove('refugi_001')
        success, updated_user, error = controller.update_user('user_001', user_data)
        
        # Verificar resposta
        assert success is True
        assert 'refugi_001' not in updated_user.favourite_refuges
        assert 'refugi_002' in updated_user.favourite_refuges

    @patch('api.controllers.user_controller.UserDAO')
    def test_get_user_not_found(self, mock_dao_class):
        """Test flux complet quan un usuari no existeix"""
        # Configurar mock per retornar None
        mock_dao = mock_dao_class.return_value
        mock_dao.get_user_by_uid.return_value = None
        
        # Executar a través del controller
        controller = UserController()
        success, user, error = controller.get_user_by_uid('user_999')
        
        # Verificar resposta d'error
        assert success is False
        assert user is None
        assert error is not None

    @patch('api.controllers.user_controller.UserDAO')
    def test_create_duplicate_user(self, mock_dao_class):
        """Test flux complet quan s'intenta crear un usuari que ja existeix"""
        # Preparar dades
        existing_user_data = {
            'uid': 'user_001',
            'username': 'existinguser',
            'email': 'test@example.com',
            'language': 'ca',
            'favourite_refuges': [],
            'visited_refuges': [],
            'num_uploaded_photos': 0,
            'num_shared_experiences': 0,
            'num_renovated_refuges': 0,
            'created_at': get_madrid_now().isoformat()
        }
        
        new_user_data = {
            'uid': 'user_001',
            'username': 'newuser',
            'email': 'test@example.com',
            'language': 'ca'
        }
        
        # Configurar mock per indicar que l'usuari ja existeix
        mock_dao = mock_dao_class.return_value
        mock_dao.get_user_by_uid.return_value = User.from_dict(existing_user_data)
        
        # Executar a través del controller
        controller = UserController()
        success, user, error = controller.create_user(new_user_data, 'user_001')
        
        # Verificar resposta d'error
        assert success is False
        assert user is None
        assert error is not None
        assert 'ja existeix' in error.lower() or 'already exists' in error.lower()
