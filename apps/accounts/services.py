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

from django.db import IntegrityError, OperationalError, connection, transaction
from django.db.models import F
from django.db.models.functions import Now
from firebase_admin import auth as firebase_auth

from apps.audit import services as audit
from api.services import r2_media_service
from api.utils.age_utils import is_old_enough
from api.utils.timezone_utils import get_madrid_timezone
from apps.core.rls import rls_context, system_context
from apps.experiences.models import Experience
from apps.refuges import selectors as refuge_selectors
from apps.proposals.models import RefugeProposal
from apps.refuges.models import RefugeMedia
from apps.renovations import services as renovation_services
from apps.uploads.models import UploadStatus, UploadIntent

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
    """Un pas de l'esborrat ha fallat: R2 (tot desfet) o Firebase Auth (dades ja esborrades); reintentable."""


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


# ---------- Esborrat d'usuari (D42, §8.4) ----------

# Pas 2 de §8.4: els mitjans ocults que només ho són per denúncies pendents d'aquest usuari tornen a la cua com a
# denúncia automàtica. D42 (5): si alguna d'aquestes denúncies és `legal_hold` (es conserva anonimitzada) el mitjà ja
# continua a la cua i no se n'afegeix cap. Els mitjans de les experiències de l'usuari s'exclouen: cauen per cascada.
_AUTO_REPORTS_SQL = """
INSERT INTO moderation.media_reports
    (refuge_id, media_key, reporter_uid, reason, details, media_creator_uid, priority, source)
SELECT m.refuge_id, m.key, NULL, 'other', 'reporter_account_deleted', m.creator_uid, 'high', 'automatic'
  FROM refuges.refuge_media m
 WHERE m.status = 'hidden_pending_review'
   AND m.creator_uid <> %(uid)s
   AND (m.experience_id IS NULL
        OR NOT EXISTS (SELECT 1 FROM activity.experiences e WHERE e.id = m.experience_id AND e.creator_uid = %(uid)s))
   AND EXISTS     (SELECT 1 FROM moderation.media_reports r
                    WHERE r.refuge_id = m.refuge_id AND r.media_key = m.key
                      AND r.status = 'pending' AND r.reporter_uid = %(uid)s)
   AND NOT EXISTS (SELECT 1 FROM moderation.media_reports r
                    WHERE r.refuge_id = m.refuge_id AND r.media_key = m.key AND r.status = 'pending'
                      AND (r.reporter_uid IS DISTINCT FROM %(uid)s OR r.legal_hold))
ON CONFLICT DO NOTHING
"""


def _collect_r2_keys(uid: str) -> list:
    """
    Claus d'R2 que cal esborrar (D22, D38, D42): avatar i miniatura, mitjans propis, mitjans de les seves experiències
    (encara que els hagi pujat un altre) i `quarantine/` dels intents no confirmats (`pending` i `failed`). Mai
    `moderation-hold/`. Nombre constant de consultes.
    """
    keys = []
    for key, thumb in UserAvatar.objects.filter(user_id=uid).values_list('key', 'thumb_key'):
        keys += [key, thumb]
    with system_context():        # els mitjans amagats d'un altre a les seves experiències no són visibles per a ell
        # Dues consultes amb índex (`refuge_media_creator_idx` i `refuge_media_experience_idx`) en lloc d'una amb `OR`
        # entre columna i subconsulta, que feia un *seq scan* de `refuge_media` (EXPLAIN verificat).
        own = RefugeMedia.objects.filter(creator_id=uid)
        in_own_experiences = RefugeMedia.objects.filter(
            experience_id__in=Experience.objects.filter(creator_id=uid).values('id'))
        for queryset in (own, in_own_experiences):
            for key, thumb in queryset.values_list('key', 'thumb_key'):
                keys += [key, thumb]
    keys += list(UploadIntent.objects.filter(user_id=uid).exclude(status=UploadStatus.CONFIRMED)
                 .values_list('quarantine_key', flat=True))
    return [k for k in dict.fromkeys(keys) if k]


def _delete_r2_keys(keys: list, media_service=None) -> None:
    """Esborra les claus a R2; qualsevol fallada és `UserDeletionError` (fa desfer la transacció)."""
    if not keys:
        return
    service = media_service or r2_media_service.get_refugi_media_service()
    try:
        result = service.delete_files(keys)
    except Exception as exc:
        raise UserDeletionError("R2 ha fallat en esborrar els fitxers de l'usuari") from exc
    if result.get('failed'):
        logger.error("R2: %d fitxers de l'usuari no s'han pogut esborrar", len(result['failed']))
        raise UserDeletionError("R2 no ha esborrat tots els fitxers de l'usuari")


DEADLOCK_SQLSTATE = '40P01'
DELETE_DEADLOCK_RETRIES = 2


def _delete_user_data(uid: str, media_service=None) -> bool:
    """Transacció única de l'esborrat (§8.4). `False` si l'usuari no té fila (res a fer)."""
    with rls_context(uid):
        # 1. Bloqueig de la fila: impedeix contingut nou durant l'esborrat (les FK hi prenen `KEY SHARE`).
        if not UserAccount.objects.select_for_update().filter(pk=uid).exists():
            return False
        keys = _collect_r2_keys(uid)                                                    # 2
        renovation_services.delete_current_by_creator(uid)                              # 3
        with system_context():
            with connection.cursor() as cur:                                            # 4
                cur.execute(_AUTO_REPORTS_SQL, {'uid': uid})
            # 5. El `comment` (text lliure, pot dur dades personals); la FK `SET NULL` anonimitza la resta.
            RefugeProposal.objects.filter(creator_id=uid).update(comment=None)
        UserAccount.objects.filter(pk=uid).delete()                                     # 6
        audit.audit_log_service.log(None, audit.ACTION_USER_DELETED)                    # 7: cap identificador
        # 8. Les FK i els *constraint triggers* diferits s'avaluen ara: un error de BD ha de sortir abans d'esborrar a
        # R2 (no al COMMIT, amb els fitxers ja perduts). Només una fallada del propi COMMIT deixa R2 buit amb la fila;
        # el reintent és idempotent (esborrar claus inexistents a R2 no falla).
        with connection.cursor() as cur:
            cur.execute('SET CONSTRAINTS ALL IMMEDIATE')
        _delete_r2_keys(keys, media_service)                                            # 9: l'últim pas
    return True


def delete_user(uid: str, media_service=None) -> None:
    """
    Procediment únic d'esborrat d'usuari (D42, §8.4): una transacció pròpia (amb el seu context de RLS) amb el bloqueig
    de la fila, la recollida de claus, reformes vigents, denúncies automàtiques, `comment` de propostes, R2, `DELETE`
    i auditoria; i **després del COMMIT**, Firebase Auth (`UserNotFoundError` = èxit).

    Sense fila a `users.users` salta directament a Firebase (idempotent, sense R2 ni auditoria). Si R2 falla,
    `UserDeletionError` i tot desfet; si falla Firebase, `UserDeletionError` amb les dades ja esborrades: es pot
    tornar a cridar mentre el compte existeixi. Per tenir un COMMIT real, la vista és `non_atomic_requests`.
    """
    for attempt in range(DELETE_DEADLOCK_RETRIES + 1):
        try:
            _delete_user_data(uid, media_service)
            break
        except OperationalError as exc:
            # Un `DELETE` pot creuar-se amb un flux de moderació que bloqueja primer el mitjà i després l'usuari
            # (`media_creator_uid`); Postgres tria una víctima. La transacció s'ha desfet sencera: es reintenta.
            if getattr(exc.__cause__, 'sqlstate', None) != DEADLOCK_SQLSTATE or attempt == DELETE_DEADLOCK_RETRIES:
                raise
            logger.warning("Esborrat d'usuari: deadlock, reintent %d", attempt + 1)
    _delete_firebase_account(uid)
