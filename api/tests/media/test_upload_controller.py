"""
Tests de MediaUploadController: intents, confirmació, publicació, rollbacks i moderació.
S'usa el processament REAL (Pillow/ffmpeg) i un R2MediaService real amb el client mockat.
"""
import io
import re
from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from PIL import Image

from api.controllers.media_upload_controller import (
    MediaUploadController, ERROR_NOT_OWNER, ERROR_REFUGE_NOT_FOUND, ERROR_EXPERIENCE_NOT_FOUND,
)
from api.models.experience import Experience
from api.models.media_metadata import MediaMetadata
from api.models.upload_intent import UploadIntent
from apps.accounts.models import UserAvatar
from api.services.moderation_service import ModerationResult
from api.services.image_processing_service import IMAGE_MAX_BYTES
from api.utils.timezone_utils import get_madrid_now
from api.tests.media.helpers import make_jpeg_with_gps, make_png, fake_r2_service, fake_avatar_service, GPS_IFD

UUID_RE = r'[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}'


@pytest.fixture
def ctrl():
    controller = MediaUploadController()
    controller.intent_dao = MagicMock()
    controller.refugi_dao = MagicMock()
    controller.accounts = MagicMock()
    controller.account_selectors = MagicMock()
    controller.account_selectors.get_avatar.return_value = None
    controller.experience_dao = MagicMock()
    controller.report_dao = MagicMock()
    controller.notice_dao = MagicMock()
    controller.moderation_service = MagicMock()
    controller.moderation_service.check.return_value = ModerationResult(False)
    controller.refugi_media_service = fake_r2_service()
    controller.avatar_service = fake_avatar_service()
    controller.intent_dao.new_id.side_effect = ['up_1', 'up_2', 'up_3']
    controller.intent_dao.create_intents.return_value = True
    controller.refugi_dao.refugi_exists.return_value = True
    controller.refugi_dao.add_media_metadata.return_value = True
    controller.refugi_dao.delete_media_metadata.return_value = (True, {})
    controller.experience_dao.add_media_keys_to_experience.return_value = (True, None)
    return controller


def make_intent(**overrides):
    now = get_madrid_now()
    data = dict(id='up_1', uid='user_1', target='refuge', content_type='image/jpeg', size=1000,
                quarantine_key='quarantine/up_1', refuge_id='ref_1', created_at=now.isoformat(),
                expire_at=now + timedelta(days=1), rights_confirmed_at=now.isoformat())
    data.update(overrides)
    return UploadIntent(**data)


@pytest.mark.controllers
class TestCreateUploadIntents:
    def test_refuge_intents(self, ctrl):
        files = [{'content_type': 'image/jpg', 'size': 1234}, {'content_type': 'video/mp4', 'size': 5000}]
        result, error = ctrl.create_upload_intents('user_1', 'refuge', files, refuge_id='ref_1')

        assert error is None
        uploads = result['uploads']
        assert [u['upload_id'] for u in uploads] == ['up_1', 'up_2']
        assert uploads[0]['headers'] == {'Content-Type': 'image/jpeg'}
        assert uploads[0]['expires_in'] == 600
        assert 'quarantine/up_1' in uploads[0]['put_url']
        # La URL PUT signa Content-Type i Content-Length
        params = ctrl.refugi_media_service.client.generate_presigned_url.call_args_list[0]
        assert params.args[0] == 'put_object'
        assert params.kwargs['Params'] == {'Bucket': 'test-bucket', 'Key': 'quarantine/up_1',
                                           'ContentType': 'image/jpeg', 'ContentLength': 1234}
        assert params.kwargs['ExpiresIn'] == 600
        intents = ctrl.intent_dao.create_intents.call_args.args[0]
        assert intents[0].uid == 'user_1' and intents[0].refuge_id == 'ref_1'
        assert intents[0].rights_confirmed_at
        assert intents[0].expire_at > get_madrid_now()

    def test_refuge_not_found(self, ctrl):
        ctrl.refugi_dao.refugi_exists.return_value = False
        result, error = ctrl.create_upload_intents('u', 'refuge', [{'content_type': 'image/png', 'size': 1}], refuge_id='x')
        assert result is None and error == ERROR_REFUGE_NOT_FOUND

    def test_experience_not_owner(self, ctrl):
        ctrl.experience_dao.get_experience_by_id.return_value = Experience(
            id='exp_1', refuge_id='ref_1', creator_uid='other', modified_at='', comment='c')
        result, error = ctrl.create_upload_intents('user_1', 'experience', [{'content_type': 'image/png', 'size': 1}],
                                                   experience_id='exp_1')
        assert error == ERROR_NOT_OWNER

    def test_experience_admin_allowed_and_refuge_from_experience(self, ctrl):
        ctrl.experience_dao.get_experience_by_id.return_value = Experience(
            id='exp_1', refuge_id='ref_9', creator_uid='other', modified_at='', comment='c')
        result, error = ctrl.create_upload_intents('admin', 'experience', [{'content_type': 'image/png', 'size': 1}],
                                                   experience_id='exp_1', is_admin=True)
        assert error is None
        intent = ctrl.intent_dao.create_intents.call_args.args[0][0]
        assert intent.refuge_id == 'ref_9' and intent.experience_id == 'exp_1'

    def test_experience_not_found_and_mismatch(self, ctrl):
        ctrl.experience_dao.get_experience_by_id.return_value = None
        _, error = ctrl.create_upload_intents('u', 'experience', [{'content_type': 'image/png', 'size': 1}], experience_id='e')
        assert error == ERROR_EXPERIENCE_NOT_FOUND
        ctrl.experience_dao.get_experience_by_id.return_value = Experience(
            id='e', refuge_id='ref_1', creator_uid='u', modified_at='', comment='c')
        _, error = ctrl.create_upload_intents('u', 'experience', [{'content_type': 'image/png', 'size': 1}],
                                              experience_id='e', refuge_id='other_ref')
        assert error.startswith('invalid:')

    def test_avatar_intent(self, ctrl):
        result, error = ctrl.create_upload_intents('user_1', 'avatar', [{'content_type': 'image/heic', 'size': 10}])
        assert error is None
        intent = ctrl.intent_dao.create_intents.call_args.args[0][0]
        assert intent.target == 'avatar' and intent.refuge_id is None

    def test_firestore_failure(self, ctrl):
        ctrl.intent_dao.create_intents.return_value = False
        result, error = ctrl.create_upload_intents('u', 'refuge', [{'content_type': 'image/png', 'size': 1}], refuge_id='r')
        assert result is None and 'Error intern' in error


@pytest.mark.controllers
class TestConfirmUploadIntents:
    def test_confirm_jpeg_publishes_clean_webp_with_uuid_keys(self, ctrl):
        data = make_jpeg_with_gps((1000, 800), orientation=1)
        ctrl.refugi_media_service.store['quarantine/up_1'] = data
        ctrl.intent_dao.get_intent.return_value = make_intent(size=len(data))

        result, error = ctrl.confirm_upload_intents('user_1', ['up_1'])

        assert error is None
        assert result['failed'] == []
        item = result['uploaded'][0]
        assert re.fullmatch(rf'refugis-lliures/ref_1/{UUID_RE}\.webp', item['key'])
        assert item['thumb_url'] != item['url'] and '_thumb.webp' in item['thumb_url']
        assert item['media_type'] == 'image'
        assert (item['width'], item['height']) == (1000, 800)
        assert item['taken_at'] == '2024-07-15T10:20:30+02:00'
        assert item['creator_uid'] == 'user_1' and item['experience_id'] is None
        assert set(item) == {'key', 'url', 'thumb_url', 'media_type', 'width', 'height', 'blurhash',
                             'creator_uid', 'uploaded_at', 'taken_at', 'experience_id'}

        store = ctrl.refugi_media_service.store
        assert 'quarantine/up_1' not in store  # quarantine esborrat
        published = Image.open(io.BytesIO(store[item['key']]))
        assert dict(published.getexif()) == {} and not published.getexif().get_ifd(GPS_IFD)
        thumb_key = item['key'].replace('.webp', '_thumb.webp')
        assert thumb_key in store

        metadata = ctrl.refugi_dao.add_media_metadata.call_args.args[1][item['key']]
        assert metadata['status'] == 'visible'
        assert metadata['taken_at'] == '2024-07-15T10:20:30+02:00'
        assert metadata['thumb_key'] == thumb_key
        assert metadata['rights_confirmed_at']
        ctrl.intent_dao.mark_confirmed.assert_called_once_with('up_1', item['key'])

    def test_non_image_bytes_declared_jpeg_is_invalid_type(self, ctrl):
        ctrl.refugi_media_service.store['quarantine/up_1'] = b'%PDF-1.5\n' + b'x' * 500
        ctrl.intent_dao.get_intent.return_value = make_intent()

        result, _ = ctrl.confirm_upload_intents('user_1', ['up_1'])

        assert result['uploaded'] == []
        assert result['failed'] == [{'upload_id': 'up_1', 'reason': 'invalid_type'}]
        assert 'quarantine/up_1' not in ctrl.refugi_media_service.store  # s'esborra de quarantine
        ctrl.intent_dao.mark_failed.assert_called_once_with('up_1', 'invalid_type')
        ctrl.refugi_dao.add_media_metadata.assert_not_called()

    def test_oversize_is_too_large(self, ctrl):
        ctrl.refugi_media_service.store['quarantine/up_1'] = b'\xff\xd8\xff' + b'0' * IMAGE_MAX_BYTES
        ctrl.intent_dao.get_intent.return_value = make_intent()

        result, _ = ctrl.confirm_upload_intents('user_1', ['up_1'])

        assert result['failed'] == [{'upload_id': 'up_1', 'reason': 'too_large'}]
        assert 'quarantine/up_1' not in ctrl.refugi_media_service.store
        ctrl.refugi_media_service.client.get_object.assert_not_called()

    def test_missing_object_and_foreign_intent(self, ctrl):
        ctrl.intent_dao.get_intent.side_effect = lambda i: {
            'up_1': make_intent(),
            'up_2': make_intent(id='up_2', uid='someone_else'),
        }.get(i)
        result, _ = ctrl.confirm_upload_intents('user_1', ['up_1', 'up_2', 'up_3', 'up_1'])
        assert result['failed'] == [
            {'upload_id': 'up_1', 'reason': 'missing_object'},
            {'upload_id': 'up_2', 'reason': 'missing_object'},
            {'upload_id': 'up_3', 'reason': 'missing_object'},
        ]
        ctrl.intent_dao.mark_failed.assert_not_called()  # el client encara pot repetir el PUT

    def test_expired_intent(self, ctrl):
        ctrl.refugi_media_service.store['quarantine/up_1'] = make_png((10, 10))
        ctrl.intent_dao.get_intent.return_value = make_intent(expire_at=get_madrid_now() - timedelta(seconds=1))
        result, _ = ctrl.confirm_upload_intents('user_1', ['up_1'])
        assert result['failed'][0]['reason'] == 'missing_object'

    def test_idempotent_reconfirm(self, ctrl):
        ctrl.intent_dao.get_intent.return_value = make_intent(status='confirmed', result_key='refugis-lliures/ref_1/k.webp')
        ctrl.refugi_dao.get_media_entry.return_value = (True, {'creator_uid': 'user_1', 'uploaded_at': 't', 'media_type': 'image'})
        result, _ = ctrl.confirm_upload_intents('user_1', ['up_1'])
        assert result['uploaded'][0]['key'] == 'refugis-lliures/ref_1/k.webp'
        assert result['failed'] == []

    def test_previously_failed_intent(self, ctrl):
        ctrl.intent_dao.get_intent.return_value = make_intent(status='failed', failure_reason='too_large')
        result, _ = ctrl.confirm_upload_intents('user_1', ['up_1'])
        assert result['failed'] == [{'upload_id': 'up_1', 'reason': 'too_large'}]

    def test_experience_target_links_media(self, ctrl):
        ctrl.refugi_media_service.store['quarantine/up_1'] = make_png((40, 40))
        ctrl.intent_dao.get_intent.return_value = make_intent(target='experience', experience_id='exp_1',
                                                              content_type='image/png')
        result, _ = ctrl.confirm_upload_intents('user_1', ['up_1'])
        item = result['uploaded'][0]
        assert item['experience_id'] == 'exp_1'
        ctrl.experience_dao.add_media_keys_to_experience.assert_called_once_with('exp_1', [item['key']])

    def test_firestore_failure_rolls_back_files(self, ctrl):
        ctrl.refugi_media_service.store['quarantine/up_1'] = make_png((40, 40))
        ctrl.intent_dao.get_intent.return_value = make_intent(content_type='image/png')
        ctrl.refugi_dao.add_media_metadata.return_value = False

        result, _ = ctrl.confirm_upload_intents('user_1', ['up_1'])

        assert result['failed'] == [{'upload_id': 'up_1', 'reason': 'processing_error'}]
        assert [k for k in ctrl.refugi_media_service.store if k.startswith('refugis-lliures/')] == []

    def test_moderation_error_fails_closed(self, ctrl):
        ctrl.refugi_media_service.store['quarantine/up_1'] = make_png((40, 40))
        ctrl.intent_dao.get_intent.return_value = make_intent(content_type='image/png')
        ctrl.moderation_service.check.side_effect = Exception('firestore down')
        result, _ = ctrl.confirm_upload_intents('user_1', ['up_1'])
        assert result['failed'][0]['reason'] == 'processing_error'
        ctrl.refugi_dao.add_media_metadata.assert_not_called()


@pytest.mark.controllers
class TestModerationBlock:
    def test_hash_match_blocks_user_and_holds_evidence(self, ctrl):
        data = make_png((40, 40))
        ctrl.refugi_media_service.store['quarantine/up_1'] = data
        ctrl.intent_dao.get_intent.return_value = make_intent(content_type='image/png')
        ctrl.moderation_service.check.return_value = ModerationResult(True, 'hash_blocklist', 'csam', 'sha256')

        result, _ = ctrl.confirm_upload_intents('user_1', ['up_1'])

        assert result['failed'] == [{'upload_id': 'up_1', 'reason': 'moderation_blocked'}]
        store = ctrl.refugi_media_service.store
        assert 'quarantine/up_1' not in store
        assert store['moderation-hold/user_1/up_1'] == data
        assert not any(k.startswith('refugis-lliures/') for k in store)
        ctrl.refugi_dao.add_media_metadata.assert_not_called()
        assert ctrl.accounts.set_blocked.call_args.args[:2] == ('user_1', True)
        report = ctrl.report_dao.create_report.call_args.args[0]
        assert report.reason == 'child_sexual_abuse'
        assert report.priority == 'high'
        assert report.reporter_uid == 'system' and report.media_creator_uid == 'user_1'
        assert report.media_key == 'moderation-hold/user_1/up_1'
        notice = ctrl.notice_dao.create_notice.call_args.args[0]
        assert notice['uid'] == 'user_1' and notice['type'] == 'account_blocked'
        ctrl.intent_dao.mark_failed.assert_called_once_with('up_1', 'moderation_blocked')

    def test_hash_match_on_legacy_path_stores_evidence(self, ctrl):
        ctrl.moderation_service.check.return_value = ModerationResult(True, 'hash_blocklist', 'csam', 'phash')
        item, reason = ctrl.process_and_publish(make_png((20, 20)), 'image/png', 'refuge', 'user_1', refuge_id='ref_1')
        assert item is None and reason == 'moderation_blocked'
        assert any(k.startswith('moderation-hold/user_1/') for k in ctrl.refugi_media_service.store)


@pytest.mark.controllers
class TestAvatarPublish:
    def test_new_avatar_saved_before_old_deleted(self, ctrl):
        old_key = 'users-avatars/user_1/old.jpg'
        ctrl.avatar_service.store[old_key] = b'old'
        ctrl.account_selectors.get_avatar.return_value = UserAvatar(key=old_key, user_id='user_1', content_type='image/jpeg')
        calls = []
        ctrl.accounts.update_avatar_metadata.side_effect = lambda uid, md: calls.append(('update', md['key'])) or True
        original_delete = ctrl.avatar_service.delete_file

        def tracking_delete(key):
            calls.append(('delete', key))
            return original_delete(key)
        ctrl.avatar_service.delete_file = tracking_delete

        item, reason = ctrl.process_and_publish(make_jpeg_with_gps((1500, 1500), orientation=1), 'image/jpeg', 'avatar', 'user_1')

        assert reason is None
        assert re.fullmatch(rf'users-avatars/user_1/{UUID_RE}\.webp', item['key'])
        assert item['width'] == 512 and item['creator_uid'] == 'user_1' and item['thumb_url'] == item['url']
        assert calls == [('update', item['key']), ('delete', old_key)]
        assert old_key not in ctrl.avatar_service.store
        published = Image.open(io.BytesIO(ctrl.avatar_service.store[item['key']]))
        assert dict(published.getexif()) == {}

    def test_old_avatar_kept_when_the_database_write_fails(self, ctrl):
        old_key = 'users-avatars/user_1/old.jpg'
        ctrl.avatar_service.store[old_key] = b'old'
        ctrl.account_selectors.get_avatar.return_value = UserAvatar(key=old_key, user_id='user_1', content_type='image/jpeg')
        ctrl.accounts.update_avatar_metadata.return_value = False

        item, reason = ctrl.process_and_publish(make_png((100, 100)), 'image/png', 'avatar', 'user_1')

        assert item is None and reason == 'processing_error'
        assert list(ctrl.avatar_service.store) == [old_key]  # l'antic es conserva i el nou s'esborra

    def test_avatar_confirm_via_intent(self, ctrl):
        ctrl.accounts.update_avatar_metadata.return_value = True
        ctrl.refugi_media_service.store['quarantine/up_1'] = make_png((600, 600))
        ctrl.intent_dao.get_intent.return_value = make_intent(target='avatar', refuge_id=None, content_type='image/png')
        result, _ = ctrl.confirm_upload_intents('user_1', ['up_1'])
        assert result['uploaded'][0]['key'].startswith('users-avatars/user_1/')
