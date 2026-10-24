"""
Ajudes de test del domini refugis (chunk 2).

Els models de producció (`apps.refuges`, `apps.accounts`) encara no existeixen quan s'escriuen els tests:
s'importen **de manera mandrosa** (`refuge_models()`, `account_models()`) perquè cada test falli pel seu propi motiu
(`ModuleNotFoundError: apps.refuges`) en lloc de trencar la col·lecció de tota la suite.

Les dades de prova s'escriuen amb el rol `app` dins `system_context()`, llevat del catàleg (`refuges`, `refuge_amenities`,
`refuge_links`): `app` no hi té escriptura fins al chunk 8 (§7.2), i `as_owner()` el crea amb el rol de proves
`test_fixtures` (`BYPASSRLS`, només existeix a la BD de proves: `scripts/dev/setup_local_postgres.sh`) dins la mateixa
transacció del test.
"""
import importlib
import json
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone as dt_timezone
from pathlib import Path
from unittest.mock import patch

from django.db import connection
from django.test.utils import CaptureQueriesContext

ROOT = Path(__file__).resolve().parents[3]
JSON_PATH = ROOT / 'api' / 'utils' / 'final_data_refuges.json'
VERIFY = 'api.middleware.firebase_auth_middleware.auth.verify_id_token'

AMENITY_FIELDS = ('manque_un_mur', 'cheminee', 'poele', 'couvertures', 'latrines', 'bois', 'eau', 'matelas',
                  'couchage', 'bas_flancs', 'lits', 'mezzanine_etage')
REFUGE_TYPES = ('non gardé', 'fermée', 'cabane ouverte mais ocupee par le berger l ete', 'orri', 'emergence',
                'key_needed')
BASE_KEYS = {'id', 'name', 'coord', 'altitude', 'places', 'info_comp', 'description', 'links', 'type',
             'modified_at', 'region', 'departement', 'condition'}
MEDIA_ITEM_KEYS = {'key', 'url', 'thumb_url', 'media_type', 'width', 'height', 'blurhash', 'creator_uid',
                   'uploaded_at', 'taken_at', 'experience_id'}

T0 = datetime(2025, 1, 1, 10, 0, tzinfo=dt_timezone.utc)


def refuge_models():
    return importlib.import_module('apps.refuges.models')


def account_models():
    return importlib.import_module('apps.accounts.models')


def load_json():
    return json.loads(JSON_PATH.read_text(encoding='utf-8'))


# ---------- Dades de prova (rol app + system_context) ----------

def make_user(uid='u1', username='', **fields):
    """Fila de `users.users` + `user_public_profiles` (es creen a la mateixa transacció, com a l'alta real)."""
    from apps.core.rls import system_context
    am = account_models()
    with system_context():
        user = am.UserAccount.objects.create(uid=uid, **fields)
        am.UserPublicProfile.objects.create(user_id=uid, username=username)
    return user


@contextmanager
def as_owner():
    """Escriu amb el rol de proves `test_fixtures` (sense RLS) a la connexió `default`, dins la transacció en curs."""
    with connection.cursor() as cursor:
        cursor.execute('SET ROLE test_fixtures')
    yield
    # Només si no hi ha hagut excepció: si n'hi ha, la transacció (o el punt de desat) està avortada i el seu
    # `ROLLBACK` ja desfà el `SET ROLE`; executar res aquí faria fallar el `ROLLBACK TO SAVEPOINT` de Django.
    with connection.cursor() as cursor:
        cursor.execute('RESET ROLE')


def make_refuge(name='Refugi Test', lat=42.5, long=1.5, amenities=None, links=None, **fields):
    """Refugi + amenities (sempre, invariant §2.6) + enllaços ordenats (com a propietari: `as_owner()`)."""
    from django.contrib.gis.geos import Point
    rm = refuge_models()
    fields.setdefault('type_id', fields.pop('type', 'non gardé'))
    with as_owner():
        refuge = rm.Refuge.objects.create(name=name, coord=Point(long, lat, srid=4326), **fields)
        rm.RefugeAmenities.objects.create(refuge=refuge, **(amenities or {}))
        for position, url in enumerate(links or []):
            rm.RefugeLink.objects.create(refuge=refuge, position=position, url=url)
    return refuge


def make_media(refuge, creator_uid, key=None, status='visible', minutes=0, **fields):
    from apps.core.rls import system_context
    rm = refuge_models()
    key = key or f'refugis-lliures/{refuge.pk}/{creator_uid}-{minutes}-{status}.webp'
    fields.setdefault('media_type', 'image')
    fields.setdefault('content_type', 'image/webp')
    fields.setdefault('rights_confirmed_at', T0)
    with system_context():
        return rm.RefugeMedia.objects.create(
            key=key, refuge=refuge, creator_id=creator_uid, status=status,
            uploaded_at=T0 + timedelta(minutes=minutes), **fields)


# ---------- HTTP ----------

def api_get(client, path, claims=None, **extra):
    """GET com a anònim (`claims=None`) o amb un token de Firebase simulat (el middleware el verifica)."""
    if claims is None:
        return client.get(path, **extra)
    with patch(VERIFY, return_value=claims):
        return client.get(path, HTTP_AUTHORIZATION='Bearer tok', **extra)


def api_delete(client, path, claims=None, **extra):
    if claims is None:
        return client.delete(path, **extra)
    with patch(VERIFY, return_value=claims):
        return client.delete(path, HTTP_AUTHORIZATION='Bearer tok', **extra)


def user_claims(uid='u1'):
    return {'uid': uid, 'role': 'user'}


def admin_claims(uid='adm'):
    return {'uid': uid, 'role': 'admin'}


# ---------- Comptatge de consultes (sense el soroll de transacció/context) ----------

_NOISE = ('set_config', 'SAVEPOINT', 'RELEASE SAVEPOINT', 'ROLLBACK TO SAVEPOINT')


class QueryCounter:
    """`with QueryCounter() as q: ...; q.count`, sense `set_config` (§5.3) ni punts de desat."""

    def __enter__(self):
        self._ctx = CaptureQueriesContext(connection)
        self._ctx.__enter__()
        return self

    def __exit__(self, *exc):
        self._ctx.__exit__(*exc)
        self.queries = [q['sql'] for q in self._ctx.captured_queries
                        if not any(n in q['sql'] for n in _NOISE)]
        self.count = len(self.queries)
        return False
