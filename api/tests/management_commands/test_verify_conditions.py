"""
Tests unitaris per al management command verify_conditions
"""
import pytest
from unittest.mock import MagicMock, patch
from io import StringIO
from api.management.commands.verify_conditions import Command as VerifyConditionsCommand


# ============= FIXTURES =============

@pytest.fixture
def mock_firestore_db():
    """Mock del client Firestore"""
    mock_db = MagicMock()
    mock_collection = MagicMock()
    
    mock_db.collection.return_value = mock_collection
    
    return mock_db


@pytest.fixture
def sample_refugi_doc_condition_3():
    """Refugi amb condition 3"""
    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = {
        'name': 'Refugi Excel·lent',
        'condition': 3.0,
        'num_contributed_conditions': 1,
        'info_comp': {
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
    }
    return mock_doc


@pytest.fixture
def sample_refugi_doc_condition_0():
    """Refugi amb condition 0"""
    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = {
        'name': 'Refugi Pobre',
        'condition': 0.0,
        'num_contributed_conditions': 1,
        'info_comp': {
            'cheminee': 0,
            'manque_un_mur': 1
        }
    }
    return mock_doc


@pytest.fixture
def sample_refugi_doc_not_found():
    """Refugi que no existeix"""
    mock_doc = MagicMock()
    mock_doc.exists = False
    return mock_doc


@pytest.fixture
def sample_refugi_doc_wrong_condition():
    """Refugi amb condition incorrecta"""
    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = {
        'name': 'Refugi Incorrecte',
        'condition': 1.0,  # Hauria de ser 3
        'num_contributed_conditions': 2,  # Hauria de ser 1
        'info_comp': {
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
    }
    return mock_doc


# ============= TESTS =============

class TestVerifyConditions:
    """Tests per al command verify_conditions"""
    
    @patch('api.management.commands.verify_conditions.firestore_service')
    def test_verify_conditions_all_correct(self, mock_firestore_service, mock_firestore_db, 
                                           sample_refugi_doc_condition_3):
        """Test: Verificació amb totes les conditions correctes"""
        # Arrange
        mock_firestore_service.get_db.return_value = mock_firestore_db
        
        def document_side_effect(doc_id):
            mock_doc_ref = MagicMock()
            mock_doc_ref.get.return_value = sample_refugi_doc_condition_3
            return mock_doc_ref
        
        mock_firestore_db.collection().document.side_effect = document_side_effect
        
        # Mock stream for statistics
        mock_stream_docs = [
            MagicMock(to_dict=lambda: {'condition': 0.0}),
            MagicMock(to_dict=lambda: {'condition': 1.0}),
            MagicMock(to_dict=lambda: {'condition': 2.0}),
            MagicMock(to_dict=lambda: {'condition': 3.0}),
            MagicMock(to_dict=lambda: {'condition': 3.0}),
        ]
        mock_firestore_db.collection().stream.return_value = mock_stream_docs
        
        command = VerifyConditionsCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle()
        
        # Assert
        output = out.getvalue()
        assert 'Verificant conditions assignades' in output
        assert 'ESTADÍSTIQUES GENERALS' in output
        assert 'Condition 0 (Pobre):' in output
        assert 'Condition 1 (Correcte):' in output
        assert 'Condition 2 (Bé):' in output
        assert 'Condition 3 (Excel·lent):' in output
    
    @patch('api.management.commands.verify_conditions.firestore_service')
    def test_verify_conditions_refugi_not_found(self, mock_firestore_service, mock_firestore_db, 
                                                sample_refugi_doc_not_found):
        """Test: Verificació amb refugi no trobat"""
        # Arrange
        mock_firestore_service.get_db.return_value = mock_firestore_db
        
        def document_side_effect(doc_id):
            mock_doc_ref = MagicMock()
            mock_doc_ref.get.return_value = sample_refugi_doc_not_found
            return mock_doc_ref
        
        mock_firestore_db.collection().document.side_effect = document_side_effect
        mock_firestore_db.collection().stream.return_value = []
        
        command = VerifyConditionsCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle()
        
        # Assert
        output = out.getvalue()
        assert 'no trobat' in output
    
    @patch('api.management.commands.verify_conditions.firestore_service')
    def test_verify_conditions_wrong_condition(self, mock_firestore_service, mock_firestore_db, 
                                               sample_refugi_doc_wrong_condition):
        """Test: Verificació amb condition incorrecta"""
        # Arrange
        mock_firestore_service.get_db.return_value = mock_firestore_db
        
        def document_side_effect(doc_id):
            mock_doc_ref = MagicMock()
            mock_doc_ref.get.return_value = sample_refugi_doc_wrong_condition
            return mock_doc_ref
        
        mock_firestore_db.collection().document.side_effect = document_side_effect
        mock_firestore_db.collection().stream.return_value = []
        
        command = VerifyConditionsCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle()
        
        # Assert
        output = out.getvalue()
        assert 'FAIL' in output
        assert 'Refugi Incorrecte' in output
    
    @patch('api.management.commands.verify_conditions.firestore_service')
    def test_verify_conditions_statistics(self, mock_firestore_service, mock_firestore_db):
        """Test: Estadístiques generals"""
        # Arrange
        mock_firestore_service.get_db.return_value = mock_firestore_db
        
        # Mock refugis to check
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            'name': 'Test',
            'condition': 3.0,
            'num_contributed_conditions': 1,
            'info_comp': {'cheminee': 1, 'poele': 1, 'couvertures': 1, 'latrines': 1, 
                         'bois': 1, 'eau': 1, 'matelas': 1}
        }
        
        def document_side_effect(doc_id):
            mock_doc_ref = MagicMock()
            mock_doc_ref.get.return_value = mock_doc
            return mock_doc_ref
        
        mock_firestore_db.collection().document.side_effect = document_side_effect
        
        # Mock stream for statistics with different conditions
        mock_stream_docs = [
            MagicMock(to_dict=lambda: {'condition': 0.0}),
            MagicMock(to_dict=lambda: {'condition': 0.0}),
            MagicMock(to_dict=lambda: {'condition': 1.0}),
            MagicMock(to_dict=lambda: {'condition': 2.0}),
            MagicMock(to_dict=lambda: {'condition': 2.0}),
            MagicMock(to_dict=lambda: {'condition': 2.0}),
            MagicMock(to_dict=lambda: {'condition': 3.0}),
            MagicMock(to_dict=lambda: {'condition': None}),
        ]
        mock_firestore_db.collection().stream.return_value = mock_stream_docs
        
        command = VerifyConditionsCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle()
        
        # Assert
        output = out.getvalue()
        assert 'Condition 0 (Pobre): 2' in output
        assert 'Condition 1 (Correcte): 1' in output
        assert 'Condition 2 (Bé): 3' in output
        assert 'Condition 3 (Excel·lent): 1' in output
        assert 'Sense condition: 1' in output
    
    @patch('api.management.commands.verify_conditions.firestore_service')
    def test_verify_conditions_amenities_count(self, mock_firestore_service, mock_firestore_db):
        """Test: Comptar comoditats correctament"""
        # Arrange
        mock_firestore_service.get_db.return_value = mock_firestore_db
        
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            'name': 'Refugi Test',
            'condition': 2.0,
            'num_contributed_conditions': 1,
            'info_comp': {
                'cheminee': 1,
                'poele': 1,
                'couvertures': 1,
                'latrines': 1,
                'bois': 1,
                'eau': 0,
                'manque_un_mur': 0
            }
        }
        
        def document_side_effect(doc_id):
            mock_doc_ref = MagicMock()
            mock_doc_ref.get.return_value = mock_doc
            return mock_doc_ref
        
        mock_firestore_db.collection().document.side_effect = document_side_effect
        mock_firestore_db.collection().stream.return_value = []
        
        command = VerifyConditionsCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle()
        
        # Assert
        output = out.getvalue()
        assert 'Amenities: 5 comoditats' in output
    
    @patch('api.management.commands.verify_conditions.firestore_service')
    def test_verify_conditions_missing_wall(self, mock_firestore_service, mock_firestore_db):
        """Test: Detectar mur que falta"""
        # Arrange
        mock_firestore_service.get_db.return_value = mock_firestore_db
        
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            'name': 'Refugi Amb Mur',
            'condition': 0.0,
            'num_contributed_conditions': 1,
            'info_comp': {
                'cheminee': 1,
                'poele': 1,
                'manque_un_mur': 1
            }
        }
        
        def document_side_effect(doc_id):
            mock_doc_ref = MagicMock()
            mock_doc_ref.get.return_value = mock_doc
            return mock_doc_ref
        
        mock_firestore_db.collection().document.side_effect = document_side_effect
        mock_firestore_db.collection().stream.return_value = []
        
        command = VerifyConditionsCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle()
        
        # Assert
        output = out.getvalue()
        assert 'Manque un mur: 1' in output
    
    @patch('api.management.commands.verify_conditions.firestore_service')
    def test_verify_conditions_success_fail_count(self, mock_firestore_service, mock_firestore_db):
        """Test: Comptar èxits i fallades"""
        # Arrange
        mock_firestore_service.get_db.return_value = mock_firestore_db
        
        # Create mix of correct and incorrect refugis
        correct_doc = MagicMock()
        correct_doc.exists = True
        correct_doc.to_dict.return_value = {
            'name': 'Correcte',
            'condition': 3.0,
            'num_contributed_conditions': 1,
            'info_comp': {'cheminee': 1, 'poele': 1, 'couvertures': 1, 'latrines': 1,
                         'bois': 1, 'eau': 1, 'matelas': 1, 'couchage': 1}
        }
        
        wrong_doc = MagicMock()
        wrong_doc.exists = True
        wrong_doc.to_dict.return_value = {
            'name': 'Incorrecte',
            'condition': 1.0,  # Should be 3
            'num_contributed_conditions': 2,  # Should be 1
            'info_comp': {'cheminee': 1, 'poele': 1, 'couvertures': 1, 'latrines': 1,
                         'bois': 1, 'eau': 1, 'matelas': 1, 'couchage': 1}
        }
        
        docs = [correct_doc, correct_doc, correct_doc, wrong_doc, wrong_doc]
        call_count = [0]
        
        def document_side_effect(doc_id):
            mock_doc_ref = MagicMock()
            doc = docs[call_count[0] % len(docs)]
            call_count[0] += 1
            mock_doc_ref.get.return_value = doc
            return mock_doc_ref
        
        mock_firestore_db.collection().document.side_effect = document_side_effect
        mock_firestore_db.collection().stream.return_value = []
        
        command = VerifyConditionsCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle()
        
        # Assert
        output = out.getvalue()
        assert 'OK' in output
        assert 'FAIL' in output
        assert 'Verificació completada' in output
    
    @patch('api.management.commands.verify_conditions.firestore_service')
    def test_verify_conditions_empty_database(self, mock_firestore_service, mock_firestore_db):
        """Test: Base de dades buida"""
        # Arrange
        mock_firestore_service.get_db.return_value = mock_firestore_db
        
        not_found_doc = MagicMock()
        not_found_doc.exists = False
        
        def document_side_effect(doc_id):
            mock_doc_ref = MagicMock()
            mock_doc_ref.get.return_value = not_found_doc
            return mock_doc_ref
        
        mock_firestore_db.collection().document.side_effect = document_side_effect
        mock_firestore_db.collection().stream.return_value = []
        
        command = VerifyConditionsCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle()
        
        # Assert
        output = out.getvalue()
        assert 'Condition 0 (Pobre): 0' in output
        assert 'Condition 1 (Correcte): 0' in output
        assert 'Condition 2 (Bé): 0' in output
        assert 'Condition 3 (Excel·lent): 0' in output
        assert 'Sense condition: 0' in output
    
    @patch('api.management.commands.verify_conditions.firestore_service')
    def test_verify_conditions_long_name_truncation(self, mock_firestore_service, mock_firestore_db):
        """Test: Truncar noms llargs"""
        # Arrange
        mock_firestore_service.get_db.return_value = mock_firestore_db
        
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            'name': 'A' * 100,  # Very long name
            'condition': 3.0,
            'num_contributed_conditions': 1,
            'info_comp': {'cheminee': 1, 'poele': 1, 'couvertures': 1, 'latrines': 1,
                         'bois': 1, 'eau': 1, 'matelas': 1, 'couchage': 1}
        }
        
        def document_side_effect(doc_id):
            mock_doc_ref = MagicMock()
            mock_doc_ref.get.return_value = mock_doc
            return mock_doc_ref
        
        mock_firestore_db.collection().document.side_effect = document_side_effect
        mock_firestore_db.collection().stream.return_value = []
        
        command = VerifyConditionsCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle()
        
        # Assert
        output = out.getvalue()
        # Name should be truncated to 50 chars
        assert 'A' * 50 in output
        assert 'A' * 51 not in output
    
    @patch('api.management.commands.verify_conditions.firestore_service')
    def test_verify_conditions_no_name(self, mock_firestore_service, mock_firestore_db):
        """Test: Refugi sense nom"""
        # Arrange
        mock_firestore_service.get_db.return_value = mock_firestore_db
        
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            'condition': 2.0,
            'num_contributed_conditions': 1,
            'info_comp': {'cheminee': 1, 'poele': 1, 'couvertures': 1}
        }
        
        def document_side_effect(doc_id):
            mock_doc_ref = MagicMock()
            mock_doc_ref.get.return_value = mock_doc
            return mock_doc_ref
        
        mock_firestore_db.collection().document.side_effect = document_side_effect
        mock_firestore_db.collection().stream.return_value = []
        
        command = VerifyConditionsCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle()
        
        # Assert
        output = out.getvalue()
        assert 'Sense nom' in output
