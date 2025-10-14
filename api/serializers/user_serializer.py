"""
Serializers per a l'API d'usuaris
"""
from rest_framework import serializers
from ..models.user import User

class UserSerializer(serializers.Serializer):
    """Serializer per a usuaris"""
    
    uid = serializers.CharField(max_length=255, help_text="Identificador únic de l'usuari")
    username = serializers.CharField(max_length=255, allow_blank=True, required=False, 
                                   help_text="Nom d'usuari")
    email = serializers.EmailField(help_text="Adreça de correu electrònic")
    avatar = serializers.URLField(allow_blank=True, required=False, 
                                help_text="URL de l'avatar de l'usuari")
    
    def validate_uid(self, value):
        """Validació personalitzada per a UID"""
        if not value or not value.strip():
            raise serializers.ValidationError("UID no pot estar buit")
        return value.strip()
    
    def validate_email(self, value):
        """Validació personalitzada per a email"""
        if not value or not value.strip():
            raise serializers.ValidationError("Email no pot estar buit")
        return value.strip().lower()
    
    def validate_username(self, value):
        """Validació personalitzada per a username"""
        if value and len(value.strip()) < 2:
            raise serializers.ValidationError("El nom d'usuari ha de tenir almenys 2 caràcters")
        return value.strip() if value else ""
    
    def validate_avatar(self, value):
        """Validació personalitzada per a avatar URL"""
        if value and not value.strip():
            return ""
        return value.strip() if value else ""
    
    def to_representation(self, instance):
        """Converteix instància a representació JSON"""
        if isinstance(instance, User):
            return {
                'uid': instance.uid,
                'username': instance.username,
                'email': instance.email,
                'avatar': instance.avatar
            }
        return super().to_representation(instance)
    
    def create(self, validated_data):
        """Crea una nova instància d'usuari"""
        return User(**validated_data)
    
    def update(self, instance, validated_data):
        """Actualitza una instància d'usuari"""
        instance.username = validated_data.get('username', instance.username)
        instance.email = validated_data.get('email', instance.email)
        instance.avatar = validated_data.get('avatar', instance.avatar)
        # UID no es pot actualitzar
        return instance

class UserCreateSerializer(serializers.Serializer):
    """Serializer per a creació d'usuaris"""
    
    uid = serializers.CharField(max_length=255, help_text="Identificador únic de l'usuari")
    username = serializers.CharField(max_length=255, allow_blank=True, required=False, 
                                   help_text="Nom d'usuari")
    email = serializers.EmailField(help_text="Adreça de correu electrònic")
    avatar = serializers.URLField(allow_blank=True, required=False, 
                                help_text="URL de l'avatar de l'usuari")
    
    def validate_uid(self, value):
        """Validació personalitzada per a UID"""
        if not value or not value.strip():
            raise serializers.ValidationError("UID és requerit")
        return value.strip()
    
    def validate_email(self, value):
        """Validació personalitzada per a email"""
        if not value or not value.strip():
            raise serializers.ValidationError("Email és requerit")
        return value.strip().lower()

class UserUpdateSerializer(serializers.Serializer):
    """Serializer per a actualització d'usuaris"""
    
    username = serializers.CharField(max_length=255, allow_blank=True, required=False, 
                                   help_text="Nom d'usuari")
    email = serializers.EmailField(required=False, help_text="Adreça de correu electrònic")
    avatar = serializers.URLField(allow_blank=True, required=False, 
                                help_text="URL de l'avatar de l'usuari")
    
    def validate_email(self, value):
        """Validació personalitzada per a email"""
        if value is not None:
            return value.strip().lower()
        return value
    
    def validate_username(self, value):
        """Validació personalitzada per a username"""
        if value is not None and len(value.strip()) < 2:
            raise serializers.ValidationError("El nom d'usuari ha de tenir almenys 2 caràcters")
        return value.strip() if value else ""
    
    def validate(self, attrs):
        """Validació global"""
        if not any(attrs.values()):
            raise serializers.ValidationError("Almenys un camp ha de ser proporcionat per actualitzar")
        return attrs

class UserListSerializer(serializers.Serializer):
    """Serializer per a llistes d'usuaris amb paginació"""
    
    users = UserSerializer(many=True, help_text="Llista d'usuaris")
    total_count = serializers.IntegerField(help_text="Nombre total d'usuaris")
    has_next = serializers.BooleanField(help_text="Hi ha més usuaris disponibles")
    
class PaginationQuerySerializer(serializers.Serializer):
    """Serializer per a paràmetres de paginació"""
    
    limit = serializers.IntegerField(min_value=1, max_value=100, default=20, 
                                   help_text="Nombre màxim d'usuaris a retornar")
    offset = serializers.IntegerField(min_value=0, default=0, 
                                    help_text="Nombre d'usuaris a saltar")