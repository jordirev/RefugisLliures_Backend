"""
Ajudes de test del domini experiències (chunk 7).

Reutilitza les dels chunks 2 i 3 (`make_user`, `make_refuge`, `make_media`, `as_owner`, `QueryCounter`, `api_*`, `sql`...).
Els models de producció (`apps.experiences`) encara no existeixen quan s'escriuen els tests: s'importen de manera
mandrosa (`experience_models()`) perquè cada test falli pel seu propi motiu.

Les files de `activity.experiences` es creen amb SQL pla (rol `app` dins `system_context()`, que passa la RLS). Compte:
el *trigger* de condició (§2.9) també s'executa en aquests `INSERT`, de manera que `make_experience` **sí que vota** a la
mitjana del refugi (com ho faria un POST). Els tests de la mitjana en parteixen i comproven el resultat esperat.

Els helpers HTTP **no** creen el perfil de qui fa la petició (`ensure=False`): els tests han de crear l'usuari amb
`make_user` (o provar `profile_required`).
"""
import importlib
import uuid
from datetime import datetime, timezone as dt_timezone

from apps.accounts.tests.helpers import (  # noqa: F401  (re-exportats)
    MEDIA_ITEM_KEYS, QueryCounter, T0, VERIFY, admin_claims, api_delete, api_get, api_patch, api_post, as_owner, at,
    count_all, make_media, make_refuge, sql, user_claims)

from apps.accounts.tests.helpers import make_user as _make_user

EXPERIENCES = '/api/experiences/'
EXP_KEYS = {'id', 'refuge_id', 'creator_uid', 'modified_at', 'comment', 'condition', 'images_metadata'}
NOT_OWNER = 'not_owner'
ZERO_UUID = '00000000-0000-0000-0000-000000000000'


def make_user(uid='u1', username='', **fields):
    """Usuari amb l'edat confirmada (POST/PATCH d'experiències exigeixen `IsAgeConfirmed`); es pot sobreescriure."""
    fields.setdefault('age_confirmed_at', at())
    fields.setdefault('age_threshold', 16)
    return _make_user(uid, username, **fields)


def experience_models():
    return importlib.import_module('apps.experiences.models')


# ---------- Rutes ----------

def exp_url(experience_id):
    return f'{EXPERIENCES}{experience_id}/'


def list_url(refuge_id):
    return f'{EXPERIENCES}?refuge_id={refuge_id}'


def new_body(refuge, comment='Refugi net i amb llenya.', condition=2):
    return {'refuge_id': str(getattr(refuge, 'pk', refuge)), 'comment': comment, 'condition': condition}


# ---------- Dades de prova (SQL pla, rol app + system_context) ----------

def make_experience(refuge, creator_uid, comment='Refugi net', condition=2, minutes=0, experience_id=None):
    """Insereix una experiència i en retorna l'id (`str`). `created_at` = `modified_at` = `T0 + minutes`.

    Atenció: el *trigger* de condició vota a la mitjana del refugi (`condition_counted_at` el posa el trigger)."""
    rid = getattr(refuge, 'pk', refuge)
    cols = ['refuge_id', 'creator_uid', 'comment', 'condition', 'created_at', 'modified_at']
    params = [rid, creator_uid, comment, condition, at(minutes), at(minutes)]
    if experience_id is not None:
        cols.insert(0, 'id')
        params.insert(0, experience_id)
    rows = sql(f'INSERT INTO activity.experiences ({", ".join(cols)}) VALUES ({", ".join(["%s"] * len(cols))}) '
               'RETURNING id', params)
    return str(rows[0][0])


EXP_COLS = ('id', 'refuge_id', 'creator_uid', 'comment', 'created_at', 'modified_at', 'condition',
            'condition_counted_at')


def exp_row(experience_id):
    """Fila d'`activity.experiences` com a diccionari (`id`/`refuge_id` com a `str`) o `None`."""
    rows = sql(f'SELECT {", ".join(EXP_COLS)} FROM activity.experiences WHERE id = %s', [experience_id])
    if not rows:
        return None
    row = dict(zip(EXP_COLS, rows[0]))
    row['id'], row['refuge_id'] = str(row['id']), str(row['refuge_id'])
    return row


def exp_ids(refuge=None, creator_uid=None):
    where, params = [], []
    if refuge is not None:
        where.append('refuge_id = %s')
        params.append(getattr(refuge, 'pk', refuge))
    if creator_uid is not None:
        where.append('creator_uid = %s')
        params.append(creator_uid)
    clause = ('WHERE ' + ' AND '.join(where)) if where else ''
    return [str(r[0]) for r in sql(f'SELECT id FROM activity.experiences {clause} ORDER BY created_at, id', params)]


def refuge_state(refuge):
    """`(condition, num_contributed_conditions, condition_reset_at)` del refugi."""
    rid = getattr(refuge, 'pk', refuge)
    return sql('SELECT condition, num_contributed_conditions, condition_reset_at FROM refuges.refuges WHERE id = %s',
               [rid])[0]


def set_refuge_state(refuge, condition, n, reset_at=None):
    """Fixa la mitjana del refugi (com a propietari del catàleg: `app` no pot fer `UPDATE refuges`)."""
    rid = getattr(refuge, 'pk', refuge)
    with as_owner():
        sql('UPDATE refuges.refuges SET condition = %s, num_contributed_conditions = %s, condition_reset_at = %s '
            'WHERE id = %s', [condition, n, reset_at, rid])


def set_counted_at(experience_id, when):
    """Fixa `condition_counted_at` (el *trigger* només el toca en comptar un vot nou)."""
    with as_owner():
        sql('UPDATE activity.experiences SET condition_counted_at = %s WHERE id = %s', [when, experience_id])


def make_exp_media(refuge, creator_uid, experience_id, key=None, status='visible', minutes=0, **fields):
    """Fila de `refuge_media` lligada a una experiència (substitueix `media_keys`)."""
    key = key or f'refugis-lliures/{refuge.pk}/{creator_uid}-exp-{minutes}-{status}.webp'
    return make_media(refuge, creator_uid, key=key, status=status, minutes=minutes, experience_id=experience_id,
                      **fields)


def media_keys_of(experience_id):
    rows = sql('SELECT key FROM refuges.refuge_media WHERE experience_id = %s ORDER BY uploaded_at, key',
               [experience_id])
    return [r[0] for r in rows]


def all_media_keys():
    return [r[0] for r in sql('SELECT key FROM refuges.refuge_media ORDER BY key')]


def is_uuid(value):
    try:
        return str(uuid.UUID(value)) == value
    except (ValueError, AttributeError, TypeError):
        return False


def utc(*args):
    return datetime(*args, tzinfo=dt_timezone.utc)


def deleted_keys(r2):
    """Claus que s'han demanat esborrar a R2 (per `delete_file` o per `delete_files`: el service pot triar)."""
    keys = [c.args[0] for c in r2.delete_file.call_args_list]
    for c in r2.delete_files.call_args_list:
        keys += list(c.args[0])
    return keys


def fail_r2(r2):
    """Fa que R2 no esborri res (`delete_file` retorna `False`; `delete_files` ho informa a `failed`)."""
    r2.delete_file.return_value = False
    r2.delete_files.side_effect = lambda keys: {'deleted': [], 'failed': list(keys)}
