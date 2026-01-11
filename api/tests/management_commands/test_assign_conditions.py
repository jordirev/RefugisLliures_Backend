"""
Tests unitaris per al management command assign_conditions
"""
import pytest
from unittest.mock import MagicMock, patch
from io import StringIO
from api.management.commands.assign_conditions import Command as AssignConditionsCommand


# ============= FIXTURES =============

@pytest.fixture
def mock_firestore_db():
    """Mock del client Firestore"""
    mock_db = MagicMock()
    mock_collection = MagicMock()
    mock_doc = MagicMock()
    
    mock_db.collection.return_value = mock_collection
    mock_collection.document.return_value = mock_doc
    mock_collection.stream.return_value = []
    mock_db.batch.return_value = MagicMock()
    
    return mock_db


@pytest.fixture
def sample_refugi_with_info_comp():
    """Refugi amb info_comp complet"""
    return {
        'id': 'refugi1',
        'name': 'Refugi Test',
        'info_comp': {
            'cheminee': 1,
            'poele': 1,
            'couvertures': 1,
            'latrines': 1,
            'bois': 1,
            'eau': 1,
            'matelas': 1,
            'couchage': 1,
            'bas_flancs': 0,
            'lits': 0,
            'mezzanine_etage': 0,
            'manque_un_mur': 0
        }
    }


@pytest.fixture
def sample_refugi_with_missing_wall():
    """Refugi amb un mur que falta"""
    return {
        'id': 'refugi2',
        'name': 'Refugi Mur',
        'info_comp': {
            'cheminee': 1,
            'manque_un_mur': 1
        }
    }


@pytest.fixture
def sample_refugi_without_info_comp():
    """Refugi sense info_comp"""
    return {
        'id': 'refugi3',
        'name': 'Refugi Sin Info'
    }


@pytest.fixture
def sample_refugi_with_condition():
    """Refugi que ja té condition assignada"""
    return {
        'id': 'refugi4',
        'name': 'Refugi Amb Condition',
        'condition': 2.0,
        'num_contributed_conditions': 1,
        'info_comp': {
            'cheminee': 1,
            'poele': 1,
            'couvertures': 1
        }
    }


# ============= TESTS =============

class TestAssignConditions:
    """Tests per al command assign_conditions"""
    
    def test_determine_condition_excellent(self):
        """Test: Determinar condició excel·lent (7+ comoditats)"""
        # Arrange
        command = AssignConditionsCommand()
        info_comp = {
            'cheminee': 1,
            'poele': 1,
            'couvertures': 1,
            'latrines': 1,
            'bois': 1,
            'eau': 1,
            'matelas': 1,
            'couchage': 1,
            'manque_un_mur': 0
        }
        
        # Act
        condition = command.determine_condition(info_comp)
        
        # Assert
        assert condition == 3
    
    def test_determine_condition_good(self):
        """Test: Determinar condició bona (5-6 comoditats)"""
        # Arrange
        command = AssignConditionsCommand()
        info_comp = {
            'cheminee': 1,
            'poele': 1,
            'couvertures': 1,
            'latrines': 1,
            'bois': 1,
            'eau': 0,
            'manque_un_mur': 0
        }
        
        # Act
        condition = command.determine_condition(info_comp)
        
        # Assert
        assert condition == 2
    
    def test_determine_condition_fair(self):
        """Test: Determinar condició correcta (3-4 comoditats)"""
        # Arrange
        command = AssignConditionsCommand()
        info_comp = {
            'cheminee': 1,
            'poele': 1,
            'couvertures': 1,
            'latrines': 0,
            'manque_un_mur': 0
        }
        
        # Act
        condition = command.determine_condition(info_comp)
        
        # Assert
        assert condition == 1
    
    def test_determine_condition_poor(self):
        """Test: Determinar condició pobra (0-2 comoditats)"""
        # Arrange
        command = AssignConditionsCommand()
        info_comp = {
            'cheminee': 1,
            'poele': 0,
            'manque_un_mur': 0
        }
        
        # Act
        condition = command.determine_condition(info_comp)
        
        # Assert
        assert condition == 0
    
    def test_determine_condition_missing_wall(self):
        """Test: Determinar condició amb mur que falta (sempre 0)"""
        # Arrange
        command = AssignConditionsCommand()
        info_comp = {
            'cheminee': 1,
            'poele': 1,
            'couvertures': 1,
            'latrines': 1,
            'bois': 1,
            'eau': 1,
            'matelas': 1,
            'couchage': 1,
            'manque_un_mur': 1  # Mur que falta
        }
        
        # Act
        condition = command.determine_condition(info_comp)
        
        # Assert
        assert condition == 0
    
    def test_determine_condition_no_info_comp(self):
        """Test: Determinar condició sense info_comp"""
        # Arrange
        command = AssignConditionsCommand()
        
        # Act
        condition = command.determine_condition(None)
        
        # Assert
        assert condition is None
    
    def test_determine_condition_empty_info_comp(self):
        """Test: Determinar condició amb info_comp buit"""
        # Arrange
        command = AssignConditionsCommand()
        
        # Act
        condition = command.determine_condition({})
        
        # Assert
        # Empty info_comp is treated as None (no info available)
        assert condition is None
    
    @patch('api.management.commands.assign_conditions.credentials')
    @patch('api.management.commands.assign_conditions.firebase_admin')
    @patch('api.management.commands.assign_conditions.firestore')
    @patch('api.management.commands.assign_conditions.ConditionService')
    @patch('os.path.exists')
    def test_assign_success(self, mock_exists, mock_condition_service, mock_firestore, 
                           mock_firebase, mock_credentials, mock_firestore_db, 
                           sample_refugi_with_info_comp):
        """Test: Assignació exitosa de conditions"""
        # Arrange
        mock_exists.return_value = True
        mock_firebase.get_app.side_effect = ValueError
        mock_credentials.Certificate.return_value = MagicMock()
        mock_firestore.client.return_value = mock_firestore_db
        mock_condition_service.initialize_condition.return_value = {
            'condition': 3.0,
            'num_contributed_conditions': 1
        }
        
        mock_doc = MagicMock()
        mock_doc.id = sample_refugi_with_info_comp['id']
        mock_doc.to_dict.return_value = sample_refugi_with_info_comp
        mock_firestore_db.collection().stream.return_value = [mock_doc]
        
        command = AssignConditionsCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle(
            collection='data_refugis_lliures',
            dry_run=False,
            batch_size=500,
            overwrite=False
        )
        
        # Assert
        output = out.getvalue()
        assert 'Updated refugi1: condition=3.0' in output
        assert 'Total refugis updated: 1' in output
    
    @patch('api.management.commands.assign_conditions.firebase_admin')
    @patch('api.management.commands.assign_conditions.firestore')
    @patch('os.path.exists')
    def test_assign_firebase_credentials_not_found(self, mock_exists, mock_firestore, mock_firebase):
        """Test: Error quan no es troben les credencials"""
        # Arrange
        mock_firebase.get_app.side_effect = ValueError
        mock_exists.return_value = False
        
        command = AssignConditionsCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle(
            collection='data_refugis_lliures',
            dry_run=False,
            batch_size=500,
            overwrite=False
        )
        
        # Assert
        output = out.getvalue()
        assert 'Credentials file not found' in output
    
    @patch('api.management.commands.assign_conditions.firebase_admin')
    @patch('api.management.commands.assign_conditions.firestore')
    @patch('api.management.commands.assign_conditions.ConditionService')
    @patch('os.path.exists')
    def test_assign_skip_without_info_comp(self, mock_exists, mock_condition_service, 
                                          mock_firestore, mock_firebase, mock_firestore_db, 
                                          sample_refugi_without_info_comp):
        """Test: Saltar refugis sense info_comp"""
        # Arrange
        mock_exists.return_value = True
        mock_firebase.get_app.return_value = True
        mock_firestore.client.return_value = mock_firestore_db
        
        mock_doc = MagicMock()
        mock_doc.id = sample_refugi_without_info_comp['id']
        mock_doc.to_dict.return_value = sample_refugi_without_info_comp
        mock_firestore_db.collection().stream.return_value = [mock_doc]
        
        command = AssignConditionsCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle(
            collection='data_refugis_lliures',
            dry_run=False,
            batch_size=500,
            overwrite=False
        )
        
        # Assert
        output = out.getvalue()
        assert 'Skipping refugi3 - No info_comp available' in output
        assert 'Refugis skipped (no info_comp): 1' in output
    
    @patch('api.management.commands.assign_conditions.firebase_admin')
    @patch('api.management.commands.assign_conditions.firestore')
    @patch('api.management.commands.assign_conditions.ConditionService')
    @patch('os.path.exists')
    def test_assign_skip_existing_condition(self, mock_exists, mock_condition_service, 
                                           mock_firestore, mock_firebase, mock_firestore_db, 
                                           sample_refugi_with_condition):
        """Test: Saltar refugis que ja tenen condition (sense overwrite)"""
        # Arrange
        mock_exists.return_value = True
        mock_firebase.get_app.return_value = True
        mock_firestore.client.return_value = mock_firestore_db
        
        mock_doc = MagicMock()
        mock_doc.id = sample_refugi_with_condition['id']
        mock_doc.to_dict.return_value = sample_refugi_with_condition
        mock_firestore_db.collection().stream.return_value = [mock_doc]
        
        command = AssignConditionsCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle(
            collection='data_refugis_lliures',
            dry_run=False,
            batch_size=500,
            overwrite=False
        )
        
        # Assert
        output = out.getvalue()
        assert 'Skipping refugi4 - Already has condition: 2.0' in output
        assert 'Refugis skipped (already have condition): 1' in output
    
    @patch('api.management.commands.assign_conditions.firebase_admin')
    @patch('api.management.commands.assign_conditions.firestore')
    @patch('api.management.commands.assign_conditions.ConditionService')
    @patch('os.path.exists')
    def test_assign_overwrite_existing_condition(self, mock_exists, mock_condition_service, 
                                                 mock_firestore, mock_firebase, mock_firestore_db, 
                                                 sample_refugi_with_condition):
        """Test: Sobreescriure conditions existents amb --overwrite"""
        # Arrange
        mock_exists.return_value = True
        mock_firebase.get_app.return_value = True
        mock_firestore.client.return_value = mock_firestore_db
        mock_condition_service.initialize_condition.return_value = {
            'condition': 1.0,
            'num_contributed_conditions': 1
        }
        
        mock_doc = MagicMock()
        mock_doc.id = sample_refugi_with_condition['id']
        mock_doc.to_dict.return_value = sample_refugi_with_condition
        mock_firestore_db.collection().stream.return_value = [mock_doc]
        
        command = AssignConditionsCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle(
            collection='data_refugis_lliures',
            dry_run=False,
            batch_size=500,
            overwrite=True
        )
        
        # Assert
        output = out.getvalue()
        assert 'Updated refugi4: condition=1.0' in output
        assert 'Total refugis updated: 1' in output
    
    @patch('api.management.commands.assign_conditions.firebase_admin')
    @patch('api.management.commands.assign_conditions.firestore')
    @patch('api.management.commands.assign_conditions.ConditionService')
    @patch('os.path.exists')
    def test_assign_dry_run(self, mock_exists, mock_condition_service, mock_firestore, 
                           mock_firebase, mock_firestore_db, sample_refugi_with_info_comp):
        """Test: Mode dry-run (no assigna res)"""
        # Arrange
        mock_exists.return_value = True
        mock_firebase.get_app.return_value = True
        mock_firestore.client.return_value = mock_firestore_db
        mock_condition_service.initialize_condition.return_value = {
            'condition': 3.0,
            'num_contributed_conditions': 1
        }
        
        mock_doc = MagicMock()
        mock_doc.id = sample_refugi_with_info_comp['id']
        mock_doc.to_dict.return_value = sample_refugi_with_info_comp
        mock_firestore_db.collection().stream.return_value = [mock_doc]
        
        mock_batch = MagicMock()
        mock_firestore_db.batch.return_value = mock_batch
        
        command = AssignConditionsCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle(
            collection='data_refugis_lliures',
            dry_run=True,
            batch_size=500,
            overwrite=False
        )
        
        # Assert
        output = out.getvalue()
        assert 'DRY RUN MODE' in output
        assert 'Would update refugi1: condition=3.0' in output
        assert 'This was a DRY RUN' in output
        
        # Verify no batch commits
        assert not mock_batch.commit.called
    
    @patch('api.management.commands.assign_conditions.firebase_admin')
    @patch('api.management.commands.assign_conditions.firestore')
    @patch('api.management.commands.assign_conditions.ConditionService')
    @patch('os.path.exists')
    def test_assign_batch_processing(self, mock_exists, mock_condition_service, 
                                     mock_firestore, mock_firebase, mock_firestore_db):
        """Test: Processament per batches"""
        # Arrange
        mock_exists.return_value = True
        mock_firebase.get_app.return_value = True
        mock_firestore.client.return_value = mock_firestore_db
        mock_condition_service.initialize_condition.return_value = {
            'condition': 2.0,
            'num_contributed_conditions': 1
        }
        
        # Create 3 documents (batch_size=2)
        mock_docs = []
        for i in range(3):
            mock_doc = MagicMock()
            mock_doc.id = f'refugi{i}'
            mock_doc.to_dict.return_value = {
                'id': f'refugi{i}',
                'name': f'Refugi {i}',
                'info_comp': {'cheminee': 1, 'poele': 1, 'couvertures': 1}
            }
            mock_docs.append(mock_doc)
        
        mock_firestore_db.collection().stream.return_value = mock_docs
        
        mock_batch = MagicMock()
        mock_firestore_db.batch.return_value = mock_batch
        
        command = AssignConditionsCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle(
            collection='data_refugis_lliures',
            dry_run=False,
            batch_size=2,
            overwrite=False
        )
        
        # Assert
        output = out.getvalue()
        assert 'Committed batch of 2 updates' in output
        assert 'Committed final batch of 1 updates' in output
        assert mock_batch.commit.call_count == 2
    
    @patch('api.management.commands.assign_conditions.firebase_admin')
    @patch('api.management.commands.assign_conditions.firestore')
    @patch('api.management.commands.assign_conditions.ConditionService')
    @patch('os.path.exists')
    def test_assign_with_errors(self, mock_exists, mock_condition_service, 
                               mock_firestore, mock_firebase, mock_firestore_db):
        """Test: Gestió d'errors durant l'assignació"""
        # Arrange
        mock_exists.return_value = True
        mock_firebase.get_app.return_value = True
        mock_firestore.client.return_value = mock_firestore_db
        mock_condition_service.initialize_condition.return_value = {
            'condition': 2.0,
            'num_contributed_conditions': 1
        }
        
        # First doc OK, second raises exception
        mock_doc1 = MagicMock()
        mock_doc1.id = 'refugi1'
        mock_doc1.to_dict.return_value = {
            'id': 'refugi1',
            'info_comp': {'cheminee': 1}
        }
        
        mock_doc2 = MagicMock()
        mock_doc2.id = 'refugi2'
        mock_doc2.to_dict.side_effect = Exception("Firestore error")
        
        mock_firestore_db.collection().stream.return_value = [mock_doc1, mock_doc2]
        
        command = AssignConditionsCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle(
            collection='data_refugis_lliures',
            dry_run=False,
            batch_size=500,
            overwrite=False
        )
        
        # Assert
        output = out.getvalue()
        assert 'Updated refugi1' in output
        assert 'Error processing refugi2' in output
        assert 'Errors: 1' in output
    
    @patch('api.management.commands.assign_conditions.firebase_admin')
    @patch('api.management.commands.assign_conditions.firestore')
    @patch('os.path.exists')
    def test_assign_custom_collection(self, mock_exists, mock_firestore, 
                                      mock_firebase, mock_firestore_db):
        """Test: Usar col·lecció personalitzada"""
        # Arrange
        mock_exists.return_value = True
        mock_firebase.get_app.return_value = True
        mock_firestore.client.return_value = mock_firestore_db
        mock_firestore_db.collection().stream.return_value = []
        
        command = AssignConditionsCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle(
            collection='custom_collection',
            dry_run=False,
            batch_size=500,
            overwrite=False
        )
        
        # Assert
        mock_firestore_db.collection.assert_called_with('custom_collection')
