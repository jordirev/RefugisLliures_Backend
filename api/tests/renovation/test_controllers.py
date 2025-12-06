"""
Tests per renovations
"""
import pytest
from unittest.mock import patch
from datetime import datetime, date, timedelta
from api.models.renovation import Renovation
from api.controllers.renovation_controller import RenovationController

# ===== FIXTURES =====
@pytest.fixture
def sample_renovation_data():
    """Dades de prova per a una renovation"""
    today = date.today()
    return {
        'id': 'test_renovation_id',
        'creator_uid': 'test_creator_uid',
        'refuge_id': 'test_refuge_id',
        'ini_date': (today + timedelta(days=1)).isoformat(),
        'fin_date': (today + timedelta(days=5)).isoformat(),
        'description': 'Test renovation description',
        'materials_needed': 'Wood, nails, paint',
        'group_link': 'https://wa.me/group/test',
        'participants_uids': ['participant1', 'participant2']
    }
@pytest.fixture
def sample_renovation(sample_renovation_data):
    """Instància de model Renovation de prova"""
    return Renovation(
        id=sample_renovation_data['id'],
        creator_uid=sample_renovation_data['creator_uid'],
        refuge_id=sample_renovation_data['refuge_id'],
        ini_date=datetime.fromisoformat(sample_renovation_data['ini_date']),
        fin_date=datetime.fromisoformat(sample_renovation_data['fin_date']),
        description=sample_renovation_data['description'],
        materials_needed=sample_renovation_data['materials_needed'],
        group_link=sample_renovation_data['group_link'],
        participants_uids=sample_renovation_data['participants_uids']
    )
@pytest.fixture
def minimal_renovation_data():
    """Dades mínimes per crear una renovation"""
    today = date.today()
    return {
        'refuge_id': 'test_refuge_id',
        'ini_date': (today + timedelta(days=1)).strftime('%Y-%m-%d'),
        'fin_date': (today + timedelta(days=5)).strftime('%Y-%m-%d'),
        'description': 'Test renovation',
        'group_link': 'https://t.me/test'
    }
# ===== TEST MODEL =====


# ===== TEST CONTROLLER =====

@pytest.mark.django_db
class TestRenovationController:
    """Tests per al controller de renovation"""
    
    @patch('api.controllers.renovation_controller.UserDAO')
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_create_renovation_success(self, mock_dao_class, mock_user_dao_class, sample_renovation_data, sample_renovation):
        """Test creació exitosa de renovation"""
        mock_dao = mock_dao_class.return_value
        mock_dao.check_overlapping_renovations.return_value = None
        mock_dao.create_renovation.return_value = sample_renovation
        
        mock_user_dao = mock_user_dao_class.return_value
        
        controller = RenovationController()
        renovation_data = sample_renovation_data.copy()
        renovation_data.pop('id')
        renovation_data.pop('creator_uid')
        renovation_data.pop('participants_uids')
        
        success, renovation, error = controller.create_renovation(renovation_data, 'test_creator')
        
        assert success is True
        assert renovation is not None
        assert error is None
        mock_user_dao.increment_renovated_refuges.assert_called_once_with('test_creator')
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_create_renovation_overlap(self, mock_dao_class, sample_renovation_data, sample_renovation):
        """Test creació amb solapament"""
        mock_dao = mock_dao_class.return_value
        mock_dao.check_overlapping_renovations.return_value = sample_renovation
        
        controller = RenovationController()
        renovation_data = sample_renovation_data.copy()
        renovation_data.pop('id')
        renovation_data.pop('creator_uid')
        renovation_data.pop('participants_uids')
        
        success, renovation, error = controller.create_renovation(renovation_data, 'test_creator')
        
        assert success is False
        assert renovation == sample_renovation
        assert 'solapa' in error.lower()
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_get_renovation_by_id_success(self, mock_dao_class, sample_renovation):
        """Test obtenció exitosa de renovation"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.return_value = sample_renovation
        
        controller = RenovationController()
        success, renovation, error = controller.get_renovation_by_id('test_id')
        
        assert success is True
        assert renovation == sample_renovation
        assert error is None
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_get_renovation_by_id_not_found(self, mock_dao_class):
        """Test obtenció de renovation no existent"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.return_value = None
        
        controller = RenovationController()
        success, renovation, error = controller.get_renovation_by_id('nonexistent_id')
        
        assert success is False
        assert renovation is None
        assert 'no trobada' in error.lower()
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_get_all_renovations(self, mock_dao_class, sample_renovation):
        """Test obtenció de totes les renovations"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_all_renovations.return_value = [sample_renovation]
        
        controller = RenovationController()
        success, renovations, error = controller.get_all_renovations()
        
        assert success is True
        assert len(renovations) == 1
        assert error is None
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_update_renovation_success(self, mock_dao_class, sample_renovation):
        """Test actualització exitosa"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.return_value = sample_renovation
        mock_dao.update_renovation.return_value = True
        
        controller = RenovationController()
        success, renovation, error = controller.update_renovation(
            'test_id',
            {'description': 'Updated'},
            sample_renovation.creator_uid
        )
        
        assert success is True
        assert renovation is not None
        assert error is None
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_update_renovation_not_creator(self, mock_dao_class, sample_renovation):
        """Test actualització per no creador"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.return_value = sample_renovation
        
        controller = RenovationController()
        success, renovation, error = controller.update_renovation(
            'test_id',
            {'description': 'Updated'},
            'other_user'
        )
        
        assert success is False
        assert renovation is None
        assert 'creador' in error.lower()
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_update_renovation_invalid_dates(self, mock_dao_class, sample_renovation):
        """Test actualització amb dates invàlides"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.return_value = sample_renovation
        
        controller = RenovationController()
        today = date.today()
        success, renovation, error = controller.update_renovation(
            'test_id',
            {
                'ini_date': (today + timedelta(days=5)).isoformat(),
                'fin_date': (today + timedelta(days=1)).isoformat()
            },
            sample_renovation.creator_uid
        )
        
        assert success is False
        assert 'anterior' in error.lower()
    
    @patch('api.controllers.renovation_controller.UserDAO')
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_delete_renovation_success(self, mock_dao_class, mock_user_dao_class, sample_renovation):
        """Test eliminació exitosa"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.return_value = sample_renovation
        mock_dao.delete_renovation.return_value = (True, sample_renovation.creator_uid, sample_renovation.participants_uids)
        
        mock_user_dao = mock_user_dao_class.return_value
        
        controller = RenovationController()
        success, error = controller.delete_renovation('test_id', sample_renovation.creator_uid)
        
        assert success is True
        assert error is None
        # Verificar que es crida decrement per al creador i tots els participants
        assert mock_user_dao.decrement_renovated_refuges.call_count == 3  # 1 creator + 2 participants
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_delete_renovation_not_creator(self, mock_dao_class, sample_renovation):
        """Test eliminació per no creador"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.return_value = sample_renovation
        
        controller = RenovationController()
        success, error = controller.delete_renovation('test_id', 'other_user')
        
        assert success is False
        assert 'creador' in error.lower()
    
    @patch('api.controllers.renovation_controller.UserDAO')
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_add_participant_success(self, mock_dao_class, mock_user_dao_class, sample_renovation):
        """Test afegir participant amb èxit"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.return_value = sample_renovation
        mock_dao.add_participant.return_value = (True, None)  # (success, error_code)
        
        mock_user_dao = mock_user_dao_class.return_value
        
        controller = RenovationController()
        success, renovation, error = controller.add_participant('test_id', 'new_participant')
        
        assert success is True
        assert renovation is not None
        assert error is None
        mock_user_dao.increment_renovated_refuges.assert_called_once_with('new_participant')
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_add_participant_is_creator(self, mock_dao_class, sample_renovation):
        """Test afegir creador com a participant"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.return_value = sample_renovation
        
        controller = RenovationController()
        success, renovation, error = controller.add_participant('test_id', sample_renovation.creator_uid)
        
        assert success is False
        assert 'creador' in error.lower()
    
    @patch('api.controllers.renovation_controller.UserDAO')
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_remove_participant_success(self, mock_dao_class, mock_user_dao_class, sample_renovation):
        """Test eliminar participant amb èxit"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.return_value = sample_renovation
        mock_dao.remove_participant.return_value = True
        
        mock_user_dao = mock_user_dao_class.return_value
        
        controller = RenovationController()
        success, renovation, error = controller.remove_participant('test_id', 'participant1', 'participant1')
        
        assert success is True
        assert renovation is not None
        assert error is None
        mock_user_dao.decrement_renovated_refuges.assert_called_once_with('participant1')
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_remove_participant_expulsion_by_creator(self, mock_dao_class, sample_renovation):
        """Test expulsió d'un participant pel creador"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.return_value = sample_renovation
        mock_dao.remove_participant.return_value = True
        
        controller = RenovationController()
        # El creador expulsa un participant
        success, renovation, error = controller.remove_participant('test_id', 'participant1', sample_renovation.creator_uid)
        
        assert success is True
        assert renovation is not None
        assert error is None
        # Verificar que es crida amb is_expulsion=True
        mock_dao.remove_participant.assert_called_once_with('test_id', 'participant1', is_expulsion=True)
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_remove_participant_no_permission(self, mock_dao_class, sample_renovation):
        """Test eliminar participant sense permís"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.return_value = sample_renovation
        
        controller = RenovationController()
        success, renovation, error = controller.remove_participant('test_id', 'participant1', 'other_user')
        
        assert success is False
        assert 'permís' in error.lower()
    
    # ===== NOUS TESTS PER COBRIR EXCEPCIONS I CASOS NO COBERTS =====
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_create_renovation_dao_returns_none(self, mock_dao_class, sample_renovation_data):
        """Test quan el DAO retorna None en la creació"""
        mock_dao = mock_dao_class.return_value
        mock_dao.check_overlapping_renovations.return_value = None
        mock_dao.create_renovation.return_value = None  # DAO retorna None
        
        controller = RenovationController()
        renovation_data = sample_renovation_data.copy()
        renovation_data.pop('id')
        renovation_data.pop('creator_uid')
        renovation_data.pop('participants_uids')
        
        success, renovation, error = controller.create_renovation(renovation_data, 'test_creator')
        
        assert success is False
        assert renovation is None
        assert 'Error creant renovation a la base de dades' in error
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_create_renovation_exception(self, mock_dao_class, sample_renovation_data):
        """Test excepció durant la creació"""
        mock_dao = mock_dao_class.return_value
        mock_dao.check_overlapping_renovations.side_effect = Exception("Database error")
        
        controller = RenovationController()
        renovation_data = sample_renovation_data.copy()
        renovation_data.pop('id')
        renovation_data.pop('creator_uid')
        renovation_data.pop('participants_uids')
        
        success, renovation, error = controller.create_renovation(renovation_data, 'test_creator')
        
        assert success is False
        assert renovation is None
        assert 'Error intern' in error
        assert 'Database error' in error
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_get_renovation_by_id_exception(self, mock_dao_class):
        """Test excepció durant l'obtenció per ID"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.side_effect = Exception("Connection error")
        
        controller = RenovationController()
        success, renovation, error = controller.get_renovation_by_id('test_id')
        
        assert success is False
        assert renovation is None
        assert 'Error intern' in error
        assert 'Connection error' in error
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_get_all_renovations_exception(self, mock_dao_class):
        """Test excepció durant l'obtenció de totes les renovations"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_all_renovations.side_effect = Exception("Firestore error")
        
        controller = RenovationController()
        success, renovations, error = controller.get_all_renovations()
        
        assert success is False
        assert renovations == []
        assert 'Error intern' in error
        assert 'Firestore error' in error
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_update_renovation_not_found(self, mock_dao_class):
        """Test actualització de renovation no existent"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.return_value = None
        
        controller = RenovationController()
        success, renovation, error = controller.update_renovation(
            'nonexistent_id',
            {'description': 'Updated'},
            'test_user'
        )
        
        assert success is False
        assert renovation is None
        assert 'no trobada' in error.lower()
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_update_renovation_with_dates_overlap(self, mock_dao_class, sample_renovation):
        """Test actualització amb dates que es solapen amb altra renovation"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.return_value = sample_renovation
        
        # Crear una altra renovation que es solapa
        overlapping_renovation = Renovation(
            id='other_renovation_id',
            creator_uid='other_user',
            refuge_id=sample_renovation.refuge_id,
            ini_date=sample_renovation.ini_date,
            fin_date=sample_renovation.fin_date,
            description='Overlapping renovation',
            group_link='https://t.me/other'
        )
        mock_dao.check_overlapping_renovations.return_value = overlapping_renovation
        
        controller = RenovationController()
        today = date.today()
        success, renovation, error = controller.update_renovation(
            'test_id',
            {
                'ini_date': (today + timedelta(days=2)).isoformat(),
                'fin_date': (today + timedelta(days=6)).isoformat()
            },
            sample_renovation.creator_uid
        )
        
        assert success is False
        assert renovation == overlapping_renovation
        assert 'solapa' in error.lower()
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_update_renovation_dao_returns_false(self, mock_dao_class, sample_renovation):
        """Test quan el DAO retorna False en l'actualització"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.return_value = sample_renovation
        mock_dao.update_renovation.return_value = False  # DAO retorna False
        
        controller = RenovationController()
        success, renovation, error = controller.update_renovation(
            'test_id',
            {'description': 'Updated'},
            sample_renovation.creator_uid
        )
        
        assert success is False
        assert renovation is None
        assert 'Error actualitzant renovation a la base de dades' in error
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_update_renovation_exception(self, mock_dao_class, sample_renovation):
        """Test excepció durant l'actualització"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.side_effect = Exception("Update error")
        
        controller = RenovationController()
        success, renovation, error = controller.update_renovation(
            'test_id',
            {'description': 'Updated'},
            'test_user'
        )
        
        assert success is False
        assert renovation is None
        assert 'Error intern' in error
        assert 'Update error' in error
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_delete_renovation_not_found(self, mock_dao_class):
        """Test eliminació de renovation no existent"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.return_value = None
        
        controller = RenovationController()
        success, error = controller.delete_renovation('nonexistent_id', 'test_user')
        
        assert success is False
        assert 'no trobada' in error.lower()
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_delete_renovation_dao_returns_false(self, mock_dao_class, sample_renovation):
        """Test quan el DAO retorna False en l'eliminació"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.return_value = sample_renovation
        mock_dao.delete_renovation.return_value = (False, None, None)
        
        controller = RenovationController()
        success, error = controller.delete_renovation('test_id', sample_renovation.creator_uid)
        
        assert success is False
        assert 'Error eliminant renovation de la base de dades' in error
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_delete_renovation_exception(self, mock_dao_class, sample_renovation):
        """Test excepció durant l'eliminació"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.side_effect = Exception("Delete error")
        
        controller = RenovationController()
        success, error = controller.delete_renovation('test_id', 'test_user')
        
        assert success is False
        assert 'Error intern' in error
        assert 'Delete error' in error
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_add_participant_renovation_not_found(self, mock_dao_class):
        """Test afegir participant a renovation no existent"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.return_value = None
        
        controller = RenovationController()
        success, renovation, error = controller.add_participant('nonexistent_id', 'participant_uid')
        
        assert success is False
        assert renovation is None
        assert 'no trobada' in error.lower()
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_add_participant_dao_returns_false(self, mock_dao_class, sample_renovation):
        """Test quan el DAO retorna False (participant ja existeix o error)"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.return_value = sample_renovation
        mock_dao.add_participant.return_value = (False, 'already_participant')  # DAO retorna False amb error_code
        
        controller = RenovationController()
        success, renovation, error = controller.add_participant('test_id', 'new_participant')
        
        assert success is False
        assert renovation is None
        assert 'ja és participant' in error.lower()
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_add_participant_expelled(self, mock_dao_class, sample_renovation):
        """Test quan l'usuari està expulsat"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.return_value = sample_renovation
        mock_dao.add_participant.return_value = (False, 'expelled')
        
        controller = RenovationController()
        success, renovation, error = controller.add_participant('test_id', 'expelled_user')
        
        assert success is False
        assert renovation is None
        assert 'expulsat' in error.lower()
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_add_participant_exception(self, mock_dao_class, sample_renovation):
        """Test excepció durant l'afegició de participant"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.side_effect = Exception("Add participant error")
        
        controller = RenovationController()
        success, renovation, error = controller.add_participant('test_id', 'participant_uid')
        
        assert success is False
        assert renovation is None
        assert 'Error intern' in error
        assert 'Add participant error' in error
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_remove_participant_renovation_not_found(self, mock_dao_class):
        """Test eliminar participant de renovation no existent"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.return_value = None
        
        controller = RenovationController()
        success, renovation, error = controller.remove_participant('nonexistent_id', 'participant_uid', 'requester_uid')
        
        assert success is False
        assert renovation is None
        assert 'no trobada' in error.lower()
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_remove_participant_dao_returns_false(self, mock_dao_class, sample_renovation):
        """Test quan el DAO retorna False (participant no existeix o error)"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.return_value = sample_renovation
        mock_dao.remove_participant.return_value = False  # DAO retorna False
        
        controller = RenovationController()
        success, renovation, error = controller.remove_participant('test_id', 'participant1', 'participant1')
        
        assert success is False
        assert renovation is None
        assert 'Error eliminant participant o no és participant' in error
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_remove_participant_exception(self, mock_dao_class, sample_renovation):
        """Test excepció durant l'eliminació de participant"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.side_effect = Exception("Remove participant error")
        
        controller = RenovationController()
        success, renovation, error = controller.remove_participant('test_id', 'participant1', 'participant1')
        
        assert success is False
        assert renovation is None
        assert 'Error intern' in error
        assert 'Remove participant error' in error
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_get_renovations_by_refuge_success(self, mock_dao_class, sample_renovation):
        """Test obtenció de renovations per refugi amb èxit"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovations_by_refuge.return_value = [sample_renovation]
        
        controller = RenovationController()
        success, renovations, error = controller.get_renovations_by_refuge('test_refuge_id')
        
        assert success is True
        assert len(renovations) == 1
        assert renovations[0] == sample_renovation
        assert error is None
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_get_renovations_by_refuge_empty(self, mock_dao_class):
        """Test obtenció de renovations per refugi sense resultats"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovations_by_refuge.return_value = []
        
        controller = RenovationController()
        success, renovations, error = controller.get_renovations_by_refuge('test_refuge_id')
        
        assert success is True
        assert len(renovations) == 0
        assert error is None
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_get_renovations_by_refuge_exception(self, mock_dao_class):
        """Test excepció durant l'obtenció de renovations per refugi"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovations_by_refuge.side_effect = Exception("Query error")
        
        controller = RenovationController()
        success, renovations, error = controller.get_renovations_by_refuge('test_refuge_id')
        
        assert success is False
        assert renovations == []
        assert 'Error intern' in error
        assert 'Query error' in error
