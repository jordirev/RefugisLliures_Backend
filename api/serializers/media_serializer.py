"""
Serializers de mitjans: MediaItem (contracte), intents de pujada, confirmació,
denúncies i resolució de denúncies.
"""
from rest_framework import serializers

from ..models.upload_intent import UPLOAD_TARGETS, UPLOAD_TARGET_REFUGE, UPLOAD_TARGET_EXPERIENCE, UPLOAD_TARGET_AVATAR
from ..models.media_report import (
    REPORT_REASONS, REPORT_ACTIONS, REPORT_DETAILS_MAX_LENGTH, REPORT_STATUSES,
)
from ..services.image_processing_service import (
    normalize_content_type, kind_for_content_type, max_bytes_for_kind,
    ALLOWED_IMAGE_CONTENT_TYPES, ALLOWED_VIDEO_CONTENT_TYPES, FAILURE_REASONS,
)

MAX_FILES_PER_INTENT = 10


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
# Upload intents
# ---------------------------------------------------------------------------

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
    target = serializers.ChoiceField(choices=list(UPLOAD_TARGETS))
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
        if target == UPLOAD_TARGET_REFUGE and not attrs.get('refuge_id'):
            raise serializers.ValidationError({'refuge_id': "refuge_id és obligatori per a target=refuge"})
        if target == UPLOAD_TARGET_EXPERIENCE and not attrs.get('experience_id'):
            raise serializers.ValidationError({'experience_id': "experience_id és obligatori per a target=experience"})
        if target == UPLOAD_TARGET_AVATAR:
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
