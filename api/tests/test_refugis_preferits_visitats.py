"""
Tests exhaustius per a la gestió de refugis preferits i visitats
Cobreix: Controllers, DAOs i totes les branques d'execució
"""
import pytest
from unittest.mock import Mock, MagicMock, patch

from api.controllers.user_controller import UserController
from api.daos.user_dao import UserDAO
from api.daos.refugi_lliure_dao import RefugiLliureDAO

from rest_framework import status
from rest_framework.test import APIRequestFactory

from api.views.user_views import (
    UserFavouriteRefugesAPIView,
    UserFavouriteRefugesDetailAPIView,
    UserVisitedRefugesAPIView,
    UserVisitedRefugesDetailAPIView
)


# ==================== FIXTURES ====================

@pytest.fixture
def user_controller():
    """Controller d'usuaris amb DAOs mockejats"""
    controller = UserController()
    controller.user_dao = Mock(spec=UserDAO)
    controller.refugi_dao = Mock(spec=RefugiLliureDAO)
    return controller


@pytest.fixture
def sample_uid():
    """UID d'usuari de prova"""
    return "test_user_uid_123"


@pytest.fixture
def sample_refugi_id():
    """ID de refugi de prova"""
    return "refugi_001"


@pytest.fixture
def sample_refugi_ids():
    """Llista d'IDs de refugis de prova"""
    return ["refugi_001", "refugi_002", "refugi_003"]


@pytest.fixture
def sample_refugis_info():
    """Informació de refugis de mostra"""
    return [
        {
            'id': 'refugi_001',
            'name': 'Refugi A',
            'region': 'Pirineus',
            'places': 10,
            'coordinates': {'long': 1.5, 'lat': 42.5}
        },
        {
            'id': 'refugi_002',
            'name': 'Refugi B',
            'region': 'Pirineus',
            'places': 15,
            'coordinates': {'long': 1.6, 'lat': 42.6}
        }
    ]


# ==================== TESTS REFUGIS PREFERITS ====================

@pytest.mark.controller
class TestAddRefugiPreferit:
    """Tests per add_refugi_preferit"""
    
    def test_add_refugi_preferit_success(self, user_controller, sample_uid, sample_refugi_id, sample_refugis_info):
        """Test afegir refugi preferit amb èxit"""
        # Arrange
        user_controller.user_dao.user_exists.return_value = True
        user_controller.refugi_dao.refugi_exists.return_value = True
        user_controller.user_dao.add_refugi_to_list.return_value = (True, [sample_refugi_id])
        user_controller.user_dao.get_refugis_info.return_value = sample_refugis_info
        
        # Act
        success, refugis_info, error = user_controller.add_refugi_preferit(sample_uid, sample_refugi_id)
        
        # Assert
        assert success is True
        assert refugis_info == sample_refugis_info
        assert error is None
        user_controller.user_dao.user_exists.assert_called_once_with(sample_uid)
        user_controller.refugi_dao.refugi_exists.assert_called_once_with(sample_refugi_id)
        user_controller.user_dao.add_refugi_to_list.assert_called_once_with(
            sample_uid, sample_refugi_id, 'favourite_refuges'
        )
        user_controller.user_dao.get_refugis_info.assert_called_once_with(
            sample_uid, 'favourite_refuges', refugis_ids=[sample_refugi_id]
        )
    
    def test_add_refugi_preferit_uid_empty(self, user_controller, sample_refugi_id):
        """Test afegir refugi preferit amb UID buit"""
        # Act
        success, refugis_info, error = user_controller.add_refugi_preferit("", sample_refugi_id)
        
        # Assert
        assert success is False
        assert refugis_info is None
        assert error == "UID no proporcionat"
        user_controller.user_dao.user_exists.assert_not_called()
    
    def test_add_refugi_preferit_uid_none(self, user_controller, sample_refugi_id):
        """Test afegir refugi preferit amb UID None"""
        # Act
        success, refugis_info, error = user_controller.add_refugi_preferit(None, sample_refugi_id)
        
        # Assert
        assert success is False
        assert refugis_info is None
        assert error == "UID no proporcionat"
    
    def test_add_refugi_preferit_refugi_id_empty(self, user_controller, sample_uid):
        """Test afegir refugi preferit amb refuge_id buit"""
        # Act
        success, refugis_info, error = user_controller.add_refugi_preferit(sample_uid, "")
        
        # Assert
        assert success is False
        assert refugis_info is None
        assert error == "ID del refugi no proporcionat"
    
    def test_add_refugi_preferit_refugi_id_none(self, user_controller, sample_uid):
        """Test afegir refugi preferit amb refuge_id None"""
        # Act
        success, refugis_info, error = user_controller.add_refugi_preferit(sample_uid, None)
        
        # Assert
        assert success is False
        assert refugis_info is None
        assert error == "ID del refugi no proporcionat"
    
    def test_add_refugi_preferit_user_not_exists(self, user_controller, sample_uid, sample_refugi_id):
        """Test afegir refugi preferit quan l'usuari no existeix"""
        # Arrange
        user_controller.user_dao.user_exists.return_value = False
        
        # Act
        success, refugis_info, error = user_controller.add_refugi_preferit(sample_uid, sample_refugi_id)
        
        # Assert
        assert success is False
        assert refugis_info is None
        assert error == f"Usuari amb UID {sample_uid} no trobat"
        user_controller.user_dao.user_exists.assert_called_once_with(sample_uid)
        user_controller.refugi_dao.refugi_exists.assert_not_called()
    
    def test_add_refugi_preferit_refugi_not_exists(self, user_controller, sample_uid, sample_refugi_id):
        """Test afegir refugi preferit quan el refugi no existeix"""
        # Arrange
        user_controller.user_dao.user_exists.return_value = True
        user_controller.refugi_dao.refugi_exists.return_value = False
        
        # Act
        success, refugis_info, error = user_controller.add_refugi_preferit(sample_uid, sample_refugi_id)
        
        # Assert
        assert success is False
        assert refugis_info is None
        assert error == f"Refugi amb ID {sample_refugi_id} no trobat"
        user_controller.refugi_dao.refugi_exists.assert_called_once_with(sample_refugi_id)
    
    def test_add_refugi_preferit_dao_add_fails(self, user_controller, sample_uid, sample_refugi_id):
        """Test afegir refugi preferit quan falla el DAO"""
        # Arrange
        user_controller.user_dao.user_exists.return_value = True
        user_controller.refugi_dao.refugi_exists.return_value = True
        user_controller.user_dao.add_refugi_to_list.return_value = (False, None)
        
        # Act
        success, refugis_info, error = user_controller.add_refugi_preferit(sample_uid, sample_refugi_id)
        
        # Assert
        assert success is False
        assert refugis_info is None
        assert error == "Error afegint refugi als preferits"
    
    def test_add_refugi_preferit_exception(self, user_controller, sample_uid, sample_refugi_id):
        """Test afegir refugi preferit amb excepció"""
        # Arrange
        user_controller.user_dao.user_exists.side_effect = Exception("Database error")
        
        # Act
        success, refugis_info, error = user_controller.add_refugi_preferit(sample_uid, sample_refugi_id)
        
        # Assert
        assert success is False
        assert refugis_info is None
        assert "Error intern: Database error" in error


@pytest.mark.controller
class TestRemoveRefugiPreferit:
    """Tests per remove_refugi_preferit"""
    
    def test_remove_refugi_preferit_success(self, user_controller, sample_uid, sample_refugi_id, sample_refugis_info):
        """Test eliminar refugi preferit amb èxit"""
        # Arrange
        user_controller.user_dao.user_exists.return_value = True
        user_controller.user_dao.remove_refugi_from_list.return_value = (True, [])
        user_controller.user_dao.get_refugis_info.return_value = sample_refugis_info
        
        # Act
        success, refugis_info, error = user_controller.remove_refugi_preferit(sample_uid, sample_refugi_id)
        
        # Assert
        assert success is True
        assert refugis_info == sample_refugis_info
        assert error is None
        user_controller.user_dao.user_exists.assert_called_once_with(sample_uid)
        user_controller.user_dao.remove_refugi_from_list.assert_called_once_with(
            sample_uid, sample_refugi_id, 'favourite_refuges'
        )
    
    def test_remove_refugi_preferit_uid_empty(self, user_controller, sample_refugi_id):
        """Test eliminar refugi preferit amb UID buit"""
        # Act
        success, refugis_info, error = user_controller.remove_refugi_preferit("", sample_refugi_id)
        
        # Assert
        assert success is False
        assert refugis_info is None
        assert error == "UID no proporcionat"
    
    def test_remove_refugi_preferit_refugi_id_empty(self, user_controller, sample_uid):
        """Test eliminar refugi preferit amb refuge_id buit"""
        # Act
        success, refugis_info, error = user_controller.remove_refugi_preferit(sample_uid, "")
        
        # Assert
        assert success is False
        assert refugis_info is None
        assert error == "ID del refugi no proporcionat"
    
    def test_remove_refugi_preferit_user_not_exists(self, user_controller, sample_uid, sample_refugi_id):
        """Test eliminar refugi preferit quan l'usuari no existeix"""
        # Arrange
        user_controller.user_dao.user_exists.return_value = False
        
        # Act
        success, refugis_info, error = user_controller.remove_refugi_preferit(sample_uid, sample_refugi_id)
        
        # Assert
        assert success is False
        assert refugis_info is None
        assert error == f"Usuari amb UID {sample_uid} no trobat"
    
    def test_remove_refugi_preferit_dao_remove_fails(self, user_controller, sample_uid, sample_refugi_id):
        """Test eliminar refugi preferit quan falla el DAO"""
        # Arrange
        user_controller.user_dao.user_exists.return_value = True
        user_controller.user_dao.remove_refugi_from_list.return_value = (False, None)
        
        # Act
        success, refugis_info, error = user_controller.remove_refugi_preferit(sample_uid, sample_refugi_id)
        
        # Assert
        assert success is False
        assert refugis_info is None
        assert error == "Error eliminant refugi dels preferits"
    
    def test_remove_refugi_preferit_exception(self, user_controller, sample_uid, sample_refugi_id):
        """Test eliminar refugi preferit amb excepció"""
        # Arrange
        user_controller.user_dao.user_exists.side_effect = Exception("Connection timeout")
        
        # Act
        success, refugis_info, error = user_controller.remove_refugi_preferit(sample_uid, sample_refugi_id)
        
        # Assert
        assert success is False
        assert refugis_info is None
        assert "Error intern: Connection timeout" in error


@pytest.mark.controller
class TestGetRefugisPreferitsInfo:
    """Tests per get_refugis_preferits_info"""
    
    def test_get_refugis_preferits_info_success(self, user_controller, sample_uid, sample_refugis_info):
        """Test obtenir info de refugis preferits amb èxit"""
        # Arrange
        user_controller.user_dao.user_exists.return_value = True
        user_controller.user_dao.get_refugis_info.return_value = sample_refugis_info
        
        # Act
        success, refugis_info, error = user_controller.get_refugis_preferits_info(sample_uid)
        
        # Assert
        assert success is True
        assert refugis_info == sample_refugis_info
        assert error is None
        user_controller.user_dao.get_refugis_info.assert_called_once_with(sample_uid, 'favourite_refuges')
    
    def test_get_refugis_preferits_info_empty_list(self, user_controller, sample_uid):
        """Test obtenir info de refugis preferits amb llista buida"""
        # Arrange
        user_controller.user_dao.user_exists.return_value = True
        user_controller.user_dao.get_refugis_info.return_value = []
        
        # Act
        success, refugis_info, error = user_controller.get_refugis_preferits_info(sample_uid)
        
        # Assert
        assert success is True
        assert refugis_info == []
        assert error is None
    
    def test_get_refugis_preferits_info_uid_empty(self, user_controller):
        """Test obtenir info de refugis preferits amb UID buit"""
        # Act
        success, refugis_info, error = user_controller.get_refugis_preferits_info("")
        
        # Assert
        assert success is False
        assert refugis_info is None
        assert error == "UID no proporcionat"
    
    def test_get_refugis_preferits_info_user_not_exists(self, user_controller, sample_uid):
        """Test obtenir info de refugis preferits quan l'usuari no existeix"""
        # Arrange
        user_controller.user_dao.user_exists.return_value = False
        
        # Act
        success, refugis_info, error = user_controller.get_refugis_preferits_info(sample_uid)
        
        # Assert
        assert success is False
        assert refugis_info is None
        assert error == f"Usuari amb UID {sample_uid} no trobat"
    
    def test_get_refugis_preferits_info_exception(self, user_controller, sample_uid):
        """Test obtenir info de refugis preferits amb excepció"""
        # Arrange
        user_controller.user_dao.user_exists.side_effect = Exception("Firestore error")
        
        # Act
        success, refugis_info, error = user_controller.get_refugis_preferits_info(sample_uid)
        
        # Assert
        assert success is False
        assert refugis_info is None
        assert "Error intern: Firestore error" in error


# ==================== TESTS REFUGIS VISITATS ====================

@pytest.mark.controller
class TestAddRefugiVisitat:
    """Tests per add_refugi_visitat"""
    
    def test_add_refugi_visitat_success(self, user_controller, sample_uid, sample_refugi_id, sample_refugis_info):
        """Test afegir refugi visitat amb èxit"""
        # Arrange
        user_controller.user_dao.user_exists.return_value = True
        user_controller.refugi_dao.refugi_exists.return_value = True
        user_controller.user_dao.add_refugi_to_list.return_value = (True, [sample_refugi_id])
        user_controller.refugi_dao.add_visitor_to_refugi.return_value = True
        user_controller.user_dao.get_refugis_info.return_value = sample_refugis_info
        
        # Act
        success, refugis_info, error = user_controller.add_refugi_visitat(sample_uid, sample_refugi_id)
        
        # Assert
        assert success is True
        assert refugis_info == sample_refugis_info
        assert error is None
        user_controller.user_dao.add_refugi_to_list.assert_called_once_with(
            sample_uid, sample_refugi_id, 'visited_refuges'
        )
        user_controller.refugi_dao.add_visitor_to_refugi.assert_called_once_with(sample_refugi_id, sample_uid)
    
    def test_add_refugi_visitat_visitor_update_fails(self, user_controller, sample_uid, sample_refugi_id, sample_refugis_info):
        """Test afegir refugi visitat quan falla actualitzar visitants del refugi (warning, no error)"""
        # Arrange
        user_controller.user_dao.user_exists.return_value = True
        user_controller.refugi_dao.refugi_exists.return_value = True
        user_controller.user_dao.add_refugi_to_list.return_value = (True, [sample_refugi_id])
        user_controller.refugi_dao.add_visitor_to_refugi.return_value = False  # Falla però no atura el procés
        user_controller.user_dao.get_refugis_info.return_value = sample_refugis_info
        
        # Act
        success, refugis_info, error = user_controller.add_refugi_visitat(sample_uid, sample_refugi_id)
        
        # Assert - el procés continua amb èxit malgrat el warning
        assert success is True
        assert refugis_info == sample_refugis_info
        assert error is None
    
    def test_add_refugi_visitat_uid_empty(self, user_controller, sample_refugi_id):
        """Test afegir refugi visitat amb UID buit"""
        # Act
        success, refugis_info, error = user_controller.add_refugi_visitat("", sample_refugi_id)
        
        # Assert
        assert success is False
        assert refugis_info is None
        assert error == "UID no proporcionat"
    
    def test_add_refugi_visitat_refugi_id_none(self, user_controller, sample_uid):
        """Test afegir refugi visitat amb refuge_id None"""
        # Act
        success, refugis_info, error = user_controller.add_refugi_visitat(sample_uid, None)
        
        # Assert
        assert success is False
        assert refugis_info is None
        assert error == "ID del refugi no proporcionat"
    
    def test_add_refugi_visitat_user_not_exists(self, user_controller, sample_uid, sample_refugi_id):
        """Test afegir refugi visitat quan l'usuari no existeix"""
        # Arrange
        user_controller.user_dao.user_exists.return_value = False
        
        # Act
        success, refugis_info, error = user_controller.add_refugi_visitat(sample_uid, sample_refugi_id)
        
        # Assert
        assert success is False
        assert refugis_info is None
        assert error == f"Usuari amb UID {sample_uid} no trobat"
    
    def test_add_refugi_visitat_refugi_not_exists(self, user_controller, sample_uid, sample_refugi_id):
        """Test afegir refugi visitat quan el refugi no existeix"""
        # Arrange
        user_controller.user_dao.user_exists.return_value = True
        user_controller.refugi_dao.refugi_exists.return_value = False
        
        # Act
        success, refugis_info, error = user_controller.add_refugi_visitat(sample_uid, sample_refugi_id)
        
        # Assert
        assert success is False
        assert refugis_info is None
        assert error == f"Refugi amb ID {sample_refugi_id} no trobat"
    
    def test_add_refugi_visitat_dao_add_fails(self, user_controller, sample_uid, sample_refugi_id):
        """Test afegir refugi visitat quan falla el DAO"""
        # Arrange
        user_controller.user_dao.user_exists.return_value = True
        user_controller.refugi_dao.refugi_exists.return_value = True
        user_controller.user_dao.add_refugi_to_list.return_value = (False, None)
        
        # Act
        success, refugis_info, error = user_controller.add_refugi_visitat(sample_uid, sample_refugi_id)
        
        # Assert
        assert success is False
        assert refugis_info is None
        assert error == "Error afegint refugi als visitats"
    
    def test_add_refugi_visitat_exception(self, user_controller, sample_uid, sample_refugi_id):
        """Test afegir refugi visitat amb excepció"""
        # Arrange
        user_controller.user_dao.user_exists.side_effect = Exception("Network error")
        
        # Act
        success, refugis_info, error = user_controller.add_refugi_visitat(sample_uid, sample_refugi_id)
        
        # Assert
        assert success is False
        assert refugis_info is None
        assert "Error intern: Network error" in error


@pytest.mark.controller
class TestRemoveRefugiVisitat:
    """Tests per remove_refugi_visitat"""
    
    def test_remove_refugi_visitat_success(self, user_controller, sample_uid, sample_refugi_id, sample_refugis_info):
        """Test eliminar refugi visitat amb èxit"""
        # Arrange
        user_controller.user_dao.user_exists.return_value = True
        user_controller.user_dao.remove_refugi_from_list.return_value = (True, [])
        user_controller.refugi_dao.remove_visitor_from_refugi.return_value = True
        user_controller.user_dao.get_refugis_info.return_value = sample_refugis_info
        
        # Act
        success, refugis_info, error = user_controller.remove_refugi_visitat(sample_uid, sample_refugi_id)
        
        # Assert
        assert success is True
        assert refugis_info == sample_refugis_info
        assert error is None
        user_controller.user_dao.remove_refugi_from_list.assert_called_once_with(
            sample_uid, sample_refugi_id, 'visited_refuges'
        )
        user_controller.refugi_dao.remove_visitor_from_refugi.assert_called_once_with(sample_refugi_id, sample_uid)
    
    def test_remove_refugi_visitat_visitor_update_fails(self, user_controller, sample_uid, sample_refugi_id, sample_refugis_info):
        """Test eliminar refugi visitat quan falla actualitzar visitants del refugi (warning, no error)"""
        # Arrange
        user_controller.user_dao.user_exists.return_value = True
        user_controller.user_dao.remove_refugi_from_list.return_value = (True, [])
        user_controller.refugi_dao.remove_visitor_from_refugi.return_value = False  # Falla però no atura el procés
        user_controller.user_dao.get_refugis_info.return_value = sample_refugis_info
        
        # Act
        success, refugis_info, error = user_controller.remove_refugi_visitat(sample_uid, sample_refugi_id)
        
        # Assert - el procés continua amb èxit malgrat el warning
        assert success is True
        assert refugis_info == sample_refugis_info
        assert error is None
    
    def test_remove_refugi_visitat_uid_none(self, user_controller, sample_refugi_id):
        """Test eliminar refugi visitat amb UID None"""
        # Act
        success, refugis_info, error = user_controller.remove_refugi_visitat(None, sample_refugi_id)
        
        # Assert
        assert success is False
        assert refugis_info is None
        assert error == "UID no proporcionat"
    
    def test_remove_refugi_visitat_refugi_id_empty(self, user_controller, sample_uid):
        """Test eliminar refugi visitat amb refuge_id buit"""
        # Act
        success, refugis_info, error = user_controller.remove_refugi_visitat(sample_uid, "")
        
        # Assert
        assert success is False
        assert refugis_info is None
        assert error == "ID del refugi no proporcionat"
    
    def test_remove_refugi_visitat_user_not_exists(self, user_controller, sample_uid, sample_refugi_id):
        """Test eliminar refugi visitat quan l'usuari no existeix"""
        # Arrange
        user_controller.user_dao.user_exists.return_value = False
        
        # Act
        success, refugis_info, error = user_controller.remove_refugi_visitat(sample_uid, sample_refugi_id)
        
        # Assert
        assert success is False
        assert refugis_info is None
        assert error == f"Usuari amb UID {sample_uid} no trobat"
    
    def test_remove_refugi_visitat_dao_remove_fails(self, user_controller, sample_uid, sample_refugi_id):
        """Test eliminar refugi visitat quan falla el DAO"""
        # Arrange
        user_controller.user_dao.user_exists.return_value = True
        user_controller.user_dao.remove_refugi_from_list.return_value = (False, None)
        
        # Act
        success, refugis_info, error = user_controller.remove_refugi_visitat(sample_uid, sample_refugi_id)
        
        # Assert
        assert success is False
        assert refugis_info is None
        assert error == "Error eliminant refugi dels visitats"
    
    def test_remove_refugi_visitat_exception(self, user_controller, sample_uid, sample_refugi_id):
        """Test eliminar refugi visitat amb excepció"""
        # Arrange
        user_controller.user_dao.user_exists.side_effect = Exception("Timeout error")
        
        # Act
        success, refugis_info, error = user_controller.remove_refugi_visitat(sample_uid, sample_refugi_id)
        
        # Assert
        assert success is False
        assert refugis_info is None
        assert "Error intern: Timeout error" in error


@pytest.mark.controller
class TestGetRefugisVisitatsInfo:
    """Tests per get_refugis_visitats_info"""
    
    def test_get_refugis_visitats_info_success(self, user_controller, sample_uid, sample_refugis_info):
        """Test obtenir info de refugis visitats amb èxit"""
        # Arrange
        user_controller.user_dao.user_exists.return_value = True
        user_controller.user_dao.get_refugis_info.return_value = sample_refugis_info
        
        # Act
        success, refugis_info, error = user_controller.get_refugis_visitats_info(sample_uid)
        
        # Assert
        assert success is True
        assert refugis_info == sample_refugis_info
        assert error is None
        user_controller.user_dao.get_refugis_info.assert_called_once_with(sample_uid, 'visited_refuges')
    
    def test_get_refugis_visitats_info_empty_list(self, user_controller, sample_uid):
        """Test obtenir info de refugis visitats amb llista buida"""
        # Arrange
        user_controller.user_dao.user_exists.return_value = True
        user_controller.user_dao.get_refugis_info.return_value = []
        
        # Act
        success, refugis_info, error = user_controller.get_refugis_visitats_info(sample_uid)
        
        # Assert
        assert success is True
        assert refugis_info == []
        assert error is None
    
    def test_get_refugis_visitats_info_uid_none(self, user_controller):
        """Test obtenir info de refugis visitats amb UID None"""
        # Act
        success, refugis_info, error = user_controller.get_refugis_visitats_info(None)
        
        # Assert
        assert success is False
        assert refugis_info is None
        assert error == "UID no proporcionat"
    
    def test_get_refugis_visitats_info_user_not_exists(self, user_controller, sample_uid):
        """Test obtenir info de refugis visitats quan l'usuari no existeix"""
        # Arrange
        user_controller.user_dao.user_exists.return_value = False
        
        # Act
        success, refugis_info, error = user_controller.get_refugis_visitats_info(sample_uid)
        
        # Assert
        assert success is False
        assert refugis_info is None
        assert error == f"Usuari amb UID {sample_uid} no trobat"
    
    def test_get_refugis_visitats_info_exception(self, user_controller, sample_uid):
        """Test obtenir info de refugis visitats amb excepció"""
        # Arrange
        user_controller.user_dao.user_exists.side_effect = Exception("Internal error")
        
        # Act
        success, refugis_info, error = user_controller.get_refugis_visitats_info(sample_uid)
        
        # Assert
        assert success is False
        assert refugis_info is None
        assert "Error intern: Internal error" in error


# ==================== TESTS PATRÓ TEMPLATE METHOD ====================

@pytest.mark.controller
class TestTemplateMethodPattern:
    """Tests per verificar que el patró Template Method funciona correctament"""
    
    def test_template_method_calls_correct_list_type_for_preferits(self, user_controller, sample_uid, sample_refugi_id):
        """Test que el mètode plantilla usa 'favourite_refuges' per preferits"""
        # Arrange
        user_controller.user_dao.user_exists.return_value = True
        user_controller.refugi_dao.refugi_exists.return_value = True
        user_controller.user_dao.add_refugi_to_list.return_value = (True, [sample_refugi_id])
        user_controller.user_dao.get_refugis_info.return_value = []
        
        # Act
        user_controller.add_refugi_preferit(sample_uid, sample_refugi_id)
        
        # Assert - verifica que s'usa el list_type correcte
        user_controller.user_dao.add_refugi_to_list.assert_called_with(
            sample_uid, sample_refugi_id, 'favourite_refuges'
        )
    
    def test_template_method_calls_correct_list_type_for_visitats(self, user_controller, sample_uid, sample_refugi_id):
        """Test que el mètode plantilla usa 'visited_refuges' per visitats"""
        # Arrange
        user_controller.user_dao.user_exists.return_value = True
        user_controller.refugi_dao.refugi_exists.return_value = True
        user_controller.user_dao.add_refugi_to_list.return_value = (True, [sample_refugi_id])
        user_controller.refugi_dao.add_visitor_to_refugi.return_value = True
        user_controller.user_dao.get_refugis_info.return_value = []
        
        # Act
        user_controller.add_refugi_visitat(sample_uid, sample_refugi_id)
        
        # Assert - verifica que s'usa el list_type correcte
        user_controller.user_dao.add_refugi_to_list.assert_called_with(
            sample_uid, sample_refugi_id, 'visited_refuges'
        )
    
    def test_hook_method_not_called_for_preferits(self, user_controller, sample_uid, sample_refugi_id):
        """Test que el hook method NO s'executa per preferits"""
        # Arrange
        user_controller.user_dao.user_exists.return_value = True
        user_controller.refugi_dao.refugi_exists.return_value = True
        user_controller.user_dao.add_refugi_to_list.return_value = (True, [sample_refugi_id])
        user_controller.user_dao.get_refugis_info.return_value = []
        
        # Act
        user_controller.add_refugi_preferit(sample_uid, sample_refugi_id)
        
        # Assert - verifica que NO s'actualitza la llista de visitants
        user_controller.refugi_dao.add_visitor_to_refugi.assert_not_called()
        user_controller.refugi_dao.remove_visitor_from_refugi.assert_not_called()
    
    def test_hook_method_called_for_visitats_add(self, user_controller, sample_uid, sample_refugi_id):
        """Test que el hook method SÍ s'executa per visitats (add)"""
        # Arrange
        user_controller.user_dao.user_exists.return_value = True
        user_controller.refugi_dao.refugi_exists.return_value = True
        user_controller.user_dao.add_refugi_to_list.return_value = (True, [sample_refugi_id])
        user_controller.refugi_dao.add_visitor_to_refugi.return_value = True
        user_controller.user_dao.get_refugis_info.return_value = []
        
        # Act
        user_controller.add_refugi_visitat(sample_uid, sample_refugi_id)
        
        # Assert - verifica que SÍ s'actualitza la llista de visitants
        user_controller.refugi_dao.add_visitor_to_refugi.assert_called_once_with(sample_refugi_id, sample_uid)
    
    def test_hook_method_called_for_visitats_remove(self, user_controller, sample_uid, sample_refugi_id):
        """Test que el hook method SÍ s'executa per visitats (remove)"""
        # Arrange
        user_controller.user_dao.user_exists.return_value = True
        user_controller.user_dao.remove_refugi_from_list.return_value = (True, [])
        user_controller.refugi_dao.remove_visitor_from_refugi.return_value = True
        user_controller.user_dao.get_refugis_info.return_value = []
        
        # Act
        user_controller.remove_refugi_visitat(sample_uid, sample_refugi_id)
        
        # Assert - verifica que SÍ s'actualitza la llista de visitants
        user_controller.refugi_dao.remove_visitor_from_refugi.assert_called_once_with(sample_refugi_id, sample_uid)


# ==================== TESTS D'INTEGRACIÓ (SIMULATS) ====================

@pytest.mark.integration
class TestRefugisIntegration:
    """Tests d'integració simulats per validar fluxos complets"""
    
    def test_complete_flow_add_multiple_preferits(self, user_controller, sample_uid, sample_refugi_ids):
        """Test flux complet afegint múltiples refugis preferits"""
        # Arrange
        user_controller.user_dao.user_exists.return_value = True
        user_controller.refugi_dao.refugi_exists.return_value = True
        
        # Act - afegeix múltiples refugis
        for i, refuge_id in enumerate(sample_refugi_ids):
            current_list = sample_refugi_ids[:i+1]
            user_controller.user_dao.add_refugi_to_list.return_value = (True, current_list)
            user_controller.user_dao.get_refugis_info.return_value = [
                {'id': rid, 'name': f'Refugi {rid}'} for rid in current_list
            ]
            
            success, refugis_info, error = user_controller.add_refugi_preferit(sample_uid, refuge_id)
            
            assert success is True
            assert error is None
            assert len(refugis_info) == i + 1
    
    def test_complete_flow_add_and_remove_visitat(self, user_controller, sample_uid, sample_refugi_id):
        """Test flux complet afegint i eliminant un refugi visitat"""
        # Arrange
        user_controller.user_dao.user_exists.return_value = True
        user_controller.refugi_dao.refugi_exists.return_value = True
        
        # Act 1 - afegir
        user_controller.user_dao.add_refugi_to_list.return_value = (True, [sample_refugi_id])
        user_controller.refugi_dao.add_visitor_to_refugi.return_value = True
        user_controller.user_dao.get_refugis_info.return_value = [{'id': sample_refugi_id}]
        
        success_add, refugis_add, error_add = user_controller.add_refugi_visitat(sample_uid, sample_refugi_id)
        
        # Act 2 - eliminar
        user_controller.user_dao.remove_refugi_from_list.return_value = (True, [])
        user_controller.refugi_dao.remove_visitor_from_refugi.return_value = True
        user_controller.user_dao.get_refugis_info.return_value = []
        
        success_remove, refugis_remove, error_remove = user_controller.remove_refugi_visitat(sample_uid, sample_refugi_id)
        
        # Assert
        assert success_add is True
        assert len(refugis_add) == 1
        assert success_remove is True
        assert len(refugis_remove) == 0
        
        # Verifica que s'han cridat ambdós mètodes del refugi
        user_controller.refugi_dao.add_visitor_to_refugi.assert_called_once()
        user_controller.refugi_dao.remove_visitor_from_refugi.assert_called_once()
    
    def test_mix_preferits_and_visitats(self, user_controller, sample_uid):
        """Test que preferits i visitats són independents"""
        # Arrange
        refugi_preferit = "refugi_fav_001"
        refugi_visitat = "refugi_vis_001"
        
        user_controller.user_dao.user_exists.return_value = True
        user_controller.refugi_dao.refugi_exists.return_value = True
        
        # Act 1 - afegir a preferits
        user_controller.user_dao.add_refugi_to_list.return_value = (True, [refugi_preferit])
        user_controller.user_dao.get_refugis_info.return_value = [{'id': refugi_preferit}]
        success_pref, _, _ = user_controller.add_refugi_preferit(sample_uid, refugi_preferit)
        
        # Act 2 - afegir a visitats
        user_controller.user_dao.add_refugi_to_list.return_value = (True, [refugi_visitat])
        user_controller.refugi_dao.add_visitor_to_refugi.return_value = True
        user_controller.user_dao.get_refugis_info.return_value = [{'id': refugi_visitat}]
        success_vis, _, _ = user_controller.add_refugi_visitat(sample_uid, refugi_visitat)
        
        # Assert
        assert success_pref is True
        assert success_vis is True
        
        # Verifica que s'han cridat els mètodes amb els list_type correctes
        calls = user_controller.user_dao.add_refugi_to_list.call_args_list
        assert any('favourite_refuges' in str(call) for call in calls)
        assert any('visited_refuges' in str(call) for call in calls)


# ==================== TESTS D'INTEGRACIÓ AMB FIRESTORE MOCKEJAT ====================

@pytest.mark.integration
class TestRefugisIntegrationWithFirestore:
    """Tests d'integració amb Firestore i cache mockejats per validar fluxos end-to-end"""
    
    @patch('api.daos.user_dao.cache_service')
    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    @patch('api.daos.refugi_lliure_dao.firestore_service')
    def test_integration_add_refugi_preferit_full_flow(
        self, 
        mock_refugi_firestore, 
        mock_refugi_cache,
        mock_user_firestore_service,
        mock_user_cache,
        sample_uid,
        sample_refugi_id
    ):
        """Test d'integració complet per afegir refugi preferit amb Firestore real"""
        # ==== SETUP MOCKS ====
        
        # Mock cache (cache miss per forçar llegir de Firestore)
        mock_user_cache.get.return_value = None
        mock_user_cache.generate_key.return_value = 'test_cache_key'
        mock_refugi_cache.get.return_value = None
        mock_refugi_cache.generate_key.return_value = 'test_refugi_cache_key'
        
        # Mock Firestore - User DAO
        mock_user_db = MagicMock()
        mock_user_firestore_instance = mock_user_firestore_service.return_value
        mock_user_firestore_instance.get_db.return_value = mock_user_db
        
        mock_user_collection = MagicMock()
        mock_user_db.collection.return_value = mock_user_collection
        
        # Mock usuari existent
        mock_user_doc = MagicMock()
        mock_user_doc.exists = True
        mock_user_doc.to_dict.return_value = {
            'uid': sample_uid,
            'email': 'test@example.com',
            'username': 'testuser',
            'favourite_refuges': []
        }
        
        mock_user_doc_ref = MagicMock()
        mock_user_doc_ref.get.return_value = mock_user_doc
        mock_user_collection.document.return_value = mock_user_doc_ref
        
        # Mock Firestore - Refugi DAO
        mock_refugi_db = MagicMock()
        mock_refugi_firestore.get_db.return_value = mock_refugi_db
        
        mock_refugi_collection = MagicMock()
        mock_refugi_db.collection.return_value = mock_refugi_collection
        
        # Mock refugi existent
        mock_refugi_doc = MagicMock()
        mock_refugi_doc.exists = True
        mock_refugi_doc.to_dict.return_value = {
            'id': sample_refugi_id,
            'name': 'Refugi Test',
            'region': 'Pirineus',
            'places': 10,
            'coord': {'long': 1.5, 'lat': 42.5}
        }
        
        mock_refugi_doc_ref = MagicMock()
        mock_refugi_doc_ref.get.return_value = mock_refugi_doc
        mock_refugi_collection.document.return_value = mock_refugi_doc_ref
        
        # ==== EXECUTE ====
        controller = UserController()
        success, refugis_info, error = controller.add_refugi_preferit(sample_uid, sample_refugi_id)
        
        # ==== VERIFY ====
        assert success is True
        assert error is None
        assert refugis_info is not None
        assert len(refugis_info) == 1
        assert refugis_info[0]['id'] == sample_refugi_id
        
        # Verifica que s'ha actualitzat a Firestore
        mock_user_doc_ref.update.assert_called_once()
        update_call = mock_user_doc_ref.update.call_args[0][0]
        assert 'favourite_refuges' in update_call
        assert sample_refugi_id in update_call['favourite_refuges']
    
    @patch('api.daos.user_dao.cache_service')
    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    @patch('api.daos.refugi_lliure_dao.firestore_service')
    def test_integration_add_refugi_visitat_updates_both_collections(
        self,
        mock_refugi_firestore,
        mock_refugi_cache,
        mock_user_firestore_service,
        mock_user_cache,
        sample_uid,
        sample_refugi_id
    ):
        """Test que afegir refugi visitat actualitza tant user com refugi"""
        # ==== SETUP MOCKS ====
        mock_user_cache.get.return_value = None
        mock_user_cache.generate_key.return_value = 'user_key'
        mock_refugi_cache.get.return_value = None
        mock_refugi_cache.generate_key.return_value = 'refugi_key'
        
        # Mock User Firestore
        mock_user_db = MagicMock()
        mock_user_firestore_instance = mock_user_firestore_service.return_value
        mock_user_firestore_instance.get_db.return_value = mock_user_db
        mock_user_collection = MagicMock()
        mock_user_db.collection.return_value = mock_user_collection
        
        mock_user_doc = MagicMock()
        mock_user_doc.exists = True
        mock_user_doc.to_dict.return_value = {
            'uid': sample_uid,
            'email': 'test@example.com',
            'visited_refuges': []
        }
        mock_user_doc_ref = MagicMock()
        mock_user_doc_ref.get.return_value = mock_user_doc
        mock_user_collection.document.return_value = mock_user_doc_ref
        
        # Mock Refugi Firestore
        mock_refugi_db = MagicMock()
        mock_refugi_firestore.get_db.return_value = mock_refugi_db
        mock_refugi_collection = MagicMock()
        mock_refugi_db.collection.return_value = mock_refugi_collection
        
        mock_refugi_doc = MagicMock()
        mock_refugi_doc.exists = True
        mock_refugi_doc.to_dict.return_value = {
            'id': sample_refugi_id,
            'name': 'Refugi Test',
            'visitors': []
        }
        mock_refugi_doc_ref = MagicMock()
        mock_refugi_doc_ref.get.return_value = mock_refugi_doc
        mock_refugi_collection.document.return_value = mock_refugi_doc_ref
        
        # ==== EXECUTE ====
        controller = UserController()
        success, refugis_info, error = controller.add_refugi_visitat(sample_uid, sample_refugi_id)
        
        # ==== VERIFY ====
        assert success is True
        assert error is None
        
        # Verifica actualització a col·lecció users
        user_update_calls = mock_user_doc_ref.update.call_args_list
        assert len(user_update_calls) == 1
        user_update_data = user_update_calls[0][0][0]
        assert 'visited_refuges' in user_update_data
        assert sample_refugi_id in user_update_data['visited_refuges']
        
        # Verifica actualització a col·lecció refugis
        refugi_update_calls = mock_refugi_doc_ref.update.call_args_list
        assert len(refugi_update_calls) == 1
        refugi_update_data = refugi_update_calls[0][0][0]
        assert 'visitors' in refugi_update_data
        assert sample_uid in refugi_update_data['visitors']
    
    @patch('api.daos.user_dao.cache_service')
    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    @patch('api.daos.refugi_lliure_dao.firestore_service')
    def test_integration_remove_refugi_visitat_updates_both_collections(
        self,
        mock_refugi_firestore,
        mock_refugi_cache,
        mock_user_firestore_service,
        mock_user_cache,
        sample_uid,
        sample_refugi_id
    ):
        """Test que eliminar refugi visitat actualitza tant user com refugi"""
        # ==== SETUP MOCKS ====
        mock_user_cache.get.return_value = None
        mock_user_cache.generate_key.return_value = 'user_key'
        mock_refugi_cache.get.return_value = None
        mock_refugi_cache.generate_key.return_value = 'refugi_key'
        
        # Mock User Firestore (amb refugi ja a la llista)
        mock_user_db = MagicMock()
        mock_user_firestore_instance = mock_user_firestore_service.return_value
        mock_user_firestore_instance.get_db.return_value = mock_user_db
        mock_user_collection = MagicMock()
        mock_user_db.collection.return_value = mock_user_collection
        
        mock_user_doc = MagicMock()
        mock_user_doc.exists = True
        mock_user_doc.to_dict.return_value = {
            'uid': sample_uid,
            'email': 'test@example.com',
            'visited_refuges': [sample_refugi_id]  # Refugi ja està a la llista
        }
        mock_user_doc_ref = MagicMock()
        mock_user_doc_ref.get.return_value = mock_user_doc
        mock_user_collection.document.return_value = mock_user_doc_ref
        
        # Mock Refugi Firestore (amb user ja a la llista)
        mock_refugi_db = MagicMock()
        mock_refugi_firestore.get_db.return_value = mock_refugi_db
        mock_refugi_collection = MagicMock()
        mock_refugi_db.collection.return_value = mock_refugi_collection
        
        mock_refugi_doc = MagicMock()
        mock_refugi_doc.exists = True
        mock_refugi_doc.to_dict.return_value = {
            'id': sample_refugi_id,
            'name': 'Refugi Test',
            'visitors': [sample_uid]  # User ja està a la llista
        }
        mock_refugi_doc_ref = MagicMock()
        mock_refugi_doc_ref.get.return_value = mock_refugi_doc
        mock_refugi_collection.document.return_value = mock_refugi_doc_ref
        
        # ==== EXECUTE ====
        controller = UserController()
        success, refugis_info, error = controller.remove_refugi_visitat(sample_uid, sample_refugi_id)
        
        # ==== VERIFY ====
        assert success is True
        assert error is None
        assert len(refugis_info) == 0  # Llista buida després d'eliminar
        
        # Verifica actualització a col·lecció users
        user_update_calls = mock_user_doc_ref.update.call_args_list
        assert len(user_update_calls) == 1
        user_update_data = user_update_calls[0][0][0]
        assert 'visited_refuges' in user_update_data
        assert sample_refugi_id not in user_update_data['visited_refuges']
        
        # Verifica actualització a col·lecció refugis
        refugi_update_calls = mock_refugi_doc_ref.update.call_args_list
        assert len(refugi_update_calls) == 1
        refugi_update_data = refugi_update_calls[0][0][0]
        assert 'visitors' in refugi_update_data
        assert sample_uid not in refugi_update_data['visitors']
    
    @patch('api.daos.user_dao.cache_service')
    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    @patch('api.daos.refugi_lliure_dao.firestore_service')
    def test_integration_cache_invalidation_on_add(
        self,
        mock_refugi_firestore,
        mock_refugi_cache,
        mock_user_firestore_service,
        mock_user_cache,
        sample_uid,
        sample_refugi_id
    ):
        """Test que afegir refugi invalida correctament les caches"""
        # ==== SETUP MOCKS ====
        mock_user_cache.get.return_value = None
        mock_user_cache.generate_key.return_value = 'cache_key'
        mock_refugi_cache.get.return_value = None
        mock_refugi_cache.generate_key.return_value = 'refugi_cache_key'
        
        # Mock User Firestore
        mock_user_db = MagicMock()
        mock_user_firestore_instance = mock_user_firestore_service.return_value
        mock_user_firestore_instance.get_db.return_value = mock_user_db
        mock_user_collection = MagicMock()
        mock_user_db.collection.return_value = mock_user_collection
        
        mock_user_doc = MagicMock()
        mock_user_doc.exists = True
        mock_user_doc.to_dict.return_value = {
            'uid': sample_uid,
            'email': 'test@example.com',
            'favourite_refuges': []
        }
        mock_user_doc_ref = MagicMock()
        mock_user_doc_ref.get.return_value = mock_user_doc
        mock_user_collection.document.return_value = mock_user_doc_ref
        
        # Mock Refugi Firestore
        mock_refugi_db = MagicMock()
        mock_refugi_firestore.get_db.return_value = mock_refugi_db
        mock_refugi_collection = MagicMock()
        mock_refugi_db.collection.return_value = mock_refugi_collection
        
        mock_refugi_doc = MagicMock()
        mock_refugi_doc.exists = True
        mock_refugi_doc.to_dict.return_value = {
            'id': sample_refugi_id,
            'name': 'Refugi Test'
        }
        mock_refugi_doc_ref = MagicMock()
        mock_refugi_doc_ref.get.return_value = mock_refugi_doc
        mock_refugi_collection.document.return_value = mock_refugi_doc_ref
        
        # ==== EXECUTE ====
        controller = UserController()
        success, refugis_info, error = controller.add_refugi_preferit(sample_uid, sample_refugi_id)
        
        # ==== VERIFY ====
        assert success is True
        
        # Verifica que s'ha invalidat la cache de l'usuari
        assert mock_user_cache.delete.called
        delete_calls = [str(call) for call in mock_user_cache.delete.call_args_list]
        
        # Hauria d'invalidar almenys la cache de user_detail i user_refugis_info
        assert len(delete_calls) >= 2
    
    @patch('api.daos.user_dao.cache_service')
    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    @patch('api.daos.refugi_lliure_dao.firestore_service')
    def test_integration_idempotent_add_refugi_already_in_list(
        self,
        mock_refugi_firestore,
        mock_refugi_cache,
        mock_user_firestore_service,
        mock_user_cache,
        sample_uid,
        sample_refugi_id
    ):
        """Test que afegir un refugi ja existent és idempotent"""
        # ==== SETUP MOCKS ====
        mock_user_cache.get.return_value = None
        mock_user_cache.generate_key.return_value = 'cache_key'
        mock_refugi_cache.get.return_value = None
        mock_refugi_cache.generate_key.return_value = 'refugi_cache_key'
        
        # Mock User Firestore (refugi ja a la llista)
        mock_user_db = MagicMock()
        mock_user_firestore_instance = mock_user_firestore_service.return_value
        mock_user_firestore_instance.get_db.return_value = mock_user_db
        mock_user_collection = MagicMock()
        mock_user_db.collection.return_value = mock_user_collection
        
        mock_user_doc = MagicMock()
        mock_user_doc.exists = True
        mock_user_doc.to_dict.return_value = {
            'uid': sample_uid,
            'email': 'test@example.com',
            'favourite_refuges': [sample_refugi_id]  # Ja està a la llista!
        }
        mock_user_doc_ref = MagicMock()
        mock_user_doc_ref.get.return_value = mock_user_doc
        mock_user_collection.document.return_value = mock_user_doc_ref
        
        # Mock Refugi Firestore
        mock_refugi_db = MagicMock()
        mock_refugi_firestore.get_db.return_value = mock_refugi_db
        mock_refugi_collection = MagicMock()
        mock_refugi_db.collection.return_value = mock_refugi_collection
        
        mock_refugi_doc = MagicMock()
        mock_refugi_doc.exists = True
        mock_refugi_doc.to_dict.return_value = {
            'id': sample_refugi_id,
            'name': 'Refugi Test'
        }
        mock_refugi_doc_ref = MagicMock()
        mock_refugi_doc_ref.get.return_value = mock_refugi_doc
        mock_refugi_collection.document.return_value = mock_refugi_doc_ref
        
        # ==== EXECUTE ====
        controller = UserController()
        success, refugis_info, error = controller.add_refugi_preferit(sample_uid, sample_refugi_id)
        
        # ==== VERIFY ====
        assert success is True
        assert error is None
        
        # Verifica que NO s'ha cridat update (ja que el refugi ja hi era)
        mock_user_doc_ref.update.assert_not_called()
    
    @patch('api.daos.user_dao.cache_service')
    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    @patch('api.daos.refugi_lliure_dao.firestore_service')
    def test_integration_get_refugis_info_with_multiple_refugis(
        self,
        mock_refugi_firestore,
        mock_refugi_cache,
        mock_user_firestore_service,
        mock_user_cache,
        sample_uid,
        sample_refugi_ids
    ):
        """Test obtenir info de múltiples refugis"""
        # ==== SETUP MOCKS ====
        mock_user_cache.get.return_value = None
        mock_user_cache.generate_key.return_value = 'cache_key'
        mock_refugi_cache.get.return_value = None
        mock_refugi_cache.generate_key.return_value = 'refugi_cache_key'
        
        # Mock User Firestore amb múltiples refugis
        mock_user_db = MagicMock()
        mock_user_firestore_instance = mock_user_firestore_service.return_value
        mock_user_firestore_instance.get_db.return_value = mock_user_db
        mock_user_collection = MagicMock()
        mock_user_db.collection.return_value = mock_user_collection
        
        mock_user_doc = MagicMock()
        mock_user_doc.exists = True
        mock_user_doc.to_dict.return_value = {
            'uid': sample_uid,
            'favourite_refuges': sample_refugi_ids
        }
        mock_user_doc_ref = MagicMock()
        mock_user_doc_ref.get.return_value = mock_user_doc
        mock_user_collection.document.return_value = mock_user_doc_ref
        
        # Mock Refugi Firestore - retorna diferents refugis segons l'ID
        mock_refugi_db = MagicMock()
        mock_refugi_firestore.get_db.return_value = mock_refugi_db
        mock_refugi_collection = MagicMock()
        mock_refugi_db.collection.return_value = mock_refugi_collection
        
        def get_refugi_mock(refuge_id):
            """Mock que retorna diferents refugis segons l'ID"""
            mock_doc = MagicMock()
            mock_doc.exists = True
            mock_doc.to_dict.return_value = {
                'id': refuge_id,
                'name': f'Refugi {refuge_id}',
                'region': 'Pirineus',
                'places': 10,
                'coord': {'long': 1.5, 'lat': 42.5}
            }
            return mock_doc
        
        mock_refugi_doc_ref = MagicMock()
        mock_refugi_doc_ref.get.side_effect = lambda: get_refugi_mock(mock_refugi_collection.document.call_args[0][0])
        mock_refugi_collection.document.return_value = mock_refugi_doc_ref
        
        # ==== EXECUTE ====
        controller = UserController()
        success, refugis_info, error = controller.get_refugis_preferits_info(sample_uid)
        
        # ==== VERIFY ====
        assert success is True
        assert error is None
        assert len(refugis_info) == len(sample_refugi_ids)
        
        # Verifica que cada refugi té la informació correcta
        for i, refugi_info in enumerate(refugis_info):
            assert 'id' in refugi_info
            assert 'name' in refugi_info
            assert refugi_info['id'] in sample_refugi_ids


# ==================== TESTS DE LÍMITS I EDGE CASES ====================

@pytest.mark.edge_cases
class TestEdgeCases:
    """Tests de casos límit i situacions extremes"""
    
    def test_add_same_refugi_twice_to_preferits(self, user_controller, sample_uid, sample_refugi_id):
        """Test afegir el mateix refugi dues vegades a preferits"""
        # Arrange - simula que el refugi ja està a la llista
        user_controller.user_dao.user_exists.return_value = True
        user_controller.refugi_dao.refugi_exists.return_value = True
        user_controller.user_dao.add_refugi_to_list.return_value = (True, [sample_refugi_id])
        user_controller.user_dao.get_refugis_info.return_value = [{'id': sample_refugi_id}]
        
        # Act - afegeix dues vegades
        success1, refugis1, error1 = user_controller.add_refugi_preferit(sample_uid, sample_refugi_id)
        success2, refugis2, error2 = user_controller.add_refugi_preferit(sample_uid, sample_refugi_id)
        
        # Assert - ambdues operacions tenen èxit (idempotent)
        assert success1 is True
        assert success2 is True
        assert len(refugis1) == 1
        assert len(refugis2) == 1
    
    def test_remove_non_existent_refugi_from_list(self, user_controller, sample_uid, sample_refugi_id):
        """Test eliminar un refugi que no està a la llista"""
        # Arrange - simula que el refugi no està a la llista
        user_controller.user_dao.user_exists.return_value = True
        user_controller.user_dao.remove_refugi_from_list.return_value = (True, [])
        user_controller.user_dao.get_refugis_info.return_value = []
        
        # Act
        success, refugis_info, error = user_controller.remove_refugi_preferit(sample_uid, sample_refugi_id)
        
        # Assert - no és error, retorna èxit
        assert success is True
        assert refugis_info == []
        assert error is None
    
    @pytest.mark.parametrize("uid_value", ["", None])
    def test_various_empty_uid_formats(self, user_controller, uid_value, sample_refugi_id):
        """Test diferents formats d'UID buit/invalid"""
        # Act
        success, refugis_info, error = user_controller.add_refugi_preferit(uid_value, sample_refugi_id)
        
        # Assert
        assert success is False
        assert refugis_info is None
        assert "UID no proporcionat" in error
    
    @pytest.mark.parametrize("refugi_value", ["", None])
    def test_various_empty_refugi_id_formats(self, user_controller, sample_uid, refugi_value):
        """Test diferents formats de refuge_id buit/invalid"""
        # Act
        success, refugis_info, error = user_controller.add_refugi_visitat(sample_uid, refugi_value)
        
        # Assert
        assert success is False
        assert refugis_info is None
        assert "ID del refugi no proporcionat" in error
    
    def test_get_info_with_large_list(self, user_controller, sample_uid):
        """Test obtenir info amb una llista molt gran de refugis"""
        # Arrange
        large_list = [{'id': f'refugi_{i:04d}', 'name': f'Refugi {i}'} for i in range(100)]
        user_controller.user_dao.user_exists.return_value = True
        user_controller.user_dao.get_refugis_info.return_value = large_list
        
        # Act
        success, refugis_info, error = user_controller.get_refugis_preferits_info(sample_uid)
        
        # Assert
        assert success is True
        assert len(refugis_info) == 100
        assert error is None
    
    def test_concurrent_operations_same_refugi(self, user_controller, sample_uid, sample_refugi_id):
        """Test operacions concurrents sobre el mateix refugi"""
        # Arrange
        user_controller.user_dao.user_exists.return_value = True
        user_controller.refugi_dao.refugi_exists.return_value = True
        user_controller.user_dao.add_refugi_to_list.return_value = (True, [sample_refugi_id])
        user_controller.refugi_dao.add_visitor_to_refugi.return_value = True
        user_controller.user_dao.get_refugis_info.return_value = [{'id': sample_refugi_id}]
        
        # Act - afegeix a preferits i visitats al mateix temps
        success_pref, _, _ = user_controller.add_refugi_preferit(sample_uid, sample_refugi_id)
        success_vis, _, _ = user_controller.add_refugi_visitat(sample_uid, sample_refugi_id)
        
        # Assert - ambdues operacions tenen èxit
        assert success_pref is True
        assert success_vis is True
        
        # Verifica que s'ha cridat als dos list_types diferents
        assert user_controller.user_dao.add_refugi_to_list.call_count == 2


# ==================== TESTS VIEWS/ENDPOINTS ====================
"""
Tests exhaustius per a les views/endpoints de refugis preferits i visitats
Cobreix: Totes les branques d'execució, try-except, errors, validacions
"""

# ==================== FIXTURES ====================

@pytest.fixture
def api_factory():
    """Factory per crear requests"""
    return APIRequestFactory()


@pytest.fixture
def mock_authenticated_request(api_factory):
    """Crea un request autenticat mock"""
    def _create_request(method='get', path='/', data=None, uid='test_uid_123'):
        if method == 'get':
            request = api_factory.get(path)
        elif method == 'post':
            request = api_factory.post(path, data or {}, format='json')
        elif method == 'delete':
            request = api_factory.delete(path)
        else:
            raise ValueError(f"Method {method} not supported")
        
        # Mock d'autenticació
        request.user = Mock()
        request.user.is_authenticated = True
        request.user_uid = uid
        
        return request
    return _create_request


@pytest.fixture
def sample_refugi_info():
    """Informació de refugi de mostra"""
    return {
        'id': 'refugi_001',
        'name': 'Refugi Test',
        'region': 'Pirineus',
        'places': 10,
        'coordinates': {'long': 1.5, 'lat': 42.5}
    }


@pytest.fixture
def sample_refugis_info_list(sample_refugi_info):
    """Llista d'informació de refugis"""
    return [
        sample_refugi_info,
        {
            'id': 'refugi_002',
            'name': 'Refugi Test 2',
            'region': 'Pirineus',
            'places': 15,
            'coordinates': {'long': 1.6, 'lat': 42.6}
        }
    ]


# ==================== TESTS REFUGIS PREFERITS - COLLECTION ENDPOINT ====================

@pytest.mark.views
class TestUserFavouriteRefugesAPIViewGet:
    """Tests per GET /users/{uid}/favorite-refuges/"""
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_get_refugis_preferits_success(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request, sample_refugis_info_list):
        """Test obtenir refugis preferits amb èxit"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.get_refugis_preferits_info.return_value = (True, sample_refugis_info_list, None)
        
        request = mock_authenticated_request('get', '/api/users/test_uid_123/favorite-refuges/')
        view = UserFavouriteRefugesAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123')
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 2
        assert len(response.data['results']) == 2
        assert response.data['results'][0]['id'] == 'refugi_001'
        mock_controller.get_refugis_preferits_info.assert_called_once_with('test_uid_123')
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_get_refugis_preferits_empty_list(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request):
        """Test obtenir refugis preferits amb llista buida"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.get_refugis_preferits_info.return_value = (True, [], None)
        
        request = mock_authenticated_request('get', '/api/users/test_uid_123/favorite-refuges/')
        view = UserFavouriteRefugesAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123')
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 0
        assert response.data['results'] == []
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_get_refugis_preferits_user_not_found(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request):
        """Test obtenir refugis preferits quan l'usuari no existeix"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.get_refugis_preferits_info.return_value = (False, None, "Usuari amb UID test_uid_123 no trobat")
        
        request = mock_authenticated_request('get', '/api/users/test_uid_123/favorite-refuges/')
        view = UserFavouriteRefugesAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123')
        
        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert 'error' in response.data
        assert 'no trobat' in response.data['error']
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_get_refugis_preferits_generic_error(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request):
        """Test obtenir refugis preferits amb error genèric"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.get_refugis_preferits_info.return_value = (False, None, "Error genèric")
        
        request = mock_authenticated_request('get', '/api/users/test_uid_123/favorite-refuges/')
        view = UserFavouriteRefugesAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123')
        
        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_get_refugis_preferits_exception(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request):
        """Test obtenir refugis preferits amb excepció"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.get_refugis_preferits_info.side_effect = Exception("Database error")
        
        request = mock_authenticated_request('get', '/api/users/test_uid_123/favorite-refuges/')
        view = UserFavouriteRefugesAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123')
        
        # Assert
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert 'error' in response.data


@pytest.mark.views
class TestUserFavouriteRefugesAPIViewPost:
    """Tests per POST /users/{uid}/favorite-refuges/"""
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_post_refugi_preferit_success(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request, sample_refugis_info_list):
        """Test afegir refugi preferit amb èxit"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.add_refugi_preferit.return_value = (True, sample_refugis_info_list, None)
        
        data = {'refuge_id': 'refugi_001'}
        request = mock_authenticated_request('post', '/api/users/test_uid_123/favorite-refuges/', data)
        view = UserFavouriteRefugesAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123')
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 2
        assert len(response.data['results']) == 2
        mock_controller.add_refugi_preferit.assert_called_once_with('test_uid_123', 'refugi_001')
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_post_refugi_preferit_invalid_data_missing_refugi_id(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request):
        """Test afegir refugi preferit sense refuge_id"""
        # Arrange
        data = {}  # Falta refuge_id
        request = mock_authenticated_request('post', '/api/users/test_uid_123/favorite-refuges/', data)
        view = UserFavouriteRefugesAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123')
        
        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data
        assert 'details' in response.data
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_post_refugi_preferit_invalid_data_empty_refugi_id(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request):
        """Test afegir refugi preferit amb refuge_id buit"""
        # Arrange
        data = {'refuge_id': ''}
        request = mock_authenticated_request('post', '/api/users/test_uid_123/favorite-refuges/', data)
        view = UserFavouriteRefugesAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123')
        
        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_post_refugi_preferit_user_not_found(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request):
        """Test afegir refugi preferit quan l'usuari no existeix"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.add_refugi_preferit.return_value = (False, None, "Usuari amb UID test_uid_123 no trobat")
        
        data = {'refuge_id': 'refugi_001'}
        request = mock_authenticated_request('post', '/api/users/test_uid_123/favorite-refuges/', data)
        view = UserFavouriteRefugesAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123')
        
        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert 'error' in response.data
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_post_refugi_preferit_refugi_not_found(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request):
        """Test afegir refugi preferit quan el refugi no existeix"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.add_refugi_preferit.return_value = (False, None, "Refugi amb ID refugi_001 no trobat")
        
        data = {'refuge_id': 'refugi_001'}
        request = mock_authenticated_request('post', '/api/users/test_uid_123/favorite-refuges/', data)
        view = UserFavouriteRefugesAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123')
        
        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert 'error' in response.data
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_post_refugi_preferit_exception(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request):
        """Test afegir refugi preferit amb excepció"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.add_refugi_preferit.side_effect = Exception("Network error")
        
        data = {'refuge_id': 'refugi_001'}
        request = mock_authenticated_request('post', '/api/users/test_uid_123/favorite-refuges/', data)
        view = UserFavouriteRefugesAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123')
        
        # Assert
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert 'error' in response.data


# ==================== TESTS REFUGIS PREFERITS - DETAIL ENDPOINT ====================

@pytest.mark.views
class TestUserFavouriteRefugesDetailAPIViewDelete:
    """Tests per DELETE /users/{uid}/favorite-refuges/{refuge_id}/"""
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_delete_refugi_preferit_success(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request, sample_refugis_info_list):
        """Test eliminar refugi preferit amb èxit"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.remove_refugi_preferit.return_value = (True, sample_refugis_info_list, None)
        
        request = mock_authenticated_request('delete', '/api/users/test_uid_123/favorite-refuges/refugi_001/')
        view = UserFavouriteRefugesDetailAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123', refuge_id='refugi_001')
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 2
        assert len(response.data['results']) == 2
        mock_controller.remove_refugi_preferit.assert_called_once_with('test_uid_123', 'refugi_001')
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_delete_refugi_preferit_empty_result(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request):
        """Test eliminar refugi preferit resultant en llista buida"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.remove_refugi_preferit.return_value = (True, [], None)
        
        request = mock_authenticated_request('delete', '/api/users/test_uid_123/favorite-refuges/refugi_001/')
        view = UserFavouriteRefugesDetailAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123', refuge_id='refugi_001')
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 0
        assert response.data['results'] == []
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_delete_refugi_preferit_user_not_found(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request):
        """Test eliminar refugi preferit quan l'usuari no existeix"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.remove_refugi_preferit.return_value = (False, None, "Usuari amb UID test_uid_123 no trobat")
        
        request = mock_authenticated_request('delete', '/api/users/test_uid_123/favorite-refuges/refugi_001/')
        view = UserFavouriteRefugesDetailAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123', refuge_id='refugi_001')
        
        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert 'error' in response.data
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_post_refugi_preferit_generic_error(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request):
        """Test eliminar refugi preferit amb error genèric"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.remove_refugi_preferit.return_value = (False, None, "Error eliminant refugi")
        
        request = mock_authenticated_request('delete', '/api/users/test_uid_123/favorite-refuges/refugi_001/')
        view = UserFavouriteRefugesDetailAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123', refuge_id='refugi_001')
        
        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_delete_refugi_preferit_exception(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request):
        """Test eliminar refugi preferit amb excepció"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.remove_refugi_preferit.side_effect = Exception("Connection timeout")
        
        request = mock_authenticated_request('delete', '/api/users/test_uid_123/favorite-refuges/refugi_001/')
        view = UserFavouriteRefugesDetailAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123', refuge_id='refugi_001')
        
        # Assert
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert 'error' in response.data


# ==================== TESTS REFUGIS VISITATS - COLLECTION ENDPOINT ====================

@pytest.mark.views
class TestUserVisitedRefugesAPIViewGet:
    """Tests per GET /users/{uid}/visited-refuges/"""
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_get_refugis_visitats_success(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request, sample_refugis_info_list):
        """Test obtenir refugis visitats amb èxit"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.get_refugis_visitats_info.return_value = (True, sample_refugis_info_list, None)
        
        request = mock_authenticated_request('get', '/api/users/test_uid_123/visited-refuges/')
        view = UserVisitedRefugesAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123')
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 2
        assert len(response.data['results']) == 2
        assert response.data['results'][0]['id'] == 'refugi_001'
        mock_controller.get_refugis_visitats_info.assert_called_once_with('test_uid_123')
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_get_refugis_visitats_empty_list(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request):
        """Test obtenir refugis visitats amb llista buida"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.get_refugis_visitats_info.return_value = (True, [], None)
        
        request = mock_authenticated_request('get', '/api/users/test_uid_123/visited-refuges/')
        view = UserVisitedRefugesAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123')
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 0
        assert response.data['results'] == []
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_get_refugis_visitats_user_not_found(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request):
        """Test obtenir refugis visitats quan l'usuari no existeix"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.get_refugis_visitats_info.return_value = (False, None, "Usuari amb UID test_uid_123 no trobat")
        
        request = mock_authenticated_request('get', '/api/users/test_uid_123/visited-refuges/')
        view = UserVisitedRefugesAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123')
        
        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert 'error' in response.data
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_get_refugis_visitats_generic_error(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request):
        """Test obtenir refugis visitats amb error genèric"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.get_refugis_visitats_info.return_value = (False, None, "Error genèric")
        
        request = mock_authenticated_request('get', '/api/users/test_uid_123/visited-refuges/')
        view = UserVisitedRefugesAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123')
        
        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_get_refugis_visitats_exception(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request):
        """Test obtenir refugis visitats amb excepció"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.get_refugis_visitats_info.side_effect = Exception("Database error")
        
        request = mock_authenticated_request('get', '/api/users/test_uid_123/visited-refuges/')
        view = UserVisitedRefugesAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123')
        
        # Assert
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert 'error' in response.data


@pytest.mark.views
class TestUserVisitedRefugesAPIViewPost:
    """Tests per POST /users/{uid}/visited-refuges/"""
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_post_refugi_visitat_success(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request, sample_refugis_info_list):
        """Test afegir refugi visitat amb èxit"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.add_refugi_visitat.return_value = (True, sample_refugis_info_list, None)
        
        data = {'refuge_id': 'refugi_001'}
        request = mock_authenticated_request('post', '/api/users/test_uid_123/visited-refuges/', data)
        view = UserVisitedRefugesAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123')
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 2
        assert len(response.data['results']) == 2
        mock_controller.add_refugi_visitat.assert_called_once_with('test_uid_123', 'refugi_001')
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_post_refugi_visitat_invalid_data_missing_refugi_id(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request):
        """Test afegir refugi visitat sense refuge_id"""
        # Arrange
        data = {}  # Falta refuge_id
        request = mock_authenticated_request('post', '/api/users/test_uid_123/visited-refuges/', data)
        view = UserVisitedRefugesAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123')
        
        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data
        assert 'details' in response.data
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_post_refugi_visitat_invalid_data_empty_refugi_id(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request):
        """Test afegir refugi visitat amb refuge_id buit"""
        # Arrange
        data = {'refuge_id': ''}
        request = mock_authenticated_request('post', '/api/users/test_uid_123/visited-refuges/', data)
        view = UserVisitedRefugesAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123')
        
        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_post_refugi_visitat_user_not_found(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request):
        """Test afegir refugi visitat quan l'usuari no existeix"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.add_refugi_visitat.return_value = (False, None, "Usuari amb UID test_uid_123 no trobat")
        
        data = {'refuge_id': 'refugi_001'}
        request = mock_authenticated_request('post', '/api/users/test_uid_123/visited-refuges/', data)
        view = UserVisitedRefugesAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123')
        
        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert 'error' in response.data
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_post_refugi_visitat_refugi_not_found(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request):
        """Test afegir refugi visitat quan el refugi no existeix"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.add_refugi_visitat.return_value = (False, None, "Refugi amb ID refugi_001 no trobat")
        
        data = {'refuge_id': 'refugi_001'}
        request = mock_authenticated_request('post', '/api/users/test_uid_123/visited-refuges/', data)
        view = UserVisitedRefugesAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123')
        
        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert 'error' in response.data
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_post_refugi_visitat_exception(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request):
        """Test afegir refugi visitat amb excepció"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.add_refugi_visitat.side_effect = Exception("Network error")
        
        data = {'refuge_id': 'refugi_001'}
        request = mock_authenticated_request('post', '/api/users/test_uid_123/visited-refuges/', data)
        view = UserVisitedRefugesAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123')
        
        # Assert
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert 'error' in response.data


# ==================== TESTS REFUGIS VISITATS - DETAIL ENDPOINT ====================

@pytest.mark.views
class TestUserVisitedRefugesDetailAPIViewDelete:
    """Tests per DELETE /users/{uid}/visited-refuges/{refuge_id}/"""
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_delete_refugi_visitat_success(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request, sample_refugis_info_list):
        """Test eliminar refugi visitat amb èxit"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.remove_refugi_visitat.return_value = (True, sample_refugis_info_list, None)
        
        request = mock_authenticated_request('delete', '/api/users/test_uid_123/visited-refuges/refugi_001/')
        view = UserVisitedRefugesDetailAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123', refuge_id='refugi_001')
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 2
        assert len(response.data['results']) == 2
        mock_controller.remove_refugi_visitat.assert_called_once_with('test_uid_123', 'refugi_001')
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_delete_refugi_visitat_empty_result(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request):
        """Test eliminar refugi visitat resultant en llista buida"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.remove_refugi_visitat.return_value = (True, [], None)
        
        request = mock_authenticated_request('delete', '/api/users/test_uid_123/visited-refuges/refugi_001/')
        view = UserVisitedRefugesDetailAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123', refuge_id='refugi_001')
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 0
        assert response.data['results'] == []
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_delete_refugi_visitat_user_not_found(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request):
        """Test eliminar refugi visitat quan l'usuari no existeix"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.remove_refugi_visitat.return_value = (False, None, "Usuari amb UID test_uid_123 no trobat")
        
        request = mock_authenticated_request('delete', '/api/users/test_uid_123/visited-refuges/refugi_001/')
        view = UserVisitedRefugesDetailAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123', refuge_id='refugi_001')
        
        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert 'error' in response.data
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_delete_refugi_visitat_generic_error(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request):
        """Test eliminar refugi visitat amb error genèric"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.remove_refugi_visitat.return_value = (False, None, "Error eliminant refugi")
        
        request = mock_authenticated_request('delete', '/api/users/test_uid_123/visited-refuges/refugi_001/')
        view = UserVisitedRefugesDetailAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123', refuge_id='refugi_001')
        
        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_delete_refugi_visitat_exception(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request):
        """Test eliminar refugi visitat amb excepció"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.remove_refugi_visitat.side_effect = Exception("Connection timeout")
        
        request = mock_authenticated_request('delete', '/api/users/test_uid_123/visited-refuges/refugi_001/')
        view = UserVisitedRefugesDetailAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123', refuge_id='refugi_001')
        
        # Assert
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert 'error' in response.data

