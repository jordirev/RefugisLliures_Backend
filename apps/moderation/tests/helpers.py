"""
Ajudes de test del domini moderació (chunk 9): denúncies, avisos i llista de hashes (schema `moderation`).

Reutilitza les dels chunks anteriors (`make_user` amb l'edat confirmada, `make_refuge`, `make_media`, `as_owner`, `sql`,
`QueryCounter`, `api_*`, l'R2 fals `R2Store`...). Els models de producció (`apps.moderation`, `apps.audit`) encara no
existeixen quan s'escriuen els tests: s'importen de manera mandrosa perquè cada test falli pel seu propi motiu.

- Les files de `moderation.media_reports` / `moderation_notices` dels fixtures es creen amb SQL pla (rol `app` dins
  `system_context()`: passa la RLS i **no** salta els `CHECK`/`UNIQUE`).
- La llista de hashes (`moderation_hash_blocklist`) és il·legible per a `app`: els fixtures hi escriuen amb el rol de
  proves `test_fixtures` (`as_owner()`, `BYPASSRLS`) dins la transacció del test.
- Constants de domini (motius, accions, tipus): vegeu les de `apps.moderation.models` (contracte).
"""
import importlib
import json
import uuid
from datetime import datetime, timedelta, timezone as dt_timezone

from apps.accounts.tests.helpers import (  # noqa: F401  (re-exportats)
    QueryCounter, T0, VERIFY, admin_claims, api_delete, api_get, api_patch, api_post, as_owner, at, count_all,
    make_avatar, sql, user_claims)
from apps.experiences.tests.helpers import make_exp_media, make_experience  # noqa: F401
from apps.refuges.tests.helpers import MEDIA_ITEM_KEYS, make_media, make_refuge  # noqa: F401
from apps.uploads.tests.helpers import (  # noqa: F401
    CONFIRM, INTENTS, R2Store, file_spec, intent_body, make_intent, make_jpeg_with_gps, make_png)
from apps.uploads.tests.helpers import make_user as _make_user

REPORTS = '/api/media/reports/'
ADMIN_REPORTS = '/api/admin/media-reports/'

REASONS = ('child_sexual_abuse', 'child_endangerment', 'sexual_nonconsensual', 'violence_gore', 'terrorism_extremism',
           'hate_speech', 'harassment_bullying', 'animal_cruelty', 'self_harm', 'illegal_goods', 'my_image',
           'privacy_personal_data', 'intellectual_property', 'fraud_scam_spam', 'misleading_irrelevant', 'other')
AUTO_HIDE = ('child_sexual_abuse', 'child_endangerment', 'sexual_nonconsensual', 'terrorism_extremism', 'my_image')
NORMAL_REASONS = tuple(r for r in REASONS if r not in AUTO_HIDE)
ACTIONS = ('dismiss', 'remove', 'remove_and_strike')
NOTICE_TYPES = ('content_hidden', 'content_restored', 'content_removed', 'strike', 'account_blocked', 'upload_blocked')

CREATE_RESPONSE_KEYS = {'id', 'refuge_id', 'media_key', 'reason', 'details', 'status', 'priority', 'created_at',
                        'media_hidden'}
REPORT_KEYS = {'id', 'refuge_id', 'media_key', 'reporter_uid', 'reason', 'details', 'media_creator_uid', 'status',
               'priority', 'created_at', 'resolved_at', 'resolved_by', 'action', 'statement', 'source'}
RESOLVE_KEYS = {'report', 'resolved_report_ids', 'media_status', 'strikes', 'user_blocked'}
NOTICE_KEYS = {'id', 'uid', 'type', 'statement', 'created_at', 'refuge_id', 'media_key', 'reason', 'action',
               'report_id', 'automated', 'strikes', 'redress'}
REDRESS = ("Pots demanar la revisió d'aquesta decisió (art. 20 DSA) responent al correu de contacte "
           "indicat a la Política de privacitat i termes, en un termini de 6 mesos.")
ZERO_UUID = '00000000-0000-0000-0000-000000000000'
HIDDEN = 'hidden_pending_review'


def make_user(uid='u1', username='', **fields):
    """Usuari amb l'edat confirmada (denunciar exigeix `IsAgeConfirmed`); es pot sobreescriure."""
    return _make_user(uid, username, **fields)


def moderation_models():
    return importlib.import_module('apps.moderation.models')


def audit_models():
    return importlib.import_module('apps.audit.models')


def is_uuid(value):
    try:
        return str(uuid.UUID(value)) == value
    except (ValueError, AttributeError, TypeError):
        return False


def resolve_url(report_id):
    return f'{ADMIN_REPORTS}{report_id}/'


def notices_url(uid):
    return f'/api/users/{uid}/moderation-notices/'


def now_minus(**kwargs):
    return datetime.now(dt_timezone.utc) - timedelta(**kwargs)


def media_key_for(refuge, name='m1'):
    return f'refugis-lliures/{refuge.pk}/{name}.webp'


# ---------- Dades de prova ----------

REPORT_COLS = ('id', 'refuge_id', 'media_key', 'reporter_uid', 'reason', 'details', 'media_creator_uid', 'status',
               'priority', 'created_at', 'resolved_at', 'resolved_by', 'action', 'statement', 'source', 'legal_hold',
               'anonymized_at')


def make_report(refuge, media_key, reporter='u2', reason='hate_speech', *, creator=None, status='pending',
                priority=None, source='user', minutes=0, legal_hold=None, details=None, report_id=None,
                resolved_by='adm', resolved_at=None, action='remove', statement='motiu', created_at=None,
                anonymized_at=None):
    """Insereix una denúncia i en retorna l'`id` (`str`). `created_at` = `T0 + minutes` si no s'indica.

    `source='automatic'` ⇒ `reporter=None`. Una denúncia `resolved` rep `resolved_at` (per defecte `created_at + 1 h`),
    `action` i `statement` (el `CHECK` de resolució ho exigeix). `legal_hold` per defecte: `reason == CSAM`.
    """
    if source == 'automatic':
        reporter = None
    if legal_hold is None:
        legal_hold = reason == 'child_sexual_abuse'
    if priority is None:
        priority = 'high' if reason in AUTO_HIDE else 'normal'
    created = created_at or at(minutes)
    cols = ['refuge_id', 'media_key', 'reporter_uid', 'reason', 'details', 'media_creator_uid', 'status', 'priority',
            'created_at', 'source', 'legal_hold', 'anonymized_at']
    params = [getattr(refuge, 'pk', refuge), media_key, reporter,
              reason, details if details is not None else ('detall' if reason == 'other' else None), creator, status,
              priority, created, source, legal_hold, anonymized_at]
    if status == 'resolved':
        cols += ['resolved_at', 'resolved_by', 'action', 'statement']
        params += [resolved_at or created + timedelta(hours=1), resolved_by, action, statement]
    if report_id:
        cols.insert(0, 'id')
        params.insert(0, report_id)
    rows = sql(f'INSERT INTO moderation.media_reports ({", ".join(cols)}) '
               f'VALUES ({", ".join(["%s"] * len(cols))}) RETURNING id', params)
    return str(rows[0][0])


def _report_dict(row):
    d = dict(zip(REPORT_COLS, row))
    d['id'] = str(d['id'])
    d['refuge_id'] = str(d['refuge_id']) if d['refuge_id'] else None
    return d


def report_row(report_id):
    """Fila de `media_reports` com a diccionari (`id`/`refuge_id` com a `str`) o `None`."""
    rows = sql(f'SELECT {", ".join(REPORT_COLS)} FROM moderation.media_reports WHERE id = %s', [report_id])
    return _report_dict(rows[0]) if rows else None


def report_rows(**where):
    """Totes les denúncies (ordenades per `created_at, id`); `where` filtra per igualtat de columna."""
    clause = ' AND '.join(f'{k} = %s' for k in where) or 'true'
    rows = sql(f'SELECT {", ".join(REPORT_COLS)} FROM moderation.media_reports WHERE {clause} '
               'ORDER BY created_at, id', list(where.values()))
    return [_report_dict(r) for r in rows]


def count_reports():
    return sql('SELECT count(*) FROM moderation.media_reports')[0][0]


NOTICE_COLS = ('id', 'user_uid', 'type', 'statement', 'created_at', 'refuge_id', 'media_key', 'reason', 'action',
               'report_id', 'automated', 'strikes')


def make_notice(uid, type='content_removed', *, statement='Declaració de motius', refuge=None, media_key=None,
                reason=None, action=None, report_id=None, automated=False, strikes=None, minutes=0, created_at=None,
                notice_id=None):
    """Insereix un avís i en retorna l'`id` (`str`). `created_at` = `T0 + minutes` si no s'indica."""
    cols = ['user_uid', 'type', 'statement', 'created_at', 'refuge_id', 'media_key', 'reason', 'action', 'report_id',
            'automated', 'strikes']
    params = [uid, type, statement, created_at or at(minutes), getattr(refuge, 'pk', refuge), media_key, reason,
              action, report_id, automated, strikes]
    if notice_id:
        cols.insert(0, 'id')
        params.insert(0, notice_id)
    rows = sql(f'INSERT INTO moderation.moderation_notices ({", ".join(cols)}) '
               f'VALUES ({", ".join(["%s"] * len(cols))}) RETURNING id', params)
    return str(rows[0][0])


def notice_rows(uid=None):
    where, params = ('WHERE user_uid = %s', [uid]) if uid else ('', [])
    rows = sql(f'SELECT {", ".join(NOTICE_COLS)} FROM moderation.moderation_notices {where} '
               'ORDER BY created_at, id', params)
    out = []
    for r in rows:
        d = dict(zip(NOTICE_COLS, r))
        for k in ('id', 'refuge_id', 'report_id'):
            d[k] = str(d[k]) if d[k] else None
        out.append(d)
    return out


def make_hash(sha256=None, phash=None, category='csam', source='proves'):
    """Entrada de la llista de hashes (rol `test_fixtures`: `app` no hi té cap privilegi). `phash`: `int` amb signe."""
    with as_owner():
        rows = sql('INSERT INTO moderation.moderation_hash_blocklist (sha256, phash, category, source) '
                   'VALUES (%s, %s, %s, %s) RETURNING id', [sha256, phash, category, source])
    return str(rows[0][0])


def hash_count():
    with as_owner():
        return sql('SELECT count(*) FROM moderation.moderation_hash_blocklist')[0][0]


def media_row(key):
    rows = sql('SELECT status, creator_uid, thumb_key FROM refuges.refuge_media WHERE key = %s', [key])
    return dict(zip(('status', 'creator_uid', 'thumb_key'), rows[0])) if rows else None


def media_status(key):
    row = media_row(key)
    return row['status'] if row else None


def user_state(uid):
    rows = sql('SELECT moderation_strikes, is_blocked, blocked_reason, blocked_at FROM users.users WHERE uid = %s',
               [uid])
    return dict(zip(('strikes', 'is_blocked', 'blocked_reason', 'blocked_at'), rows[0])) if rows else None


AUDIT_COLS = ('actor_uid', 'subject_uid', 'action', 'target_type', 'target_id', 'metadata', 'legal_hold', 'created_at',
              'expire_at')


def audit_rows(action=None):
    """Entrades d'`audit.audit_logs` com a diccionaris (ordenades per `created_at, id`)."""
    where, params = ('WHERE action = %s', [action]) if action else ('', [])
    rows = sql(f'SELECT {", ".join(AUDIT_COLS)} FROM audit.audit_logs {where} ORDER BY created_at, id', params)
    out = []
    for r in rows:
        d = dict(zip(AUDIT_COLS, r))
        if isinstance(d['metadata'], str):                # el `jsonb` d'un cursor cru surt com a `str` (GOTCHAS #80)
            d['metadata'] = json.loads(d['metadata'])
        out.append(d)
    return out
