"""
Lectures de `accounts` (substitueixen el `UserDAO` de Firestore; docs/design/postgres-schema.md §4, §5.2, §5.3).

Totes les consultes van amb el rol `app`: la RLS ja limita `users` i les llistes al propi usuari (l'admin veu `users`
i els visitats). Pressupost de consultes constant (no depèn del nombre de files):
- `get_user`: 1; `get_own_profile` i `get_public_profile`: 1 (llistes, claus de fotos i avatar com a subconsultes);
- llistes de preferits/visitats: 1 (JOIN amb els refugis) + 1 (primera imatge visible de cada refugi, en bloc).
"""
import logging
from typing import Optional

from django.contrib.postgres.expressions import ArraySubquery
from django.db.models import OuterRef, Subquery
from django.db.models.functions import JSONObject

from apps.refuges.models import RefugeMedia

from .models import FavouriteRefuge, UserAccount, UserAvatar, UserPublicProfile, VisitedRefuge

logger = logging.getLogger(__name__)

LIST_MODELS = {'favourite': FavouriteRefuge, 'visited': VisitedRefuge}


def get_user(uid: str) -> Optional[UserAccount]:
    """Fila de `users.users` (1 consulta). La RLS només deixa veure la pròpia (o totes a admin/sistema)."""
    if not uid:
        return None
    return UserAccount.objects.filter(pk=uid).first()


def _avatar_json(outer: str = 'pk'):
    """Avatar (0..1) com a objecte JSON d'una subconsulta escalar: no afegeix cap consulta ni cap JOIN multiplicador."""
    return Subquery(
        UserAvatar.objects.filter(user_id=OuterRef(outer))
        .annotate(data=JSONObject(key='key', thumb_key='thumb_key', content_type='content_type', width='width',
                                  height='height', blurhash='blurhash', uploaded_at='uploaded_at'))
        .values('data')[:1])


def get_own_profile(uid: str) -> Optional[UserAccount]:
    """
    Perfil complet del propi usuari (1 consulta): `users` + `user_public_profiles` (JOIN) i, com a subconsultes, les
    llistes de refugis (`favourite_ids`, `visited_ids`, ordenades per `(created_at, refuge_id)`), les claus de les
    fotos pujades (`photo_keys`, tots els estats, per `(uploaded_at, key)`) i l'avatar (`avatar_json`).
    """
    def ids(model):
        return ArraySubquery(model.objects.filter(user_id=OuterRef('pk')).order_by('created_at', 'refuge_id')
                             .values('refuge_id'))

    photo_keys = ArraySubquery(RefugeMedia.objects.filter(creator_id=OuterRef('pk'))
                               .order_by('uploaded_at', 'key').values('key'))
    return (UserAccount.objects.filter(pk=uid).select_related('public_profile')
            .annotate(favourite_ids=ids(FavouriteRefuge), visited_ids=ids(VisitedRefuge), photo_keys=photo_keys,
                      avatar_json=_avatar_json())
            .first())


def get_public_profile(uid: str) -> Optional[UserPublicProfile]:
    """Perfil públic d'un altre usuari: `{uid, username, avatar}` (1 consulta; cap comptador ni llista)."""
    return UserPublicProfile.objects.filter(pk=uid).annotate(avatar_json=_avatar_json()).first()


def get_avatar(uid: str) -> Optional[UserAvatar]:
    """Avatar de l'usuari (1 consulta)."""
    return UserAvatar.objects.filter(user_id=uid).first()


def list_refuges(kind: str, uid: str) -> list:
    """
    Preferits (`'favourite'`) o visitats (`'visited'`) de l'usuari, per `(created_at, refuge_id)`.

    Retorna `[(refuge, first_media | None)]`: 1 consulta amb JOIN als refugis + 1 amb la primera imatge **visible** de
    cada refugi (`DISTINCT ON (refuge_id)`), sense N+1.
    """
    rows = list(LIST_MODELS[kind].objects.filter(user_id=uid).select_related('refuge')
                .order_by('created_at', 'refuge_id'))
    refuges = [r.refuge for r in rows]
    first = first_visible_media([r.pk for r in refuges])
    return [(r, first.get(r.pk)) for r in refuges]


def first_visible_media(refuge_ids: list) -> dict:
    """`{refuge_id: primera imatge visible}` (1 consulta; `uploaded_at, key` com a ordre determinista)."""
    if not refuge_ids:
        return {}
    qs = (RefugeMedia.objects.filter(refuge_id__in=refuge_ids, status='visible')
          .order_by('refuge_id', 'uploaded_at', 'key').distinct('refuge_id'))
    return {m.refuge_id: m for m in qs}


def get_refuge_with_first_media(refuge_id):
    """`(refuge, first_media | None)` d'un refugi (2 consultes) o `None` si no existeix."""
    from apps.refuges.selectors import parse_refuge_id
    from apps.refuges.models import Refuge
    pk = parse_refuge_id(refuge_id)
    refuge = Refuge.objects.filter(pk=pk).first() if pk else None
    if refuge is None:
        return None
    return refuge, first_visible_media([refuge.pk]).get(refuge.pk)


# ---------- Comptadors del perfil propi ----------

def _firestore_count(collection: str, field: str, op: str, value: str) -> int:
    """`count()` d'agregació de Firestore. Només per a les experiències (chunk 7); les reformes ja són a SQL."""
    from google.cloud.firestore_v1.base_query import FieldFilter

    from api.services.firestore_service import FirestoreService
    query = FirestoreService().get_db().collection(collection).where(filter=FieldFilter(field, op, value)).count()
    return int(query.get()[0][0].value)


def get_legacy_counts(uid: str) -> dict:
    """
    `num_shared_experiences` i `num_renovated_refuges` del perfil propi (D19).

    - Reformes (chunk 5): agregació SQL, 1 consulta (§4): creades + unides, passades incloses; els expulsats no compten.
    - Experiències: `count()` de Firestore fins al chunk 7. Una fallada de Firestore es propaga (el perfil no ha de
      mostrar zeros falsos).
    """
    from apps.renovations import selectors as renovation_selectors
    return {
        'num_shared_experiences': _firestore_count('experiences', 'creator_uid', '==', uid),
        'num_renovated_refuges': renovation_selectors.count_renovated_refuges(uid),
    }
