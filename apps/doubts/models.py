"""
Models de `doubts` (schema `activity`), docs/design/postgres-schema.md §2.16-2.17, §6.3.

- Les PK són `uuid` v7 generats per la BD (`DEFAULT uuidv7()`); `created_at` és el `now()` de la transacció
  (`TransactionNow`, GOTCHAS #53), de manera que l'ordre `(created_at, id)` coincideix amb el del DDL.
- Les FK són `DO_NOTHING` + `db_constraint=False`: la restricció real (`ON DELETE CASCADE`) la crea la migració per
  `RunSQL`. Això inclou la FK composta `(doubt_id, parent_answer_id) -> answers (doubt_id, id)`, que Django 5.2 no
  sap expressar: `parent_answer` és una FK simple sense restricció i garanteix a la BD que el pare existeix i és del
  mateix dubte; en esborrar una resposta s'esborra tot el seu subarbre.
- `answers_count` no es desa (§4): es calcula amb `Count('answers')` (`selectors.list_doubts`).
"""
from django.db import models
from django.db.models import F, Func, IntegerField, Q, TextField, UUIDField, Value
from django.db.models.lookups import Exact, LessThanOrEqual

from apps.accounts.models import UserAccount
from apps.core.db_functions import TransactionNow
from apps.refuges.models import Refuge

# `DEFAULT uuidv7()` de Postgres 18: l'únic generador d'ID.
UUIDV7 = Func(function='uuidv7', output_field=UUIDField())

MESSAGE_MAX_LENGTH = 2000
# Espais en blanc que `btrim` retalla al CHECK (per defecte només treu espais: «\n\t» passaria com a missatge).
BLANK_CHARS = ' \t\n\r\f\v'


def _message_check():
    """`btrim(message, <blancs>) <> '' AND char_length(message) <= 2000` (mateixa regla al DDL i al serializer)."""
    trimmed = Func(F('message'), Value(BLANK_CHARS), function='btrim', output_field=TextField())
    length = Func(F('message'), function='char_length', output_field=IntegerField())
    return ~Exact(trimmed, Value('')) & LessThanOrEqual(length, Value(MESSAGE_MAX_LENGTH))


class Doubt(models.Model):
    """`activity.doubts`: pregunta d'un usuari sobre un refugi (lectura pública; escriptura/esborrat del creador)."""

    id = models.UUIDField(primary_key=True, db_default=UUIDV7, editable=False)
    refuge = models.ForeignKey(
        Refuge, on_delete=models.DO_NOTHING, db_constraint=False, db_index=False, db_column='refuge_id',
        related_name='+')
    creator = models.ForeignKey(
        UserAccount, on_delete=models.DO_NOTHING, db_constraint=False, db_index=False, db_column='creator_uid',
        related_name='+')
    message = models.TextField()
    created_at = models.DateTimeField(db_default=TransactionNow())

    class Meta:
        db_table = 'activity"."doubts'
        constraints = [models.CheckConstraint(condition=_message_check(), name='doubts_message_ck')]
        indexes = [
            models.Index(fields=['refuge', '-created_at', '-id'], name='doubts_refuge_idx'),     # llista (keyset) + FK
            models.Index(fields=['creator'], name='doubts_creator_idx'),                          # FK / esborrat d'usuari
        ]

    def __str__(self):
        return f'Doubt {self.pk}'


class Answer(models.Model):
    """`activity.answers`: resposta a un dubte; arbre pla per `parent_answer_id` (`NULL` = resposta directa)."""

    id = models.UUIDField(primary_key=True, db_default=UUIDV7, editable=False)
    doubt = models.ForeignKey(
        Doubt, on_delete=models.DO_NOTHING, db_constraint=False, db_index=False, db_column='doubt_id',
        related_name='answers')
    creator = models.ForeignKey(
        UserAccount, on_delete=models.DO_NOTHING, db_constraint=False, db_index=False, db_column='creator_uid',
        related_name='+')
    parent_answer = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.DO_NOTHING, db_constraint=False, db_index=False,
        db_column='parent_answer_id', related_name='replies')
    message = models.TextField()
    created_at = models.DateTimeField(db_default=TransactionNow())

    class Meta:
        db_table = 'activity"."answers'
        constraints = [
            models.CheckConstraint(condition=_message_check(), name='answers_message_ck'),
            models.CheckConstraint(condition=Q(parent_answer__isnull=True) | ~Q(parent_answer=F('id')),
                                   name='answers_not_self_parent_ck'),
            # Objectiu de la FK composta `answers_parent_same_doubt_fk` (RunSQL de la migració).
            models.UniqueConstraint(fields=['doubt', 'id'], name='answers_doubt_id_uq'),
        ]
        indexes = [
            models.Index(fields=['doubt', 'created_at', 'id'], name='answers_doubt_created_idx'),   # llista + recompte
            models.Index(fields=['doubt', 'parent_answer'], name='answers_doubt_parent_idx'),      # cascada de la FK composta
            models.Index(fields=['creator'], name='answers_creator_idx'),                           # FK / esborrat d'usuari
        ]

    def __str__(self):
        return f'Answer {self.pk}'
