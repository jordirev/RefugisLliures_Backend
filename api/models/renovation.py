"""
Model de renovation (reforma) per a l'aplicació RefugisLliures
"""
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class Renovation:
    """Model per representar una reforma"""
    id: str
    creator_uid: str
    refuge_id: str
    ini_date: datetime
    fin_date: datetime
    description: str = None
    materials_needed: Optional[str] = None
    group_link: str = None  # Enllaç a grup de coordinació (Whatsapp o Telegram)
    participants_uids: Optional[list] = None
    expelled_uids: Optional[list] = None  # UIDs dels usuaris expulsats pel creador

    def __post_init__(self):
        """Validacions després de la inicialització"""
        if not self.id:
            raise ValueError("ID és requerit")
        if not self.creator_uid:
            raise ValueError("Creator UID és requerit")
        if not self.refuge_id:
            raise ValueError("Refuge ID és requerit")
        if not self.ini_date:
            raise ValueError("Data d'inici és requerida")
        if not self.ini_date < self.fin_date:
            raise ValueError("Data d'inici ha de ser anterior a data de finalització")
        if not self.description:
            raise ValueError("Descripció és requerida")
        # Permet group_link null només si l'usuari ha estat anonimitzat
        if not self.group_link and self.creator_uid != 'unknown':
            raise ValueError("Enllaç de grup és requerit")
    
    def to_dict(self) -> dict:
        """Converteix la reforma a diccionari"""
        return {
            'id': self.id,
            'creator_uid': self.creator_uid,
            'refuge_id': self.refuge_id,
            'ini_date': self.ini_date.isoformat(),
            'fin_date': self.fin_date.isoformat(),
            'description': self.description,
            'materials_needed': self.materials_needed,
            'group_link': self.group_link,
            'participants_uids': self.participants_uids or [],
            'expelled_uids': self.expelled_uids or []
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Renovation':
        """Crea una reforma des d'un diccionari"""
        return cls(
            id=data['id'],
            creator_uid=data['creator_uid'],
            refuge_id=data['refuge_id'],
            ini_date=datetime.fromisoformat(data['ini_date']),
            fin_date=datetime.fromisoformat(data['fin_date']),
            description=data.get('description'),
            materials_needed=data.get('materials_needed'),
            group_link=data.get('group_link'),  # Permet None
            participants_uids=data.get('participants_uids', []),
            expelled_uids=data.get('expelled_uids', [])
        )
    
    def __str__(self) -> str:
        """Representació textual de la reforma"""
        return f"Renovation(id={self.id}, creator_uid={self.creator_uid}, refuge_id={self.refuge_id})"
    
    def __repr__(self) -> str:
        """Representació detallada de la reforma"""
        return self.__str__()