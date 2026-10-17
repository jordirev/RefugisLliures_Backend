"""
Model d'intent de pujada directa (presigned PUT a quarantine/{upload_id}).
Col·lecció Firestore: `upload_intents` (TTL sobre `expire_at`).
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

UPLOAD_TARGET_REFUGE = 'refuge'
UPLOAD_TARGET_EXPERIENCE = 'experience'
UPLOAD_TARGET_AVATAR = 'avatar'
UPLOAD_TARGETS = (UPLOAD_TARGET_REFUGE, UPLOAD_TARGET_EXPERIENCE, UPLOAD_TARGET_AVATAR)

INTENT_STATUS_PENDING = 'pending'
INTENT_STATUS_CONFIRMED = 'confirmed'
INTENT_STATUS_FAILED = 'failed'
INTENT_STATUSES = (INTENT_STATUS_PENDING, INTENT_STATUS_CONFIRMED, INTENT_STATUS_FAILED)


@dataclass
class UploadIntent:
    """Intent de pujada: una URL PUT prefirmada per a un fitxer"""
    id: str
    uid: str
    target: str
    content_type: str
    size: int
    quarantine_key: str
    refuge_id: Optional[str] = None
    experience_id: Optional[str] = None
    status: str = INTENT_STATUS_PENDING
    rights_confirmed_at: Optional[str] = None
    created_at: str = ''
    expire_at: Optional[datetime] = None
    result_key: Optional[str] = None
    failure_reason: Optional[str] = None

    def __post_init__(self):
        if not self.id:
            raise ValueError("ID és requerit")
        if not self.uid:
            raise ValueError("UID és requerit")
        if self.target not in UPLOAD_TARGETS:
            raise ValueError(f"Target no vàlid: {self.target}")
        if self.status not in INTENT_STATUSES:
            raise ValueError(f"Status no vàlid: {self.status}")
        if self.target in (UPLOAD_TARGET_REFUGE, UPLOAD_TARGET_EXPERIENCE) and not self.refuge_id:
            raise ValueError("refuge_id és requerit per a aquest target")
        if self.target == UPLOAD_TARGET_EXPERIENCE and not self.experience_id:
            raise ValueError("experience_id és requerit per al target experience")

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'uid': self.uid,
            'target': self.target,
            'content_type': self.content_type,
            'size': self.size,
            'quarantine_key': self.quarantine_key,
            'refuge_id': self.refuge_id,
            'experience_id': self.experience_id,
            'status': self.status,
            'rights_confirmed_at': self.rights_confirmed_at,
            'created_at': self.created_at,
            'expire_at': self.expire_at,
            'result_key': self.result_key,
            'failure_reason': self.failure_reason,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'UploadIntent':
        return cls(
            id=data.get('id', ''),
            uid=data.get('uid', ''),
            target=data.get('target', ''),
            content_type=data.get('content_type', ''),
            size=int(data.get('size') or 0),
            quarantine_key=data.get('quarantine_key', ''),
            refuge_id=data.get('refuge_id'),
            experience_id=data.get('experience_id'),
            status=data.get('status', INTENT_STATUS_PENDING),
            rights_confirmed_at=data.get('rights_confirmed_at'),
            created_at=data.get('created_at', ''),
            expire_at=data.get('expire_at'),
            result_key=data.get('result_key'),
            failure_reason=data.get('failure_reason'),
        )
