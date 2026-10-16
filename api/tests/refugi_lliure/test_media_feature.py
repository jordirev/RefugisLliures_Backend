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
class TestVisibilityFilter:
    def test_detail_filters_hidden_for_others(self, ctrl):
        refugi = MagicMock()
        refugi.images_metadata = [media('a'), media('b', status='hidden_pending_review'), media('c', status='removed')]
        ctrl.refugi_dao.get_by_id.return_value = refugi
        result, _ = ctrl.get_refugi_by_id('ref_1', is_authenticated=True, viewer_uid='someone')
        assert [m.key for m in result.images_metadata] == ['a']

    def test_detail_author_and_admin_see_hidden(self, ctrl):
        refugi = MagicMock()
        refugi.images_metadata = [media('a'), media('b', status='hidden_pending_review')]
        ctrl.refugi_dao.get_by_id.return_value = refugi
        assert len(ctrl.get_refugi_by_id('ref_1', True, viewer_uid='author')[0].images_metadata) == 2
        refugi.images_metadata = [media('a'), media('b', status='hidden_pending_review')]
        assert len(ctrl.get_refugi_by_id('ref_1', True, viewer_uid='x', is_admin=True)[0].images_metadata) == 2

    def test_get_media_passes_viewer_and_audits(self, ctrl):
        ctrl.refugi_dao.get_media_metadata.return_value = [{'key': 'a'}]
        with patch('api.services.audit_log_service.AuditLogService.log') as audit:
            items, error = ctrl.get_refugi_media('ref_1', 3600, viewer_uid='v', is_admin=False)
        assert items == [{'key': 'a'}] and error is None
        ctrl.refugi_dao.get_media_metadata.assert_called_once_with('ref_1', viewer_uid='v', is_admin=False)
        assert audit.call_args.args[1] == 'media.list'


@pytest.mark.controllers
class TestDeleteRollback:
    def test_delete_file_false_restores_metadata(self, ctrl):
        """delete_file retorna False (no llança): abans es reportava èxit"""
        backup = {'creator_uid': 'author', 'experience_id': 'exp_1', 'thumb_key': THUMB}
        ctrl.refugi_dao.delete_media_metadata.return_value = (True, backup)
        ctrl.media_service.delete_file.return_value = False

        with patch('api.daos.experience_dao.ExperienceDAO') as mock_exp:
            success, error = ctrl.delete_refugi_media('ref_1', KEY)

        assert success is False and 'storage' in error
        ctrl.refugi_dao.add_media_metadata.assert_called_once_with('ref_1', {KEY: backup})
        mock_exp.return_value.add_media_keys_to_experience.assert_called_once_with('exp_1', [KEY])
        ctrl.user_dao.remove_uploaded_photos_keys.assert_not_called()

    def test_delete_success_removes_thumbnail(self, ctrl):
        ctrl.refugi_dao.delete_media_metadata.return_value = (True, {'creator_uid': 'author', 'thumb_key': THUMB})
        ctrl.media_service.delete_file.return_value = True
        success, error = ctrl.delete_refugi_media('ref_1', KEY, actor_uid='author')
        assert success is True and error is None
        assert [c.args[0] for c in ctrl.media_service.delete_file.call_args_list] == [KEY, THUMB]
        ctrl.user_dao.remove_uploaded_photos_keys.assert_called_once_with('author', [KEY])

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
