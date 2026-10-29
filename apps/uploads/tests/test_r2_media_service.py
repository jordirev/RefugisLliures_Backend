"""
Tests de les operacions de R2MediaService (presigned PUT, head/get/put/copy/move, claus UUID).
"""
import re
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest

from apps.uploads.r2_media_service import (
    R2MediaService, RefugiMediaStrategy, UserAvatarStrategy, quarantine_key, moderation_hold_key,
)
from apps.uploads.tests.media_helpers import fake_r2_service


@pytest.fixture(autouse=True)
def r2store():
    """Sobreescriu l'autouse del conftest de l'app: aquí es proven el client real (URL prefirmada local, sense xarxa)
    i els fakes de `fake_r2_service`."""
    yield None


@pytest.mark.unit
class TestR2MediaServiceNewOps:
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

    def test_key_helpers(self):
        assert quarantine_key('x') == 'quarantine/x'
        assert moderation_hold_key('refugis-lliures/r/k.webp') == 'moderation-hold/refugis-lliures/r/k.webp'
