"""
Models de `refuges` (schema `refuges`), docs/design/postgres-schema.md §2.5-2.8, §4.1, §6.

- Les PK substitutes són `uuid` v7 generats per l'app (`api.utils.ids.uuid7`); `RefugeMedia.key` és la clau R2.
- Les FK són `DO_NOTHING` + `db_constraint=False`: la restricció real (amb `ON DELETE` del DDL) la crea la migració
  per `RunSQL` (§6.3). Així `Refuge.delete()` emet un sol `DELETE` i la BD cascadeja amb els privilegis del propietari.
- `condition` és una mitjana desada (`double precision`, 0-3); només s'arrodoneix en mostrar-la i en filtrar
  (`core.round_half_even`, que coincideix amb el `round()` de Python).
"""
from django.contrib.gis.db.models import PointField
from django.contrib.postgres.indexes import GinIndex, GistIndex, OpClass
from django.db import models
from django.db.models import F, Func, Q, TextField, Value
from django.db.models.functions import Length, Now, Trim
from django.db.models.lookups import Exact, GreaterThan, LessThanOrEqual

from api.utils.ids import uuid7
from apps.accounts.models import UserAccount


class RefugeType(models.TextChoices):
    NON_GARDE = 'non gardé'
    FERMEE = 'fermée'
    CABANE_OUVERTE = 'cabane ouverte mais ocupee par le berger l ete'
    ORRI = 'orri'
    EMERGENCE = 'emergence'
    KEY_NEEDED = 'key_needed'


class MediaStatus(models.TextChoices):
    VISIBLE = 'visible'
    HIDDEN_PENDING_REVIEW = 'hidden_pending_review'
    REMOVED = 'removed'


class MediaType(models.TextChoices):
    IMAGE = 'image'
    VIDEO = 'video'


def norm_name(expression):
    """`core.norm_name(expr)`: sense accents i en minúscules (mateixa expressió a l'índex i a les consultes)."""
    return Func(expression, function='core.norm_name', output_field=TextField())


def _not_blank(field):
    return GreaterThan(Length(Trim(field)), 0)


class Refuge(models.Model):
    """`refuges.refuges`: lectura pública; escriptura només admin/sistema (RLS)."""

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    name = models.CharField(max_length=255)
    surname = models.CharField(max_length=255, null=True, blank=True)    # àlies: es desa i només s'usa a la cerca
    type = models.CharField(max_length=64, choices=RefugeType.choices, db_default=RefugeType.NON_GARDE)
    coord = PointField(geography=True, srid=4326, spatial_index=False)   # x = longitud, y = latitud
    altitude = models.IntegerField(null=True, blank=True)
    places = models.IntegerField(null=True, blank=True)
    remarque = models.TextField(db_default='', blank=True)
    description = models.TextField(db_default='', blank=True)
    region = models.CharField(max_length=255, null=True, blank=True)
    departement = models.CharField(max_length=255, null=True, blank=True)
    modified_at = models.DateField(null=True, blank=True)
    condition = models.FloatField(null=True, blank=True)                 # mitjana 0-3 sense arrodonir
    num_contributed_conditions = models.IntegerField(db_default=0)
    condition_reset_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(db_default=Now())

    class Meta:
        db_table = 'refuges"."refuges'
        constraints = [
            models.CheckConstraint(condition=Q(condition__isnull=True) | Q(condition__gte=0, condition__lte=3),
                                   name='refuges_condition_ck'),
            models.CheckConstraint(
                condition=Q(num_contributed_conditions__gte=0)
                & (Q(num_contributed_conditions=0) | Q(condition__isnull=False)),
                name='refuges_condition_n_ck'),
            models.CheckConstraint(condition=_not_blank('name'), name='refuges_name_ck'),
            models.CheckConstraint(condition=Q(surname__isnull=True) | Q(_not_blank('surname')),
                                   name='refuges_surname_ck'),
            models.CheckConstraint(condition=Q(type__in=RefugeType.values), name='refuges_type_ck'),
            models.CheckConstraint(condition=Q(altitude__isnull=True) | Q(altitude__gte=0, altitude__lte=8848),
                                   name='refuges_altitude_ck'),
            models.CheckConstraint(condition=Q(places__isnull=True) | Q(places__gte=0), name='refuges_places_ck'),
            # `refuges_coord_ck` (punt 0,0 prohibit) no és expressable amb l'ORM: es crea per RunSQL a la migració.
        ]
        indexes = [
            GistIndex(fields=['coord'], name='refuges_coord_gist'),
            GinIndex(OpClass(norm_name(F('name')), name='gin_trgm_ops'), name='refuges_name_trgm_gin'),
            GinIndex(OpClass(norm_name(F('surname')), name='gin_trgm_ops'), name='refuges_surname_trgm_gin',
                     condition=Q(surname__isnull=False)),
            models.Index(fields=['type'], name='refuges_type_idx'),
            models.Index(fields=['places'], name='refuges_places_idx', condition=Q(places__isnull=False)),
            models.Index(fields=['altitude'], name='refuges_altitude_idx', condition=Q(altitude__isnull=False)),
        ]

    def __str__(self):
        return self.name


class RefugeAmenities(models.Model):
    """`refuges.refuge_amenities`: 1-1 amb el refugi (`info_comp`); `info_couchage`/`info_eau` s'ignoren."""

    AMENITY_FIELDS = ('manque_un_mur', 'cheminee', 'poele', 'couvertures', 'latrines', 'bois', 'eau', 'matelas',
                      'couchage', 'bas_flancs', 'lits', 'mezzanine_etage')

    refuge = models.OneToOneField(
        Refuge, primary_key=True, on_delete=models.DO_NOTHING, db_constraint=False, db_column='refuge_id',
        related_name='amenities')
    manque_un_mur = models.BooleanField(db_default=False)
    cheminee = models.BooleanField(db_default=False)
    poele = models.BooleanField(db_default=False)
    couvertures = models.BooleanField(db_default=False)
    latrines = models.BooleanField(db_default=False)
    bois = models.BooleanField(db_default=False)
    eau = models.BooleanField(db_default=False)
    matelas = models.BooleanField(db_default=False)
    couchage = models.BooleanField(db_default=False)
    bas_flancs = models.BooleanField(db_default=False)
    lits = models.BooleanField(db_default=False)
    mezzanine_etage = models.BooleanField(db_default=False)

    class Meta:
        db_table = 'refuges"."refuge_amenities'


class RefugeLink(models.Model):
    """`refuges.refuge_links`: enllaços ordenats per `position`."""

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    refuge = models.ForeignKey(
        Refuge, on_delete=models.DO_NOTHING, db_constraint=False, db_index=False, db_column='refuge_id',
        related_name='links')
    position = models.SmallIntegerField()
    url = models.TextField()

    class Meta:
        db_table = 'refuges"."refuge_links'
        constraints = [
            models.CheckConstraint(condition=Q(position__gte=0), name='refuge_links_position_ck'),
            models.CheckConstraint(condition=Q(url__iregex=r'^https?://') & Q(LessThanOrEqual(Length('url'), 2048)),
                                   name='refuge_links_url_ck'),
            # Diferible: permet reordenar (intercanviar posicions) dins la mateixa transacció.
            models.UniqueConstraint(fields=['refuge', 'position'], name='refuge_links_refuge_position_uq',
                                    deferrable=models.Deferrable.DEFERRED),
            models.UniqueConstraint(fields=['refuge', 'url'], name='refuge_links_refuge_url_uq'),
        ]


class RefugeMedia(models.Model):
    """`refuges.refuge_media`: imatge o vídeo d'un refugi (la clau és la clau R2)."""

    key = models.TextField(primary_key=True)
    refuge = models.ForeignKey(
        Refuge, on_delete=models.DO_NOTHING, db_constraint=False, db_index=False, db_column='refuge_id',
        related_name='media')
    creator = models.ForeignKey(
        UserAccount, on_delete=models.DO_NOTHING, db_constraint=False, db_index=False, db_column='creator_uid',
        related_name='+')
    media_type = models.CharField(max_length=5, choices=MediaType.choices)
    content_type = models.CharField(max_length=100)
    status = models.CharField(max_length=24, choices=MediaStatus.choices, db_default=MediaStatus.VISIBLE)
    uploaded_at = models.DateTimeField(db_default=Now())
    taken_at = models.DateTimeField(null=True, blank=True)
    width = models.IntegerField(null=True, blank=True)
    height = models.IntegerField(null=True, blank=True)
    size_bytes = models.BigIntegerField(null=True, blank=True)
    thumb_key = models.TextField(null=True, blank=True)
    blurhash = models.CharField(max_length=100, null=True, blank=True)
    rights_confirmed_at = models.DateTimeField()
    # `experience_id` (+ FK cap a `activity.experiences`) arriba al chunk 7 amb `refuges.0002` (§6.2).

    class Meta:
        db_table = 'refuges"."refuge_media'
        constraints = [
            models.CheckConstraint(condition=Q(status__in=MediaStatus.values), name='refuge_media_status_ck'),
            models.CheckConstraint(condition=Q(media_type__in=MediaType.values), name='refuge_media_type_ck'),
            models.CheckConstraint(condition=~Exact(Trim('key'), Value('')), name='refuge_media_key_ck'),
            models.CheckConstraint(condition=Q(thumb_key__isnull=True) | ~Q(thumb_key=F('key')),
                                   name='refuge_media_thumb_ck'),
            models.CheckConstraint(
                condition=(Q(width__isnull=True) | Q(width__gt=0)) & (Q(height__isnull=True) | Q(height__gt=0))
                & (Q(size_bytes__isnull=True) | Q(size_bytes__gt=0)),
                name='refuge_media_dims_ck'),
            models.UniqueConstraint(fields=['thumb_key'], condition=Q(thumb_key__isnull=False),
                                    name='refuge_media_thumb_key_uq'),
        ]
        indexes = [
            models.Index(fields=['refuge', 'uploaded_at', 'key'], name='refuge_media_refuge_idx'),
            models.Index(fields=['creator', 'uploaded_at'], name='refuge_media_creator_idx'),
        ]


class RefugeMapPoint(models.Model):
    """Vista `refuges.refuge_map` (no gestionada): punts del mapa sense joins (substitueix `coords_refugis`)."""

    id = models.OneToOneField(Refuge, primary_key=True, on_delete=models.DO_NOTHING, db_column='id',
                              related_name='map_point')
    name = models.CharField(max_length=255)
    lat = models.FloatField()
    lng = models.FloatField()
    geohash = models.CharField(max_length=5)
    coord = PointField(geography=True, srid=4326, spatial_index=False)

    class Meta:
        managed = False
        db_table = 'refuges"."refuge_map'
