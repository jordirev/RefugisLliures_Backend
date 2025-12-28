"""
Tests per als serializers de propostes de refugi
"""
import pytest
from api.serializers.refuge_proposal_serializer import (
    RefugeProposalCreateSerializer, RefugeProposalResponseSerializer,
    RefugeProposalRejectSerializer
)

@pytest.mark.serializers
class TestRefugeProposalSerializers:
    """Tests per als serializers de propostes de refugi"""
    
    def test_create_proposal_valid_create(self):
        """Test RefugeProposalCreateSerializer per acció 'create'"""
        data = {
            'action': 'create',
            'payload': {
                'name': 'New Refuge',
                'coord': {'lat': 42.0, 'long': 1.0},
                'altitude': 2000
            }
        }
        serializer = RefugeProposalCreateSerializer(data=data)
        assert serializer.is_valid()

    def test_create_proposal_invalid_create_missing_payload(self):
        """Test RefugeProposalCreateSerializer per 'create' sense payload"""
        data = {
            'action': 'create'
        }
        serializer = RefugeProposalCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert 'payload' in serializer.errors

    def test_create_proposal_valid_update(self):
        """Test RefugeProposalCreateSerializer per acció 'update'"""
        data = {
            'action': 'update',
            'refuge_id': 'ref_1',
            'payload': {
                'places': 20
            }
        }
        serializer = RefugeProposalCreateSerializer(data=data)
        assert serializer.is_valid()

    def test_create_proposal_valid_delete(self):
        """Test RefugeProposalCreateSerializer per acció 'delete'"""
        data = {
            'action': 'delete',
            'refuge_id': 'ref_1'
        }
        serializer = RefugeProposalCreateSerializer(data=data)
        assert serializer.is_valid()

    def test_create_proposal_invalid_delete_with_payload(self):
        """Test RefugeProposalCreateSerializer per 'delete' amb payload (no permès)"""
        data = {
            'action': 'delete',
            'refuge_id': 'ref_1',
            'payload': {'name': 'Should not be here'}
        }
        serializer = RefugeProposalCreateSerializer(data=data)
        assert not serializer.is_valid()

    def test_response_serializer_valid(self):
        """Test RefugeProposalResponseSerializer amb dades vàlides"""
        data = {
            'id': 'prop_1',
            'refuge_id': None,
            'action': 'create',
            'payload': {'name': 'New'},
            'comment': 'Test',
            'status': 'pending',
            'creator_uid': 'user_1',
            'created_at': '2024-01-01',
            'reviewer_uid': None,
            'reviewed_at': None
        }
        serializer = RefugeProposalResponseSerializer(data=data)
        assert serializer.is_valid()
