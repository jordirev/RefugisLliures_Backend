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
    images_metadata = RefugeMediaMetadataSerializer(
        many=True,
        required=False,
        allow_null=True,
        help_text="Metadades de la imatge principal del refugi"
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
    database = serializers.BooleanField(required=False)