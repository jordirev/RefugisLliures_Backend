"""
Model de doubt (dubte) i answer (resposta) per a l'aplicació RefugisLliures
"""
from dataclasses import dataclass
from typing import Optional, List


@dataclass
class Doubt:
    """Model per representar un dubte sobre un refugi"""
    id: str
    refuge_id: str
    creator_uid: str
    message: str
    created_at: str  # ISO 8601 format amb timezone Madrid
    answers_count: int = 0
    answers: Optional[List['Answer']] = None  # Llista d'Answer, no es guarda a Firestore
    
    def __post_init__(self):
        """Validacions després de la inicialització"""
        if not self.id:
            raise ValueError("ID és requerit")
        if not self.refuge_id:
            raise ValueError("Refuge ID és requerit")
        if not self.creator_uid:
            raise ValueError("Creator UID és requerit")
        if not self.message:
            raise ValueError("Message és requerit")
        if not self.created_at:
            raise ValueError("Created at és requerit")
        if self.answers is None:
            self.answers = []
    
    def to_dict(self) -> dict:
        """Converteix el dubte a diccionari per guardar a Firestore"""
        data = {
            'id': self.id,
            'refuge_id': self.refuge_id,
            'creator_uid': self.creator_uid,
            'message': self.message,
            'created_at': self.created_at,
            'answers_count': self.answers_count
        }
        
        # Si té answers, les incloem al diccionari (per a la resposta, no per Firestore)
        if self.answers:
            data['answers'] = [answer.to_dict() for answer in self.answers]
        
        return data
    
    @classmethod
    def from_dict(cls, data: dict, answers: Optional[List['Answer']] = None) -> 'Doubt':
        """Crea un dubte des d'un diccionari"""
        return cls(
            id=data['id'],
            refuge_id=data['refuge_id'],
            creator_uid=data['creator_uid'],
            message=data['message'],
            created_at=data['created_at'],
            answers_count=data.get('answers_count', 0),
            answers=answers or []
        )


@dataclass
class Answer:
    """Model per representar una resposta a un dubte"""
    id: str
    creator_uid: str
    message: str
    created_at: str  # ISO 8601 format amb timezone Madrid
    parent_answer_id: Optional[str] = None  # ID de l'answer pare si és una resposta a una resposta
    
    def __post_init__(self):
        """Validacions després de la inicialització"""
        if not self.id:
            raise ValueError("ID és requerit")
        if not self.creator_uid:
            raise ValueError("Creator UID és requerit")
        if not self.message:
            raise ValueError("Message és requerit")
        if not self.created_at:
            raise ValueError("Created at és requerit")
    
    def to_dict(self) -> dict:
        """Converteix la resposta a diccionari"""
        return {
            'id': self.id,
            'creator_uid': self.creator_uid,
            'message': self.message,
            'created_at': self.created_at,
            'parent_answer_id': self.parent_answer_id
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Answer':
        """Crea una resposta des d'un diccionari"""
        return cls(
            id=data['id'],
            creator_uid=data['creator_uid'],
            message=data['message'],
            created_at=data['created_at'],
            parent_answer_id=data.get('parent_answer_id')
        )
