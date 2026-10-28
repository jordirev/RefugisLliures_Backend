"""
Serializers de `proposals`: contracte JSON de l'API (docs/design/postgres-schema.md §2.18) i validació de l'entrada.

Es conserven les regles i els missatges d'abans. Serializer, model i `CHECK` apliquen les mateixes regles (GOTCHAS #5):
els límits que la BD imposaria en aprovar (nom/regió/departament <= 255, `places` <= 2**31-1, latitud/longitud en rang i
fora de (0, 0), enllaços http(s) únics i <= 2048, `info_comp` 0/1, payload < 64 KiB, `type` del catàleg) es comproven
aquí perquè una aprovació no acabi en un 500 (D39).

El payload validat només porta **les claus enviades** i amb els tipus coercits (M9: `"1200"` -> `1200`): en un
`update`, «absent» i `null` són coses diferents (`null` = «buida'l»). No s'hi injecta cap valor per defecte.
"""
import json
import math

from rest_framework import serializers

from apps.refuges.models import RefugeAmenities
from apps.refuges.selectors import refuge_type_codes
from apps.refuges.serializers import isoformat_madrid

from .models import COMMENT_MAX_LENGTH, REASON_MAX_LENGTH, Action, Status

UNKNOWN_CREATOR = 'unknown'
INT_MAX = 2 ** 31 - 1
MAX_PAYLOAD_BYTES = 60 * 1024                 # la BD limita el `jsonb` a < 64 KiB (`refuge_proposals_size_ck`)
URL_MAX_LENGTH = 2048

ALLOWED_INFO_COMP_FIELDS = frozenset(RefugeAmenities.AMENITY_FIELDS)
# Llista blanca de camps (sense `remarque`, S-6); `images_metadata`, `visitors`, `id` i `modified_at` hi són prohibits.
ALLOWED_REFUGE_FIELDS = frozenset({'name', 'coord', 'altitude', 'places', 'info_comp', 'description', 'links', 'type',
                                   'region', 'departement', 'condition'})


# ---------- Payload ----------

class CoordSerializer(serializers.Serializer):
    long = serializers.FloatField(min_value=-180, max_value=180)
    lat = serializers.FloatField(min_value=-90, max_value=90)

    def validate(self, data):
        if not (math.isfinite(data['long']) and math.isfinite(data['lat'])):
            raise serializers.ValidationError('Coordenades no vàlides')
        if data['long'] == 0 and data['lat'] == 0:
            raise serializers.ValidationError('El punt (0, 0) no és una coordenada vàlida')
        return data


class InfoCompSerializer(serializers.Serializer):
    """Només les 12 claus d'`info_comp`, com a 0/1; les enviades es conserven (no se n'afegeix cap de buida)."""
    manque_un_mur = serializers.IntegerField(required=False, min_value=0, max_value=1)
    cheminee = serializers.IntegerField(required=False, min_value=0, max_value=1)
    poele = serializers.IntegerField(required=False, min_value=0, max_value=1)
    couvertures = serializers.IntegerField(required=False, min_value=0, max_value=1)
    latrines = serializers.IntegerField(required=False, min_value=0, max_value=1)
    bois = serializers.IntegerField(required=False, min_value=0, max_value=1)
    eau = serializers.IntegerField(required=False, min_value=0, max_value=1)
    matelas = serializers.IntegerField(required=False, min_value=0, max_value=1)
    couchage = serializers.IntegerField(required=False, min_value=0, max_value=1)
    bas_flancs = serializers.IntegerField(required=False, min_value=0, max_value=1)
    lits = serializers.IntegerField(required=False, min_value=0, max_value=1)
    mezzanine_etage = serializers.IntegerField(required=False, min_value=0, max_value=1)


class LinkField(serializers.URLField):
    """Enllaç http(s) d'<= 2048 caràcters (el `CHECK` de `refuge_links`; el `URLValidator` també accepta `ftp`)."""

    def __init__(self, **kwargs):
        super().__init__(max_length=URL_MAX_LENGTH, **kwargs)

    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        if not value.lower().startswith(('http://', 'https://')):
            self.fail('invalid')
        return value


class PayloadSerializer(serializers.Serializer):
    """Camps del refugi d'una proposta; tots opcionals (la obligatorietat depèn de l'acció)."""
    name = serializers.CharField(required=False, max_length=255)
    coord = CoordSerializer(required=False)
    altitude = serializers.IntegerField(required=False, allow_null=True, min_value=0, max_value=8848)
    places = serializers.IntegerField(required=False, allow_null=True, min_value=0, max_value=INT_MAX)
    info_comp = InfoCompSerializer(required=False)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    links = serializers.ListField(required=False, child=LinkField(), allow_empty=True)
    type = serializers.CharField(required=False, max_length=64)
    region = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=255)
    departement = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=255)
    condition = serializers.IntegerField(required=False, allow_null=True, min_value=0, max_value=3)

    def validate_links(self, value):
        if len(set(value)) != len(value):
            raise serializers.ValidationError('Hi ha enllaços repetits')
        return value

    def validate_type(self, value):
        if value not in refuge_type_codes():             # catàleg `refuges.refuge_types` (1 consulta)
            raise serializers.ValidationError(f"Tipus de refugi no vàlid: '{value}'")
        return value


def _plain(value):
    """`OrderedDict`/`ReturnDict` imbricats -> `dict`/`list` purs (el que es desa al `jsonb`)."""
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value


def _sorted_names(names):
    return ', '.join(sorted(names))


# ---------- Entrada ----------

class CreateProposalSerializer(serializers.Serializer):
    """`POST /refuges-proposals/`: validació per acció i del payload (només claus de la llista blanca)."""
    refuge_id = serializers.CharField(required=False, allow_null=True, help_text='ID del refugi (null per a create)')
    action = serializers.ChoiceField(choices=Action.values, help_text="Tipus d'acció: create, update o delete")
    payload = serializers.DictField(required=False, allow_null=True,
                                    help_text='Dades del refugi (obligatori per a create i update)')
    comment = serializers.CharField(required=False, allow_null=True, allow_blank=True,
                                    max_length=COMMENT_MAX_LENGTH, help_text='Comentari opcional per als admins')

    def validate(self, data):
        action, refuge_id, payload = data.get('action'), data.get('refuge_id'), data.get('payload')

        if action == Action.CREATE:
            if refuge_id:
                raise serializers.ValidationError(
                    {'refuge_id': "El camp 'refuge_id' no ha d'estar present per a l'acció 'create'"})
            if not payload:
                raise serializers.ValidationError(
                    {'payload': "El camp 'payload' és obligatori per a l'acció 'create'"})
            name = payload.get('name')
            if not isinstance(name, str) or not name.strip():
                raise serializers.ValidationError(
                    {'payload': "El camp 'name' és obligatori al payload per a l'acció 'create'"})
            if 'coord' not in payload:
                raise serializers.ValidationError(
                    {'payload': "El camp 'coord' és obligatori al payload per a l'acció 'create'"})
        elif action == Action.UPDATE:
            if not refuge_id:
                raise serializers.ValidationError(
                    {'refuge_id': "El camp 'refuge_id' és obligatori per a l'acció 'update'"})
            if not payload:
                raise serializers.ValidationError(
                    {'payload': "El camp 'payload' és obligatori per a l'acció 'update'"})
        elif action == Action.DELETE:
            if not refuge_id:
                raise serializers.ValidationError(
                    {'refuge_id': "El camp 'refuge_id' és obligatori per a l'acció 'delete'"})
            if payload:
                raise serializers.ValidationError(
                    {'payload': "El camp 'payload' no ha d'estar present per a l'acció 'delete'"})

        data['payload'] = self._clean_payload(payload) if action in (Action.CREATE, Action.UPDATE) else None
        return data

    @staticmethod
    def _clean_payload(payload):
        unknown = set(payload) - ALLOWED_REFUGE_FIELDS
        if unknown:
            raise serializers.ValidationError({
                'payload': f'Camps no permesos al payload: {_sorted_names(unknown)}. '
                           f'Camps permesos: {_sorted_names(ALLOWED_REFUGE_FIELDS)}'})
        info_comp = payload.get('info_comp')
        if isinstance(info_comp, dict) and set(info_comp) - ALLOWED_INFO_COMP_FIELDS:
            bad = _sorted_names(set(info_comp) - ALLOWED_INFO_COMP_FIELDS)
            raise serializers.ValidationError({'payload': {
                'info_comp': f'Camps no permesos en info_comp: {bad}. '
                             f'Camps permesos: {_sorted_names(ALLOWED_INFO_COMP_FIELDS)}'}})
        serializer = PayloadSerializer(data=payload)
        if not serializer.is_valid():
            raise serializers.ValidationError({'payload': serializer.errors})
        cleaned = _plain(serializer.validated_data)
        if len(json.dumps(cleaned, ensure_ascii=False).encode('utf-8')) > MAX_PAYLOAD_BYTES:
            raise serializers.ValidationError({'payload': 'El payload és massa gran (màxim 60 KiB)'})
        return cleaned


class RejectProposalSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=REASON_MAX_LENGTH,
                                   help_text='Motiu del rebuig')


# ---------- Sortida ----------

class ProposalSerializer(serializers.Serializer):
    """
    Proposta tal com la dona l'API. `instance` és un `RefugeProposal`; `creator_uid` `NULL` (usuari esborrat) -> `'unknown'`.
    Les dates són ISO 8601 amb el desplaçament de Madrid; `payload` i `refuge_snapshot` es retornen tal com es van desar.
    """
    id = serializers.CharField()
    refuge_id = serializers.CharField(allow_null=True)
    refuge_snapshot = serializers.DictField(allow_null=True)
    action = serializers.CharField()
    payload = serializers.DictField(allow_null=True)
    comment = serializers.CharField(allow_null=True)
    status = serializers.ChoiceField(choices=Status.values)
    creator_uid = serializers.CharField()
    created_at = serializers.CharField()
    reviewer_uid = serializers.CharField(allow_null=True)
    reviewed_at = serializers.CharField(allow_null=True)
    rejection_reason = serializers.CharField(allow_null=True)

    def to_representation(self, instance):
        return {
            'id': str(instance.pk),
            'refuge_id': str(instance.refuge_id) if instance.refuge_id else None,
            'refuge_snapshot': instance.refuge_snapshot,
            'action': instance.action,
            'payload': instance.payload,
            'comment': instance.comment,
            'status': instance.status,
            'creator_uid': instance.creator_id or UNKNOWN_CREATOR,
            'created_at': isoformat_madrid(instance.created_at),
            'reviewer_uid': instance.reviewer_id,
            'reviewed_at': isoformat_madrid(instance.reviewed_at),
            'rejection_reason': instance.rejection_reason,
        }
