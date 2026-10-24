"""
Models de `accounts` (schema `users`), només el mínim que necessita el chunk 2 (§2.1, §2.1.1, §2.2, §2.2.1, §6.2):
`refuge_media.creator_uid` apunta a `users.users`. Les llistes (`user_favourite_refuges`, `user_visited_refuges`)
i la resta de la feature arriben al chunk 3 (`accounts.0002`).

Les FK són `DO_NOTHING` + `db_constraint=False`: la restricció real (amb `ON DELETE`) la crea la migració per
`RunSQL` (§6.3). Les escriptures passen per la RLS del rol `app` (vegeu la migració).
"""
from django.db import models
from django.db.models import F, Q, Value
from django.db.models.functions import Length, Now, Trim
from django.db.models.lookups import Exact, GreaterThanOrEqual

from apps.core.db_functions import TransactionNow


class Language(models.Model):
    """`users.languages`: catàleg obert dels idiomes (un idioma nou és un `INSERT` en una migració de dades)."""

    DEFAULT = 'en'

    code = models.CharField(max_length=8, primary_key=True)

    class Meta:
        db_table = 'users"."languages'
        constraints = [
            models.CheckConstraint(condition=Q(code__regex=r'^[a-z]{2}(-[a-z0-9]{2,4})?$'), name='languages_code_ck'),
        ]

    def __str__(self):
        return self.code


class UserAccount(models.Model):
    """`users.users`: dades privades i minimitzades (sense email ni data de naixement)."""

    uid = models.CharField(max_length=128, primary_key=True)          # UID de Firebase
    language = models.ForeignKey(
        Language, on_delete=models.DO_NOTHING, db_constraint=False, db_index=False, db_column='language',
        db_default=Language.DEFAULT, related_name='+')
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
        indexes = [models.Index(fields=['language'], name='users_language_idx')]

    def __str__(self):
        return self.uid


class UserPublicProfile(models.Model):
    """`users.user_public_profiles`: 1-1 amb `users`, lectura oberta (nom d'usuari; l'avatar és a `UserAvatar`)."""

    user = models.OneToOneField(
        UserAccount, primary_key=True, on_delete=models.DO_NOTHING, db_constraint=False, db_column='uid',
        related_name='public_profile')
    username = models.CharField(max_length=255, db_default='', blank=True)
    updated_at = models.DateTimeField(db_default=Now())

    class Meta:
        db_table = 'users"."user_public_profiles'
        constraints = [
            models.CheckConstraint(
                condition=Q(username='') | Q(GreaterThanOrEqual(Length(Trim('username')), 2)),
                name='upp_username_ck'),
        ]

    def __str__(self):
        return f'{self.user_id}: {self.username}'


class UserAvatar(models.Model):
    """`users.user_avatars`: avatar (0..1 per usuari); la PK és la clau R2. Canviar-lo = `DELETE` + `INSERT`."""

    key = models.TextField(primary_key=True)
    # FK + `UNIQUE` amb nom explícit (un `OneToOneField` crearia la unicitat amb un nom generat).
    user = models.ForeignKey(
        UserAccount, on_delete=models.DO_NOTHING, db_constraint=False, db_index=False, db_column='user_uid',
        related_name='+')
    thumb_key = models.TextField(null=True, blank=True)
    content_type = models.CharField(max_length=100)
    width = models.IntegerField(null=True, blank=True)
    height = models.IntegerField(null=True, blank=True)
    size_bytes = models.BigIntegerField(null=True, blank=True)
    blurhash = models.CharField(max_length=100, null=True, blank=True)
    uploaded_at = models.DateTimeField(db_default=Now())

    class Meta:
        db_table = 'users"."user_avatars'
        constraints = [
            models.CheckConstraint(condition=~Exact(Trim('key'), Value('')), name='user_avatars_key_ck'),
            models.CheckConstraint(condition=Q(thumb_key__isnull=True) | ~Q(thumb_key=F('key')),
                                   name='user_avatars_thumb_ck'),
            models.CheckConstraint(
                condition=(Q(width__isnull=True) | Q(width__gt=0)) & (Q(height__isnull=True) | Q(height__gt=0))
                & (Q(size_bytes__isnull=True) | Q(size_bytes__gt=0)),
                name='user_avatars_dims_ck'),
            models.UniqueConstraint(fields=['user'], name='user_avatars_user_uq'),     # un avatar per usuari; índex de la FK
            models.UniqueConstraint(fields=['thumb_key'], condition=Q(thumb_key__isnull=False),
                                    name='user_avatars_thumb_key_uq'),
        ]

    def __str__(self):
        return f'{self.user_id}: {self.key}'


class _UserRefugeList(models.Model):
    """
    Base abstracta de les llistes d'un usuari (preferits i visitats): PK composta `(user_uid, refuge_id)`, sense `id`.

    Afegir dues vegades és un `INSERT ... ON CONFLICT DO NOTHING` (no una carrera); `created_at` conserva l'ordre
    d'inserció (decisió del PO, com l'`ArrayUnion` de Firestore). Les FK reals (`ON DELETE CASCADE`) i la RLS són a
    la migració per `RunSQL` (§6.3).
    """

    pk = models.CompositePrimaryKey('user', 'refuge')
    user = models.ForeignKey(
        UserAccount, on_delete=models.DO_NOTHING, db_constraint=False, db_index=False, db_column='user_uid',
        related_name='+')
    refuge = models.ForeignKey(
        'refuges.Refuge', on_delete=models.DO_NOTHING, db_constraint=False, db_index=False, db_column='refuge_id',
        related_name='+')
    created_at = models.DateTimeField(db_default=TransactionNow())

    class Meta:
        abstract = True

    def __str__(self):
        return f'{self.user_id}: {self.refuge_id}'


class FavouriteRefuge(_UserRefugeList):
    """`users.user_favourite_refuges` (§2.3): privada (només el propi usuari)."""

    class Meta:
        db_table = 'users"."user_favourite_refuges'
        indexes = [
            models.Index(fields=['user', '-created_at', 'refuge'], name='favourites_user_created_idx'),   # keyset
            models.Index(fields=['refuge'], name='favourites_refuge_idx'),                                   # FK/cascada
        ]


class VisitedRefuge(_UserRefugeList):
    """`users.user_visited_refuges` (§2.4): font de veritat de «visitats» i de `refuge.visitors` (admins)."""

    class Meta:
        db_table = 'users"."user_visited_refuges'
        indexes = [
            models.Index(fields=['user', '-created_at', 'refuge'], name='visited_user_created_idx'),      # keyset
            models.Index(fields=['refuge', 'user'], name='visited_refuge_user_idx'),                       # visitors + FK
        ]
