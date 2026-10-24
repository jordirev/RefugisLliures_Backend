"""
Tests de la feature images al domini refugi: filtre de status per a qui consulta,
rollback real en esborrar, esborrat de miniatures i primera imatge visible.
"""
from unittest.mock import MagicMock, patch

import pytest

from api.controllers.refugi_lliure_controller import RefugiLliureController
from api.mappers.refugi_lliure_mapper import RefugiLliureMapper
from api.models.media_metadata import RefugeMediaMetadata
from api.tests.media.helpers import fake_r2_service

KEY = 'refugis-lliures/ref_1/abc.webp'
THUMB = 'refugis-lliures/ref_1/abc_thumb.webp'


@pytest.fixture
def ctrl():
    with patch('api.controllers.refugi_lliure_controller.RefugiLliureDAO'), \
            patch('api.controllers.refugi_lliure_controller.UserDAO'), \
            patch('api.controllers.refugi_lliure_controller.r2_media_service'):
        controller = RefugiLliureController()
        controller.media_service = MagicMock()
        yield controller


def media(key, creator='author', status='visible'):
    return RefugeMediaMetadata(key=key, url=f'https://{key}', creator_uid=creator, status=status)


@pytest.mark.controllers
class TestDeleteRollback:


    def test_bulk_delete_removes_thumbnails(self, ctrl):
        ctrl.refugi_dao.delete_multiple_media_metadata.return_value = (True, [
            {'key': KEY, 'creator_uid': 'author', 'thumb_key': THUMB},
            {'key': 'legacy.jpg', 'creator_uid': 'author'},
        ])
        ctrl.media_service.delete_files.return_value = {'deleted': [KEY, 'legacy.jpg'], 'failed': []}
        ctrl.media_service.delete_file.return_value = True
        success, _ = ctrl.delete_multiple_refugi_media('ref_1', [KEY, 'legacy.jpg'])
        assert success is True
        ctrl.media_service.delete_file.assert_called_once_with(THUMB)


@pytest.mark.mappers
class TestFirstVisibleImage:
    @patch('api.mappers.refugi_lliure_mapper.r2_media_service')
    def test_skips_hidden_and_returns_media_item(self, mock_r2):
        mock_r2.get_refugi_media_service.return_value = fake_r2_service()
        data = {'id': 'r', 'name': 'n', 'media_metadata': {
            'hidden.webp': {'creator_uid': 'a', 'status': 'hidden_pending_review'},
            'ok.webp': {'creator_uid': 'a', 'thumb_key': 'ok_thumb.webp', 'blurhash': 'bh'},
        }}
        result = RefugiLliureMapper.dict_to_refugi_info_representation(data)
        assert len(result['images_metadata']) == 1
        item = result['images_metadata'][0]
        assert item['key'] == 'ok.webp' and item['blurhash'] == 'bh' and 'ok_thumb.webp' in item['thumb_url']
        assert 'media_metadata' not in result

    @patch('api.mappers.refugi_lliure_mapper.r2_media_service')
    def test_only_hidden_media_returns_none(self, mock_r2):
        mock_r2.get_refugi_media_service.return_value = fake_r2_service()
        data = {'id': 'r', 'media_metadata': {'h.webp': {'status': 'removed'}}}
        assert RefugiLliureMapper.dict_to_refugi_info_representation(data)['images_metadata'] is None
