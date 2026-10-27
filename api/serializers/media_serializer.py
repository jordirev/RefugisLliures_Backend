"""
Serializers de mitjans: MediaItem (contracte), denúncies i resolució de denúncies.
(Els d'intents de pujada i confirmació són a `apps/uploads/serializers.py`.)
"""
from rest_framework import serializers

from ..models.media_report import (
    REPORT_REASONS, REPORT_ACTIONS, REPORT_DETAILS_MAX_LENGTH, REPORT_STATUSES,
)


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
            from ..models.media_metadata import infer_media_type
            data['media_type'] = infer_media_type(data.get('key'))
        return data


# ---------------------------------------------------------------------------
# Denúncies
# ---------------------------------------------------------------------------

class MediaReportCreateSerializer(serializers.Serializer):
    """POST /api/media/reports/"""
    refuge_id = serializers.CharField(max_length=100)
    media_key = serializers.CharField(max_length=500)
    reason = serializers.ChoiceField(choices=list(REPORT_REASONS))
    details = serializers.CharField(required=False, allow_blank=True, allow_null=True,
                                    max_length=REPORT_DETAILS_MAX_LENGTH)

    def validate(self, attrs):
        if attrs['reason'] == 'other' and not (attrs.get('details') or '').strip():
            raise serializers.ValidationError({'details': "Cal una descripció quan el motiu és 'other'"})
        return attrs


class MediaReportResponseSerializer(serializers.Serializer):
    id = serializers.CharField()
    refuge_id = serializers.CharField()
    media_key = serializers.CharField()
    reason = serializers.CharField()
    details = serializers.CharField(allow_null=True)
    status = serializers.CharField()
    priority = serializers.CharField()
    created_at = serializers.CharField()
    media_hidden = serializers.BooleanField()


class MediaReportListQuerySerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=list(REPORT_STATUSES), required=False, default='pending')


class MediaReportResolveSerializer(serializers.Serializer):
    """PATCH /api/admin/media-reports/{id}/"""
    action = serializers.ChoiceField(choices=list(REPORT_ACTIONS))
    statement = serializers.CharField(max_length=2000, allow_blank=False, trim_whitespace=True)


class ModerationNoticeSerializer(serializers.Serializer):
    id = serializers.CharField()
    uid = serializers.CharField()
    type = serializers.CharField()
    statement = serializers.CharField(allow_blank=True)
    created_at = serializers.CharField(allow_blank=True)
    refuge_id = serializers.CharField(allow_null=True, required=False)
    media_key = serializers.CharField(allow_null=True, required=False)
    reason = serializers.CharField(allow_null=True, required=False)
    action = serializers.CharField(allow_null=True, required=False)
    report_id = serializers.CharField(allow_null=True, required=False)
    automated = serializers.BooleanField()
    strikes = serializers.IntegerField(allow_null=True, required=False)
    redress = serializers.CharField()
