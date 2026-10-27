"""
Serializers d'entrada d'`apps.experiences.serializers` (chunk 7): `ExperienceCreateSerializer` (POST) i
`ExperienceUpdateSerializer` (PATCH). Mateixos noms que els de `api/serializers/experience_serializer.py` (que
desapareix); regles d'avui + `condition` (§2.15: POST l'exigeix 0-3; PATCH l'accepta opcional).

Les regles són les mateixes que els `CHECK` de la BD (CLAUDE.md gotcha 5): comentari no buit i <= 2000, condició 0-3.
Cap `default=` als serializers d'actualització (gotcha 6).
"""
import pytest

pytestmark = [pytest.mark.serializers, pytest.mark.unit]


@pytest.fixture
def S():
    from apps.experiences import serializers
    return serializers


def valid(serializer_cls, data):
    s = serializer_cls(data=data)
    return s.is_valid(), s


OK = {'refuge_id': '0190aaaa-bbbb-7ccc-8ddd-eeeeffff0000', 'comment': 'Refugi net', 'condition': 2}


# ---------- creació ----------

def test_create_valid(S):
    ok, s = valid(S.ExperienceCreateSerializer, OK)
    assert ok and s.validated_data == {'refuge_id': OK['refuge_id'], 'comment': 'Refugi net', 'condition': 2}


@pytest.mark.parametrize('field', ['refuge_id', 'comment', 'condition'])
def test_create_camps_obligatoris(S, field):
    data = {k: v for k, v in OK.items() if k != field}
    ok, s = valid(S.ExperienceCreateSerializer, data)
    assert not ok and field in s.errors


@pytest.mark.parametrize('value', [0, 1, 2, 3, '0', '3'])
def test_create_condicio_valida(S, value):
    ok, s = valid(S.ExperienceCreateSerializer, {**OK, 'condition': value})
    assert ok and s.validated_data['condition'] == int(value)


@pytest.mark.parametrize('value', [-1, 4, 10, 1.5, 'abc', '', None, True, [], {}])
def test_create_condicio_invalida(S, value):
    ok, s = valid(S.ExperienceCreateSerializer, {**OK, 'condition': value})
    assert not ok and 'condition' in s.errors


@pytest.mark.parametrize('comment', ['', '   ', '\n\t ', None])
def test_create_comentari_buit_o_no_text(S, comment):
    ok, s = valid(S.ExperienceCreateSerializer, {**OK, 'comment': comment})
    assert not ok and 'comment' in s.errors


def test_create_comentari_limit_2000(S):
    assert valid(S.ExperienceCreateSerializer, {**OK, 'comment': 'x' * 2000})[0]
    ok, s = valid(S.ExperienceCreateSerializer, {**OK, 'comment': 'x' * 2001})
    assert not ok and 'comment' in s.errors


def test_create_comentari_es_retalla(S):
    ok, s = valid(S.ExperienceCreateSerializer, {**OK, 'comment': '  hola  '})
    assert ok and s.validated_data['comment'] == 'hola'


@pytest.mark.parametrize('refuge_id', ['', '   ', None, 'x' * 101])
def test_create_refuge_id_invalid(S, refuge_id):
    ok, s = valid(S.ExperienceCreateSerializer, {**OK, 'refuge_id': refuge_id})
    assert not ok and 'refuge_id' in s.errors


def test_create_ignora_camps_desconeguts_i_no_deixa_triar_el_creador(S):
    ok, s = valid(S.ExperienceCreateSerializer, {**OK, 'creator_uid': 'hacker', 'id': 'x', 'modified_at': 'y',
                                                'media_keys': ['k']})
    assert ok and set(s.validated_data) == {'refuge_id', 'comment', 'condition'}


# ---------- actualització ----------

def test_update_buit_es_valid_i_no_porta_defaults(S):
    ok, s = valid(S.ExperienceUpdateSerializer, {})
    assert ok and s.validated_data == {}


def test_update_acepta_comment_i_condition_per_separat(S):
    assert valid(S.ExperienceUpdateSerializer, {'comment': 'nou'})[1].validated_data == {'comment': 'nou'}
    assert valid(S.ExperienceUpdateSerializer, {'condition': 0})[1].validated_data == {'condition': 0}


@pytest.mark.parametrize('data,field', [({'comment': ''}, 'comment'), ({'comment': '   '}, 'comment'),
                                        ({'comment': 'x' * 2001}, 'comment'), ({'comment': None}, 'comment'),
                                        ({'condition': 4}, 'condition'), ({'condition': -1}, 'condition'),
                                        ({'condition': None}, 'condition'), ({'condition': 'm'}, 'condition')])
def test_update_invalid(S, data, field):
    ok, s = valid(S.ExperienceUpdateSerializer, data)
    assert not ok and field in s.errors


def test_update_ignora_camps_que_no_es_poden_editar(S):
    ok, s = valid(S.ExperienceUpdateSerializer, {'comment': 'x', 'refuge_id': 'altre', 'creator_uid': 'h',
                                                'media_keys': ['k']})
    assert ok and s.validated_data == {'comment': 'x'}
