"""
Tests de la inferència del tipus de mitjà (`infer_media_type`)
"""
import pytest

from apps.uploads.media_metadata import infer_media_type


@pytest.mark.models
class TestInferMediaType:
    def test_infer_media_type(self):
        assert infer_media_type('a/b.MOV') == 'video'
        assert infer_media_type('a/b.webp') == 'image'
        assert infer_media_type('a/b', 'video/webm') == 'video'
        assert infer_media_type('a/b.mp4', 'image/jpeg') == 'image'
        assert infer_media_type(None) == 'image'
