"""
Model de proposta de refugi per a l'aplicació RefugisLliures
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import date


@dataclass
class RefugeProposal:
    """Model per representar una proposta de refugi"""
    id: str
    refuge_id: Optional[str]  # None per a CREATE, ID del refugi per a UPDATE/DELETE
    action: str  # 'create', 'update', 'delete'
    payload: Optional[Dict[str, Any]]  # None per a DELETE
    comment: Optional[str]  # Comentari opcional de l'usuari
    status: str  # 'pending', 'approved', 'rejected'
    creator_uid: str
    created_at: str  # Format ISO 8601: YYYY-MM-DD
    reviewer_uid: Optional[str]  # UID de l'admin que revisa
    reviewed_at: Optional[str]  # Data de revisió, format ISO 8601: YYYY-MM-DD
    rejection_reason: Optional[str] = None  # Raó del rebuig (només per rejected)
    refuge_snapshot: Optional[Dict[str, Any]] = None  # Snapshot del refugi (només per UPDATE/DELETE)
    
    def to_dict(self) -> Dict[str, Any]:
        """Converteix el model a diccionari"""
        return {
            'id': self.id,
            'refuge_id': self.refuge_id,
            'refuge_snapshot': self.refuge_snapshot,
            'action': self.action,
            'payload': self.payload,
            'comment': self.comment,
            'status': self.status,
            'creator_uid': self.creator_uid,
            'created_at': self.created_at,
            'reviewer_uid': self.reviewer_uid,
            'reviewed_at': self.reviewed_at,
            'rejection_reason': self.rejection_reason
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RefugeProposal':
        """Crea una instància des d'un diccionari"""
        return cls(
            id=data.get('id'),
            refuge_id=data.get('refuge_id'),
            refuge_snapshot=data.get('refuge_snapshot'),
            action=data.get('action'),
            payload=data.get('payload'),
            comment=data.get('comment'),
            status=data.get('status', 'pending'),
            creator_uid=data.get('creator_uid'),
            created_at=data.get('created_at'),
            reviewer_uid=data.get('reviewer_uid'),
            reviewed_at=data.get('reviewed_at'),
            rejection_reason=data.get('rejection_reason')
        )
