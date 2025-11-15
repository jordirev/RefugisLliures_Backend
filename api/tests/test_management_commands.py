"""
Tests unitaris per als management commands
"""
import pytest
import json
import os
from unittest.mock import Mock, MagicMock, patch, mock_open, call
from io import StringIO
from django.core.management import call_command
from django.core.management.base import CommandError
from api.management.commands.upload_refugis_to_firestore import Command as UploadCommand
from api.management.commands.extract_coords_to_firestore import Command as ExtractCommand


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


@pytest.fixture
def mock_firestore_docs(sample_refugis_json):
    """Mock de documents Firestore per streaming"""
    mock_docs = []
    for refugi_data in sample_refugis_json:
        mock_doc = MagicMock()
        mock_doc.id = str(refugi_data['id'])
        mock_doc.to_dict.return_value = refugi_data
        mock_docs.append(mock_doc)
    return mock_docs


# ============= TESTS UPLOAD_REFUGIS_TO_FIRESTORE =============

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
            dry_run=False
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
            dry_run=False
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
            dry_run=False
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
            dry_run=False
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
            dry_run=False
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
            dry_run=True
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
            dry_run=False
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
            dry_run=False
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
            dry_run=False
        )
        
        # Assert
        output = out.getvalue()
        assert 'Found 0 refugis in JSON file' in output
        assert 'Successfully uploaded: 0 documents' in output


# ============= TESTS EXTRACT_COORDS_TO_FIRESTORE =============

class TestExtractCoordsToFirestore:
    """Tests per al command extract_coords_to_firestore"""
    
    @patch('api.management.commands.extract_coords_to_firestore.credentials')
    @patch('api.management.commands.extract_coords_to_firestore.firebase_admin')
    @patch('api.management.commands.extract_coords_to_firestore.firestore')
    @patch('os.path.exists')
    def test_extract_success(self, mock_exists, mock_firestore, mock_firebase,
                            mock_credentials, mock_firestore_db, mock_firestore_docs):
        """Test: Extracció exitosa de coordenades"""
        # Arrange
        mock_exists.return_value = True
        mock_firebase.get_app.side_effect = ValueError
        mock_credentials.Certificate.return_value = MagicMock()
        mock_firestore.client.return_value = mock_firestore_db
        mock_firestore_db.collection().stream.return_value = mock_firestore_docs
        
        command = ExtractCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle(
            source_collection='data_refugis_lliures',
            target_collection='coords_refugis',
            dry_run=False,
            clear_target=False
        )
        
        # Assert
        output = out.getvalue()
        assert 'Reading refugis from collection: data_refugis_lliures' in output
        assert 'Writing all 2 coordinates to a single document' in output
        assert 'Successfully created single document with 2 refugi coordinates' in output
    
    @patch('api.management.commands.extract_coords_to_firestore.firebase_admin')
    @patch('api.management.commands.extract_coords_to_firestore.firestore')
    @patch('os.path.exists')
    def test_extract_firebase_credentials_not_found(self, mock_exists, 
                                                     mock_firestore, mock_firebase):
        """Test: Error quan no es troben les credencials"""
        # Arrange
        mock_firebase.get_app.side_effect = ValueError
        mock_exists.return_value = False
        
        command = ExtractCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle(
            source_collection='data_refugis_lliures',
            target_collection='coords_refugis',
            dry_run=False,
            clear_target=False
        )
        
        # Assert
        output = out.getvalue()
        assert 'Firebase credentials file not found' in output
    
    @patch('api.management.commands.extract_coords_to_firestore.firebase_admin')
    @patch('api.management.commands.extract_coords_to_firestore.firestore')
    @patch('os.path.exists')
    def test_extract_missing_coordinates(self, mock_exists, mock_firestore, 
                                        mock_firebase, mock_firestore_db):
        """Test: Gestió de refugis sense coordenades"""
        # Arrange
        mock_exists.return_value = True
        mock_firebase.get_app.return_value = True
        mock_firestore.client.return_value = mock_firestore_db
        
        # Create docs with and without coordinates
        mock_doc_with_coords = MagicMock()
        mock_doc_with_coords.id = '0'
        mock_doc_with_coords.to_dict.return_value = {
            'name': 'Refugi Valid',
            'coord': {'lat': 42.5, 'long': 1.5}
        }
        
        mock_doc_without_coords = MagicMock()
        mock_doc_without_coords.id = '1'
        mock_doc_without_coords.to_dict.return_value = {
            'name': 'Refugi Invalid',
            'coord': {}  # Missing lat/long
        }
        
        mock_firestore_db.collection().stream.return_value = [
            mock_doc_with_coords, mock_doc_without_coords
        ]
        
        command = ExtractCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle(
            source_collection='data_refugis_lliures',
            target_collection='coords_refugis',
            dry_run=False,
            clear_target=False
        )
        
        # Assert
        output = out.getvalue()
        assert 'Skipping refugi 1: missing coordinates' in output
        assert 'Skipped 1 refugis due to missing coordinates' in output
        assert 'Successfully created single document with 1 refugi coordinates' in output
    
    @patch('api.management.commands.extract_coords_to_firestore.firebase_admin')
    @patch('api.management.commands.extract_coords_to_firestore.firestore')
    @patch('os.path.exists')
    def test_extract_dry_run(self, mock_exists, mock_firestore, mock_firebase, 
                            mock_firestore_db, mock_firestore_docs):
        """Test: Mode dry-run (no crea documents)"""
        # Arrange
        mock_exists.return_value = True
        mock_firebase.get_app.return_value = True
        mock_firestore.client.return_value = mock_firestore_db
        mock_firestore_db.collection().stream.return_value = mock_firestore_docs
        
        command = ExtractCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle(
            source_collection='data_refugis_lliures',
            target_collection='coords_refugis',
            dry_run=True,
            clear_target=False
        )
        
        # Assert
        output = out.getvalue()
        assert '[DRY RUN] Would create coordinate document for refugi: 0' in output
        assert '[DRY RUN] Would create coordinate document for refugi: 1' in output
        assert '[DRY RUN] Would create a single document with 2 refugi coordinates' in output
        
        # Verify no actual writes
        assert not mock_firestore_db.collection().document().set.called
    
    @patch('api.management.commands.extract_coords_to_firestore.firebase_admin')
    @patch('api.management.commands.extract_coords_to_firestore.firestore')
    @patch('os.path.exists')
    def test_extract_custom_collections(self, mock_exists, mock_firestore, 
                                        mock_firebase, mock_firestore_db, 
                                        mock_firestore_docs):
        """Test: Ús de col·leccions personalitzades"""
        # Arrange
        mock_exists.return_value = True
        mock_firebase.get_app.return_value = True
        mock_firestore.client.return_value = mock_firestore_db
        mock_firestore_db.collection().stream.return_value = mock_firestore_docs
        
        command = ExtractCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle(
            source_collection='custom_source',
            target_collection='custom_target',
            dry_run=False,
            clear_target=False
        )
        
        # Assert
        output = out.getvalue()
        assert 'Reading refugis from collection: custom_source' in output
        
        # Verify collections were called correctly
        collection_calls = mock_firestore_db.collection.call_args_list
        assert any('custom_source' in str(call) for call in collection_calls)
        assert any('custom_target' in str(call) for call in collection_calls)
    
    @patch('api.management.commands.extract_coords_to_firestore.firebase_admin')
    @patch('api.management.commands.extract_coords_to_firestore.firestore')
    @patch('os.path.exists')
    def test_extract_clear_target(self, mock_exists, mock_firestore, mock_firebase, 
                                  mock_firestore_db, mock_firestore_docs):
        """Test: Neteja de la col·lecció destí abans d'extreure"""
        # Arrange
        mock_exists.return_value = True
        mock_firebase.get_app.return_value = True
        mock_firestore.client.return_value = mock_firestore_db
        
        # Mock existing docs to clear
        mock_existing_doc = MagicMock()
        mock_existing_doc.reference = MagicMock()
        
        def stream_side_effect():
            # First call for clearing, second for extracting
            call_count = stream_side_effect.counter
            stream_side_effect.counter += 1
            if call_count == 0:
                return [mock_existing_doc]  # Docs to clear
            else:
                return mock_firestore_docs  # Docs to extract
        
        stream_side_effect.counter = 0
        mock_firestore_db.collection().stream.side_effect = stream_side_effect
        
        command = ExtractCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle(
            source_collection='data_refugis_lliures',
            target_collection='coords_refugis',
            dry_run=False,
            clear_target=True
        )
        
        # Assert
        output = out.getvalue()
        assert 'Clearing target collection: coords_refugis' in output
        assert 'Cleared 1 documents from coords_refugis' in output
    
    @patch('api.management.commands.extract_coords_to_firestore.firebase_admin')
    @patch('api.management.commands.extract_coords_to_firestore.firestore')
    @patch('os.path.exists')
    def test_extract_with_exception(self, mock_exists, mock_firestore, 
                                    mock_firebase, mock_firestore_db):
        """Test: Gestió d'excepcions durant l'extracció"""
        # Arrange
        mock_exists.return_value = True
        mock_firebase.get_app.return_value = True
        mock_firestore.client.return_value = mock_firestore_db
        mock_firestore_db.collection().stream.side_effect = Exception("Firestore error")
        
        command = ExtractCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle(
            source_collection='data_refugis_lliures',
            target_collection='coords_refugis',
            dry_run=False,
            clear_target=False
        )
        
        # Assert
        output = out.getvalue()
        assert 'Error processing refugis' in output
    
    @patch('api.management.commands.extract_coords_to_firestore.firebase_admin')
    @patch('api.management.commands.extract_coords_to_firestore.firestore')
    @patch('os.path.exists')
    def test_extract_geohash_generation(self, mock_exists, mock_firestore, 
                                       mock_firebase, mock_firestore_db):
        """Test: Generació de geohash per a coordenades"""
        # Arrange
        mock_exists.return_value = True
        mock_firebase.get_app.return_value = True
        mock_firestore.client.return_value = mock_firestore_db
        
        mock_doc = MagicMock()
        mock_doc.id = '0'
        mock_doc.to_dict.return_value = {
            'name': 'Test Refugi',
            'coord': {'lat': 42.5, 'long': 1.5}
        }
        mock_firestore_db.collection().stream.return_value = [mock_doc]
        
        command = ExtractCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle(
            source_collection='data_refugis_lliures',
            target_collection='coords_refugis',
            dry_run=False,
            clear_target=False
        )
        
        # Assert - verify document was set with geohash
        set_call = mock_firestore_db.collection().document().set
        assert set_call.called
        call_args = set_call.call_args[0][0]
        assert 'refugis_coordinates' in call_args
        assert len(call_args['refugis_coordinates']) == 1
        assert 'geohash' in call_args['refugis_coordinates'][0]
    
    @patch('api.management.commands.extract_coords_to_firestore.firebase_admin')
    @patch('api.management.commands.extract_coords_to_firestore.firestore')
    @patch('os.path.exists')
    def test_extract_empty_collection(self, mock_exists, mock_firestore, 
                                      mock_firebase, mock_firestore_db):
        """Test: Extracció d'una col·lecció buida"""
        # Arrange
        mock_exists.return_value = True
        mock_firebase.get_app.return_value = True
        mock_firestore.client.return_value = mock_firestore_db
        mock_firestore_db.collection().stream.return_value = []
        
        command = ExtractCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle(
            source_collection='data_refugis_lliures',
            target_collection='coords_refugis',
            dry_run=False,
            clear_target=False
        )
        
        # Assert
        output = out.getvalue()
        assert 'Writing all 0 coordinates to a single document' in output
        assert 'Successfully created single document with 0 refugi coordinates' in output
