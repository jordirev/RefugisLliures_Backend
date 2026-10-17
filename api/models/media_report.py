"""
Model de denúncia d'un mitjà (notificació i retirada, art. 16 DSA).
Col·lecció Firestore: `media_reports`. L'ID és determinista per (refugi, mitjà, denunciant),
de manera que una segona denúncia del mateix usuari és un conflicte (409).
"""
import hashlib
from dataclasses import dataclass
from typing import Optional

# Motius (contracte d'API). Ordre = ordre de presentació a l'app.
REPORT_REASONS = (
    'child_sexual_abuse',      # Abús o explotació sexual de menors
    'child_endangerment',      # Menors en situació de risc / imatges inapropiades de menors
    'sexual_nonconsensual',    # Nuesa o contingut sexual (inclosos íntims no consentits i deepfakes)
    'violence_gore',           # Violència explícita o contingut sagnant
    'terrorism_extremism',     # Terrorisme o extremisme violent
    'hate_speech',             # Odi o discriminació
    'harassment_bullying',     # Assetjament o intimidació
    'animal_cruelty',          # Maltractament animal
    'self_harm',               # Suïcidi o autolesions
    'illegal_goods',           # Drogues, armes o activitats il·legals
    'my_image',                # Hi surto jo sense el meu consentiment
    'privacy_personal_data',   # Dades personals d'altres
    'intellectual_property',   # Drets d'autor o marca
    'fraud_scam_spam',         # Frau, estafa, spam o publicitat
    'misleading_irrelevant',   # Falsa o no correspon a aquest refugi
    'other',                   # Altres (cal descripció)
)

# Motius que oculten el mitjà immediatament i tenen prioritat alta
AUTO_HIDE_REASONS = frozenset({
    'child_sexual_abuse',
    'child_endangerment',
    'sexual_nonconsensual',
    'terrorism_extremism',
    'my_image',
})

# Nombre de denunciants diferents a partir del qual s'oculta per a la resta de motius
AUTO_HIDE_DISTINCT_REPORTERS = 3

REPORT_STATUS_PENDING = 'pending'
REPORT_STATUS_RESOLVED = 'resolved'
REPORT_STATUSES = (REPORT_STATUS_PENDING, REPORT_STATUS_RESOLVED)

REPORT_PRIORITY_HIGH = 'high'
REPORT_PRIORITY_NORMAL = 'normal'

REPORT_ACTION_DISMISS = 'dismiss'
REPORT_ACTION_REMOVE = 'remove'
REPORT_ACTION_REMOVE_AND_STRIKE = 'remove_and_strike'
REPORT_ACTIONS = (REPORT_ACTION_DISMISS, REPORT_ACTION_REMOVE, REPORT_ACTION_REMOVE_AND_STRIKE)

REPORT_DETAILS_MAX_LENGTH = 1000
SYSTEM_REPORTER_UID = 'system'


def build_report_id(refuge_id: str, media_key: str, reporter_uid: str) -> str:
    """ID determinista: una denúncia per (refugi, mitjà, denunciant)"""
    raw = f"{refuge_id}|{media_key}|{reporter_uid}".encode('utf-8')
    return hashlib.sha256(raw).hexdigest()[:40]


@dataclass
class MediaReport:
    """Denúncia d'un mitjà"""
    id: str
    refuge_id: str
    media_key: str
    reporter_uid: str
    reason: str
    details: Optional[str] = None
    media_creator_uid: Optional[str] = None
    status: str = REPORT_STATUS_PENDING
    priority: str = REPORT_PRIORITY_NORMAL
    created_at: str = ''
    resolved_at: Optional[str] = None
    resolved_by: Optional[str] = None
    action: Optional[str] = None
    statement: Optional[str] = None
    source: str = 'user'  # 'user' | 'automatic'

    def __post_init__(self):
        if not self.id:
            raise ValueError("ID és requerit")
        if not self.refuge_id or not self.media_key:
            raise ValueError("refuge_id i media_key són requerits")
        if self.reason not in REPORT_REASONS:
            raise ValueError(f"Motiu no vàlid: {self.reason}")
        if self.reason == 'other' and not (self.details or '').strip():
            raise ValueError("details és obligatori quan reason és 'other'")
        if self.details and len(self.details) > REPORT_DETAILS_MAX_LENGTH:
            raise ValueError(f"details no pot superar {REPORT_DETAILS_MAX_LENGTH} caràcters")
        if self.status not in REPORT_STATUSES:
            raise ValueError(f"Status no vàlid: {self.status}")
        if self.action is not None and self.action not in REPORT_ACTIONS:
            raise ValueError(f"Acció no vàlida: {self.action}")

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'refuge_id': self.refuge_id,
            'media_key': self.media_key,
            'reporter_uid': self.reporter_uid,
            'reason': self.reason,
            'details': self.details,
            'media_creator_uid': self.media_creator_uid,
            'status': self.status,
            'priority': self.priority,
            'created_at': self.created_at,
            'resolved_at': self.resolved_at,
            'resolved_by': self.resolved_by,
            'action': self.action,
            'statement': self.statement,
            'source': self.source,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'MediaReport':
        return cls(
            id=data.get('id', ''),
            refuge_id=data.get('refuge_id', ''),
            media_key=data.get('media_key', ''),
            reporter_uid=data.get('reporter_uid', ''),
            reason=data.get('reason', ''),
            details=data.get('details'),
            media_creator_uid=data.get('media_creator_uid'),
            status=data.get('status', REPORT_STATUS_PENDING),
            priority=data.get('priority', REPORT_PRIORITY_NORMAL),
            created_at=data.get('created_at', ''),
            resolved_at=data.get('resolved_at'),
            resolved_by=data.get('resolved_by'),
            action=data.get('action'),
            statement=data.get('statement'),
            source=data.get('source', 'user'),
        )
