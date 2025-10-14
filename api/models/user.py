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
    avatar: str
    
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
            'avatar': self.avatar
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'User':
        """Crea un usuari des d'un diccionari"""
        return cls(
            uid=data.get('uid', ''),
            username=data.get('username', ''),
            email=data.get('email', ''),
            avatar=data.get('avatar', '')
        )
    
    def __str__(self) -> str:
        """Representació textual de l'usuari"""
        return f"User(uid={self.uid}, username={self.username}, email={self.email})"
    
    def __repr__(self) -> str:
        """Representació detallada de l'usuari"""
        return self.__str__()