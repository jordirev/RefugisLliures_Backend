# Importem des de la carpeta views
from .refugi_lliure_api import RefugiLliureApiView

# No importem health_check aquí per evitar conflictes
__all__ = ['RefugiLliureApiView']