"""
Serializers per a la gestió de refugis
"""
from rest_framework import serializers

class CoordinatesSerializer(serializers.Serializer):
    """Serializer per a coordenades"""
    long = serializers.FloatField()
    lat = serializers.FloatField()

class InfoComplementariaSerializer(serializers.Serializer):
    """Serializer per a informació complementària"""
    manque_un_mur = serializers.IntegerField(default=0)
    cheminee = serializers.IntegerField(default=0)
    poele = serializers.IntegerField(default=0)
    couvertures = serializers.IntegerField(default=0)
    latrines = serializers.IntegerField(default=0)
    bois = serializers.IntegerField(default=0)
    eau = serializers.IntegerField(default=0)
    matelas = serializers.IntegerField(default=0)
    couchage = serializers.IntegerField(default=0)
    bas_flancs = serializers.IntegerField(default=0)
    lits = serializers.IntegerField(default=0)
    mezzanine_etage = serializers.IntegerField(default=0)

class RefugeMediaMetadataSerializer(serializers.Serializer):
    """Serializer per a metadades de mitjans"""
    key = serializers.CharField()
    url = serializers.URLField()
    creator_uid = serializers.CharField()
    uploaded_at = serializers.CharField()  # ISO 8601 format

class RefugiSerializer(serializers.Serializer):
    """Serializer per a refugi"""
    id = serializers.CharField()
    name = serializers.CharField()
    coord = CoordinatesSerializer()
    altitude = serializers.IntegerField(default=None, allow_null=True)
    places = serializers.IntegerField(default=None, allow_null=True)
    remarque = serializers.CharField(default='', allow_blank=True)
    info_comp = InfoComplementariaSerializer()
    description = serializers.CharField(default='', allow_blank=True)
    links = serializers.ListField(child=serializers.URLField(), default=list)
    type = serializers.CharField(default='no guardat')
    modified_at = serializers.CharField(default=None, allow_null=True)
    region = serializers.CharField(default=None, allow_null=True, required=False)
    departement = serializers.CharField(default=None, allow_null=True, required=False)
    condition = serializers.IntegerField(default=None, allow_null=True, required=False, min_value=0, max_value=3)
    visitors = serializers.ListField(child=serializers.CharField(), default=list, required=False)
    images_metadata = RefugeMediaMetadataSerializer(many=True, required=False, allow_null=True)

    def to_representation(self, instance):
        data = super().to_representation(instance)

        # Arrodonir la condition cap a l'enter més proper
        if 'condition' in data and data['condition'] is not None:
            try:
                data['condition'] = round(float(data['condition']))
            except (TypeError, ValueError):
                pass  # Mantenir el valor original si no es pot convertir

        # Eliminem  informació sensible si l'usuari no està autenticat
        is_authenticated = self.context.get('is_authenticated', False)
        if not is_authenticated:
            if 'visitors' in data:
                data.pop('visitors', None)
            if 'media_metadata' in data:
                data.pop('media_metadata', None)
            if 'images_metadata' in data:
                data.pop('images_metadata', None)
        return data

class RefugiSearchResponseSerializer(serializers.Serializer):
    """Serializer per a resposta de cerca"""
    count = serializers.IntegerField()
    results = RefugiSerializer(many=True)

class RefugiSearchFiltersSerializer(serializers.Serializer):
    """Serializer per a filtres de cerca"""
    # Text search
    name = serializers.CharField(required=False, default='', allow_blank=True)

    # Characteristics filters - accepten strings amb comes o llistes
    type = serializers.CharField(
        required=False,
        allow_blank=True,
        default='',
        help_text="Comma-separated list of refuge types to filter by"
    )
    condition = serializers.CharField(
        required=False,
        allow_blank=True,
        default='',
        help_text="Comma-separated list of conditions to filter by (0: pobre, 1: correcte, 2: bé)"
    )
    
    # Numeric range filters
    places_min = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    places_max = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    altitude_min = serializers.IntegerField(required=False, allow_null=True, min_value=0, max_value=8848)
    altitude_max = serializers.IntegerField(required=False, allow_null=True, min_value=0, max_value=8848)
    
    def _validate_range(self, min_value, max_value, field_prefix):
        if min_value is not None and min_value < 0:
            raise serializers.ValidationError({
                f'{field_prefix}_min': f'{field_prefix}_min ha de ser un enter positiu'
            })
        if max_value is not None and max_value < 0:
            raise serializers.ValidationError({
                f'{field_prefix}_max': f'{field_prefix}_max ha de ser un enter positiu'
            })
        if min_value is not None and max_value is not None and min_value > max_value:
            raise serializers.ValidationError({
                f'{field_prefix}_min': f'{field_prefix}_min ha de ser menor o igual que {field_prefix}_max'
            })
    
    def validate(self, data):
        """Validació personalitzada per assegurar que min < max i que siguin enters positius"""
        # Convertir type i condition de strings amb comes a llistes
        VALID_TYPES = ['non gardé', 'fermée', 'cabane ouverte mais ocupee par le berger l ete', 'orri']
        
        if 'type' in data and isinstance(data['type'], str):
            if data['type'].strip():
                data['type'] = [t.strip() for t in data['type'].split(',') if t.strip()]
                # Validar que els valors de type són vàlids
                for t in data['type']:
                    if t not in VALID_TYPES:
                        raise serializers.ValidationError({
                            'type': f'El valor "{t}" no és vàlid. Els valors permesos són: {", ".join(VALID_TYPES)}'
                        })
            else:
                data['type'] = []
        
        if 'condition' in data and isinstance(data['condition'], str):
            if data['condition'].strip():
                try:
                    data['condition'] = [int(c.strip()) for c in data['condition'].split(',') if c.strip() and (c != '' or c != '--')]

                except ValueError:
                    raise serializers.ValidationError({
                        'condition': 'condition ha de contenir només enters (0, 1 o 2) separats per comes'
                    })
                
                # Validar que els valors de condition són vàlids
                for c in data['condition']:
                    if c not in [0, 1, 2]:
                        raise serializers.ValidationError({
                            'condition': 'Els valors de condition han de ser 0 (pobre), 1 (correcte) o 2 (bé)'
                        })
            else:
                data['condition'] = []
        
        places_min = data.get('places_min')
        places_max = data.get('places_max')
        self._validate_range(places_min, places_max, 'places')
        
        altitude_min = data.get('altitude_min')
        altitude_max = data.get('altitude_max')
        self._validate_range(altitude_min, altitude_max, 'altitude')
        
        return data

class UserRefugiInfoSerializer(serializers.Serializer):
    """Serializer per a llistar refugis preferits o visitats amb informació resumida"""
    
    id = serializers.CharField(
        help_text="Identificador únic del refugi"
    )
    name = serializers.CharField(
        help_text="Nom del refugi"
    )
    region = serializers.CharField(
        help_text="Regió del refugi"
    )
    places = serializers.IntegerField(
        help_text="Nombre de places del refugi"
    )
    coord = CoordinatesSerializer(
        help_text="Coordenades del refugi"
    )

class UserRefugiInfoResponseSerializer(serializers.Serializer):
    """Serializer per a resposta de llistar refugis preferits o visitats"""
    
    count = serializers.IntegerField(
        help_text="Nombre total de refugis en la llista"
    )
    results = UserRefugiInfoSerializer(
        many=True,
        help_text="Llista de refugis amb informació resumida"
    )

class HealthCheckResponseSerializer(serializers.Serializer):
    """Serializer per a resposta de health check"""
    status = serializers.CharField()
    message = serializers.CharField()
    firebase = serializers.BooleanField()
    firestore = serializers.BooleanField(required=False)
    collections_count = serializers.IntegerField(required=False)