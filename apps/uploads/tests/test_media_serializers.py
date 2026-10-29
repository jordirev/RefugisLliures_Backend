"""
Tests del serializer de mitjans (MediaItem)
"""
import pytest

from apps.uploads.media_metadata import MediaMetadata
from apps.uploads.media_serializer import MediaItemSerializer
from apps.refuges.serializers import RefugiSerializer

PUBLIC_FIELDS = {'key', 'url', 'thumb_url', 'media_type', 'width', 'height', 'blurhash',
                 'creator_uid', 'uploaded_at', 'taken_at', 'experience_id'}


@pytest.mark.serializers
class TestMediaItemSerializer:
    def test_legacy_dict_backfills_contract_fields(self):
        data = MediaItemSerializer({'key': 'a/b.mov', 'url': 'https://u', 'creator_uid': 'c', 'uploaded_at': 't'}).data
        assert set(data) == PUBLIC_FIELDS
        assert data['thumb_url'] == 'https://u' and data['media_type'] == 'video'
        assert data['width'] is None and data['taken_at'] is None and data['experience_id'] is None

    def test_model_instance(self):
        item = MediaMetadata(key='k.webp', url='u', thumb_url='t', media_type='image', width=1, height=2,
                             blurhash='b', creator_uid='c', uploaded_at='x', taken_at='y', experience_id='e')
        assert MediaItemSerializer(item).data == item.to_dict()

    def test_refuge_detail_images_metadata_shape(self):
        refugi = {'id': 'r', 'name': 'n', 'coord': {'long': 1.0, 'lat': 2.0}, 'info_comp': {},
                  'images_metadata': [{'key': 'old.jpg', 'url': 'https://old', 'creator_uid': 'c', 'uploaded_at': 't'}]}
        data = RefugiSerializer(refugi, context={'is_authenticated': True}).data
        assert set(data['images_metadata'][0]) == PUBLIC_FIELDS
        assert data['images_metadata'][0]['thumb_url'] == 'https://old'
