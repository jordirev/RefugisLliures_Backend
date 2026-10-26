"""Serializers de `visits`: entrada (`num_visitors`) i sortida (la visita tal com la veu l'usuari)."""
from rest_framework import serializers

# D27: tope per evitar valors absurds (§2.11); el CHECK de la BD només exigeix >= 1.
MAX_NUM_VISITORS = 100


class CreateRefugeVisitSerializer(serializers.Serializer):
    """POST: nombre de persones que visitaran el refugi."""
    num_visitors = serializers.IntegerField(
        required=True, min_value=1, max_value=MAX_NUM_VISITORS,
        help_text='Nombre de persones que visitaran el refugi (1-100)')


class UpdateRefugeVisitSerializer(serializers.Serializer):
    """PATCH: nou nombre de persones de l'usuari."""
    num_visitors = serializers.IntegerField(
        required=True, min_value=1, max_value=MAX_NUM_VISITORS,
        help_text='Nombre de persones que visitaran el refugi (1-100)')


class RefugeVisitListSerializer(serializers.Serializer):
    """Sortida: un `VisitSummary`. No exposa mai participants."""
    date = serializers.DateField(help_text='Data de la visita (YYYY-MM-DD)')
    refuge_id = serializers.UUIDField(help_text='ID del refugi')
    total_visitors = serializers.IntegerField(help_text='Total de visitants (tots els usuaris)')
    is_visitor = serializers.BooleanField(help_text="L'usuari autenticat hi és")
    num_visitors = serializers.IntegerField(help_text="Visitants de l'usuari autenticat (0 si no hi és)")
