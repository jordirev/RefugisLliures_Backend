"""
Escriptures de `proposals` (substitueixen el `RefugeProposalController` i les estratègies de Firestore; docs/design/
postgres-schema.md §2.18, §2.5-2.9, §8.5).

Excepcions de domini (cap tupla). Qui fa què el reforça la RLS (només l'admin o el sistema revisen) i les vistes
(`IsFirebaseAdmin`). L'aprovació és **una sola transacció** (`transaction.atomic`): la proposta es bloqueja
`FOR UPDATE` amb `WHERE status = 'pending'` (C2: la doble aprovació és impossible a la BD i ja no depèn d'una cache) i
s'hi aplica l'acció sobre `refuges`, `refuge_amenities` i `refuge_links`; qualsevol error desfà tot i la proposta
continua pendent.

- `modified_at` del refugi = data (Madrid) de la **creació** de la proposta; `info_comp` d'un `update` substitueix els 12
  indicadors (els absents passen a `false`); `links` se substitueixen sencers; `coord` -> `Point(long, lat)`;
  `description: null` -> `''`; `region`/`departement` `''` -> `NULL`.
- `condition` present (create o update) **reinicia** la mitjana del refugi (§2.9): `c = valor`, `n = 1`,
  `condition_reset_at = now()`; absent o `null`, no la toca.
- `delete`: la proposta es marca aprovada, es rebutgen les altres pendents del refugi (`CHECK refuge_ref_ck`, §2.18),
  es llegeixen les claus d'R2 dels seus mitjans amb `system_context()`, s'esborra el refugi amb **un sol `DELETE`**
  (la BD cascadeja amb els privilegis del propietari, §8.5) i s'esborren els fitxers d'R2; si R2 falla es desfà tot.
"""
import logging
from typing import Optional

from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.db import IntegrityError, transaction

from apps.uploads import r2_media_service
from apps.core.timezone_utils import get_madrid_timezone
from apps.core.db_functions import TransactionNow
from apps.core.rls import system_context
from apps.refuges import selectors as refuge_selectors
from apps.refuges.models import Refuge, RefugeAmenities, RefugeLink, RefugeMedia
from apps.refuges.serializers import RefugiSerializer, refuge_to_dict

from .models import Action, RefugeProposal, Status

logger = logging.getLogger(__name__)

DELETED_REASON = 'refuge has been deleted'
DUPLICATE_RADIUS_M = 500
MAX_DUPLICATES = 20


class RefugeNotFound(Exception):
    """El refugi d'un `update`/`delete` no existeix (inclou un ID que no és UUID)."""


class ProposalNotFound(Exception):
    """La proposta no existeix (inclou un ID que no és UUID o una que l'actor no pot veure)."""


class ProposalAlreadyReviewed(Exception):
    """La proposta ja ha estat aprovada o rebutjada (`.status`)."""

    def __init__(self, status):
        super().__init__(f'Proposal is already {status}')
        self.status = status


class LinkAlreadyUsed(Exception):
    """Un enllaç del payload ja pertany a un altre refugi (PK de `refuge_links`, TECH_DEBT R12)."""


class PossibleDuplicates(Exception):
    """Hi ha refugis a <= 500 m amb un nom semblant al d'una proposta `create` (`.duplicates`)."""

    def __init__(self, duplicates):
        super().__init__('Possible duplicate refuges')
        self.duplicates = duplicates


class MediaStorageError(Exception):
    """R2 no ha pogut esborrar un fitxer del refugi: es desfà l'aprovació."""


# ---------- Crear ----------

def _snapshot(refuge: Refuge) -> dict:
    """El refugi en forma d'API (la del detall) sense `visitors` ni mitjans: foto històrica immutable."""
    data = RefugiSerializer(refuge_to_dict(refuge)).data         # sense `is_authenticated`: no hi surten ni `visitors` ni mitjans
    return {key: value for key, value in dict(data).items() if key not in ('visitors', 'images_metadata')}


def find_possible_duplicates(payload: dict) -> list:
    """
    Refugis existents a <= 500 m (`ST_DWithin` sobre la `geography`) i amb un nom semblant (la regla de la cerca:
    `norm_name` + `pg_trgm`/subcadena sobre `name` i `surname`). Una consulta; per distància ascendent.
    """
    coord = payload['coord']
    point = Point(coord['long'], coord['lat'], srid=4326)
    queryset = refuge_selectors.filter_name_similar(Refuge.objects.all(), payload['name'].strip())
    # `ST_DWithin` (amb 1 m de marge) usa l'índex GiST; el tall exacte és `ST_Distance <= 500` (a la vora, `ST_DWithin` i
    # `ST_Distance` poden discrepar en 1e-13 m).
    rows = (queryset.filter(coord__dwithin=(point, D(m=DUPLICATE_RADIUS_M + 1)))
            .annotate(distance=Distance('coord', point)).filter(distance__lte=D(m=DUPLICATE_RADIUS_M))
            .order_by('distance', 'id').values_list('id', 'name', 'distance')[:MAX_DUPLICATES])
    return [{'id': str(pk), 'name': name, 'distance_m': round(distance.m)} for pk, name, distance in rows]


def create_proposal(*, creator_uid: str, action: str, refuge_id=None, payload: Optional[dict] = None,
                    comment: Optional[str] = None) -> RefugeProposal:
    """
    Desa una proposta pendent. `update`/`delete` en fan una foto del refugi (`RefugeNotFound` si no existeix);
    `create` comprova els possibles duplicats (`PossibleDuplicates`; no es desa res).
    """
    snapshot = None
    if action == Action.CREATE:
        duplicates = find_possible_duplicates(payload)
        if duplicates:
            raise PossibleDuplicates(duplicates)
        refuge_id = None
    else:
        refuge = refuge_selectors.get_refuge(refuge_id)
        if refuge is None:
            raise RefugeNotFound('Refuge does not exists')
        refuge_id, snapshot = refuge.pk, _snapshot(refuge)
        if action == Action.DELETE:
            payload = None
    try:
        with transaction.atomic():
            return RefugeProposal.objects.create(
                creator_id=creator_uid, action=action, refuge_id=refuge_id, payload=payload,
                refuge_snapshot=snapshot, comment=comment)
    except IntegrityError as exc:
        diag = getattr(exc.__cause__, 'diag', None)
        if getattr(diag, 'constraint_name', None) == 'refuge_proposals_refuge_id_fk':    # esborrat entre la lectura i l'INSERT
            raise RefugeNotFound('Refuge does not exists') from exc
        raise


# ---------- Aprovar / rebutjar ----------

def _lock_pending(proposal_id) -> RefugeProposal:
    """La proposta pendent bloquejada `FOR UPDATE`; si no hi és, 404 o 409 segons el seu estat (2n `SELECT` sense bloqueig)."""
    pk = refuge_selectors.parse_refuge_id(proposal_id)
    if pk is None:
        raise ProposalNotFound('Proposal not found')
    proposal = RefugeProposal.objects.select_for_update().filter(pk=pk, status=Status.PENDING).first()
    if proposal is not None:
        return proposal
    current = RefugeProposal.objects.filter(pk=pk).values_list('status', flat=True).first()
    if current is None or current == Status.PENDING:      # inexistent, invisible o no revisable per l'actor (RLS)
        raise ProposalNotFound('Proposal not found')
    raise ProposalAlreadyReviewed(current)


def _madrid_date(instant):
    return instant.astimezone(get_madrid_timezone()).date()


def _blank_to_none(value):
    return value or None


def _refuge_columns(payload: dict) -> dict:
    """Columnes de `refuges` que el payload canvia (només les claus enviades)."""
    columns = {}
    for key in ('name', 'altitude', 'places'):
        if key in payload:
            columns[key] = payload[key]
    if 'type' in payload:
        columns['type_id'] = payload['type']
    if 'coord' in payload:
        columns['coord'] = Point(payload['coord']['long'], payload['coord']['lat'], srid=4326)
    if 'description' in payload:
        columns['description'] = payload['description'] or ''                 # NOT NULL: `null` -> ''
    for key in ('region', 'departement'):
        if key in payload:
            columns[key] = _blank_to_none(payload[key])                       # '' -> NULL
    if payload.get('condition') is not None:                                  # reinicia la mitjana (§2.9)
        columns.update(condition=float(payload['condition']), num_contributed_conditions=1,
                       condition_reset_at=TransactionNow())
    return columns


def _amenity_flags(info_comp: dict) -> dict:
    """Els 12 indicadors; els absents de l'`info_comp` enviat passen a `false`."""
    return {field: bool(info_comp.get(field)) for field in RefugeAmenities.AMENITY_FIELDS}


def _replace_links(refuge_id, urls: list) -> None:
    RefugeLink.objects.filter(refuge_id=refuge_id).delete()
    if not urls:
        return
    try:
        with transaction.atomic():
            RefugeLink.objects.bulk_create(
                [RefugeLink(url=url, refuge_id=refuge_id, position=i) for i, url in enumerate(urls)])
    except IntegrityError as exc:
        diag = getattr(exc.__cause__, 'diag', None)
        if getattr(diag, 'constraint_name', None) == 'refuge_links_pkey':
            raise LinkAlreadyUsed('A link of the proposal already belongs to another refuge') from exc
        raise


def _apply_create(proposal: RefugeProposal):
    payload = proposal.payload
    columns = _refuge_columns(payload)
    columns.setdefault('description', '')
    columns['modified_at'] = _madrid_date(proposal.created_at)
    refuge = Refuge.objects.create(**columns)
    RefugeAmenities.objects.create(refuge=refuge, **_amenity_flags(payload.get('info_comp') or {}))
    _replace_links(refuge.pk, payload.get('links') or [])
    return refuge.pk


def _apply_update(proposal: RefugeProposal):
    payload = proposal.payload
    columns = _refuge_columns(payload)
    columns['modified_at'] = _madrid_date(proposal.created_at)
    if not Refuge.objects.filter(pk=proposal.refuge_id).update(**columns):
        raise RefugeNotFound('Refuge does not exists')
    if 'info_comp' in payload:
        flags = _amenity_flags(payload['info_comp'] or {})
        if not RefugeAmenities.objects.filter(refuge_id=proposal.refuge_id).update(**flags):
            RefugeAmenities.objects.create(refuge_id=proposal.refuge_id, **flags)
    if 'links' in payload:
        _replace_links(proposal.refuge_id, payload['links'] or [])
    return proposal.refuge_id


def _delete_files(service, keys: list, what: str) -> list:
    """Esborra fitxers d'R2; retorna els que han fallat (`delete_files` informa de `failed` o llança)."""
    try:
        return list(service.delete_files(keys).get('failed') or [])
    except Exception as exc:
        raise MediaStorageError(f'R2 ha fallat en esborrar {what}') from exc


def _own_keys(refuge_id, keys: list) -> list:
    """
    Defensa en profunditat: només les claus sota `refugis-lliures/{refuge_id}/` i sense `..` (les que fabrica el servidor);
    qualsevol altra (dada corrupta, d'un altre refugi o d'altres prefixos) no es passa mai a R2.
    """
    prefix = f'refugis-lliures/{refuge_id}/'
    own = [key for key in keys if key.startswith(prefix) and '..' not in key]
    if len(own) != len(keys):
        logger.warning("Claus d'R2 fora del prefix del refugi %s ignorades: %d", refuge_id, len(keys) - len(own))
    return own


def _apply_delete(proposal: RefugeProposal, media_service=None):
    """Esborra el refugi (un sol `DELETE`) i els seus fitxers d'R2; retorna les miniatures a esborrar després del `COMMIT`."""
    refuge_id = proposal.refuge_id
    # Les altres pendents del refugi es rebutgen abans (si no, el `SET NULL` violaria `refuge_ref_ck`).
    RefugeProposal.objects.filter(refuge_id=refuge_id, status=Status.PENDING).exclude(pk=proposal.pk).update(
        status=Status.REJECTED, reviewed_at=TransactionNow(), rejection_reason=DELETED_REASON, reviewer=None)
    with system_context():           # tots els mitjans, també els amagats i els d'altres usuaris o d'experiències
        rows = list(RefugeMedia.objects.filter(refuge_id=refuge_id).values_list('key', 'thumb_key'))
    if not Refuge.objects.filter(pk=refuge_id).delete()[0]:
        raise RefugeNotFound('Refuge does not exists')
    keys = _own_keys(refuge_id, [key for key, _ in rows])
    thumbs = _own_keys(refuge_id, [thumb for _, thumb in rows if thumb])
    if keys:
        service = media_service or r2_media_service.get_refugi_media_service()
        if _delete_files(service, keys, 'els fitxers del refugi'):
            raise MediaStorageError('R2 no ha esborrat tots els fitxers del refugi')      # desfà l'aprovació
    return thumbs


def approve_proposal(*, proposal_id, reviewer_uid: str, media_service=None) -> RefugeProposal:
    """
    Aprova la proposta i n'aplica l'acció, tot en una transacció. `ProposalNotFound`, `ProposalAlreadyReviewed`,
    `LinkAlreadyUsed` (cap canvi), `MediaStorageError` (R2 caigut en un `delete`: cap canvi).
    """
    thumbs = []
    with transaction.atomic():
        proposal = _lock_pending(proposal_id)
        new_refuge_id = proposal.refuge_id
        if proposal.action == Action.CREATE:
            new_refuge_id = _apply_create(proposal)
        elif proposal.action == Action.UPDATE:
            _apply_update(proposal)
        # La proposta passa a aprovada abans d'esborrar el refugi: la resta de pendents d'aquell refugi es rebutgen a part.
        updated = RefugeProposal.objects.filter(pk=proposal.pk, status=Status.PENDING).update(
            status=Status.APPROVED, reviewer_id=reviewer_uid, reviewed_at=TransactionNow(), refuge_id=new_refuge_id)
        if updated != 1:
            raise ProposalAlreadyReviewed(Status.APPROVED)
        if proposal.action == Action.DELETE:
            thumbs = _apply_delete(proposal, media_service)
        proposal.status, proposal.reviewer_id, proposal.refuge_id = Status.APPROVED, reviewer_uid, new_refuge_id
        if proposal.action == Action.DELETE:
            proposal.refuge_id = None
        proposal.refresh_from_db(fields=['reviewed_at'])
    if thumbs:                      # miniatures: si falla només queden fitxers orfes
        service = media_service or r2_media_service.get_refugi_media_service()
        try:
            failed = _delete_files(service, thumbs, 'les miniatures del refugi')
        except MediaStorageError:
            failed = thumbs
        if failed:
            logger.warning('Miniatures òrfenes a R2: %d fitxers', len(failed))
    return proposal


def reject_proposal(*, proposal_id, reviewer_uid: str, reason: Optional[str] = None) -> RefugeProposal:
    """Rebutja la proposta (no s'aplica res); sense motiu, `rejection_reason` queda a `NULL`."""
    with transaction.atomic():
        proposal = _lock_pending(proposal_id)
        RefugeProposal.objects.filter(pk=proposal.pk, status=Status.PENDING).update(
            status=Status.REJECTED, reviewer_id=reviewer_uid, reviewed_at=TransactionNow(),
            rejection_reason=reason or None)
        proposal.status, proposal.reviewer_id, proposal.rejection_reason = Status.REJECTED, reviewer_uid, reason or None
        proposal.refresh_from_db(fields=['reviewed_at'])
    return proposal
