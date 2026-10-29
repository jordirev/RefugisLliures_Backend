"""
Serializers d'`experiences` (contracte JSON d'abans amb el camp nou `condition`, 0-3 i obligatori a la creació).

- Entrada: `ExperienceCreateSerializer` (`refuge_id`, `comment`, `condition`) i `ExperienceUpdateSerializer` (`comment`
  i `condition`, opcionals i **sense valors per defecte**). El comentari es retalla, no pot ser buit, té com a molt
  2000 caràcters i no pot dur NUL (les mateixes regles que el CHECK de la BD).
- Sortida: `experience_to_dict` converteix una `Experience` i els seus mitjans a la forma de l'API;
  `ExperienceResponseSerializer` i `ExperienceListResponseSerializer` només documenten la resposta.
"""
from django.core.validators import ProhibitNullCharactersValidator
from rest_framework import serializers

from apps.refuges.serializers import isoformat_madrid, media_to_dict
from apps.uploads.serializers import MediaItemSerializer

from .models import COMMENT_MAX_LENGTH, CONDITION_MAX, CONDITION_MIN


class RefugeIdField(serializers.CharField):
    """
    `refuge_id` del cos: un valor que no és un UUID (NUL inclòs) no és una dada invàlida sinó un refugi que no existeix
    (404), com ja passava amb els IDs antics de Firestore; per això no s'hi aplica la prohibició de NUL.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.validators = [v for v in self.validators if not isinstance(v, ProhibitNullCharactersValidator)]


class ExperienceCreateSerializer(serializers.Serializer):
    """POST /api/experiences/"""
    refuge_id = RefugeIdField(required=True, allow_blank=False, max_length=100)
    comment = serializers.CharField(required=True, allow_blank=False, max_length=COMMENT_MAX_LENGTH)
    condition = serializers.IntegerField(required=True, min_value=CONDITION_MIN, max_value=CONDITION_MAX)


class ExperienceUpdateSerializer(serializers.Serializer):
    """PATCH /api/experiences/{id}/ (cap camp és obligatori i cap té valor per defecte)."""
    comment = serializers.CharField(required=False, allow_blank=False, max_length=COMMENT_MAX_LENGTH)
    condition = serializers.IntegerField(required=False, min_value=CONDITION_MIN, max_value=CONDITION_MAX)


class ExperienceResponseSerializer(serializers.Serializer):
    """Forma d'una experiència a les respostes (només per a la documentació de Swagger)."""
    id = serializers.CharField()
    refuge_id = serializers.CharField()
    creator_uid = serializers.CharField()
    modified_at = serializers.CharField(help_text='ISO 8601 amb el desplaçament de Madrid')
    comment = serializers.CharField()
    condition = serializers.IntegerField(min_value=CONDITION_MIN, max_value=CONDITION_MAX)
    images_metadata = MediaItemSerializer(many=True)


class ExperienceWrapperSerializer(serializers.Serializer):
    experience = ExperienceResponseSerializer()


class ExperienceListResponseSerializer(serializers.Serializer):
    experiences = ExperienceResponseSerializer(many=True)


def experience_to_dict(experience, media, presign):
    """`Experience` + els seus mitjans (instàncies de `RefugeMedia`) -> diccionari de la resposta."""
    return {
        'id': str(experience.pk),
        'refuge_id': str(experience.refuge_id),
        'creator_uid': experience.creator_id,
        'modified_at': isoformat_madrid(experience.modified_at),
        'comment': experience.comment,
        'condition': experience.condition,
        'images_metadata': [media_to_dict(m, presign) for m in media],
    }
