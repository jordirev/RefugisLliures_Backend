"""
Detecció de duplicats en crear una proposta `create` (decisió del PO, 27/10; D39).

- Només `action = 'create'`, només contra **refugis existents** (no contra propostes pendents).
- Candidat = refugi a **<= 500 m** (`ST_DWithin` geography) **i** amb nom semblant. Nom semblant = la regla de la cerca de
  `apps/refuges/selectors.search_queryset`: `core.norm_name` (sense accents ni majúscules) amb `trigram_similar` o
  subcadena, contra `name` i `surname` (pot ser NULL). Calen les dues condicions.
- 409 `{error: 'possible_duplicates', code: 'possible_duplicates', message: <català>,
  possible_duplicates: [{id, name, distance_m}]}`, per distància ascendent, `distance_m` enter arrodonit. No es crea res.
- Service: `PossibleDuplicates` (amb `.duplicates`, llista de diccionaris `{id, name, distance_m}`).
- Pressupost: una consulta més, constant amb el nombre de refugis i de candidats.
"""
import pytest

from apps.proposals.tests.helpers import (
    PROPOSALS, QueryCounter, api_post, count_proposals, create_body, delete_body, make_proposal, make_refuge, sql,
    update_body, user_claims, proposal_ids)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration,
              pytest.mark.real_permissions]

LAT, LONG = 42.5, 1.5
KEYS = {'error', 'code', 'message', 'possible_duplicates'}


def north(meters, lat=LAT, long=LONG):
    """Coordenada a `meters` metres al nord (geography, `ST_Project`)."""
    lon, la = sql("SELECT ST_X(p::geometry), ST_Y(p::geometry) FROM (SELECT ST_Project("
                  "ST_GeogFromText(%s), %s, 0) AS p) t", [f'SRID=4326;POINT({long} {lat})', meters])[0]
    return {'lat': la, 'long': lon}


def distance(coord, refuge):
    return sql("SELECT ST_Distance(coord, ST_GeogFromText(%s)) FROM refuges.refuges WHERE id = %s",
               [f"SRID=4326;POINT({coord['long']} {coord['lat']})", refuge.pk])[0][0]


def post(client, name, coord, uid='u1'):
    return api_post(client, PROPOSALS, user_claims(uid), create_body(name=name, coord=coord))


@pytest.fixture
def colomers(world):
    return make_refuge(name='Refugi de Colomers', lat=LAT, long=LONG, surname='Cabane Alba')


def test_proper_i_nom_semblant_409_amb_la_llista(client, colomers):
    r = post(client, 'Refugi de Colomers', north(200))
    assert r.status_code == 409, r.content
    body = r.json()
    assert set(body) == KEYS and body['error'] == body['code'] == 'possible_duplicates'
    assert isinstance(body['message'], str) and body['message']
    [d] = body['possible_duplicates']
    assert set(d) == {'id', 'name', 'distance_m'}
    assert d['id'] == str(colomers.pk) and d['name'] == 'Refugi de Colomers'
    assert type(d['distance_m']) is int and abs(d['distance_m'] - 200) <= 1
    assert count_proposals() == 0                                                  # no es crea res


def test_proper_pero_amb_un_altre_nom_es_201(client, colomers):
    assert post(client, 'Cabana Totalment Diferent', north(100)).status_code == 201


def test_lluny_pero_amb_el_mateix_nom_es_201(client, colomers):
    assert post(client, 'Refugi de Colomers', north(5000)).status_code == 201
    assert post(client, 'Refugi de Colomers', north(501)).status_code == 201


@pytest.mark.parametrize('name', ['refugi de colomers', 'REFUGI DE COLOMERS', 'Réfugi de Colomérs', 'Colomers',
                                  'refugi de colomers nou'])
def test_diferencies_d_accents_majuscules_i_subcadena_tambe_son_duplicats(client, colomers, name):
    r = post(client, name, north(50))
    assert r.status_code == 409, (name, r.content)
    assert [d['id'] for d in r.json()['possible_duplicates']] == [str(colomers.pk)]


def test_coincidencia_pel_sobrenom_surname(client, colomers):
    r = post(client, 'cabane alba', north(80))
    assert r.status_code == 409 and r.json()['possible_duplicates'][0]['id'] == str(colomers.pk)


def test_un_refugi_sense_surname_no_trenca_la_comparacio(client, world):
    make_refuge(name='Sense alias', lat=44.0)                                      # surname NULL
    assert post(client, 'Un nom diferent', {'lat': 44.0, 'long': 1.5}).status_code == 201
    assert post(client, 'Sense alias', {'lat': 44.0, 'long': 1.5}).status_code == 409


def test_el_limit_de_500_m_inclou_els_500(client, colomers):
    inside, outside = north(499.5), north(500.5)
    assert post(client, 'Refugi de Colomers', inside).status_code == 409
    assert post(client, 'Refugi de Colomers', outside).status_code == 201
    exact = north(500)
    expected = 409 if distance(exact, colomers) <= 500 else 201                   # <= 500 m compta (ST_DWithin)
    assert post(client, 'Refugi de Colomers', exact).status_code == expected


def test_diversos_candidats_ordenats_per_distancia(client, world):
    far = make_refuge(name='Colomers lluny', lat=42.5, long=1.5)
    near = make_refuge(name='Colomers aprop', lat=42.5, long=1.5)
    mid = make_refuge(name='Colomers mig', lat=42.5, long=1.5)
    for r, m in ((far, 400), (near, 50), (mid, 200)):
        c = north(m)
        sql("UPDATE refuges.refuges SET coord = ST_GeogFromText(%s) WHERE id = %s",
            [f"SRID=4326;POINT({c['long']} {c['lat']})", r.pk])
    make_refuge(name='Colomers fora de rang', lat=43.5, long=1.5)
    make_refuge(name='Altre nom del tot', lat=42.5, long=1.5)
    r = post(client, 'Colomers', {'lat': LAT, 'long': LONG})
    assert r.status_code == 409
    dups = r.json()['possible_duplicates']
    assert [d['id'] for d in dups] == [str(near.pk), str(mid.pk), str(far.pk)]
    assert [d['distance_m'] for d in dups] == sorted(d['distance_m'] for d in dups)
    assert all(type(d['distance_m']) is int for d in dups)
    assert abs(dups[0]['distance_m'] - 50) <= 1 and abs(dups[2]['distance_m'] - 400) <= 1


def test_nomes_per_a_create_no_per_a_update_ni_delete(client, colomers):
    r = api_post(client, PROPOSALS, user_claims('u1'),
                 update_body(colomers, {'name': 'Refugi de Colomers', 'coord': north(10)}))
    assert r.status_code == 201
    assert api_post(client, PROPOSALS, user_claims('u1'), delete_body(colomers)).status_code == 201


def test_nomes_contra_refugis_existents_no_contra_propostes_pendents(client, world):
    make_proposal(payload={'name': 'Cabana Nova', 'coord': {'lat': 44.0, 'long': 2.0}})
    assert post(client, 'Cabana Nova', {'lat': 44.0, 'long': 2.0}).status_code == 201


def test_un_cop_aprovada_la_primera_la_segona_ja_es_duplicat(client, world):
    from apps.proposals.tests.helpers import admin_claims, approve_url, new_refuge_id
    pid = post(client, 'Cabana Nova', {'lat': 44.0, 'long': 2.0}).json()['id']
    assert api_post(client, approve_url(pid), admin_claims('adm')).status_code == 200
    r = post(client, 'Cabana Nova', {'lat': 44.001, 'long': 2.0}, uid='u2')
    assert r.status_code == 409 and r.json()['possible_duplicates'][0]['id'] == new_refuge_id(pid)


def test_la_validacio_va_abans_del_409(client, colomers):
    r = api_post(client, PROPOSALS, user_claims('u1'), create_body(name='Refugi de Colomers', altitude=99999,
                                                                  coord=north(10)))
    assert r.status_code == 400


def test_el_409_no_deixa_rastre_a_la_bd(client, colomers):
    post(client, 'Refugi de Colomers', north(10))
    assert count_proposals() == 0 and proposal_ids() == set()


def test_una_consulta_mes_i_constant(client, world):
    counts = []
    for n in (0, 8):
        for i in range(n):
            make_refuge(name=f'Altre {i}', lat=46 + i * 0.1)
        for i in range(n):
            make_refuge(name='Colomers', lat=LAT, long=LONG + 0.0001 * (i + 1))
        with QueryCounter() as q:
            r = post(client, f'Cabana Inexistent {n}', {'lat': 47.5, 'long': 3.0})
        assert r.status_code == 201
        counts.append(q.count)
    assert counts[0] == counts[1] <= 5, counts
    with QueryCounter() as q:
        r = post(client, 'Colomers', {'lat': LAT, 'long': LONG})
    assert r.status_code == 409 and len(r.json()['possible_duplicates']) == 8 and q.count <= counts[0], q.queries
