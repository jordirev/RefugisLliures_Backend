"""
Tests per als serializers de visites a refugi
"""
import pytest
from api.serializers.refuge_visit_serializer import (
    UserVisitSerializer, RefugeVisitSerializer, 
    RefugeVisitListSerializer, CreateRefugeVisitSerializer
)
from api.models.refuge_visit import RefugeVisit, UserVisit

@pytest.mark.serializers
class TestRefugeVisitSerializers:
    """Tests per als serializers de visites a refugi"""
    
    def test_user_visit_serializer_valid(self):
        """Test UserVisitSerializer amb dades vàlides"""
        data = {'uid': 'user_1', 'num_visitors': 2}
        serializer = UserVisitSerializer(data=data)
        assert serializer.is_valid()

    def test_refuge_visit_serializer_valid(self):
        """Test RefugeVisitSerializer amb dades vàlides"""
        data = {
            'date': '2024-01-01',
            'refuge_id': 'ref_1',
            'visitors': [{'uid': 'u1', 'num_visitors': 2}],
            'total_visitors': 2
        }
        serializer = RefugeVisitSerializer(data=data)
        assert serializer.is_valid()

    def test_refuge_visit_list_serializer_methods(self):
        """Test RefugeVisitListSerializer SerializerMethodFields"""
        visit = RefugeVisit(
            date="2024-01-01",
            refuge_id="ref_1",
            visitors=[UserVisit(uid="u1", num_visitors=3)],
            total_visitors=3
        )
        
        # Cas usuari registrat
        context = {'user_uid': 'u1'}
        serializer = RefugeVisitListSerializer(visit, context=context)
        assert serializer.data['is_visitor'] is True
        assert serializer.data['num_visitors'] == 3
        
        # Cas usuari no registrat
        context = {'user_uid': 'u2'}
        serializer = RefugeVisitListSerializer(visit, context=context)
        assert serializer.data['is_visitor'] is False
        assert serializer.data['num_visitors'] == 0

    def test_create_refuge_visit_serializer_valid(self):
        """Test CreateRefugeVisitSerializer amb dades vàlides"""
        data = {'num_visitors': 5}
        serializer = CreateRefugeVisitSerializer(data=data)
        assert serializer.is_valid()
