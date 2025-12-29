"""
Tests per als serializers de dubtes
"""
import pytest
from api.serializers.doubt_serializer import (
    AnswerSerializer, DoubtSerializer, CreateDoubtSerializer, CreateAnswerSerializer
)

@pytest.mark.serializers
class TestDoubtSerializers:
    """Tests per als serializers de dubtes"""
    
    def test_answer_serializer_valid(self):
        """Test AnswerSerializer amb dades vàlides"""
        data = {
            'id': 'ans_1',
            'creator_uid': 'user_1',
            'message': 'Test',
            'created_at': '2024-01-01',
            'parent_answer_id': None
        }
        serializer = AnswerSerializer(data=data)
        assert serializer.is_valid()
        assert serializer.validated_data['id'] == 'ans_1'

    def test_doubt_serializer_valid(self):
        """Test DoubtSerializer amb dades vàlides"""
        data = {
            'id': 'doubt_1',
            'refuge_id': 'ref_1',
            'creator_uid': 'user_1',
            'message': 'Test',
            'created_at': '2024-01-01',
            'answers_count': 1,
            'answers': [
                {
                    'id': 'ans_1',
                    'creator_uid': 'user_2',
                    'message': 'Reply',
                    'created_at': '2024-01-02',
                    'parent_answer_id': None
                }
            ]
        }
        serializer = DoubtSerializer(data=data)
        assert serializer.is_valid()
        assert len(serializer.validated_data['answers']) == 1

    def test_create_doubt_serializer_valid(self):
        """Test CreateDoubtSerializer amb dades vàlides"""
        data = {
            'refuge_id': 'ref_1',
            'message': 'Test'
        }
        serializer = CreateDoubtSerializer(data=data)
        assert serializer.is_valid()

    def test_create_doubt_serializer_invalid(self):
        """Test CreateDoubtSerializer amb dades invàlides"""
        data = {
            'refuge_id': '',
            'message': ''
        }
        serializer = CreateDoubtSerializer(data=data)
        assert not serializer.is_valid()
        assert 'refuge_id' in serializer.errors
        assert 'message' in serializer.errors

    def test_create_answer_serializer_valid(self):
        """Test CreateAnswerSerializer amb dades vàlides"""
        data = {
            'message': 'Test'
        }
        serializer = CreateAnswerSerializer(data=data)
        assert serializer.is_valid()

    def test_create_answer_serializer_invalid(self):
        """Test CreateAnswerSerializer amb dades invàlides"""
        data = {
            'message': ''
        }
        serializer = CreateAnswerSerializer(data=data)
        assert not serializer.is_valid()
