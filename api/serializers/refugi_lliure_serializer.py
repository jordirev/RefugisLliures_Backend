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
    mezzanine_etage = serializers.IntegerField(default=0, source='mezzanine/etage')

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

class RefugiCoordinatesSerializer(serializers.Serializer):
    """Serializer per a coordenades de refugi"""
    refugi_id = serializers.CharField()
    refugi_name = serializers.CharField()
    coordinates = CoordinatesSerializer()
    geohash = serializers.CharField(default=None, allow_null=True)

class RefugiSearchResponseSerializer(serializers.Serializer):
    """Serializer per a resposta de cerca"""
    count = serializers.IntegerField()
    results = RefugiSerializer(many=True)


class HealthCheckResponseSerializer(serializers.Serializer):
    """Serializer per a resposta de health check"""
    status = serializers.CharField()
    message = serializers.CharField()
    firebase = serializers.BooleanField()
    firestore = serializers.BooleanField(required=False)
    collections_count = serializers.IntegerField(required=False)

class RefugiSearchFiltersSerializer(serializers.Serializer):
    """Serializer per a filtres de cerca"""
    # Text search
    name = serializers.CharField(required=False, default='', allow_blank=True)
    
    # Location filters
    region = serializers.CharField(required=False, default='', allow_blank=True)
    departement = serializers.CharField(required=False, default='', allow_blank=True)

    # Characteristics filters
    type = serializers.CharField(required=False, default='', allow_blank=True)
    
    # Numeric range filters
    places_min = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    places_max = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    altitude_min = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    altitude_max = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    
    # Info complementaria filters (1 = required feature)
    cheminee = serializers.IntegerField(required=False, allow_null=True, min_value=0, max_value=1)
    poele = serializers.IntegerField(required=False, allow_null=True, min_value=0, max_value=1)
    couvertures = serializers.IntegerField(required=False, allow_null=True, min_value=0, max_value=1)
    latrines = serializers.IntegerField(required=False, allow_null=True, min_value=0, max_value=1)
    bois = serializers.IntegerField(required=False, allow_null=True, min_value=0, max_value=1)
    eau = serializers.IntegerField(required=False, allow_null=True, min_value=0, max_value=1)
    matelas = serializers.IntegerField(required=False, allow_null=True, min_value=0, max_value=1)
    couchage = serializers.IntegerField(required=False, allow_null=True, min_value=0, max_value=1)
    lits = serializers.IntegerField(required=False, allow_null=True, min_value=0, max_value=1)
    
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
        places_min = data.get('places_min')
        places_max = data.get('places_max')
        self._validate_range(places_min, places_max, 'places')
        
        altitude_min = data.get('altitude_min')
        altitude_max = data.get('altitude_max')
        self._validate_range(altitude_min, altitude_max, 'altitude')
        
        return data

#class RefugiCoordinatesFiltersSerializer(serializers.Serializer):
    """Serializer per a filtres de coordenades"""
    """Serà util per quan haguem de filtrar per ubicació"""

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
    coordinates = CoordinatesSerializer(
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