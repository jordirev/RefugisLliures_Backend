"""
Serializers per a la gestió de dubtes i respostes
"""
from rest_framework import serializers


class AnswerSerializer(serializers.Serializer):
    """Serializer per la resposta d'una answer"""
    id = serializers.CharField()
    creator_uid = serializers.CharField()
    message = serializers.CharField()
    created_at = serializers.CharField()  # ISO 8601 format
    parent_answer_id = serializers.CharField(required=False, allow_null=True)


class DoubtSerializer(serializers.Serializer):
    """Serializer per la resposta d'un dubte amb les seves answers"""
    id = serializers.CharField()
    refuge_id = serializers.CharField()
    creator_uid = serializers.CharField()
    message = serializers.CharField()
    created_at = serializers.CharField()  # ISO 8601 format
    answers_count = serializers.IntegerField()
    answers = AnswerSerializer(many=True, required=False)


class CreateDoubtSerializer(serializers.Serializer):
    """Serializer per crear un dubte (POST)"""
    refuge_id = serializers.CharField(required=True, allow_blank=False, max_length=100)
    message = serializers.CharField(required=True, allow_blank=False, max_length=2000)


class CreateAnswerSerializer(serializers.Serializer):
    """Serializer per crear una resposta (POST)"""
    refuge_id = serializers.CharField(required=True, allow_blank=False, max_length=100)
    message = serializers.CharField(required=True, allow_blank=False, max_length=2000)
