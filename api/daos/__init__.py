"""
Data Access Objects per a la gestió de dades amb Firebase
"""
from .user_dao import UserDAO
from .refugi_lliure_dao import RefugiLliureDAO

__all__ = ['UserDAO', 'RefugiLliureDAO']