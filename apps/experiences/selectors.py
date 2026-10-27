"""
Lectures d'`experiences` (substitueixen el `ExperienceDAO` de Firestore; docs/design/postgres-schema.md §5.3).

Sense cache. La RLS d'`activity.experiences` és de lectura pública i la dels mitjans deixa veure els visibles, els propis
i (admin) tots; a més es filtra explícitament (defensa en profunditat). Els IDs són UUID: qualsevol altra cosa (p. ex. un
ID antic de Firestore) no existeix (`None` / llista buida, mai 500).
Pressupost de consultes constant (no depèn del nombre de files): `get_experience` 1, `list_experiences` 2.
"""
import uuid
from typing import List, Optional

from django.db.models import Prefetch

from apps.refuges.models import RefugeMedia
from apps.refuges.selectors import media_visible_to

from .models import Experience


def parse_id(value) -> Optional[uuid.UUID]:
    """`UUID` d'un identificador o `None` si no ho és (NUL, text lliure, longitud errònia...)."""
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return None


def _visible_media(viewer_uid: Optional[str], is_admin: bool):
    return RefugeMedia.objects.filter(media_visible_to(viewer_uid, is_admin)).order_by('uploaded_at', 'key')


def get_experience(experience_id) -> Optional[Experience]:
    """Experiència (1 consulta); `None` si no existeix o l'ID no és un UUID."""
    pk = parse_id(experience_id)
    return None if pk is None else Experience.objects.filter(pk=pk).first()


def get_experience_media(experience_id, viewer_uid: Optional[str] = None, is_admin: bool = False) -> List[RefugeMedia]:
    """Mitjans d'una experiència visibles per a qui mira, per `(uploaded_at, key)` (1 consulta)."""
    return list(_visible_media(viewer_uid, is_admin).filter(experience_id=experience_id))


def list_experiences(refuge_id, viewer_uid: Optional[str] = None, is_admin: bool = False) -> List[Experience]:
    """
    Experiències d'un refugi per `(modified_at, id)` descendent, cadascuna amb `media_list` = els seus mitjans visibles per
    a qui mira (`status = 'visible'`, els propis o tots si és admin) per `(uploaded_at, key)`: 2 consultes amb qualsevol
    nombre de files. Refugi inexistent o ID que no és UUID: llista buida (l'existència la comprova la vista).
    """
    pk = parse_id(refuge_id)
    if pk is None:
        return []
    media = Prefetch('media', queryset=_visible_media(viewer_uid, is_admin), to_attr='media_list')
    return list(Experience.objects.filter(refuge_id=pk).order_by('-modified_at', '-id').prefetch_related(media))
