"""
Escriptures de `accounts` (substitueixen el `UserController` de Firestore).

Les escriptures de l'usuari van amb el context de RLS de la petició (només el propi compte); les de moderació
(strikes, bloqueig) i l'avatar des del flux de pujades s'executen dins `system_context()` (D20): el *trigger*
`fn_users_guard` impedeix canviar les columnes de moderació com a usuari corrent i la petició pot ser d'un altre
usuari (denúncia) o del mateix (coincidència de hash). Excepcions de domini; cap tupla.
"""
import logging
import uuid
from datetime import date
from typing import Any, Dict, Optional

from django.db import IntegrityError, transaction
from django.db.models import F
from django.db.models.functions import Now
from firebase_admin import auth as firebase_auth

from api.services import audit_log_service as audit
from api.services import r2_media_service
from api.utils.age_utils import is_old_enough
from api.utils.timezone_utils import get_madrid_timezone
from apps.core.rls import system_context
from apps.refuges import selectors as refuge_selectors
from apps.refuges.models import RefugeMedia

from . import selectors
from .models import FavouriteRefuge, UserAccount, UserAvatar, UserPublicProfile, VisitedRefuge

logger = logging.getLogger(__name__)

# Edat mínima per usar l'app (RGPD art. 8 / LOPDGDD art. 7 → 14; l'app exigeix 16)
AGE_THRESHOLD = 16


class UserAlreadyExists(Exception):
    """Ja hi ha una fila a `users.users` amb aquest UID."""


class UserNotFound(Exception):
    """L'usuari no existeix."""


class UserUnderage(Exception):
    """L'usuari és menor de l'edat mínima (`AGE_THRESHOLD`)."""


class RefugeNotFound(Exception):
    """El refugi no existeix (inclou un ID que no és un UUID, com un ID antic de Firestore)."""


class AvatarNotFound(Exception):
    """L'usuari no té cap avatar."""


class AvatarStorageError(Exception):
    """R2 no ha pogut esborrar l'avatar: la fila es conserva."""


class UserDeletionError(Exception):
    """Un pas de l'esborrat (Firestore, R2 o Firebase Auth) ha fallat: l'usuari es conserva i és reintentable."""


class FirebaseAccountNotFound(Exception):
    """L'UID del token ja no té compte a Firebase Auth (esborrat amb el token encara vigent, U7)."""


def _firebase_account_exists(uid: str) -> bool:
    """`True` si l'UID té compte a Firebase Auth; qualsevol error que no sigui «no existeix» es propaga (500)."""
    try:
        firebase_auth.get_user(uid)
    except firebase_auth.UserNotFoundError:
        return False
    return True


def _delete_firebase_account(uid: str) -> None:
    """Esborra el compte de Firebase Auth (U7). Si ja no hi és, l'esborrat ja està fet (idempotent)."""
    try:
        firebase_auth.delete_user(uid)
    except firebase_auth.UserNotFoundError:
        logger.warning("Esborrat d'usuari: el compte de Firebase Auth ja no existia")
    except Exception as exc:
        raise UserDeletionError("Firebase Auth no ha esborrat el compte") from exc


# ---------- Alta, edició i edat ----------

def create_user(*, uid: str, username: str = '', language: Optional[str] = None,
                birth_date: Optional[date] = None) -> UserAccount:
    """
    Crea `users` + `user_public_profiles` en una sola transacció (`savepoint`): o es creen tots dos o cap.

    La data de naixement **només** serveix per comprovar l'edat; mai es desa (només `age_confirmed_at` i
    `age_threshold`). `UserUnderage` si és menor; `UserAlreadyExists` si l'UID ja té fila; `FirebaseAccountNotFound`
    si el compte de Firebase Auth ja s'ha esborrat però el token encara és vigent (fins a 1 h): sense aquesta
    comprovació, un usuari bloquejat podria esborrar-se i tornar a crear-se amb el mateix UID sense el bloqueig (U7).
    """
    fields: Dict[str, Any] = {}
    if birth_date is not None:
        if not is_old_enough(birth_date, AGE_THRESHOLD):
            raise UserUnderage()
        fields.update(age_confirmed_at=Now(), age_threshold=AGE_THRESHOLD)    # rellotge de la BD (decisió 26/10)
    if not _firebase_account_exists(uid):
        raise FirebaseAccountNotFound()
    if language:
        fields['language_id'] = language
    try:
        with transaction.atomic():
            user = UserAccount.objects.create(uid=uid, **fields)
            UserPublicProfile.objects.create(user=user, username=username or '')
    except IntegrityError:
        # Fora del savepoint (ja desfet): si l'UID existeix és un duplicat; qualsevol altra cosa és un error real.
        if UserAccount.objects.filter(pk=uid).exists():
            raise UserAlreadyExists(f'Usuari amb UID {uid} ja existeix') from None
        raise
    return user


def ensure_user(uid: str) -> None:
    """
    Assegura que `users` + `user_public_profiles` existeixen (`INSERT ... ON CONFLICT DO NOTHING`; no trepitja res).
    Per a `scripts/manage_admins.py add` (cal `system_context()`: no hi ha petició d'usuari).
    """
    with transaction.atomic():
        UserAccount.objects.bulk_create([UserAccount(uid=uid)], ignore_conflicts=True)
        UserPublicProfile.objects.bulk_create([UserPublicProfile(user_id=uid)], ignore_conflicts=True)


def update_user(uid: str, *, username: Optional[str] = None, language: Optional[str] = None) -> None:
    """Actualitza el nom d'usuari (perfil públic) i/o l'idioma. Només es toca el que es proporciona."""
    with transaction.atomic():
        if language is not None and not UserAccount.objects.filter(pk=uid).update(language_id=language):
            raise UserNotFound()
        if username is not None:
            if not UserPublicProfile.objects.filter(pk=uid).update(username=username, updated_at=Now()):
                raise UserNotFound()


def confirm_age(uid: str, birth_date: date) -> None:
    """Confirma l'edat (només `age_confirmed_at` i `age_threshold`; la data de naixement es descarta)."""
    if not is_old_enough(birth_date, AGE_THRESHOLD):
        raise UserUnderage()
    if not UserAccount.objects.filter(pk=uid).update(age_confirmed_at=Now(), age_threshold=AGE_THRESHOLD):
        raise UserNotFound()
    audit.audit_log_service.log(uid, audit.ACTION_AGE_CONFIRMED, 'user', uid, {'age_threshold': AGE_THRESHOLD})


# ---------- Preferits i visitats ----------

def _refuge_pk(refuge_id) -> uuid.UUID:
    pk = refuge_selectors.parse_refuge_id(refuge_id)
    if pk is None or not refuge_selectors.refuge_exists(pk):
        raise RefugeNotFound(f'Refugi amb ID {refuge_id} no trobat')
    return pk


def _add(model, uid: str, refuge_id) -> uuid.UUID:
    pk = _refuge_pk(refuge_id)
    # `INSERT ... ON CONFLICT DO NOTHING`: idempotent i sense carreres; conserva el `created_at` original.
    model.objects.bulk_create([model(user_id=uid, refuge_id=pk)], ignore_conflicts=True)
    return pk


def _remove(model, uid: str, refuge_id) -> None:
    pk = _refuge_pk(refuge_id)
    model.objects.filter(user_id=uid, refuge_id=pk).delete()          # idempotent: 0 files no és un error


def add_favourite(uid: str, refuge_id) -> uuid.UUID:
    return _add(FavouriteRefuge, uid, refuge_id)


def remove_favourite(uid: str, refuge_id) -> None:
    _remove(FavouriteRefuge, uid, refuge_id)


def add_visited(uid: str, refuge_id) -> uuid.UUID:
    return _add(VisitedRefuge, uid, refuge_id)


def remove_visited(uid: str, refuge_id) -> None:
    _remove(VisitedRefuge, uid, refuge_id)


# ---------- Moderació (D20): dins `system_context()` ----------

def increment_moderation_strikes(uid: str) -> Optional[int]:
    """Suma un *strike* (atòmic, `F()`) i retorna el total; `None` si l'usuari no existeix."""
    with system_context():
        if not UserAccount.objects.filter(pk=uid).update(moderation_strikes=F('moderation_strikes') + 1):
            return None
        return UserAccount.objects.filter(pk=uid).values_list('moderation_strikes', flat=True).get()


def set_blocked(uid: str, blocked: bool = True, reason: Optional[str] = None) -> bool:
    """
    Bloqueja (`reason` ∈ `csam_confirmed|strikes|moderation_hash_match`; `blocked_at` = rellotge de la BD) o
    desbloqueja (neteja motiu i data) un usuari. `False` si no existeix; un motiu invàlid llança `IntegrityError`.
    """
    changes = ({'is_blocked': True, 'blocked_reason': reason, 'blocked_at': Now()} if blocked
               else {'is_blocked': False, 'blocked_reason': None, 'blocked_at': None})
    with system_context():
        return bool(UserAccount.objects.filter(pk=uid).update(**changes))


# ---------- Avatar ----------

def update_avatar_metadata(uid: str, metadata: Dict[str, Any]) -> bool:
    """
    Substitueix l'avatar: `DELETE` de la fila antiga + `INSERT` de la nova (la PK és la clau R2) en una transacció (D20).
    `metadata`: `key, width, height, blurhash, size, content_type[, thumb_key]` (forma que produeix el flux de
    pujades; un `uploaded_at` s'ignora: el posa el rellotge de la BD, `db_default`). `False` si l'usuari no existeix.
    Els fitxers antics d'R2 els esborra qui crida.
    """
    with system_context():
        # `FOR UPDATE` de la fila d'usuari: serialitza dues substitucions concurrents (si no, totes dues farien
        # `DELETE` de res i el segon `INSERT` fallaria per `user_avatars_user_uq`).
        if not UserAccount.objects.select_for_update().filter(pk=uid).exists():
            return False
        UserAvatar.objects.filter(user_id=uid).delete()
        avatar = UserAvatar.objects.create(
            key=metadata['key'], user_id=uid, thumb_key=metadata.get('thumb_key'),
            content_type=metadata['content_type'], width=metadata.get('width'), height=metadata.get('height'),
            size_bytes=metadata.get('size'), blurhash=metadata.get('blurhash'))
    # El valor real (rellotge de la BD, recuperat amb `RETURNING`) torna a `metadata` per a la resposta de la pujada
    metadata['uploaded_at'] = avatar.uploaded_at.astimezone(get_madrid_timezone()).isoformat()
    return True


def delete_avatar(uid: str, media_service=None) -> None:
    """
    Esborra l'avatar: la fila de `user_avatars` i els fitxers d'R2 (clau i miniatura).

    `R2MediaService.delete_file` retorna `False` (no llança): es comprova i es desfà l'esborrat de la fila
    (`AvatarStorageError`). Una miniatura que no s'esborra només queda com a fitxer orfe (avís al log).
    """
    avatar = selectors.get_avatar(uid)
    if avatar is None:
        raise AvatarNotFound("L'usuari no té cap avatar")
    service = media_service or r2_media_service.get_user_avatar_service()
    with transaction.atomic():
        UserAvatar.objects.filter(pk=avatar.key).delete()
        try:
            stored = service.delete_file(avatar.key)
        except Exception as exc:
            raise AvatarStorageError("R2 ha fallat en esborrar l'avatar") from exc     # desfà l'esborrat de la fila
        if not stored:
            raise AvatarStorageError("R2 no ha esborrat l'avatar")
    if avatar.thumb_key and not service.delete_file(avatar.thumb_key):
        logger.warning("Miniatura d'avatar òrfena a R2: %s", avatar.thumb_key)


# ---------- Esborrat d'usuari provisional (D21, D22) ----------

def _firestore_steps(uid: str):
    """Passos de l'esborrat que encara viuen a Firestore (D21), en l'ordre de sempre: `(nom, callable)`."""
    from api.controllers.experience_controller import ExperienceController
    from api.controllers.refuge_proposal_controller import RefugeProposalController
    from api.controllers.renovation_controller import RenovationController
    renovations = RenovationController()
    return [
        ('experiències', lambda: ExperienceController().delete_experiences_by_creator(uid)),
        ('propostes', lambda: RefugeProposalController().anonymize_proposals_by_creator(uid)),
        ('reformes actuals', lambda: renovations.delete_current_renovations_by_creator(uid)),
        ('reformes anonimitzades', lambda: renovations.anonymize_renovations_by_creator(uid)),
        ('participacions en reformes', lambda: renovations.remove_user_from_participations(uid)),
        ('expulsions de reformes', lambda: renovations.remove_user_from_expelled(uid)),
    ]


def _delete_r2_media(uid: str, media_service=None) -> None:
    """D22 (RGPD): esborra a R2 l'avatar (clau i miniatura) i les fotos pujades per l'usuari (i les seves miniatures)."""
    keys = []
    for key, thumb in UserAvatar.objects.filter(user_id=uid).values_list('key', 'thumb_key'):
        keys += [key, thumb]
    for key, thumb in RefugeMedia.objects.filter(creator_id=uid).values_list('key', 'thumb_key'):
        keys += [key, thumb]
    keys = [k for k in dict.fromkeys(keys) if k]
    if not keys:
        return
    service = media_service or r2_media_service.get_refugi_media_service()
    result = service.delete_files(keys)
    if result.get('failed'):
        logger.error("R2: %d fitxers de l'usuari no s'han pogut esborrar", len(result['failed']))
        raise UserDeletionError("R2 no ha esborrat tots els fitxers de l'usuari")


def delete_user(uid: str, media_service=None) -> None:
    """
    Esborra l'usuari: primer els passos de Firestore (D21), després R2 (D22), el `DELETE` de `users.users` (la BD
    cascadeja perfil, avatar, preferits, visitats i fotos) i al final el compte de Firebase Auth (U7, D24): primer
    les dades i després el compte, perquè l'usuari pugui reintentar mentre el compte existeixi.

    El `DELETE` i Firebase Auth van dins un *savepoint*: si Firebase falla, `UserDeletionError` desfà el `DELETE`
    (la vista retorna 500 sense excepció, així que `ATOMIC_REQUESTS` no el desfaria) i l'usuari es conserva.
    Els passos d'abans no es desfan (Firestore/R2 no són transaccionals; són idempotents).
    Finestra residual: si el `COMMIT` falla després d'esborrar el compte, queden les dades sense compte (rar;
    ho tanca el procediment únic del chunk 10).
    """
    for name, step in _firestore_steps(uid):
        success, error = step()
        if not success:
            logger.error("Esborrat d'usuari: ha fallat el pas «%s»: %s", name, error)
            raise UserDeletionError(f'Ha fallat el pas «{name}» a Firestore')
    _delete_r2_media(uid, media_service)
    with transaction.atomic():
        if not UserAccount.objects.filter(pk=uid).delete()[0]:
            raise UserNotFound()
        _delete_firebase_account(uid)
