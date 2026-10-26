"""
Serializers de `doubts` (contracte JSON idèntic a l'anterior; `answers` surt sempre, `[]` si no n'hi ha: D30).

- Entrada: `CreateDoubtSerializer` (`refuge_id`, `message`) i `CreateAnswerSerializer` (`message`). El `message` es
  retalla, no pot ser buit, té com a molt 2000 caràcters i no pot dur NUL (les mateixes regles que el CHECK de la BD).
- Sortida: `DoubtSerializer` espera un `Doubt` amb `answers_count` anotat i `answers` precarregades (sortida de
  `selectors.list_doubts`) o acabat de crear (`services.create_doubt`, `answers_count = 0`); `AnswerSerializer`, una
  `Answer`. Les dates surten en ISO 8601 amb el desplaçament de Madrid.
"""
from django.core.validators import ProhibitNullCharactersValidator
from rest_framework import serializers


class RefugeIdField(serializers.CharField):
    """
    `refuge_id` del cos: un valor que no és un UUID (NUL inclòs) no és una dada invàlida sinó un refugi que no existeix
    (404), com ja passava amb els IDs antics de Firestore; per això no s'hi aplica la prohibició de NUL.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.validators = [v for v in self.validators if not isinstance(v, ProhibitNullCharactersValidator)]


class AnswerSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    creator_uid = serializers.CharField(source='creator_id')
    message = serializers.CharField()
    created_at = serializers.DateTimeField()
    parent_answer_id = serializers.UUIDField(allow_null=True)


class DoubtSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    refuge_id = serializers.UUIDField()
    creator_uid = serializers.CharField(source='creator_id')
    message = serializers.CharField()
    created_at = serializers.DateTimeField()
    answers_count = serializers.IntegerField()
    answers = serializers.SerializerMethodField()

    def get_answers(self, doubt):
        if not doubt.answers_count:                           # sense respostes: no cal tocar la relació
            return []
        return AnswerSerializer(doubt.answers.all(), many=True).data


class CreateDoubtSerializer(serializers.Serializer):
    refuge_id = RefugeIdField(max_length=100)
    message = serializers.CharField(max_length=2000)


class CreateAnswerSerializer(serializers.Serializer):
    message = serializers.CharField(max_length=2000)
