"""
Comanda `load_refuges` (§9): càrrega **d'un sol ús** de `api/utils/final_data_refuges.json` amb el rol propietari.

    python manage.py load_refuges [--json PATH] [--dry-run] [--database ALIAS]

Contracte (respostes del PO): la comanda i `puntua_refugi` viuen a `apps/refuges/management/commands/load_refuges.py`;
**no hi ha `--overwrite`** i, si ja hi ha refugis a la BD, acaba amb `CommandError` sense escriure res (els antics
tests d'idempotència i d'`--overwrite` ara proven aquest error). L'alias per defecte és `migrator`; aquests tests
sempre el passen explícit. Fa `COMMIT` de debò (connexió `migrator`), per això usen la fixture `wipe_catalog`, que
neteja abans i després.
"""
import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.core.testing import fetch_all, fetch_one
from apps.refuges.tests.helpers import AMENITY_FIELDS, JSON_PATH, load_json

pytestmark = [pytest.mark.db_infra, pytest.mark.integration]


def run(*args, json_path=None):
    out, err = StringIO(), StringIO()
    argv = ['--database', 'migrator', *args]
    if json_path is not None:
        argv += ['--json', str(json_path)]
    call_command('load_refuges', *argv, stdout=out, stderr=err)
    return out.getvalue() + err.getvalue()


def counts(conn):
    return {t: fetch_one(conn, f'SELECT count(*) FROM refuges.{t}')[0]
            for t in ('refuges', 'refuge_amenities', 'refuge_links', 'refuge_media')}


def record(name='Cabane A', lat=42.5, long=1.5, **kw):
    r = {'name': name, 'coord': {'lat': lat, 'long': long}, 'altitude': 1500, 'places': 4, 'type': 'non gardé',
         'description': 'desc', 'links': ['https://a.org/1', 'https://a.org/2'], 'region': 'Ariège',
         'departement': 'Ariège', 'modified_at': '2024-05-17',
         'info_comp': {'cheminee': 1, 'eau': 1, 'bois': 1, 'lits': 1}}
    r.update(kw)
    return r


@pytest.fixture
def json_file(tmp_path):
    def _write(records, name='refuges.json'):
        p = tmp_path / name
        p.write_text(json.dumps(records), encoding='utf-8')
        return p
    return _write


# ============ Càrrega completa del JSON real (una sola vegada per mòdul) ============

@pytest.fixture(scope='module')
def full(django_db_setup, django_db_blocker):
    from django.db import connections
    with django_db_blocker.unblock():
        conn = connections['migrator']
        with conn.cursor() as cur:
            cur.execute('DELETE FROM refuges.refuges')
        report = run()
        yield report
        with conn.cursor() as cur:
            cur.execute('DELETE FROM refuges.refuges')
            cur.execute('DELETE FROM users.users')


@pytest.fixture
def mig(full, migrator_db):
    return migrator_db


def test_json_per_defecte_es_el_del_repo(full, mig):
    assert JSON_PATH.exists() and counts(mig)['refuges'] == 1542


def test_recomptes_1542_1542_2075(full, mig):
    c = counts(mig)
    assert (c['refuges'], c['refuge_amenities'], c['refuge_links'], c['refuge_media']) == (1542, 1542, 2075, 0)


def test_l_informe_conte_els_recomptes(full):
    for needle in ('1542', '2075'):
        assert needle in full, f"l'informe final ha de dir {needle}: {full!r}"


def test_condicio_inicial_amb_n_zero_i_distribucio_del_disseny(full, mig):
    rows = fetch_all(mig, "SELECT core.round_half_even(condition), count(*) FROM refuges.refuges "
                          "WHERE condition IS NOT NULL AND num_contributed_conditions = 0 "
                          "AND condition_reset_at IS NULL GROUP BY 1")
    assert dict(rows) == {0: 605, 1: 565, 2: 332, 3: 40}
    assert fetch_one(mig, "SELECT count(*) FROM refuges.refuges WHERE condition IS NULL "
                          "OR num_contributed_conditions <> 0")[0] == 0
    # `condition` llavor = nota entera (0-3) desada com a double
    assert fetch_one(mig, "SELECT count(*) FROM refuges.refuges WHERE condition <> floor(condition)")[0] == 0


def test_cada_refugi_es_correspon_amb_el_json(full, mig):
    """Compara camp a camp tots els refugis, amenities i enllaços amb el JSON (clau natural nom+coord)."""
    from apps.refuges.management.commands.load_refuges import puntua_refugi
    cols = ', '.join(f'a.{f}' for f in AMENITY_FIELDS)
    rows = fetch_all(mig, f"""
        SELECT r.name, ST_Y(r.coord::geometry), ST_X(r.coord::geometry), r.surname, r.type, r.altitude, r.places,
               r.remarque, r.description, r.region, r.departement, r.modified_at, r.condition,
               ARRAY(SELECT l.url FROM refuges.refuge_links l WHERE l.refuge_id = r.id ORDER BY l.position),
               {cols}
          FROM refuges.refuges r JOIN refuges.refuge_amenities a ON a.refuge_id = r.id""")
    db = {(r[0], round(r[1], 6), round(r[2], 6)): r for r in rows}
    data = load_json()
    assert len(db) == len(data) == 1542
    for rec in data:
        key = (rec['name'].strip(), round(rec['coord']['lat'], 6), round(rec['coord']['long'], 6))
        r = db[key]
        assert r[1] == pytest.approx(rec['coord']['lat'], abs=1e-9) and r[2] == pytest.approx(rec['coord']['long'], abs=1e-9)
        assert r[3] == ((rec.get('surname') or '').strip() or None)
        assert r[4] == rec['type']
        assert r[5] == rec['altitude']
        assert r[6] == rec['places']                                    # null → NULL, mai 0
        assert r[7] == ''                                               # `remarque` no és al JSON
        assert r[8] == (rec['description'] or '')
        assert r[9] == ((rec.get('region') or '').strip() or None)
        assert r[10] == ((rec.get('departement') or '').strip() or None)
        assert (r[11].isoformat() if r[11] else None) == rec.get('modified_at')
        assert r[12] == puntua_refugi(rec['info_comp'])[0]
        assert r[13] == rec['links']                                    # mateix ordre (position = índex)
        for f, v in zip(AMENITY_FIELDS, r[14:]):
            assert v is bool(rec['info_comp'].get(f, 0)), (rec['name'], f)


def test_regions_buides_passen_a_null(full, mig):
    assert fetch_one(mig, "SELECT count(*) FROM refuges.refuges WHERE region = '' OR departement = ''")[0] == 0
    assert fetch_one(mig, "SELECT count(*) FROM refuges.refuges WHERE region IS NULL OR departement IS NULL")[0] > 0


def test_places_sense_dada_son_null_i_no_zero(full, mig):
    assert fetch_one(mig, 'SELECT count(*) FROM refuges.refuges WHERE places IS NULL')[0] == 405


def test_hi_ha_noms_repetits_i_tots_carregats(full, mig):
    assert fetch_one(mig, "SELECT count(*) FROM (SELECT name FROM refuges.refuges GROUP BY name "
                          "HAVING count(*) > 1) d")[0] == 8


def test_amenities_no_tenen_les_dades_ignorades(full, mig):
    """`info_couchage` i `info_eau` s'ignoren (decisió del PLAN)."""
    cols = {r[0] for r in fetch_all(mig, "SELECT column_name FROM information_schema.columns "
                                         "WHERE table_schema = 'refuges'")}
    assert not ({'info_couchage', 'info_eau'} & cols)


def test_geohash_de_la_vista_coincideix_amb_generate_simple_geohash(full, mig):
    """§4: `ST_GeoHash(coord::geometry, 5)` == `generate_simple_geohash` actual (inferència del disseny)."""
    from api.daos.refuge_proposal_dao import generate_simple_geohash
    rows = fetch_all(mig, 'SELECT lat, lng, geohash FROM refuges.refuge_map')
    assert len(rows) == 1542
    bad = [(lat, lng, g) for lat, lng, g in rows if g != generate_simple_geohash(lat, lng)]
    assert bad == [], f'{len(bad)} geohash difereixen, p. ex. {bad[:3]}'


def test_segona_execucio_es_rebutjada_sense_escriure_res(full, mig):
    """Càrrega d'un sol ús (resposta 1 del PO): amb refugis a la BD, `CommandError` i cap canvi."""
    before = counts(mig)
    ids_before = {r[0] for r in fetch_all(mig, 'SELECT id FROM refuges.refuges')}
    with pytest.raises(CommandError, match='ja té refugis'):
        run()
    assert counts(mig) == before
    assert {r[0] for r in fetch_all(mig, 'SELECT id FROM refuges.refuges')} == ids_before, 'els ids no canvien'


def test_els_ids_son_uuid_v7(full, mig):
    versions = {r[0] for r in fetch_all(mig, "SELECT substr(id::text, 15, 1) FROM refuges.refuges")}
    assert versions == {'7'}


def test_cap_dada_d_altres_dominis(full, mig):
    assert fetch_one(mig, 'SELECT count(*) FROM users.users')[0] == 0


# ============ Comportament amb fitxers petits ============

def test_dry_run_no_escriu_res(wipe_catalog, json_file):
    report = run('--dry-run', json_path=json_file([record('A'), record('B', lat=43)]))
    assert counts(wipe_catalog) == {'refuges': 0, 'refuge_amenities': 0, 'refuge_links': 0, 'refuge_media': 0}
    assert '2' in report                                               # informa del que carregaria


def test_dry_run_amb_refugis_a_la_bd_tambe_es_rebutjat(wipe_catalog, json_file):
    run(json_path=json_file([record('A')]))
    with pytest.raises(CommandError, match='ja té refugis'):
        run('--dry-run', json_path=json_file([record('A'), record('B', lat=43)], 'b.json'))
    assert counts(wipe_catalog)['refuges'] == 1


def test_carrega_un_registre_amb_tots_els_camps(wipe_catalog, json_file):
    run(json_path=json_file([record(surname='  Alias  ', remarque_ignorada='x')]))
    row = fetch_one(wipe_catalog, """
        SELECT name, surname, altitude, places, type, ST_X(coord::geometry), ST_Y(coord::geometry),
               condition, num_contributed_conditions, modified_at::text FROM refuges.refuges""")
    # info_comp {cheminee, eau, bois, lits}: escalfor 1,5 + dormir 3 + aigua 2,5 = 7 → round(2,2) = 2
    assert row == ('Cabane A', 'Alias', 1500, 4, 'non gardé', 1.5, 42.5, 2.0, 0, '2024-05-17')


def test_nom_amb_espais_es_retalla(wipe_catalog, json_file):
    run(json_path=json_file([record('  Cabane A  ')]))
    assert fetch_one(wipe_catalog, 'SELECT name FROM refuges.refuges')[0] == 'Cabane A'


def test_amenities_absents_valen_fals_i_valors_0_1_es_conserven(wipe_catalog, json_file):
    run(json_path=json_file([record(info_comp={'eau': 1})]))
    got = fetch_one(wipe_catalog, 'SELECT eau, poele, manque_un_mur FROM refuges.refuge_amenities')
    assert got == (True, False, False)


def test_un_refugi_preexistent_bloqueja_la_carrega_sense_escriure_res(wipe_catalog, json_file):
    """Ja no es identifiquen refugis per clau natural: qualsevol refugi a la BD atura la càrrega."""
    from apps.refuges.models import Refuge
    from django.contrib.gis.geos import Point
    pre = Refuge.objects.using('migrator').create(name='Cabane A', coord=Point(1.5, 42.5, srid=4326))
    with pytest.raises(CommandError, match='ja té refugis'):
        run(json_path=json_file([record('Cabane A'), record('Cabane B', lat=43)]))
    assert [r[0] for r in fetch_all(wipe_catalog, 'SELECT id FROM refuges.refuges')] == [pre.pk]
    assert counts(wipe_catalog) == {'refuges': 1, 'refuge_amenities': 0, 'refuge_links': 0, 'refuge_media': 0}


def test_mateix_nom_i_altres_coordenades_son_refugis_diferents(wipe_catalog, json_file):
    run(json_path=json_file([record('Dup', lat=42.5), record('Dup', lat=42.6)]))
    assert counts(wipe_catalog)['refuges'] == 2


def test_la_comanda_no_accepta_overwrite(wipe_catalog, json_file):
    """Resposta 1 del PO: no hi ha `--overwrite` (no es poden trepitjar les edicions fetes via propostes)."""
    with pytest.raises(CommandError):
        run('--overwrite', json_path=json_file([record('A')]))
    assert counts(wipe_catalog)['refuges'] == 0


def test_no_toca_els_mitjans_ni_els_usuaris_existents_si_la_carrega_es_rebutjada(wipe_catalog, json_file):
    from apps.refuges.tests.helpers import T0
    run(json_path=json_file([record('A')]))
    with wipe_catalog.cursor() as cur:
        cur.execute("INSERT INTO users.users (uid) VALUES ('u1')")
        cur.execute("INSERT INTO refuges.refuge_media (key, refuge_id, creator_uid, media_type, content_type, "
                    "status, uploaded_at, rights_confirmed_at) SELECT 'k.webp', id, 'u1', 'image', 'image/webp', "
                    "'visible', %s, %s FROM refuges.refuges", [T0, T0])
    with pytest.raises(CommandError):
        run(json_path=json_file([record('B', lat=43)], 'b.json'))
    assert counts(wipe_catalog)['refuge_media'] == 1


# ---------- Validació: s'informa de tots els registres invàlids i no s'escriu res ----------

BAD = [
    ('lat fora de rang', record('Mala lat', lat=95)),
    ('long fora de rang', record('Mala long', long=181)),
    ('nom buit', record('   ')),
    ('altitud', record('Mala altitud', altitude=9000)),
    ('places negatives', record('Mala places', places=-1)),
    ('tipus', record('Mal tipus', type='garde')),
    ('link', record('Mal link', links=['ftp://x.org'])),
    ('info_comp', record('Mala info', info_comp={'eau': 2})),
    ('info_comp clau', record('Mala clau', info_comp={'piscina': 1})),
]


@pytest.mark.parametrize('label,bad', BAD, ids=[b[0] for b in BAD])
def test_un_registre_invalid_atura_la_carrega_sense_escriure(wipe_catalog, json_file, label, bad):
    with pytest.raises(CommandError):
        run(json_path=json_file([record('Bo'), bad]))
    assert counts(wipe_catalog)['refuges'] == 0


def test_s_informa_de_tots_els_invalids(wipe_catalog, json_file):
    records = [record('Bo')] + [b for _, b in BAD if b['name'].strip()]
    out = StringIO()
    with pytest.raises(CommandError) as exc:
        call_command('load_refuges', '--database', 'migrator', '--json', str(json_file(records)),
                     stdout=out, stderr=out)
    text = str(exc.value) + out.getvalue()
    for _, b in BAD:
        if b['name'].strip():
            assert b['name'] in text, f"falta {b['name']!r} a l'informe d'errors"
    assert counts(wipe_catalog)['refuges'] == 0


def test_fitxer_inexistent_o_no_llista(wipe_catalog, tmp_path, json_file):
    with pytest.raises(CommandError):
        run(json_path=tmp_path / 'no_existeix.json')
    bad = tmp_path / 'obj.json'
    bad.write_text('{"a": 1}', encoding='utf-8')
    with pytest.raises(CommandError):
        run(json_path=bad)
    broken = tmp_path / 'trencat.json'
    broken.write_text('[{', encoding='utf-8')
    with pytest.raises(CommandError):
        run(json_path=broken)


def test_tot_en_una_transaccio_si_alguna_cosa_falla_no_queda_res(wipe_catalog, json_file):
    """Un enllaç repetit dins la mateixa fitxa (UNIQUE refugi+url) aborta la càrrega sencera: ni el registre bo."""
    dup = record('Dup links', lat=43, links=['https://a.org/x', 'https://a.org/x'])
    with pytest.raises(Exception):
        run(json_path=json_file([record('Bo'), dup]))
    assert counts(wipe_catalog) == {'refuges': 0, 'refuge_amenities': 0, 'refuge_links': 0, 'refuge_media': 0}


def test_comanda_amb_el_rol_app_no_pot_escriure(wipe_catalog, json_file):
    """La càrrega és una operació d'administració: amb `default` (rol app, sense context) la RLS ho denega."""
    with pytest.raises(Exception):
        call_command('load_refuges', '--database', 'default', '--json', str(json_file([record('A')])),
                     stdout=StringIO(), stderr=StringIO())
    assert counts(wipe_catalog)['refuges'] == 0


def test_l_alias_per_defecte_es_migrator_i_no_hi_ha_overwrite():
    """Resposta 2 del PO: per defecte el rol propietari (`migrator`); sense `--overwrite`."""
    from apps.refuges.management.commands.load_refuges import Command
    parser = Command().create_parser('manage.py', 'load_refuges')
    args = parser.parse_args([])
    assert args.database == 'migrator' and args.dry_run is False and not hasattr(args, 'overwrite')
