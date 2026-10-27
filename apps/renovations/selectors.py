"""
Lectures de `renovations` (substitueixen el `RenovationDAO` de Firestore; docs/design/postgres-schema.md §4, §5.3 recepta 7).

Una consulta per cas d'ús i **sense cache**. Cada reforma duu dues anotacions:
- `participants_uids`: llista de UIDs ordenada per `(created_at, user_id)` (`ArraySubquery`, sense N+1);
- `group_link`: `LEFT JOIN` a `renovation_group_links`; la RLS el deixa a `None` a qui no és creador, participant ni
  admin (el serializer n'omet la clau). `expelled_uids` no es llegeix mai.
"""
import uuid
from typing import Optional

from django.contrib.postgres.expressions import ArraySubquery
from django.db import connection
from django.db.models import F, OuterRef

from api.utils.timezone_utils import get_madrid_today
from apps.refuges import selectors as refuge_selectors

from .models import Renovation, RenovationParticipant


def parse_renovation_id(value) -> Optional[uuid.UUID]:
    """Els IDs són UUID; qualsevol altra cosa (p. ex. un ID antic de Firestore) no existeix (404, no 500)."""
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value)) if value is not None else None
    except (ValueError, AttributeError, TypeError):
        return None


def annotated():
    """`Renovation.objects` amb `participants_uids` i `group_link` (1 sola consulta, qualsevol nombre de files)."""
    participants = ArraySubquery(
        RenovationParticipant.objects.filter(renovation_id=OuterRef('pk')).order_by('created_at', 'user_id')
        .values('user_id'))
    return Renovation.objects.annotate(participants_uids=participants, group_link=F('group_link_row__group_link'))


def get_renovation(renovation_id) -> Optional[Renovation]:
    """Reforma anotada (1 consulta) o `None` si no existeix o l'ID no és un UUID."""
    pk = parse_renovation_id(renovation_id)
    return annotated().filter(pk=pk).first() if pk else None


def list_active_renovations() -> list:
    """Reformes vigents (`fin_date >= avui de Madrid`, l'última inclosa) per `(ini_date, id)` (1 consulta)."""
    return list(annotated().filter(fin_date__gte=get_madrid_today()).order_by('ini_date', 'id'))


def list_refuge_renovations(refuge_id, active_only: bool = False) -> Optional[list]:
    """
    Reformes d'un refugi per `(ini_date, id)`; només les vigents si `active_only`. `None` si el refugi no existeix
    (o l'ID no és un UUID). 2 consultes: existència del refugi + dades (cal per distingir «sense reformes» de «404»).
    """
    pk = refuge_selectors.parse_refuge_id(refuge_id)
    if pk is None or not refuge_selectors.refuge_exists(pk):
        return None
    qs = annotated().filter(refuge_id=pk)
    if active_only:
        qs = qs.filter(fin_date__gte=get_madrid_today())
    return list(qs.order_by('ini_date', 'id'))


def find_overlapping(refuge_id, ini_date, fin_date, exclude_id=None) -> Optional[Renovation]:
    """
    Una reforma del refugi que se solapa amb `[ini_date, fin_date]` (límits inclusius: `a <= d AND c <= b`), també
    les acabades i les anònimes, com l'`EXCLUDE` de la BD (§2.12). `exclude_id`: la reforma que s'està editant.
    """
    qs = annotated().filter(refuge_id=refuge_id, ini_date__lte=fin_date, fin_date__gte=ini_date)
    if exclude_id is not None:
        qs = qs.exclude(pk=exclude_id)
    return qs.order_by('ini_date', 'id').first()


# Subconsulta escalar (dos paràmetres: l'uid dues vegades): reformes creades + reformes on participa.
RENOVATED_REFUGES_SQL = (
    '((SELECT count(*) FROM activity.renovations WHERE creator_uid = %s) '
    '+ (SELECT count(*) FROM activity.renovation_participants WHERE user_uid = %s))')


def count_renovated_refuges(uid: str) -> int:
    """`num_renovated_refuges` (§4): reformes creades + reformes on participa, passades incloses (1 consulta)."""
    with connection.cursor() as cur:
        cur.execute(f'SELECT {RENOVATED_REFUGES_SQL}', [uid, uid])
        return int(cur.fetchone()[0])
