"""Serializer de denúncia: el motiu `other` accepta `details`."""
import pytest

from apps.moderation.serializers import MediaReportCreateSerializer


@pytest.mark.serializers
class TestRequestSerializers:
    def test_report_other_with_details(self):
        s = MediaReportCreateSerializer(data={'refuge_id': 'r', 'media_key': 'k', 'reason': 'other', 'details': 'x'})
        assert s.is_valid(), s.errors
