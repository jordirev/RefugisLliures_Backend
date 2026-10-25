"""
Lectures de `refuges` (substitueixen el DAO de Firestore; docs/design/postgres-schema.md §5.3).

Totes les consultes van amb el rol `app`: la RLS ja filtra els mitjans (visibles per a tothom; la resta, autor i
admin) i, a més, es filtra explícitament (defensa en profunditat). Cap N+1: el pressupost de consultes és constant
(llista sense filtres 1; amb filtres 1 + 1 de mitjans si és autenticat; detall 1 + 1 de mitjans + visitants d'admin).
"""
import uuid
from typing import Iterable, Optional

from django.contrib.postgres.expressions import ArraySubquery
from django.contrib.postgres.search import TrigramSimilarity
from django.contrib.gis.db.models import GeometryField
from django.db.models import CharField, F, FloatField, Func, IntegerField, OuterRef, Prefetch, Q, QuerySet, Value
from django.db.models.functions import Cast
from django.db.models.functions import Coalesce, Greatest

from apps.accounts.models import VisitedRefuge

from .models import Refuge, RefugeLink, RefugeMedia, RefugeType, norm_name


def parse_refuge_id(value) -> Optional[uuid.UUID]:
    """Els IDs són UUID; qualsevol altra cosa (p. ex. un ID antic de Firestore) no existeix (404, no 500)."""
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return None


def media_visible_to(viewer_uid: Optional[str], is_admin: bool) -> Q:
    """Mitjans que veu l'espectador: els visibles, els propis i (si és admin) tots. Redundant amb la RLS."""
    if is_admin:
        return Q()
    q = Q(status='visible')
    if viewer_uid:
        q |= Q(creator_id=viewer_uid)
    return q


def _ordered_media(viewer_uid: Optional[str], is_admin: bool) -> QuerySet:
    return RefugeMedia.objects.filter(media_visible_to(viewer_uid, is_admin)).order_by('uploaded_at', 'key')


def _with_links(qs: QuerySet) -> QuerySet:
    """Enllaços ordenats com a `ARRAY(...)` d'una subconsulta: no afegeix cap consulta ni cap fila duplicada."""
    links = ArraySubquery(
        RefugeLink.objects.filter(refuge=OuterRef('pk')).order_by('position').values('url'))
    return qs.select_related('amenities').annotate(links_list=links)


# ---------- Detall ----------

def get_refuge(refuge_id) -> Optional[Refuge]:
    """Refugi amb serveis i enllaços (1 consulta); `None` si no existeix o l'ID no és un UUID."""
    pk = parse_refuge_id(refuge_id)
    if pk is None:
        return None
    return _with_links(Refuge.objects.filter(pk=pk)).first()


def refuge_exists(refuge_id) -> bool:
    pk = parse_refuge_id(refuge_id)
    return pk is not None and Refuge.objects.filter(pk=pk).exists()


def get_refuge_media(refuge_id, viewer_uid: Optional[str] = None, is_admin: bool = False) -> list:
    """Mitjans d'un refugi ordenats per `(uploaded_at, key)` (determinista)."""
    return list(_ordered_media(viewer_uid, is_admin).filter(refuge_id=refuge_id))


def get_visitor_uids(refuge_id) -> list:
    """
    UIDs dels visitants del refugi, de `users.user_visited_refuges` (1 consulta; només es mostren als admins).

    La RLS només deixa veure totes les files a admin/sistema; un usuari normal només veuria la pròpia.
    """
    pk = parse_refuge_id(refuge_id)
    if pk is None:
        return []
    return list(VisitedRefuge.objects.filter(refuge_id=pk).order_by('created_at', 'user_id')
                .values_list('user_id', flat=True))


def get_media_by_key(refuge_id, key: str) -> Optional[RefugeMedia]:
    """Un mitjà del refugi (la RLS només deixa veure'l si és visible, propi o l'espectador és admin)."""
    pk = parse_refuge_id(refuge_id)
    if pk is None or chr(0) in key:                 # Postgres no admet NUL en un `text`: seria un 500, no un «no existeix»
        return None
    return RefugeMedia.objects.filter(pk=key, refuge_id=pk).first()


# ---------- Llista sense filtres (punts del mapa) ----------

def _geometry(field):
    return Cast(F(field), GeometryField(srid=4326))


def list_map_points() -> list:
    """`[{id, name, lat, lng, geohash}]` ordenats per nom: 1 consulta directa a `refuges`, sense joins (§5.3, recepta 5)."""
    return list(
        Refuge.objects.annotate(
            lat=Func(_geometry('coord'), function='ST_Y', output_field=FloatField()),
            lng=Func(_geometry('coord'), function='ST_X', output_field=FloatField()),
            geohash=Func(_geometry('coord'), Value(5), function='ST_GeoHash', output_field=CharField()),
        ).order_by('name', 'id').values('id', 'name', 'lat', 'lng', 'geohash'))


def refuge_type_codes() -> set:
    """Codis del catàleg `refuges.refuge_types` (1 consulta; valida el filtre `type`)."""
    return set(RefugeType.objects.values_list('code', flat=True))


# ---------- Cerca amb filtres ----------

def has_active_filters(filters: dict) -> bool:
    return bool(
        (filters.get('name') or '').strip() or filters.get('type') or filters.get('condition')
        or any(filters.get(k) is not None for k in ('places_min', 'places_max', 'altitude_min', 'altitude_max')))


def search_queryset(filters: dict) -> QuerySet:
    """
    `QuerySet` de la cerca amb filtres (una sola consulta SQL; vegeu `search_refuges`).

    - `name`: coincidència parcial i sense accents ni majúscules sobre `name` i `surname`
      (`core.norm_name` + `pg_trgm`: similitud o subcadena; usa els índexs GIN); ordena per similitud descendent.
    - `type`, `places_*`, `altitude_*`: `WHERE`. Els `NULL` no compleixen cap rang.
    - `condition` (0-3): sobre `core.round_half_even(condition)`; els refugis sense valoració no coincideixen.
    """
    qs = _with_links(Refuge.objects.all())

    name = (filters.get('name') or '').strip()
    if name:
        wanted = norm_name(Value(name))
        qs = qs.alias(name_n=norm_name(F('name')), surname_n=norm_name(F('surname')))
        # `surname IS NOT NULL` a cada braç (OR pla): sense ell el planificador no pot usar l'índex GIN parcial de l'àlies.
        qs = qs.filter(
            Q(name_n__trigram_similar=wanted) | Q(name_n__contains=wanted)
            | Q(surname__isnull=False, surname_n__trigram_similar=wanted)
            | Q(surname__isnull=False, surname_n__contains=wanted))
        qs = qs.alias(similarity=Greatest(
            TrigramSimilarity(norm_name(F('name')), wanted),
            Coalesce(TrigramSimilarity(norm_name(F('surname')), wanted), 0.0))).order_by('-similarity', 'name', 'id')
    else:
        qs = qs.order_by('name', 'id')

    if filters.get('type'):
        qs = qs.filter(type__in=filters['type'])
    for field in ('places', 'altitude'):
        if filters.get(f'{field}_min') is not None:
            qs = qs.filter(**{f'{field}__gte': filters[f'{field}_min']})
        if filters.get(f'{field}_max') is not None:
            qs = qs.filter(**{f'{field}__lte': filters[f'{field}_max']})
    if filters.get('condition'):
        qs = qs.alias(condition_rounded=Func(F('condition'), function='core.round_half_even',
                                             output_field=IntegerField()))
        qs = qs.filter(condition_rounded__in=filters['condition'])
    return qs


def search_refuges(filters: dict, viewer_uid: Optional[str] = None, authenticated: bool = False,
                   is_admin: bool = False) -> list:
    """Cerca amb filtres: 1 consulta (+1 de mitjans en bloc, amb `Prefetch`, si l'espectador és autenticat)."""
    qs = search_queryset(filters)
    if authenticated:
        qs = qs.prefetch_related(Prefetch('media', queryset=_ordered_media(viewer_uid, is_admin),
                                          to_attr='media_list'))
    return list(qs)


def media_of(refuge: Refuge) -> Iterable[RefugeMedia]:
    """Mitjans ja carregats per `search_refuges(..., authenticated=True)`."""
    return getattr(refuge, 'media_list', [])
