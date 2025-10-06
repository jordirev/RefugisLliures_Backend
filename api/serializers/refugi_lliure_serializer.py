from rest_framework import serializers
from ..models import RefugiLliure


class RefugiLliureSerializer(serializers.ModelSerializer):
    """
    Serializer per al model RefugiLliure
    """
    
    # Camps calculats
    is_available = serializers.ReadOnlyField()
    
    # Camps amb validació personalitzada
    altitud = serializers.IntegerField(min_value=0, help_text="Altitud en metres")
    capacitat = serializers.IntegerField(min_value=1, help_text="Capacitat de persones")
    
    class Meta:
        model = RefugiLliure
        fields = [
            'id',
            'nom',
            'descripcio',
            'tipus',
            'imatges',
            'ubicacio',
            'regio',
            'altitud',
            'capacitat',
            'estat',
            'serveis',
            'clau_necessaria',
            'tancat',
            'is_available',
            'created_at',
            'modified_at'
        ]
        read_only_fields = ['id', 'created_at', 'modified_at', 'is_available']
    
    def validate_nom(self, value):
        """
        Validació personalitzada per al nom
        """
        if len(value.strip()) < 3:
            raise serializers.ValidationError(
                "El nom del refugi ha de tenir almenys 3 caràcters."
            )
        return value.strip()
    
    def validate_descripcio(self, value):
        """
        Validació personalitzada per a la descripció
        """
        if len(value.strip()) < 10:
            raise serializers.ValidationError(
                "La descripció ha de tenir almenys 10 caràcters."
            )
        return value.strip()
    
    def validate_imatges(self, value):
        """
        Validació personalitzada per a les imatges
        """
        if not isinstance(value, list):
            raise serializers.ValidationError(
                "Les imatges han de ser una llista."
            )
        
        # Validar que siguin URLs vàlides o paths
        for imatge in value:
            if not isinstance(imatge, str) or len(imatge.strip()) == 0:
                raise serializers.ValidationError(
                    "Cada imatge ha de ser una cadena de text vàlida."
                )
        
        return value
    
    def validate_serveis(self, value):
        """
        Validació personalitzada per als serveis
        """
        if not isinstance(value, list):
            raise serializers.ValidationError(
                "Els serveis han de ser una llista."
            )
        
        serveis_valids = [
            'aigua', 'llits', 'cuina', 'dutxa', 'wc', 'calefaccio', 
            'electricitat', 'wifi', 'botiqui', 'mantes'
        ]
        
        for servei in value:
            if servei not in serveis_valids:
                raise serializers.ValidationError(
                    f"El servei '{servei}' no és vàlid. Serveis disponibles: {', '.join(serveis_valids)}"
                )
        
        return value
    
    def validate(self, data):
        """
        Validacions a nivell d'objecte
        """
        # Si està tancat, l'estat no pot ser 'obert'
        if data.get('tancat', False) and data.get('estat') == 'obert':
            raise serializers.ValidationError(
                "Un refugi no pot estar obert i tancat alhora."
            )
        
        return data


class RefugiLliureListSerializer(RefugiLliureSerializer):
    """
    Serializer simplificat per a llistats (menys camps)
    """
    
    class Meta(RefugiLliureSerializer.Meta):
        fields = [
            'id',
            'nom',
            'tipus',
            'ubicacio',
            'regio',
            'altitud',
            'capacitat',
            'estat',
            'clau_necessaria',
            'tancat',
            'is_available'
        ]