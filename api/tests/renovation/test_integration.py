"""
Tests d'integració simplificats per a renovations.
Aquests tests proven el flux complet de Controller -> DAO -> Model.
"""

import pytest
from unittest.mock import patch
from datetime import date, timedelta, datetime
from zoneinfo import ZoneInfo
from api.controllers.renovation_controller import RenovationController
from api.models.renovation import Renovation


@pytest.mark.integration
class TestRenovationIntegration:
    """Tests d'integració per renovations"""

    @patch('api.controllers.renovation_controller.UserDAO')
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_create_renovation_complete_flow(self, mock_renovation_dao_class, mock_user_dao_class):
        """Test flux complet: Controller -> DAO per crear renovation"""
        # Preparar dades
        today = date.today()
        renovation_data = {
            'refuge_id': 'refugi_001',
            'ini_date': (today + timedelta(days=1)).strftime('%Y-%m-%d'),
            'fin_date': (today + timedelta(days=5)).strftime('%Y-%m-%d'),
            'description': 'Reparar teulada i portes',
            'materials_needed': 'Fusta, claus, pintura',
            'group_link': 'https://wa.me/group/test'
        }
        
        created_renovation_data = {
            'id': 'renovation_001',
            'creator_uid': 'user_001',
            'refuge_id': 'refugi_001',
            'ini_date': (today + timedelta(days=1)).isoformat(),
            'fin_date': (today + timedelta(days=5)).isoformat(),
            'description': 'Reparar teulada i portes',
            'materials_needed': 'Fusta, claus, pintura',
            'group_link': 'https://wa.me/group/test',
            'participants_uids': [],
            'expelled_uids': []
        }
        
        # Configurar mocks
        mock_renovation_dao = mock_renovation_dao_class.return_value
        mock_renovation_dao.check_overlapping_renovations.return_value = None
        mock_renovation_dao.create_renovation.return_value = Renovation.from_dict(created_renovation_data)
        
        mock_user_dao = mock_user_dao_class.return_value
        mock_user_dao.increment_renovated_refuges.return_value = True
        
        # Executar a través del controller
        controller = RenovationController()
        success, renovation, error = controller.create_renovation(renovation_data, 'user_001')
        
        # Verificar resposta
        assert success is True
        assert error is None
        assert renovation is not None
        assert renovation.id == 'renovation_001'
        assert renovation.creator_uid == 'user_001'
        assert renovation.refuge_id == 'refugi_001'
        
        # Verificar crides al DAO
        mock_renovation_dao.check_overlapping_renovations.assert_called_once()
        mock_renovation_dao.create_renovation.assert_called_once()
        mock_user_dao.increment_renovated_refuges.assert_called_once_with('user_001')

    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_get_renovation_detail_complete_flow(self, mock_dao_class):
        """Test flux complet: Controller -> DAO per obtenir renovation"""
        # Preparar dades
        today = datetime.now(ZoneInfo('UTC'))
        renovation_data = {
            'id': 'renovation_001',
            'creator_uid': 'user_001',
            'refuge_id': 'refugi_001',
            'ini_date': today.isoformat(),
            'fin_date': (today + timedelta(days=7)).isoformat(),
            'description': 'Reparar refugi',
            'materials_needed': 'Fusta i pintura',
            'group_link': 'https://wa.me/test',
            'participants_uids': ['user_001', 'user_002'],
            'expelled_uids': []
        }
        
        # Configurar mock DAO
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.return_value = Renovation.from_dict(renovation_data)
        
        # Executar a través del controller
        controller = RenovationController()
        success, renovation, error = controller.get_renovation_by_id('renovation_001')
        
        # Verificar resposta
        assert success is True
        assert error is None
        assert renovation is not None
        assert renovation.id == 'renovation_001'
        assert renovation.creator_uid == 'user_001'
        assert len(renovation.participants_uids) == 2
        
        # Verificar crida al DAO
        mock_dao.get_renovation_by_id.assert_called_once_with('renovation_001')

    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_update_renovation_complete_flow(self, mock_dao_class):
        """Test flux complet: Controller -> DAO per actualitzar renovation"""
        # Dades originals
        today = datetime.now(ZoneInfo('UTC'))
        original_data = {
            'id': 'renovation_001',
            'creator_uid': 'user_001',
            'refuge_id': 'refugi_001',
            'ini_date': today.isoformat(),
            'fin_date': (today + timedelta(days=7)).isoformat(),
            'description': 'Descripció antiga',
            'materials_needed': 'Materials antics',
            'group_link': 'https://wa.me/old',
            'participants_uids': ['user_001'],
            'expelled_uids': []
        }
        
        # Dades actualitzades
        update_data = {
            'description': 'Descripció actualitzada',
            'materials_needed': 'Materials nous'
        }
        
        updated_data = {
            **original_data,
            'description': 'Descripció actualitzada',
            'materials_needed': 'Materials nous'
        }
        
        # Configurar mock DAO
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.return_value = Renovation.from_dict(original_data)
        mock_dao.update_renovation.return_value = True
        # Després d'actualitzar, get_renovation_by_id retorna les dades actualitzades
        mock_dao.get_renovation_by_id.side_effect = [
            Renovation.from_dict(original_data),
            Renovation.from_dict(updated_data)
        ]
        
        # Executar a través del controller
        controller = RenovationController()
        success, renovation, error = controller.update_renovation('renovation_001', update_data, 'user_001')
        
        # Verificar resposta
        assert success is True
        assert error is None
        assert renovation.description == 'Descripció actualitzada'
        assert renovation.materials_needed == 'Materials nous'
        
        # Verificar crides al DAO
        assert mock_dao.get_renovation_by_id.call_count == 2
        mock_dao.update_renovation.assert_called_once()

    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_delete_renovation_complete_flow(self, mock_dao_class):
        """Test flux complet: Controller -> DAO per eliminar renovation"""
        # Preparar dades
        today = datetime.now(ZoneInfo('UTC'))
        renovation_data = {
            'id': 'renovation_001',
            'creator_uid': 'user_001',
            'refuge_id': 'refugi_001',
            'ini_date': today.isoformat(),
            'fin_date': (today + timedelta(days=7)).isoformat(),
            'description': 'Reparar refugi',
            'materials_needed': 'Fusta',
            'group_link': 'https://wa.me/test',
            'participants_uids': ['user_001'],
            'expelled_uids': []
        }
        
        # Configurar mock DAO
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.return_value = Renovation.from_dict(renovation_data)
        mock_dao.delete_renovation.return_value = (True, 'user_001', ['user_001'])
        
        # Executar a través del controller
        controller = RenovationController()
        success, error = controller.delete_renovation('renovation_001', 'user_001')
        
        # Verificar resposta
        assert success is True
        assert error is None
        
        # Verificar crides al DAO
        mock_dao.get_renovation_by_id.assert_called_once_with('renovation_001')
        mock_dao.delete_renovation.assert_called_once_with('renovation_001')

    @patch('api.controllers.renovation_controller.UserDAO')
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_add_participant_complete_flow(self, mock_renovation_dao_class, mock_user_dao_class):
        """Test flux complet: Controller -> DAO per afegir participant"""
        # Preparar dades
        today = datetime.now(ZoneInfo('UTC'))
        renovation_data = {
            'id': 'renovation_001',
            'creator_uid': 'user_001',
            'refuge_id': 'refugi_001',
            'ini_date': today.isoformat(),
            'fin_date': (today + timedelta(days=7)).isoformat(),
            'description': 'Reparar refugi',
            'materials_needed': 'Fusta',
            'group_link': 'https://wa.me/test',
            'participants_uids': ['user_001'],
            'expelled_uids': []
        }
        
        updated_renovation_data = {
            **renovation_data,
            'participants_uids': ['user_001', 'user_002']
        }
        
        # Configurar mocks
        mock_renovation_dao = mock_renovation_dao_class.return_value
        mock_renovation_dao.get_renovation_by_id.return_value = Renovation.from_dict(renovation_data)
        mock_renovation_dao.add_participant.return_value = (True, None)
        mock_renovation_dao.get_renovation_by_id.side_effect = [
            Renovation.from_dict(renovation_data),
            Renovation.from_dict(updated_renovation_data)
        ]
        
        mock_user_dao = mock_user_dao_class.return_value
        mock_user_dao.increment_renovated_refuges.return_value = True
        
        # Executar a través del controller
        controller = RenovationController()
        success, renovation, error = controller.add_participant('renovation_001', 'user_002')
        
        # Verificar resposta
        assert success is True
        assert error is None
        assert 'user_002' in renovation.participants_uids
        
        # Verificar crides als DAOs
        mock_renovation_dao.add_participant.assert_called_once()
        mock_user_dao.increment_renovated_refuges.assert_called_once_with('user_002')

    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_get_renovation_not_found(self, mock_dao_class):
        """Test flux complet quan una renovation no existeix"""
        # Configurar mock per retornar None
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.return_value = None
        
        # Executar a través del controller
        controller = RenovationController()
        success, renovation, error = controller.get_renovation_by_id('renovation_999')
        
        # Verificar resposta d'error
        assert success is False
        assert renovation is None
        assert error is not None

    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_create_renovation_with_overlap(self, mock_dao_class):
        """Test flux complet quan es crea una renovation que es solapa"""
        # Preparar dades
        today = date.today()
        renovation_data = {
            'refuge_id': 'refugi_001',
            'ini_date': (today + timedelta(days=1)).strftime('%Y-%m-%d'),
            'fin_date': (today + timedelta(days=5)).strftime('%Y-%m-%d'),
            'description': 'Reparar teulada',
            'materials_needed': 'Fusta',
            'group_link': 'https://wa.me/test'
        }
        
        existing_renovation = Renovation.from_dict({
            'id': 'renovation_existing',
            'creator_uid': 'user_002',
            'refuge_id': 'refugi_001',
            'ini_date': today.isoformat(),
            'fin_date': (today + timedelta(days=3)).isoformat(),
            'description': 'Altra renovació',
            'materials_needed': 'Materials',
            'group_link': 'https://wa.me/other',
            'participants_uids': ['user_002'],
            'expelled_uids': []
        })
        
        # Configurar mock - hi ha solapament
        mock_dao = mock_dao_class.return_value
        mock_dao.check_overlapping_renovations.return_value = existing_renovation
        
        # Executar a través del controller
        controller = RenovationController()
        success, renovation, error = controller.create_renovation(renovation_data, 'user_001')
        
        # Verificar resposta d'error
        assert success is False
        assert error is not None
        assert 'solapa' in error.lower() or 'overlap' in error.lower()
