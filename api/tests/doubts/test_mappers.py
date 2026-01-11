"""
Tests per als mappers de dubtes i respostes
"""
import pytest
from api.mappers.doubt_mapper import DoubtMapper, AnswerMapper
from api.models.doubt import Doubt, Answer

@pytest.mark.mappers
class TestDoubtMappers:
    """Tests per als mappers DoubtMapper i AnswerMapper"""
    
    def test_answer_mapper_firestore_to_model(self):
        """Test conversió de Firestore a model Answer"""
        data = {
            'id': 'ans_1',
            'creator_uid': 'user_1',
            'message': 'Test',
            'created_at': '2024-01-01'
        }
        answer = AnswerMapper.firestore_to_model(data)
        assert isinstance(answer, Answer)
        assert answer.id == 'ans_1'

    def test_answer_mapper_model_to_firestore(self):
        """Test conversió de model Answer a Firestore"""
        answer = Answer(
            id='ans_1',
            creator_uid='user_1',
            message='Test',
            created_at='2024-01-01'
        )
        data = AnswerMapper.model_to_firestore(answer)
        assert data['id'] == 'ans_1'
        assert 'message' in data

    def test_doubt_mapper_firestore_to_model(self):
        """Test conversió de Firestore a model Doubt"""
        data = {
            'id': 'doubt_1',
            'refuge_id': 'ref_1',
            'creator_uid': 'user_1',
            'message': 'Test',
            'created_at': '2024-01-01',
            'answers_count': 0
        }
        doubt = DoubtMapper.firestore_to_model(data)
        assert isinstance(doubt, Doubt)
        assert doubt.id == 'doubt_1'

    def test_doubt_mapper_model_to_firestore(self):
        """Test conversió de model Doubt a Firestore"""
        doubt = Doubt(
            id='doubt_1',
            refuge_id='ref_1',
            creator_uid='user_1',
            message='Test',
            created_at='2024-01-01',
            answers_count=1,
            answers=[Answer(id='ans_1', creator_uid='u', message='m', created_at='d')]
        )
        data = DoubtMapper.model_to_firestore(doubt)
        assert data['id'] == 'doubt_1'
        assert 'answers' not in data  # S'ha d'eliminar per Firestore
        assert data['answers_count'] == 1

    def test_lists_conversion(self):
        """Test conversió de llistes"""
        data_list = [{'id': 'ans_1', 'creator_uid': 'u', 'message': 'm', 'created_at': 'd'}]
        models = AnswerMapper.firestore_list_to_models(data_list)
        assert len(models) == 1
        assert models[0].id == 'ans_1'
        
        back_to_data = AnswerMapper.models_to_firestore_list(models)
        assert len(back_to_data) == 1
        assert back_to_data[0]['id'] == 'ans_1'
