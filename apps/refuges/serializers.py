"""
Serializers de `refuges`: contracte JSON de l'API (el frontend no canvia; docs/design/postgres-schema.md §5.2).

- Els serializers de sortida treballen sobre diccionaris; `refuge_to_dict` / `media_to_dict` converteixen les
  instàncies dels models (sense consultes addicionals: tot el que fa falta ve dels selectors).
- `condition` es desa com a mitjana decimal; es mostra com a enter arrodonit **half-to-even** (`round()` de Python,
  el mateix que `core.round_half_even` a SQL).
- `surname` no s'emet mai; `visitors` només per als admins; `images_metadata` només per als autenticats.
"""
from datetime import date, datetime

from rest_framework import serializers

from api.serializers.media_serializer import MediaItemSerializer
from api.utils.timezone_utils import get_madrid_timezone

from .models import RefugeAmenities, RefugeType

VALID_TYPES = list(RefugeType.values)
CONDITION_VALUES = (0, 1, 2, 3)


# ---------- Model -> diccionari (forma del contracte) ----------

def isoformat_madrid(value):
    """`datetime` -> ISO 8601 amb l'offset d'`Europe/Madrid` (com ara); `None` es manté."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(get_madrid_timezone()).isoformat()
    return value.isoformat() if isinstance(value, date) else str(value)


def media_to_dict(media, presign):
    """Fila de `refuge_media` -> `MediaItem` `{key, url, thumb_url, media_type, ...}`; `presign(key)` -> URL."""
    url = presign(media.key)
    return {
        'key': media.key,
        'url': url,
        'thumb_url': presign(media.thumb_key) if media.thumb_key else url,
        'media_type': media.media_type,
        'width': media.width,
        'height': media.height,
        'blurhash': media.blurhash,
        'creator_uid': media.creator_id,
        'uploaded_at': isoformat_madrid(media.uploaded_at),
        'taken_at': isoformat_madrid(media.taken_at),
        'experience_id': None,        # la columna arriba amb el chunk 7
    }


def refuge_to_dict(refuge, links=None, media=None, visitors=None):
    """
    Refugi (amb `amenities` ja carregades pel `select_related`) -> diccionari de la resposta.
    `links`: URLs ordenades; `media`: llista de `MediaItem` o `None`; `visitors`: llista d'UIDs o `None`.
    """
    try:
        amenities = refuge.amenities
    except RefugeAmenities.DoesNotExist:           # invariant no forçat per la BD: tot `false`
        amenities = None
    data = {
        'id': str(refuge.pk),
        'name': refuge.name,
        'coord': {'lat': refuge.coord.y, 'long': refuge.coord.x},
        'altitude': refuge.altitude,
        'places': refuge.places,
        'remarque': refuge.remarque,
        'info_comp': {f: int(bool(getattr(amenities, f, False))) for f in RefugeAmenities.AMENITY_FIELDS},
        'description': refuge.description,
        'links': list(links if links is not None else getattr(refuge, 'links_list', None) or []),
        'type': refuge.type,
        'modified_at': refuge.modified_at.isoformat() if refuge.modified_at else None,
        'region': refuge.region,
        'departement': refuge.departement,
        'condition': refuge.condition,
    }
    if visitors is not None:
        data['visitors'] = visitors
    if media is not None:
        data['images_metadata'] = media
    return data


# ---------- Serializers de sortida ----------

class CoordinatesSerializer(serializers.Serializer):
    long = serializers.FloatField()
    lat = serializers.FloatField()


class InfoComplementariaSerializer(serializers.Serializer):
    """Serveis del refugi com a enters 0/1 (el DTO del frontend és `number`)."""
    manque_un_mur = serializers.IntegerField(default=0)
    cheminee = serializers.IntegerField(default=0)
    poele = serializers.IntegerField(default=0)
    couvertures = serializers.IntegerField(default=0)
    latrines = serializers.IntegerField(default=0)
    bois = serializers.IntegerField(default=0)
    eau = serializers.IntegerField(default=0)
    matelas = serializers.IntegerField(default=0)
    couchage = serializers.IntegerField(default=0)
    bas_flancs = serializers.IntegerField(default=0)
    lits = serializers.IntegerField(default=0)
    mezzanine_etage = serializers.IntegerField(default=0)


class RefugeMediaMetadataSerializer(MediaItemSerializer):
    """Forma MediaItem del contracte."""


class RefugiSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    coord = CoordinatesSerializer()
    altitude = serializers.IntegerField(default=None, allow_null=True)
    places = serializers.IntegerField(default=None, allow_null=True)
    remarque = serializers.CharField(default='', allow_blank=True)
    info_comp = InfoComplementariaSerializer()
    description = serializers.CharField(default='', allow_blank=True)
    links = serializers.ListField(child=serializers.URLField(), default=list)
    type = serializers.CharField(default=RefugeType.NON_GARDE.value)
    modified_at = serializers.CharField(default=None, allow_null=True)
    region = serializers.CharField(default=None, allow_null=True, required=False)
    departement = serializers.CharField(default=None, allow_null=True, required=False)
    # Float (no Integer): un IntegerField truncaria 1.5 -> 1 abans d'arrodonir. L'enter el calcula `to_representation`.
    condition = serializers.FloatField(default=None, allow_null=True, required=False)
    visitors = serializers.ListField(child=serializers.CharField(), default=list, required=False)
    images_metadata = RefugeMediaMetadataSerializer(many=True, required=False, allow_null=True)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if data.get('condition') is not None:
            data['condition'] = round(float(data['condition']))        # half-to-even, com `core.round_half_even`
        if not self.context.get('is_authenticated', False):
            data.pop('visitors', None)
            data.pop('images_metadata', None)
        else:
            if 'visitors' not in instance:                              # només els admins en reben
                data.pop('visitors', None)
            if 'images_metadata' not in instance:
                data.pop('images_metadata', None)
        return data


class RefugiSearchResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    has_filters = serializers.BooleanField()
    results = RefugiSerializer(many=True)


class RefugeMapPointSerializer(serializers.Serializer):
    """Llista sense filtres: `{id, name, coord, geohash}` (vista `refuge_map`)."""
    id = serializers.CharField()
    name = serializers.CharField()
    coord = CoordinatesSerializer()
    geohash = serializers.CharField(allow_null=True)


class RefugeMapResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    has_filters = serializers.BooleanField()
    results = RefugeMapPointSerializer(many=True)


class RefugeMediaListResponseSerializer(serializers.Serializer):
    media = RefugeMediaMetadataSerializer(many=True)


class RefugeMediaDeleteResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    message = serializers.CharField()
    key = serializers.CharField()


# ---------- Serializer d'entrada (query params de la cerca) ----------

class RefugiSearchFiltersSerializer(serializers.Serializer):
    name = serializers.CharField(required=False, default='', allow_blank=True)
    type = serializers.CharField(
        required=False, allow_blank=True, default='',
        help_text='Llista de tipus de refugi separats per comes')
    condition = serializers.CharField(
        required=False, allow_blank=True, default='',
        help_text='Llista de condicions separades per comes (0: pobre, 1: correcte, 2: bé, 3: excel·lent)')
    places_min = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    places_max = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    altitude_min = serializers.IntegerField(required=False, allow_null=True, min_value=0, max_value=8848)
    altitude_max = serializers.IntegerField(required=False, allow_null=True, min_value=0, max_value=8848)

    @staticmethod
    def _validate_range(min_value, max_value, prefix):
        if min_value is not None and max_value is not None and min_value > max_value:
            raise serializers.ValidationError({
                f'{prefix}_min': f'{prefix}_min ha de ser menor o igual que {prefix}_max'})

    def validate(self, data):
        raw_types = data.get('type', '')
        types = [t.strip() for t in raw_types.split(',') if t.strip()] if isinstance(raw_types, str) else raw_types
        for t in types:
            if t not in VALID_TYPES:
                raise serializers.ValidationError({
                    'type': f'El valor "{t}" no és vàlid. Els valors permesos són: {", ".join(VALID_TYPES)}'})
        data['type'] = types

        raw_conditions = data.get('condition', '')
        conditions = []
        if isinstance(raw_conditions, str):
            for c in (c.strip() for c in raw_conditions.split(',')):
                if not c:
                    continue
                try:
                    conditions.append(int(c))
                except ValueError:
                    raise serializers.ValidationError({
                        'condition': 'condition ha de contenir només enters (0, 1, 2 o 3) separats per comes'})
        for c in conditions:
            if c not in CONDITION_VALUES:
                raise serializers.ValidationError({
                    'condition': 'Els valors de condition han de ser 0 (pobre), 1 (correcte), 2 (bé) o 3 (excel·lent)'})
        data['condition'] = conditions

        self._validate_range(data.get('places_min'), data.get('places_max'), 'places')
        self._validate_range(data.get('altitude_min'), data.get('altitude_max'), 'altitude')
        return data
