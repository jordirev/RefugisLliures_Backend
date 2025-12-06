"""
Tests per renovations
"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, date, timedelta
from api.models.renovation import Renovation
from api.daos.renovation_dao import RenovationDAO
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
        'participants_uids': ['participant1', 'participant2'],
        'expelled_uids': []
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
        participants_uids=sample_renovation_data['participants_uids'],
        expelled_uids=sample_renovation_data['expelled_uids']
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


# ===== TEST DAO =====

@pytest.mark.django_db
class TestRenovationDAO:
    """Tests per al DAO de renovation"""
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_create_renovation_success(self, mock_cache, mock_firestore_service, sample_renovation_data):
        """Test creació exitosa de renovation"""
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.id = 'new_renovation_id'
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = RenovationDAO()
        renovation_data = sample_renovation_data.copy()
        renovation_data.pop('id')
        
        result = dao.create_renovation(renovation_data)
        
        assert result is not None
        assert result.creator_uid == renovation_data['creator_uid']
        mock_doc_ref.set.assert_called_once()
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_get_renovation_by_id_found(self, mock_cache, mock_firestore_service, sample_renovation_data):
        """Test obtenció de renovation per ID (trobada)"""
        mock_cache.get.return_value = None
        mock_cache.generate_key.return_value = 'test_cache_key'
        mock_cache.get_timeout.return_value = 300
        
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.id = sample_renovation_data['id']
        mock_doc.to_dict.return_value = sample_renovation_data
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = RenovationDAO()
        result = dao.get_renovation_by_id('test_id')
        
        assert result is not None
        assert result.id == sample_renovation_data['id']
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_get_renovation_by_id_not_found(self, mock_cache, mock_firestore_service):
        """Test obtenció de renovation per ID (no trobada)"""
        mock_cache.get.return_value = None
        
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc = MagicMock()
        mock_doc.exists = False
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = RenovationDAO()
        result = dao.get_renovation_by_id('nonexistent_id')
        
        assert result is None
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_get_renovation_by_id_from_cache(self, mock_cache, mock_firestore_service, sample_renovation_data):
        """Test obtenció de renovation des de cache"""
        mock_cache.get.return_value = sample_renovation_data
        mock_cache.generate_key.return_value = 'test_cache_key'
        
        dao = RenovationDAO()
        result = dao.get_renovation_by_id('test_id')
        
        assert result is not None
        assert result.id == sample_renovation_data['id']
        # No hauria de cridar Firestore
        mock_firestore_service.return_value.get_db.assert_not_called()
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    @patch('api.daos.renovation_dao.get_madrid_today')
    def test_get_all_renovations(self, mock_get_today, mock_cache, mock_firestore_service, sample_renovation_data):
        """Test obtenció de totes les renovations actives"""
        mock_today = date.today()
        mock_get_today.return_value = mock_today
        mock_cache.get.return_value = None
        mock_cache.generate_key.return_value = 'test_cache_key'
        mock_cache.get_timeout.return_value = 300
        
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc = MagicMock()
        mock_doc.id = sample_renovation_data['id']
        mock_doc.to_dict.return_value = sample_renovation_data
        
        mock_query = MagicMock()
        mock_query.stream.return_value = [mock_doc]
        
        mock_collection = MagicMock()
        mock_collection.where.return_value.order_by.return_value = mock_query
        mock_db.collection.return_value = mock_collection
        
        dao = RenovationDAO()
        result = dao.get_all_renovations()
        
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].id == sample_renovation_data['id']
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_update_renovation_success(self, mock_cache, mock_firestore_service, sample_renovation_data):
        """Test actualització exitosa de renovation"""
        mock_cache.generate_key.return_value = 'test_cache_key'
        
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = sample_renovation_data
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = RenovationDAO()
        result = dao.update_renovation('test_id', {'description': 'Updated'})
        
        assert result is True
        mock_doc_ref.update.assert_called_once()
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_update_renovation_not_found(self, mock_cache, mock_firestore_service):
        """Test actualització de renovation no existent"""
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc = MagicMock()
        mock_doc.exists = False
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = RenovationDAO()
        result = dao.update_renovation('nonexistent_id', {'description': 'Updated'})
        
        assert result is False
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_delete_renovation_success(self, mock_cache, mock_firestore_service, sample_renovation_data):
        """Test eliminació exitosa de renovation"""
        mock_cache.generate_key.return_value = 'test_cache_key'
        
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = sample_renovation_data
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = RenovationDAO()
        result, creator, participants = dao.delete_renovation('test_id')
        
        assert result is True
        mock_doc_ref.delete.assert_called_once()
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    @patch('api.daos.renovation_dao.get_madrid_today')
    def test_check_overlapping_renovations_found(self, mock_get_today, mock_cache, mock_firestore_service, sample_renovation_data):
        """Test detecció de solapament (trobat)"""
        mock_today = date.today()
        mock_get_today.return_value = mock_today
        
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc = MagicMock()
        mock_doc.id = sample_renovation_data['id']
        mock_doc.to_dict.return_value = sample_renovation_data
        
        mock_query = MagicMock()
        mock_query.stream.return_value = [mock_doc]
        
        mock_collection = MagicMock()
        mock_collection.where.return_value.where.return_value.order_by.return_value = mock_query
        mock_db.collection.return_value = mock_collection
        
        dao = RenovationDAO()
        # Dades que se solapen
        result = dao.check_overlapping_renovations(
            sample_renovation_data['refuge_id'],
            sample_renovation_data['ini_date'],
            sample_renovation_data['fin_date']
        )
        
        assert result is not None
        assert result.id == sample_renovation_data['id']
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    @patch('api.daos.renovation_dao.get_madrid_today')
    def test_check_overlapping_renovations_not_found(self, mock_get_today, mock_cache, mock_firestore_service):
        """Test detecció de solapament (no trobat)"""
        mock_today = date.today()
        mock_get_today.return_value = mock_today
        
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_query = MagicMock()
        mock_query.stream.return_value = []
        
        mock_collection = MagicMock()
        mock_collection.where.return_value.where.return_value.order_by.return_value = mock_query
        mock_db.collection.return_value = mock_collection
        
        dao = RenovationDAO()
        result = dao.check_overlapping_renovations(
            'test_refuge',
            (date.today() + timedelta(days=10)).isoformat(),
            (date.today() + timedelta(days=15)).isoformat()
        )
        
        assert result is None
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_add_participant_success(self, mock_cache, mock_firestore_service, sample_renovation_data):
        """Test afegir participant amb èxit"""
        mock_cache.generate_key.return_value = 'test_cache_key'
        
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = sample_renovation_data
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = RenovationDAO()
        success, error_code = dao.add_participant('test_id', 'new_participant')
        
        assert success is True
        assert error_code is None
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_add_participant_already_exists(self, mock_cache, mock_firestore_service, sample_renovation_data):
        """Test afegir participant que ja existeix"""
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = sample_renovation_data
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = RenovationDAO()
        success, error_code = dao.add_participant('test_id', 'participant1')  # Ja existeix
        
        assert success is False
        assert error_code == 'already_participant'
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_add_participant_expelled(self, mock_cache, mock_firestore_service, sample_renovation_data):
        """Test afegir participant que està expulsat"""
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        # Afegir expelled_uids al sample_renovation_data
        renovation_data = sample_renovation_data.copy()
        renovation_data['expelled_uids'] = ['expelled_user']
        
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = renovation_data
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = RenovationDAO()
        success, error_code = dao.add_participant('test_id', 'expelled_user')
        
        assert success is False
        assert error_code == 'expelled'
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_remove_participant_success(self, mock_cache, mock_firestore_service, sample_renovation_data):
        """Test eliminar participant amb èxit"""
        mock_cache.generate_key.return_value = 'test_cache_key'
        
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = sample_renovation_data
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = RenovationDAO()
        result = dao.remove_participant('test_id', 'participant1')
        
        assert result is True
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_remove_participant_not_exists(self, mock_cache, mock_firestore_service, sample_renovation_data):
        """Test eliminar participant que no existeix"""
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = sample_renovation_data
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = RenovationDAO()
        result = dao.remove_participant('test_id', 'nonexistent_participant')
        
        assert result is False
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_remove_participant_with_expulsion(self, mock_cache, mock_firestore_service, sample_renovation_data):
        """Test eliminar participant amb expulsió (afegir a expelled_uids)"""
        mock_cache.generate_key.return_value = 'test_cache_key'
        
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = sample_renovation_data
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = RenovationDAO()
        result = dao.remove_participant('test_id', 'participant1', is_expulsion=True)
        
        assert result is True
        # Verificar que s'ha cridat update amb expelled_uids
        update_call_args = mock_doc_ref.update.call_args[0][0]
        assert 'expelled_uids' in update_call_args
        assert 'participant1' in update_call_args['expelled_uids']
    
    # ===== NOUS TESTS PER COBRIR EXCEPCIONS I CASOS NO COBERTS DEL DAO =====
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_create_renovation_exception(self, mock_cache, mock_firestore_service, sample_renovation_data):
        """Test excepció durant la creació de renovation"""
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.side_effect = Exception("Firestore connection error")
        
        dao = RenovationDAO()
        renovation_data = sample_renovation_data.copy()
        renovation_data.pop('id')
        
        result = dao.create_renovation(renovation_data)
        
        assert result is None
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_get_renovation_by_id_exception(self, mock_cache, mock_firestore_service):
        """Test excepció durant l'obtenció per ID"""
        mock_cache.get.return_value = None
        mock_cache.generate_key.return_value = 'test_cache_key'
        
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.side_effect = Exception("Database error")
        
        dao = RenovationDAO()
        result = dao.get_renovation_by_id('test_id')
        
        assert result is None
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    @patch('api.daos.renovation_dao.get_madrid_today')
    def test_get_all_renovations_from_cache(self, mock_get_today, mock_cache, mock_firestore_service, sample_renovation_data):
        """Test obtenció de renovations des de cache"""
        mock_today = date.today()
        mock_get_today.return_value = mock_today
        mock_cache.get.return_value = [sample_renovation_data]
        mock_cache.generate_key.return_value = 'test_cache_key'
        
        dao = RenovationDAO()
        result = dao.get_all_renovations()
        
        assert isinstance(result, list)
        assert len(result) == 1
        # No hauria de cridar Firestore
        mock_firestore_service.return_value.get_db.assert_not_called()
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    @patch('api.daos.renovation_dao.get_madrid_today')
    def test_get_all_renovations_exception(self, mock_get_today, mock_cache, mock_firestore_service):
        """Test excepció durant l'obtenció de totes les renovations"""
        mock_today = date.today()
        mock_get_today.return_value = mock_today
        mock_cache.get.return_value = None
        mock_cache.generate_key.return_value = 'test_cache_key'
        
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.side_effect = Exception("Query error")
        
        dao = RenovationDAO()
        result = dao.get_all_renovations()
        
        assert result == []
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_update_renovation_exception(self, mock_cache, mock_firestore_service):
        """Test excepció durant l'actualització"""
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.side_effect = Exception("Update error")
        
        dao = RenovationDAO()
        result = dao.update_renovation('test_id', {'description': 'Updated'})
        
        assert result is False
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_delete_renovation_not_found(self, mock_cache, mock_firestore_service):
        """Test eliminació de renovation no existent"""
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc = MagicMock()
        mock_doc.exists = False
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = RenovationDAO()
        result, creator, participants = dao.delete_renovation('nonexistent_id')
        
        assert result is False
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_delete_renovation_exception(self, mock_cache, mock_firestore_service):
        """Test excepció durant l'eliminació"""
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.side_effect = Exception("Delete error")
        
        dao = RenovationDAO()
        result, creator, participants = dao.delete_renovation('test_id')
        
        assert result is False
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_get_renovations_by_refuge_all(self, mock_cache, mock_firestore_service, sample_renovation_data):
        """Test obtenció de totes les renovations d'un refugi"""
        mock_cache.get.return_value = None
        mock_cache.generate_key.return_value = 'test_cache_key'
        mock_cache.get_timeout.return_value = 300
        
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc = MagicMock()
        mock_doc.id = sample_renovation_data['id']
        mock_doc.to_dict.return_value = sample_renovation_data
        
        mock_query = MagicMock()
        mock_query.stream.return_value = [mock_doc]
        
        # Mock per al chain: collection().where().order_by()
        mock_where = MagicMock()
        mock_where.order_by.return_value = mock_query
        
        mock_collection = MagicMock()
        mock_collection.where.return_value = mock_where
        mock_db.collection.return_value = mock_collection
        
        dao = RenovationDAO()
        result = dao.get_renovations_by_refuge('test_refuge_id', active_only=False)
        
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].refuge_id == sample_renovation_data['refuge_id']
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    @patch('api.daos.renovation_dao.get_madrid_today')
    def test_get_renovations_by_refuge_active_only(self, mock_get_today, mock_cache, mock_firestore_service, sample_renovation_data):
        """Test obtenció només de renovations actives d'un refugi"""
        mock_today = date.today()
        mock_get_today.return_value = mock_today
        mock_cache.get.return_value = None
        mock_cache.generate_key.return_value = 'test_cache_key'
        mock_cache.get_timeout.return_value = 300
        
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc = MagicMock()
        mock_doc.id = sample_renovation_data['id']
        mock_doc.to_dict.return_value = sample_renovation_data
        
        mock_query = MagicMock()
        mock_query.stream.return_value = [mock_doc]
        
        mock_collection = MagicMock()
        mock_collection.where.return_value.where.return_value.order_by.return_value = mock_query
        mock_db.collection.return_value = mock_collection
        
        dao = RenovationDAO()
        result = dao.get_renovations_by_refuge('test_refuge_id', active_only=True)
        
        assert isinstance(result, list)
        assert len(result) == 1
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_get_renovations_by_refuge_from_cache(self, mock_cache, mock_firestore_service, sample_renovation_data):
        """Test obtenció de renovations per refugi des de cache"""
        mock_cache.get.return_value = [sample_renovation_data]
        mock_cache.generate_key.return_value = 'test_cache_key'
        
        dao = RenovationDAO()
        result = dao.get_renovations_by_refuge('test_refuge_id')
        
        assert isinstance(result, list)
        assert len(result) == 1
        # No hauria de cridar Firestore
        mock_firestore_service.return_value.get_db.assert_not_called()
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_get_renovations_by_refuge_empty(self, mock_cache, mock_firestore_service):
        """Test obtenció de renovations per refugi sense resultats"""
        mock_cache.get.return_value = None
        mock_cache.generate_key.return_value = 'test_cache_key'
        mock_cache.get_timeout.return_value = 300
        
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_query = MagicMock()
        mock_query.stream.return_value = []
        
        mock_collection = MagicMock()
        mock_collection.where.return_value = mock_query
        mock_db.collection.return_value = mock_collection
        
        dao = RenovationDAO()
        result = dao.get_renovations_by_refuge('test_refuge_id')
        
        assert isinstance(result, list)
        assert len(result) == 0
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_get_renovations_by_refuge_exception(self, mock_cache, mock_firestore_service):
        """Test excepció durant l'obtenció de renovations per refugi"""
        mock_cache.get.return_value = None
        mock_cache.generate_key.return_value = 'test_cache_key'
        
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.side_effect = Exception("Query error")
        
        dao = RenovationDAO()
        result = dao.get_renovations_by_refuge('test_refuge_id')
        
        assert result == []
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    @patch('api.daos.renovation_dao.get_madrid_today')
    def test_check_overlapping_renovations_with_exclude(self, mock_get_today, mock_cache, mock_firestore_service, sample_renovation_data):
        """Test detecció de solapament excloent una renovation"""
        mock_today = date.today()
        mock_get_today.return_value = mock_today
        
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc = MagicMock()
        mock_doc.id = sample_renovation_data['id']
        mock_doc.to_dict.return_value = sample_renovation_data
        
        mock_query = MagicMock()
        mock_query.stream.return_value = [mock_doc]
        
        mock_collection = MagicMock()
        mock_collection.where.return_value.where.return_value.order_by.return_value = mock_query
        mock_db.collection.return_value = mock_collection
        
        dao = RenovationDAO()
        # Excloure la renovation que coincideix
        result = dao.check_overlapping_renovations(
            sample_renovation_data['refuge_id'],
            sample_renovation_data['ini_date'],
            sample_renovation_data['fin_date'],
            exclude_id=sample_renovation_data['id']
        )
        
        assert result is None
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    @patch('api.daos.renovation_dao.get_madrid_today')
    def test_check_overlapping_renovations_exception(self, mock_get_today, mock_cache, mock_firestore_service):
        """Test excepció durant la comprovació de solapaments"""
        mock_today = date.today()
        mock_get_today.return_value = mock_today
        
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.side_effect = Exception("Query error")
        
        dao = RenovationDAO()
        result = dao.check_overlapping_renovations(
            'test_refuge',
            (date.today() + timedelta(days=1)).isoformat(),
            (date.today() + timedelta(days=5)).isoformat()
        )
        
        assert result is None
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_add_participant_renovation_not_found(self, mock_cache, mock_firestore_service):
        """Test afegir participant a renovation no existent"""
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc = MagicMock()
        mock_doc.exists = False
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = RenovationDAO()
        success, error_code = dao.add_participant('nonexistent_id', 'participant_uid')
        
        assert success is False
        assert error_code == 'not_found'
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_add_participant_exception(self, mock_cache, mock_firestore_service):
        """Test excepció durant l'afegició de participant"""
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.side_effect = Exception("Add error")
        
        dao = RenovationDAO()
        success, error_code = dao.add_participant('test_id', 'participant_uid')
        
        assert success is False
        assert error_code is None
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_remove_participant_renovation_not_found(self, mock_cache, mock_firestore_service):
        """Test eliminar participant de renovation no existent"""
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc = MagicMock()
        mock_doc.exists = False
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = RenovationDAO()
        result = dao.remove_participant('nonexistent_id', 'participant_uid')
        
        assert result is False
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_remove_participant_exception(self, mock_cache, mock_firestore_service):
        """Test excepció durant l'eliminació de participant"""
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.side_effect = Exception("Remove error")
        
        dao = RenovationDAO()
        result = dao.remove_participant('test_id', 'participant_uid')
        
        assert result is False
