"""
Serializers de `moderation`: entrada (denúncia, resolució, filtre del llistat) i sortida (denúncia amb previsualització
del mitjà, avís). La validació és la mateixa que els `CHECK` de la BD (GOTCHAS #5).
"""
from rest_framework import serializers

from apps.refuges.serializers import isoformat_madrid, media_to_dict

from .models import (
    REPORT_DETAILS_MAX_LENGTH, REPORT_STATEMENT_MAX_LENGTH, ReportAction, ReportReason, ReportStatus)

# Text constant de la via de recurs (art. 20 DSA); no es desa.
REDRESS_TEXT = (
    "Pots demanar la revisió d'aquesta decisió (art. 20 DSA) responent al correu de contacte "
    "indicat a la Política de privacitat i termes, en un termini de 6 mesos."
)
SYSTEM_REPORTER = 'system'          # denúncia automàtica (abans `reporter_uid = 'system'`)
UNKNOWN_REPORTER = 'unknown'        # denúncia `legal_hold` anonimitzada en esborrar el denunciant


class MediaReportCreateSerializer(serializers.Serializer):
    """POST /api/media/reports/"""
    refuge_id = serializers.CharField(max_length=100)
    media_key = serializers.CharField(max_length=500)
    reason = serializers.ChoiceField(choices=ReportReason.values)
    details = serializers.CharField(required=False, allow_blank=True, allow_null=True,
                                    max_length=REPORT_DETAILS_MAX_LENGTH)

    def validate(self, attrs):
        if attrs['reason'] == ReportReason.OTHER and not (attrs.get('details') or '').strip():
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
    status = serializers.ChoiceField(choices=ReportStatus.values, required=False, default=ReportStatus.PENDING.value)


class MediaReportResolveSerializer(serializers.Serializer):
    """PATCH /api/admin/media-reports/{id}/"""
    action = serializers.ChoiceField(choices=ReportAction.values)
    statement = serializers.CharField(max_length=REPORT_STATEMENT_MAX_LENGTH, allow_blank=False, trim_whitespace=True)


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


# ---------- Sortida ----------

def reporter_uid_of(source: str, reporter_uid):
    """`reporter_uid` de l'API: `'system'` si és automàtica, `'unknown'` si s'ha anonimitzat."""
    if source == 'automatic':
        return SYSTEM_REPORTER
    return reporter_uid or UNKNOWN_REPORTER


def report_to_dict(report) -> dict:
    """Forma de l'API d'una denúncia (instància) sense `media`: `legal_hold` i `anonymized_at` són interns."""
    return {
        'id': str(report.pk), 'refuge_id': str(report.refuge_id) if report.refuge_id else None,
        'media_key': report.media_key, 'reporter_uid': reporter_uid_of(report.source, report.reporter_id),
        'reason': report.reason, 'details': report.details, 'media_creator_uid': report.media_creator_id,
        'status': report.status, 'priority': report.priority, 'created_at': isoformat_madrid(report.created_at),
        'resolved_at': isoformat_madrid(report.resolved_at), 'resolved_by': report.resolved_by_id,
        'action': report.action, 'statement': report.statement, 'source': report.source,
    }


def report_row_to_dict(row: dict, presign) -> dict:
    """Fila de `selectors.list_reports` -> denúncia de l'API amb `media` (MediaItem + `status`) o `None`."""
    media = row['media']
    media_item = None
    if media is not None:
        media_item = media_to_dict(media, presign)
        media_item['status'] = media.status
    return {
        'id': str(row['id']),
        'refuge_id': str(row['refuge_id']) if row['refuge_id'] else None,
        'media_key': row['media_key'],
        'reporter_uid': reporter_uid_of(row['source'], row['reporter_uid']),
        'reason': row['reason'],
        'details': row['details'],
        'media_creator_uid': row['media_creator_uid'],
        'status': row['status'],
        'priority': row['priority'],
        'created_at': isoformat_madrid(row['created_at']),
        'resolved_at': isoformat_madrid(row['resolved_at']),
        'resolved_by': row['resolved_by'],
        'action': row['action'],
        'statement': row['statement'],
        'source': row['source'],
        'media': media_item,
    }


def notice_to_dict(notice) -> dict:
    return {
        'id': str(notice.pk),
        'uid': notice.user_id,
        'type': notice.type,
        'statement': notice.statement,
        'created_at': isoformat_madrid(notice.created_at),
        'refuge_id': str(notice.refuge_id) if notice.refuge_id else None,
        'media_key': notice.media_key,
        'reason': notice.reason,
        'action': notice.action,
        'report_id': str(notice.report_id) if notice.report_id else None,
        'automated': notice.automated,
        'strikes': notice.strikes,
        'redress': REDRESS_TEXT,
    }
