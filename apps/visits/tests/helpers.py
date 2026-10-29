"""
Ajudes de test del domini visites (chunk 4).

Reutilitza les dels chunks 2 i 3 (`apps.accounts.tests.helpers`: `make_user`, `make_refuge`, `sql`, `QueryCounter`,
`api_get`/`api_post`/`api_patch`/`api_delete` sense crear el perfil de qui fa la peticio...). IMPORTANT: igual que a
`apps/accounts`, els tests han de crear l'usuari amb `make_user` abans de fer una peticio com a ell.

Els models de produccio (`apps.visits.models`) encara no existeixen quan s'escriuen els tests: s'importen de manera
mandrosa (`visit_models()`) i les files de prova es creen amb SQL pla (rol `app` dins `system_context()`), perque
els fixtures no depenguin del nom dels models. Nomes `test_models_constraints.py` fa servir els models.
"""
import importlib
import uuid
from datetime import date, timedelta

from apps.accounts.tests.helpers import (  # noqa: F401  (re-exportats)
    QueryCounter, admin_claims, api_delete, api_get, api_patch, api_post, as_owner, make_refuge, make_user, sql,
    user_claims)

_make_user = make_user


def make_user(uid='u1', username='', **fields):
    """Usuari amb perfil i edat confirmada per defecte (POST/PATCH exigeixen `IsAgeConfirmed`); es pot sobreescriure."""
    from apps.accounts.tests.helpers import at
    fields.setdefault('age_confirmed_at', at(0))
    fields.setdefault('age_threshold', 16)
    return _make_user(uid, username=username, **fields)


PROFILE_REQUIRED = 'profile_required'
VISIT_KEYS = {'date', 'refuge_id', 'total_visitors', 'is_visitor', 'num_visitors'}

VISITS = 'activity.refuge_visits'
PARTS = 'activity.refuge_visit_participants'
TOTALS = 'activity.refuge_visit_totals'


def visit_models():
    return importlib.import_module('apps.visits.models')


def visit_services():
    return importlib.import_module('apps.visits.services')


def visit_selectors():
    return importlib.import_module('apps.visits.selectors')


# ---------- Dates (sempre l'avui de Madrid, mai el de la BD ni el d'UTC) ----------

def today():
    from apps.core.timezone_utils import get_madrid_today
    return get_madrid_today()


def day(offset=0):
    """Data de negoci: l'avui de Madrid +/- `offset` dies."""
    return today() + timedelta(days=offset)


def months_ago(d, months):
    """`d` menys `months` mesos naturals (29/02 -> 28/02), com la purga de 12 mesos (§8.3)."""
    y, m = divmod(d.year * 12 + d.month - 1 - months, 12)
    y, m = y, m + 1
    last = (date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1)).day
    return date(y, m, min(d.day, last))


# ---------- Dades de prova (SQL pla, rol app + system_context) ----------

def make_visit(refuge, visit_date, participants=None):
    """Fila de `refuge_visits` + participants (`{uid: num_visitors}`); retorna l'`id` (UUID) de la visita."""
    rid = getattr(refuge, 'pk', refuge)
    visit_id = sql(f'INSERT INTO {VISITS} (refuge_id, visit_date) VALUES (%s, %s) RETURNING id', [rid, visit_date])[0][0]
    for uid, num in (participants or {}).items():
        add_participant(visit_id, uid, num)
    return visit_id


def add_participant(visit_id, uid, num_visitors=1):
    sql(f'INSERT INTO {PARTS} (visit_id, user_uid, num_visitors) VALUES (%s, %s, %s)', [visit_id, uid, num_visitors])


def visit_rows(refuge=None):
    """`[(id, refuge_id, visit_date)]` ordenats per `(visit_date, refuge_id)`."""
    where, params = ('WHERE refuge_id = %s', [getattr(refuge, 'pk', refuge)]) if refuge is not None else ('', [])
    return sql(f'SELECT id, refuge_id, visit_date FROM {VISITS} {where} ORDER BY visit_date, refuge_id', params)


def visit_dates(refuge=None):
    return [r[2] for r in visit_rows(refuge)]


def participant_rows(visit_id=None):
    """`{uid: num_visitors}` (tots els participants o els d'una visita)."""
    where, params = ('WHERE visit_id = %s', [visit_id]) if visit_id is not None else ('', [])
    return dict(sql(f'SELECT user_uid, num_visitors FROM {PARTS} {where}', params))


def total_of(visit_id):
    """Total de la vista `refuge_visit_totals` (0 si la visita no te participants)."""
    rows = sql(f'SELECT total_visitors FROM {TOTALS} WHERE visit_id = %s', [visit_id])
    return rows[0][0] if rows else 0


def visited_ids(uid):
    return [r[0] for r in sql('SELECT refuge_id FROM users.user_visited_refuges WHERE user_uid = %s '
                              'ORDER BY created_at, refuge_id', [uid])]


def visit_id_of(refuge, visit_date):
    rows = sql(f'SELECT id FROM {VISITS} WHERE refuge_id = %s AND visit_date = %s',
               [getattr(refuge, 'pk', refuge), visit_date])
    return rows[0][0] if rows else None


# ---------- URLs ----------

def refuge_visits_url(refuge_id):
    return f'/api/refuges/{refuge_id}/visits/'


def visit_url(refuge_id, visit_date):
    return f'/api/refuges/{refuge_id}/visits/{visit_date}/'


def user_visits_url(uid):
    return f'/api/users/{uid}/visits/'


def unknown_id():
    return str(uuid.uuid4())
