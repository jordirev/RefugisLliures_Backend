"""
Models de `renovations` (schema `activity`; docs/design/postgres-schema.md §2.12, §2.12.1, §2.13, §2.14, §6.4).

Les FK són `DO_NOTHING` + `db_constraint=False`: la restricció real (`ON DELETE CASCADE`/`SET NULL`), la RLS, els
grants i els *triggers* són a la migració per `RunSQL` (GOTCHAS #12). Els instants usen el rellotge de la BD.
"""
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateRangeField, RangeOperators
from django.db import models
from django.db.models import F, Func, Q, TextField, Value
from django.db.models.functions import Length
from django.db.models.lookups import Exact, LessThanOrEqual

from apps.core.db_functions import TransactionNow

# Mateixos caràcters que `btrim` de les altres apps: espais, tabuladors, salts de línia...
_BLANKS = ' \t\n\r\f\v'


class Renovation(models.Model):
    """
    `activity.renovations`. L'enllaç del grup viu a `RenovationGroupLink` (privat per RLS). `creator` és `NULL` quan
    s'ha esborrat el creador d'una reforma passada (l'API emet `'unknown'`). Rang de dates inclusiu als dos extrems.
    """

    id = models.UUIDField(primary_key=True, db_default=Func(function='uuidv7', output_field=models.UUIDField()),
                          editable=False)
    refuge = models.ForeignKey(
        'refuges.Refuge', on_delete=models.DO_NOTHING, db_constraint=False, db_index=False, db_column='refuge_id',
        related_name='+')
    creator = models.ForeignKey(
        'accounts.UserAccount', null=True, blank=True, on_delete=models.DO_NOTHING, db_constraint=False,
        db_index=False, db_column='creator_uid', related_name='+')
    ini_date = models.DateField()
    fin_date = models.DateField()
    description = models.TextField()
    materials_needed = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(db_default=TransactionNow())

    class Meta:
        db_table = 'activity"."renovations'
        constraints = [
            models.CheckConstraint(condition=Q(ini_date__lte=F('fin_date')), name='renovations_dates_ck'),
            models.CheckConstraint(
                condition=~Q(Exact(Func(F('description'), Value(_BLANKS), function='btrim', output_field=TextField()),
                                   Value(''))),
                name='renovations_description_ck'),
            ExclusionConstraint(
                name='renovations_no_overlap',
                expressions=[
                    ('refuge', RangeOperators.EQUAL),
                    (Func(F('ini_date'), F('fin_date'), Value('[]'), function='daterange',
                          output_field=DateRangeField()), RangeOperators.OVERLAPS),
                ]),
        ]
        indexes = [
            models.Index(fields=['refuge', 'fin_date', 'ini_date'], name='renovations_refuge_fin_idx'),
            models.Index(fields=['fin_date', 'ini_date'], name='renovations_fin_ini_idx'),
            models.Index(fields=['creator', 'fin_date'], condition=Q(creator__isnull=False),
                         name='renovations_creator_fin_idx'),
        ]

    def __str__(self):
        return f'{self.pk} ({self.ini_date}..{self.fin_date})'


class RenovationGroupLink(models.Model):
    """`activity.renovation_group_links` (§2.12.1): enllaç al grup, només per a creador, participants i admins."""

    renovation = models.OneToOneField(
        Renovation, primary_key=True, on_delete=models.DO_NOTHING, db_constraint=False, db_column='renovation_id',
        related_name='group_link_row')
    group_link = models.TextField()

    class Meta:
        db_table = 'activity"."renovation_group_links'
        constraints = [
            models.CheckConstraint(
                condition=Q(group_link__iregex=r'^https?://') & Q(LessThanOrEqual(Length('group_link'), 2048)),
                name='renovation_group_links_url_ck'),
        ]


class _RenovationMember(models.Model):
    """Base abstracta de participants i expulsats: PK composta `(renovation_id, user_uid)`, sense `id`."""

    pk = models.CompositePrimaryKey('renovation', 'user')
    renovation = models.ForeignKey(
        Renovation, on_delete=models.DO_NOTHING, db_constraint=False, db_index=False, db_column='renovation_id',
        related_name='+')
    user = models.ForeignKey(
        'accounts.UserAccount', on_delete=models.DO_NOTHING, db_constraint=False, db_index=False,
        db_column='user_uid', related_name='+')

    class Meta:
        abstract = True

    def __str__(self):
        return f'{self.renovation_id}: {self.user_id}'


class RenovationParticipant(_RenovationMember):
    """`activity.renovation_participants` (§2.13): qui s'ha unit a la reforma (ordre d'arribada = `created_at`)."""

    created_at = models.DateTimeField(db_default=TransactionNow())

    class Meta:
        db_table = 'activity"."renovation_participants'
        indexes = [models.Index(fields=['user', 'renovation'], name='rparts_user_reno_idx')]


class RenovationExpelled(_RenovationMember):
    """`activity.renovation_expelled` (§2.14): expulsió definitiva; mai s'exposa a l'API."""

    expelled_at = models.DateTimeField(db_default=TransactionNow())

    class Meta:
        db_table = 'activity"."renovation_expelled'
        indexes = [models.Index(fields=['user', 'renovation'], name='rexp_user_reno_idx')]
