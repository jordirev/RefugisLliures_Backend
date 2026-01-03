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
        mock_cache.generate_key.return_value = 'test_cache_key'
        mock_cache.get_timeout.return_value = 300
        mock_cache.get_or_fetch_list.return_value = [sample_renovation_data]
        
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
        mock_cache.get_or_fetch_list.return_value = [sample_renovation_data]
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
        mock_cache.generate_key.return_value = 'test_cache_key'
        mock_cache.get_timeout.return_value = 300
        mock_cache.get_or_fetch_list.return_value = [sample_renovation_data]
        
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
        mock_cache.generate_key.return_value = 'test_cache_key'
        mock_cache.get_timeout.return_value = 300
        mock_cache.get_or_fetch_list.return_value = [sample_renovation_data]
        
        dao = RenovationDAO()
        result = dao.get_renovations_by_refuge('test_refuge_id', active_only=True)
        
        assert isinstance(result, list)
        assert len(result) == 1
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_get_renovations_by_refuge_from_cache(self, mock_cache, mock_firestore_service, sample_renovation_data):
        """Test obtenció de renovations per refugi des de cache"""
        mock_cache.get_or_fetch_list.return_value = [sample_renovation_data]
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

    # ===== TESTS ADICIONALS PER MILLORAR COVERAGE =====

    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    @patch('api.daos.renovation_dao.get_madrid_today')
    def test_get_all_renovations_fetch_all_internal(self, mock_get_today, mock_cache, mock_firestore_service, sample_renovation_data):
        """Test obtenció de renovations amb funcions internes executades"""
        mock_today = date.today()
        mock_get_today.return_value = mock_today
        
        mock_cache.generate_key.return_value = 'test_cache_key'
        mock_cache.get_timeout.return_value = 300
        
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        # Simular document de Firestore
        mock_doc = MagicMock()
        mock_doc.id = 'test_renovation_id'
        mock_doc.to_dict.return_value = sample_renovation_data
        
        mock_query = MagicMock()
        mock_query.stream.return_value = [mock_doc]
        mock_collection = MagicMock()
        mock_collection.where.return_value.order_by.return_value = mock_query
        mock_db.collection.return_value = mock_collection
        
        # Capturar funcions internes
        captured_funcs = {}
        def capture_and_execute(**kwargs):
            captured_funcs['fetch_all'] = kwargs.get('fetch_all_fn')
            captured_funcs['fetch_single'] = kwargs.get('fetch_single_fn')
            captured_funcs['get_id'] = kwargs.get('get_id_fn')
            # Executar fetch_all per cobrir línies 126-141
            return captured_funcs['fetch_all']()
        
        mock_cache.get_or_fetch_list.side_effect = capture_and_execute
        
        dao = RenovationDAO()
        result = dao.get_all_renovations()
        
        assert len(result) == 1
        assert 'fetch_all' in captured_funcs

    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    @patch('api.daos.renovation_dao.get_madrid_today')
    def test_get_all_renovations_fetch_single_internal(self, mock_get_today, mock_cache, mock_firestore_service, sample_renovation_data):
        """Test obtenció de renovation individual amb fetch_single"""
        mock_today = date.today()
        mock_get_today.return_value = mock_today
        
        mock_cache.generate_key.return_value = 'test_cache_key'
        mock_cache.get_timeout.return_value = 300
        
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        # Simular document individual de Firestore
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.id = 'test_renovation_id'
        mock_doc.to_dict.return_value = sample_renovation_data
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        # Capturar funcions internes
        captured_funcs = {}
        def capture_and_execute(**kwargs):
            captured_funcs['fetch_all'] = kwargs.get('fetch_all_fn')
            captured_funcs['fetch_single'] = kwargs.get('fetch_single_fn')
            captured_funcs['get_id'] = kwargs.get('get_id_fn')
            # Executar fetch_single per cobrir línies 145-153
            result = captured_funcs['fetch_single']('test_renovation_id')
            return [result] if result else []
        
        mock_cache.get_or_fetch_list.side_effect = capture_and_execute
        
        dao = RenovationDAO()
        result = dao.get_all_renovations()
        
        assert len(result) == 1

    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    @patch('api.daos.renovation_dao.get_madrid_today')
    def test_get_all_renovations_fetch_single_not_found(self, mock_get_today, mock_cache, mock_firestore_service):
        """Test fetch_single retorna None quan no troba document"""
        mock_today = date.today()
        mock_get_today.return_value = mock_today
        
        mock_cache.generate_key.return_value = 'test_cache_key'
        mock_cache.get_timeout.return_value = 300
        
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        # Simular document que no existeix
        mock_doc = MagicMock()
        mock_doc.exists = False
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        # Capturar funcions internes
        captured_funcs = {}
        def capture_and_execute(**kwargs):
            captured_funcs['fetch_single'] = kwargs.get('fetch_single_fn')
            # Executar fetch_single amb document no existent
            result = captured_funcs['fetch_single']('nonexistent_id')
            return [] if result is None else [result]
        
        mock_cache.get_or_fetch_list.side_effect = capture_and_execute
        
        dao = RenovationDAO()
        result = dao.get_all_renovations()
        
        assert result == []

    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    @patch('api.daos.renovation_dao.get_madrid_today')
    def test_get_all_renovations_exception(self, mock_get_today, mock_cache, mock_firestore_service):
        """Test excepció durant l'obtenció de renovations"""
        mock_today = date.today()
        mock_get_today.return_value = mock_today
        mock_cache.generate_key.return_value = 'test_cache_key'
        mock_cache.get_or_fetch_list.side_effect = Exception("Cache error")
        
        dao = RenovationDAO()
        result = dao.get_all_renovations()
        
        assert result == []

    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    @patch('api.daos.renovation_dao.get_madrid_today')
    def test_delete_current_renovations_by_creator_success(self, mock_get_today, mock_cache, mock_firestore_service, sample_renovation_data):
        """Test eliminació de renovations actuals per creador"""
        mock_today = date.today()
        mock_get_today.return_value = mock_today
        
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        # Simular una renovation amb participants
        mock_doc = MagicMock()
        mock_doc.id = 'test_renovation_id'
        mock_doc.to_dict.return_value = {
            'refuge_id': 'refuge_1',
            'participants_uids': ['user1', 'user2']
        }
        mock_doc.reference = MagicMock()
        
        mock_query = MagicMock()
        mock_query.stream.return_value = [mock_doc]
        mock_collection = MagicMock()
        mock_collection.where.return_value.where.return_value = mock_query
        mock_db.collection.return_value = mock_collection
        
        mock_cache.generate_key.return_value = 'test_cache_key'
        
        dao = RenovationDAO()
        success, participants, error = dao.delete_current_renovations_by_creator('test_creator')
        
        assert success is True
        assert error is None
        assert 'user1' in participants
        assert 'user2' in participants
        mock_doc.reference.delete.assert_called_once()

    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    @patch('api.daos.renovation_dao.get_madrid_today')
    def test_delete_current_renovations_by_creator_exception(self, mock_get_today, mock_cache, mock_firestore_service):
        """Test excepció durant l'eliminació de renovations actuals"""
        mock_today = date.today()
        mock_get_today.return_value = mock_today
        
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.side_effect = Exception("Database error")
        
        dao = RenovationDAO()
        success, participants, error = dao.delete_current_renovations_by_creator('test_creator')
        
        assert success is False
        assert participants is None
        assert 'Database error' in error

    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_anonymize_renovations_by_creator_success(self, mock_cache, mock_firestore_service):
        """Test anonimització de renovations per creador"""
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc = MagicMock()
        mock_doc.id = 'test_renovation_id'
        mock_doc.to_dict.return_value = {'refuge_id': 'refuge_1'}
        mock_doc.reference = MagicMock()
        
        mock_query = MagicMock()
        mock_query.stream.return_value = [mock_doc]
        mock_collection = MagicMock()
        mock_collection.where.return_value = mock_query
        mock_db.collection.return_value = mock_collection
        
        mock_cache.generate_key.return_value = 'test_cache_key'
        
        dao = RenovationDAO()
        success, error = dao.anonymize_renovations_by_creator('test_creator')
        
        assert success is True
        assert error is None
        mock_doc.reference.update.assert_called_once_with({
            'creator_uid': 'unknown',
            'group_link': None
        })

    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_anonymize_renovations_by_creator_exception(self, mock_cache, mock_firestore_service):
        """Test excepció durant l'anonimització de renovations"""
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.side_effect = Exception("Database error")
        
        dao = RenovationDAO()
        success, error = dao.anonymize_renovations_by_creator('test_creator')
        
        assert success is False
        assert 'Database error' in error

    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_remove_user_from_participations_success(self, mock_cache, mock_firestore_service):
        """Test eliminació d'usuari de participacions"""
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc = MagicMock()
        mock_doc.id = 'test_renovation_id'
        mock_doc.to_dict.return_value = {'refuge_id': 'refuge_1'}
        mock_doc.reference = MagicMock()
        
        mock_query = MagicMock()
        mock_query.stream.return_value = [mock_doc]
        mock_collection = MagicMock()
        mock_collection.where.return_value = mock_query
        mock_db.collection.return_value = mock_collection
        
        mock_cache.generate_key.return_value = 'test_cache_key'
        
        dao = RenovationDAO()
        success, error = dao.remove_user_from_participations('user_uid')
        
        assert success is True
        assert error is None
        mock_doc.reference.update.assert_called_once()

    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_remove_user_from_participations_exception(self, mock_cache, mock_firestore_service):
        """Test excepció durant l'eliminació d'usuari de participacions"""
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.side_effect = Exception("Database error")
        
        dao = RenovationDAO()
        success, error = dao.remove_user_from_participations('user_uid')
        
        assert success is False
        assert 'Database error' in error

    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_remove_user_from_expelled_success(self, mock_cache, mock_firestore_service):
        """Test eliminació d'usuari de expelled_uids"""
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc = MagicMock()
        mock_doc.id = 'test_renovation_id'
        mock_doc.to_dict.return_value = {'refuge_id': 'refuge_1'}
        mock_doc.reference = MagicMock()
        
        mock_query = MagicMock()
        mock_query.stream.return_value = [mock_doc]
        mock_collection = MagicMock()
        mock_collection.where.return_value = mock_query
        mock_db.collection.return_value = mock_collection
        
        mock_cache.generate_key.return_value = 'test_cache_key'
        
        dao = RenovationDAO()
        success, error = dao.remove_user_from_expelled('user_uid')
        
        assert success is True
        assert error is None
        mock_doc.reference.update.assert_called_once()

    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_remove_user_from_expelled_exception(self, mock_cache, mock_firestore_service):
        """Test excepció durant l'eliminació d'usuari de expelled"""
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.side_effect = Exception("Database error")
        
        dao = RenovationDAO()
        success, error = dao.remove_user_from_expelled('user_uid')
        
        assert success is False
        assert 'Database error' in error

    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    @patch('api.daos.renovation_dao.get_madrid_today')
    def test_get_all_renovations_get_id_function(self, mock_get_today, mock_cache, mock_firestore_service, sample_renovation_data):
        """Test que verifica la funció get_id de get_all_renovations"""
        mock_today = date.today()
        mock_get_today.return_value = mock_today
        
        mock_cache.generate_key.return_value = 'test_cache_key'
        mock_cache.get_timeout.return_value = 300
        
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        # Simular get_or_fetch_list per capturar les funcions internes
        captured_funcs = {}
        def capture_funcs(**kwargs):
            captured_funcs['fetch_all'] = kwargs.get('fetch_all_fn')
            captured_funcs['fetch_single'] = kwargs.get('fetch_single_fn')
            captured_funcs['get_id'] = kwargs.get('get_id_fn')
            return [sample_renovation_data]
        
        mock_cache.get_or_fetch_list.side_effect = capture_funcs
        
        dao = RenovationDAO()
        result = dao.get_all_renovations()
        
        assert len(result) == 1
        assert 'fetch_all' in captured_funcs
        assert 'fetch_single' in captured_funcs
        assert 'get_id' in captured_funcs
        
        # Testejar get_id (línia 157)
        test_data = {'id': 'test_123'}
        assert captured_funcs['get_id'](test_data) == 'test_123'

    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    @patch('api.daos.renovation_dao.get_madrid_today')
    def test_get_renovations_by_refuge_internal_functions(self, mock_get_today, mock_cache, mock_firestore_service, sample_renovation_data):
        """Test que verifica les funcions internes de get_renovations_by_refuge"""
        mock_today = date.today()
        mock_get_today.return_value = mock_today
        
        mock_cache.generate_key.return_value = 'test_cache_key'
        mock_cache.get_timeout.return_value = 300
        
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        # Simular get_or_fetch_list per capturar les funcions internes
        captured_funcs = {}
        def capture_funcs(**kwargs):
            captured_funcs['fetch_all'] = kwargs.get('fetch_all_fn')
            captured_funcs['fetch_single'] = kwargs.get('fetch_single_fn')
            captured_funcs['get_id'] = kwargs.get('get_id_fn')
            return [sample_renovation_data]
        
        mock_cache.get_or_fetch_list.side_effect = capture_funcs
        
        dao = RenovationDAO()
        result = dao.get_renovations_by_refuge('test_refuge_id', active_only=True)
        
        assert len(result) == 1
        assert 'fetch_all' in captured_funcs

        # Testejar get_id
        test_data = {'id': 'test_456'}
        assert captured_funcs['get_id'](test_data) == 'test_456'

    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_update_renovation_date_normalization(self, mock_cache, mock_firestore_service, sample_renovation_data):
        """Test normalització de dates durant update_renovation"""
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {'refuge_id': 'test_refuge'}
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        mock_cache.generate_key.return_value = 'test_cache_key'
        
        dao = RenovationDAO()
        
        # Test amb datetime objects
        update_data = {
            'ini_date': datetime(2024, 6, 15, 10, 30),
            'fin_date': datetime(2024, 6, 20, 15, 45)
        }
        
        result = dao.update_renovation('test_id', update_data)
        
        assert result is True
        mock_doc_ref.update.assert_called_once()

    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_update_renovation_with_date_objects(self, mock_cache, mock_firestore_service):
        """Test update_renovation amb objectes date"""
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {'refuge_id': 'test_refuge'}
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        mock_cache.generate_key.return_value = 'test_cache_key'
        
        dao = RenovationDAO()
        
        # Test amb date objects
        update_data = {
            'ini_date': date(2024, 6, 15),
            'fin_date': date(2024, 6, 20)
        }
        
        result = dao.update_renovation('test_id', update_data)
        
        assert result is True
