"""
Model d'avís de moderació (declaració de motius, art. 17 DSA).
Col·lecció Firestore: `moderation_notices` (un document per decisió que afecta un usuari).
"""
from dataclasses import dataclass
from typing import Optional

NOTICE_CONTENT_HIDDEN = 'content_hidden'        # ocultació cautelar pendent de revisió
NOTICE_CONTENT_RESTORED = 'content_restored'    # denúncia desestimada, torna a ser visible
NOTICE_CONTENT_REMOVED = 'content_removed'      # retirada per un moderador
NOTICE_STRIKE = 'strike'                        # retirada + strike
NOTICE_ACCOUNT_BLOCKED = 'account_blocked'      # bloqueig del compte
NOTICE_UPLOAD_BLOCKED = 'upload_blocked'        # pujada bloquejada per la moderació automàtica
NOTICE_TYPES = (NOTICE_CONTENT_HIDDEN, NOTICE_CONTENT_RESTORED, NOTICE_CONTENT_REMOVED,
                NOTICE_STRIKE, NOTICE_ACCOUNT_BLOCKED, NOTICE_UPLOAD_BLOCKED)

REDRESS_TEXT = (
    "Pots demanar la revisió d'aquesta decisió (art. 20 DSA) responent al correu de contacte "
    "indicat a la Política de privacitat i termes, en un termini de 6 mesos."
)


@dataclass
class ModerationNotice:
    """Avís de moderació adreçat a un usuari"""
    id: str
    uid: str
    type: str
    statement: str
    created_at: str = ''
    refuge_id: Optional[str] = None
    media_key: Optional[str] = None
    reason: Optional[str] = None
    action: Optional[str] = None
    report_id: Optional[str] = None
    automated: bool = False
    strikes: Optional[int] = None

    def __post_init__(self):
        if not self.uid:
            raise ValueError("UID és requerit")
        if self.type not in NOTICE_TYPES:
            raise ValueError(f"Tipus d'avís no vàlid: {self.type}")

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'uid': self.uid,
            'type': self.type,
            'statement': self.statement,
            'created_at': self.created_at,
            'refuge_id': self.refuge_id,
            'media_key': self.media_key,
            'reason': self.reason,
            'action': self.action,
            'report_id': self.report_id,
            'automated': self.automated,
            'strikes': self.strikes,
            'redress': REDRESS_TEXT,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'ModerationNotice':
        return cls(
            id=data.get('id', ''),
            uid=data.get('uid', ''),
            type=data.get('type', ''),
            statement=data.get('statement', ''),
            created_at=data.get('created_at', ''),
            refuge_id=data.get('refuge_id'),
            media_key=data.get('media_key'),
            reason=data.get('reason'),
            action=data.get('action'),
            report_id=data.get('report_id'),
            automated=bool(data.get('automated', False)),
            strikes=data.get('strikes'),
        )
