"""
Serializers de mitjans: MediaItem (contracte).
(Els d'intents de pujada i confirmació són a `apps/uploads/serializers.py`; els de denúncies i avisos, a
`apps/moderation/serializers.py`.)
"""
from rest_framework import serializers


class MediaItemSerializer(serializers.Serializer):
    """
    Forma pública d'un mitjà (contracte d'API):
    {key, url, thumb_url, media_type, width, height, blurhash, creator_uid, uploaded_at, taken_at, experience_id}
    """
    key = serializers.CharField()
    url = serializers.CharField()
    thumb_url = serializers.CharField(required=False, allow_null=True)
    media_type = serializers.ChoiceField(choices=['image', 'video'], required=False, allow_null=True)
    width = serializers.IntegerField(required=False, allow_null=True)
    height = serializers.IntegerField(required=False, allow_null=True)
    blurhash = serializers.CharField(required=False, allow_null=True)
    creator_uid = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    uploaded_at = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    taken_at = serializers.CharField(required=False, allow_null=True)
    experience_id = serializers.CharField(required=False, allow_null=True)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Compatibilitat: items antics sense miniatura → thumb_url = url
        if not data.get('thumb_url'):
            data['thumb_url'] = data.get('url')
        for field_name in ('width', 'height', 'blurhash', 'taken_at', 'experience_id', 'media_type'):
            data.setdefault(field_name, None)
        if data.get('media_type') is None:
            from .media_metadata import infer_media_type
            data['media_type'] = infer_media_type(data.get('key'))
        return data
