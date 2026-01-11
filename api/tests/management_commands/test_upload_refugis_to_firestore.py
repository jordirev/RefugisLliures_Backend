"""
Tests unitaris per al management command upload_refugis_to_firestore
"""
import pytest
import json
from unittest.mock import MagicMock, patch, mock_open
from io import StringIO
from api.management.commands.upload_refugis_to_firestore import Command as UploadCommand


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
    
    return mock_db


@pytest.fixture
def sample_refugis_json():
    """Dades de mostra en format JSON"""
    return [
        {
            "id": 0,
            "name": "Refugi Test 1",
            "coord": {"lat": 42.5, "long": 1.5},
            "region": "Ariège"
        },
        {
            "id": 1,
            "name": "Refugi Test 2",
            "coord": {"lat": 42.6, "long": 1.6},
            "region": "Pallars"
        }
    ]


# ============= TESTS =============

class TestUploadRefugisToFirestore:
    """Tests per al command upload_refugis_to_firestore"""
    
    @patch('api.management.commands.upload_refugis_to_firestore.credentials')
    @patch('api.management.commands.upload_refugis_to_firestore.firebase_admin')
    @patch('api.management.commands.upload_refugis_to_firestore.firestore')
    @patch('api.management.commands.upload_refugis_to_firestore.json.load')
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.path.exists')
    def test_upload_success(self, mock_exists, mock_file, mock_json_load, 
                           mock_firestore, mock_firebase, mock_credentials, 
                           mock_firestore_db, sample_refugis_json):
        """Test: Pujada exitosa de refugis"""
        # Arrange
        mock_exists.return_value = True
        mock_firebase.get_app.side_effect = ValueError  # Force initialization
        mock_credentials.Certificate.return_value = MagicMock()
        mock_firestore.client.return_value = mock_firestore_db
        mock_json_load.return_value = sample_refugis_json
        
        command = UploadCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle(
            json_file='api/utils/demo_data_refugis.json',
            collection='data_refugis_lliures',
            dry_run=False,
            clear_collection=False
        )
        
        # Assert
        output = out.getvalue()
        assert 'Found 2 refugis in JSON file' in output
        assert '✓ Uploaded refugi 0: Refugi Test 1' in output
        assert '✓ Uploaded refugi 1: Refugi Test 2' in output
        assert 'Successfully uploaded: 2 documents' in output
        
        # Verify Firestore calls
        assert mock_firestore_db.collection.called
        assert mock_firestore_db.collection().document.call_count == 2
    
    @patch('api.management.commands.upload_refugis_to_firestore.firebase_admin')
    @patch('api.management.commands.upload_refugis_to_firestore.firestore')
    @patch('os.path.exists')
    def test_upload_firebase_credentials_not_found(self, mock_exists, 
                                                    mock_firestore, mock_firebase):
        """Test: Error quan no es troben les credencials de Firebase"""
        # Arrange
        mock_firebase.get_app.side_effect = ValueError
        mock_exists.return_value = False
        
        command = UploadCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle(
            json_file='api/utils/demo_data_refugis.json',
            collection='data_refugis_lliures',
            dry_run=False,
            clear_collection=False
        )
        
        # Assert
        output = out.getvalue()
        assert 'Firebase credentials file not found' in output
    
    @patch('api.management.commands.upload_refugis_to_firestore.firebase_admin')
    @patch('api.management.commands.upload_refugis_to_firestore.firestore')
    @patch('os.path.exists')
    def test_upload_json_file_not_found(self, mock_exists, mock_firestore, 
                                       mock_firebase, mock_firestore_db):
        """Test: Error quan no es troba el fitxer JSON"""
        # Arrange
        mock_firebase.get_app.return_value = True  # Already initialized
        mock_firestore.client.return_value = mock_firestore_db
        
        def exists_side_effect(path):
            if 'firebase-service-account.json' in path:
                return True
            return False
        
        mock_exists.side_effect = exists_side_effect
        
        command = UploadCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle(
            json_file='api/utils/demo_data_refugis.json',
            collection='data_refugis_lliures',
            dry_run=False,
            clear_collection=False
        )
        
        # Assert
        output = out.getvalue()
        assert 'JSON file not found' in output
    
    @patch('api.management.commands.upload_refugis_to_firestore.firebase_admin')
    @patch('api.management.commands.upload_refugis_to_firestore.firestore')
    @patch('api.management.commands.upload_refugis_to_firestore.json.load')
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.path.exists')
    def test_upload_invalid_json(self, mock_exists, mock_file, mock_json_load,
                                 mock_firestore, mock_firebase, mock_firestore_db):
        """Test: Error amb JSON invàlid"""
        # Arrange
        mock_exists.return_value = True
        mock_firebase.get_app.return_value = True
        mock_firestore.client.return_value = mock_firestore_db
        mock_json_load.side_effect = json.JSONDecodeError("Expecting value", "", 0)
        
        command = UploadCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle(
            json_file='api/utils/demo_data_refugis.json',
            collection='data_refugis_lliures',
            dry_run=False,
            clear_collection=False
        )
        
        # Assert
        output = out.getvalue()
        assert 'Error parsing JSON file' in output
    
    @patch('api.management.commands.upload_refugis_to_firestore.firebase_admin')
    @patch('api.management.commands.upload_refugis_to_firestore.firestore')
    @patch('api.management.commands.upload_refugis_to_firestore.json.load')
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.path.exists')
    def test_upload_json_not_array(self, mock_exists, mock_file, mock_json_load,
                                   mock_firestore, mock_firebase, mock_firestore_db):
        """Test: Error quan el JSON no és un array"""
        # Arrange
        mock_exists.return_value = True
        mock_firebase.get_app.return_value = True
        mock_firestore.client.return_value = mock_firestore_db
        mock_json_load.return_value = {"not": "array"}
        
        command = UploadCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle(
            json_file='api/utils/demo_data_refugis.json',
            collection='data_refugis_lliures',
            dry_run=False,
            clear_collection=False
        )
        
        # Assert
        output = out.getvalue()
        assert 'JSON file must contain an array of refugis' in output
    
    @patch('api.management.commands.upload_refugis_to_firestore.firebase_admin')
    @patch('api.management.commands.upload_refugis_to_firestore.firestore')
    @patch('api.management.commands.upload_refugis_to_firestore.json.load')
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.path.exists')
    def test_upload_dry_run(self, mock_exists, mock_file, mock_json_load,
                           mock_firestore, mock_firebase, mock_firestore_db, sample_refugis_json):
        """Test: Mode dry-run (no puja res)"""
        # Arrange
        mock_exists.return_value = True
        mock_firebase.get_app.return_value = True
        mock_firestore.client.return_value = mock_firestore_db
        mock_json_load.return_value = sample_refugis_json
        
        command = UploadCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle(
            json_file='api/utils/demo_data_refugis.json',
            collection='data_refugis_lliures',
            dry_run=True,
            clear_collection=False
        )
        
        # Assert
        output = out.getvalue()
        assert 'DRY RUN - No data will be uploaded' in output
        assert 'Would upload refugi 0: Refugi Test 1' in output
        assert 'Would upload refugi 1: Refugi Test 2' in output
        
        # Verify no actual uploads
        assert not mock_firestore_db.collection().document().set.called
    
    @patch('api.management.commands.upload_refugis_to_firestore.firebase_admin')
    @patch('api.management.commands.upload_refugis_to_firestore.firestore')
    @patch('api.management.commands.upload_refugis_to_firestore.json.load')
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.path.exists')
    def test_upload_custom_collection(self, mock_exists, mock_file, mock_json_load,
                                      mock_firestore, mock_firebase, mock_firestore_db, sample_refugis_json):
        """Test: Pujada a una col·lecció personalitzada"""
        # Arrange
        mock_exists.return_value = True
        mock_firebase.get_app.return_value = True
        mock_firestore.client.return_value = mock_firestore_db
        mock_json_load.return_value = sample_refugis_json
        
        command = UploadCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle(
            json_file='api/utils/demo_data_refugis.json',
            collection='custom_collection',
            dry_run=False,
            clear_collection=False
        )
        
        # Assert
        mock_firestore_db.collection.assert_called_with('custom_collection')
    
    @patch('api.management.commands.upload_refugis_to_firestore.firebase_admin')
    @patch('api.management.commands.upload_refugis_to_firestore.firestore')
    @patch('api.management.commands.upload_refugis_to_firestore.json.load')
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.path.exists')
    def test_upload_with_errors(self, mock_exists, mock_file, mock_json_load,
                                mock_firestore, mock_firebase, mock_firestore_db, sample_refugis_json):
        """Test: Gestió d'errors durant la pujada"""
        # Arrange
        mock_exists.return_value = True
        mock_firebase.get_app.return_value = True
        mock_firestore.client.return_value = mock_firestore_db
        mock_json_load.return_value = sample_refugis_json
        
        # Simulate error on second document
        mock_doc = MagicMock()
        mock_doc.set.side_effect = [None, Exception("Firestore error")]
        mock_firestore_db.collection().document.return_value = mock_doc
        
        command = UploadCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle(
            json_file='api/utils/demo_data_refugis.json',
            collection='data_refugis_lliures',
            dry_run=False,
            clear_collection=False
        )
        
        # Assert
        output = out.getvalue()
        assert '✓ Uploaded refugi 0' in output
        assert '✗ Error uploading refugi 1' in output
        assert 'Errors: 1 documents failed' in output
    
    @patch('api.management.commands.upload_refugis_to_firestore.firebase_admin')
    @patch('api.management.commands.upload_refugis_to_firestore.firestore')
    @patch('api.management.commands.upload_refugis_to_firestore.json.load')
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.path.exists')
    def test_upload_empty_json(self, mock_exists, mock_file, mock_json_load,
                               mock_firestore, mock_firebase, mock_firestore_db):
        """Test: Pujada amb array buit"""
        # Arrange
        mock_exists.return_value = True
        mock_firebase.get_app.return_value = True
        mock_firestore.client.return_value = mock_firestore_db
        mock_json_load.return_value = []
        
        command = UploadCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle(
            json_file='api/utils/demo_data_refugis.json',
            collection='data_refugis_lliures',
            dry_run=False,
            clear_collection=False
        )
        
        # Assert
        output = out.getvalue()
        assert 'Found 0 refugis in JSON file' in output
        assert 'Successfully uploaded: 0 documents' in output
