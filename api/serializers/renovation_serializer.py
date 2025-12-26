"""
Serializers per a l'API de renovations
"""
from rest_framework import serializers
from ..models.renovation import Renovation
from ..utils.timezone_utils import get_madrid_today


class DateValidationMixin:
    """Mixin per a validació de dates de renovations"""
    
    @staticmethod
    def validate_dates(ini_date, fin_date):
        """
        Valida que la data d'inici sigui anterior a la de finalització
        
        Args:
            ini_date: Data d'inici
            fin_date: Data de finalització
            
        Raises:
            serializers.ValidationError: Si les dates no són vàlides
        """
        if ini_date >= fin_date:
            raise serializers.ValidationError({
                'fin_date': "La data de finalització ha de ser posterior a la data d'inici"
            })
    
    @staticmethod
    def validate_ini_date_is_current_or_future(ini_date):
        """
        Valida que la data d'inici sigui igual o posterior a la data actual (zona horaria Madrid)
        
        Args:
            ini_date: Data d'inici
            
        Raises:
            serializers.ValidationError: Si la data d'inici és anterior a la data actual
        """
        madrid_today = get_madrid_today()
        if ini_date < madrid_today:
            raise serializers.ValidationError({
                'ini_date': f"La data d'inici ha de ser igual o posterior a la data actual ({madrid_today.strftime('%Y-%m-%d')})"
            })


class RenovationSerializer(serializers.Serializer, DateValidationMixin):
    """Serializer per a renovations"""
    
    id = serializers.CharField(
        max_length=255,
        help_text="Identificador únic de la reforma",
        read_only=True
    )
    creator_uid = serializers.CharField(
        max_length=255,
        help_text="UID del creador de la reforma",
        read_only=True
    )
    refuge_id = serializers.CharField(
        max_length=255,
        help_text="ID del refugi a reformar"
    )
    ini_date = serializers.DateField(
        help_text="Data d'inici de la reforma",
        format="%Y-%m-%d",
        input_formats=['%Y-%m-%d', 'iso-8601']
    )
    fin_date = serializers.DateField(
        help_text="Data de finalització de la reforma",
        format="%Y-%m-%d",
        input_formats=['%Y-%m-%d', 'iso-8601']
    )
    description = serializers.CharField(
        help_text="Descripció de la reforma"
    )
    materials_needed = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="Materials necessaris per a la reforma"
    )
    group_link = serializers.URLField(
        help_text="Enllaç al grup de coordinació (WhatsApp/Telegram)"
    )
    participants_uids = serializers.ListField(
        child=serializers.CharField(),
        help_text="UIDs dels participants a la reforma",
        read_only=True
    )
    expelled_uids = serializers.ListField(
        child=serializers.CharField(),
        help_text="UIDs dels usuaris expulsats pel creador",
        read_only=True
    )
    
    def validate(self, data):
        """Validació general de les dades"""
        if 'ini_date' in data and 'fin_date' in data:
            self.validate_dates(data['ini_date'], data['fin_date'])
        return data
    
    def to_representation(self, instance):
        """Converteix instància a representació JSON"""
        if isinstance(instance, Renovation):
            data = instance.to_dict()
            # Convertir dates ISO a format de només data
            if 'ini_date' in data:
                data['ini_date'] = data['ini_date'][:10]
            if 'fin_date' in data:
                data['fin_date'] = data['fin_date'][:10]
            return data
        return super().to_representation(instance)
    
    def create(self, validated_data):
        """Crea una nova instància de renovation"""
        return Renovation(**validated_data)
    
    def update(self, instance, validated_data):
        """Actualitza una instància de renovation"""
        # Camps que no es poden actualitzar
        validated_data.pop('creator_uid', None)
        validated_data.pop('refuge_id', None)
        
        instance.ini_date = validated_data.get('ini_date', instance.ini_date)
        instance.fin_date = validated_data.get('fin_date', instance.fin_date)
        instance.description = validated_data.get('description', instance.description)
        instance.materials_needed = validated_data.get('materials_needed', instance.materials_needed)
        instance.group_link = validated_data.get('group_link', instance.group_link)
        return instance


class RenovationCreateSerializer(serializers.Serializer, DateValidationMixin):
    """Serializer per a creació de renovations"""
    
    refuge_id = serializers.CharField(
        max_length=255,
        help_text="ID del refugi a reformar"
    )
    ini_date = serializers.DateField(
        help_text="Data d'inici de la reforma",
        format="%Y-%m-%d",
        input_formats=['%Y-%m-%d', 'iso-8601']
    )
    fin_date = serializers.DateField(
        help_text="Data de finalització de la reforma",
        format="%Y-%m-%d",
        input_formats=['%Y-%m-%d', 'iso-8601']
    )
    description = serializers.CharField(
        help_text="Descripció de la reforma"
    )
    materials_needed = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="Materials necessaris per a la reforma"
    )
    group_link = serializers.URLField(
        help_text="Enllaç al grup de coordinació (WhatsApp/Telegram)"
    )
    
    def validate(self, data):
        """Validació general de les dades"""
        self.validate_dates(data['ini_date'], data['fin_date'])
        self.validate_ini_date_is_current_or_future(data['ini_date'])
        return data


class RenovationUpdateSerializer(serializers.Serializer, DateValidationMixin):
    """Serializer per a actualització de renovations"""
    
    ini_date = serializers.DateField(
        required=False,
        help_text="Data d'inici de la reforma",
        format="%Y-%m-%d",
        input_formats=['%Y-%m-%d', 'iso-8601']
    )
    fin_date = serializers.DateField(
        required=False,
        help_text="Data de finalització de la reforma",
        format="%Y-%m-%d",
        input_formats=['%Y-%m-%d', 'iso-8601']
    )
    description = serializers.CharField(
        required=False,
        help_text="Descripció de la reforma"
    )
    materials_needed = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="Materials necessaris per a la reforma"
    )
    group_link = serializers.URLField(
        required=False,
        allow_null=True,
        help_text="Enllaç al grup de coordinació (WhatsApp/Telegram)"
    )
    
    def validate(self, data):
        """Validació general de les dades"""
        if 'ini_date' in data and 'fin_date' in data:
            self.validate_dates(data['ini_date'], data['fin_date'])
        if 'ini_date' in data:
            self.validate_ini_date_is_current_or_future(data['ini_date'])
        return data
