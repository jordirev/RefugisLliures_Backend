"""
Serializers d'entrada de `apps.accounts.serializers` (chunk 3).

Contracte: `UserCreateSerializer`, `UserUpdateSerializer`, `AgeConfirmationSerializer` i `RefugeIdSerializer`
(substitueix `UserRefugiSerializer`). L'idioma es valida contra el cataleg `users.languages` (BD, §2.1.1), no contra una
llista fixa; per aixo els tests necessiten Postgres.
"""
from datetime import timedelta

import pytest

from apps.accounts.tests.helpers import as_owner, madrid_today, years_ago

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.serializers, pytest.mark.real_permissions]


@pytest.fixture
def S():
    from apps.accounts import serializers
    return serializers


# ---------- UserCreateSerializer ----------

def test_create_valida_i_normalitza(S):
    s = S.UserCreateSerializer(data={'username': '  Anna  ', 'language': ' ES ', 'birth_date': '1990-05-17'})
    assert s.is_valid(), s.errors
    assert s.validated_data['username'] == 'Anna'
    assert s.validated_data['language'] == 'es'
    assert str(s.validated_data['birth_date']) == '1990-05-17'


def test_create_buit_es_valid_i_l_idioma_per_defecte_es_en(S):
    s = S.UserCreateSerializer(data={})
    assert s.is_valid(), s.errors
    assert s.validated_data.get('username', '') == ''
    assert s.validated_data.get('language', 'en') == 'en'       # canvi de contracte: 'ca' -> 'en' (§12 #11)
    assert 'birth_date' not in s.validated_data


@pytest.mark.parametrize('data,field', [
    ({'username': 'a'}, 'username'),
    ({'username': ' a '}, 'username'),
    ({'username': 'x' * 256}, 'username'),
    ({'language': 'xx'}, 'language'),
    ({'language': 'de'}, 'language'),
    ({'language': ''}, 'language'),
    ({'birth_date': '2999-01-01'}, 'birth_date'),
    ({'birth_date': '1899-12-31'}, 'birth_date'),
    ({'birth_date': '17/05/1990'}, 'birth_date'),
    ({'birth_date': 'avui'}, 'birth_date'),
])
def test_create_invalid(S, data, field):
    s = S.UserCreateSerializer(data=data)
    assert not s.is_valid()
    assert field in s.errors


def test_create_el_cataleg_d_idiomes_es_a_la_bd_no_al_codi(S, AM):
    assert not S.UserCreateSerializer(data={'language': 'pt'}).is_valid()
    with as_owner():
        AM.Language.objects.create(code='pt')
    s = S.UserCreateSerializer(data={'language': 'pt'})
    assert s.is_valid(), s.errors
    assert s.validated_data['language'] == 'pt'


# ---------- UserUpdateSerializer (TECH_DEBT M1) ----------

def test_update_no_afegeix_cap_idioma_per_defecte(S):
    """M1/gotcha 6: el PATCH d'usuari no ha de resetejar `language` (cap `default=` en un serializer d'update)."""
    s = S.UserUpdateSerializer(data={'username': 'Nou'})
    assert s.is_valid(), s.errors
    assert s.validated_data == {'username': 'Nou'}


def test_update_idioma_sol(S):
    s = S.UserUpdateSerializer(data={'language': 'Fr'})
    assert s.is_valid(), s.errors
    assert s.validated_data == {'language': 'fr'}


def test_update_exigeix_almenys_un_camp(S):
    """M1: el `validate()` «almenys un camp» mai fallava; ara un cos buit (o sense camps coneguts) es rebutja."""
    for data in ({}, {'is_blocked': True}, {'moderation_strikes': 0}):
        s = S.UserUpdateSerializer(data=data)
        assert not s.is_valid(), data
        assert 'non_field_errors' in s.errors


def test_update_username_buit_es_un_camp_proporcionat(S):
    s = S.UserUpdateSerializer(data={'username': ''})
    assert s.is_valid(), s.errors
    assert s.validated_data == {'username': ''}


def test_update_ignora_camps_de_moderacio(S):
    s = S.UserUpdateSerializer(data={'username': 'ok', 'is_blocked': True, 'moderation_strikes': 5, 'uid': 'x'})
    assert s.is_valid()
    assert set(s.validated_data) == {'username'}


@pytest.mark.parametrize('data,field', [({'username': 'a'}, 'username'), ({'language': 'zz'}, 'language')])
def test_update_invalid(S, data, field):
    s = S.UserUpdateSerializer(data=data)
    assert not s.is_valid() and field in s.errors


# ---------- AgeConfirmationSerializer ----------

def test_age_requereix_birth_date(S):
    assert 'birth_date' in (lambda s: (s.is_valid(), s.errors)[1])(S.AgeConfirmationSerializer(data={}))


@pytest.mark.parametrize('value', ['2999-01-01', '1899-01-01', '01-01-1990', '', None])
def test_age_data_invalida(S, value):
    assert not S.AgeConfirmationSerializer(data={'birth_date': value}).is_valid()


def test_age_data_valida_i_avui_es_valid(S):
    for d in (years_ago(30), madrid_today(), madrid_today() - timedelta(days=1)):
        s = S.AgeConfirmationSerializer(data={'birth_date': d.isoformat()})
        assert s.is_valid(), (d, s.errors)


# ---------- RefugeIdSerializer ----------

def test_refuge_id_obligatori_i_no_buit(S):
    assert S.RefugeIdSerializer(data={'refuge_id': 'abc'}).is_valid()
    for data in ({}, {'refuge_id': ''}, {'refuge_id': None}, {'refuge_id': 'x' * 256}):
        assert not S.RefugeIdSerializer(data=data).is_valid(), data
