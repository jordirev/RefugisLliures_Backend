"""
ImageProcessingService - Processament autoritatiu de mitjans al servidor.

Tot fitxer pujat (presigned PUT + confirm) passa per aquí abans de
publicar-se:
  1. Detecció del tipus REAL pels magic bytes (no ens refiem del Content-Type declarat).
  2. Obertura real del fitxer (Pillow / pillow-heif per a imatges, ffmpeg per a vídeos).
  3. Imatges: orientació EXIF aplicada, recodificació a WebP (2048 px de costat llarg,
     512 px per a avatars) + miniatura de 400 px, eliminació de TOTES les metadades
     (EXIF/GPS/XMP/IPTC/ICC/dispositiu), extracció de DateTimeOriginal -> taken_at
     (es desa a `refuge_media.taken_at`), blurhash i pHash per a moderació.
  4. Vídeos: remux sense recodificar (-map_metadata -1 -c copy -movflags +faststart)
     i pòster WebP com a miniatura.

Errors: es llança MediaRejected amb reason ∈ {invalid_type, too_large, processing_error}.
"""
import hashlib
import io
import logging
import os
import re
import subprocess
import tempfile
import warnings
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Tuple

from PIL import Image, ImageOps

from apps.core.timezone_utils import make_madrid_aware

logger = logging.getLogger(__name__)

try:  # HEIC/HEIF
    import pillow_heif
    pillow_heif.register_heif_opener()
    HEIF_SUPPORTED = True
except Exception:  # pragma: no cover - depèn de l'entorn
    HEIF_SUPPORTED = False
    logger.warning("pillow-heif no disponible: les imatges HEIC/HEIF es rebutjaran")

# Límit de píxels (bombes de descompressió). 80 MP cobreix càmeres de 48-64 MP.
Image.MAX_IMAGE_PIXELS = 80_000_000

# ---------------------------------------------------------------------------
# Límits i llistes blanques (contracte d'API)
# ---------------------------------------------------------------------------
MB = 1024 * 1024
IMAGE_MAX_BYTES = 15 * MB
VIDEO_MAX_BYTES = 50 * MB

MEDIA_TYPE_IMAGE = 'image'
MEDIA_TYPE_VIDEO = 'video'

ALLOWED_IMAGE_CONTENT_TYPES = ('image/jpeg', 'image/png', 'image/webp', 'image/heic', 'image/heif')
ALLOWED_VIDEO_CONTENT_TYPES = ('video/mp4', 'video/quicktime', 'video/webm')
CONTENT_TYPE_ALIASES = {'image/jpg': 'image/jpeg', 'image/pjpeg': 'image/jpeg'}

MAIN_MAX_EDGE = 2048
THUMB_MAX_EDGE = 400
AVATAR_MAX_EDGE = 512
WEBP_QUALITY = 80

REASON_MISSING_OBJECT = 'missing_object'
REASON_TOO_LARGE = 'too_large'
REASON_INVALID_TYPE = 'invalid_type'
REASON_PROCESSING_ERROR = 'processing_error'
REASON_MODERATION_BLOCKED = 'moderation_blocked'
FAILURE_REASONS = (REASON_MISSING_OBJECT, REASON_TOO_LARGE, REASON_INVALID_TYPE,
                   REASON_PROCESSING_ERROR, REASON_MODERATION_BLOCKED)

FFMPEG_TIMEOUT_SECONDS = 120

# Brands ISO-BMFF (caixa ftyp)
_HEIF_BRANDS = {b'heic', b'heix', b'hevc', b'hevx', b'heim', b'heis', b'hevm', b'hevs', b'mif1', b'msf1'}
_MP4_BRANDS = {b'isom', b'iso2', b'iso3', b'iso4', b'iso5', b'iso6', b'mp41', b'mp42', b'avc1',
               b'dash', b'M4V ', b'mmp4', b'MSNV', b'3gp4', b'3gp5', b'3g2a', b'f4v '}
_QT_BRANDS = {b'qt  '}

# Format de sortida de vídeo per format detectat: (extensió, content type)
_VIDEO_OUTPUT = {
    'mp4': ('.mp4', 'video/mp4'),
    'quicktime': ('.mov', 'video/quicktime'),
    'webm': ('.webm', 'video/webm'),
}


class MediaRejected(Exception):
    """El fitxer no es pot publicar. `reason` és un dels FAILURE_REASONS."""

    def __init__(self, reason: str, message: str = ''):
        super().__init__(message or reason)
        self.reason = reason


@dataclass
class DetectedType:
    kind: str  # 'image' | 'video'
    fmt: str   # 'jpeg' | 'png' | 'webp' | 'heif' | 'mp4' | 'quicktime' | 'webm'


@dataclass
class ProcessedMedia:
    """Resultat del processament, llest per pujar a R2."""
    media_type: str            # 'image' | 'video'
    content_type: str          # content type de la variant principal
    extension: str             # '.webp' | '.mp4' | '.mov' | '.webm'
    main_bytes: bytes
    thumb_bytes: Optional[bytes]
    width: int
    height: int
    blurhash: Optional[str]
    taken_at: Optional[str]
    sha256: str
    phash: Optional[str]

    @property
    def size(self) -> int:
        return len(self.main_bytes)


# ---------------------------------------------------------------------------
# Helpers de tipus
# ---------------------------------------------------------------------------

def normalize_content_type(content_type: Optional[str]) -> str:
    ct = (content_type or '').split(';')[0].strip().lower()
    return CONTENT_TYPE_ALIASES.get(ct, ct)


def kind_for_content_type(content_type: Optional[str]) -> Optional[str]:
    ct = normalize_content_type(content_type)
    if ct in ALLOWED_IMAGE_CONTENT_TYPES:
        return MEDIA_TYPE_IMAGE
    if ct in ALLOWED_VIDEO_CONTENT_TYPES:
        return MEDIA_TYPE_VIDEO
    return None


def max_bytes_for_kind(kind: str) -> int:
    return VIDEO_MAX_BYTES if kind == MEDIA_TYPE_VIDEO else IMAGE_MAX_BYTES


def detect_media_type(data: bytes) -> Optional[DetectedType]:
    """
    Detecta el tipus real a partir dels magic bytes. Només retorna tipus de la llista
    blanca; qualsevol altra cosa (PDF, ZIP, executables, GIF, AVIF, MKV...) -> None.
    """
    if not data or len(data) < 12:
        return None
    head = data[:64]
    if head[:3] == b'\xff\xd8\xff':
        return DetectedType('image', 'jpeg')
    if head[:8] == b'\x89PNG\r\n\x1a\n':
        return DetectedType('image', 'png')
    if head[:4] == b'RIFF' and head[8:12] == b'WEBP':
        return DetectedType('image', 'webp')
    if head[4:8] == b'ftyp':
        box_size = int.from_bytes(head[0:4], 'big')
        major = head[8:12]
        compat_end = min(max(box_size, 16), len(data), 256)
        compatible = [data[i:i + 4] for i in range(16, compat_end - 3, 4)]
        if major in _HEIF_BRANDS:
            return DetectedType('image', 'heif')
        if major in _QT_BRANDS:
            return DetectedType('video', 'quicktime')
        if major in _MP4_BRANDS:
            return DetectedType('video', 'mp4')
        # Major brand desconegut: mirar els compatibles
        if any(b in _HEIF_BRANDS for b in compatible) and not any(b in _MP4_BRANDS for b in compatible):
            return DetectedType('image', 'heif')
        if any(b in _MP4_BRANDS for b in compatible):
            return DetectedType('video', 'mp4')
        return None
    if head[:4] == b'\x1a\x45\xdf\xa3' and b'webm' in data[:256]:
        return DetectedType('video', 'webm')
    return None


# ---------------------------------------------------------------------------
# Imatges
# ---------------------------------------------------------------------------

_EXIF_IFD = 0x8769
_TAG_DATETIME = 306
_TAG_DATETIME_ORIGINAL = 36867
_TAG_OFFSET_TIME_ORIGINAL = 36881
_EXIF_DATE_RE = re.compile(r'^(\d{4}):(\d{2}):(\d{2})[ T](\d{2}):(\d{2}):(\d{2})')


def _parse_exif_date(value, offset=None) -> Optional[str]:
    if not value:
        return None
    if isinstance(value, bytes):
        value = value.decode('ascii', errors='ignore')
    match = _EXIF_DATE_RE.match(str(value).strip())
    if not match:
        return None
    y, mo, d, h, mi, s = match.groups()
    if y == '0000':
        return None
    iso = f"{y}-{mo}-{d}T{h}:{mi}:{s}"
    if offset:
        if isinstance(offset, bytes):
            offset = offset.decode('ascii', errors='ignore')
        offset = str(offset).strip()
        if re.match(r'^[+-]\d{2}:\d{2}$', offset):
            return iso + offset
    # Sense desplaçament a l'EXIF: s'assumeix l'hora de Madrid (decisió del PO, 26/10; DST inclòs). Un naïf es
    # desaria com a UTC a `taken_at` (timestamptz) i la foto sortiria 1-2 h desplaçada.
    try:
        return make_madrid_aware(datetime.fromisoformat(iso)).isoformat()
    except ValueError:                              # data impossible (p. ex. 2025-02-30): sense taken_at
        return None


def extract_taken_at(img: Image.Image) -> Optional[str]:
    """Extreu DateTimeOriginal (o DateTime) de l'EXIF com a ISO 8601."""
    try:
        exif = img.getexif()
        if not exif:
            return None
        exif_ifd = exif.get_ifd(_EXIF_IFD) or {}
        taken = _parse_exif_date(exif_ifd.get(_TAG_DATETIME_ORIGINAL), exif_ifd.get(_TAG_OFFSET_TIME_ORIGINAL))
        return taken or _parse_exif_date(exif.get(_TAG_DATETIME))
    except Exception as e:  # EXIF corrupte: no és motiu de rebuig
        logger.info(f"No s'ha pogut llegir l'EXIF: {e}")
        return None


def _strip_metadata(img: Image.Image) -> Image.Image:
    """Retorna una imatge nova només amb els píxels (sense info/EXIF/ICC/XMP)."""
    has_alpha = img.mode in ('RGBA', 'LA', 'PA') or (img.mode == 'P' and 'transparency' in img.info)
    mode = 'RGBA' if has_alpha else 'RGB'
    converted = img.convert(mode)
    return Image.frombytes(mode, converted.size, converted.tobytes())


def _encode_webp(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format='WEBP', quality=WEBP_QUALITY, method=4, exif=b'', icc_profile=None)
    return buf.getvalue()


def _resized(img: Image.Image, max_edge: int) -> Image.Image:
    out = img.copy()
    out.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
    return out


def compute_blurhash(img: Image.Image) -> Optional[str]:
    try:
        import blurhash
        small = img.convert('RGB')
        small.thumbnail((32, 32), Image.Resampling.BILINEAR)
        width, height = small.size
        pixels = list(small.getdata())
        rows = [[list(pixels[y * width + x]) for x in range(width)] for y in range(height)]
        return blurhash.encode(rows, components_x=4, components_y=3)
    except Exception as e:
        logger.warning(f"No s'ha pogut calcular el blurhash: {e}")
        return None


def compute_phash(img: Image.Image) -> Optional[str]:
    try:
        import imagehash
        return str(imagehash.phash(img.convert('RGB')))
    except Exception as e:
        logger.warning(f"No s'ha pogut calcular el pHash: {e}")
        return None


def _open_image(data: bytes) -> Image.Image:
    """Obre i descodifica completament una imatge, traduint errors a MediaRejected."""
    with warnings.catch_warnings():
        warnings.simplefilter('error', Image.DecompressionBombWarning)
        try:
            with Image.open(io.BytesIO(data)) as probe:
                probe.verify()
            img = Image.open(io.BytesIO(data))
            img.load()
        except (Image.DecompressionBombError, Image.DecompressionBombWarning):
            raise MediaRejected(REASON_TOO_LARGE, "Imatge amb massa píxels")
        except MediaRejected:
            raise
        except Exception as e:
            raise MediaRejected(REASON_INVALID_TYPE, f"No és una imatge vàlida: {e}")
    if img.format not in ('JPEG', 'PNG', 'WEBP', 'HEIF'):
        raise MediaRejected(REASON_INVALID_TYPE, f"Format d'imatge no permès: {img.format}")
    return img


def process_image(data: bytes, max_edge: int = MAIN_MAX_EDGE,
                  thumb_edge: Optional[int] = THUMB_MAX_EDGE) -> ProcessedMedia:
    """
    Recodifica una imatge: orientació aplicada, sense metadades, WebP.

    Raises:
        MediaRejected
    """
    detected = detect_media_type(data)
    if detected is None or detected.kind != 'image':
        raise MediaRejected(REASON_INVALID_TYPE, "Els magic bytes no corresponen a cap imatge permesa")
    if detected.fmt == 'heif' and not HEIF_SUPPORTED:  # pragma: no cover
        raise MediaRejected(REASON_INVALID_TYPE, "HEIC/HEIF no suportat al servidor")

    img = _open_image(data)
    try:
        taken_at = extract_taken_at(img)
        try:
            img = ImageOps.exif_transpose(img) or img
        except Exception as e:
            logger.info(f"No s'ha pogut aplicar l'orientació EXIF: {e}")
        clean = _strip_metadata(img)

        main = _resized(clean, max_edge)
        main_bytes = _encode_webp(main)
        thumb_bytes = _encode_webp(_resized(clean, thumb_edge)) if thumb_edge else None

        return ProcessedMedia(
            media_type='image',
            content_type='image/webp',
            extension='.webp',
            main_bytes=main_bytes,
            thumb_bytes=thumb_bytes,
            width=main.width,
            height=main.height,
            blurhash=compute_blurhash(clean),
            taken_at=taken_at,
            sha256=hashlib.sha256(data).hexdigest(),
            phash=compute_phash(clean),
        )
    except MediaRejected:
        raise
    except Exception as e:
        logger.error(f"Error processant imatge: {e}")
        raise MediaRejected(REASON_PROCESSING_ERROR, str(e))


# ---------------------------------------------------------------------------
# Vídeos
# ---------------------------------------------------------------------------

_CREATION_TIME_RE = re.compile(r'creation_time\s*:\s*(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})')


def _ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as e:  # pragma: no cover - depèn de l'entorn
        raise MediaRejected(REASON_PROCESSING_ERROR, f"ffmpeg no disponible: {e}")


def _run(args, timeout=FFMPEG_TIMEOUT_SECONDS) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(args, capture_output=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        raise MediaRejected(REASON_PROCESSING_ERROR, "ffmpeg ha superat el temps màxim")


def probe_video(ffmpeg: str, path: str) -> Tuple[bool, Optional[str]]:
    """
    Comprova amb ffmpeg que el fitxer té una pista de vídeo descodificable.
    (imageio-ffmpeg no inclou ffprobe; `ffmpeg -i` fa el mateix paper.)
    Retorna (té_vídeo, creation_time ISO o None).
    """
    result = _run([ffmpeg, '-hide_banner', '-i', path])
    stderr = result.stderr.decode('utf-8', errors='ignore')
    has_video = bool(re.search(r'Stream #\d+:\d+.*: Video:', stderr))
    taken_at = None
    match = _CREATION_TIME_RE.search(stderr)
    if match and not match.group(1).startswith('1970') and not match.group(1).startswith('1904'):
        taken_at = f"{match.group(1)}T{match.group(2)}+00:00"     # `creation_time` de l'MP4/MOV és UTC (ISO BMFF)
    return has_video, taken_at


def process_video(data: bytes) -> ProcessedMedia:
    """
    Remux sense recodificar eliminant metadades + pòster WebP.

    Raises:
        MediaRejected
    """
    detected = detect_media_type(data)
    if detected is None or detected.kind != 'video':
        raise MediaRejected(REASON_INVALID_TYPE, "Els magic bytes no corresponen a cap vídeo permès")
    extension, content_type = _VIDEO_OUTPUT[detected.fmt]
    ffmpeg = _ffmpeg_exe()

    with tempfile.TemporaryDirectory(prefix='rl-media-') as tmp:
        in_path = os.path.join(tmp, f"in{extension}")
        out_path = os.path.join(tmp, f"out{extension}")
        with open(in_path, 'wb') as fh:
            fh.write(data)

        has_video, taken_at = probe_video(ffmpeg, in_path)
        if not has_video:
            raise MediaRejected(REASON_INVALID_TYPE, "El fitxer no conté cap pista de vídeo vàlida")

        args = [ffmpeg, '-hide_banner', '-v', 'error', '-y', '-i', in_path,
                '-map', '0:v:0', '-map', '0:a?', '-c', 'copy',
                '-map_metadata', '-1', '-map_chapters', '-1', '-fflags', '+bitexact']
        if extension in ('.mp4', '.mov'):
            args += ['-movflags', '+faststart']
        args.append(out_path)
        result = _run(args)
        if result.returncode != 0 or not os.path.exists(out_path):
            logger.info(f"ffmpeg remux ha fallat: {result.stderr[-500:]!r}")
            raise MediaRejected(REASON_INVALID_TYPE, "No s'ha pogut processar el vídeo")

        poster = _run([ffmpeg, '-hide_banner', '-v', 'error', '-i', out_path,
                       '-frames:v', '1', '-f', 'image2pipe', '-vcodec', 'png', '-'])
        if poster.returncode != 0 or not poster.stdout:
            raise MediaRejected(REASON_INVALID_TYPE, "No s'ha pogut extreure cap fotograma del vídeo")

        with open(out_path, 'rb') as fh:
            main_bytes = fh.read()

    try:
        frame = Image.open(io.BytesIO(poster.stdout))
        frame.load()
        clean = _strip_metadata(frame)
        return ProcessedMedia(
            media_type='video',
            content_type=content_type,
            extension=extension,
            main_bytes=main_bytes,
            thumb_bytes=_encode_webp(_resized(clean, THUMB_MAX_EDGE)),
            width=clean.width,
            height=clean.height,
            blurhash=compute_blurhash(clean),
            taken_at=taken_at,
            sha256=hashlib.sha256(data).hexdigest(),
            phash=compute_phash(clean),
        )
    except Exception as e:
        logger.error(f"Error generant el pòster del vídeo: {e}")
        raise MediaRejected(REASON_PROCESSING_ERROR, str(e))


# ---------------------------------------------------------------------------
# Punt d'entrada
# ---------------------------------------------------------------------------

class ImageProcessingService:
    """Façana del processament (fàcil de mockejar als tests)."""

    def process(self, data: bytes, declared_content_type: Optional[str], avatar: bool = False) -> ProcessedMedia:
        """
        Valida mida i tipus i processa el fitxer.

        Args:
            data: bytes originals
            declared_content_type: Content-Type declarat pel client
            avatar: True -> només imatges, 512 px i sense miniatura

        Raises:
            MediaRejected
        """
        declared_kind = kind_for_content_type(declared_content_type)
        detected = detect_media_type(data)
        if detected is None:
            raise MediaRejected(REASON_INVALID_TYPE, "Tipus de fitxer no permès (magic bytes)")
        if declared_kind is not None and declared_kind != detected.kind:
            raise MediaRejected(REASON_INVALID_TYPE, "El tipus declarat no coincideix amb el contingut")
        if avatar and detected.kind != 'image':
            raise MediaRejected(REASON_INVALID_TYPE, "L'avatar només pot ser una imatge")
        if len(data) > max_bytes_for_kind(detected.kind):
            raise MediaRejected(REASON_TOO_LARGE, "Fitxer massa gran")

        if detected.kind == 'image':
            if avatar:
                return process_image(data, max_edge=AVATAR_MAX_EDGE, thumb_edge=None)
            return process_image(data)
        return process_video(data)


image_processing_service = ImageProcessingService()
