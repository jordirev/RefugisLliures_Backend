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
    language: str = 'ca'
    favourite_refuges: Optional[list] = None
    visited_refuges: Optional[list] = None
    renovations: Optional[list] = None
    num_uploaded_photos: int = 0
    num_shared_experiences: int = 0
    num_renovated_refuges: int = 0
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
            'language': self.language,
            'favourite_refuges': self.favourite_refuges,
            'visited_refuges': self.visited_refuges,
            'renovations': self.renovations,
            'num_uploaded_photos': self.num_uploaded_photos,
            'num_shared_experiences': self.num_shared_experiences,
            'num_renovated_refuges': self.num_renovated_refuges,
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
            language=data.get('language', 'ca'),
            favourite_refuges=data.get('favourite_refuges', []),
            visited_refuges=data.get('visited_refuges', []),
            renovations=data.get('renovations', []),
            num_uploaded_photos=data.get('num_uploaded_photos', 0),
            num_shared_experiences=data.get('num_shared_experiences', 0),
            num_renovated_refuges=data.get('num_renovated_refuges', 0),
            created_at=data.get('created_at', '')
        )
    
    def __str__(self) -> str:
        """Representació textual de l'usuari"""
        return f"User(uid={self.uid}, username={self.username}, email={self.email})"
    
    def __repr__(self) -> str:
        """Representació detallada de l'usuari"""
        return self.__str__()