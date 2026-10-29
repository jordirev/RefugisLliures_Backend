"""
Serializers d'`uploads`: intents de pujada directa i confirmació (contracte JSON idèntic a l'anterior).

- Entrada: `UploadIntentCreateSerializer` (`target`, `refuge_id`/`experience_id` segons el `target`, `rights_confirmed`,
  fins a 10 `files {content_type, size}`) i `UploadConfirmSerializer` (`upload_ids`).
- Sortida: només documenten la resposta (Swagger); els `MediaItem` els emet `apps.refuges.serializers.media_to_dict`.
"""
from rest_framework import serializers

from apps.uploads.media_serializer import MediaItemSerializer
from apps.uploads.image_processing_service import (
    ALLOWED_IMAGE_CONTENT_TYPES, ALLOWED_VIDEO_CONTENT_TYPES, FAILURE_REASONS, kind_for_content_type,
    max_bytes_for_kind, normalize_content_type)

from .models import UploadTarget

MAX_FILES_PER_INTENT = 10


class UploadFileSpecSerializer(serializers.Serializer):
    content_type = serializers.CharField(max_length=100)
    size = serializers.IntegerField(min_value=1)

    def validate(self, attrs):
        content_type = normalize_content_type(attrs['content_type'])
        kind = kind_for_content_type(content_type)
        if kind is None:
            raise serializers.ValidationError({
                'content_type': (
                    f"Tipus no permès. Imatges: {', '.join(ALLOWED_IMAGE_CONTENT_TYPES)}. "
                    f"Vídeos: {', '.join(ALLOWED_VIDEO_CONTENT_TYPES)}"
                )
            })
        limit = max_bytes_for_kind(kind)
        if attrs['size'] > limit:
            raise serializers.ValidationError({
                'size': f"Mida màxima per a {kind}: {limit // (1024 * 1024)} MB"
            })
        attrs['content_type'] = content_type
        attrs['kind'] = kind
        return attrs


class UploadIntentCreateSerializer(serializers.Serializer):
    """POST /api/media/upload-intents/"""
    target = serializers.ChoiceField(choices=list(UploadTarget.values))
    refuge_id = serializers.CharField(required=False, allow_blank=False, max_length=100)
    experience_id = serializers.CharField(required=False, allow_blank=False, max_length=100)
    rights_confirmed = serializers.BooleanField(required=True)
    files = UploadFileSpecSerializer(many=True, allow_empty=False)

    def validate_files(self, value):
        if len(value) > MAX_FILES_PER_INTENT:
            raise serializers.ValidationError(f"Com a màxim {MAX_FILES_PER_INTENT} fitxers per petició")
        return value

    def validate(self, attrs):
        if attrs.get('rights_confirmed') is not True:
            raise serializers.ValidationError({
                'rights_confirmed': "Cal declarar que tens els drets i el permís de les persones que hi surten"
            })
        target = attrs['target']
        if target == UploadTarget.REFUGE and not attrs.get('refuge_id'):
            raise serializers.ValidationError({'refuge_id': "refuge_id és obligatori per a target=refuge"})
        if target == UploadTarget.EXPERIENCE and not attrs.get('experience_id'):
            raise serializers.ValidationError({'experience_id': "experience_id és obligatori per a target=experience"})
        if target == UploadTarget.AVATAR:
            files = attrs.get('files') or []
            if len(files) != 1:
                raise serializers.ValidationError({'files': "L'avatar requereix exactament un fitxer"})
            if files[0].get('kind') != 'image':
                raise serializers.ValidationError({'files': "L'avatar només pot ser una imatge"})
        return attrs


class UploadIntentItemSerializer(serializers.Serializer):
    upload_id = serializers.CharField()
    put_url = serializers.CharField()
    headers = serializers.DictField(child=serializers.CharField())
    expires_in = serializers.IntegerField()


class UploadIntentResponseSerializer(serializers.Serializer):
    uploads = UploadIntentItemSerializer(many=True)


class UploadConfirmSerializer(serializers.Serializer):
    """POST /api/media/upload-intents/confirm/"""
    upload_ids = serializers.ListField(
        child=serializers.CharField(max_length=128), allow_empty=False, max_length=MAX_FILES_PER_INTENT
    )


class UploadFailureSerializer(serializers.Serializer):
    upload_id = serializers.CharField()
    reason = serializers.ChoiceField(choices=list(FAILURE_REASONS))


class UploadConfirmResponseSerializer(serializers.Serializer):
    uploaded = MediaItemSerializer(many=True)
    failed = UploadFailureSerializer(many=True)
