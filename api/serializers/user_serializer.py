"""
Serializers per a l'API d'usuaris
"""
from rest_framework import serializers
from ..models.user import User

USERNAME_HELPER_TEXT = "Nom d'usuari"
EMAIL_HELPER_TEXT = "Adreça de correu electrònic"
URL_AVATAR_HELPER_TEXT = "URL de l'avatar de l'usuari"
LANGUAGE_HELPER_TEXT = "Idioma preferit de l'usuari (codi ISO 639-1, ex: 'ca', 'es', 'en', 'fr')"

class UserValidatorMixin:
    """Mixin amb validadors comuns per a usuaris"""
    
    VALID_LANGUAGES = ['ca', 'es', 'en', 'fr']
    
    @staticmethod
    def validate_email_field(value, required=True):
        """Validador reutilitzable per a email"""
        if not value or not value.strip():
            if required:
                raise serializers.ValidationError("Email és requerit")
            return value
        return value.strip().lower()
    
    @staticmethod
    def validate_username_field(value, required=False):
        """Validador reutilitzable per a username"""
        if value is None:
            return "" if not required else None
        
        if value and len(value.strip()) < 2:
            raise serializers.ValidationError("El nom d'usuari ha de tenir almenys 2 caràcters")
        return value.strip() if value else ""
    
    @staticmethod
    def validate_language_field(value, required=False):
        """Validador reutilitzable per a language"""
        if value is None:
            return 'ca' if required else None
            
        if value.strip().lower() not in UserValidatorMixin.VALID_LANGUAGES:
            raise serializers.ValidationError(
                f"Idioma no vàlid. Opcions vàlides: {', '.join(UserValidatorMixin.VALID_LANGUAGES)}"
            )
        return value.strip().lower()
    
    @staticmethod
    def validate_uid_field(value):
        """Validador reutilitzable per a UID"""
        if not value or not value.strip():
            raise serializers.ValidationError("UID no pot estar buit")
        return value.strip()

class MediaMetadataSerializer(serializers.Serializer):
    """Serializer per a metadades de mitjans"""
    key = serializers.CharField()
    url = serializers.URLField()
    uploaded_at = serializers.CharField()  # ISO 8601 formatelp_text="Data i hora de pujada (ISO 8601)"

class UserSerializer(UserValidatorMixin, serializers.Serializer):
    """Serializer per a usuaris"""
    
    uid = serializers.CharField(
        max_length=255, 
        help_text="Identificador únic de l'usuari",
        read_only=True
    )
    username = serializers.CharField(
        max_length=255, 
        allow_blank=True, 
        required=False, 
        help_text=USERNAME_HELPER_TEXT
    )
    email = serializers.EmailField(
        help_text=EMAIL_HELPER_TEXT
    )
    avatar_metadata = MediaMetadataSerializer(
        required=False,
        allow_null=True,
        help_text="Metadades de l'avatar (key, url, uploaded_at)",
        read_only=True
    )
    language = serializers.CharField(
        max_length=5,
        default='ca',
        help_text=LANGUAGE_HELPER_TEXT
    )
    favourite_refuges = serializers.ListField(
        child=serializers.CharField(),
        help_text="Refugis favorits de l'usuari",
        read_only=True
    )
    visited_refuges = serializers.ListField(
        child=serializers.CharField(),
        help_text="Refugis visitats de l'usuari",
        read_only=True
    )
    num_uploaded_photos = serializers.IntegerField(
        help_text="Nombre de fotos pujades per l'usuari",
        read_only=True
    )
    num_shared_experiences = serializers.IntegerField(
        help_text="Nombre d'experiències compartides per l'usuari",
        read_only=True
    )
    num_renovated_refuges = serializers.IntegerField(
        help_text="Nombre de refugis reformats per l'usuari",
        read_only=True
    )
    created_at = serializers.DateTimeField(
        help_text="Data de creació de l'usuari",
        read_only=True
    )

    def validate_uid(self, value):
        return self.validate_uid_field(value)
    
    def validate_email(self, value):
        return self.validate_email_field(value, required=True)
    
    def validate_username(self, value):
        return self.validate_username_field(value, required=False)
    
    def validate_language(self, value):
        return self.validate_language_field(value, required=False)
    
    def to_representation(self, instance):
        """Converteix instància a representació JSON"""
        if isinstance(instance, User):
            return instance.to_dict()
        return super().to_representation(instance)
    
    def create(self, validated_data):
        """Crea una nova instància d'usuari"""
        return User(**validated_data)
    
    def update(self, instance, validated_data):
        """Actualitza una instància d'usuari"""
        instance.username = validated_data.get('username', instance.username)
        instance.email = validated_data.get('email', instance.email)
        instance.avatar = validated_data.get('avatar', instance.avatar)
        return instance

class UserCreateSerializer(UserValidatorMixin, serializers.Serializer):
    """Serializer per a creació d'usuaris"""

    username = serializers.CharField(max_length=255, allow_blank=True, required=False, 
                                   help_text=USERNAME_HELPER_TEXT)
    email = serializers.EmailField(help_text=EMAIL_HELPER_TEXT)
    language = serializers.CharField(default='ca', max_length=5, required=False,
                                help_text=LANGUAGE_HELPER_TEXT)
    
    def validate_email(self, value):
        return self.validate_email_field(value, required=True)
    
    def validate_username(self, value):
        return self.validate_username_field(value, required=False)
    
    def validate_language(self, value):
        return self.validate_language_field(value, required=False)

class UserUpdateSerializer(UserValidatorMixin, serializers.Serializer):
    """Serializer per a actualització d'usuaris"""
    
    username = serializers.CharField(max_length=255, allow_blank=True, required=False, 
                                   help_text=USERNAME_HELPER_TEXT)
    email = serializers.EmailField(required=False, help_text=EMAIL_HELPER_TEXT)
    language = serializers.CharField(default='ca', max_length=5, required=False,
                                help_text=LANGUAGE_HELPER_TEXT)
    
    def validate_email(self, value):
        return self.validate_email_field(value, required=False)
    
    def validate_username(self, value):
        return self.validate_username_field(value, required=False)
    
    def validate_language(self, value):
        return self.validate_language_field(value, required=False)
    
    def validate(self, attrs):
        """Validació global"""
        if not any(attrs.values()):
            raise serializers.ValidationError("Almenys un camp ha de ser proporcionat per actualitzar")
        return attrs
    
class UserRefugiSerializer(serializers.Serializer):
    """Serializer per a afegir/treure refugis preferits o visitats"""
    
    refuge_id = serializers.CharField(
        max_length=255,
        help_text="Identificador únic del refugi"
    )
