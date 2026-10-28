"""
Ajudes de test del domini propostes de refugi (chunk 8).

Reutilitza les dels chunks 2-6 (`make_user` amb l'edat confirmada, `make_refuge`, `as_owner`, `sql`, `QueryCounter`,
`api_*`...). Els models de producció (`apps.proposals`) encara no existeixen quan s'escriuen els tests: s'importen de
manera mandrosa (`proposal_models()`) perquè cada test falli pel seu propi motiu.

Les files de `proposals.refuge_proposals` dels fixtures es creen amb SQL pla (rol `app` dins `system_context()`, que
passa la RLS i **no** salta els `CHECK`) perquè no depenguin del nom dels models ni dels services. El catàleg de
refugis es crea com a propietari (`as_owner()`), igual que als chunks anteriors.
"""
import importlib
import json
import uuid
from datetime import datetime, timedelta, timezone as dt_timezone

from apps.doubts.tests.helpers import (  # noqa: F401  (re-exportats)
    QueryCounter, T0, VERIFY, admin_claims, api_delete, api_get, api_post, as_owner, at, is_uuid,
    make_refuge, make_user, sql, user_claims)
from apps.refuges.tests.helpers import make_media  # noqa: F401

PROPOSALS = '/api/refuges-proposals/'
MINE = '/api/my-refuges-proposals/'
REFUGES = '/api/refuges/'

PROPOSAL_KEYS = {'id', 'refuge_id', 'refuge_snapshot', 'action', 'payload', 'comment', 'status', 'creator_uid',
                 'created_at', 'reviewer_uid', 'reviewed_at', 'rejection_reason'}
ALLOWED_REFUGE_FIELDS = ['altitude', 'condition', 'coord', 'departement', 'description', 'info_comp', 'links', 'name',
                         'places', 'region', 'type']          # llista blanca sense `remarque` (S-6)
INFO_COMP_FIELDS = ['manque_un_mur', 'cheminee', 'poele', 'couvertures', 'latrines', 'bois', 'eau', 'matelas',
                    'couchage', 'bas_flancs', 'lits', 'mezzanine_etage']
SNAPSHOT_KEYS = {'id', 'name', 'coord', 'altitude', 'places', 'info_comp', 'description', 'links', 'type',
                 'modified_at', 'region', 'departement', 'condition'}      # refugi en forma d'API sense visitors/mitjans
DELETED_REASON = 'refuge has been deleted'
UNKNOWN = 'unknown'


def proposal_models():
    return importlib.import_module('apps.proposals.models')


def approve_url(proposal_id):
    return f'{PROPOSALS}{proposal_id}/approve/'


def reject_url(proposal_id):
    return f'{PROPOSALS}{proposal_id}/reject/'


# ---------- Cossos de petició ----------

def new_payload(**over):
    payload = {'name': 'Refugi Nou', 'coord': {'long': 1.234, 'lat': 42.567}, 'altitude': 1800, 'places': 15,
               'type': 'non gardé', 'info_comp': {'cheminee': 1, 'eau': 1, 'lits': 1}}
    payload.update(over)
    return payload


def create_body(comment='Descobert durant una excursió', **payload_over):
    return {'action': 'create', 'payload': new_payload(**payload_over), 'comment': comment}


def update_body(refuge, payload=None, comment='Canvi'):
    return {'action': 'update', 'refuge_id': str(getattr(refuge, 'pk', refuge)),
            'payload': {'places': 45} if payload is None else payload, 'comment': comment}


def delete_body(refuge, comment='Destruït per una allau'):
    return {'action': 'delete', 'refuge_id': str(getattr(refuge, 'pk', refuge)), 'comment': comment}


# ---------- Dades de prova (SQL pla) ----------

def snapshot_of(refuge, **over):
    """Còpia mínima d'un refugi en forma d'API (la foto històrica que desa una proposta `update`/`delete`)."""
    data = {'id': str(refuge.pk), 'name': refuge.name, 'coord': {'lat': 42.5, 'long': 1.5}, 'altitude': None,
            'places': None, 'info_comp': {f: 0 for f in INFO_COMP_FIELDS}, 'description': '', 'links': [],
            'type': 'non gardé', 'modified_at': None, 'region': None, 'departement': None, 'condition': None}
    data.update(over)
    return data


def _json(value):
    return json.dumps(value) if value is not None else None


_UNSET = object()


def make_proposal(action='create', *, creator='u1', refuge=None, payload=_UNSET, snapshot=_UNSET, comment=None,
                  status='pending', reviewer=None, reviewed_at=None, rejection_reason=None, minutes=0,
                  created_at=None):
    """Insereix una proposta i en retorna l'`id` (`str`). `created_at` = `T0 + minutes` si no s'indica.

    Per defecte `create` porta un payload mínim vàlid, `update` el canvi `{'places': 20}` i `delete` cap payload;
    `update`/`delete` exigeixen `refuge` i en desen una foto (`snapshot_of`). Una proposta `approved`/`rejected`
    rep per defecte `reviewer='adm'` i `reviewed_at = created_at + 1 min` (el `CHECK` de revisió ho exigeix).
    """
    if payload is _UNSET:
        payload = {'create': new_payload(), 'update': {'places': 20}, 'delete': None}[action]
    if snapshot is _UNSET:
        snapshot = snapshot_of(refuge) if action in ('update', 'delete') else None
    created = created_at or at(minutes)
    if status != 'pending':
        reviewed_at = reviewed_at or created + timedelta(minutes=1)
        reviewer = reviewer if reviewer is not None else 'adm'
    refuge_id = getattr(refuge, 'pk', refuge)
    rows = sql(
        'INSERT INTO proposals.refuge_proposals (refuge_id, action, status, payload, refuge_snapshot, comment, '
        'creator_uid, created_at, reviewer_uid, reviewed_at, rejection_reason) '
        'VALUES (%s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s, %s, %s, %s) RETURNING id',
        [refuge_id, action, status, _json(payload), _json(snapshot), comment, creator, created, reviewer,
         reviewed_at, rejection_reason])
    return str(rows[0][0])


PROPOSAL_COLS = ('id', 'refuge_id', 'action', 'status', 'payload', 'refuge_snapshot', 'comment', 'creator_uid',
                 'created_at', 'reviewer_uid', 'reviewed_at', 'rejection_reason')


def proposal_row(proposal_id):
    """Fila de `proposals.refuge_proposals` com a diccionari (`id`/`refuge_id` com a `str`) o `None`."""
    rows = sql(f'SELECT {", ".join(PROPOSAL_COLS)} FROM proposals.refuge_proposals WHERE id = %s', [proposal_id])
    if not rows:
        return None
    row = dict(zip(PROPOSAL_COLS, rows[0]))
    row['id'] = str(row['id'])
    row['refuge_id'] = str(row['refuge_id']) if row['refuge_id'] else None
    return row


def proposal_ids(status=None):
    where, params = ('WHERE status = %s', [status]) if status else ('', [])
    return {str(r[0]) for r in sql(f'SELECT id FROM proposals.refuge_proposals {where}', params)}


def count_proposals():
    return sql('SELECT count(*) FROM proposals.refuge_proposals')[0][0]


def refuge_ids():
    return {str(r[0]) for r in sql('SELECT id FROM refuges.refuges')}


def refuge_state(refuge_id):
    """Estat complet d'un refugi (columnes, serveis `amenities` i enllaços per `position`) o `None`."""
    rows = sql('SELECT name, surname, type, ST_X(coord::geometry), ST_Y(coord::geometry), altitude, places, '
               'description, region, departement, modified_at, condition, num_contributed_conditions, '
               'condition_reset_at FROM refuges.refuges WHERE id = %s', [refuge_id])
    if not rows:
        return None
    keys = ('name', 'surname', 'type', 'long', 'lat', 'altitude', 'places', 'description', 'region', 'departement',
            'modified_at', 'condition', 'n', 'condition_reset_at')
    state = dict(zip(keys, rows[0]))
    cols = ', '.join(INFO_COMP_FIELDS)
    am = sql(f'SELECT {cols} FROM refuges.refuge_amenities WHERE refuge_id = %s', [refuge_id])
    state['amenities'] = dict(zip(INFO_COMP_FIELDS, am[0])) if am else None
    state['links'] = [r[0] for r in sql('SELECT url FROM refuges.refuge_links WHERE refuge_id = %s '
                                        'ORDER BY position', [refuge_id])]
    state['link_positions'] = [r[0] for r in sql('SELECT position FROM refuges.refuge_links WHERE refuge_id = %s '
                                                 'ORDER BY position', [refuge_id])]
    return state


def utc(*args):
    return datetime(*args, tzinfo=dt_timezone.utc)


def new_refuge_id(proposal_id):
    """`refuge_id` que l'aprovació d'una proposta `create` ha desat a la proposta."""
    return proposal_row(proposal_id)['refuge_id']


def uuid7_ok(value):
    return is_uuid(value) and uuid.UUID(value).version == 7
