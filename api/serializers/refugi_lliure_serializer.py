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
    filters = serializers.DictField()

class RefugiCoordinatesResponseSerializer(serializers.Serializer):
    """Serializer per a resposta de coordenades"""
    count = serializers.IntegerField()
    total_available = serializers.IntegerField()
    coordinates = RefugiCoordinatesSerializer(many=True)

class HealthCheckResponseSerializer(serializers.Serializer):
    """Serializer per a resposta de health check"""
    status = serializers.CharField()
    message = serializers.CharField()
    firebase = serializers.BooleanField()
    firestore = serializers.BooleanField(required=False)
    collections_count = serializers.IntegerField(required=False)

class RefugiSearchFiltersSerializer(serializers.Serializer):
    """Serializer per a filtres de cerca"""
    q = serializers.CharField(required=False, default='', allow_blank=True)
    limit = serializers.IntegerField(required=False, default=10, min_value=1, max_value=100)

class RefugiCoordinatesFiltersSerializer(serializers.Serializer):
    """Serializer per a filtres de coordenades"""
    limit = serializers.IntegerField(required=False, default=1000, min_value=1, max_value=1000)