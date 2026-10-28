"""
Lectures de `moderation` (substitueixen els DAOs de Firestore; docs/design/postgres-schema.md §2.20–§2.22, §5.3).

- `list_reports`: **una sola consulta** amb `LEFT JOIN refuges.refuge_media` (cap N+1 per refugi). Cal ser admin (RLS).
- `list_notices`: els avisos de l'usuari, més recents primer (RLS: només els propis o admin).
- `hash_match`: la llista de hashes és il·legible per a `app`; només es consulta `moderation.fn_hash_match`.
"""
from types import SimpleNamespace
from typing import List, NamedTuple, Optional

from django.db import connection

from .hashing import phash_hex_to_signed
from .models import ModerationNotice

# Columnes de la denúncia i del mitjà (prefix `m_`) del `LEFT JOIN`. Només s'uneix el mitjà del mateix refugi de la
# denúncia: una clau d'una altra ubicació o una `moderation-hold/...` (evidència) no en tenen previsualització.
_LIST_SQL = """
SELECT r.id, r.refuge_id, r.media_key, r.reporter_uid, r.reason, r.details, r.media_creator_uid, r.status, r.priority,
       r.created_at, r.resolved_at, r.resolved_by, r.action, r.statement, r.source, r.anonymized_at,
       m.key, m.thumb_key, m.media_type, m.width, m.height, m.blurhash, m.creator_uid, m.uploaded_at, m.taken_at,
       m.experience_id, m.status
  FROM moderation.media_reports r
  LEFT JOIN refuges.refuge_media m ON m.key = r.media_key AND m.refuge_id = r.refuge_id
 WHERE r.status = %s
 ORDER BY r.priority, r.created_at, r.id"""      # 'high' < 'normal': alta prioritat primer
_REPORT_COLUMNS = ('id', 'refuge_id', 'media_key', 'reporter_uid', 'reason', 'details', 'media_creator_uid', 'status',
                   'priority', 'created_at', 'resolved_at', 'resolved_by', 'action', 'statement', 'source',
                   'anonymized_at')
_MEDIA_COLUMNS = ('key', 'thumb_key', 'media_type', 'width', 'height', 'blurhash', 'creator_id', 'uploaded_at',
                  'taken_at', 'experience_id', 'status')


def list_reports(status: str) -> List[dict]:
    """
    Denúncies amb `status`, ordenades per `(priority, created_at, id)`. Cada element és el diccionari de columnes de la
    denúncia més `media` (un objecte amb les columnes de `refuge_media`) o `None` si el mitjà ja no existeix.
    """
    with connection.cursor() as cur:
        cur.execute(_LIST_SQL, [status])
        rows = cur.fetchall()
    split = len(_REPORT_COLUMNS)
    result = []
    for row in rows:
        report = dict(zip(_REPORT_COLUMNS, row[:split]))
        media = row[split:]
        report['media'] = SimpleNamespace(**dict(zip(_MEDIA_COLUMNS, media))) if media[0] is not None else None
        result.append(report)
    return result


def list_notices(uid: str) -> List[ModerationNotice]:
    """Avisos de moderació de l'usuari, més recents primer (desempat per `id` descendent)."""
    return list(ModerationNotice.objects.filter(user_id=uid).order_by('-created_at', '-id'))


class HashMatch(NamedTuple):
    entry_id: str
    category: str
    match_type: str        # 'sha256' | 'phash'


def hash_match(sha256: Optional[str] = None, phash_hex: Optional[str] = None) -> Optional[HashMatch]:
    """
    Coincidència amb la llista de hashes prohibits (sha256 exacte o pHash a distància de Hamming <= 6) via
    `moderation.fn_hash_match`. Un `phash_hex` invàlid no coincideix (no llança). Sense cap hash no fa cap consulta.
    """
    phash = None
    if phash_hex:
        try:
            phash = phash_hex_to_signed(phash_hex)
        except (ValueError, TypeError):
            phash = None
    if not sha256 and phash is None:
        return None
    with connection.cursor() as cur:
        cur.execute('SELECT entry_id, category, match_type FROM moderation.fn_hash_match(%s::text, %s::bigint)',
                    [sha256 or None, None if phash is None else str(phash)])    # text: -2**63 com a `int` no cap al literal
        row = cur.fetchone()
    return HashMatch(str(row[0]), row[1], row[2]) if row else None
