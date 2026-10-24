"""
Models de `accounts` (schema `users`), només el mínim que necessita el chunk 2 (§2.1, §2.2, §6.2):
`refuge_media.creator_uid` apunta a `users.users`. Les llistes (`user_favourite_refuges`, `user_visited_refuges`)
i la resta de la feature arriben al chunk 3 (`accounts.0002`).

Les FK són `DO_NOTHING` + `db_constraint=False`: la restricció real (amb `ON DELETE`) la crea la migració per
`RunSQL` (§6.3). Les escriptures passen per la RLS del rol `app` (vegeu la migració).
"""
from django.db import models
from django.db.models import Q
from django.db.models.functions import Length, Now, Trim
from django.db.models.lookups import GreaterThanOrEqual


class UserAccount(models.Model):
    """`users.users`: dades privades i minimitzades (sense email ni data de naixement)."""

    class Language(models.TextChoices):
        CA = 'ca'
        ES = 'es'
        EN = 'en'
        FR = 'fr'

    uid = models.CharField(max_length=128, primary_key=True)          # UID de Firebase
    language = models.CharField(max_length=2, choices=Language.choices, db_default=Language.CA)
    created_at = models.DateTimeField(db_default=Now())
    age_confirmed_at = models.DateTimeField(null=True, blank=True)
    age_threshold = models.SmallIntegerField(null=True, blank=True)
    moderation_strikes = models.SmallIntegerField(db_default=0)
    is_blocked = models.BooleanField(db_default=False)
    blocked_reason = models.CharField(max_length=32, null=True, blank=True)
    blocked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'users"."users'
        constraints = [
            models.CheckConstraint(
                condition=Q(GreaterThanOrEqual(Length('uid'), 1)) & ~Q(uid__in=['system', 'unknown']),
                name='users_uid_ck'),
            models.CheckConstraint(condition=Q(language__in=['ca', 'es', 'en', 'fr']), name='users_language_ck'),
            models.CheckConstraint(
                condition=Q(age_confirmed_at__isnull=True, age_threshold__isnull=True)
                | Q(age_confirmed_at__isnull=False, age_threshold__isnull=False),
                name='users_age_pair_ck'),
            models.CheckConstraint(
                condition=Q(age_threshold__isnull=True) | Q(age_threshold__gte=13, age_threshold__lte=21),
                name='users_age_threshold_ck'),
            models.CheckConstraint(condition=Q(moderation_strikes__gte=0), name='users_strikes_ck'),
            models.CheckConstraint(
                condition=Q(is_blocked=True) | Q(blocked_reason__isnull=True, blocked_at__isnull=True),
                name='users_blocked_ck'),
            models.CheckConstraint(
                condition=Q(blocked_reason__isnull=True)
                | Q(blocked_reason__in=['csam_confirmed', 'strikes', 'moderation_hash_match']),
                name='users_blocked_reason_ck'),
        ]

    def __str__(self):
        return self.uid


class UserPublicProfile(models.Model):
    """`users.user_public_profiles`: 1-1 amb `users`, lectura oberta (nom d'usuari i avatar)."""

    user = models.OneToOneField(
        UserAccount, primary_key=True, on_delete=models.DO_NOTHING, db_constraint=False, db_column='uid',
        related_name='public_profile')
    username = models.CharField(max_length=255, db_default='', blank=True)
    avatar_key = models.TextField(null=True, blank=True)
    avatar_thumb_key = models.TextField(null=True, blank=True)
    avatar_content_type = models.CharField(max_length=100, null=True, blank=True)
    avatar_width = models.IntegerField(null=True, blank=True)
    avatar_height = models.IntegerField(null=True, blank=True)
    avatar_size_bytes = models.BigIntegerField(null=True, blank=True)
    avatar_blurhash = models.CharField(max_length=100, null=True, blank=True)
    avatar_uploaded_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(db_default=Now())

    class Meta:
        db_table = 'users"."user_public_profiles'
        constraints = [
            models.CheckConstraint(
                condition=Q(username='') | Q(GreaterThanOrEqual(Length(Trim('username')), 2)),
                name='upp_username_ck'),
            models.CheckConstraint(
                condition=(Q(avatar_key__isnull=True, avatar_uploaded_at__isnull=True)
                           | Q(avatar_key__isnull=False, avatar_uploaded_at__isnull=False))
                & (Q(avatar_thumb_key__isnull=True) | Q(avatar_key__isnull=False)),
                name='upp_avatar_all_or_none_ck'),
            models.CheckConstraint(
                condition=(Q(avatar_width__isnull=True) | Q(avatar_width__gt=0))
                & (Q(avatar_height__isnull=True) | Q(avatar_height__gt=0))
                & (Q(avatar_size_bytes__isnull=True) | Q(avatar_size_bytes__gt=0)),
                name='upp_avatar_dims_ck'),
            models.UniqueConstraint(fields=['avatar_key'], condition=Q(avatar_key__isnull=False),
                                    name='upp_avatar_key_uq'),
        ]

    def __str__(self):
        return f'{self.user_id}: {self.username}'
