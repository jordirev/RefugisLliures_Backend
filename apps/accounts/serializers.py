"""
Serializers de `accounts`: entrada (validació) i forma JSON de la sortida (docs/design/postgres-schema.md §5.2).

- L'idioma es valida contra el catàleg `users.languages` (BD, §2.1.1), no contra una llista fixa; el valor per defecte
  (`en`) el posa la BD. Cap `default=` als serializers d'actualització (TECH_DEBT M1: el PATCH resetejava `language`).
- Perfil **propi**: `{uid, username, avatar_metadata, language, favourite_refuges, visited_refuges,
  uploaded_photos_keys, num_shared_experiences, num_renovated_refuges, created_at, age_confirmed}`.
  Perfil **d'un altre**: només `{uid, username, avatar_metadata}` (decisió del PO, també per a un admin: D23).
"""
from datetime import datetime

from rest_framework import serializers

from apps.uploads.media_serializer import MediaItemSerializer
from apps.core.timezone_utils import get_madrid_today
from apps.refuges.serializers import CoordinatesSerializer, isoformat_madrid, media_to_dict

from .models import Language

USERNAME_HELP = "Nom d'usuari (buit o de 2 a 255 caràcters)"
LANGUAGE_HELP = "Idioma preferit: un codi del catàleg `users.languages` (inicialment ca, es, en, fr)"
BIRTH_DATE_HELP = ("Data de naixement (YYYY-MM-DD). Només s'usa per comprovar l'edat mínima (16); no es desa.")


def validate_birth_date_value(value):
    """Rebutja dates futures (a Madrid, com `is_old_enough`) o absurdes (abans de 1900)."""
    if value > get_madrid_today():
        raise serializers.ValidationError('La data de naixement no pot ser futura')
    if value.year < 1900:
        raise serializers.ValidationError('Data de naixement no vàlida')
    return value


class _UsernameLanguageMixin:
    def validate_username(self, value):
        value = (value or '').strip()
        if value and len(value) < 2:
            raise serializers.ValidationError("El nom d'usuari ha de tenir almenys 2 caràcters")
        return value

    def validate_language(self, value):
        value = value.strip().lower()
        if not Language.objects.filter(code=value).exists():            # catàleg obert a la BD
            codes = ', '.join(Language.objects.order_by('code').values_list('code', flat=True))
            raise serializers.ValidationError(f'Idioma no vàlid. Opcions vàlides: {codes}')
        return value


class UserCreateSerializer(_UsernameLanguageMixin, serializers.Serializer):
    """`POST /users/`. L'UID surt del token; qualsevol altre camp del cos s'ignora."""
    username = serializers.CharField(max_length=255, allow_blank=True, required=False, help_text=USERNAME_HELP)
    language = serializers.CharField(max_length=8, required=False, help_text=LANGUAGE_HELP)
    birth_date = serializers.DateField(required=False, input_formats=['%Y-%m-%d'], help_text=BIRTH_DATE_HELP)

    def validate_birth_date(self, value):
        return validate_birth_date_value(value)


class UserUpdateSerializer(_UsernameLanguageMixin, serializers.Serializer):
    """`PATCH /users/{uid}/`: només `username` i/o `language`; cap valor per defecte; almenys un camp."""
    username = serializers.CharField(max_length=255, allow_blank=True, required=False, help_text=USERNAME_HELP)
    language = serializers.CharField(max_length=8, required=False, help_text=LANGUAGE_HELP)

    def validate(self, attrs):
        if not attrs:                       # `username=''` és un camp proporcionat (D23)
            raise serializers.ValidationError('Almenys un camp ha de ser proporcionat per actualitzar')
        return attrs


class AgeConfirmationSerializer(serializers.Serializer):
    """`PATCH /users/{uid}/age-confirmation/`"""
    birth_date = serializers.DateField(required=True, input_formats=['%Y-%m-%d'], help_text=BIRTH_DATE_HELP)

    def validate_birth_date(self, value):
        return validate_birth_date_value(value)


class RefugeIdSerializer(serializers.Serializer):
    """Cos de `POST /users/{uid}/favorite-refuges/` i `.../visited-refuges/`."""
    refuge_id = serializers.CharField(max_length=255, help_text='Identificador del refugi (UUID)')


# ---------- Model -> diccionari (forma del contracte) ----------

def avatar_to_dict(data, uid, presign):
    """Avatar (`dict` de la subconsulta JSON o instància de `UserAvatar`) -> MediaItem; `None` si no n'hi ha."""
    if not data:
        return None
    if not isinstance(data, dict):
        data = {f: getattr(data, f) for f in ('key', 'thumb_key', 'width', 'height', 'blurhash', 'uploaded_at')}
    uploaded_at = data.get('uploaded_at')
    if isinstance(uploaded_at, str):
        uploaded_at = datetime.fromisoformat(uploaded_at)
    url = presign(data['key'])
    return {
        'key': data['key'],
        'url': url,
        'thumb_url': presign(data['thumb_key']) if data.get('thumb_key') else url,
        'media_type': 'image',
        'width': data.get('width'),
        'height': data.get('height'),
        'blurhash': data.get('blurhash'),
        'creator_uid': uid,
        'uploaded_at': isoformat_madrid(uploaded_at),
        'taken_at': None,
        'experience_id': None,
    }


def own_profile_to_dict(user, counts, presign):
    """
    `UserAccount` (de `selectors.get_own_profile` o de `services.create_user`) -> perfil complet.
    `counts`: `{'num_shared_experiences', 'num_renovated_refuges'}` (agregacions SQL, `selectors.get_legacy_counts`).
    """
    profile = user.public_profile
    return {
        'uid': user.uid,
        'username': profile.username,
        'avatar_metadata': avatar_to_dict(getattr(user, 'avatar_json', None), user.uid, presign),
        'language': user.language_id,
        'favourite_refuges': [str(i) for i in getattr(user, 'favourite_ids', [])],
        'visited_refuges': [str(i) for i in getattr(user, 'visited_ids', [])],
        'uploaded_photos_keys': list(getattr(user, 'photo_keys', [])),
        'num_shared_experiences': counts['num_shared_experiences'],
        'num_renovated_refuges': counts['num_renovated_refuges'],
        'created_at': isoformat_madrid(user.created_at),
        'age_confirmed': user.age_confirmed_at is not None,
    }


def public_profile_to_dict(profile, presign):
    """`UserPublicProfile` (de `selectors.get_public_profile`) -> `{uid, username, avatar_metadata}`."""
    return {
        'uid': profile.user_id,
        'username': profile.username,
        'avatar_metadata': avatar_to_dict(getattr(profile, 'avatar_json', None), profile.user_id, presign),
    }


def refuge_summary_to_dict(refuge, first_media, presign):
    """Refugi d'una llista d'usuari -> `{id, name, region, places, coord, images_metadata: [1a foto visible] | null}`."""
    return {
        'id': str(refuge.pk),
        'name': refuge.name,
        'region': refuge.region,
        'places': refuge.places,
        'coord': {'lat': refuge.coord.y, 'long': refuge.coord.x},
        'images_metadata': [media_to_dict(first_media, presign)] if first_media is not None else None,
    }


# ---------- Serializers de sortida (documentació Swagger) ----------

class UserSerializer(serializers.Serializer):
    uid = serializers.CharField()
    username = serializers.CharField(allow_blank=True)
    avatar_metadata = MediaItemSerializer(allow_null=True)
    language = serializers.CharField()
    favourite_refuges = serializers.ListField(child=serializers.CharField())
    visited_refuges = serializers.ListField(child=serializers.CharField())
    uploaded_photos_keys = serializers.ListField(child=serializers.CharField())
    num_shared_experiences = serializers.IntegerField()
    num_renovated_refuges = serializers.IntegerField()
    created_at = serializers.CharField()
    age_confirmed = serializers.BooleanField()


class PublicUserSerializer(serializers.Serializer):
    uid = serializers.CharField()
    username = serializers.CharField(allow_blank=True)
    avatar_metadata = MediaItemSerializer(allow_null=True)


class UserRefugeInfoSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    region = serializers.CharField(allow_null=True)
    places = serializers.IntegerField(allow_null=True)
    coord = CoordinatesSerializer()
    images_metadata = MediaItemSerializer(many=True, allow_null=True)


class UserRefugeListSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    results = UserRefugeInfoSerializer(many=True)
