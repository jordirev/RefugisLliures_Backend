"""
Serializers per a la gestió de propostes de refugis
"""
from rest_framework import serializers
from ..utils.timezone_utils import get_madrid_today
from .refugi_lliure_serializer import CoordinatesSerializer, InfoComplementariaSerializer


class RefugeProposalPayloadSerializer(serializers.Serializer):
    """Serializer per validar el payload d'una proposta de refugi"""
    # Camps obligatoris per CREATE (opcionals per UPDATE)
    name = serializers.CharField(required=False, allow_blank=False)
    coord = CoordinatesSerializer(required=False)
    
    # Camps opcionals
    altitude = serializers.IntegerField(required=False, allow_null=True, min_value=0, max_value=8848)
    places = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    remarque = serializers.CharField(required=False, allow_blank=True, default='')
    info_comp = InfoComplementariaSerializer(required=False)
    description = serializers.CharField(required=False, allow_blank=True, default='')
    links = serializers.ListField(child=serializers.URLField(), required=False, default=list)
    type = serializers.ChoiceField(choices=['non gardé', 'fermée', 'cabane ouverte mais occupee par le berger l ete', 'orri'], required=False, default='non gardé')
    region = serializers.CharField(required=False, allow_null=True)
    departement = serializers.CharField(required=False, allow_null=True)
    
    def validate(self, data):
        """Validació extra del payload"""
        # Comprovar que no hi ha camps prohibits
        forbidden_fields = ['images_metadata', 'visitors', 'id', 'modified_at']
        for field in forbidden_fields:
            if field in data:
                raise serializers.ValidationError({
                    field: f"El camp '{field}' no pot estar present al payload de la proposta"
                })
        
        # Validar info_comp si està present
        if 'info_comp' in data and data['info_comp']:
            allowed_info_comp_fields = {
                'manque_un_mur', 'cheminee', 'poele', 'couvertures', 'latrines',
                'bois', 'eau', 'matelas', 'couchage', 'bas_flancs', 'lits', 'mezzanine/etage'
            }
            info_comp = data['info_comp']
            if isinstance(info_comp, dict):
                unknown_fields = set(info_comp.keys()) - allowed_info_comp_fields
                if unknown_fields:
                    raise serializers.ValidationError({
                        'info_comp': f"Camps no permesos en info_comp: {', '.join(unknown_fields)}. "
                                    f"Camps permesos: {', '.join(sorted(allowed_info_comp_fields))}"
                    })
        
        return data
    
    def validate_unknown_fields(self, data):
        """Valida que no hi hagi camps desconeguts al payload"""
        # Camps permesos al payload
        allowed_fields = {
            'name', 'coord', 'altitude', 'places', 'remarque', 'info_comp',
            'description', 'links', 'type', 'region', 'departement'
        }
        
        unknown_fields = set(data.keys()) - allowed_fields
        if unknown_fields:
            raise serializers.ValidationError(
                f"Camps no permesos al payload: {', '.join(unknown_fields)}. "
                f"Camps permesos: {', '.join(sorted(allowed_fields))}"
            )
        
        return data


class RefugeProposalCreateSerializer(serializers.Serializer):
    """Serializer per crear una proposta de refugi"""
    refuge_id = serializers.CharField(required=False, allow_null=True, help_text="ID del refugi (null per CREATE)")
    action = serializers.ChoiceField(choices=['create', 'update', 'delete'], help_text="Tipus d'acció: create, update o delete")
    payload = serializers.DictField(required=False, allow_null=True, help_text="Dades del refugi (requerit per CREATE i UPDATE)")
    comment = serializers.CharField(required=False, allow_null=True, allow_blank=True, help_text="Comentari opcional per ajudar als admins")
    
    def validate(self, data):
        """Validació dels camps segons l'acció"""
        action = data.get('action')
        refuge_id = data.get('refuge_id')
        payload = data.get('payload')
        
        # Validació per CREATE: no ha de tenir refuge_id, però sí payload
        if action == 'create':
            if refuge_id:
                raise serializers.ValidationError({
                    'refuge_id': "El camp 'refuge_id' no ha d'estar present per a l'acció 'create'"
                })
            if not payload:
                raise serializers.ValidationError({
                    'payload': "El camp 'payload' és obligatori per a l'acció 'create'"
                })
            
            # Validar que el payload per CREATE té els camps obligatoris
            if 'name' not in payload or not payload['name']:
                raise serializers.ValidationError({
                    'payload': "El camp 'name' és obligatori al payload per a l'acció 'create'"
                })
            if 'coord' not in payload:
                raise serializers.ValidationError({
                    'payload': "El camp 'coord' és obligatori al payload per a l'acció 'create'"
                })
        
        # Validació per UPDATE: ha de tenir refuge_id i payload
        elif action == 'update':
            if not refuge_id:
                raise serializers.ValidationError({
                    'refuge_id': "El camp 'refuge_id' és obligatori per a l'acció 'update'"
                })
            if not payload:
                raise serializers.ValidationError({
                    'payload': "El camp 'payload' és obligatori per a l'acció 'update'"
                })
        
        # Validació per DELETE: ha de tenir refuge_id, no ha de tenir payload
        elif action == 'delete':
            if not refuge_id:
                raise serializers.ValidationError({
                    'refuge_id': "El camp 'refuge_id' és obligatori per a l'acció 'delete'"
                })
            if payload:
                raise serializers.ValidationError({
                    'payload': "El camp 'payload' no ha d'estar present per a l'acció 'delete'"
                })
        
        # Validar l'estructura del payload si existeix
        if payload and (action in ['create', 'update']):
            # Primer validar que no hi hagi camps desconeguts
            allowed_payload_fields = {
                'name', 'coord', 'altitude', 'places', 'remarque', 'info_comp',
                'description', 'links', 'type', 'region', 'departement'
            }
            unknown_fields = set(payload.keys()) - allowed_payload_fields
            if unknown_fields:
                raise serializers.ValidationError({
                    'payload': f"Camps no permesos al payload: {', '.join(sorted(unknown_fields))}. "
                              f"Camps permesos: {', '.join(sorted(allowed_payload_fields))}"
                })
            
            # Validar info_comp si està present
            if 'info_comp' in payload and payload['info_comp']:
                allowed_info_comp_fields = {
                    'manque_un_mur', 'cheminee', 'poele', 'couvertures', 'latrines',
                    'bois', 'eau', 'matelas', 'couchage', 'bas_flancs', 'lits', 'mezzanine/etage'
                }
                info_comp = payload['info_comp']
                if isinstance(info_comp, dict):
                    unknown_info_comp_fields = set(info_comp.keys()) - allowed_info_comp_fields
                    if unknown_info_comp_fields:
                        raise serializers.ValidationError({
                            'payload': {
                                'info_comp': f"Camps no permesos en info_comp: {', '.join(sorted(unknown_info_comp_fields))}. "
                                           f"Camps permesos: {', '.join(sorted(allowed_info_comp_fields))}"
                            }
                        })
            
            # Després validar amb el serializer
            payload_serializer = RefugeProposalPayloadSerializer(data=payload)
            if not payload_serializer.is_valid():
                raise serializers.ValidationError({
                    'payload': payload_serializer.errors
                })
        
        return data


class RefugeProposalResponseSerializer(serializers.Serializer):
    """Serializer per la resposta de les propostes de refugi"""
    id = serializers.CharField()
    refuge_id = serializers.CharField(allow_null=True)
    action = serializers.CharField()
    payload = serializers.DictField(allow_null=True)
    comment = serializers.CharField(allow_null=True)
    status = serializers.CharField()
    creator_uid = serializers.CharField()
    created_at = serializers.CharField()
    reviewer_uid = serializers.CharField(allow_null=True)
    reviewed_at = serializers.CharField(allow_null=True)
    rejection_reason = serializers.CharField(allow_null=True, required=False)


class RefugeProposalRejectSerializer(serializers.Serializer):
    """Serializer per rebutjar una proposta"""
    reason = serializers.CharField(required=False, allow_blank=True, help_text="Raó del rebuig")
