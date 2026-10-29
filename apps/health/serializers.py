from rest_framework import serializers


class HealthCheckResponseSerializer(serializers.Serializer):
    """Resposta de `GET /api/health/` (D43): només PostgreSQL i Firebase Admin."""
    status = serializers.CharField()
    message = serializers.CharField()
    firebase = serializers.BooleanField()
    database = serializers.BooleanField()
