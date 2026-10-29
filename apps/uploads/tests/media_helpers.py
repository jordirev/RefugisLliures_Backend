"""
Helpers per als tests de mitjans: imatges reals generades en memòria (amb EXIF/GPS),
vídeos generats amb ffmpeg i un R2MediaService real amb el client boto3 mockat.
"""
import io
import os
import subprocess
import tempfile
from unittest.mock import MagicMock

from PIL import Image

from apps.uploads.media.r2_media_service import R2MediaService, RefugiMediaStrategy, UserAvatarStrategy

GPS_IFD = 0x8825
EXIF_IFD = 0x8769


def make_jpeg_with_gps(size=(3000, 2000), orientation=6, color=(120, 30, 200)) -> bytes:
    """JPEG amb càmera, orientació, data de presa i coordenades GPS a l'EXIF"""
    img = Image.new('RGB', size, color)
    exif = Image.Exif()
    exif[0x010F] = 'Canon'          # Make
    exif[0x0110] = 'EOS 5D'         # Model
    exif[0x0131] = 'Firmware 1.0'   # Software
    exif[0x0112] = orientation      # Orientation
    exif[GPS_IFD] = {1: 'N', 2: (41.0, 23.0, 10.0), 3: 'E', 4: (2.0, 10.0, 5.0)}
    exif[EXIF_IFD] = {36867: '2024:07:15 10:20:30', 36881: '+02:00'}
    buf = io.BytesIO()
    img.save(buf, 'JPEG', exif=exif.tobytes(), quality=85)
    return buf.getvalue()


def make_png(size=(800, 600), alpha=False) -> bytes:
    img = Image.new('RGBA' if alpha else 'RGB', size, (10, 200, 30, 128) if alpha else (10, 200, 30))
    buf = io.BytesIO()
    img.save(buf, 'PNG')
    return buf.getvalue()


def make_mp4(seconds=1, with_metadata=True) -> bytes:
    """Vídeo MP4 curt generat amb el ffmpeg d'imageio-ffmpeg (amb metadades de localització)"""
    import imageio_ffmpeg
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, 'v.mp4')
        args = [ffmpeg, '-v', 'error', '-f', 'lavfi', '-i', f'testsrc=duration={seconds}:size=320x240:rate=10',
                '-c:v', 'mpeg4']
        if with_metadata:
            args += ['-metadata', 'location=+41.3851+002.1734/', '-metadata', 'creation_time=2024-05-01T10:00:00Z',
                     '-metadata', 'make=Apple', '-metadata', 'model=iPhone 15']
        args.append(path)
        subprocess.run(args, check=True, capture_output=True)
        with open(path, 'rb') as fh:
            return fh.read()


def ffmpeg_metadata_dump(data: bytes, ext='.mp4') -> str:
    import imageio_ffmpeg
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, f'v{ext}')
        with open(path, 'wb') as fh:
            fh.write(data)
        result = subprocess.run([ffmpeg, '-hide_banner', '-i', path], capture_output=True)
        return result.stderr.decode('utf-8', errors='ignore')


def fake_r2_service(strategy=None, objects=None) -> R2MediaService:
    """
    R2MediaService real (claus, URLs, estratègia) amb el client boto3 mockat.
    `objects` és un dict key -> bytes que simula el bucket.
    """
    from botocore.exceptions import ClientError

    service = R2MediaService(strategy or RefugiMediaStrategy())
    store = objects if objects is not None else {}
    client = MagicMock()

    def presign(operation, Params, ExpiresIn, **kwargs):
        return f"https://r2.test/{Params['Key']}?op={operation}&exp={ExpiresIn}"

    def not_found():
        return ClientError({'Error': {'Code': '404', 'Message': 'Not Found'}}, 'HeadObject')

    def head_object(Bucket, Key):
        if Key not in store:
            raise not_found()
        return {'ContentLength': len(store[Key]), 'ContentType': 'application/octet-stream'}

    def get_object(Bucket, Key):
        if Key not in store:
            raise ClientError({'Error': {'Code': 'NoSuchKey', 'Message': 'x'}}, 'GetObject')
        return {'Body': io.BytesIO(store[Key])}

    def put_object(Bucket, Key, Body, ContentType, **kwargs):
        store[Key] = Body if isinstance(Body, bytes) else Body.read()
        return {}

    def delete_object(Bucket, Key):
        store.pop(Key, None)
        return {}

    def copy_object(Bucket, Key, CopySource):
        store[Key] = store[CopySource['Key']]
        return {}

    client.generate_presigned_url.side_effect = presign
    client.head_object.side_effect = head_object
    client.get_object.side_effect = get_object
    client.put_object.side_effect = put_object
    client.delete_object.side_effect = delete_object
    client.copy_object.side_effect = copy_object
    service.client = client
    service.store = store
    return service


def fake_avatar_service(objects=None) -> R2MediaService:
    return fake_r2_service(UserAvatarStrategy(), objects)
