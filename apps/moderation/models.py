"""
Models de `moderation` (schema `moderation`), docs/design/postgres-schema.md §2.20–§2.22, §3, §6.3.

- `MediaReport` (`media_reports`): denúncia d'un mitjà (DSA art. 16). L'`id` és un UUID v7 opac; la unicitat «una
  denúncia per (refugi, mitjà, denunciant)» és una restricció (`UNIQUE`), no un id determinista.
- `ModerationNotice` (`moderation_notices`): declaració de motius adreçada a un usuari (DSA art. 17). Immutable.
- `HashBlocklistEntry` (`moderation_hash_blocklist`): hashes prohibits (CSAM). **L'aplicació no la llegeix ni l'escriu**
  (el rol `app` no hi té cap privilegi): només `moderation.fn_hash_match`; s'alimenta amb `load_hash_blocklist`.

Les FK són `DO_NOTHING` + `db_constraint=False`: les restriccions reals (`ON DELETE`), la RLS, els grants, la funció i els
*triggers* són a la migració per `RunSQL`. Les enumeracions són `CHECK` amb el seu `TextChoices`.
"""
from django.db import models
from django.db.models import F, Func, IntegerField, Q, TextField, UUIDField, Value
from django.db.models.lookups import Exact, GreaterThanOrEqual, LessThanOrEqual

from apps.accounts.models import UserAccount
from apps.core.db_functions import TransactionNow
from apps.refuges.models import Refuge

from .fields import FixedCharField

# `DEFAULT uuidv7()` de Postgres 18: l'únic generador d'ID.
UUIDV7 = Func(function='uuidv7', output_field=UUIDField())

REPORT_DETAILS_MAX_LENGTH = 1000
REPORT_STATEMENT_MAX_LENGTH = 2000
# Blancs que `btrim` retalla al CHECK (D31/D34: per defecte només treu espais).
BLANK_CHARS = ' \t\n\r\f\v'

# Nombre de denunciants diferents a partir del qual s'oculta el mitjà per als motius no greus.
AUTO_HIDE_DISTINCT_REPORTERS = 3


class ReportReason(models.TextChoices):
    """Motius (contracte d'API). Ordre = ordre de presentació a l'app."""
    CHILD_SEXUAL_ABUSE = 'child_sexual_abuse'            # Abús o explotació sexual de menors
    CHILD_ENDANGERMENT = 'child_endangerment'            # Menors en situació de risc
    SEXUAL_NONCONSENSUAL = 'sexual_nonconsensual'        # Nuesa o contingut sexual no consentit
    VIOLENCE_GORE = 'violence_gore'                      # Violència explícita o contingut sagnant
    TERRORISM_EXTREMISM = 'terrorism_extremism'          # Terrorisme o extremisme violent
    HATE_SPEECH = 'hate_speech'                          # Odi o discriminació
    HARASSMENT_BULLYING = 'harassment_bullying'          # Assetjament o intimidació
    ANIMAL_CRUELTY = 'animal_cruelty'                    # Maltractament animal
    SELF_HARM = 'self_harm'                              # Suïcidi o autolesions
    ILLEGAL_GOODS = 'illegal_goods'                      # Drogues, armes o activitats il·legals
    MY_IMAGE = 'my_image'                                # Hi surto jo sense el meu consentiment
    PRIVACY_PERSONAL_DATA = 'privacy_personal_data'      # Dades personals d'altres
    INTELLECTUAL_PROPERTY = 'intellectual_property'      # Drets d'autor o marca
    FRAUD_SCAM_SPAM = 'fraud_scam_spam'                  # Frau, estafa, spam o publicitat
    MISLEADING_IRRELEVANT = 'misleading_irrelevant'      # Falsa o no correspon a aquest refugi
    OTHER = 'other'                                      # Altres (cal descripció)


# Motius que oculten el mitjà immediatament i tenen prioritat alta.
AUTO_HIDE_REASONS = frozenset({
    ReportReason.CHILD_SEXUAL_ABUSE.value, ReportReason.CHILD_ENDANGERMENT.value,
    ReportReason.SEXUAL_NONCONSENSUAL.value, ReportReason.TERRORISM_EXTREMISM.value, ReportReason.MY_IMAGE.value})
CSAM_REASON = ReportReason.CHILD_SEXUAL_ABUSE.value


class ReportStatus(models.TextChoices):
    PENDING = 'pending'
    RESOLVED = 'resolved'


class ReportPriority(models.TextChoices):
    HIGH = 'high'
    NORMAL = 'normal'


class ReportAction(models.TextChoices):
    DISMISS = 'dismiss'
    REMOVE = 'remove'
    REMOVE_AND_STRIKE = 'remove_and_strike'


class ReportSource(models.TextChoices):
    USER = 'user'
    AUTOMATIC = 'automatic'


class NoticeType(models.TextChoices):
    CONTENT_HIDDEN = 'content_hidden'
    CONTENT_RESTORED = 'content_restored'
    CONTENT_REMOVED = 'content_removed'
    STRIKE = 'strike'
    ACCOUNT_BLOCKED = 'account_blocked'
    UPLOAD_BLOCKED = 'upload_blocked'


class NoticeAction(models.TextChoices):
    DISMISS = 'dismiss'
    REMOVE = 'remove'
    REMOVE_AND_STRIKE = 'remove_and_strike'
    AUTO_HIDE = 'auto_hide'
    UPLOAD_BLOCKED = 'upload_blocked'


class HashCategory(models.TextChoices):
    CSAM = 'csam'
    OTHER = 'other'


def _btrim(column):
    return Func(F(column), Value(BLANK_CHARS), function='btrim', output_field=TextField())


def _char_length(column):
    return Func(F(column), function='char_length', output_field=IntegerField())


class MediaReport(models.Model):
    """`moderation.media_reports`: privada (denunciant + admin, RLS)."""

    id = models.UUIDField(primary_key=True, db_default=UUIDV7, editable=False)
    # `NULL` quan una denúncia `legal_hold` sobreviu a l'esborrat del refugi (trigger `refuges_detach_legal_hold`).
    refuge = models.ForeignKey(
        Refuge, null=True, blank=True, on_delete=models.DO_NOTHING, db_constraint=False, db_index=False,
        db_column='refuge_id', related_name='+')
    media_key = models.CharField(max_length=500)                       # sense FK: pot ser `moderation-hold/...`
    # `NULL` ⇔ automàtica o `legal_hold` anonimitzada en esborrar el denunciant (`anonymized_at`).
    reporter = models.ForeignKey(
        UserAccount, null=True, blank=True, on_delete=models.DO_NOTHING, db_constraint=False, db_index=False,
        db_column='reporter_uid', related_name='+')
    reason = models.CharField(max_length=32, choices=ReportReason.choices)
    details = models.TextField(null=True, blank=True)
    media_creator = models.ForeignKey(
        UserAccount, null=True, blank=True, on_delete=models.DO_NOTHING, db_constraint=False, db_index=False,
        db_column='media_creator_uid', related_name='+')
    status = models.CharField(max_length=8, choices=ReportStatus.choices, db_default=ReportStatus.PENDING)
    priority = models.CharField(max_length=6, choices=ReportPriority.choices, db_default=ReportPriority.NORMAL)
    created_at = models.DateTimeField(db_default=TransactionNow())
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        UserAccount, null=True, blank=True, on_delete=models.DO_NOTHING, db_constraint=False, db_index=False,
        db_column='resolved_by', related_name='+')
    action = models.CharField(max_length=20, null=True, blank=True, choices=ReportAction.choices)
    statement = models.TextField(null=True, blank=True)
    source = models.CharField(max_length=9, choices=ReportSource.choices, db_default=ReportSource.USER)
    legal_hold = models.BooleanField(db_default=False)
    anonymized_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'moderation"."media_reports'
        constraints = [
            models.CheckConstraint(condition=Q(reason__in=ReportReason.values), name='media_reports_reason_ck'),
            models.CheckConstraint(condition=Q(status__in=ReportStatus.values), name='media_reports_status_ck'),
            models.CheckConstraint(condition=Q(priority__in=ReportPriority.values), name='media_reports_priority_ck'),
            models.CheckConstraint(condition=Q(action__isnull=True) | Q(action__in=ReportAction.values),
                                   name='media_reports_action_ck'),
            models.CheckConstraint(condition=Q(source__in=ReportSource.values), name='media_reports_source_values_ck'),
            models.CheckConstraint(
                condition=~Q(reason=ReportReason.OTHER) | (Q(details__isnull=False) & ~Exact(_btrim('details'), Value(''))),
                name='media_reports_other_details_ck'),
            models.CheckConstraint(
                condition=Q(details__isnull=True) | LessThanOrEqual(_char_length('details'), Value(REPORT_DETAILS_MAX_LENGTH)),
                name='media_reports_details_len_ck'),
            models.CheckConstraint(
                condition=Q(statement__isnull=True)
                | LessThanOrEqual(_char_length('statement'), Value(REPORT_STATEMENT_MAX_LENGTH)),
                name='media_reports_statement_len_ck'),
            models.CheckConstraint(
                condition=(Q(source=ReportSource.USER) & (Q(reporter__isnull=False) | Q(anonymized_at__isnull=False)))
                | (Q(source=ReportSource.AUTOMATIC) & Q(reporter__isnull=True)),
                name='media_reports_source_ck'),
            models.CheckConstraint(condition=Q(anonymized_at__isnull=True) | Q(legal_hold=True),
                                   name='media_reports_hold_ck'),
            models.CheckConstraint(
                condition=(Q(status=ReportStatus.PENDING) & Q(resolved_at__isnull=True) & Q(resolved_by__isnull=True)
                           & Q(action__isnull=True) & Q(statement__isnull=True))
                | (Q(status=ReportStatus.RESOLVED) & Q(resolved_at__isnull=False) & Q(action__isnull=False)
                   & Q(statement__isnull=False)),
                name='media_reports_resolution_ck'),
            models.CheckConstraint(
                condition=Q(reporter__isnull=True) | Q(media_creator__isnull=True) | ~Q(reporter=F('media_creator')),
                name='media_reports_not_own_ck'),
            # Una denúncia per (refugi, mitjà, denunciant); el 409 `already_reported` surt d'aquesta restricció.
            models.UniqueConstraint(fields=['refuge', 'media_key', 'reporter'], condition=Q(reporter__isnull=False),
                                    name='media_reports_unique_reporter_uq'),
            # Una automàtica per mitjà (també amb `refuge_id` NULL: avatars).
            models.UniqueConstraint(fields=['refuge', 'media_key'], condition=Q(source=ReportSource.AUTOMATIC),
                                    nulls_distinct=False, name='media_reports_unique_auto_uq'),
        ]
        indexes = [
            models.Index(fields=['status', 'priority', 'created_at', 'id'], name='media_reports_list_idx'),
            models.Index(fields=['reporter'], name='media_reports_reporter_idx'),
            models.Index(fields=['media_creator'], name='media_reports_creator_idx',
                         condition=Q(media_creator__isnull=False)),
            models.Index(fields=['resolved_by'], name='media_reports_resolver_idx',
                         condition=Q(resolved_by__isnull=False)),
        ]

    def __str__(self):
        return f'MediaReport {self.pk}'


class ModerationNotice(models.Model):
    """`moderation.moderation_notices`: privada (l'afectat + admin). `redress` de l'API és un text constant."""

    id = models.UUIDField(primary_key=True, db_default=UUIDV7, editable=False)
    user = models.ForeignKey(
        UserAccount, on_delete=models.DO_NOTHING, db_constraint=False, db_index=False, db_column='user_uid',
        related_name='+')
    type = models.CharField(max_length=20, choices=NoticeType.choices)
    statement = models.TextField()
    created_at = models.DateTimeField(db_default=TransactionNow())
    refuge = models.ForeignKey(
        Refuge, null=True, blank=True, on_delete=models.DO_NOTHING, db_constraint=False, db_index=False,
        db_column='refuge_id', related_name='+')
    media_key = models.CharField(max_length=500, null=True, blank=True)
    reason = models.CharField(max_length=32, null=True, blank=True, choices=ReportReason.choices)
    action = models.CharField(max_length=20, null=True, blank=True, choices=NoticeAction.choices)
    report = models.ForeignKey(
        MediaReport, null=True, blank=True, on_delete=models.DO_NOTHING, db_constraint=False, db_index=False,
        db_column='report_id', related_name='+')
    automated = models.BooleanField(db_default=False)
    strikes = models.SmallIntegerField(null=True, blank=True)

    class Meta:
        db_table = 'moderation"."moderation_notices'
        constraints = [
            models.CheckConstraint(condition=Q(type__in=NoticeType.values), name='moderation_notices_type_ck'),
            models.CheckConstraint(condition=Q(action__isnull=True) | Q(action__in=NoticeAction.values),
                                   name='moderation_notices_action_ck'),
            models.CheckConstraint(condition=Q(reason__isnull=True) | Q(reason__in=ReportReason.values),
                                   name='moderation_notices_reason_ck'),
            models.CheckConstraint(condition=Q(strikes__isnull=True) | GreaterThanOrEqual(F('strikes'), Value(0)),
                                   name='moderation_notices_strikes_ck'),
        ]
        indexes = [
            models.Index(fields=['user', '-created_at', '-id'], name='moderation_notices_user_idx'),
            models.Index(fields=['report'], name='moderation_notices_report_idx', condition=Q(report__isnull=False)),
            models.Index(fields=['refuge'], name='moderation_notices_refuge_idx', condition=Q(refuge__isnull=False)),
        ]

    def __str__(self):
        return f'ModerationNotice {self.pk}'


class HashBlocklistEntry(models.Model):
    """`moderation.moderation_hash_blocklist`: il·legible per a `app` (només `moderation.fn_hash_match`)."""

    id = models.UUIDField(primary_key=True, db_default=UUIDV7, editable=False)
    sha256 = FixedCharField(max_length=64, null=True, blank=True)
    phash = models.BigIntegerField(null=True, blank=True)             # pHash de 64 bits com a enter amb signe
    category = models.CharField(max_length=16, choices=HashCategory.choices, db_default=HashCategory.CSAM)
    source = models.CharField(max_length=100)
    added_at = models.DateTimeField(db_default=TransactionNow())

    class Meta:
        db_table = 'moderation"."moderation_hash_blocklist'
        constraints = [
            models.CheckConstraint(condition=Q(sha256__isnull=True) | Q(sha256__regex=r'^[0-9a-f]{64}$'),
                                   name='moderation_hash_blocklist_sha256_ck'),
            models.CheckConstraint(condition=Q(category__in=HashCategory.values),
                                   name='moderation_hash_blocklist_category_ck'),
            models.CheckConstraint(condition=Q(sha256__isnull=False) | Q(phash__isnull=False),
                                   name='moderation_hash_blocklist_any_ck'),
            models.UniqueConstraint(fields=['sha256'], condition=Q(sha256__isnull=False),
                                    name='moderation_hash_blocklist_sha256_uq'),
        ]

    def __str__(self):
        return f'HashBlocklistEntry {self.pk}'
