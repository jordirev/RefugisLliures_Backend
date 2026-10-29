"""
Tests del processament autoritatiu de mitjans (ImageProcessingService)
"""
import io

import pytest
from PIL import Image

from apps.uploads.image_processing_service import (
    image_processing_service, detect_media_type, process_image, MediaRejected,
    normalize_content_type, kind_for_content_type, extract_taken_at, IMAGE_MAX_BYTES,
    AVATAR_MAX_EDGE, MAIN_MAX_EDGE, THUMB_MAX_EDGE,
)
from apps.uploads.tests.media_helpers import make_jpeg_with_gps, make_png, make_mp4, ffmpeg_metadata_dump, GPS_IFD


@pytest.mark.unit
class TestDetectMediaType:
    def test_jpeg_png_webp(self):
        assert detect_media_type(make_jpeg_with_gps((10, 10))).fmt == 'jpeg'
        assert detect_media_type(make_png((10, 10))).fmt == 'png'
        buf = io.BytesIO()
        Image.new('RGB', (10, 10)).save(buf, 'WEBP')
        assert detect_media_type(buf.getvalue()).fmt == 'webp'

    def test_iso_bmff_brands(self):
        def ftyp(major, compat=b''):
            body = major + b'\x00\x00\x00\x00' + compat
            return (8 + len(body)).to_bytes(4, 'big') + b'ftyp' + body + b'\x00' * 32

        assert detect_media_type(ftyp(b'heic')).kind == 'image'
        assert detect_media_type(ftyp(b'mif1', b'heic')).fmt == 'heif'
        assert detect_media_type(ftyp(b'qt  ')).fmt == 'quicktime'
        assert detect_media_type(ftyp(b'isom', b'mp41')).fmt == 'mp4'
        assert detect_media_type(ftyp(b'avif')) is None  # AVIF no és a la llista blanca

    def test_webm(self):
        data = b'\x1a\x45\xdf\xa3' + b'\x00' * 20 + b'webm' + b'\x00' * 40
        assert detect_media_type(data).fmt == 'webm'

    @pytest.mark.parametrize('data', [
        b'%PDF-1.7 this is a pdf document......',
        b'PK\x03\x04 zip archive with stuff inside',
        b'MZ\x90\x00 windows executable header....',
        b'GIF89a\x01\x00\x01\x00 gif not allowed...',
        b'<html><body>not an image</body></html>',
        b'',
        b'short',
    ])
    def test_rejects_non_whitelisted(self, data):
        assert detect_media_type(data) is None

    def test_content_type_helpers(self):
        assert normalize_content_type('IMAGE/JPG; charset=binary') == 'image/jpeg'
        assert kind_for_content_type('image/heic') == 'image'
        assert kind_for_content_type('video/quicktime') == 'video'
        assert kind_for_content_type('video/x-msvideo') is None
        assert kind_for_content_type('application/pdf') is None


@pytest.mark.unit
class TestProcessImage:
    def test_jpeg_with_gps_is_fully_stripped(self):
        """JPEG amb GPS EXIF → la sortida no té EXIF ni GPS (getexif() buit)"""
        original = make_jpeg_with_gps()
        source = Image.open(io.BytesIO(original))
        assert source.getexif().get_ifd(GPS_IFD), "el fixture ha de portar GPS"

        result = image_processing_service.process(original, 'image/jpeg')

        out = Image.open(io.BytesIO(result.main_bytes))
        assert out.format == 'WEBP'
        assert dict(out.getexif()) == {}
        assert not out.getexif().get_ifd(GPS_IFD)
        assert 'exif' not in out.info and 'xmp' not in out.info and 'icc_profile' not in out.info
        assert b'Exif' not in result.main_bytes and b'Canon' not in result.main_bytes
        thumb = Image.open(io.BytesIO(result.thumb_bytes))
        assert dict(thumb.getexif()) == {}
        assert b'Canon' not in result.thumb_bytes

    def test_orientation_applied_and_resized(self):
        result = image_processing_service.process(make_jpeg_with_gps((3000, 2000), orientation=6), 'image/jpeg')
        # Orientació 6 = rotació 90°: 3000x2000 → 2000x3000 → escalat a 2048 de costat llarg
        assert (result.width, result.height) == (1365, MAIN_MAX_EDGE)
        thumb = Image.open(io.BytesIO(result.thumb_bytes))
        assert max(thumb.size) == THUMB_MAX_EDGE

    def test_taken_at_extracted_to_metadata(self):
        result = image_processing_service.process(make_jpeg_with_gps((100, 100)), 'image/jpeg')
        assert result.taken_at == '2024-07-15T10:20:30+02:00'
        assert result.blurhash and isinstance(result.blurhash, str)
        assert result.phash and len(result.phash) == 16
        assert len(result.sha256) == 64

    def test_small_image_not_upscaled(self):
        result = image_processing_service.process(make_png((300, 200)), 'image/png')
        assert (result.width, result.height) == (300, 200)
        assert result.taken_at is None

    def test_png_with_alpha_keeps_transparency(self):
        result = image_processing_service.process(make_png((50, 50), alpha=True), 'image/png')
        assert Image.open(io.BytesIO(result.main_bytes)).mode == 'RGBA'

    def test_avatar_512_without_thumb(self):
        result = image_processing_service.process(make_jpeg_with_gps((2000, 2000), orientation=1), 'image/jpeg', avatar=True)
        assert max(result.width, result.height) == AVATAR_MAX_EDGE
        assert result.thumb_bytes is None

    def test_non_image_declared_as_jpeg_is_invalid_type(self):
        """Bytes que no són una imatge declarats com a image/jpeg → invalid_type"""
        with pytest.raises(MediaRejected) as exc:
            image_processing_service.process(b'%PDF-1.4\n' + b'0' * 2000, 'image/jpeg')
        assert exc.value.reason == 'invalid_type'

    def test_truncated_jpeg_is_invalid_type(self):
        data = make_jpeg_with_gps((200, 200))[:300]
        with pytest.raises(MediaRejected) as exc:
            image_processing_service.process(data, 'image/jpeg')
        assert exc.value.reason == 'invalid_type'

    def test_declared_video_but_image_bytes_is_invalid_type(self):
        with pytest.raises(MediaRejected) as exc:
            image_processing_service.process(make_png((10, 10)), 'video/mp4')
        assert exc.value.reason == 'invalid_type'

    def test_avatar_rejects_video(self):
        with pytest.raises(MediaRejected) as exc:
            image_processing_service.process(make_mp4(), None, avatar=True)
        assert exc.value.reason == 'invalid_type'

    def test_oversize_is_too_large(self):
        data = make_png((10, 10)) + b'\x00' * (IMAGE_MAX_BYTES + 1)
        with pytest.raises(MediaRejected) as exc:
            image_processing_service.process(data, 'image/png')
        assert exc.value.reason == 'too_large'

    def test_decompression_bomb_is_too_large(self, monkeypatch):
        monkeypatch.setattr(Image, 'MAX_IMAGE_PIXELS', 1000)
        with pytest.raises(MediaRejected) as exc:
            process_image(make_png((100, 100)))
        assert exc.value.reason == 'too_large'

    def test_extract_taken_at_without_exif(self):
        assert extract_taken_at(Image.new('RGB', (5, 5))) is None

    @pytest.mark.parametrize('value, offset, expected', [
        ('2024:07:15 10:20:30', '+02:00', '2024-07-15T10:20:30+02:00'),    # amb desplaçament: es respecta
        ('2024:07:15 10:20:30', '-05:00', '2024-07-15T10:20:30-05:00'),
        ('2024:07:15 10:20:30', None, '2024-07-15T10:20:30+02:00'),        # sense: hora de Madrid (estiu)
        ('2024:01:15 10:20:30', None, '2024-01-15T10:20:30+01:00'),        # sense: hora de Madrid (hivern)
        ('2024:01:15 10:20:30', 'garbage', '2024-01-15T10:20:30+01:00'),   # desplaçament invàlid = sense
        ('2025:02:30 10:00:00', None, None),                               # data impossible
        ('0000:00:00 00:00:00', None, None),
    ])
    def test_parse_exif_date_sense_desplacament_assumeix_madrid(self, value, offset, expected):
        """Decisió del PO (26/10): un EXIF sense OffsetTime es desaria com a UTC (1-2 h de desfasament)."""
        from apps.uploads.image_processing_service import _parse_exif_date
        assert _parse_exif_date(value, offset) == expected


@pytest.mark.unit
@pytest.mark.slow
class TestProcessVideo:
    def test_video_remuxed_without_metadata_and_poster(self):
        original = make_mp4()
        assert 'location' in ffmpeg_metadata_dump(original)

        result = image_processing_service.process(original, 'video/mp4')

        assert result.media_type == 'video'
        assert result.content_type == 'video/mp4'
        assert result.extension == '.mp4'
        assert (result.width, result.height) == (320, 240)
        assert result.taken_at == '2024-05-01T10:00:00+00:00'   # creation_time és UTC: es fa explícit
        dump = ffmpeg_metadata_dump(result.main_bytes)
        assert 'location' not in dump
        assert 'iPhone' not in dump and 'Apple' not in dump
        assert 'creation_time' not in dump
        poster = Image.open(io.BytesIO(result.thumb_bytes))
        assert poster.format == 'WEBP'
        assert result.blurhash

    def test_fake_video_is_invalid_type(self):
        fake = (24).to_bytes(4, 'big') + b'ftypisom' + b'\x00' * 12 + b'garbage' * 50
        with pytest.raises(MediaRejected) as exc:
            image_processing_service.process(fake, 'video/mp4')
        assert exc.value.reason == 'invalid_type'
