"""
Ajudes de test del domini reformes (chunk 5).

Reutilitza les dels chunks 2 i 3 (`apps.accounts.tests.helpers`: `make_user`, `make_refuge`, `api_*`, `sql`,
`QueryCounter`, `user_claims`, `admin_claims`...). Aquí s'hi afegeixen les dades de prova de reformes.

Els models de producció (`apps.renovations`) encara no existeixen quan s'escriuen els tests: s'importen de manera
mandrosa (`renovation_models()`) perquè cada test falli pel seu propi motiu. Les dades de prova es creen amb SQL pla
(rol `app` dins `system_context()`), per no dependre del nom dels models; els tests de models sí que els fan servir.

IMPORTANT: els `api_*` NO creen el perfil de qui fa la petició (com al chunk 3): cal `make_user`. Els tests de vistes
porten el marker `real_permissions` perquè `HasProfile` consulti Postgres de debò.
"""
import importlib
import uuid
from datetime import timedelta

from apps.accounts.tests.helpers import (  # noqa: F401  (re-exportats)
    PROFILE_REQUIRED, QueryCounter, T0, VERIFY, account_models, admin_claims, api_delete, api_get, api_patch,
    api_post, as_owner, at, count_all, make_refuge, make_user, madrid_today, refuge_models, sql, user_claims)

RENOVATIONS = '/api/renovations/'
LINK = 'https://chat.whatsapp.com/abc123'

# Claus de l'API d'una reforma (§5.2). `group_link` només hi és per al creador, els participants i els admins.
BASE_KEYS = {'id', 'creator_uid', 'refuge_id', 'ini_date', 'fin_date', 'description', 'materials_needed',
             'participants_uids'}
FULL_KEYS = BASE_KEYS | {'group_link'}

T = {'renovations': 'activity.renovations', 'links': 'activity.renovation_group_links',
     'participants': 'activity.renovation_participants', 'expelled': 'activity.renovation_expelled'}


def renovation_models():
    return importlib.import_module('apps.renovations.models')


def day(offset=0):
    """Data d'avui a Madrid (+ `offset` dies)."""
    return madrid_today() + timedelta(days=offset)


def reno_url(rid, *parts):
    """`/api/renovations/{id}/...`"""
    return f'{RENOVATIONS}{rid}/' + ''.join(f'{p}/' for p in parts)


def refuge_reno_url(refuge_id):
    return f'/api/refuges/{refuge_id}/renovations/'


def make_renovation(refuge, creator='u1', ini=None, fin=None, description='Pintar la cabana', materials=None,
                    link=LINK, participants=(), expelled=()):
    """
    Crea una reforma amb SQL pla (`system_context()`) i en retorna l'id (`uuid.UUID`).

    - `creator=None`: reforma anònima (creador esborrat); no té enllaç.
    - `link=None`: sense fila a `renovation_group_links`. ATENCIÓ: amb creador, el *constraint trigger* diferit
      `renovations_requires_link` fa fallar la verificació de final de test de Django (`check_constraints`); només es
      pot usar amb `creator=None` o si el test hi afegeix l'enllaç abans d'acabar.
    - `participants`/`expelled`: UIDs (els usuaris han d'existir); es desen en l'ordre donat (`created_at` creixent).
    """
    ini = ini or day(5)
    fin = fin or day(10)
    rid = refuge.pk if hasattr(refuge, 'pk') else refuge
    with_link = creator is not None and link is not None
    row = sql('INSERT INTO activity.renovations (refuge_id, creator_uid, ini_date, fin_date, description, '
              'materials_needed) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id',
              [rid, creator, ini, fin, description, materials])
    reno_id = row[0][0]
    if with_link:
        sql('INSERT INTO activity.renovation_group_links (renovation_id, group_link) VALUES (%s, %s)',
            [reno_id, link])
    for i, uid in enumerate(participants):
        sql('INSERT INTO activity.renovation_participants (renovation_id, user_uid, created_at) VALUES (%s, %s, %s)',
            [reno_id, uid, at(i)])
    for i, uid in enumerate(expelled):
        sql('INSERT INTO activity.renovation_expelled (renovation_id, user_uid, expelled_at) VALUES (%s, %s, %s)',
            [reno_id, uid, at(i)])
    return reno_id


def constraint_name(excinfo):
    """Nom de la restricció que ha fet fallar la sentència (`diag.constraint_name` de psycopg), que és el que el servei
    fa servir per traduir l'error (p. ex. `renovations_no_overlap` → 409)."""
    cause = excinfo.value.__cause__
    return getattr(getattr(cause, 'diag', None), 'constraint_name', None)


def renovation_row(rid):
    """Fila de `activity.renovations` com a diccionari (o `None`)."""
    cols = ('id', 'refuge_id', 'creator_uid', 'ini_date', 'fin_date', 'description', 'materials_needed', 'created_at')
    rows = sql(f'SELECT {", ".join(cols)} FROM activity.renovations WHERE id = %s', [rid])
    return dict(zip(cols, rows[0])) if rows else None


def link_of(rid):
    rows = sql('SELECT group_link FROM activity.renovation_group_links WHERE renovation_id = %s', [rid])
    return rows[0][0] if rows else None


def participants_of(rid):
    return [r[0] for r in sql('SELECT user_uid FROM activity.renovation_participants WHERE renovation_id = %s '
                              'ORDER BY created_at, user_uid', [rid])]


def expelled_of(rid):
    return [r[0] for r in sql('SELECT user_uid FROM activity.renovation_expelled WHERE renovation_id = %s '
                              'ORDER BY expelled_at, user_uid', [rid])]


def count_renovations():
    return count_all('activity.renovations')


def new_body(refuge, **overrides):
    """Cos vàlid d'un `POST /renovations/` (reforma d'aquí a 5-10 dies)."""
    body = {'refuge_id': str(refuge.pk), 'ini_date': day(5).isoformat(), 'fin_date': day(10).isoformat(),
            'description': 'Canviar el sostre', 'group_link': LINK}
    body.update(overrides)
    return body


def missing_uuid():
    return str(uuid.uuid4())
