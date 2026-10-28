"""
Model de `proposals` (schema `proposals`), docs/design/postgres-schema.md §2.18, §6.3.

- La PK és un `uuid` v7 generat per la BD (`DEFAULT uuidv7()`); `created_at` és el `now()` de la transacció
  (`TransactionNow`).
- Les FK són `DO_NOTHING` + `db_constraint=False`: la restricció real (`ON DELETE SET NULL`) la crea la migració per
  `RunSQL`. Una proposta sobreviu a l'esborrat del refugi i dels usuaris (historial); el seu `comment` es posa a `NULL`
  en esborrar el creador (decisió del PO, RGPD; `apps.accounts.services.delete_user`).
- `payload` i `refuge_snapshot` són `jsonb`: el payload només porta els camps enviats («absent» i `null` són coses
  diferents en un `update`) i la foto és una còpia històrica immutable del refugi en forma d'API.
- Els `CHECK` simples són a `Meta.constraints`; els que usen operadors de `jsonb` (`-`, `?`, `?&`) i la mida
  (`pg_column_size`) només els sap crear la migració per `RunSQL`.
"""
from django.db import models
from django.db.models import F, Func, IntegerField, Q, UUIDField
from django.db.models.lookups import LessThanOrEqual

from apps.accounts.models import UserAccount
from apps.core.db_functions import TransactionNow
from apps.refuges.models import Refuge

# `DEFAULT uuidv7()` de Postgres 18: l'únic generador d'ID.
UUIDV7 = Func(function='uuidv7', output_field=UUIDField())

COMMENT_MAX_LENGTH = 4000
REASON_MAX_LENGTH = 2000


class Action(models.TextChoices):
    CREATE = 'create'
    UPDATE = 'update'
    DELETE = 'delete'


class Status(models.TextChoices):
    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'


def _max_length(field, limit):
    """`field IS NULL OR char_length(field) <= limit` (mateixa regla al DDL i al serializer)."""
    length = Func(F(field), function='char_length', output_field=IntegerField())
    return Q(**{f'{field}__isnull': True}) | Q(LessThanOrEqual(length, limit))


class RefugeProposal(models.Model):
    """`proposals.refuge_proposals`: proposta de crear, canviar o esborrar un refugi; la revisa un admin."""

    id = models.UUIDField(primary_key=True, db_default=UUIDV7, editable=False)
    refuge = models.ForeignKey(
        Refuge, null=True, blank=True, on_delete=models.DO_NOTHING, db_constraint=False, db_index=False,
        db_column='refuge_id', related_name='+')
    action = models.CharField(max_length=6, choices=Action.choices)
    status = models.CharField(max_length=8, choices=Status.choices, db_default=Status.PENDING)
    payload = models.JSONField(null=True, blank=True)
    refuge_snapshot = models.JSONField(null=True, blank=True)
    comment = models.TextField(null=True, blank=True)
    creator = models.ForeignKey(
        UserAccount, null=True, blank=True, on_delete=models.DO_NOTHING, db_constraint=False, db_index=False,
        db_column='creator_uid', related_name='+')
    created_at = models.DateTimeField(db_default=TransactionNow())
    reviewer = models.ForeignKey(
        UserAccount, null=True, blank=True, on_delete=models.DO_NOTHING, db_constraint=False, db_index=False,
        db_column='reviewer_uid', related_name='+')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'proposals"."refuge_proposals'
        constraints = [
            models.CheckConstraint(condition=Q(action__in=Action.values), name='refuge_proposals_action_ck'),
            models.CheckConstraint(condition=Q(status__in=Status.values), name='refuge_proposals_status_ck'),
            models.CheckConstraint(condition=_max_length('comment', COMMENT_MAX_LENGTH),
                                   name='refuge_proposals_comment_ck'),
            models.CheckConstraint(condition=_max_length('rejection_reason', REASON_MAX_LENGTH),
                                   name='refuge_proposals_reason_ck'),
            # Els altres 5 `CHECK` (forma per acció, `refuge_id`, revisió, claus del payload, `coord` i mida) són de
            # la migració (`RunSQL`): usen operadors de `jsonb` que l'ORM no expressa.
        ]
        indexes = [
            models.Index(fields=['-created_at', '-id'], name='proposals_pending_idx',
                         condition=Q(status='pending')),                                  # cua de l'admin
            models.Index(fields=['status', '-created_at', '-id'], name='proposals_status_idx'),
            models.Index(fields=['creator', '-created_at', '-id'], name='proposals_creator_idx'),   # les meves + FK
            models.Index(fields=['refuge', 'status'], name='proposals_refuge_idx'),        # pendents d'un refugi + FK
            models.Index(fields=['reviewer'], name='proposals_reviewer_idx', condition=Q(reviewer__isnull=False)),
        ]

    def __str__(self):
        return f'RefugeProposal {self.pk}'
