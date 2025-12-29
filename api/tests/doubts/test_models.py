"""
Tests per als models de dubtes i respostes
"""
import pytest
from api.models.doubt import Doubt, Answer

@pytest.mark.models
class TestDoubtModels:
    """Tests per als models Doubt i Answer"""
    
    def test_create_doubt(self):
        """Test creació de Doubt"""
        doubt = Doubt(
            id="doubt_123",
            refuge_id="refuge_456",
            creator_uid="user_789",
            message="Is there water?",
            created_at="2024-01-01T10:00:00Z"
        )
        
        assert doubt.id == "doubt_123"
        assert doubt.refuge_id == "refuge_456"
        assert doubt.answers_count == 0
        assert doubt.answers == []

    def test_doubt_validation(self):
        """Test validació de camps obligatoris en Doubt"""
        with pytest.raises(ValueError):
            Doubt(id="", refuge_id="r", creator_uid="u", message="m", created_at="d")
        
        with pytest.raises(ValueError):
            Doubt(id="i", refuge_id="", creator_uid="u", message="m", created_at="d")

    def test_doubt_to_dict(self):
        """Test conversió de Doubt a diccionari"""
        doubt = Doubt(
            id="doubt_123",
            refuge_id="refuge_456",
            creator_uid="user_789",
            message="Message",
            created_at="2024-01-01T10:00:00Z",
            answers_count=2
        )
        
        data = doubt.to_dict()
        assert data['id'] == "doubt_123"
        assert data['answers_count'] == 2
        assert 'answers' not in data  # Per defecte no inclou answers si és None o buit en to_dict? 
        # El codi diu: if self.answers: data['answers'] = ...
        
    def test_doubt_from_dict(self):
        """Test creació de Doubt des de diccionari"""
        data = {
            'id': "doubt_123",
            'refuge_id': "refuge_456",
            'creator_uid': "user_789",
            'message': "Message",
            'created_at': "2024-01-01T10:00:00Z",
            'answers_count': 5
        }
        
        doubt = Doubt.from_dict(data)
        assert doubt.id == "doubt_123"
        assert doubt.answers_count == 5
        assert doubt.answers == []

    def test_create_answer(self):
        """Test creació de Answer"""
        answer = Answer(
            id="ans_1",
            creator_uid="user_1",
            message="Yes",
            created_at="2024-01-01T12:00:00Z"
        )
        
        assert answer.id == "ans_1"
        assert answer.parent_answer_id is None

    def test_answer_to_dict(self):
        """Test conversió de Answer a diccionari"""
        answer = Answer(
            id="ans_1",
            creator_uid="user_1",
            message="Yes",
            created_at="2024-01-01T12:00:00Z",
            parent_answer_id="ans_0"
        )
        
        data = answer.to_dict()
        assert data['id'] == "ans_1"
        assert data['parent_answer_id'] == "ans_0"

    def test_answer_from_dict(self):
        """Test creació de Answer des de diccionari"""
        data = {
            'id': "ans_1",
            'creator_uid': "user_1",
            'message': "Yes",
            'created_at': "2024-01-01T12:00:00Z"
        }
        
        answer = Answer.from_dict(data)
        assert answer.id == "ans_1"
        assert answer.parent_answer_id is None
