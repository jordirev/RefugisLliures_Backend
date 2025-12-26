"""
Serializers per a l'API de visites a refugis
"""
from rest_framework import serializers


class UserVisitSerializer(serializers.Serializer):
    """Serializer per a un visitant i el nombre de persones que l'acompanyen"""
    uid = serializers.CharField(
        required=True,
        help_text="UID de l'usuari visitant"
    )
    num_visitors = serializers.IntegerField(
        required=True,
        min_value=1,
        help_text="Nombre de persones que visitaran el refugi"
    )


class RefugeVisitSerializer(serializers.Serializer):
    """Serializer per a visites a refugis"""
    date = serializers.DateField(
        required=True,
        help_text="Data de la visita (format YYYY-MM-DD)"
    )
    refuge_id = serializers.CharField(
        required=True,
        help_text="ID del refugi"
    )
    visitors = UserVisitSerializer(
        many=True,
        required=False,
        allow_null=True,
        help_text="Llista de visitants"
    )
    total_visitors = serializers.IntegerField(
        required=False,
        default=0,
        min_value=0,
        help_text="Nombre total de visitants"
    )


class RefugeVisitListSerializer(serializers.Serializer):
    """Serializer per a la llista de visites a refugis (resposta GET)"""
    date = serializers.DateField(
        help_text="Data de la visita (format YYYY-MM-DD)"
    )
    refuge_id = serializers.CharField(
        required=False,
        help_text="ID del refugi (només per user visits)"
    )
    total_visitors = serializers.IntegerField(
        help_text="Nombre total de visitants"
    )
    is_visitor = serializers.SerializerMethodField(
        help_text="Indica si l'usuari autenticat està registrat a aquesta visita"
    )
    num_visitors = serializers.SerializerMethodField(
        help_text="Nombre de visitants de l'usuari autenticat (0 si no està registrat)"
    )
    
    def get_is_visitor(self, obj):
        """Comprova si l'usuari autenticat està a la llista de visitors"""
        user_uid = self.context.get('user_uid')
        if not user_uid or not obj.visitors:
            return False
        
        for visitor in obj.visitors:
            if visitor.uid == user_uid:
                return True
        return False
    
    def get_num_visitors(self, obj):
        """Obté el nombre de visitants de l'usuari autenticat"""
        user_uid = self.context.get('user_uid')
        if not user_uid or not obj.visitors:
            return 0
        
        for visitor in obj.visitors:
            if visitor.uid == user_uid:
                return visitor.num_visitors
        return 0


class CreateRefugeVisitSerializer(serializers.Serializer):
    """Serializer per crear una visita a un refugi (POST)"""
    num_visitors = serializers.IntegerField(
        required=True,
        min_value=1,
        help_text="Nombre de persones que visitaran el refugi"
    )


class UpdateRefugeVisitSerializer(serializers.Serializer):
    """Serializer per actualitzar una visita a un refugi (PATCH)"""
    num_visitors = serializers.IntegerField(
        required=True,
        min_value=1,
        help_text="Nombre de persones que visitaran el refugi"
    )
