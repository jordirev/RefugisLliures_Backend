"""
Tests del serializer de mitjans (MediaItem)
"""
import pytest

from apps.uploads.serializers import MediaItemSerializer

PUBLIC_FIELDS = {'key', 'url', 'thumb_url', 'media_type', 'width', 'height', 'blurhash',
                 'creator_uid', 'uploaded_at', 'taken_at', 'experience_id'}


@pytest.mark.serializers
class TestMediaItemSerializer:
    def test_full_dict_roundtrip(self):
        item = {'key': 'k.webp', 'url': 'u', 'thumb_url': 't', 'media_type': 'image', 'width': 1, 'height': 2,
                'blurhash': 'b', 'creator_uid': 'c', 'uploaded_at': 'x', 'taken_at': 'y', 'experience_id': 'e'}
        assert dict(MediaItemSerializer(item).data) == item
