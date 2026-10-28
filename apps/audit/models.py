"""
Model d'`audit` (schema `audit`), docs/design/postgres-schema.md §2.24, §3, §6.3.

`AuditLog` és el registre d'accés i accions (art. 32 RGPD / DSA). Només s'hi escriu (cap endpoint el llegeix) i és
**immutable**: el rol `app` no té `UPDATE`. Les FK són `DO_NOTHING` + `db_constraint=False`: les restriccions reals
(`ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED`), la RLS i els grants són a la migració. Les files `legal_hold` (CSAM)
no cauen amb l'usuari: el *trigger* `users_detach_legal_hold` (`moderation.0001`) les desvincula.
"""
from datetime import timedelta

from django.db import models
from django.db.models import F, Func, Q, UUIDField, Value

from apps.accounts.models import UserAccount
from apps.core.db_functions import TransactionNow

# `DEFAULT uuidv7()` de Postgres 18: l'únic generador d'ID.
UUIDV7 = Func(function='uuidv7', output_field=UUIDField())

RETENTION = timedelta(days=365)


class AuditLog(models.Model):
    """`audit.audit_logs`: `actor_uid` NULL = sistema; `subject_uid` = usuari sobre el qual es fa l'acció."""

    id = models.UUIDField(primary_key=True, db_default=UUIDV7, editable=False)
    actor = models.ForeignKey(
        UserAccount, null=True, blank=True, on_delete=models.DO_NOTHING, db_constraint=False, db_index=False,
        db_column='actor_uid', related_name='+')
    subject = models.ForeignKey(
        UserAccount, null=True, blank=True, on_delete=models.DO_NOTHING, db_constraint=False, db_index=False,
        db_column='subject_uid', related_name='+')
    action = models.CharField(max_length=48)
    target_type = models.CharField(max_length=32, null=True, blank=True)
    target_id = models.CharField(max_length=500, null=True, blank=True)
    metadata = models.JSONField(db_default=Value({}, output_field=models.JSONField()))
    created_at = models.DateTimeField(db_default=TransactionNow())
    expire_at = models.DateTimeField(db_default=TransactionNow() + RETENTION)
    legal_hold = models.BooleanField(db_default=False)

    class Meta:
        db_table = 'audit"."audit_logs'
        constraints = [
            # format, no llista tancada: afegir una acció no ha de requerir migració (§2.24)
            models.CheckConstraint(condition=Q(action__regex=r'^[a-z_]+\.[a-z_]+$'), name='audit_logs_action_ck'),
            models.CheckConstraint(condition=Q(expire_at__gt=F('created_at')), name='audit_logs_expire_ck'),
            # `audit_logs_metadata_ck` (objecte < 16 KiB) és a la migració (SQL pla)
        ]
        indexes = [
            models.Index(fields=['expire_at'], name='audit_logs_expire_idx', condition=Q(legal_hold=False)),
            models.Index(fields=['actor', '-created_at'], name='audit_logs_actor_idx'),
            models.Index(fields=['subject'], name='audit_logs_subject_idx', condition=Q(subject__isnull=False)),
        ]

    def __str__(self):
        return f'AuditLog {self.pk} {self.action}'
