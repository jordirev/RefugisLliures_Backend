"""
Tests dels serveis nous: ModerationService/HashBlocklistProvider, AuditLogService i les
operacions noves de R2MediaService (presigned PUT, head/get/put/copy/move, claus UUID).
"""
import re
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest

from api.services.moderation_service import (
    ModerationService, HashBlocklistProvider, PhotoDNAProvider, GoogleContentSafetyProvider,
    ModerationInput, ModerationResult, phash_distance,
)
from api.services.audit_log_service import AuditLogService, AUDIT_RETENTION_DAYS
from api.services.r2_media_service import (
    R2MediaService, RefugiMediaStrategy, UserAvatarStrategy, quarantine_key, moderation_hold_key,
)
from api.tests.media.helpers import fake_r2_service


def stream_doc(data, doc_id='d'):
    d = MagicMock()
    d.id = doc_id
    d.to_dict.return_value = data
    return d


@pytest.mark.unit
class TestModerationService:
    def test_disabled_stubs_are_skipped(self):
        assert PhotoDNAProvider().enabled is False
        assert GoogleContentSafetyProvider().enabled is False
        service = ModerationService([PhotoDNAProvider(), GoogleContentSafetyProvider()])
        assert service.check(ModerationInput(sha256='x')).blocked is False

    def test_first_blocking_provider_wins(self):
        clean, dirty = MagicMock(enabled=True), MagicMock(enabled=True)
        clean.check.return_value = ModerationResult(False)
        dirty.check.return_value = ModerationResult(True, 'p', 'csam', 'sha256')
        result = ModerationService([clean, dirty]).check(ModerationInput(sha256='x'))
        assert result.blocked and result.provider == 'p'

    def test_provider_error_propagates(self):
        bad = MagicMock(enabled=True)
        bad.check.side_effect = RuntimeError('down')
        with pytest.raises(RuntimeError):
            ModerationService([bad]).check(ModerationInput(sha256='x'))

    def test_phash_distance(self):
        assert phash_distance('ffffffffffffffff', 'ffffffffffffffff') == 0
        assert phash_distance('0000000000000000', '000000000000000f') == 4
        assert phash_distance('zz', '00') == 64

    @patch('api.services.moderation_service.cache_service')
    @patch('api.services.moderation_service.FirestoreService')
    def test_hash_blocklist_sha256_match(self, mock_fs, mock_cache):
        db = mock_fs.return_value.get_db.return_value
        db.collection.return_value.where.return_value.limit.return_value.stream.return_value = [
            stream_doc({'sha256': 'abc', 'category': 'csam'}, 'e1')]
        result = HashBlocklistProvider().check(ModerationInput(sha256='abc', phash='0' * 16))
        assert result.blocked and result.match_type == 'sha256' and result.details == {'entry_id': 'e1'}

    @patch('api.services.moderation_service.cache_service')
    @patch('api.services.moderation_service.FirestoreService')
    def test_hash_blocklist_phash_near_match(self, mock_fs, mock_cache):
        db = mock_fs.return_value.get_db.return_value
        db.collection.return_value.where.return_value.limit.return_value.stream.return_value = []
        mock_cache.get.return_value = None
        db.collection.return_value.stream.return_value = [
            stream_doc({'phash': 'ffff0000ffff0000', 'category': 'csam'}, 'p1'),
            stream_doc({'sha256': 'only-sha'}, 'p2'),
        ]
        provider = HashBlocklistProvider()
        assert provider.check(ModerationInput(sha256='zzz', phash='ffff0000ffff0003')).blocked is True  # 2 bits
        mock_cache.set.assert_called_once()
        mock_cache.get.return_value = [{'id': 'p1', 'phash': 'ffff0000ffff0000', 'category': 'csam'}]
        assert provider.check(ModerationInput(sha256='zzz', phash='0000ffff0000ffff')).blocked is False


@pytest.mark.unit
class TestAuditLogService:
    @pytest.mark.real_audit_log
    @patch('api.services.audit_log_service.FirestoreService')
    def test_writes_entry_with_ttl(self, mock_fs):
        db = mock_fs.return_value.get_db.return_value
        assert AuditLogService().log('u1', 'media.upload_confirm', 'refuge', 'k', {'a': 1}) is True
        entry = db.collection.return_value.add.call_args.args[0]
        db.collection.assert_called_with('audit_logs')
        assert entry['actor_uid'] == 'u1' and entry['action'] == 'media.upload_confirm'
        assert entry['target_type'] == 'refuge' and entry['target_id'] == 'k' and entry['metadata'] == {'a': 1}
        delta = entry['expire_at'] - __import__('datetime').datetime.fromisoformat(entry['timestamp'])
        assert delta == timedelta(days=AUDIT_RETENTION_DAYS)

    @pytest.mark.real_audit_log
    @patch('api.services.audit_log_service.FirestoreService')
    def test_never_raises(self, mock_fs):
        mock_fs.return_value.get_db.side_effect = Exception('down')
        assert AuditLogService().log(None, 'x') is False

    @pytest.mark.real_audit_log
    @patch('api.services.audit_log_service.FirestoreService')
    def test_system_actor(self, mock_fs):
        AuditLogService().log(None, 'x')
        assert mock_fs.return_value.get_db.return_value.collection.return_value.add.call_args.args[0]['actor_uid'] == 'system'


@pytest.mark.unit
class TestR2MediaServiceNewOps:
    def test_upload_file_ignores_filename_and_uses_uuid(self):
        service = fake_r2_service()
        result = service.upload_file(b'data', 'ref_1', 'image/jpeg', filename='IMG_0001.jpg')
        assert re.fullmatch(r'refugis-lliures/ref_1/[0-9a-f-]{36}\.jpg', result['key'])
        assert 'IMG_0001' not in result['key']

    def test_build_media_key(self):
        service = fake_r2_service()
        key = service.build_media_key('ref_1', 'webp', suffix='_thumb', media_id='abc')
        assert key == 'refugis-lliures/ref_1/abc_thumb.webp'
        avatar = fake_r2_service(UserAvatarStrategy())
        assert re.fullmatch(r'users-avatars/u1/[0-9a-f-]{36}\.webp', avatar.build_media_key('u1', '.webp'))

    def test_presigned_put_signs_type_and_length(self):
        service = R2MediaService(RefugiMediaStrategy())
        url = service.generate_presigned_put_url('quarantine/x', 'image/webp', 1234, 600)
        assert 'quarantine/x' in url
        assert 'X-Amz-Expires=600' in url
        signed = re.search(r'X-Amz-SignedHeaders=([^&]+)', url).group(1)
        assert 'content-length' in signed and 'content-type' in signed

    def test_head_get_put_copy_move_delete(self):
        service = fake_r2_service(objects={'a': b'12345'})
        assert service.head_object('a') == {'size': 5, 'content_type': 'application/octet-stream'}
        assert service.head_object('missing') is None
        assert service.get_object_bytes('a') == b'12345'
        assert service.get_object_bytes('a', max_bytes=2) == b'123'
        assert service.get_object_bytes('missing') is None
        service.put_bytes('b', b'x', 'image/webp')
        assert service.client.put_object.call_args.kwargs['CacheControl'].startswith('private')
        assert service.copy_object('a', 'c') and service.store['c'] == b'12345'
        assert service.move_object('a', 'd') and 'a' not in service.store
        assert service.delete_file('d') is True

    def test_copy_failure(self):
        from botocore.exceptions import ClientError
        service = fake_r2_service()
        service.client.copy_object.side_effect = ClientError({'Error': {'Code': '500'}}, 'CopyObject')
        assert service.copy_object('a', 'b') is False
        assert service.move_object('a', 'b') is False

    def test_head_other_errors_raise(self):
        from botocore.exceptions import ClientError
        service = fake_r2_service()
        service.client.head_object.side_effect = ClientError({'Error': {'Code': '403'}}, 'HeadObject')
        with pytest.raises(ClientError):
            service.head_object('x')

    def test_media_item_from_strategy(self):
        service = fake_r2_service()
        item = service.generate_media_metadata_from_dict({'k.webp': {'creator_uid': 'u', 'thumb_key': 'k_thumb.webp'}})
        data = item.to_dict()
        assert data['thumb_url'].startswith('https://r2.test/k_thumb.webp')
        legacy = service.generate_media_metadata_from_dict({'k.jpg': {'creator_uid': 'u'}}).to_dict()
        assert legacy['thumb_url'] == legacy['url']
        avatar = fake_r2_service(UserAvatarStrategy()).generate_media_metadata_from_dict({'key': 'a.webp', 'width': 512})
        assert avatar.to_dict()['media_type'] == 'image' and avatar.width == 512

    def test_key_helpers(self):
        assert quarantine_key('x') == 'quarantine/x'
        assert moderation_hold_key('refugis-lliures/r/k.webp') == 'moderation-hold/refugis-lliures/r/k.webp'
