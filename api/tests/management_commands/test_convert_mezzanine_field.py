"""
Tests unitaris per al management command convert_mezzanine_field
"""
import pytest
from unittest.mock import MagicMock, patch
from io import StringIO
from api.management.commands.convert_mezzanine_field import Command as ConvertMezzanineCommand


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
def sample_refugi_with_old_field():
    """Refugi amb camp mezzanine/etage"""
    return {
        'id': 'refugi1',
        'name': 'Refugi Test',
        'info_comp': {
            'cheminee': 1,
            'mezzanine/etage': 1
        }
    }


@pytest.fixture
def sample_refugi_without_old_field():
    """Refugi sense camp mezzanine/etage"""
    return {
        'id': 'refugi2',
        'name': 'Refugi Sin Campo',
        'info_comp': {
            'cheminee': 1,
            'poele': 0
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
def sample_refugi_with_new_field():
    """Refugi que ja té el camp nou"""
    return {
        'id': 'refugi4',
        'name': 'Refugi Ya Convertido',
        'info_comp': {
            'cheminee': 1,
            'mezzanine_etage': 1
        }
    }


# ============= TESTS =============

class TestConvertMezzanineField:
    """Tests per al command convert_mezzanine_field"""
    
    @patch('api.management.commands.convert_mezzanine_field.credentials')
    @patch('api.management.commands.convert_mezzanine_field.firebase_admin')
    @patch('api.management.commands.convert_mezzanine_field.firestore')
    @patch('os.path.exists')
    def test_convert_success(self, mock_exists, mock_firestore, mock_firebase, 
                            mock_credentials, mock_firestore_db, sample_refugi_with_old_field):
        """Test: Conversió exitosa del camp"""
        # Arrange
        mock_exists.return_value = True
        mock_firebase.get_app.side_effect = ValueError
        mock_credentials.Certificate.return_value = MagicMock()
        mock_firestore.client.return_value = mock_firestore_db
        
        mock_doc = MagicMock()
        mock_doc.id = sample_refugi_with_old_field['id']
        mock_doc.to_dict.return_value = sample_refugi_with_old_field
        mock_firestore_db.collection().stream.return_value = [mock_doc]
        
        mock_batch = MagicMock()
        mock_firestore_db.batch.return_value = mock_batch
        
        command = ConvertMezzanineCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle(
            collection='data_refugis_lliures',
            dry_run=False,
            batch_size=500
        )
        
        # Assert
        output = out.getvalue()
        assert 'Queued refugi1: mezzanine/etage=1 -> mezzanine_etage=1' in output
        assert 'Documents updated: 1' in output
        assert mock_batch.commit.called
    
    @patch('api.management.commands.convert_mezzanine_field.firebase_admin')
    @patch('api.management.commands.convert_mezzanine_field.firestore')
    @patch('os.path.exists')
    def test_convert_firebase_credentials_not_found(self, mock_exists, mock_firestore, mock_firebase):
        """Test: Error quan no es troben les credencials"""
        # Arrange
        mock_firebase.get_app.side_effect = ValueError
        mock_exists.return_value = False
        
        command = ConvertMezzanineCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle(
            collection='data_refugis_lliures',
            dry_run=False,
            batch_size=500
        )
        
        # Assert
        output = out.getvalue()
        assert 'Firebase credentials file not found' in output
    
    @patch('api.management.commands.convert_mezzanine_field.firebase_admin')
    @patch('api.management.commands.convert_mezzanine_field.firestore')
    @patch('os.path.exists')
    def test_convert_skip_without_info_comp(self, mock_exists, mock_firestore, 
                                           mock_firebase, mock_firestore_db, 
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
        
        command = ConvertMezzanineCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle(
            collection='data_refugis_lliures',
            dry_run=False,
            batch_size=500
        )
        
        # Assert
        output = out.getvalue()
        assert 'Skipped refugi3: No info_comp field' in output
        assert 'Documents skipped: 1' in output
    
    @patch('api.management.commands.convert_mezzanine_field.firebase_admin')
    @patch('api.management.commands.convert_mezzanine_field.firestore')
    @patch('os.path.exists')
    def test_convert_skip_without_old_field(self, mock_exists, mock_firestore, 
                                           mock_firebase, mock_firestore_db, 
                                           sample_refugi_without_old_field):
        """Test: Saltar refugis sense el camp antic"""
        # Arrange
        mock_exists.return_value = True
        mock_firebase.get_app.return_value = True
        mock_firestore.client.return_value = mock_firestore_db
        
        mock_doc = MagicMock()
        mock_doc.id = sample_refugi_without_old_field['id']
        mock_doc.to_dict.return_value = sample_refugi_without_old_field
        mock_firestore_db.collection().stream.return_value = [mock_doc]
        
        command = ConvertMezzanineCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle(
            collection='data_refugis_lliures',
            dry_run=False,
            batch_size=500
        )
        
        # Assert
        output = out.getvalue()
        assert 'Skipped refugi2: No mezzanine/etage field' in output
        assert 'Documents skipped: 1' in output
    
    @patch('api.management.commands.convert_mezzanine_field.firebase_admin')
    @patch('api.management.commands.convert_mezzanine_field.firestore')
    @patch('os.path.exists')
    def test_convert_dry_run(self, mock_exists, mock_firestore, mock_firebase, 
                            mock_firestore_db, sample_refugi_with_old_field):
        """Test: Mode dry-run (no converteix res)"""
        # Arrange
        mock_exists.return_value = True
        mock_firebase.get_app.return_value = True
        mock_firestore.client.return_value = mock_firestore_db
        
        mock_doc = MagicMock()
        mock_doc.id = sample_refugi_with_old_field['id']
        mock_doc.to_dict.return_value = sample_refugi_with_old_field
        mock_firestore_db.collection().stream.return_value = [mock_doc]
        
        mock_batch = MagicMock()
        mock_firestore_db.batch.return_value = mock_batch
        
        command = ConvertMezzanineCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle(
            collection='data_refugis_lliures',
            dry_run=True,
            batch_size=500
        )
        
        # Assert
        output = out.getvalue()
        assert 'DRY RUN MODE' in output
        assert 'Would update refugi1: mezzanine/etage=1 -> mezzanine_etage=1' in output
        assert 'This was a dry run' in output
        
        # Verify no batch commits
        assert not mock_batch.commit.called
    
    @patch('api.management.commands.convert_mezzanine_field.firebase_admin')
    @patch('api.management.commands.convert_mezzanine_field.firestore')
    @patch('os.path.exists')
    def test_convert_batch_processing(self, mock_exists, mock_firestore, 
                                      mock_firebase, mock_firestore_db):
        """Test: Processament per batches"""
        # Arrange
        mock_exists.return_value = True
        mock_firebase.get_app.return_value = True
        mock_firestore.client.return_value = mock_firestore_db
        
        # Create 3 documents (batch_size=2)
        mock_docs = []
        for i in range(3):
            mock_doc = MagicMock()
            mock_doc.id = f'refugi{i}'
            mock_doc.to_dict.return_value = {
                'id': f'refugi{i}',
                'name': f'Refugi {i}',
                'info_comp': {
                    'cheminee': 1,
                    'mezzanine/etage': 1
                }
            }
            mock_docs.append(mock_doc)
        
        mock_firestore_db.collection().stream.return_value = mock_docs
        
        mock_batch = MagicMock()
        mock_firestore_db.batch.return_value = mock_batch
        
        command = ConvertMezzanineCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle(
            collection='data_refugis_lliures',
            dry_run=False,
            batch_size=2
        )
        
        # Assert
        output = out.getvalue()
        assert 'Committed batch of 2 updates' in output
        assert 'Committed final batch of 1 updates' in output
        assert mock_batch.commit.call_count == 2
    
    @patch('api.management.commands.convert_mezzanine_field.firebase_admin')
    @patch('api.management.commands.convert_mezzanine_field.firestore')
    @patch('os.path.exists')
    def test_convert_with_errors(self, mock_exists, mock_firestore, 
                                 mock_firebase, mock_firestore_db):
        """Test: Gestió d'errors durant la conversió"""
        # Arrange
        mock_exists.return_value = True
        mock_firebase.get_app.return_value = True
        mock_firestore.client.return_value = mock_firestore_db
        
        # First doc OK
        mock_doc1 = MagicMock()
        mock_doc1.id = 'refugi1'
        mock_doc1.to_dict.return_value = {
            'id': 'refugi1',
            'info_comp': {'mezzanine/etage': 1}
        }
        
        # Second doc has the field but batch.update will fail
        mock_doc2 = MagicMock()
        mock_doc2.id = 'refugi2'
        mock_doc2.to_dict.return_value = {
            'id': 'refugi2',
            'info_comp': {'mezzanine/etage': 0}
        }
        
        mock_firestore_db.collection().stream.return_value = [mock_doc1, mock_doc2]
        
        mock_batch = MagicMock()
        mock_firestore_db.batch.return_value = mock_batch
        
        # Make batch.update raise exception on second call
        call_count = [0]
        def update_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 2:
                raise Exception("Firestore error")
        
        mock_batch.update.side_effect = update_side_effect
        
        command = ConvertMezzanineCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle(
            collection='data_refugis_lliures',
            dry_run=False,
            batch_size=500
        )
        
        # Assert
        output = out.getvalue()
        assert 'Queued refugi1' in output
        assert 'Error updating refugi2' in output
        assert 'Documents with errors: 1' in output
    
    @patch('api.management.commands.convert_mezzanine_field.firebase_admin')
    @patch('api.management.commands.convert_mezzanine_field.firestore')
    @patch('os.path.exists')
    def test_convert_custom_collection(self, mock_exists, mock_firestore, 
                                       mock_firebase, mock_firestore_db):
        """Test: Usar col·lecció personalitzada"""
        # Arrange
        mock_exists.return_value = True
        mock_firebase.get_app.return_value = True
        mock_firestore.client.return_value = mock_firestore_db
        mock_firestore_db.collection().stream.return_value = []
        
        command = ConvertMezzanineCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle(
            collection='custom_collection',
            dry_run=False,
            batch_size=500
        )
        
        # Assert
        mock_firestore_db.collection.assert_called_with('custom_collection')
    
    @patch('api.management.commands.convert_mezzanine_field.firebase_admin')
    @patch('api.management.commands.convert_mezzanine_field.firestore')
    @patch('os.path.exists')
    def test_convert_empty_collection(self, mock_exists, mock_firestore, 
                                      mock_firebase, mock_firestore_db):
        """Test: Conversió d'una col·lecció buida"""
        # Arrange
        mock_exists.return_value = True
        mock_firebase.get_app.return_value = True
        mock_firestore.client.return_value = mock_firestore_db
        mock_firestore_db.collection().stream.return_value = []
        
        command = ConvertMezzanineCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle(
            collection='data_refugis_lliures',
            dry_run=False,
            batch_size=500
        )
        
        # Assert
        output = out.getvalue()
        assert 'Total documents processed: 0' in output
        assert 'Documents updated: 0' in output
    
    @patch('api.management.commands.convert_mezzanine_field.firebase_admin')
    @patch('api.management.commands.convert_mezzanine_field.firestore')
    @patch('os.path.exists')
    def test_convert_value_zero(self, mock_exists, mock_firestore, 
                                mock_firebase, mock_firestore_db):
        """Test: Conversió amb valor 0"""
        # Arrange
        mock_exists.return_value = True
        mock_firebase.get_app.return_value = True
        mock_firestore.client.return_value = mock_firestore_db
        
        mock_doc = MagicMock()
        mock_doc.id = 'refugi1'
        mock_doc.to_dict.return_value = {
            'id': 'refugi1',
            'info_comp': {'mezzanine/etage': 0}
        }
        mock_firestore_db.collection().stream.return_value = [mock_doc]
        
        mock_batch = MagicMock()
        mock_firestore_db.batch.return_value = mock_batch
        
        command = ConvertMezzanineCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle(
            collection='data_refugis_lliures',
            dry_run=False,
            batch_size=500
        )
        
        # Assert
        output = out.getvalue()
        assert 'Queued refugi1: mezzanine/etage=0 -> mezzanine_etage=0' in output
    
    @patch('api.management.commands.convert_mezzanine_field.firebase_admin')
    @patch('api.management.commands.convert_mezzanine_field.firestore')
    @patch('os.path.exists')
    def test_convert_firebase_already_initialized(self, mock_exists, mock_firestore, mock_firebase):
        """Test: Firebase ja inicialitzat"""
        # Arrange
        mock_exists.return_value = True
        mock_firebase.get_app.return_value = True  # Already initialized
        mock_firestore.client.return_value = MagicMock()
        mock_firestore.client().collection().stream.return_value = []
        
        command = ConvertMezzanineCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle(
            collection='data_refugis_lliures',
            dry_run=False,
            batch_size=500
        )
        
        # Assert
        output = out.getvalue()
        assert 'Firebase already initialized' in output
