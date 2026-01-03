"""
Tests per als serializers de propostes de refugi
"""
import pytest
from api.serializers.refuge_proposal_serializer import (
    RefugeProposalCreateSerializer, RefugeProposalResponseSerializer,
    RefugeProposalRejectSerializer, RefugeProposalPayloadSerializer
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

    # ===== TESTS ADICIONALS PER MILLORAR COVERAGE =====

    def test_payload_serializer_forbidden_fields_via_create(self):
        """Test RefugeProposalCreateSerializer amb camps prohibits al payload"""
        data = {
            'action': 'create',
            'payload': {
                'name': 'New Refuge',
                'coord': {'lat': 42.0, 'long': 1.0},
                'images_metadata': [{'key': 'test.jpg'}]  # Camp prohibit
            }
        }
        serializer = RefugeProposalCreateSerializer(data=data)
        assert not serializer.is_valid()
        # El payload serializer ha de rebutjar-ho

    def test_payload_serializer_info_comp_valid(self):
        """Test RefugeProposalPayloadSerializer amb info_comp vàlid"""
        data = {
            'name': 'Test Refuge',
            'coord': {'lat': 42.0, 'long': 1.0},
            'info_comp': {
                'cheminee': 1,
                'eau': 1,
                'bois': 0
            }
        }
        serializer = RefugeProposalPayloadSerializer(data=data)
        assert serializer.is_valid()

    def test_create_proposal_create_with_refuge_id(self):
        """Test RefugeProposalCreateSerializer per 'create' amb refuge_id (no permès)"""
        data = {
            'action': 'create',
            'refuge_id': 'ref_1',  # No hauria d'estar present per create
            'payload': {
                'name': 'New Refuge',
                'coord': {'lat': 42.0, 'long': 1.0}
            }
        }
        serializer = RefugeProposalCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert 'refuge_id' in serializer.errors

    def test_create_proposal_update_missing_refuge_id(self):
        """Test RefugeProposalCreateSerializer per 'update' sense refuge_id"""
        data = {
            'action': 'update',
            'payload': {
                'places': 20
            }
        }
        serializer = RefugeProposalCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert 'refuge_id' in serializer.errors

    def test_create_proposal_update_missing_payload(self):
        """Test RefugeProposalCreateSerializer per 'update' sense payload"""
        data = {
            'action': 'update',
            'refuge_id': 'ref_1'
        }
        serializer = RefugeProposalCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert 'payload' in serializer.errors

    def test_create_proposal_delete_missing_refuge_id(self):
        """Test RefugeProposalCreateSerializer per 'delete' sense refuge_id"""
        data = {
            'action': 'delete'
        }
        serializer = RefugeProposalCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert 'refuge_id' in serializer.errors

    def test_create_proposal_payload_unknown_fields(self):
        """Test RefugeProposalCreateSerializer amb camps desconeguts al payload"""
        data = {
            'action': 'create',
            'payload': {
                'name': 'New Refuge',
                'coord': {'lat': 42.0, 'long': 1.0},
                'unknown_field': 'value'
            }
        }
        serializer = RefugeProposalCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert 'payload' in serializer.errors

    def test_create_proposal_payload_info_comp_unknown_fields(self):
        """Test RefugeProposalCreateSerializer amb camps desconeguts en info_comp del payload"""
        data = {
            'action': 'update',
            'refuge_id': 'ref_1',
            'payload': {
                'info_comp': {
                    'unknown_info_field': 'value'
                }
            }
        }
        serializer = RefugeProposalCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert 'payload' in serializer.errors

    def test_reject_serializer_valid(self):
        """Test RefugeProposalRejectSerializer amb dades vàlides"""
        data = {
            'comment': 'Rejected because of invalid data'
        }
        serializer = RefugeProposalRejectSerializer(data=data)
        assert serializer.is_valid()

    def test_reject_serializer_without_comment(self):
        """Test RefugeProposalRejectSerializer sense comentari (opcional)"""
        data = {}
        serializer = RefugeProposalRejectSerializer(data=data)
        assert serializer.is_valid()

    def test_create_proposal_create_missing_name(self):
        """Test RefugeProposalCreateSerializer per 'create' sense name"""
        data = {
            'action': 'create',
            'payload': {
                'coord': {'lat': 42.0, 'long': 1.0}
                # name és obligatori per create
            }
        }
        serializer = RefugeProposalCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert 'payload' in serializer.errors

    def test_create_proposal_create_missing_coord(self):
        """Test RefugeProposalCreateSerializer per 'create' sense coord"""
        data = {
            'action': 'create',
            'payload': {
                'name': 'Test Refuge'
                # coord és obligatori per create
            }
        }
        serializer = RefugeProposalCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert 'payload' in serializer.errors

    def test_create_proposal_create_empty_name(self):
        """Test RefugeProposalCreateSerializer per 'create' amb name buit"""
        data = {
            'action': 'create',
            'payload': {
                'name': '',  # Buit, no vàlid
                'coord': {'lat': 42.0, 'long': 1.0}
            }
        }
        serializer = RefugeProposalCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert 'payload' in serializer.errors
