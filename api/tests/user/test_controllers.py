"""
Tests per usuaris
"""

import pytest
from unittest.mock import Mock, patch
from api.models.user import User
from api.controllers.user_controller import UserController
from api.daos.user_dao import UserDAO
from api.daos.refugi_lliure_dao import RefugiLliureDAO


# ==================== FIXTURES PER PREFERITS I VISITATS ====================

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
            'coord': {'long': 1.5, 'lat': 42.5}
        },
        {
            'id': 'refugi_002',
            'name': 'Refugi B',
            'region': 'Pirineus',
            'places': 15,
            'coord': {'long': 1.6, 'lat': 42.6}
        }
    ]


# ==================== TESTS DE CONTROLLERS ====================


@pytest.mark.controllers
class TestUserController:
    """Tests per al UserController"""
    
    @patch('api.controllers.user_controller.UserDAO')
    def test_create_user_success(self, mock_dao_class, sample_user_data, sample_user):
        """Test creació d'usuari exitosa"""
        # Configurar mocks
        mock_dao = mock_dao_class.return_value
        mock_dao.get_user_by_uid.return_value = None  # No existeix
        mock_dao.create_user.return_value = sample_user
        
        # Executar
        controller = UserController()
        success, user, error = controller.create_user(sample_user_data, 'test_uid')
        
        # Verificacions
        assert success is True
        assert user is not None
        assert error is None
        mock_dao.create_user.assert_called_once()
    
    @patch('api.controllers.user_controller.UserDAO')
    def test_create_user_duplicate_uid(self, mock_dao_class, sample_user_data):
        """Test creació d'usuari amb UID duplicat"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_user_by_uid.return_value = sample_user_data  # Ja existeix
        
        controller = UserController()
        success, user, error = controller.create_user(sample_user_data, 'test_uid')
        
        assert success is False
        assert user is None
        assert 'ja existeix' in error
    
    @patch('api.controllers.user_controller.UserDAO')
    def test_get_user_by_uid_success(self, mock_dao_class, sample_user):
        """Test obtenció d'usuari per UID exitosa"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_user_by_uid.return_value = sample_user
        
        controller = UserController()
        success, user, error = controller.get_user_by_uid('test_uid')
        
        assert success is True
        assert user is not None
        assert error is None
    
    @patch('api.controllers.user_controller.UserDAO')
    def test_get_user_by_uid_not_found(self, mock_dao_class):
        """Test obtenció d'usuari no existent"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_user_by_uid.return_value = None
        
        controller = UserController()
        success, user, error = controller.get_user_by_uid('nonexistent_uid')
        
        assert success is False
        assert user is None
        assert 'no trobat' in error
    
    @patch('api.controllers.user_controller.UserDAO')
    def test_get_user_by_uid_empty_uid(self, mock_dao_class):
        """Test obtenció d'usuari amb UID buit"""
        controller = UserController()
        success, user, error = controller.get_user_by_uid('')
        
        assert success is False
        assert user is None
        assert 'no proporcionat' in error
    
    @patch('api.controllers.user_controller.UserDAO')
    def test_update_user_success(self, mock_dao_class, sample_user):
        """Test actualització d'usuari exitosa"""
        mock_dao = mock_dao_class.return_value
        mock_dao.user_exists.return_value = True
        mock_dao.update_user.return_value = True
        mock_dao.get_user_by_uid.return_value = sample_user
        
        controller = UserController()
        update_data = {'username': 'updated'}
        success, user, error = controller.update_user('test_uid', update_data)
        
        assert success is True
        assert user is not None
        assert error is None
    
    @patch('api.controllers.user_controller.UserDAO')
    def test_update_user_not_found(self, mock_dao_class):
        """Test actualització d'usuari no existent"""
        mock_dao = mock_dao_class.return_value
        mock_dao.user_exists.return_value = False
        
        controller = UserController()
        success, user, error = controller.update_user('nonexistent_uid', {'username': 'test'})
        
        assert success is False
        assert user is None
        assert 'no trobat' in error
    
    @patch('api.controllers.user_controller.UserDAO')
    def test_update_user_duplicate_email(self, mock_dao_class, sample_user):
        """Test actualització amb email ja en ús per altre usuari"""
        mock_dao = mock_dao_class.return_value
        mock_dao.user_exists.return_value = True
        mock_dao.user_exists_by_email.return_value = True
        
        # Email ja en ús per altre usuari
        other_user = User(
            uid='other_uid',
            username=sample_user.username,
            email=sample_user.email,
            language=sample_user.language
        )
        mock_dao.get_user_by_email.return_value = other_user
        
        controller = UserController()
        success, user, error = controller.update_user('test_uid', {'email': 'test@example.com'})
        
        assert success is False
        assert user is None
        assert 'ja està en ús' in error
    
    @patch('api.controllers.refuge_visit_controller.RefugeVisitController')
    @patch('api.controllers.refugi_lliure_controller.RefugiLliureController')
    @patch('api.controllers.renovation_controller.RenovationController')
    @patch('api.controllers.refuge_proposal_controller.RefugeProposalController')
    @patch('api.controllers.doubt_controller.DoubtController')
    @patch('api.controllers.experience_controller.ExperienceController')
    @patch('api.controllers.user_controller.UserDAO')
    def test_delete_user_success(self, mock_dao_class, mock_exp_ctrl, mock_doubt_ctrl, mock_prop_ctrl, mock_ren_ctrl, mock_refugi_ctrl, mock_visit_ctrl):
        """Test eliminació d'usuari exitosa"""
        mock_dao = mock_dao_class.return_value
        mock_dao.user_exists.return_value = True
        mock_dao.delete_user.return_value = True
        mock_dao.get_user_by_uid.return_value = Mock(uploaded_photos_keys=[], avatar_metadata=None, visited_refuges=[])
        
        # Configurar mocks dels altres controllers
        mock_exp_ctrl.return_value.delete_experiences_by_creator.return_value = (True, None)
        mock_doubt_ctrl.return_value.delete_doubts_by_creator.return_value = (True, None)
        mock_doubt_ctrl.return_value.delete_answers_by_creator.return_value = (True, None)
        mock_prop_ctrl.return_value.anonymize_proposals_by_creator.return_value = (True, None)
        mock_ren_ctrl.return_value.anonymize_renovations_by_creator.return_value = (True, None)
        mock_ren_ctrl.return_value.remove_user_from_participations.return_value = (True, None)
        mock_visit_ctrl.return_value.remove_user_from_all_visits.return_value = (True, None)
        
        controller = UserController()
        success, error = controller.delete_user('test_uid')
        
        assert success is True
        assert error is None
    
    @patch('api.controllers.user_controller.UserDAO')
    def test_delete_user_not_found(self, mock_dao_class):
        """Test eliminació d'usuari no existent"""
        mock_dao = mock_dao_class.return_value
        # get_user_by_uid retorna None si no existeix
        mock_dao.get_user_by_uid.return_value = None
        
        controller = UserController()
        success, error = controller.delete_user('nonexistent_uid')
        
        assert success is False
        assert 'no trobat' in error
    
    # ===== NOUS TESTS PER COBRIR EXCEPCIONS I CASOS NO COBERTS =====
    
    @patch('api.controllers.user_controller.UserDAO')
    def test_create_user_dao_returns_none(self, mock_dao_class, sample_user_data):
        """Test quan el DAO retorna None en la creació"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_user_by_uid.return_value = None
        mock_dao.user_exists_by_email.return_value = False
        mock_dao.create_user.return_value = None
        
        controller = UserController()
        success, user, error = controller.create_user(sample_user_data, 'test_uid')
        
        assert success is False
        assert user is None
        assert 'Error creant usuari' in error
    
    @patch('api.controllers.user_controller.UserDAO')
    def test_create_user_exception(self, mock_dao_class, sample_user_data):
        """Test excepció durant la creació"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_user_by_uid.side_effect = Exception("Database error")
        
        controller = UserController()
        success, user, error = controller.create_user(sample_user_data, 'test_uid')
        
        assert success is False
        assert user is None
        assert 'Error intern' in error
    
    @patch('api.controllers.user_controller.UserDAO')
    def test_get_user_by_uid_exception(self, mock_dao_class):
        """Test excepció durant l'obtenció per UID"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_user_by_uid.side_effect = Exception("Connection error")
        
        controller = UserController()
        success, user, error = controller.get_user_by_uid('test_uid')
        
        assert success is False
        assert user is None
        assert 'Error intern' in error
    
    @patch('api.controllers.user_controller.UserDAO')
    def test_update_user_empty_uid(self, mock_dao_class):
        """Test actualització amb UID buit"""
        controller = UserController()
        success, user, error = controller.update_user('', {'username': 'test'})
        
        assert success is False
        assert user is None
        assert 'no proporcionat' in error
    
    @patch('api.controllers.user_controller.UserDAO')
    def test_update_user_empty_data(self, mock_dao_class):
        """Test actualització sense dades"""
        mock_dao = mock_dao_class.return_value
        mock_dao.user_exists.return_value = True
        
        controller = UserController()
        success, user, error = controller.update_user('test_uid', {})
        
        assert success is False
        assert user is None
        assert 'No s\'han proporcionat dades' in error
    
    @patch('api.controllers.user_controller.UserDAO')
    def test_update_user_email_same_user(self, mock_dao_class, sample_user):
        """Test actualització amb el mateix email de l'usuari"""
        mock_dao = mock_dao_class.return_value
        mock_dao.user_exists.return_value = True
        mock_dao.user_exists_by_email.return_value = True
        mock_dao.get_user_by_email.return_value = sample_user  # Mateix usuari
        mock_dao.update_user.return_value = True
        mock_dao.get_user_by_uid.return_value = sample_user
        
        controller = UserController()
        success, user, error = controller.update_user(sample_user.uid, {'email': sample_user.email})
        
        assert success is True
        assert user is not None
        assert error is None
    
    @patch('api.controllers.user_controller.UserDAO')
    def test_update_user_dao_returns_false(self, mock_dao_class):
        """Test quan el DAO retorna False en l'actualització"""
        mock_dao = mock_dao_class.return_value
        mock_dao.user_exists.return_value = True
        mock_dao.update_user.return_value = False
        
        controller = UserController()
        success, user, error = controller.update_user('test_uid', {'username': 'test'})
        
        assert success is False
        assert user is None
        assert 'Error actualitzant usuari' in error
    
    @patch('api.controllers.user_controller.UserDAO')
    def test_update_user_exception(self, mock_dao_class):
        """Test excepció durant l'actualització"""
        mock_dao = mock_dao_class.return_value
        mock_dao.user_exists.side_effect = Exception("Update error")
        
        controller = UserController()
        success, user, error = controller.update_user('test_uid', {'username': 'test'})
        
        assert success is False
        assert user is None
        assert 'Error intern' in error
    
    @patch('api.controllers.user_controller.UserDAO')
    def test_delete_user_empty_uid(self, mock_dao_class):
        """Test eliminació amb UID buit"""
        controller = UserController()
        success, error = controller.delete_user('')
        
        assert success is False
        assert 'no proporcionat' in error
    
    @patch('api.controllers.refuge_visit_controller.RefugeVisitController')
    @patch('api.controllers.refugi_lliure_controller.RefugiLliureController')
    @patch('api.controllers.renovation_controller.RenovationController')
    @patch('api.controllers.refuge_proposal_controller.RefugeProposalController')
    @patch('api.controllers.doubt_controller.DoubtController')
    @patch('api.controllers.experience_controller.ExperienceController')
    @patch('api.controllers.user_controller.UserDAO')
    def test_delete_user_dao_returns_false(self, mock_dao_class, mock_exp_ctrl, mock_doubt_ctrl, mock_prop_ctrl, mock_ren_ctrl, mock_refugi_ctrl, mock_visit_ctrl):
        """Test quan el DAO retorna False en l'eliminació"""
        mock_dao = mock_dao_class.return_value
        mock_dao.user_exists.return_value = True
        mock_dao.delete_user.return_value = False
        mock_dao.get_user_by_uid.return_value = Mock(uploaded_photos_keys=[], avatar_metadata=None, visited_refuges=[])
        
        # Configurar mocks dels altres controllers
        mock_exp_ctrl.return_value.delete_experiences_by_creator.return_value = (True, None)
        mock_doubt_ctrl.return_value.delete_doubts_by_creator.return_value = (True, None)
        mock_doubt_ctrl.return_value.delete_answers_by_creator.return_value = (True, None)
        mock_prop_ctrl.return_value.anonymize_proposals_by_creator.return_value = (True, None)
        mock_ren_ctrl.return_value.anonymize_renovations_by_creator.return_value = (True, None)
        mock_ren_ctrl.return_value.remove_user_from_participations.return_value = (True, None)
        mock_visit_ctrl.return_value.remove_user_from_all_visits.return_value = (True, None)
        
        controller = UserController()
        success, error = controller.delete_user('test_uid')
        
        assert success is False
        assert 'Error eliminant usuari' in error
    
    @patch('api.controllers.user_controller.UserDAO')
    def test_delete_user_exception(self, mock_dao_class):
        """Test excepció durant l'eliminació"""
        mock_dao = mock_dao_class.return_value
        # get_user_by_uid es crida primer
        mock_dao.get_user_by_uid.side_effect = Exception("Delete error")
        
        controller = UserController()
        success, error = controller.delete_user('test_uid')
        
        assert success is False
        assert 'Error intern' in error
    
    # Tests per gestió de refugis (preferits/visitats)
    @patch('api.controllers.user_controller.RefugiLliureDAO')
    @patch('api.controllers.user_controller.UserDAO')
    def test_add_refugi_preferit_success(self, mock_user_dao_class, mock_refugi_dao_class):
        """Test afegir refugi preferit amb èxit"""
        mock_user_dao = mock_user_dao_class.return_value
        mock_refugi_dao = mock_refugi_dao_class.return_value
        
        mock_user_dao.user_exists.return_value = True
        mock_refugi_dao.refugi_exists.return_value = True
        mock_user_dao.add_refugi_to_list.return_value = (True, ['refuge1'])
        mock_user_dao.get_refugis_info.return_value = [{'id': 'refuge1'}]
        
        controller = UserController()
        success, refugis, error = controller.add_refugi_preferit('test_uid', 'refuge1')
        
        assert success is True
        assert refugis is not None
        assert error is None
    
    @patch('api.controllers.user_controller.UserDAO')
    def test_add_refugi_preferit_empty_uid(self, mock_user_dao_class):
        """Test afegir refugi preferit amb UID buit"""
        controller = UserController()
        success, refugis, error = controller.add_refugi_preferit('', 'refuge1')
        
        assert success is False
        assert refugis is None
        assert 'no proporcionat' in error
    
    @patch('api.controllers.user_controller.UserDAO')
    def test_add_refugi_preferit_empty_refuge_id(self, mock_user_dao_class):
        """Test afegir refugi preferit amb refuge_id buit"""
        controller = UserController()
        success, refugis, error = controller.add_refugi_preferit('test_uid', '')
        
        assert success is False
        assert refugis is None
        assert 'refugi no proporcionat' in error
    
    @patch('api.controllers.user_controller.UserDAO')
    def test_add_refugi_preferit_user_not_found(self, mock_user_dao_class):
        """Test afegir refugi preferit amb usuari no existent"""
        mock_user_dao = mock_user_dao_class.return_value
        mock_user_dao.user_exists.return_value = False
        
        controller = UserController()
        success, refugis, error = controller.add_refugi_preferit('test_uid', 'refuge1')
        
        assert success is False
        assert refugis is None
        assert 'no trobat' in error
    
    @patch('api.controllers.user_controller.RefugiLliureDAO')
    @patch('api.controllers.user_controller.UserDAO')
    def test_add_refugi_preferit_refuge_not_found(self, mock_user_dao_class, mock_refugi_dao_class):
        """Test afegir refugi preferit amb refugi no existent"""
        mock_user_dao = mock_user_dao_class.return_value
        mock_refugi_dao = mock_refugi_dao_class.return_value
        
        mock_user_dao.user_exists.return_value = True
        mock_refugi_dao.refugi_exists.return_value = False
        
        controller = UserController()
        success, refugis, error = controller.add_refugi_preferit('test_uid', 'refuge1')
        
        assert success is False
        assert refugis is None
        assert 'Refugi' in error
        assert 'no trobat' in error
    
    @patch('api.controllers.user_controller.RefugiLliureDAO')
    @patch('api.controllers.user_controller.UserDAO')
    def test_add_refugi_preferit_dao_returns_false(self, mock_user_dao_class, mock_refugi_dao_class):
        """Test afegir refugi preferit quan DAO retorna False"""
        mock_user_dao = mock_user_dao_class.return_value
        mock_refugi_dao = mock_refugi_dao_class.return_value
        
        mock_user_dao.user_exists.return_value = True
        mock_refugi_dao.refugi_exists.return_value = True
        mock_user_dao.add_refugi_to_list.return_value = (False, [])
        
        controller = UserController()
        success, refugis, error = controller.add_refugi_preferit('test_uid', 'refuge1')
        
        assert success is False
        assert refugis is None
        assert 'Error afegint refugi' in error
    
    @patch('api.controllers.user_controller.RefugiLliureDAO')
    @patch('api.controllers.user_controller.UserDAO')
    def test_add_refugi_preferit_exception(self, mock_user_dao_class, mock_refugi_dao_class):
        """Test excepció durant l'afegició de refugi preferit"""
        mock_user_dao = mock_user_dao_class.return_value
        mock_user_dao.user_exists.side_effect = Exception("Add error")
        
        controller = UserController()
        success, refugis, error = controller.add_refugi_preferit('test_uid', 'refuge1')
        
        assert success is False
        assert refugis is None
        assert 'Error intern' in error
    
    @patch('api.controllers.user_controller.RefugiLliureDAO')
    @patch('api.controllers.user_controller.UserDAO')
    def test_remove_refugi_preferit_success(self, mock_user_dao_class, mock_refugi_dao_class):
        """Test eliminar refugi preferit amb èxit"""
        mock_user_dao = mock_user_dao_class.return_value
        mock_refugi_dao = mock_refugi_dao_class.return_value
        
        mock_user_dao.user_exists.return_value = True
        mock_refugi_dao.refugi_exists.return_value = True
        mock_user_dao.remove_refugi_from_list.return_value = (True, [])
        mock_user_dao.get_refugis_info.return_value = []
        
        controller = UserController()
        success, refugis, error = controller.remove_refugi_preferit('test_uid', 'refuge1')
        
        assert success is True
        assert refugis is not None
        assert error is None
    
    @patch('api.controllers.user_controller.RefugiLliureDAO')
    @patch('api.controllers.user_controller.UserDAO')
    def test_add_refugi_visitat_success(self, mock_user_dao_class, mock_refugi_dao_class):
        """Test afegir refugi visitat amb èxit (actualitza visitants)"""
        mock_user_dao = mock_user_dao_class.return_value
        mock_refugi_dao = mock_refugi_dao_class.return_value
        
        mock_user_dao.user_exists.return_value = True
        mock_refugi_dao.refugi_exists.return_value = True
        mock_user_dao.add_refugi_to_list.return_value = (True, ['refuge1'])
        mock_user_dao.get_refugis_info.return_value = [{'id': 'refuge1'}]
        mock_refugi_dao.add_visitor_to_refugi.return_value = True
        
        controller = UserController()
        success, refugis, error = controller.add_refugi_visitat('test_uid', 'refuge1')
        
        assert success is True
        assert refugis is not None
        assert error is None
        mock_refugi_dao.add_visitor_to_refugi.assert_called_once()
    
    @patch('api.controllers.user_controller.RefugiLliureDAO')
    @patch('api.controllers.user_controller.UserDAO')
    def test_add_refugi_visitat_visitor_update_fails(self, mock_user_dao_class, mock_refugi_dao_class):
        """Test afegir refugi visitat quan falla l'actualització de visitants"""
        mock_user_dao = mock_user_dao_class.return_value
        mock_refugi_dao = mock_refugi_dao_class.return_value
        
        mock_user_dao.user_exists.return_value = True
        mock_refugi_dao.refugi_exists.return_value = True
        mock_user_dao.add_refugi_to_list.return_value = (True, ['refuge1'])
        mock_user_dao.get_refugis_info.return_value = [{'id': 'refuge1'}]
        mock_refugi_dao.add_visitor_to_refugi.return_value = False  # Falla
        
        controller = UserController()
        success, refugis, error = controller.add_refugi_visitat('test_uid', 'refuge1')
        
        # Encara retorna success perquè és un warning, no un error
        assert success is True
        assert refugis is not None
    
    @patch('api.controllers.user_controller.RefugiLliureDAO')
    @patch('api.controllers.user_controller.UserDAO')
    def test_remove_refugi_visitat_success(self, mock_user_dao_class, mock_refugi_dao_class):
        """Test eliminar refugi visitat amb èxit"""
        mock_user_dao = mock_user_dao_class.return_value
        mock_refugi_dao = mock_refugi_dao_class.return_value
        
        mock_user_dao.user_exists.return_value = True
        mock_refugi_dao.refugi_exists.return_value = True
        mock_user_dao.remove_refugi_from_list.return_value = (True, [])
        mock_user_dao.get_refugis_info.return_value = []
        mock_refugi_dao.remove_visitor_from_refugi.return_value = True
        
        controller = UserController()
        success, refugis, error = controller.remove_refugi_visitat('test_uid', 'refuge1')
        
        assert success is True
        assert refugis is not None
        assert error is None
        mock_refugi_dao.remove_visitor_from_refugi.assert_called_once()
    
    @patch('api.controllers.user_controller.RefugiLliureDAO')
    @patch('api.controllers.user_controller.UserDAO')
    def test_remove_refugi_visitat_visitor_update_fails(self, mock_user_dao_class, mock_refugi_dao_class):
        """Test eliminar refugi visitat quan falla l'eliminació de visitants"""
        mock_user_dao = mock_user_dao_class.return_value
        mock_refugi_dao = mock_refugi_dao_class.return_value
        
        mock_user_dao.user_exists.return_value = True
        mock_refugi_dao.refugi_exists.return_value = True
        mock_user_dao.remove_refugi_from_list.return_value = (True, [])
        mock_user_dao.get_refugis_info.return_value = []
        mock_refugi_dao.remove_visitor_from_refugi.return_value = False
        
        controller = UserController()
        success, refugis, error = controller.remove_refugi_visitat('test_uid', 'refuge1')
        
        assert success is True
        assert refugis is not None
    
    @patch('api.controllers.user_controller.UserDAO')
    def test_get_refugis_preferits_info_success(self, mock_user_dao_class):
        """Test obtenció d'informació de refugis preferits"""
        mock_user_dao = mock_user_dao_class.return_value
        mock_user_dao.user_exists.return_value = True
        mock_user_dao.get_refugis_info.return_value = [{'id': 'refuge1'}]
        
        controller = UserController()
        success, refugis, error = controller.get_refugis_preferits_info('test_uid')
        
        assert success is True
        assert refugis is not None
        assert error is None
    
    @patch('api.controllers.user_controller.UserDAO')
    def test_get_refugis_preferits_info_empty_uid(self, mock_user_dao_class):
        """Test obtenció de refugis preferits amb UID buit"""
        controller = UserController()
        success, refugis, error = controller.get_refugis_preferits_info('')
        
        assert success is False
        assert refugis is None
        assert 'no proporcionat' in error
    
    @patch('api.controllers.user_controller.UserDAO')
    def test_get_refugis_preferits_info_user_not_found(self, mock_user_dao_class):
        """Test obtenció de refugis preferits amb usuari no existent"""
        mock_user_dao = mock_user_dao_class.return_value
        mock_user_dao.user_exists.return_value = False
        
        controller = UserController()
        success, refugis, error = controller.get_refugis_preferits_info('test_uid')
        
        assert success is False
        assert refugis is None
        assert 'no trobat' in error
    
    @patch('api.controllers.user_controller.UserDAO')
    def test_get_refugis_preferits_info_exception(self, mock_user_dao_class):
        """Test excepció durant l'obtenció de refugis preferits"""
        mock_user_dao = mock_user_dao_class.return_value
        mock_user_dao.user_exists.side_effect = Exception("Query error")
        
        controller = UserController()
        success, refugis, error = controller.get_refugis_preferits_info('test_uid')
        
        assert success is False
        assert refugis is None
        assert 'Error intern' in error
    
    @patch('api.controllers.user_controller.UserDAO')
    def test_get_refugis_visitats_info_success(self, mock_user_dao_class):
        """Test obtenció d'informació de refugis visitats"""
        mock_user_dao = mock_user_dao_class.return_value
        mock_user_dao.user_exists.return_value = True
        mock_user_dao.get_refugis_info.return_value = [{'id': 'refuge1'}]
        
        controller = UserController()
        success, refugis, error = controller.get_refugis_visitats_info('test_uid')
        
        assert success is True
        assert refugis is not None
        assert error is None


# ==================== TESTS DE VIEWS ====================


# ==================== TESTS REFUGIS PREFERITS I VISITATS ====================

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

