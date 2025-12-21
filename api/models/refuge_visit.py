"""
Model de visita programada a refugi 
    - A Firestore, RefugeVisits és una subcol·lecció dins d'un refugi
      lliure on cada document representa una RefugeVisit
"""
from dataclasses import dataclass

from typing import Dict

@dataclass
class RefugeVisit:
    """Model per representar una visita programada a refugi"""
    date: str # Format ISO 8601: YYYY-MM-DD (Es el id del document a Firestore)
    refuge_id: str
    visitors: Dict[str, int] # uid visitant -> nombre de visitants que l'acompanyen
    total_visitors: int = 0

    def __post_init__(self):
        """Validacions després de la inicialització"""
        if not self.refuge_id:
            raise ValueError("Refuge ID és requerit")
        if not self.date:
            raise ValueError("Data d'inici és requerida")
    
    def to_dict(self) -> dict:
        """Converteix la reforma a diccionari"""
        return {
            'date': self.date,
            'refuge_id': self.refuge_id,
            'visitors': self.visitors,
            'total_visitors': self.total_visitors
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'RefugeVisit':
        """Crea una reforma des d'un diccionari"""
        return cls(
            date=data.get('date', ''),
            refuge_id=data.get('refuge_id', ''),
            visitors=data.get('visitors', {}),
            total_visitors=data.get('total_visitors', 0)
        )
    
    def __str__(self) -> str:
        """Representació en cadena de la visita programada a refugi"""
        return f"RefugeVisit(date={self.date}, refuge_id={self.refuge_id}, visitors={self.visitors}, total_visitors={self.total_visitors})"
    
    def __repr__(self) -> str:
        """Representació oficial en cadena de la visita programada a refugi"""
        return self.__str__()