"""
Ajudes de test del domini pujades (chunk 7): intents (`moderation.upload_intents`) i confirmació.

Reutilitza les dels chunks 2 i 3. Els models de producció (`apps.uploads`) encara no existeixen quan s'escriuen els
tests: s'importen de manera mandrosa (`upload_models()`).

- Les files d'`upload_intents` es creen amb SQL pla (rol `app` dins `system_context()`), de manera que els fixtures no
  depenguin dels noms dels models ni dels services.
- R2 és un client boto3 fals amb un diccionari com a bucket (`R2Store`): les URL prefirmades són deterministes, el
  `head_object`/`get_object`/`put_object`/`delete_object`/`copy_object` operen sobre el diccionari. S'injecta parchejant
  `apps.uploads.r2_media_service.get_r2_client` (les factories `get_refugi_media_service()` /
  `get_user_avatar_service()` creen una instància nova a cada crida: totes comparteixen el mateix client).
"""
import importlib
import io
import uuid
from datetime import timedelta
from unittest.mock import MagicMock

from PIL import Image

from apps.accounts.tests.helpers import (  # noqa: F401  (re-exportats)
    MEDIA_ITEM_KEYS, QueryCounter, T0, VERIFY, admin_claims, api_delete, api_get, api_patch, api_post, as_owner, at,
    count_all, make_avatar, make_media, make_refuge, sql, user_claims)

from apps.accounts.tests.helpers import make_user as _make_user

INTENTS = '/api/media/upload-intents/'
CONFIRM = '/api/media/upload-intents/confirm/'
ZERO_UUID = '00000000-0000-0000-0000-000000000000'
NOT_OWNER_BODY = {'error': 'not_owner', 'code': 'not_owner', 'message': "No ets el creador d'aquesta experiència"}
GPS_IFD = 0x8825
EXIF_IFD = 0x8769

INTENT_COLS = ('id', 'user_uid', 'target', 'content_type', 'size', 'quarantine_key', 'refuge_id', 'experience_id',
               'status', 'rights_confirmed_at', 'created_at', 'expire_at', 'result_key', 'failure_reason')


def make_user(uid='u1', username='', **fields):
    """Usuari amb l'edat confirmada (les pujades exigeixen `IsAgeConfirmed`); es pot sobreescriure."""
    fields.setdefault('age_confirmed_at', at())
    fields.setdefault('age_threshold', 16)
    return _make_user(uid, username, **fields)


def upload_models():
    return importlib.import_module('apps.uploads.models')


# ---------- Imatges reals en memòria ----------

def make_jpeg_with_gps(size=(3000, 2000), orientation=6, color=(120, 30, 200)) -> bytes:
    """JPEG amb càmera, orientació, data de presa i coordenades GPS a l'EXIF."""
    img = Image.new('RGB', size, color)
    exif = Image.Exif()
    exif[0x010F] = 'Canon'
    exif[0x0110] = 'EOS 5D'
    exif[0x0131] = 'Firmware 1.0'
    exif[0x0112] = orientation
    exif[GPS_IFD] = {1: 'N', 2: (41.0, 23.0, 10.0), 3: 'E', 4: (2.0, 10.0, 5.0)}
    exif[EXIF_IFD] = {36867: '2024:07:15 10:20:30', 36881: '+02:00'}
    buf = io.BytesIO()
    img.save(buf, 'JPEG', exif=exif.tobytes(), quality=85)
    return buf.getvalue()


def make_png(size=(800, 600)) -> bytes:
    buf = io.BytesIO()
    Image.new('RGB', size, (10, 200, 30)).save(buf, 'PNG')
    return buf.getvalue()


# ---------- R2 fals ----------

class R2Store:
    """Bucket en memòria + client boto3 fals. `store` és `{key: bytes}`; `puts`/`deletes` registren el que es fa."""

    def __init__(self):
        from botocore.exceptions import ClientError
        self.store = {}
        self.deletes = []
        self.puts = []
        self.fail_put_for = ()                       # claus (sufix) a les quals `put_object` ha de fallar
        client = MagicMock()
        self.client = client

        def presign(operation, Params, ExpiresIn, **kwargs):
            return f"https://r2.test/{Params['Key']}?op={operation}&exp={ExpiresIn}"

        def not_found(op):
            return ClientError({'Error': {'Code': '404', 'Message': 'Not Found'}}, op)

        def head_object(Bucket, Key):
            if Key not in self.store:
                raise not_found('HeadObject')
            return {'ContentLength': len(self.store[Key]), 'ContentType': 'application/octet-stream'}

        def get_object(Bucket, Key):
            if Key not in self.store:
                raise ClientError({'Error': {'Code': 'NoSuchKey', 'Message': 'x'}}, 'GetObject')
            return {'Body': io.BytesIO(self.store[Key])}

        def put_object(Bucket, Key, Body, ContentType, **kwargs):
            if any(Key.endswith(s) for s in self.fail_put_for):
                raise ClientError({'Error': {'Code': '500', 'Message': 'boom'}}, 'PutObject')
            self.store[Key] = Body if isinstance(Body, bytes) else Body.read()
            self.puts.append(Key)
            return {}

        def delete_object(Bucket, Key):
            self.store.pop(Key, None)
            self.deletes.append(Key)
            return {}

        def copy_object(Bucket, Key, CopySource):
            self.store[Key] = self.store[CopySource['Key']]
            return {}

        client.generate_presigned_url.side_effect = presign
        client.head_object.side_effect = head_object
        client.get_object.side_effect = get_object
        client.put_object.side_effect = put_object
        client.delete_object.side_effect = delete_object
        client.copy_object.side_effect = copy_object

    def put_quarantine(self, upload_id, data):
        self.store[f'quarantine/{upload_id}'] = data

    def keys(self, prefix=''):
        return sorted(k for k in self.store if k.startswith(prefix))


# ---------- Intents (SQL pla) ----------

def make_intent(uid, target='refuge', refuge=None, experience_id=None, content_type='image/jpeg', size=1000,
                status='pending', result_key=None, failure_reason=None, created_ago=None, expires_in=None,
                intent_id=None):
    """Insereix un intent i en retorna l'id (`str`). `created_ago`/`expires_in` són `timedelta` respecte de `now()`
    (per defecte creat ara i caduca d'aquí a un dia)."""
    intent_id = intent_id or str(uuid.uuid4())
    refuge_id = getattr(refuge, 'pk', refuge)
    created = created_ago if created_ago is not None else timedelta(0)
    expire = expires_in if expires_in is not None else timedelta(days=1)
    sql('INSERT INTO moderation.upload_intents (id, user_uid, target, content_type, size, quarantine_key, refuge_id, '
        'experience_id, status, rights_confirmed_at, created_at, expire_at, result_key, failure_reason) '
        'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, now(), now() - %s, now() + %s, %s, %s)',
        [intent_id, uid, target, content_type, size, f'quarantine/{intent_id}', refuge_id, experience_id, status,
         created, expire, result_key, failure_reason])
    return intent_id


def intent_row(intent_id):
    rows = sql(f'SELECT {", ".join(INTENT_COLS)} FROM moderation.upload_intents WHERE id = %s', [intent_id])
    if not rows:
        return None
    row = dict(zip(INTENT_COLS, rows[0]))
    for k in ('id', 'refuge_id', 'experience_id'):
        row[k] = str(row[k]) if row[k] else None
    return row


def intent_ids(uid=None):
    where, params = ('WHERE user_uid = %s', [uid]) if uid else ('', [])
    return [str(r[0]) for r in sql(f'SELECT id FROM moderation.upload_intents {where} ORDER BY created_at, id', params)]


def is_uuid(value):
    try:
        return str(uuid.UUID(value)) == value
    except (ValueError, AttributeError, TypeError):
        return False


def file_spec(content_type='image/jpeg', size=1234):
    return {'content_type': content_type, 'size': size}


def intent_body(target='refuge', refuge=None, experience_id=None, files=None, rights_confirmed=True):
    body = {'target': target, 'rights_confirmed': rights_confirmed, 'files': files if files is not None else [file_spec()]}
    if refuge is not None:
        body['refuge_id'] = str(getattr(refuge, 'pk', refuge))
    if experience_id is not None:
        body['experience_id'] = str(experience_id)
    return body


def refuge_media_rows(refuge=None):
    """`[dict]` de `refuges.refuge_media` (ordenats per clau)."""
    cols = ('key', 'refuge_id', 'creator_uid', 'experience_id', 'media_type', 'content_type', 'status', 'width',
            'height', 'size_bytes', 'thumb_key', 'blurhash', 'rights_confirmed_at', 'taken_at', 'uploaded_at')
    where, params = ('WHERE refuge_id = %s', [getattr(refuge, 'pk', refuge)]) if refuge is not None else ('', [])
    rows = sql(f'SELECT {", ".join(cols)} FROM refuges.refuge_media {where} ORDER BY key', params)
    out = []
    for r in rows:
        d = dict(zip(cols, r))
        d['refuge_id'] = str(d['refuge_id'])
        d['experience_id'] = str(d['experience_id']) if d['experience_id'] else None
        out.append(d)
    return out


def avatar_row(uid):
    cols = ('key', 'thumb_key', 'content_type', 'width', 'height', 'size_bytes', 'blurhash')
    rows = sql(f'SELECT {", ".join(cols)} FROM users.user_avatars WHERE user_uid = %s', [uid])
    return dict(zip(cols, rows[0])) if rows else None
