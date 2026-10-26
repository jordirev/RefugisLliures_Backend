"""
Escriptures de `renovations` (substitueixen el `RenovationController` de Firestore).

Tot dins `transaction.atomic`; les comprovacions de propietat són aquí (a més de la RLS) i es fan abans d'escriure.
Excepcions de domini en lloc de tuples: la vista les tradueix a HTTP. Els errors de la BD que són regles del domini
(`EXCLUDE` de solapaments, *trigger* de guarda de participants) es tradueixen per `constraint_name`, mai pel text.
"""
import logging
from typing import Optional

from django.db import IntegrityError, connection, transaction

from api.utils.timezone_utils import get_madrid_today
from apps.refuges import selectors as refuge_selectors

from . import selectors
from .models import Renovation, RenovationExpelled, RenovationGroupLink, RenovationParticipant

logger = logging.getLogger(__name__)

OVERLAP_CONSTRAINT = 'renovations_no_overlap'
EXPELLED_CONSTRAINT = 'renovation_participants_not_expelled_ck'
CREATOR_CONSTRAINT = 'renovation_participants_not_creator_ck'


class RefugeNotFound(Exception):
    """El refugi no existeix (inclou un ID que no és un UUID, com un ID antic de Firestore)."""


class RenovationNotFound(Exception):
    """La reforma no existeix (inclou un ID que no és un UUID)."""


class NotRenovationCreator(Exception):
    """Només el creador pot editar o esborrar la reforma (tampoc l'admin; una reforma anònima no té creador)."""


class InvalidDates(Exception):
    """`ini_date > fin_date` un cop combinades les dates noves amb les desades (M2)."""


class OverlappingRenovation(Exception):
    """Hi ha una altra reforma que se solapa al refugi; `.renovation` és la reforma en conflicte (pot ser `None`)."""

    def __init__(self, renovation=None):
        super().__init__('Hi ha una altra reforma que se solapa temporalment en aquest refugi')
        self.renovation = renovation


class CreatorCannotJoin(Exception):
    """El creador no pot ser participant de la seva reforma."""


class UserExpelled(Exception):
    """L'usuari ha estat expulsat de la reforma i no pot tornar a unir-s'hi."""


class AlreadyParticipant(Exception):
    """L'usuari ja és participant de la reforma."""


class NotAllowed(Exception):
    """Només el propi participant o el creador poden treure un participant."""


class NotAParticipant(Exception):
    """L'usuari que es vol treure no és participant."""


def _constraint_name(exc: IntegrityError) -> Optional[str]:
    return getattr(getattr(exc.__cause__, 'diag', None), 'constraint_name', None)


def _renovation_pk(renovation_id):
    pk = selectors.parse_renovation_id(renovation_id)
    if pk is None:
        raise RenovationNotFound()
    return pk


def _creator_of(pk) -> Optional[str]:
    """UID del creador (`None` si és anònima); `RenovationNotFound` si la reforma no existeix. 1 consulta."""
    rows = list(Renovation.objects.filter(pk=pk).values_list('creator_id', flat=True))
    if not rows:
        raise RenovationNotFound()
    return rows[0]


def _overlap_error(refuge_id, ini_date, fin_date, exclude_id=None) -> OverlappingRenovation:
    """Error de solapament amb la reforma en conflicte (es rellegeix: en una carrera ho ha detectat la BD)."""
    return OverlappingRenovation(selectors.find_overlapping(refuge_id, ini_date, fin_date, exclude_id))


def create_renovation(uid: str, *, refuge_id, ini_date, fin_date, description: str, group_link: str,
                      materials_needed: Optional[str] = None) -> Renovation:
    """
    Crea la reforma i el seu enllaç a la mateixa transacció (el *constraint trigger* diferit exigeix l'enllaç).
    `RefugeNotFound`, `OverlappingRenovation` (comprovació prèvia o `EXCLUDE` de la BD si hi ha una carrera).
    """
    pk = refuge_selectors.parse_refuge_id(refuge_id)
    if pk is None or not refuge_selectors.refuge_exists(pk):
        raise RefugeNotFound()
    with transaction.atomic():
        overlap = selectors.find_overlapping(pk, ini_date, fin_date)
        if overlap is not None:
            raise OverlappingRenovation(overlap)
        try:
            with transaction.atomic():
                renovation = Renovation.objects.create(
                    refuge_id=pk, creator_id=uid, ini_date=ini_date, fin_date=fin_date, description=description,
                    materials_needed=materials_needed)
                RenovationGroupLink.objects.create(renovation=renovation, group_link=group_link)
        except IntegrityError as exc:
            if _constraint_name(exc) == OVERLAP_CONSTRAINT:
                raise _overlap_error(pk, ini_date, fin_date) from exc
            raise
        return selectors.get_renovation(renovation.pk)


def update_renovation(renovation_id, uid: str, **fields) -> Renovation:
    """
    Actualitza només els camps presents (`ini_date`, `fin_date`, `description`, `materials_needed`, `group_link`).
    Les dates noves es comparen amb les desades (M2): `InvalidDates` si `ini > fin`; `OverlappingRenovation` si
    se solapa amb una altra del refugi. `RenovationNotFound`, `NotRenovationCreator`.
    """
    pk = _renovation_pk(renovation_id)
    with transaction.atomic():
        if _creator_of(pk) != uid:
            raise NotRenovationCreator()
        # Bloqueig de la fila (només el creador hi arriba; per a un altre, `FOR UPDATE` no retornaria res sota RLS).
        renovation = Renovation.objects.select_for_update().get(pk=pk)
        ini_date = fields.get('ini_date', renovation.ini_date)
        fin_date = fields.get('fin_date', renovation.fin_date)
        if ini_date > fin_date:
            raise InvalidDates()
        if (ini_date, fin_date) != (renovation.ini_date, renovation.fin_date):
            overlap = selectors.find_overlapping(renovation.refuge_id, ini_date, fin_date, exclude_id=pk)
            if overlap is not None:
                raise OverlappingRenovation(overlap)
        changed = [f for f in ('ini_date', 'fin_date', 'description', 'materials_needed') if f in fields]
        if changed:
            for name in changed:
                setattr(renovation, name, fields[name])
            try:
                with transaction.atomic():
                    renovation.save(update_fields=changed)
            except IntegrityError as exc:
                if _constraint_name(exc) == OVERLAP_CONSTRAINT:
                    raise _overlap_error(renovation.refuge_id, ini_date, fin_date, exclude_id=pk) from exc
                raise
        if 'group_link' in fields:
            RenovationGroupLink.objects.filter(pk=pk).update(group_link=fields['group_link'])
        return selectors.get_renovation(pk)


def delete_renovation(renovation_id, uid: str) -> None:
    """Esborra la reforma; la BD cascadeja participants, expulsats i enllaç. `RenovationNotFound`, `NotRenovationCreator`."""
    pk = _renovation_pk(renovation_id)
    with transaction.atomic():
        if _creator_of(pk) != uid:
            raise NotRenovationCreator()
        Renovation.objects.filter(pk=pk).delete()


def add_participant(renovation_id, uid: str) -> Renovation:
    """
    Afegeix `uid` com a participant (`INSERT ... ON CONFLICT DO NOTHING`: la PK resol la carrera, A3). Unir-se a una
    reforma ja acabada continua permès. `RenovationNotFound`, `CreatorCannotJoin`, `UserExpelled`, `AlreadyParticipant`.
    """
    pk = _renovation_pk(renovation_id)
    with transaction.atomic():
        if _creator_of(pk) == uid:
            raise CreatorCannotJoin()
        try:
            with transaction.atomic():
                with connection.cursor() as cur:
                    cur.execute('INSERT INTO activity.renovation_participants (renovation_id, user_uid) '
                                'VALUES (%s, %s) ON CONFLICT DO NOTHING', [pk, uid])
                    inserted = cur.rowcount
        except IntegrityError as exc:
            name = _constraint_name(exc)
            if name == EXPELLED_CONSTRAINT:
                raise UserExpelled() from exc
            if name == CREATOR_CONSTRAINT:
                raise CreatorCannotJoin() from exc
            raise
        if not inserted:
            raise AlreadyParticipant()
        return selectors.get_renovation(pk)


def remove_participant(renovation_id, participant_uid: str, requester_uid: str) -> Renovation:
    """
    Treu un participant: ell mateix (surt, pot tornar) o el creador (l'expulsa: `DELETE` de participants + `INSERT`
    d'expulsats a la mateixa transacció). `RenovationNotFound`, `NotAllowed` (ni ell mateix ni el creador),
    `NotAParticipant` (no hi és: no es crea cap expulsió).
    """
    pk = _renovation_pk(renovation_id)
    with transaction.atomic():
        creator = _creator_of(pk)
        is_self = requester_uid == participant_uid
        if not is_self and creator != requester_uid:
            raise NotAllowed()
        removed = RenovationParticipant.objects.filter(renovation_id=pk, user_id=participant_uid).delete()[0]
        if not removed:
            raise NotAParticipant()
        if not is_self:
            RenovationExpelled.objects.create(renovation_id=pk, user_id=participant_uid)
        return selectors.get_renovation(pk)


def delete_current_by_creator(uid: str) -> int:
    """
    Esborra les reformes vigents del creador (`fin_date >= avui de Madrid`; cascada a participants, expulsats i
    enllaç). Per a l'esborrat d'usuari (§8.4): s'executa al mateix *savepoint* que el `DELETE users.users`.
    Retorna quantes n'ha esborrat.
    """
    return Renovation.objects.filter(creator_id=uid, fin_date__gte=get_madrid_today()).delete()[0]
