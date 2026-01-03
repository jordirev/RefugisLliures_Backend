"""
Tests unitaris per al management command extract_coords_to_firestore
"""
import pytest
from unittest.mock import MagicMock, patch
from io import StringIO
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


# ============= TESTS =============

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
