"""
Serializers per a la gestió d'experiències
"""
from rest_framework import serializers
from .refugi_lliure_serializer import RefugeMediaMetadataSerializer


class ExperienceCreateSerializer(serializers.Serializer):
    """Serializer per crear una experiència (POST)"""
    comment = serializers.CharField(required=True, allow_blank=False, max_length=2000)
    files = serializers.ListField(
        child=serializers.FileField(),
        required=False,
        allow_empty=True
    )


class ExperienceUpdateSerializer(serializers.Serializer):
    """Serializer per actualitzar una experiència (PATCH)"""
    comment = serializers.CharField(required=False, allow_blank=False, max_length=2000)
    files = serializers.ListField(
        child=serializers.FileField(),
        required=False,
        allow_empty=True
    )


class ExperienceResponseSerializer(serializers.Serializer):
    """Serializer per la resposta d'una experiència (GET/POST/PATCH)"""
    id = serializers.CharField()
    refuge_id = serializers.CharField()
    creator_uid = serializers.CharField()
    modified_at = serializers.CharField()  # Format: DD/MM/YYYY
    comment = serializers.CharField()
    images_metadata = RefugeMediaMetadataSerializer(many=True, required=False)


class ExperienceListResponseSerializer(serializers.Serializer):
    """Serializer per la llista d'experiències (GET)"""
    experiences = ExperienceResponseSerializer(many=True)
