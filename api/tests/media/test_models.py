"""
Tests dels models de mitjans: MediaItem (MediaMetadata), UploadIntent, MediaReport, ModerationNotice
"""
import pytest

from api.models.media_metadata import MediaMetadata, RefugeMediaMetadata, infer_media_type
from api.models.media_report import MediaReport, build_report_id, AUTO_HIDE_REASONS, REPORT_REASONS
from api.models.moderation_notice import ModerationNotice, REDRESS_TEXT

PUBLIC_FIELDS = {'key', 'url', 'thumb_url', 'media_type', 'width', 'height', 'blurhash',
                 'creator_uid', 'uploaded_at', 'taken_at', 'experience_id'}


@pytest.mark.models
class TestMediaItem:
    def test_legacy_item_backward_compatible(self):
        item = RefugeMediaMetadata.from_stored('refugis-lliures/r/IMG_1.jpg',
                                               {'creator_uid': 'u', 'uploaded_at': 't'}, 'https://u')
        data = item.to_dict()
        assert set(data) == PUBLIC_FIELDS
        assert data['thumb_url'] == 'https://u'
        assert data['media_type'] == 'image'
        assert data['width'] is None and data['blurhash'] is None and data['taken_at'] is None
        assert data['experience_id'] is None
        assert item.status == 'visible'

    def test_full_item_and_internal_fields_hidden(self):
        stored = {'creator_uid': 'u', 'uploaded_at': 't', 'taken_at': 'tt', 'experience_id': 'e',
                  'media_type': 'video', 'width': 10, 'height': 20, 'blurhash': 'bh', 'size': 99,
                  'thumb_key': 'k_thumb.webp', 'status': 'hidden_pending_review', 'rights_confirmed_at': 'r',
                  'content_type': 'video/mp4'}
        item = MediaMetadata.from_stored('k.mp4', stored, 'https://k', 'https://thumb')
        data = item.to_dict()
        assert set(data) == PUBLIC_FIELDS
        assert data['thumb_url'] == 'https://thumb' and data['media_type'] == 'video'
        assert 'status' not in data and 'size' not in data and 'thumb_key' not in data
        assert item.to_firestore_dict() == stored

    def test_visibility(self):
        item = MediaMetadata(key='k', url='u', creator_uid='author', status='hidden_pending_review')
        assert not item.is_visible_to(None)
        assert not item.is_visible_to('other')
        assert item.is_visible_to('author')
        assert item.is_visible_to('other', is_admin=True)
        assert MediaMetadata(key='k', url='u').is_visible_to(None)

    def test_infer_media_type(self):
        assert infer_media_type('a/b.MOV') == 'video'
        assert infer_media_type('a/b.webp') == 'image'
        assert infer_media_type('a/b', 'video/webm') == 'video'

    def test_from_dict_public_shape(self):
        item = MediaMetadata.from_dict({'key': 'k', 'url': 'u', 'thumb_url': 't', 'width': 3})
        assert item.thumb_url == 't' and item.width == 3


@pytest.mark.models
class TestMediaReport:
    def test_reasons_enum(self):
        assert len(REPORT_REASONS) == 16
        assert AUTO_HIDE_REASONS == {'child_sexual_abuse', 'child_endangerment', 'sexual_nonconsensual',
                                     'terrorism_extremism', 'my_image'}

    def test_deterministic_id(self):
        assert build_report_id('r', 'k', 'u') == build_report_id('r', 'k', 'u')
        assert build_report_id('r', 'k', 'u') != build_report_id('r', 'k', 'u2')

    def test_roundtrip_and_validation(self):
        report = MediaReport(id='1', refuge_id='r', media_key='k', reporter_uid='u', reason='other', details='x')
        assert MediaReport.from_dict(report.to_dict()) == report
        with pytest.raises(ValueError):
            MediaReport(id='1', refuge_id='r', media_key='k', reporter_uid='u', reason='other')
        with pytest.raises(ValueError):
            MediaReport(id='1', refuge_id='r', media_key='k', reporter_uid='u', reason='nope')
        with pytest.raises(ValueError):
            MediaReport(id='1', refuge_id='r', media_key='k', reporter_uid='u', reason='hate_speech', details='x' * 1001)
        with pytest.raises(ValueError):
            MediaReport(id='1', refuge_id='r', media_key='k', reporter_uid='u', reason='hate_speech', action='ban')
        with pytest.raises(ValueError):
            MediaReport(id='', refuge_id='r', media_key='k', reporter_uid='u', reason='hate_speech')


@pytest.mark.models
class TestModerationNotice:
    def test_to_dict_includes_redress(self):
        notice = ModerationNotice(id='n', uid='u', type='strike', statement='s', strikes=1)
        data = notice.to_dict()
        assert data['redress'] == REDRESS_TEXT
        assert ModerationNotice.from_dict(data) == notice

    def test_validation(self):
        with pytest.raises(ValueError):
            ModerationNotice(id='n', uid='u', type='weird', statement='s')
        with pytest.raises(ValueError):
            ModerationNotice(id='n', uid='', type='strike', statement='s')
