"""
Serializers de `apps.proposals.serializers` (chunk 8). Contracte dels noms:
`CreateProposalSerializer`, `RejectProposalSerializer`, `ProposalSerializer`.

Es conserven les regles i els missatges d'avui (`RefugeProposalCreateSerializer`): obligatorietats per acció, llista blanca
de camps (`ALLOWED_REFUGE_FIELDS` **sense `remarque`**, S-6) i d'`info_comp`, camps prohibits, rangs. Novetats del
disseny (§2.18, `GOTCHAS` #5: serializer i `CHECK` apliquen les mateixes regles):

- `comment` <= 4000 i `reason` <= 2000;
- `info_comp` només 0/1; `type` validat contra el catàleg `refuges.refuge_types` (1 consulta);
- el payload es desa **només amb les claus enviades** (en un `update`, «absent» i `null` són coses diferents) i amb els
  tipus coercits (M9: `"1200"` -> `1200`); cap valor per defecte injectat (un `links=[]` per defecte esborraria els enllaços);
- límits que el `CHECK`/les columnes ja imposen i que, sense el serializer, donarien un 500 en aprovar: nom, regió i
  departament <= 255, `places` <= 2**31-1, latitud/longitud en rang i fora de (0, 0), enllaços únics dins el payload i
  <= 2048 caràcters, payload < 64 KiB. (PREGUNTA a l'orquestrador: aquests límits són nous respecte d'avui.)
"""
import pytest

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.serializers, pytest.mark.integration,
              pytest.mark.real_permissions]

FIELDS_MSG = ('altitude, condition, coord, departement, description, info_comp, links, name, places, region, type')
COORD = {'long': 1.234, 'lat': 42.567}
REFUGE = '0190c9a8-0000-7000-8000-000000000001'


def S():
    from apps.proposals import serializers
    return serializers


def check(data):
    s = S().CreateProposalSerializer(data=data)
    return s.is_valid(), s


def errors_of(data):
    ok, s = check(data)
    assert not ok, f'havia de ser invàlid: {data}'
    return s.errors


def payload_error(data):
    return str(errors_of(data)['payload'])


def create(**payload):
    return {'action': 'create', 'payload': {'name': 'Nou', 'coord': COORD, **payload}}


def update(**payload):
    return {'action': 'update', 'refuge_id': REFUGE, 'payload': payload}


# =================================== regles per acció ===================================

def test_create_valid_complet():
    ok, s = check({'action': 'create', 'comment': 'c', 'payload': {
        'name': 'Refugi Nou', 'coord': COORD, 'altitude': 1800, 'places': 15, 'type': 'non gardé',
        'description': 'd', 'links': ['https://a.org/x'], 'region': 'Pirineus', 'departement': 'Lleida',
        'condition': 2, 'info_comp': {'cheminee': 1, 'eau': 1, 'lits': 0}}})
    assert ok, s.errors


def test_update_i_delete_valids():
    assert check(update(places=45))[0]
    assert check({'action': 'delete', 'refuge_id': REFUGE, 'comment': 'x'})[0]
    assert check({'action': 'delete', 'refuge_id': REFUGE, 'payload': None})[0]


@pytest.mark.parametrize('data,key', [
    ({}, 'action'),
    ({'action': 'merge', 'refuge_id': REFUGE}, 'action'),
    ({'action': 'create', 'refuge_id': REFUGE, 'payload': {'name': 'x', 'coord': COORD}}, 'refuge_id'),
    ({'action': 'create'}, 'payload'),
    ({'action': 'create', 'payload': {}}, 'payload'),
    ({'action': 'create', 'payload': {'coord': COORD}}, 'payload'),
    ({'action': 'create', 'payload': {'name': '', 'coord': COORD}}, 'payload'),
    ({'action': 'create', 'payload': {'name': None, 'coord': COORD}}, 'payload'),
    ({'action': 'create', 'payload': {'name': '   ', 'coord': COORD}}, 'payload'),
    ({'action': 'create', 'payload': {'name': 'x'}}, 'payload'),
    ({'action': 'update', 'payload': {'places': 1}}, 'refuge_id'),
    ({'action': 'update', 'refuge_id': REFUGE}, 'payload'),
    ({'action': 'update', 'refuge_id': REFUGE, 'payload': {}}, 'payload'),
    ({'action': 'delete'}, 'refuge_id'),
    ({'action': 'delete', 'refuge_id': REFUGE, 'payload': {'places': 1}}, 'payload'),
])
def test_regles_per_accio(data, key):
    assert key in errors_of(data)


def test_missatges_d_avui():
    assert "obligatori per a l'acció 'update'" in str(errors_of({'action': 'update', 'payload': {'places': 1}})['refuge_id'])
    assert "'name' és obligatori" in payload_error({'action': 'create', 'payload': {'coord': COORD}})
    assert "'coord' és obligatori" in payload_error({'action': 'create', 'payload': {'name': 'x'}})
    assert "no ha d'estar present" in payload_error({'action': 'delete', 'refuge_id': REFUGE, 'payload': {'a': 1}})


def test_no_es_pot_proposar_com_a_payload_un_no_diccionari():
    for bad in ('text', 5, [1], True):
        assert 'payload' in errors_of({'action': 'create', 'payload': bad})


# =================================== llista blanca ===================================

def test_camps_desconeguts_missatge_exacte():
    msg = payload_error(create(foo=1))
    assert msg == f'Camps no permesos al payload: foo. Camps permesos: {FIELDS_MSG}'


@pytest.mark.parametrize('field', ['remarque', 'images_metadata', 'visitors', 'id', 'modified_at'])
def test_camps_prohibits_i_remarque_es_rebutgen(field):
    assert f'Camps no permesos al payload: {field}' in payload_error(update(**{field: 'x'}))


def test_info_comp_amb_clau_desconeguda():
    err = errors_of(create(info_comp={'cheminee': 1, 'piscine': 1}))['payload']
    assert 'piscine' in str(err) and 'Camps permesos' in str(err)


@pytest.mark.parametrize('value', [2, -1, 'x', 1.5, None])
def test_info_comp_nomes_admet_0_i_1(value):
    assert 'payload' in errors_of(create(info_comp={'eau': value}))


# =================================== valors ===================================

@pytest.mark.parametrize('payload', [
    {'altitude': -1}, {'altitude': 8849}, {'altitude': 'alt'}, {'places': -1}, {'places': 2 ** 31},
    {'condition': 4}, {'condition': -1}, {'condition': 'x'},
    {'name': 'x' * 256}, {'region': 'x' * 256}, {'departement': 'x' * 256},
    {'links': 'https://a.org'}, {'links': ['no-es-url']}, {'links': ['ftp://a.org/x']},
    {'links': ['https://a.org/' + 'x' * 2048]}, {'links': ['https://a.org/1', 'https://a.org/1']},
    {'links': None}, {'type': 'inexistent'}, {'type': ''},
    {'coord': {'lat': 91, 'long': 1}}, {'coord': {'lat': -91, 'long': 1}}, {'coord': {'lat': 1, 'long': 181}},
    {'coord': {'lat': 0, 'long': 0}}, {'coord': {'lat': 1}}, {'coord': {'long': 1}}, {'coord': 'x'},
    {'info_comp': 'x'},
])
def test_valors_invalids(payload):
    data = update(**payload)
    assert 'payload' in errors_of(data), payload


@pytest.mark.parametrize('payload', [
    {'altitude': 0}, {'altitude': 8848}, {'altitude': None}, {'places': 0}, {'places': 2 ** 31 - 1}, {'places': None},
    {'condition': 0}, {'condition': 3}, {'condition': None}, {'name': 'x' * 255}, {'description': None},
    {'description': ''}, {'region': None}, {'region': ''}, {'departement': None}, {'links': []},
    {'links': ['https://a.org/x', 'http://b.org/y']}, {'type': 'orri'}, {'coord': {'lat': 90, 'long': -180}},
    {'info_comp': {}}, {'info_comp': {'eau': 0}},
])
def test_valors_valids(payload):
    ok, s = check(update(**payload))
    assert ok, (payload, s.errors)


def test_type_es_valida_contra_el_cataleg_de_la_bd():
    for code in ('non gardé', 'fermée', 'cabane ouverte mais ocupee par le berger l ete', 'orri', 'emergence',
                 'key_needed'):
        assert check(update(type=code))[0], code


def test_payload_massa_gran_es_rebutjat_abans_d_arribar_a_la_bd():
    assert 'payload' in errors_of(update(description='x' * 70_000))


# =================================== comment ===================================

def test_comment_fins_a_4000():
    for ok_comment in (None, '', 'x' * 4000):
        assert check({**create(), 'comment': ok_comment})[0]
    assert 'comment' in errors_of({**create(), 'comment': 'x' * 4001})


# =================================== payload desat ===================================

def test_el_payload_validat_nomes_porta_les_claus_enviades():
    ok, s = check(update(places=45))
    assert ok
    assert s.validated_data['payload'] == {'places': 45}                       # cap `links=[]`, `type`, `remarque`…


def test_el_payload_conserva_els_null_explicits():
    ok, s = check(update(altitude=None, description=None, condition=None))
    assert ok and s.validated_data['payload'] == {'altitude': None, 'description': None, 'condition': None}


def test_el_payload_coerceix_els_tipus_m9():
    ok, s = check(update(altitude='1200', places='7', coord={'lat': '42.5', 'long': '1.5'}, condition='2'))
    assert ok, s.errors
    p = s.validated_data['payload']
    assert (p['altitude'], p['places'], p['condition']) == (1200, 7, 2)
    assert p['coord'] == {'lat': 42.5, 'long': 1.5}


def test_el_payload_de_create_conserva_el_que_s_ha_enviat():
    ok, s = check(create(info_comp={'cheminee': 1, 'eau': 1, 'lits': 1}, links=['https://a.org/x']))
    assert ok
    p = s.validated_data['payload']
    assert p['name'] == 'Nou' and p['coord'] == COORD and p['links'] == ['https://a.org/x']
    assert (p['info_comp']['cheminee'], p['info_comp']['eau'], p['info_comp']['lits']) == (1, 1, 1)
    assert 'remarque' not in p and 'description' not in p


def test_el_nom_es_retalla():
    ok, s = check(create(name='  Refugi  '))
    assert ok and s.validated_data['payload']['name'] == 'Refugi'


# =================================== reject ===================================

def test_reject_reason():
    R = S().RejectProposalSerializer
    for ok_data in ({}, {'reason': ''}, {'reason': 'Cal més evidència'}, {'reason': 'x' * 2000}):
        assert R(data=ok_data).is_valid(), ok_data
    for bad in ({'reason': 'x' * 2001}, {'reason': None}):
        s = R(data=bad)
        assert not s.is_valid() and 'reason' in s.errors, bad
