"""
Serializers legacy de refugis que encara fan servir altres dominis (usuaris, propostes, experiències, health).
Els serializers de refugi/cerca/mitjans viuen a `apps.refuges.serializers`.
"""
from rest_framework import serializers
from .media_serializer import MediaItemSerializer


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

class RefugeMediaMetadataSerializer(MediaItemSerializer):
    """Serializer per a metadades de mitjans (forma MediaItem del contracte)"""

class HealthCheckResponseSerializer(serializers.Serializer):
    """Serializer per a resposta de health check"""
    status = serializers.CharField()
    message = serializers.CharField()
    firebase = serializers.BooleanField()
    firestore = serializers.BooleanField(required=False)
    collections_count = serializers.IntegerField(required=False)
    database = serializers.BooleanField(required=False)