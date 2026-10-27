"""
Model de `experiences` (schema `activity`), docs/design/postgres-schema.md §2.15, §2.9, §6.3.

- La PK és un `uuid` v7 generat per la BD (`DEFAULT uuidv7()`); `created_at` i `modified_at` són el `now()` de la
  transacció (`TransactionNow`).
- Les FK són `DO_NOTHING` + `db_constraint=False`: la restricció real (`ON DELETE CASCADE`) la crea la migració per
  `RunSQL`. Els mitjans d'una experiència són `refuges.refuge_media.experience_id` (FK de `refuges.0002`).
- `condition` (0-3) és obligatòria i alimenta la mitjana del refugi pels *triggers* `SECURITY DEFINER` de la migració
  (§2.9): l'aplicació no calcula mai la mitjana. `condition_counted_at` també el posa el *trigger*.
"""
from django.db import models
from django.db.models import F, Func, IntegerField, Q, TextField, UUIDField, Value
from django.db.models.lookups import Exact, LessThanOrEqual

from apps.accounts.models import UserAccount
from apps.core.db_functions import TransactionNow
from apps.refuges.models import Refuge

# `DEFAULT uuidv7()` de Postgres 18: l'únic generador d'ID.
UUIDV7 = Func(function='uuidv7', output_field=UUIDField())

COMMENT_MAX_LENGTH = 2000
CONDITION_MIN, CONDITION_MAX = 0, 3
# Espais en blanc que `btrim` retalla al CHECK (per defecte només treu espais: «\n\t» passaria com a comentari).
BLANK_CHARS = ' \t\n\r\f\v'


def _comment_check():
    """`btrim(comment, <blancs>) <> '' AND char_length(comment) <= 2000` (mateixa regla al DDL i al serializer)."""
    trimmed = Func(F('comment'), Value(BLANK_CHARS), function='btrim', output_field=TextField())
    length = Func(F('comment'), function='char_length', output_field=IntegerField())
    return ~Exact(trimmed, Value('')) & LessThanOrEqual(length, Value(COMMENT_MAX_LENGTH))


class Experience(models.Model):
    """`activity.experiences`: valoració i comentari d'un usuari sobre un refugi (lectura pública; RLS per creador)."""

    id = models.UUIDField(primary_key=True, db_default=UUIDV7, editable=False)
    refuge = models.ForeignKey(
        Refuge, on_delete=models.DO_NOTHING, db_constraint=False, db_index=False, db_column='refuge_id',
        related_name='+')
    creator = models.ForeignKey(
        UserAccount, on_delete=models.DO_NOTHING, db_constraint=False, db_index=False, db_column='creator_uid',
        related_name='+')
    comment = models.TextField()
    created_at = models.DateTimeField(db_default=TransactionNow())
    modified_at = models.DateTimeField(db_default=TransactionNow())
    condition = models.SmallIntegerField()
    condition_counted_at = models.DateTimeField(db_default=TransactionNow())      # el reescriu el trigger (§2.9)

    class Meta:
        db_table = 'activity"."experiences'
        constraints = [
            models.CheckConstraint(condition=_comment_check(), name='experiences_comment_ck'),
            models.CheckConstraint(condition=Q(condition__gte=CONDITION_MIN, condition__lte=CONDITION_MAX),
                                   name='experiences_condition_ck'),
        ]
        indexes = [
            models.Index(fields=['refuge', '-modified_at', '-id'], name='experiences_refuge_idx'),   # llista + FK
            models.Index(fields=['creator', '-modified_at'], name='experiences_creator_idx'),       # recompte + FK
        ]

    def __str__(self):
        return f'Experience {self.pk}'
