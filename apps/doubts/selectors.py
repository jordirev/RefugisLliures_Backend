"""
Lectures de `doubts` (substitueixen el `DoubtDAO` de Firestore; docs/design/postgres-schema.md §5.3, recepta 3).

Sense cache: la RLS és de lectura pública (`USING (true)`) i el recompte de respostes és una agregació. Els IDs són
UUID: qualsevol altra cosa (p. ex. un ID antic de Firestore) no existeix (`None` / llista buida, mai 500).
Pressupost de consultes constant (no depèn del nombre de files): `get_doubt` 1, `get_answer` 1, `list_doubts` 2.
"""
import uuid
from typing import List, Optional

from django.db.models import Prefetch

from .models import Answer, Doubt


def parse_id(value) -> Optional[uuid.UUID]:
    """`UUID` d'un identificador o `None` si no ho és (NUL, text lliure, longitud errònia...)."""
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return None


def get_doubt(doubt_id) -> Optional[Doubt]:
    """Dubte (1 consulta); `None` si no existeix o l'ID no és un UUID."""
    pk = parse_id(doubt_id)
    return None if pk is None else Doubt.objects.filter(pk=pk).first()


def get_answer(doubt_id, answer_id) -> Optional[Answer]:
    """Resposta d'un dubte (1 consulta); `None` si no existeix o és d'un altre dubte (cap IDOR per la URL)."""
    doubt_pk, answer_pk = parse_id(doubt_id), parse_id(answer_id)
    if doubt_pk is None or answer_pk is None:
        return None
    return Answer.objects.filter(pk=answer_pk, doubt_id=doubt_pk).first()


def list_doubts(refuge_id) -> List[Doubt]:
    """
    Dubtes d'un refugi per `(created_at, id)` descendent, amb les respostes precarregades (`doubt.answers.all()`, per
    `(created_at, id)` ascendent) i `answers_count` = nombre de respostes precarregades: 2 consultes amb qualsevol
    nombre de files. El recompte no es fa a la BD (`Count('answers')` feia un `LEFT JOIN` + `GROUP BY` que llegia
    les respostes dues vegades: ~400 ms amb 3000 dubtes x 16 respostes) perquè ja les tenim totes a la memòria.
    Refugi inexistent o ID que no és UUID: llista buida (l'existència del refugi la comprova la vista).
    """
    pk = parse_id(refuge_id)
    if pk is None:
        return []
    answers = Prefetch('answers', queryset=Answer.objects.order_by('created_at', 'id'))
    doubts = list(Doubt.objects.filter(refuge_id=pk).order_by('-created_at', '-id').prefetch_related(answers))
    for doubt in doubts:
        doubt.answers_count = len(doubt.answers.all())        # de la memòria: el prefetch ja les ha carregat
    return doubts
