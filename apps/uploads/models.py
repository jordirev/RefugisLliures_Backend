"""
Model de `uploads` (schema `moderation`), docs/design/postgres-schema.md §2.19, §3, §6.3.

Un `UploadIntent` és un intent de pujada directa: l'usuari rep una URL PUT prefirmada a `quarantine/{id}` i, un cop
pujat el fitxer, el confirma. Té un TTL funcional d'1 dia (`expire_at`; purga amb `purge_upload_intents`).

- La PK és un `uuid` v7 generat per la BD i és l'`upload_id` de l'API; `created_at` i `expire_at` són el `now()` de la
  transacció (`expire_at = created_at + 1 dia`, durada real).
- Les FK són `DO_NOTHING` + `db_constraint=False`: la restricció real (`ON DELETE CASCADE`) la crea la migració per
  `RunSQL`. Les enumeracions i la forma segons el `target` són `CHECK` (mateixa regla que el serializer).
"""
from datetime import timedelta

from django.db import models
from django.db.models import F, Func, Q, UUIDField

from apps.accounts.models import UserAccount
from apps.core.db_functions import TransactionNow
from apps.experiences.models import Experience
from apps.refuges.models import Refuge

# `DEFAULT uuidv7()` de Postgres 18: l'únic generador d'ID.
UUIDV7 = Func(function='uuidv7', output_field=UUIDField())

RETENTION = timedelta(days=1)       # el mateix que el lifecycle de `quarantine/` a R2


class UploadTarget(models.TextChoices):
    REFUGE = 'refuge'
    EXPERIENCE = 'experience'
    AVATAR = 'avatar'


class UploadStatus(models.TextChoices):
    PENDING = 'pending'
    CONFIRMED = 'confirmed'
    FAILED = 'failed'


class UploadFailureReason(models.TextChoices):
    MISSING_OBJECT = 'missing_object'
    TOO_LARGE = 'too_large'
    INVALID_TYPE = 'invalid_type'
    PROCESSING_ERROR = 'processing_error'
    MODERATION_BLOCKED = 'moderation_blocked'


def _shape_check():
    """avatar: sense refugi ni experiència · refuge: refugi · experience: refugi i experiència."""
    no_refuge, no_experience = Q(refuge__isnull=True), Q(experience__isnull=True)
    return (
        (Q(target=UploadTarget.AVATAR) & no_refuge & no_experience)
        | (Q(target=UploadTarget.REFUGE) & Q(refuge__isnull=False) & no_experience)
        | (Q(target=UploadTarget.EXPERIENCE) & Q(refuge__isnull=False) & Q(experience__isnull=False)))


def _state_check():
    """`confirmed` <=> `result_key` i `failed` <=> `failure_reason`."""
    confirmed, failed = Q(status=UploadStatus.CONFIRMED), Q(status=UploadStatus.FAILED)
    return (
        ((confirmed & Q(result_key__isnull=False)) | (~confirmed & Q(result_key__isnull=True)))
        & ((failed & Q(failure_reason__isnull=False)) | (~failed & Q(failure_reason__isnull=True))))


class UploadIntent(models.Model):
    """`moderation.upload_intents`: privat (només el propietari i el sistema hi accedeixen, RLS)."""

    id = models.UUIDField(primary_key=True, db_default=UUIDV7, editable=False)
    user = models.ForeignKey(
        UserAccount, on_delete=models.DO_NOTHING, db_constraint=False, db_index=False, db_column='user_uid',
        related_name='+')
    target = models.CharField(max_length=10, choices=UploadTarget.choices)
    content_type = models.CharField(max_length=100)
    size = models.BigIntegerField()
    quarantine_key = models.TextField(unique=True)
    refuge = models.ForeignKey(
        Refuge, null=True, blank=True, on_delete=models.DO_NOTHING, db_constraint=False, db_index=False,
        db_column='refuge_id', related_name='+')
    experience = models.ForeignKey(
        Experience, null=True, blank=True, on_delete=models.DO_NOTHING, db_constraint=False, db_index=False,
        db_column='experience_id', related_name='+')
    status = models.CharField(max_length=9, choices=UploadStatus.choices, db_default=UploadStatus.PENDING)
    rights_confirmed_at = models.DateTimeField()
    created_at = models.DateTimeField(db_default=TransactionNow())
    expire_at = models.DateTimeField(db_default=TransactionNow() + RETENTION)
    result_key = models.TextField(null=True, blank=True)
    failure_reason = models.CharField(max_length=24, null=True, blank=True, choices=UploadFailureReason.choices)

    class Meta:
        db_table = 'moderation"."upload_intents'
        constraints = [
            models.CheckConstraint(condition=Q(target__in=UploadTarget.values), name='upload_intents_target_ck'),
            models.CheckConstraint(condition=Q(status__in=UploadStatus.values), name='upload_intents_status_ck'),
            models.CheckConstraint(
                condition=Q(failure_reason__isnull=True) | Q(failure_reason__in=UploadFailureReason.values),
                name='upload_intents_failure_reason_ck'),
            models.CheckConstraint(condition=Q(size__gt=0), name='upload_intents_size_ck'),
            models.CheckConstraint(condition=_shape_check(), name='upload_intents_shape_ck'),
            models.CheckConstraint(condition=_state_check(), name='upload_intents_state_ck'),
            models.CheckConstraint(condition=Q(expire_at__gt=F('created_at')), name='upload_intents_expire_ck'),
        ]
        indexes = [
            models.Index(fields=['expire_at'], name='upload_intents_expire_idx'),                     # purga
            models.Index(fields=['user', '-created_at'], name='upload_intents_user_idx'),            # FK + intents propis
            models.Index(fields=['refuge'], name='upload_intents_refuge_idx', condition=Q(refuge__isnull=False)),
            models.Index(fields=['experience'], name='upload_intents_experience_idx',
                         condition=Q(experience__isnull=False)),
        ]

    def __str__(self):
        return f'UploadIntent {self.pk}'
