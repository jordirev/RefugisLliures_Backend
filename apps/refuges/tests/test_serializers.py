"""
Serializers del domini refugi (contracte JSON actual, sense BD): arrodoniment half-to-even de `condition`,
forma de `coord`/`info_comp`, camps ocults per a anònims i filtres de cerca (la condició passa a 0-3).
"""
import pytest

from apps.refuges.serializers import RefugiSearchFiltersSerializer, RefugiSerializer
from apps.refuges.tests.helpers import AMENITY_FIELDS, BASE_KEYS

pytestmark = [pytest.mark.unit, pytest.mark.serializers]


def refuge_dict(**kw):
    d = {'id': '0190a1b2-c3d4-7e5f-8a9b-0c1d2e3f4a5b', 'name': 'Cabane', 'coord': {'lat': 42.5, 'long': 1.5},
         'altitude': 1500, 'places': None, 'remarque': '', 'info_comp': {f: 0 for f in AMENITY_FIELDS},
         'description': '', 'links': ['https://a.org'], 'type': 'orri', 'modified_at': '2024-05-17',
         'region': None, 'departement': None, 'condition': 2, 'visitors': [], 'images_metadata': []}
    d.update(kw)
    return d


def ser(data, authenticated=True):
    return RefugiSerializer(data, context={'is_authenticated': authenticated}).data


@pytest.mark.parametrize('stored,shown', [
    (0.0, 0), (0.5, 0), (0.51, 1), (1.5, 2), (2.5, 2), (2.51, 3), (3.0, 3), (2.4999, 2), (0.49, 0)])
def test_condition_es_arrodoneix_half_to_even_en_serialitzar(stored, shown):
    assert ser(refuge_dict(condition=stored))['condition'] == shown


def test_condition_null_continua_null():
    assert ser(refuge_dict(condition=None))['condition'] is None


def test_condition_enter_a_la_sortida():
    assert type(ser(refuge_dict(condition=1.5))['condition']) is int


def test_forma_de_coord_i_info_comp():
    data = ser(refuge_dict())
    assert set(data['coord']) == {'lat', 'long'}
    assert set(data['info_comp']) == set(AMENITY_FIELDS)
    assert all(type(v) is int for v in data['info_comp'].values())


def test_el_surname_no_s_emet():
    assert 'surname' not in ser(refuge_dict(surname='Alias'))


def test_anonim_no_veu_visitors_ni_images_metadata():
    data = ser(refuge_dict(), authenticated=False)
    assert 'visitors' not in data and 'images_metadata' not in data
    assert set(data) == BASE_KEYS


def test_autenticat_veu_images_metadata():
    assert 'images_metadata' in ser(refuge_dict(), authenticated=True)


# ---------- Filtres ----------

def validate(**params):
    s = RefugiSearchFiltersSerializer(data=params)
    return s.is_valid(), s


def test_filtre_condition_accepta_0_a_3():
    ok, s = validate(condition='0,1,2,3')
    assert ok, s.errors
    assert s.validated_data['condition'] == [0, 1, 2, 3]


@pytest.mark.parametrize('value', ['4', '-1', 'a', '1,9', '1.5'])
def test_filtre_condition_rebutja_fora_de_0_3(value):
    ok, s = validate(condition=value)
    assert not ok and 'condition' in s.errors


@pytest.mark.db_infra
@pytest.mark.django_db
def test_filtre_type_llista_i_validacio():
    """Els tipus vàlids són els del catàleg `refuges.refuge_types` (BD), no una llista del codi."""
    ok, s = validate(type='orri, fermée')
    assert ok and s.validated_data['type'] == ['orri', 'fermée']
    ok, s = validate(type='orri,piscina')
    assert not ok and 'type' in s.errors


@pytest.mark.db_infra
@pytest.mark.django_db
def test_filtre_type_accepta_tots_els_valors_del_disseny():
    from apps.refuges.tests.helpers import REFUGE_TYPES
    ok, s = validate(type=','.join(REFUGE_TYPES))
    assert ok, s.errors


@pytest.mark.parametrize('params,field', [
    ({'places_min': 5, 'places_max': 2}, 'places_min'),
    ({'altitude_min': 3000, 'altitude_max': 100}, 'altitude_min'),
    ({'altitude_max': 9000}, 'altitude_max'),
    ({'places_min': -1}, 'places_min'),
    ({'altitude_min': 'x'}, 'altitude_min'),
])
def test_filtres_numerics_invalids(params, field):
    ok, s = validate(**params)
    assert not ok and field in s.errors


def test_filtres_buits_son_valids_i_sense_filtres_actius():
    ok, s = validate(name='', type='', condition='')
    assert ok and s.validated_data['type'] == [] and s.validated_data['condition'] == []
