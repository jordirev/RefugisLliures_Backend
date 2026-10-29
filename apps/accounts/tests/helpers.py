"""
Ajudes de test del domini usuaris (chunk 3).

Reutilitza les del chunk 2 (`apps.refuges.tests.helpers`: `make_user`, `make_refuge`, `make_media`, `as_owner`,
`QueryCounter`...) i hi afegeix les de preferits/visitats, els avatars i les peticions amb cos.

Les files de `user_favourite_refuges`/`user_visited_refuges` es creen amb SQL pla (rol `app` dins `system_context()`)
perque els fixtures no depenguin del nom dels models; els tests de models si que usen `FavouriteRefuge`/`VisitedRefuge`.

IMPORTANT: a diferencia dels helpers del chunk 2, aqui `api_*` **no** creen el perfil de qui fa la peticio:
els tests han de crear l'usuari amb `make_user` (o provar `profile_required`).
"""
import json
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.db import connection

from apps.core.rls import system_context
from apps.refuges.tests.helpers import (  # noqa: F401  (re-exportats)
    BASE_KEYS, MEDIA_ITEM_KEYS, T0, VERIFY, QueryCounter, account_models, admin_claims, as_owner, make_media,
    make_refuge, make_user, refuge_models, user_claims)
from apps.refuges.tests.helpers import ensure_profile  # noqa: F401
from apps.refuges.tests.helpers import api_delete as _api_delete, api_get as _api_get

OWN_KEYS = {'uid', 'username', 'avatar_metadata', 'language', 'favourite_refuges', 'visited_refuges',
            'uploaded_photos_keys', 'num_shared_experiences', 'num_renovated_refuges', 'created_at',
            'age_confirmed'}
PUBLIC_KEYS = {'uid', 'username', 'avatar_metadata'}
LIST_ITEM_KEYS = {'id', 'name', 'region', 'places', 'coord', 'images_metadata'}

FAV = 'favorite-refuges'
VIS = 'visited-refuges'
TABLES = {FAV: 'users.user_favourite_refuges', VIS: 'users.user_visited_refuges'}
PROFILE_REQUIRED = 'profile_required'
USERS = '/api/users/'


# ---------- Dates ----------

def madrid_today():
    from apps.core.timezone_utils import get_madrid_today
    return get_madrid_today()


def years_ago(years, days_offset=0):
    """Data de naixement de fa `years` anys (avui a Madrid, com `is_old_enough`) +/- `days_offset` dies."""
    today = madrid_today()
    try:
        d = today.replace(year=today.year - years)
    except ValueError:                          # 29 de febrer
        d = today.replace(year=today.year - years, day=28)
    return d + timedelta(days=days_offset)


def at(minutes=0):
    return T0 + timedelta(minutes=minutes)


# ---------- Dades de prova (SQL pla, rol app + system_context) ----------

def sql(statement, params=None):
    """Executa SQL com a `system_context()` i retorna les files (si n'hi ha)."""
    with system_context():
        with connection.cursor() as cur:
            cur.execute(statement, params)
            return cur.fetchall() if cur.description else None


def add_list_row(kind, uid, refuge, minutes=None):
    """Afegeix un refugi a preferits (`FAV`) o visitats (`VIS`) de `uid` (`minutes=None`: `now()`)."""
    table = TABLES[kind]
    rid = getattr(refuge, 'pk', refuge)
    if minutes is None:
        sql(f'INSERT INTO {table} (user_uid, refuge_id) VALUES (%s, %s)', [uid, rid])
    else:
        sql(f'INSERT INTO {table} (user_uid, refuge_id, created_at) VALUES (%s, %s, %s)', [uid, rid, at(minutes)])


def list_rows(kind, uid=None):
    """`[(user_uid, refuge_id, created_at)]` ordenats per `(created_at, refuge_id)` (tots si `uid` es `None`)."""
    table = TABLES[kind]
    where, params = ('WHERE user_uid = %s', [uid]) if uid is not None else ('', [])
    return sql(f'SELECT user_uid, refuge_id, created_at FROM {table} {where} ORDER BY created_at, refuge_id', params)


def list_refuge_ids(kind, uid):
    return [r[1] for r in list_rows(kind, uid)]


USER_COLS = ('uid', 'language', 'created_at', 'age_confirmed_at', 'age_threshold', 'moderation_strikes',
             'is_blocked', 'blocked_reason', 'blocked_at')


def user_row(uid):
    """Fila de `users.users` com a diccionari (o `None`)."""
    rows = sql(f'SELECT {", ".join(USER_COLS)} FROM users.users WHERE uid = %s', [uid])
    return dict(zip(USER_COLS, rows[0])) if rows else None


def profile_row(uid):
    rows = sql('SELECT uid, username, updated_at FROM users.user_public_profiles WHERE uid = %s', [uid])
    return dict(zip(('uid', 'username', 'updated_at'), rows[0])) if rows else None


def avatar_rows(uid):
    return sql('SELECT key, thumb_key FROM users.user_avatars WHERE user_uid = %s ORDER BY key', [uid])


def make_avatar(uid, key=None, thumb_key=None, **fields):
    am = account_models()
    key = key or f'users-avatars/{uid}/{uuid.uuid4()}.webp'
    fields.setdefault('content_type', 'image/webp')
    with system_context():
        return am.UserAvatar.objects.create(key=key, user_id=uid, thumb_key=thumb_key, **fields)


def count_all(table):
    return sql(f'SELECT count(*) FROM {table}')[0][0]


# ---------- HTTP ----------

def api_get(client, path, claims=None, **extra):
    return _api_get(client, path, claims, ensure=False, **extra)


def api_delete(client, path, claims=None, **extra):
    return _api_delete(client, path, claims, ensure=False, **extra)


def _send(method, client, path, claims, body, extra):
    kwargs = dict(content_type='application/json', **extra)
    fn = getattr(client, method)
    args = {'data': json.dumps(body)} if body is not None else {}
    if claims is None:
        return fn(path, **args, **kwargs)
    with patch(VERIFY, return_value=claims):
        return fn(path, **args, HTTP_AUTHORIZATION='Bearer tok', **kwargs)


def api_post(client, path, claims=None, body=None, **extra):
    return _send('post', client, path, claims, body, extra)


def api_patch(client, path, claims=None, body=None, **extra):
    return _send('patch', client, path, claims, body, extra)


def url(uid, *parts):
    """`/api/users/{uid}/...`"""
    return f'/api/users/{uid}/' + ''.join(f'{p}/' for p in parts)
