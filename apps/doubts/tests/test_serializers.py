"""
Serializers de `apps.doubts` (chunk 6).

Contracte (`apps/doubts/serializers.py`, mateixos noms que els d'`api/serializers/doubt_serializer.py`):
- `CreateDoubtSerializer(data={refuge_id, message})`: `refuge_id` obligatori, no buit, <= 100 caràcters; `message`
  obligatori, no buit (espais retallats), <= 2000, sense caràcters NUL. Camps desconeguts s'ignoren.
- `CreateAnswerSerializer(data={message})`: les mateixes regles de `message`.
- `AnswerSerializer(answer).data` -> `{id, creator_uid, message, created_at, parent_answer_id}` (tots `str`/`None`;
  `created_at` ISO 8601 amb el desplaçament de Madrid).
- `DoubtSerializer(doubt).data` -> `{id, refuge_id, creator_uid, message, created_at, answers_count[, answers]}` on
  `doubt` és un `Doubt` amb `answers_count` anotat i `answers` precarregades (sortida de `selectors.list_doubts`);
  `answers` és la llista plana ordenada per `(created_at, id)`. Vegeu la pregunta 1 de l'informe sobre la clau `answers`
  quan no hi ha respostes (avui falta; els tests accepten tant la clau absent com `[]`).
"""
import uuid

import pytest

from apps.core.rls import rls_context
from apps.doubts.tests.helpers import (
    ANSWER_KEYS, DOUBT_BASE_KEYS, answers_of, is_uuid, make_answer, make_doubt, sql)

pytestmark = [pytest.mark.serializers]


@pytest.fixture
def S():
    from apps.doubts import serializers
    return serializers


# =================================== entrada (sense BD) ===================================

@pytest.mark.unit
def test_create_doubt_valid(S):
    s = S.CreateDoubtSerializer(data={'refuge_id': str(uuid.uuid4()), 'message': '  Hi ha aigua?  '})
    assert s.is_valid(), s.errors
    assert s.validated_data['message'] == 'Hi ha aigua?'             # es retalla (com avui)
    assert set(s.validated_data) == {'refuge_id', 'message'}


@pytest.mark.unit
@pytest.mark.parametrize('data,field', [
    ({'message': 'x'}, 'refuge_id'),
    ({'refuge_id': 'r'}, 'message'),
    ({'refuge_id': '', 'message': 'x'}, 'refuge_id'),
    ({'refuge_id': 'r', 'message': ''}, 'message'),
    ({'refuge_id': 'r', 'message': '   \n '}, 'message'),
    ({'refuge_id': 'r', 'message': None}, 'message'),
    ({'refuge_id': None, 'message': 'x'}, 'refuge_id'),
    ({'refuge_id': 'r' * 101, 'message': 'x'}, 'refuge_id'),
    ({'refuge_id': 'r', 'message': 'x' * 2001}, 'message'),
    ({'refuge_id': 'r', 'message': 'a\x00b'}, 'message'),
])
def test_create_doubt_invalid(S, data, field):
    s = S.CreateDoubtSerializer(data=data)
    assert not s.is_valid() and field in s.errors


@pytest.mark.unit
def test_create_doubt_limits_exactes(S):
    assert S.CreateDoubtSerializer(data={'refuge_id': 'r' * 100, 'message': 'x' * 2000}).is_valid()


@pytest.mark.unit
def test_create_doubt_ignora_camps_desconeguts(S):
    s = S.CreateDoubtSerializer(data={'refuge_id': 'r', 'message': 'x', 'creator_uid': 'hacker', 'id': 'i',
                                      'created_at': '2000-01-01', 'answers_count': 99})
    assert s.is_valid() and set(s.validated_data) == {'refuge_id', 'message'}


@pytest.mark.unit
@pytest.mark.parametrize('data', [[], 'text', 5, None])
def test_create_doubt_cos_que_no_es_un_objecte(S, data):
    assert not S.CreateDoubtSerializer(data=data).is_valid()


@pytest.mark.unit
def test_create_answer_valid_i_invalid(S):
    assert S.CreateAnswerSerializer(data={'message': ' Sí '}).is_valid()
    assert S.CreateAnswerSerializer(data={'message': 'x' * 2000}).is_valid()
    for bad in ({}, {'message': ''}, {'message': '  '}, {'message': 'x' * 2001}, {'message': None}, {'message': 'a\x00'}):
        s = S.CreateAnswerSerializer(data=bad)
        assert not s.is_valid() and 'message' in s.errors, bad


@pytest.mark.unit
def test_create_answer_ignora_parent_answer_id_del_cos(S):
    """El pare només ve de la URL: un `parent_answer_id` al cos no es fa servir."""
    s = S.CreateAnswerSerializer(data={'message': 'x', 'parent_answer_id': str(uuid.uuid4()), 'creator_uid': 'h'})
    assert s.is_valid() and set(s.validated_data) == {'message'}


# =================================== sortida (amb BD) ===================================

@pytest.mark.db_infra
@pytest.mark.django_db
@pytest.mark.integration
@pytest.mark.real_permissions
def test_sortida_de_dubte_i_respostes(S, selectors, world):
    r1, _ = world
    d = make_doubt(r1, 'u1', message='Hola', minutes=0)                       # 2025-01-01T10:00Z -> +01:00
    a1 = make_answer(d, 'u2', 'primera', minutes=1)
    a2 = make_answer(d, 'u3', 'filla', parent=a1, minutes=2)
    with rls_context(uid='u1'):
        [doubt] = selectors.list_doubts(r1.pk)
        data = S.DoubtSerializer(doubt).data
    assert set(data) == DOUBT_BASE_KEYS | {'answers'}
    assert data['id'] == d and data['refuge_id'] == str(r1.pk) and data['creator_uid'] == 'u1'
    assert data['message'] == 'Hola' and data['answers_count'] == 2
    assert data['created_at'] == '2025-01-01T11:00:00+01:00'                  # Europe/Madrid
    first, second = data['answers']
    assert all(set(a) == ANSWER_KEYS for a in data['answers'])
    assert (first['id'], first['parent_answer_id'], first['creator_uid']) == (a1, None, 'u2')
    assert (second['id'], second['parent_answer_id']) == (a2, a1)
    assert first['created_at'] == '2025-01-01T11:01:00+01:00'
    assert type(data['answers_count']) is int and is_uuid(data['id'])


@pytest.mark.db_infra
@pytest.mark.django_db
@pytest.mark.integration
@pytest.mark.real_permissions
def test_created_at_d_estiu_porta_el_desplacament_de_juliol(S, selectors, world):
    r1, _ = world
    sql("INSERT INTO activity.doubts (refuge_id, creator_uid, message, created_at) VALUES (%s, 'u1', 'estiu', "
        "'2025-07-01T10:00:00Z')", [r1.pk])
    with rls_context(uid='u1'):
        data = {x.message: S.DoubtSerializer(x).data for x in selectors.list_doubts(r1.pk)}
    assert data['estiu']['created_at'] == '2025-07-01T12:00:00+02:00'


@pytest.mark.db_infra
@pytest.mark.django_db
@pytest.mark.integration
@pytest.mark.real_permissions
def test_dubte_sense_respostes(S, selectors, world):
    r1, _ = world
    make_doubt(r1, 'u1')
    with rls_context(uid='u1'):
        [doubt] = selectors.list_doubts(r1.pk)
        data = S.DoubtSerializer(doubt).data
    assert data['answers_count'] == 0 and answers_of(data) == []
    assert set(data) - {'answers'} == DOUBT_BASE_KEYS


@pytest.mark.db_infra
@pytest.mark.django_db
@pytest.mark.integration
@pytest.mark.real_permissions
def test_sortida_d_una_resposta(S, selectors, world):
    d = make_doubt(world[0], 'u1')
    a = make_answer(d, 'u2')
    with rls_context(uid='u1'):
        data = S.AnswerSerializer(selectors.get_answer(d, a)).data
    assert set(data) == ANSWER_KEYS and data['id'] == a and data['parent_answer_id'] is None
    assert isinstance(data['creator_uid'], str) and data['created_at'].endswith(('+01:00', '+02:00'))
