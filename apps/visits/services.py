"""
Escriptures de `visits` (substitueixen el `RefugeVisitController` de Firestore) i el job diari.

Excepcions de domini, cap tupla. Les funcions d'usuari s'executen dins el context de RLS de la petició (només es
poden tocar les files del propi `uid`; la comprovació és doble: filtre explícit + RLS). El job
(`process_yesterday_visits`, `purge_old_visits`) obre el seu propi `system_context()`.

Visita buida: quan se'n va l'últim participant, un *trigger* de la BD (`participants_drop_empty_visit`, migració 0002)
esborra la visita (`app` no pot esborrar `refuge_visits`). Per no trepitjar-se amb qui s'hi apunta, `create_visit` i
`remove_visitor` agafen primer el bloqueig assessor `activity.fn_visit_lock(refugi, data)` (el mateix que el trigger);
així «s'apunta algú» i «se'n va l'últim» s'ordenen i la visita esborrada entre mig es torna a crear.

Concurrència (M4): la primera inscripció és `INSERT ... ON CONFLICT (refuge_id, visit_date) DO NOTHING` + `SELECT`, de
manera que dos usuaris simultanis comparteixen una sola visita; la fila del participant és
`INSERT ... ON CONFLICT DO NOTHING` i el nombre de files afectades diu si ja hi era (sense `IntegrityError` dins la
transacció). Cap lectura-modificació-escriptura d'un total: el total es calcula amb la vista (M3).
"""
import logging
import re
import uuid
from datetime import date, timedelta

from django.db import connection, transaction

from apps.core.timezone_utils import get_madrid_today
from apps.core.rls import system_context
from apps.refuges import selectors as refuge_selectors

from . import selectors
from .models import RefugeVisit, VisitParticipant
from .selectors import VisitSummary

logger = logging.getLogger(__name__)

RETENTION_MONTHS = 12            # §8.3, decisió 13: les visites de data concreta es purguen als 12 mesos
MAX_AHEAD_MONTHS = 12            # D36: una visita no pot ser a més de 12 mesos vista (si no, files que no es purguen mai)
_DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')


class RefugeNotFound(Exception):
    """El refugi no existeix (inclou un ID que no és un UUID, com un ID antic de Firestore)."""


class VisitNotFound(Exception):
    """La visita (o el seu refugi) no existeix."""


class InvalidDateFormat(Exception):
    """La data de la URL no té el format `YYYY-MM-DD`."""


class VisitDateInPast(Exception):
    """La data de la visita és anterior a avui (Madrid)."""


class VisitDateTooFar(Exception):
    """La data de la visita és a més de `MAX_AHEAD_MONTHS` mesos d'avui (Madrid)."""


class AlreadyRegistered(Exception):
    """L'usuari ja és a la visita."""


class NotRegistered(Exception):
    """L'usuari no és a la visita."""


# ---------- Ajudes ----------

def parse_visit_date(value) -> date:
    """`date` d'un `date` o d'un text estricte `YYYY-MM-DD`; si no, `InvalidDateFormat`."""
    if isinstance(value, date):
        return value
    if isinstance(value, str) and _DATE_RE.match(value):
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    raise InvalidDateFormat()


def _existing_refuge(refuge_id) -> uuid.UUID:
    pk = refuge_selectors.parse_refuge_id(refuge_id)
    if pk is None or not refuge_selectors.refuge_exists(pk):
        raise RefugeNotFound(f'Refugi amb ID {refuge_id} no trobat')
    return pk


def _lock_visit(refuge_pk, visit_date) -> None:
    """
    Bloqueig assessor de transacció per `(refugi, data)` (`activity.fn_visit_lock`, el del trigger de visita buida).
    Cal una transacció oberta (s'allibera al `COMMIT`/`ROLLBACK`); es pren **abans** de tocar cap fila de la visita o dels
    participants, per mantenir sempre el mateix ordre i evitar deadlocks.
    """
    with connection.cursor() as cur:
        cur.execute('SELECT activity.fn_visit_lock(%s, %s)', [refuge_pk, visit_date])


def _existing_visit(refuge_id, visit_date, lock: bool = False) -> tuple:
    """
    `(refuge_pk, date, visit_id)` d'una visita existent; `VisitNotFound` (sense mirar la data) si no.
    Amb `lock=True` agafa abans el bloqueig de la visita (dins d'una transacció) i després en busca l'`id`.
    """
    pk = refuge_selectors.parse_refuge_id(refuge_id)
    try:
        d = parse_visit_date(visit_date)
    except InvalidDateFormat:
        raise VisitNotFound() from None
    if lock and pk is not None:
        _lock_visit(pk, d)
    visit_id = selectors.visit_id_of(pk, d) if pk is not None else None
    if visit_id is None:
        raise VisitNotFound()
    return pk, d, visit_id


def _months_before(d: date, months: int) -> date:
    """`d` menys `months` mesos naturals (el dia es retalla a l'últim del mes: 29/02 -> 28/02)."""
    year, month = divmod(d.year * 12 + d.month - 1 - months, 12)
    month += 1
    last_day = (date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1)).day
    return date(year, month, min(d.day, last_day))


# ---------- Lectures ----------

def get_refuge_visits(uid: str, refuge_id) -> list:
    pk = _existing_refuge(refuge_id)
    return selectors.list_refuge_visits(pk, uid)


def get_user_visits(uid: str) -> list:
    return selectors.list_user_visits(uid)


# ---------- Escriptures d'usuari ----------

def create_visit(uid: str, refuge_id, visit_date, num_visitors: int) -> VisitSummary:
    """
    Registra `uid` a la visita `(refugi, data)` i la crea si no existeix (idempotent per a la visita, no per a l'usuari).
    `visit_date` és un `date` (o un text `YYYY-MM-DD`). Ordre de les comprovacions: refugi, format de data, data
    passada (avui és vàlid), data a més de 12 mesos vista (D36), ja registrat.
    """
    pk = _existing_refuge(refuge_id)
    d = parse_visit_date(visit_date)
    today = get_madrid_today()
    if d < today:
        raise VisitDateInPast()
    if d > _months_before(today, -MAX_AHEAD_MONTHS):
        raise VisitDateTooFar()
    with transaction.atomic():
        _lock_visit(pk, d)       # si l'últim participant se'n va alhora, el trigger espera (o la visita es torna a crear)
        RefugeVisit.objects.bulk_create([RefugeVisit(refuge_id=pk, visit_date=d)], ignore_conflicts=True)
        visit_id = selectors.visit_id_of(pk, d)
        with connection.cursor() as cur:
            cur.execute(
                'INSERT INTO activity.refuge_visit_participants (visit_id, user_uid, num_visitors) '
                'VALUES (%s, %s, %s) ON CONFLICT (visit_id, user_uid) DO NOTHING',
                [visit_id, uid, num_visitors])
            if cur.rowcount == 0:
                raise AlreadyRegistered()
    return selectors.get_visit(pk, d, uid)


def update_visit(uid: str, refuge_id, visit_date, num_visitors: int) -> VisitSummary:
    """Canvia el `num_visitors` de la fila de `uid`. No comprova la data (comportament de sempre)."""
    pk, d, visit_id = _existing_visit(refuge_id, visit_date)
    if not VisitParticipant.objects.filter(visit_id=visit_id, user_id=uid).update(num_visitors=num_visitors):
        raise NotRegistered()
    return selectors.get_visit(pk, d, uid)


def remove_visitor(uid: str, refuge_id, visit_date) -> None:
    """
    Treu `uid` de la visita. Si era l'últim participant, la visita s'esborra sola: ho fa el *trigger*
    `participants_drop_empty_visit` (`app` no pot esborrar `refuge_visits`, §2.10). El bloqueig de la visita es pren
    abans del `DELETE` (mateix ordre que `create_visit`), de manera que un `create_visit` simultani no es queda amb una
    visita esborrada ni amb un participant orfe.
    """
    with transaction.atomic():
        _, _, visit_id = _existing_visit(refuge_id, visit_date, lock=True)
        if not VisitParticipant.objects.filter(visit_id=visit_id, user_id=uid).delete()[0]:
            raise NotRegistered()


# ---------- Job diari (sistema) ----------

def process_yesterday_visits() -> dict:
    """
    Passa els participants de les visites d'ahir (Madrid) a `user_visited_refuges`.

    Set-based: una `INSERT ... SELECT ... ON CONFLICT DO NOTHING` (idempotent, conserva el `created_at` original); el
    nombre de consultes no depèn del volum. Ja no esborra les visites buides: se n'encarrega un *trigger* de la BD en
    treure l'últim participant. Les visites amb participants **no** s'esborren (les purga `purge_old_visits` als 12
    mesos). `processed_visits` = visites d'ahir (existents), `updated_refuges` = visites amb participants i
    `total_visitors_added` = participants d'aquestes visites.
    """
    yesterday = get_madrid_today() - timedelta(days=1)       # sempre de Madrid, mai calculat al SQL (GOTCHAS #60)
    with system_context():
        visits = RefugeVisit.objects.filter(visit_date=yesterday)
        processed = visits.count()
        with connection.cursor() as cur:
            cur.execute(
                'SELECT count(DISTINCT p.visit_id), count(*) FROM activity.refuge_visit_participants p '
                'JOIN activity.refuge_visits v ON v.id = p.visit_id WHERE v.visit_date = %s', [yesterday])
            updated_refuges, participants = cur.fetchone()
            cur.execute(
                'INSERT INTO users.user_visited_refuges (user_uid, refuge_id) '
                'SELECT p.user_uid, v.refuge_id FROM activity.refuge_visits v '
                'JOIN activity.refuge_visit_participants p ON p.visit_id = v.id WHERE v.visit_date = %s '
                'ON CONFLICT (user_uid, refuge_id) DO NOTHING', [yesterday])
    return {'processed_visits': processed, 'updated_refuges': updated_refuges,
            'total_visitors_added': participants}


def purge_old_visits() -> int:
    """Esborra les visites amb data anterior a avui menys 12 mesos (els participants cauen en cascada). Retorna quantes."""
    limit = _months_before(get_madrid_today(), RETENTION_MONTHS)
    with system_context():
        return RefugeVisit.objects.filter(visit_date__lt=limit).delete()[0]
