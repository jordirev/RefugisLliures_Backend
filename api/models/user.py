"""
Model d'usuari per a l'aplicació RefugisLliures
"""
from dataclasses import dataclass
from typing import Optional

@dataclass
class User:
    """Model per representar un usuari"""
    uid: str
    username: str
    email: str
    avatar: Optional[str] = None
    idioma: str = 'ca'
    refugis_favorits: Optional[list] = None
    refugis_visitats: Optional[list] = None
    reformes: Optional[list] = None
    num_fotos_pujades: int = 0
    num_experiencies_compartides: int = 0
    num_refugis_reformats: int = 0
    created_at: str = ''

    def __post_init__(self):
        """Validacions després de la inicialització"""
        if not self.uid:
            raise ValueError("UID és requerit")
        if not self.email:
            raise ValueError("Email és requerit")
        if '@' not in self.email:
            raise ValueError("Format d'email invàlid")
    
    def to_dict(self) -> dict:
        """Converteix l'usuari a diccionari"""
        return {
            'uid': self.uid,
            'username': self.username,
            'email': self.email,
            'avatar': self.avatar,
            'idioma': self.idioma,
            'refugis_favorits': self.refugis_favorits,
            'refugis_visitats': self.refugis_visitats,
            'reformes': self.reformes,
            'num_fotos_pujades': self.num_fotos_pujades,
            'num_experiencies_compartides': self.num_experiencies_compartides,
            'num_refugis_reformats': self.num_refugis_reformats,
            'created_at': self.created_at
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'User':
        """Crea un usuari des d'un diccionari"""
        return cls(
            uid=data.get('uid', ''),
            username=data.get('username', ''),
            email=data.get('email', ''),
            avatar=data.get('avatar', ''),
            idioma=data.get('idioma', 'ca'),
            refugis_favorits=data.get('refugis_favorits', []),
            refugis_visitats=data.get('refugis_visitats', []),
            reformes=data.get('reformes', []),
            num_fotos_pujades=data.get('num_fotos_pujades', 0),
            num_experiencies_compartides=data.get('num_experiencies_compartides', 0),
            num_refugis_reformats=data.get('num_refugis_reformats', 0),
            created_at=data.get('created_at', '')
        )
    
    def __str__(self) -> str:
        """Representació textual de l'usuari"""
        return f"User(uid={self.uid}, username={self.username}, email={self.email})"
    
    def __repr__(self) -> str:
        """Representació detallada de l'usuari"""
        return self.__str__()