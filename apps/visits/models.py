"""
Models de `visits` (schema `activity`; docs/design/postgres-schema.md §2.10, §2.11, §4.1, §6.3).

Una `RefugeVisit` és un `(refugi, dia)` únic; els visitants són files de `VisitParticipant` (privades per RLS). El total
de visitants **no es desa**: surt de la vista `refuge_visit_totals` (`VisitTotal`), que s'executa com a propietari i
per tant suma totes les files encara que la RLS només deixi veure la de l'usuari (§2.11: mai un `Sum` directe).

Les FK són `DO_NOTHING` + `db_constraint=False`: la restricció real (`ON DELETE CASCADE`), la RLS, els grants i la
vista són a la migració per `RunSQL` (§6.3).
"""
from django.db import models
from django.db.models import Func, Q

from apps.core.db_functions import TransactionNow

# `DEFAULT uuidv7()` de Postgres 18: l'únic generador d'ID (Django el recupera amb `RETURNING`).
UUIDV7 = Func(function='uuidv7', output_field=models.UUIDField())


class RefugeVisit(models.Model):
    """`activity.refuge_visits`: un refugi i un dia. Conserva `id` perquè hi apunta `refuge_visit_participants` (D18)."""

    id = models.UUIDField(primary_key=True, db_default=UUIDV7, editable=False)
    refuge = models.ForeignKey(
        'refuges.Refuge', on_delete=models.DO_NOTHING, db_constraint=False, db_index=False, db_column='refuge_id',
        related_name='+')
    visit_date = models.DateField()
    created_at = models.DateTimeField(db_default=TransactionNow())

    class Meta:
        db_table = 'activity"."refuge_visits'
        constraints = [
            # Fixa M4: «comprova i crea» és `INSERT ... ON CONFLICT (refuge_id, visit_date) DO NOTHING` + `SELECT`.
            models.UniqueConstraint(fields=['refuge', 'visit_date'], name='visits_refuge_date_uq'),
        ]
        indexes = [models.Index(fields=['visit_date'], name='visits_date_idx')]            # job diari (ahir, purga)

    def __str__(self):
        return f'{self.refuge_id} {self.visit_date}'


class VisitParticipant(models.Model):
    """`activity.refuge_visit_participants`: una fila per participant i visita; privada (només la pròpia, §2.11)."""

    pk = models.CompositePrimaryKey('visit', 'user')
    visit = models.ForeignKey(
        RefugeVisit, on_delete=models.DO_NOTHING, db_constraint=False, db_index=False, db_column='visit_id',
        related_name='+')
    user = models.ForeignKey(
        'accounts.UserAccount', on_delete=models.DO_NOTHING, db_constraint=False, db_index=False,
        db_column='user_uid', related_name='+')
    num_visitors = models.IntegerField()
    created_at = models.DateTimeField(db_default=TransactionNow())

    class Meta:
        db_table = 'activity"."refuge_visit_participants'
        constraints = [
            models.CheckConstraint(condition=Q(num_visitors__gte=1), name='participants_num_visitors_ck'),
        ]
        indexes = [
            # `GET /users/{uid}/visits/` i l'esborrat d'usuari (B5): sense recórrer la taula.
            models.Index(fields=['user'], include=['visit', 'num_visitors'], name='participants_user_idx'),
        ]

    def __str__(self):
        return f'{self.user_id} @ {self.visit_id}: {self.num_visitors}'


class VisitTotal(models.Model):
    """Vista `activity.refuge_visit_totals` (només lectura): `total_visitors` de cada visita amb participants."""

    visit = models.OneToOneField(
        RefugeVisit, primary_key=True, on_delete=models.DO_NOTHING, db_constraint=False, db_column='visit_id',
        related_name='totals')
    total_visitors = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'activity"."refuge_visit_totals'
