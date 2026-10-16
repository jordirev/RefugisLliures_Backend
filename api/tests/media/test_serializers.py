"""
Tests dels serializers de mitjans (MediaItem i peticions noves)
"""
from unittest.mock import MagicMock, patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIRequestFactory, force_authenticate

from api.models.media_metadata import MediaMetadata
from api.models.user import User
from api.serializers.media_serializer import (
    MediaItemSerializer, UploadIntentCreateSerializer, MediaReportCreateSerializer, MediaReportResolveSerializer,
)
from api.serializers.refugi_lliure_serializer import RefugiSerializer

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


@pytest.mark.serializers
class TestRequestSerializers:
    def test_intent_normalizes_content_type(self):
        s = UploadIntentCreateSerializer(data={'target': 'refuge', 'refuge_id': 'r', 'rights_confirmed': True,
                                               'files': [{'content_type': 'image/jpg', 'size': 10}]})
        assert s.is_valid(), s.errors
        assert s.validated_data['files'][0]['content_type'] == 'image/jpeg'

    def test_intent_video_limit_ok(self):
        s = UploadIntentCreateSerializer(data={'target': 'refuge', 'refuge_id': 'r', 'rights_confirmed': True,
                                               'files': [{'content_type': 'video/webm', 'size': 50 * 1024 * 1024}]})
        assert s.is_valid(), s.errors

    def test_report_other_with_details(self):
        s = MediaReportCreateSerializer(data={'refuge_id': 'r', 'media_key': 'k', 'reason': 'other', 'details': 'x'})
        assert s.is_valid(), s.errors

    def test_resolve(self):
        assert MediaReportResolveSerializer(data={'action': 'remove', 'statement': 'ok'}).is_valid()
        assert not MediaReportResolveSerializer(data={'action': 'remove', 'statement': 'x' * 2001}).is_valid()


@pytest.mark.views
class TestLegacyUploadBlocked:
    @pytest.mark.real_permissions
    @patch('api.permissions.get_user_for_permissions')
    @patch('api.views.refugi_media_views.RefugiLliureController')
    def test_blocked_user_cannot_use_legacy_multipart(self, mock_ctrl, mock_lookup):
        from api.views.refugi_media_views import RefugiMediaAPIView
        mock_lookup.return_value = User(uid='u1', username='u', is_blocked=True)
        request = APIRequestFactory().post('/x', {'files': [SimpleUploadedFile('a.jpg', b'x', 'image/jpeg')]}, format='multipart')
        force_authenticate(request, user=MagicMock(is_authenticated=True, uid='u1', claims={}))
        request.user_uid = 'u1'
        response = RefugiMediaAPIView.as_view()(request, id='ref_1')
        assert response.status_code == 403 and response.data['error'] == 'user_blocked'
        mock_ctrl.return_value.upload_refugi_media.assert_not_called()

    @pytest.mark.real_permissions
    @patch('api.permissions.get_user_for_permissions')
    @patch('api.views.refugi_media_views.RefugiLliureController')
    def test_blocked_user_can_still_list(self, mock_ctrl, mock_lookup):
        from api.views.refugi_media_views import RefugiMediaAPIView
        mock_lookup.return_value = User(uid='u1', username='u', is_blocked=True)
        mock_ctrl.return_value.get_refugi_media.return_value = ([], None)
        request = APIRequestFactory().get('/x')
        force_authenticate(request, user=MagicMock(is_authenticated=True, uid='u1', claims={}))
        assert RefugiMediaAPIView.as_view()(request, id='ref_1').status_code == 200
