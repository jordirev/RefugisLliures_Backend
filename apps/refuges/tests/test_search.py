"""
Cerca de refugis (§5.3 recepta 4): nom parcial i sense accents amb pg_trgm + `core.norm_name`, filtres en SQL,
condició sobre `core.round_half_even(condition)` (0-3) i ús dels índexs GIN/GIST.
"""
import pytest
from django.db import connection

from apps.refuges.tests.helpers import QueryCounter, api_get, make_refuge

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration]

URL = '/api/refuges/'


def search(client, qs, claims=None):
    r = api_get(client, f'{URL}?{qs}', claims)
    assert r.status_code == 200, r.content
    data = r.json()
    assert set(data) == {'count', 'results'}, 'sense has_filters (el frontend no el llegeix)'
    return data


def names(data):
    return [x['name'] for x in data['results']]


# ============ Nom: parcial, sense accents, sense majúscules ============

@pytest.fixture
def named(RM):
    make_refuge("Refugi d'Àrreu", lat=42.60, long=0.90)
    make_refuge('Cabane de l’Ôrri', lat=42.61, long=0.91)
    make_refuge('Colomers', lat=42.62, long=0.92)
    make_refuge('Refugi de Colomers', lat=42.63, long=0.93)
    make_refuge('Colomers de dalt', lat=42.64, long=0.94)
    make_refuge('Besiberri', lat=42.65, long=0.95, surname='Niu de la Mola')


@pytest.mark.parametrize('q,expected', [
    ('arreu', ["Refugi d'Àrreu"]),                    # sense accent
    ('ÀRREU', ["Refugi d'Àrreu"]),                    # majúscules i accent
    ('ARREU', ["Refugi d'Àrreu"]),
    ('rreu', ["Refugi d'Àrreu"]),                     # parcial
    ('orri', ['Cabane de l’Ôrri']),                   # accent circumflex
    ('Besiberri', ['Besiberri']),
    ('besiber', ['Besiberri']),
])
def test_cerca_per_nom(client, named, q, expected):
    assert names(search(client, f'name={q}')) == expected


def test_cerca_per_nom_sense_resultats(client, named):
    d = search(client, 'name=zzzzzzzz')
    assert d == {'count': 0, 'results': []}


def test_cerca_tolera_una_errada_de_lletra_amb_similitud_trigram(client, named):
    assert 'Colomers' in names(search(client, 'name=colmers'))


def test_cerca_ordena_per_similitud_descendent_i_despres_nom(client, named):
    got = names(search(client, 'name=colomers'))
    assert got[0] == 'Colomers'                           # coincidència exacta, similitud 1
    assert set(got) == {'Colomers', 'Refugi de Colomers', 'Colomers de dalt'}
    assert got.index('Colomers de dalt') < got.index('Refugi de Colomers'), 'més similar primer'


def test_cerca_per_surname_alies(client, named):
    """§2.5: el `surname` es desa i s'usa només per a la cerca; no s'emet."""
    d = search(client, 'name=niu mola')
    assert names(d) == ['Besiberri'] and 'surname' not in d['results'][0]


def test_cerca_retorna_tots_els_refugis_amb_el_mateix_nom(client, RM):
    """B2: el DAO antic assumia nom únic; el JSON té 8 noms repetits."""
    for i in range(3):
        make_refuge('Cabane de la Plagne', lat=42 + i / 10, long=1.0)
    assert names(search(client, 'name=Cabane de la Plagne')) == ['Cabane de la Plagne'] * 3


@pytest.mark.parametrize('q', ['%25', '%25%25%25', "'; DROP TABLE refuges.refuges; --", '\\', 'a%27%20OR%201=1'])
def test_cerca_amb_comodins_i_injeccio_no_coincideix_amb_tot(client, named, q):
    d = search(client, f'name={q}')
    assert d['count'] == 0
    assert api_get(client, URL).json()['count'] == 6, 'la taula continua intacta'


def test_cerca_per_nom_combinada_amb_filtres(client, RM):
    make_refuge('Colomers A', lat=42.1, type='orri', places=4)
    make_refuge('Colomers B', lat=42.2, type='fermée', places=20)
    assert names(search(client, 'name=colomers&type=orri')) == ['Colomers A']
    assert names(search(client, 'name=colomers&places_min=10')) == ['Colomers B']
    assert search(client, 'name=colomers&places_min=10&type=orri')['count'] == 0


# ============ Filtres numèrics, tipus i condició ============

@pytest.fixture
def catalog(RM):
    rows = [
        # name,      type,      alt,  places, condition, n
        ('a_orri',   'orri',    1000, 4,    0.4,  1),
        ('b_orri',   'orri',    2000, None, 0.5,  1),
        ('c_ferm',   'fermée',  2500, 10,   1.5,  2),
        ('d_ferm',   'fermée',  None, 20,   2.5,  2),
        ('e_non',    'non gardé', 3000, 0,  2.51, 2),
        ('f_non',    'non gardé', 500, 30,  None, 0),
    ]
    for i, (name, t, alt, pl, cond, n) in enumerate(rows):
        make_refuge(name, lat=42 + i / 10, long=1 + i / 10, type=t, altitude=alt, places=pl, condition=cond,
                    num_contributed_conditions=n)


@pytest.mark.parametrize('qs,expected', [
    ('type=orri', {'a_orri', 'b_orri'}),
    ('type=orri,fermée', {'a_orri', 'b_orri', 'c_ferm', 'd_ferm'}),
    ('type=emergence', set()),
    ('places_min=10', {'c_ferm', 'd_ferm', 'f_non'}),
    ('places_max=10', {'a_orri', 'c_ferm', 'e_non'}),                   # NULL no compleix cap rang
    ('places_min=4&places_max=10', {'a_orri', 'c_ferm'}),
    ('places_min=0&places_max=0', {'e_non'}),
    ('altitude_min=2000', {'b_orri', 'c_ferm', 'e_non'}),
    ('altitude_max=1000', {'a_orri', 'f_non'}),
    ('altitude_min=1000&altitude_max=2500', {'a_orri', 'b_orri', 'c_ferm'}),
    ('type=non gardé&altitude_min=1000', {'e_non'}),
    ('type=fermée&places_min=15', {'d_ferm'}),
])
def test_filtres_en_sql(client, catalog, qs, expected):
    assert set(names(search(client, qs))) == expected


@pytest.mark.parametrize('qs,expected', [
    ('condition=0', {'a_orri', 'b_orri'}),            # 0,4 i 0,5 → 0 (half-to-even)
    ('condition=1', set()),
    ('condition=2', {'c_ferm', 'd_ferm'}),            # 1,5 → 2 i 2,5 → 2
    ('condition=3', {'e_non'}),                       # 2,51 → 3 (el filtre accepta 0-3)
    ('condition=0,3', {'a_orri', 'b_orri', 'e_non'}),
    ('condition=0,1,2,3', {'a_orri', 'b_orri', 'c_ferm', 'd_ferm', 'e_non'}),   # sense valoració: mai coincideix
    ('condition=2&type=fermée', {'c_ferm', 'd_ferm'}),
    ('condition=2&places_min=15', {'d_ferm'}),
])
def test_filtre_de_condicio_sobre_el_valor_arrodonit(client, catalog, qs, expected):
    assert set(names(search(client, qs))) == expected


def test_la_condicio_serialitzada_coincideix_amb_la_del_filtre(client, catalog):
    for r in search(client, 'type=orri,fermée,non gardé')['results']:
        if r['condition'] is not None:
            assert search(client, f"condition={r['condition']}")['results'], r


def test_resultat_amb_filtres_es_el_refugi_complet(client, catalog):
    (r,) = search(client, 'type=orri&altitude_min=2000')['results']
    assert r['name'] == 'b_orri' and r['places'] is None and r['condition'] == 0


# ============ SQL i índexs ============

def _sql_of_search(client, qs):
    with QueryCounter() as q:
        search(client, qs)
    return q.queries


def test_la_cerca_per_nom_es_una_sola_consulta_amb_norm_name_i_trigram(client, named):
    queries = _sql_of_search(client, 'name=arreu')
    assert len(queries) == 1
    sql = queries[0]
    assert 'core.norm_name' in sql or '"norm_name"' in sql, sql
    assert '%%' in sql or ' % ' in sql or 'SIMILARITY' in sql.upper() or 'LIKE' in sql.upper(), sql


def test_la_cerca_per_condicio_usa_round_half_even_a_la_consulta(client, catalog):
    sql = _sql_of_search(client, 'condition=2')[0]
    assert 'round_half_even' in sql


def test_els_filtres_son_a_la_clausula_where_no_a_python(client, catalog):
    sql = _sql_of_search(client, 'type=orri&places_min=3&altitude_max=2500')[-1].upper()   # [0]: catàleg de tipus
    assert 'WHERE' in sql and 'PLACES' in sql and 'ALTITUDE' in sql and 'TYPE' in sql


def _explain(sql, params=None):
    with connection.cursor() as cur:
        cur.execute('SET LOCAL enable_seqscan = off')
        cur.execute('EXPLAIN ' + sql, params)
        return '\n'.join(r[0] for r in cur.fetchall())


def test_el_gin_trigram_s_usa_per_a_la_similitud_del_nom(named):
    plan = _explain("SELECT id FROM refuges.refuges WHERE core.norm_name(name) %% core.norm_name(%s)", ['colomers'])
    assert 'refuges_name_trgm_gin' in plan, plan


def test_el_gin_trigram_s_usa_per_a_la_cerca_parcial_like(named):
    plan = _explain("SELECT id FROM refuges.refuges WHERE core.norm_name(name) LIKE '%%' || core.norm_name(%s) || '%%'",
                    ['rreu'])
    assert 'refuges_name_trgm_gin' in plan, plan


def test_el_gin_trigram_del_surname_s_usa(named):
    plan = _explain("SELECT id FROM refuges.refuges WHERE surname IS NOT NULL "
                    "AND core.norm_name(surname) LIKE '%%' || core.norm_name(%s) || '%%'", ['mola'])
    assert 'refuges_surname_trgm_gin' in plan, plan


def test_el_gist_s_usa_per_a_la_proximitat(named):
    plan = _explain("SELECT id FROM refuges.refuges "
                    "WHERE ST_DWithin(coord, ST_SetSRID(ST_MakePoint(0.9, 42.6), 4326)::geography, 200)")
    assert 'refuges_coord_gist' in plan, plan


def test_el_gist_s_usa_per_a_la_caixa_del_mapa(named):
    plan = _explain("SELECT id FROM refuges.refuges "
                    "WHERE coord && ST_MakeEnvelope(0.8, 42.5, 1.0, 42.7, 4326)::geography")
    assert 'refuges_coord_gist' in plan, plan


def test_la_consulta_real_de_la_cerca_per_nom_usa_els_dos_gin_trigram(named):
    """No només el SQL a mà: el `QuerySet` que executa la vista fa `BitmapOr` sobre els GIN del nom i de l'àlies."""
    from apps.refuges import selectors
    sql, params = selectors.search_queryset({'name': 'colomers'}).query.sql_with_params()
    with connection.cursor() as cur:
        cur.execute('SET LOCAL enable_indexscan = off')    # amb estadístiques velles el planificador triaria la PK: només bitmap
    plan = _explain(sql, params)
    assert 'refuges_name_trgm_gin' in plan and 'refuges_surname_trgm_gin' in plan, plan
