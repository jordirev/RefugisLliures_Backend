"""
Tests extensos per a RefugeProposalDAO i les seves estratègies
"""
import pytest
from unittest.mock import MagicMock, patch, call
from datetime import datetime
from api.daos.refuge_proposal_dao import (
    generate_simple_geohash, add_refuge_to_coords_refugis,
    update_refuge_from_coords_refugis, delete_refuge_from_coords_refugis,
    CreateRefugeStrategy, UpdateRefugeStrategy, DeleteRefugeStrategy,
    ProposalStrategySelector, RefugeProposalDAO
)
from api.models.refuge_proposal import RefugeProposal

class TestRefugeProposalDAOExtended:
    """Tests per a les funcions auxiliars i estratègies de RefugeProposalDAO"""

    def test_generate_simple_geohash(self):
        """Test la generació de geohash"""
        # Prova amb coordenades conegudes
        gh = generate_simple_geohash(41.3851, 2.1734, precision=5)
        assert len(gh) == 5
        assert isinstance(gh, str)
        
        # Mateixes coordenades, mateix geohash
        assert generate_simple_geohash(41.3851, 2.1734, 5) == gh

    def test_add_refuge_to_coords_refugis(self):
        """Test add_refuge_to_coords_refugis"""
        db = MagicMock()
        ref_id = "ref_1"
        ref_data = {'name': 'Refugi 1', 'coord': {'lat': 41.0, 'long': 2.0}, 'surname': 'S1'}
        
        # Cas document existeix
        mock_doc = db.collection.return_value.document.return_value.get.return_value
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {'refugis_coordinates': []}
        
        add_refuge_to_coords_refugis(db, ref_id, ref_data)
        db.collection.return_value.document.return_value.update.assert_called_once()
        
        # Cas document no existeix
        db.collection.return_value.document.return_value.update.reset_mock()
        mock_doc.exists = False
        add_refuge_to_coords_refugis(db, ref_id, ref_data)
        db.collection.return_value.document.return_value.set.assert_called_once()

    def test_update_refuge_from_coords_refugis(self):
        """Test update_refuge_from_coords_refugis"""
        db = MagicMock()
        ref_id = "ref_1"
        
        # No cal actualitzar
        update_refuge_from_coords_refugis(db, ref_id, {'other': 'data'})
        db.collection.assert_not_called()
        
        # Document no existeix
        mock_doc = db.collection.return_value.document.return_value.get.return_value
        mock_doc.exists = False
        update_refuge_from_coords_refugis(db, ref_id, {'name': 'New Name'})
        db.collection.return_value.document.return_value.update.assert_not_called()
        
        # Document existeix i s'actualitza
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            'refugis_coordinates': [
                {'id': 'ref_1', 'name': 'Old Name', 'coord': {'lat': 40, 'long': 1}, 'surname': 'Old'}
            ]
        }
        update_refuge_from_coords_refugis(db, ref_id, {'name': 'New Name', 'coord': {'lat': 41, 'long': 2}, 'surname': None})
        db.collection.return_value.document.return_value.update.assert_called_once()

    def test_delete_refuge_from_coords_refugis(self):
        """Test delete_refuge_from_coords_refugis"""
        db = MagicMock()
        ref_id = "ref_1"
        
        # Document no existeix
        mock_doc = db.collection.return_value.document.return_value.get.return_value
        mock_doc.exists = False
        delete_refuge_from_coords_refugis(db, ref_id)
        db.collection.return_value.document.return_value.update.assert_not_called()
        
        # Document existeix i s'elimina
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            'refugis_coordinates': [{'id': 'ref_1'}, {'id': 'ref_2'}]
        }
        delete_refuge_from_coords_refugis(db, ref_id)
        db.collection.return_value.document.return_value.update.assert_called_once()

    @patch('api.daos.refuge_proposal_dao.RefugiLliureMapper')
    @patch('api.daos.refuge_proposal_dao.add_refuge_to_coords_refugis')
    @patch('api.daos.refuge_proposal_dao.cache_service')
    def test_create_refuge_strategy(self, mock_cache, mock_add_coords, mock_mapper):
        """Test CreateRefugeStrategy"""
        strategy = CreateRefugeStrategy()
        proposal = MagicMock(spec=RefugeProposal)
        proposal.id = "prop_1"
        proposal.created_at = "2024-01-01T12:00:00Z"
        proposal.payload = {
            'name': 'New Refuge',
            'coord': {'lat': 41, 'long': 2},
            'condition': 4.5
        }
        db = MagicMock()
        
        mock_mapper.model_to_firestore.return_value = {'name': 'New Refuge'}
        
        success, error = strategy.execute(proposal, db)
        
        assert success is True
        assert error is None
        db.collection.return_value.document.return_value.set.assert_called_once()
        mock_add_coords.assert_called_once()
        mock_cache.delete_pattern.assert_called()

    @patch('api.daos.refuge_proposal_dao.ConditionService')
    @patch('api.daos.refuge_proposal_dao.update_refuge_from_coords_refugis')
    @patch('api.daos.refuge_proposal_dao.cache_service')
    def test_update_refuge_strategy(self, mock_cache, mock_update_coords, mock_condition):
        """Test UpdateRefugeStrategy"""
        strategy = UpdateRefugeStrategy()
        proposal = MagicMock(spec=RefugeProposal)
        proposal.id = "prop_1"
        proposal.refuge_id = "ref_1"
        proposal.created_at = "2024-01-01T12:00:00Z"
        proposal.payload = {
            'name': 'Updated Name',
            'condition': 5.0,
            'info_comp': {'prop': 'val'}
        }
        db = MagicMock()
        
        # Refuge not found
        mock_doc = db.collection.return_value.document.return_value.get.return_value
        mock_doc.exists = False
        success, error = strategy.execute(proposal, db)
        assert success is False
        assert "not found" in error
        
        # Success
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {'condition': 4.0, 'num_contributed_conditions': 1}
        mock_condition.validate_condition_value.return_value = True
        mock_condition.calculate_condition_average.return_value = {
            'condition': 4.5, 'num_contributed_conditions': 2
        }
        
        success, error = strategy.execute(proposal, db)
        assert success is True
        db.collection.return_value.document.return_value.update.assert_called()

    @patch('api.daos.refuge_proposal_dao.RefugeProposalDAO')
    @patch('api.controllers.doubt_controller.DoubtController')
    @patch('api.controllers.experience_controller.ExperienceController')
    @patch('api.controllers.refugi_lliure_controller.RefugiLliureController')
    @patch('api.controllers.renovation_controller.RenovationController')
    @patch('api.daos.refuge_proposal_dao.delete_refuge_from_coords_refugis')
    @patch('api.daos.refuge_proposal_dao.cache_service')
    def test_delete_refuge_strategy(self, mock_cache, mock_del_coords, 
                                   mock_ren_ctrl_class, mock_ref_ctrl_class,
                                   mock_exp_ctrl_class, mock_doubt_ctrl_class,
                                   mock_prop_dao_class):
        """Test DeleteRefugeStrategy"""
        strategy = DeleteRefugeStrategy()
        proposal = MagicMock(spec=RefugeProposal)
        proposal.id = "prop_1"
        proposal.refuge_id = "ref_1"
        db = MagicMock()
        
        mock_doc = db.collection.return_value.document.return_value.get.return_value
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            'media_metadata': {'m1': {}}
        }
        
        # Mock controllers
        mock_doubt_ctrl = mock_doubt_ctrl_class.return_value
        mock_doubt_ctrl.get_doubts_by_refuge.return_value = ([MagicMock(id='d1')], None)
        mock_doubt_ctrl.delete_doubt.return_value = (True, None)
        
        mock_exp_ctrl = mock_exp_ctrl_class.return_value
        mock_exp_ctrl.get_experiences_by_refuge.return_value = ([MagicMock(id='e1')], None)
        mock_exp_ctrl.delete_experience.return_value = (True, None)
        
        mock_ref_ctrl = mock_ref_ctrl_class.return_value
        mock_ref_ctrl.delete_multiple_refugi_media.return_value = (True, None)
        
        mock_ren_ctrl = mock_ren_ctrl_class.return_value
        mock_ren_ctrl.get_renovations_by_refuge.return_value = (True, [MagicMock(id='r1', creator_uid='u1')], None)
        mock_ren_ctrl.delete_renovation.return_value = (True, None)
        
        mock_prop_dao = mock_prop_dao_class.return_value
        mock_prop_dao.list_all.return_value = [MagicMock(id='p2')]
        mock_prop_dao.reject.return_value = (True, None)
        
        success, error = strategy.execute(proposal, db)
        
        assert success is True
        assert error is None
        db.collection.return_value.document.return_value.delete.assert_called()
        mock_del_coords.assert_called_once()

    def test_proposal_strategy_selector(self):
        """Test ProposalStrategySelector"""
        assert isinstance(ProposalStrategySelector.get_strategy('create'), CreateRefugeStrategy)
        assert isinstance(ProposalStrategySelector.get_strategy('update'), UpdateRefugeStrategy)
        assert isinstance(ProposalStrategySelector.get_strategy('delete'), DeleteRefugeStrategy)
        assert ProposalStrategySelector.get_strategy('invalid') is None

    @patch('api.daos.refuge_proposal_dao.firestore_service')
    @patch('api.daos.refuge_proposal_dao.cache_service')
    def test_refuge_proposal_dao_list_all_with_filters(self, mock_cache, mock_firestore):
        """Test RefugeProposalDAO.list_all amb filtres"""
        dao = RefugeProposalDAO()
        mock_db = mock_firestore.get_db.return_value
        mock_cache.get.return_value = None
        
        # Configurar el mock per a consultes encadenades
        mock_query = MagicMock()
        mock_db.collection.return_value = mock_query
        mock_query.where.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.stream.return_value = []
        
        filters = {'status': 'pending', 'refuge_id': 'ref_1', 'creator_uid': 'user_1'}
        dao.list_all(filters=filters)
        
        # Verifiquem que s'han aplicat els filtres a la query
        assert mock_query.where.call_count == 3
        
    @patch('api.daos.refuge_proposal_dao.firestore_service')
    @patch('api.daos.refuge_proposal_dao.cache_service')
    def test_refuge_proposal_dao_anonymize(self, mock_cache, mock_firestore):
        """Test RefugeProposalDAO.anonymize_proposals_by_creator"""
        dao = RefugeProposalDAO()
        mock_db = mock_firestore.get_db.return_value
        
        # Mock per a la col·lecció i la query
        mock_coll = MagicMock()
        mock_db.collection.return_value = mock_coll
        
        mock_query = MagicMock()
        mock_coll.where.return_value = mock_query
        
        mock_doc = MagicMock()
        mock_doc.id = "prop_1"
        mock_doc.reference = MagicMock()
        mock_query.stream.return_value = [mock_doc]
        
        success, error = dao.anonymize_proposals_by_creator("user_1")
        
        assert success is True
        mock_coll.where.assert_called_with('creator_uid', '==', 'user_1')
        mock_doc.reference.update.assert_called_with({'creator_uid': 'unknown'})
        mock_cache.delete_pattern.assert_called()
        
        # Cas d'error
        mock_coll.where.side_effect = Exception("DB Error")
        success, error = dao.anonymize_proposals_by_creator("user_1")
        assert success is False
        assert "DB Error" in error

    def test_auxiliary_functions_errors(self):
        """Test errors en funcions auxiliars"""
        db = MagicMock()
        
        # add_refuge_to_coords_refugis exception
        db.collection.side_effect = Exception("Error")
        with pytest.raises(Exception):
            add_refuge_to_coords_refugis(db, "id", {})
            
        # update_refuge_from_coords_refugis exception
        db.collection.side_effect = Exception("Error")
        with pytest.raises(Exception):
            update_refuge_from_coords_refugis(db, "id", {'name': 'n'})
            
        # delete_refuge_from_coords_refugis exception
        db.collection.side_effect = Exception("Error")
        with pytest.raises(Exception):
            delete_refuge_from_coords_refugis(db, "id")

    def test_strategies_edge_cases(self):
        """Test casos límit de les estratègies"""
        db = MagicMock()
        
        # CreateRefugeStrategy exception
        strategy = CreateRefugeStrategy()
        proposal = MagicMock()
        proposal.payload = {} # Faltaran camps
        success, error = strategy.execute(proposal, db)
        assert success is False
        
        # UpdateRefugeStrategy missing refuge_id
        strategy = UpdateRefugeStrategy()
        proposal.refuge_id = None
        success, error = strategy.execute(proposal, db)
        assert success is False
        assert "refuge_id is required" in error
        
        # DeleteRefugeStrategy missing refuge_id
        strategy = DeleteRefugeStrategy()
        proposal.refuge_id = None
        success, error = strategy.execute(proposal, db)
        assert success is False
        assert "refuge_id is required" in error
        
        # DeleteRefugeStrategy refuge not found
        proposal.refuge_id = "ref_1"
        db.collection.return_value.document.return_value.get.return_value.exists = False
        success, error = strategy.execute(proposal, db)
        assert success is False
        assert "not found" in error

    @patch('api.daos.refuge_proposal_dao.RefugeProposalDAO.get_by_id')
    @patch('api.daos.refuge_proposal_dao.firestore_service')
    def test_dao_approve_reject_errors(self, mock_firestore, mock_get_by_id):
        """Test errors en approve i reject del DAO"""
        dao = RefugeProposalDAO()
        
        # Proposal not found
        mock_get_by_id.return_value = None
        success, error = dao.approve("p1", "u1")
        assert success is False
        assert "not found" in error
        
        success, error = dao.reject("p1", "u1")
        assert success is False
        assert "not found" in error
        
        # Already approved
        mock_proposal = MagicMock()
        mock_proposal.status = 'approved'
        mock_get_by_id.return_value = mock_proposal
        success, error = dao.approve("p1", "u1")
        assert success is False
        
        success, error = dao.reject("p1", "u1")
        assert success is False

    @patch('api.daos.refuge_proposal_dao.RefugeProposalDAO')
    @patch('api.controllers.doubt_controller.DoubtController')
    @patch('api.controllers.experience_controller.ExperienceController')
    @patch('api.controllers.refugi_lliure_controller.RefugiLliureController')
    @patch('api.controllers.renovation_controller.RenovationController')
    def test_delete_refuge_strategy_exceptions(self, mock_ren_ctrl_class, mock_ref_ctrl_class,
                                             mock_exp_ctrl_class, mock_doubt_ctrl_class,
                                             mock_prop_dao_class):
        """Test excepcions en els passos de DeleteRefugeStrategy"""
        strategy = DeleteRefugeStrategy()
        proposal = MagicMock(spec=RefugeProposal)
        proposal.id = "prop_1"
        proposal.refuge_id = "ref_1"
        db = MagicMock()
        
        mock_doc = db.collection.return_value.document.return_value.get.return_value
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {'media_metadata': {'m1': {}}}
        
        # 1. Error en dubtes
        mock_doubt_ctrl = mock_doubt_ctrl_class.return_value
        mock_doubt_ctrl.get_doubts_by_refuge.return_value = (None, "Error")
        success, error = strategy.execute(proposal, db)
        assert success is False
        assert "Error getting doubts" in error
        
        mock_doubt_ctrl.get_doubts_by_refuge.return_value = ([MagicMock(id='d1')], None)
        mock_doubt_ctrl.delete_doubt.return_value = (False, "Delete Error")
        success, error = strategy.execute(proposal, db)
        assert success is False
        assert "Error deleting doubt" in error
        
        # 2. Error en experiències
        mock_doubt_ctrl.delete_doubt.return_value = (True, None)
        mock_exp_ctrl = mock_exp_ctrl_class.return_value
        mock_exp_ctrl.get_experiences_by_refuge.return_value = (None, "Error")
        success, error = strategy.execute(proposal, db)
        assert success is False
        
        # 3. Error en fotos
        mock_exp_ctrl.get_experiences_by_refuge.return_value = ([], None)
        mock_ref_ctrl = mock_ref_ctrl_class.return_value
        mock_ref_ctrl.delete_multiple_refugi_media.return_value = (False, "Media Error")
        success, error = strategy.execute(proposal, db)
        assert success is False
        
        # 4. Error en renovacions
        mock_ref_ctrl.delete_multiple_refugi_media.return_value = (True, None)
        mock_ren_ctrl = mock_ren_ctrl_class.return_value
        mock_ren_ctrl.get_renovations_by_refuge.return_value = (False, None, "Ren Error")
        success, error = strategy.execute(proposal, db)
        assert success is False

    @patch('api.daos.refuge_proposal_dao.firestore_service')
    def test_dao_methods_exceptions(self, mock_firestore):
        """Test excepcions en mètodes del DAO"""
        dao = RefugeProposalDAO()
        mock_db = mock_firestore.get_db.return_value
        mock_db.collection.side_effect = Exception("DB Error")
        
        assert dao.create({}, "u1") is None
        assert dao.get_by_id("p1") is None
        assert dao.list_all() == []
        
        # approve/reject exceptions
        with patch.object(dao, 'get_by_id', side_effect=Exception("Error")):
            success, error = dao.approve("p1", "u1")
            assert success is False
            
            success, error = dao.reject("p1", "u1")
            assert success is False
