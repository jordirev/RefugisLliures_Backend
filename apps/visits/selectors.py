"""
Lectures de `visits` (substitueixen el `RefugeVisitDAO` de Firestore): una consulta per cas d'ús, sense cache.

El total de cada visita surt de la vista `refuge_visit_totals` (`VisitTotal`), mai d'un `Sum` sobre els participants:
la RLS només deixa veure la fila de l'usuari i el total quedaria mutilat (§2.11). `is_visitor`/`num_visitors` són
sempre els de l'usuari que pregunta; els participants d'altres mai surten d'aquí.
"""
import uuid
from dataclasses import dataclass
from datetime import date
from typing import Optional

from django.db.models import Exists, F, OuterRef, Subquery
from django.db.models.functions import Coalesce

from apps.core.timezone_utils import get_madrid_today

from .models import RefugeVisit, VisitParticipant, VisitTotal


@dataclass(frozen=True, slots=True)
class VisitSummary:
    """Visita tal com la veu `uid`: total de tothom i la seva pròpia participació (0 si no hi és)."""

    date: date
    refuge_id: uuid.UUID
    total_visitors: int
    is_visitor: bool
    num_visitors: int


_FIELDS = ('visit_date', 'refuge_id', 'total', 'is_visitor', 'my_num')


def _summaries(rows) -> list:
    return [VisitSummary(d, rid, total, bool(is_visitor), my_num) for d, rid, total, is_visitor, my_num in rows]


def _of_user(uid: str):
    """Participació de `uid` a la visita de la consulta exterior (la RLS ja només deixa veure la seva fila)."""
    return VisitParticipant.objects.filter(visit_id=OuterRef('pk'), user_id=uid)


def _total_of(visit_ref: str):
    """
    Total de la visita referenciada per `OuterRef(visit_ref)`, com a subconsulta correlacionada sobre la vista.

    Un `LEFT JOIN` amb la vista (`GROUP BY visit_id`) fa que Postgres agregui **tota** la taula de participants i
    n'enllaci el resultat (un `GroupAggregate` de milions de files per llegir-ne dues desenes). La subconsulta
    correlacionada hi empeny el `visit_id` i usa l'índex de la PK `(visit_id, user_uid)`: cost proporcional a les files llegides.
    """
    return Coalesce(Subquery(VisitTotal.objects.filter(visit_id=OuterRef(visit_ref)).values('total_visitors')[:1]), 0)


def _annotated_visits(uid: str):
    mine = _of_user(uid)
    return RefugeVisit.objects.annotate(
        total=_total_of('pk'),
        is_visitor=Exists(mine),
        my_num=Coalesce(Subquery(mine.values('num_visitors')[:1]), 0))


def list_refuge_visits(refuge_id: uuid.UUID, uid: str) -> list:
    """Visites d'avui (Madrid) en endavant d'un refugi, per data ascendent; les buides hi surten amb total 0."""
    rows = (_annotated_visits(uid)
            .filter(refuge_id=refuge_id, visit_date__gte=get_madrid_today())
            .order_by('visit_date')
            .values_list(*_FIELDS))
    return _summaries(rows)


def list_user_visits(uid: str) -> list:
    """Totes les visites on participa `uid` (passades i futures), per `(data DESC, refugi)`: usa `(user_uid) INCLUDE`."""
    rows = (VisitParticipant.objects.filter(user_id=uid)
            .annotate(visit_date=F('visit__visit_date'), refuge_id=F('visit__refuge_id'),
                      total=_total_of('visit_id'))
            .order_by('-visit_date', 'refuge_id')
            .values_list('visit_date', 'refuge_id', 'total', 'num_visitors'))
    return [VisitSummary(d, rid, total, True, num) for d, rid, total, num in rows]


def get_visit(refuge_id: uuid.UUID, visit_date: date, uid: str) -> Optional[VisitSummary]:
    """Una visita concreta tal com la veu `uid`; `None` si no existeix."""
    rows = (_annotated_visits(uid).filter(refuge_id=refuge_id, visit_date=visit_date).values_list(*_FIELDS))
    summaries = _summaries(rows)
    return summaries[0] if summaries else None


def visit_id_of(refuge_id: uuid.UUID, visit_date: date) -> Optional[uuid.UUID]:
    """`id` de la visita `(refugi, data)`; `None` si no existeix."""
    return (RefugeVisit.objects.filter(refuge_id=refuge_id, visit_date=visit_date)
            .values_list('id', flat=True).first())
