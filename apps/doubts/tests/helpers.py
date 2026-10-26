"""
Ajudes de test del domini dubtes i respostes (chunk 6).

Reutilitza les dels chunks 2 i 3 (`make_user`, `make_refuge`, `as_owner`, `QueryCounter`, `api_*`, `sql`...). Els models
de producció (`apps.doubts`) encara no existeixen quan s'escriuen els tests: s'importen de manera mandrosa
(`doubt_models()`) perquè cada test falli pel seu propi motiu.

Les files de `activity.doubts` / `activity.answers` es creen amb SQL pla (rol `app` dins `system_context()`, que passa la
RLS) perquè els fixtures no depenguin del nom dels models ni dels services; els tests de models i de services sí que
usen `Doubt` / `Answer` i `apps.doubts.services`.

Els helpers HTTP **no** creen el perfil de qui fa la petició (`ensure=False`): els tests han de crear l'usuari amb
`make_user` (o provar `profile_required`).
"""
import importlib
import uuid
from datetime import datetime, timezone as dt_timezone

from apps.accounts.tests.helpers import (  # noqa: F401  (re-exportats)
    QueryCounter, T0, VERIFY, admin_claims, api_delete, api_get, api_post, as_owner, at, make_refuge, make_user, sql,
    user_claims)

from apps.accounts.tests.helpers import make_user as _make_user

DOUBTS = '/api/doubts/'
DOUBT_BASE_KEYS = {'id', 'refuge_id', 'creator_uid', 'message', 'created_at', 'answers_count'}
ANSWER_KEYS = {'id', 'creator_uid', 'message', 'created_at', 'parent_answer_id'}
NOT_OWNER = 'not_owner'


def make_user(uid='u1', username='', **fields):
    """Usuari amb l'edat confirmada (les escriptures de dubtes exigeixen `IsAgeConfirmed`); es pot sobreescriure."""
    fields.setdefault('age_confirmed_at', at())
    fields.setdefault('age_threshold', 16)
    return _make_user(uid, username, **fields)


def doubt_models():
    return importlib.import_module('apps.doubts.models')


# ---------- Rutes ----------

def doubt_url(doubt_id):
    return f'{DOUBTS}{doubt_id}/'


def answers_url(doubt_id):
    return f'{DOUBTS}{doubt_id}/answers/'


def answer_url(doubt_id, answer_id):
    return f'{DOUBTS}{doubt_id}/answers/{answer_id}/'


def list_url(refuge_id):
    return f'{DOUBTS}?refuge_id={refuge_id}'


# ---------- Dades de prova (SQL pla, rol app + system_context) ----------

def make_doubt(refuge, creator_uid, message='Hi ha aigua?', minutes=0):
    """Insereix un dubte i en retorna l'id (`str`). `created_at` = `T0 + minutes`."""
    rid = getattr(refuge, 'pk', refuge)
    rows = sql('INSERT INTO activity.doubts (refuge_id, creator_uid, message, created_at) VALUES (%s, %s, %s, %s) '
               'RETURNING id', [rid, creator_uid, message, at(minutes)])
    return str(rows[0][0])


def make_answer(doubt_id, creator_uid, message='Sí, hi ha una font', parent=None, minutes=0, answer_id=None):
    """Insereix una resposta (`parent` = id de la resposta pare o `None`) i en retorna l'id (`str`)."""
    if answer_id is None:
        rows = sql('INSERT INTO activity.answers (doubt_id, creator_uid, parent_answer_id, message, created_at) '
                   'VALUES (%s, %s, %s, %s, %s) RETURNING id', [doubt_id, creator_uid, parent, message, at(minutes)])
    else:
        rows = sql('INSERT INTO activity.answers (id, doubt_id, creator_uid, parent_answer_id, message, created_at) '
                   'VALUES (%s, %s, %s, %s, %s, %s) RETURNING id',
                   [answer_id, doubt_id, creator_uid, parent, message, at(minutes)])
    return str(rows[0][0])


def doubt_rows(refuge=None):
    """`[(id, refuge_id, creator_uid, message, created_at)]` ordenats per `(created_at, id)` (`id`/`refuge_id` com a `str`)."""
    where, params = ('WHERE refuge_id = %s', [getattr(refuge, 'pk', refuge)]) if refuge is not None else ('', [])
    rows = sql(f'SELECT id, refuge_id, creator_uid, message, created_at FROM activity.doubts {where} '
               'ORDER BY created_at, id', params)
    return [(str(r[0]), str(r[1]), r[2], r[3], r[4]) for r in rows]


def answer_rows(doubt_id=None):
    """`[(id, doubt_id, creator_uid, parent_answer_id, message, created_at)]` ordenats per `(created_at, id)`."""
    where, params = ('WHERE doubt_id = %s', [doubt_id]) if doubt_id is not None else ('', [])
    rows = sql('SELECT id, doubt_id, creator_uid, parent_answer_id, message, created_at '
               f'FROM activity.answers {where} ORDER BY created_at, id', params)
    return [(str(r[0]), str(r[1]), r[2], str(r[3]) if r[3] else None, r[4], r[5]) for r in rows]


def doubt_ids(refuge=None):
    return [r[0] for r in doubt_rows(refuge)]


def answer_ids(doubt_id=None):
    return [r[0] for r in answer_rows(doubt_id)]


def answers_of(doubt_json):
    """`answers` d'un dubte del JSON: la clau hi és sempre, `[]` si no n'hi ha (D30)."""
    return doubt_json['answers']


def is_uuid(value):
    try:
        return str(uuid.UUID(value)) == value
    except (ValueError, AttributeError, TypeError):
        return False


def utc(*args):
    return datetime(*args, tzinfo=dt_timezone.utc)


def build_tree(refuge, doubt_creator='u1'):
    """Dubte `d` (de `doubt_creator`) amb l'arbre de respostes:

        a1 (u2)
        ├── a1r (u3)
        │   └── a1rr (u1)
        └── a1s (u2)
        a2 (u3)

    Retorna `(d, {'a1':…, 'a1r':…, 'a1rr':…, 'a1s':…, 'a2':…})` (ids `str`, `created_at` creixent en aquest ordre).
    """
    d = make_doubt(refuge, doubt_creator, minutes=0)
    a = {}
    a['a1'] = make_answer(d, 'u2', 'a1', minutes=1)
    a['a1r'] = make_answer(d, 'u3', 'a1r', parent=a['a1'], minutes=2)
    a['a1rr'] = make_answer(d, 'u1', 'a1rr', parent=a['a1r'], minutes=3)
    a['a1s'] = make_answer(d, 'u2', 'a1s', parent=a['a1'], minutes=4)
    a['a2'] = make_answer(d, 'u3', 'a2', minutes=5)
    return d, a
