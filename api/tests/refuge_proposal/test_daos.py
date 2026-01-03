"""
Tests per al DAO de propostes de refugi
"""
import pytest
from unittest.mock import MagicMock, patch, call
from api.daos.refuge_proposal_dao import RefugeProposalDAO, CreateRefugeStrategy, UpdateRefugeStrategy, DeleteRefugeStrategy
from api.models.refuge_proposal import RefugeProposal

@pytest.mark.daos
class TestRefugeProposalDAO:
    """Tests per a RefugeProposalDAO"""
    
    @pytest.fixture
    def mock_firestore_class(self):
        with patch('api.daos.refuge_proposal_dao.firestore_service') as mock:
            yield mock

    @pytest.fixture
    def mock_db(self, mock_firestore_class):
        mock_db = MagicMock()
        mock_firestore_class.get_db.return_value = mock_db
        return mock_db

    @pytest.fixture
    def mock_cache(self):
        with patch('api.daos.refuge_proposal_dao.cache_service') as mock:
            yield mock

    @pytest.fixture
    def dao(self, mock_firestore_class, mock_cache):
        return RefugeProposalDAO()
    
    def test_create_proposal_success(self, dao, mock_db, mock_cache):
        """Test creació de proposta exitosa"""
        mock_doc_ref = MagicMock()
        mock_doc_ref.id = "prop_123"
        mock_db.collection.return_value.document.return_value = mock_doc_ref
        
        with patch('api.daos.refuge_proposal_dao.get_madrid_now') as mock_now:
            mock_now.return_value.isoformat.return_value = "2024-01-01"
            
            proposal_data = {
                'action': 'create',
                'payload': {'name': 'New'},
                'comment': 'Test'
            }
            
            result = dao.create(proposal_data, "user_1")
            
            assert result is not None
            assert result.id == "prop_123"
            mock_doc_ref.set.assert_called()
            mock_cache.delete_pattern.assert_called_with('proposal_list:')

    def test_get_by_id_found(self, dao, mock_db, mock_cache):
        """Test obtenció de proposta existent"""
        mock_cache.get.return_value = None
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {'id': 'prop_1', 'status': 'pending'}
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        
        result = dao.get_by_id("prop_1")
        
        assert result is not None
        assert result.id == 'prop_1'

    @patch('api.daos.refuge_proposal_dao.ProposalStrategySelector.get_strategy')
    def test_approve_success(self, mock_get_strategy, dao, mock_db, mock_cache):
        """Test aprovació de proposta exitosa"""
        mock_proposal = MagicMock(spec=RefugeProposal, id="prop_1", status="pending", action="create")
        
        with patch.object(dao, 'get_by_id', return_value=mock_proposal):
            mock_strategy = MagicMock()
            mock_strategy.execute.return_value = (True, None)
            mock_get_strategy.return_value = mock_strategy
            
            with patch('api.daos.refuge_proposal_dao.get_madrid_now') as mock_now:
                mock_now.return_value.isoformat.return_value = "2024-01-02"
                
                success, error = dao.approve("prop_1", "admin_1")
                
                assert success is True
                assert error is None
                mock_strategy.execute.assert_called()
                mock_db.collection.return_value.document.return_value.update.assert_called()

    def test_reject_success(self, dao, mock_db, mock_cache):
        """Test rebuig de proposta exitosa"""
        mock_proposal = MagicMock(spec=RefugeProposal, id="prop_1", status="pending")
        
        with patch.object(dao, 'get_by_id', return_value=mock_proposal):
            with patch('api.daos.refuge_proposal_dao.get_madrid_now') as mock_now:
                mock_now.return_value.isoformat.return_value = "2024-01-02"
                
                success, error = dao.reject("prop_1", "admin_1", "Reason")
                
                assert success is True
                assert error is None
                mock_db.collection.return_value.document.return_value.update.assert_called()

@pytest.mark.daos
class TestProposalStrategies:
    """Tests per a les estratègies d'aprovació"""
    
    def test_create_refuge_strategy_execute(self):
        """Test execució d'estratègia de creació"""
        strategy = CreateRefugeStrategy()
        mock_db = MagicMock()
        mock_proposal = MagicMock(spec=RefugeProposal, id="prop_1", action="create", created_at="2024-01-01", payload={'name': 'New', 'coord': {'lat': 0, 'long': 0}})
        
        with patch('api.daos.refuge_proposal_dao.RefugiLliureMapper.model_to_firestore', return_value={}):
            with patch('api.daos.refuge_proposal_dao.add_refuge_to_coords_refugis'):
                success, error = strategy.execute(mock_proposal, mock_db)
                assert success is True
                mock_db.collection.return_value.document.return_value.set.assert_called()
