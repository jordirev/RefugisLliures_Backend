"""
Llista de hashes prohibits (chunk 9; §2.22; decisió del PO 28/10): `fn_hash_match`, el selector, `ModerationService` i
la comanda `load_hash_blocklist`.

Contracte:
- `moderation.fn_hash_match(p_sha256 text, p_phash bigint, p_max_distance int DEFAULT 6)` -> `(entry_id uuid, category
  text, match_type text)`, com a màxim una fila: `sha256` exacte o `bit_count((phash # p_phash)::bit(64)) <= distància`.
- `apps.moderation.services.phash_hex_to_signed(hex) -> int`: 64 bits en hexadecimal -> enter amb signe (`n - 2**64` si
  `n >= 2**63`); `ValueError` si no és hexadecimal o supera els 64 bits.
- `apps.moderation.selectors.hash_match(sha256=None, phash_hex=None) -> HashMatch | None` (`entry_id: str`, `category`,
  `match_type`), només via `fn_hash_match` (cap SELECT a la taula). Un `phash_hex` invàlid no coincideix (no llança).
- `api.services.moderation_service.ModerationService.check(ModerationInput)` continua sent el punt d'entrada de la
  pujada; el seu `HashBlocklistProvider` ja no usa Firestore ni cache: `ModerationResult(True, 'hash_blocklist',
  category, match_type, {'entry_id': str})`.
- Comanda `python manage.py load_hash_blocklist <fitxer.csv> [--database migrator]`: CSV amb capçalera
  `sha256,phash,category,source`; `sha256` (64 hex) i/o `phash` (1–16 hex; es desa amb signe), `category` `csam`|`other`
  (buida = `csam`), `source` obligatori (≤ 100). Tot o res: qualsevol fila invàlida -> `CommandError` amb el número de
  línia i no s'escriu res. Idempotent (no duplica). Sortida: «Entrades afegides: N» i «Ja existents: M».
"""
import pytest
from django.core.management import call_command, get_commands
from django.core.management.base import CommandError

from apps.core.testing import fetch_all, fetch_one
from apps.moderation.tests.helpers import make_hash

pytestmark = [pytest.mark.db_infra, pytest.mark.integration, pytest.mark.real_permissions]

SHA = 'ab' * 32


def signed(n):
    return n - 2 ** 64 if n >= 2 ** 63 else n


def flip(n, bits):
    for b in bits:
        n ^= 1 << b
    return n


def match(sha=None, phash=None, dist=None):
    from apps.moderation.tests.helpers import sql
    if dist is None:
        return sql('SELECT category, match_type FROM moderation.fn_hash_match(%s, %s)', [sha, phash])
    return sql('SELECT category, match_type FROM moderation.fn_hash_match(%s, %s, %s)', [sha, phash, dist])


# =================================== conversió hex -> bigint amb signe ===================================

@pytest.mark.parametrize('hex_value,expected', [
    ('0', 0), ('0000000000000000', 0), ('ff', 255), ('7fffffffffffffff', 2 ** 63 - 1),
    ('8000000000000000', -2 ** 63), ('ffffffffffffffff', -1), ('FFFFFFFFFFFFFFFE', -2),
    ('a5a5a5a5a5a5a5a5', signed(0xa5a5a5a5a5a5a5a5)), (' d1d1d1d1d1d1d1d1 ', signed(0xd1d1d1d1d1d1d1d1)),
])
def test_conversio_phash_hex_a_bigint_amb_signe(services, hex_value, expected):
    assert services.phash_hex_to_signed(hex_value) == expected


@pytest.mark.parametrize('bad', ['', 'xyz', '0x1f', '1' * 17, '-1', None, 'g' * 16])
def test_conversio_rebutja_el_que_no_es_hex_de_64_bits(services, bad):
    with pytest.raises((ValueError, TypeError)):
        services.phash_hex_to_signed(bad)


# =================================== fn_hash_match ===================================

@pytest.mark.django_db
def test_sha256_exacte(world):
    make_hash(sha256=SHA, category='csam')
    assert match(SHA) == [('csam', 'sha256')]
    assert match('cd' * 32) == []
    assert match(None, None) == []


@pytest.mark.django_db
def test_sha256_es_sensible_a_un_sol_caracter(world):
    make_hash(sha256=SHA)
    assert match(SHA[:-1] + 'c') == []


@pytest.mark.django_db
def test_phash_amb_distancia_de_hamming_fins_a_6(world):
    base = 0x0F0F0F0F0F0F0F0F
    make_hash(phash=signed(base))
    assert match(None, signed(base)) == [('csam', 'phash')]
    assert match(None, signed(flip(base, range(0, 6)))) == [('csam', 'phash')]            # distància 6: coincideix
    assert match(None, signed(flip(base, range(0, 7)))) == []                              # distància 7: no
    assert match(None, signed(flip(base, [63, 31, 0]))) == [('csam', 'phash')]            # bits alts i baixos


@pytest.mark.django_db
def test_phash_amb_valors_negatius_i_pas_pel_bit_de_signe(world):
    make_hash(phash=signed(0xFFFFFFFFFFFFFFFF))                     # -1
    assert match(None, signed(0xFFFFFFFFFFFFFFFF ^ 0b111)) == [('csam', 'phash')]
    assert match(None, signed(0x7FFFFFFFFFFFFFFF)) == [('csam', 'phash')]        # 1 bit de diferència (el de signe)
    assert match(None, 0) == []                                                  # 64 bits de diferència


@pytest.mark.django_db
def test_distancia_maxima_parametritzable(world):
    base = 0x00000000000000FF
    make_hash(phash=signed(base))
    probe = signed(flip(base, range(0, 8)))                          # 8 bits de diferència
    assert match(None, probe) == []
    assert match(None, probe, 8) == [('csam', 'phash')]
    assert match(None, probe, 0) == []


@pytest.mark.django_db
def test_phash_nul_no_coincideix_amb_cap_entrada_i_les_entrades_sense_phash_no_coincideixen(world):
    make_hash(sha256=SHA)                                            # sense phash
    make_hash(phash=5)
    assert match(None, None) == []
    assert match('00' * 32, 6) == [('csam', 'phash')]                # 5 vs 6 = 2 bits de diferència


@pytest.mark.django_db
def test_retorna_la_categoria_de_l_entrada_i_com_a_molt_una_fila(world):
    make_hash(sha256=SHA, phash=3, category='other')
    make_hash(phash=3, category='other')
    rows = match(SHA, 3)
    assert len(rows) == 1 and rows[0][0] == 'other' and rows[0][1] in ('sha256', 'phash')


# =================================== selector ===================================

@pytest.mark.django_db
def test_selector_sha256_i_phash(world, selectors):
    entry = make_hash(sha256=SHA, category='csam')
    hit = selectors.hash_match(sha256=SHA)
    assert (hit.entry_id, hit.category, hit.match_type) == (entry, 'csam', 'sha256')
    other = make_hash(phash=signed(0xF0F0F0F0F0F0F0F0), category='other')
    hit = selectors.hash_match(sha256='00' * 32, phash_hex='f0f0f0f0f0f0f0f1')
    assert (hit.entry_id, hit.category, hit.match_type) == (other, 'other', 'phash')
    assert selectors.hash_match(sha256='00' * 32, phash_hex='0f0f0f0f0f0f0f0f') is None
    assert selectors.hash_match() is None


@pytest.mark.django_db
def test_selector_amb_phash_invalid_no_coincideix_ni_llanca(world, selectors):
    make_hash(phash=0)
    assert selectors.hash_match(phash_hex='no-es-hex') is None
    assert selectors.hash_match(phash_hex='') is None


@pytest.mark.django_db
def test_el_selector_no_llegeix_mai_la_taula(world, selectors):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext
    make_hash(sha256=SHA)
    with CaptureQueriesContext(connection) as ctx:
        selectors.hash_match(sha256=SHA, phash_hex='0000000000000001')
    sqls = [q['sql'] for q in ctx.captured_queries if 'set_config' not in q['sql']]
    assert len(sqls) == 1 and 'fn_hash_match' in sqls[0]
    assert 'FROM "moderation"."moderation_hash_blocklist"' not in sqls[0]


# =================================== ModerationService ===================================

@pytest.mark.django_db
def test_moderation_service_bloqueja_per_sha256_i_phash(world):
    from api.services.moderation_service import ModerationInput, ModerationService
    entry = make_hash(sha256=SHA)
    res = ModerationService().check(ModerationInput(sha256=SHA))
    assert res.blocked and (res.provider, res.category, res.match_type) == ('hash_blocklist', 'csam', 'sha256')
    assert res.details == {'entry_id': entry}
    near = make_hash(phash=signed(0x1234567812345678))
    res = ModerationService().check(ModerationInput(sha256='00' * 32, phash='1234567812345670'))
    assert res.blocked and res.match_type == 'phash' and res.details == {'entry_id': near}


@pytest.mark.django_db
def test_moderation_service_no_bloqueja_si_no_coincideix_i_no_toca_firestore_ni_cache(world):
    from api.services.moderation_service import ModerationInput, ModerationService
    make_hash(sha256=SHA)
    res = ModerationService().check(ModerationInput(sha256='11' * 32, phash='ffffffffffffffff'))
    assert res.blocked is False
    # el conftest arrel prohibeix Firestore real: si arribés a tocar-lo hauria fallat


def test_moderation_service_ja_no_importa_firestore_ni_cache():
    from pathlib import Path
    import api.services.moderation_service as mod
    text = Path(mod.__file__).read_text(encoding='utf-8')
    assert 'firestore' not in text.lower() and 'cache_service' not in text


# =================================== comanda load_hash_blocklist ===================================

@pytest.fixture
def blocklist(migrator_db):
    def wipe():
        with migrator_db.cursor() as cur:
            cur.execute('DELETE FROM moderation.moderation_hash_blocklist')
    wipe()
    yield migrator_db
    wipe()


def csv_file(tmp_path, rows, header='sha256,phash,category,source'):
    path = tmp_path / 'hashes.csv'
    path.write_text('\n'.join([header, *rows]) + '\n', encoding='utf-8')
    return str(path)


def load(path, *extra):
    from io import StringIO
    out = StringIO()
    call_command('load_hash_blocklist', path, '--database', 'migrator', *extra, stdout=out)
    return out.getvalue()


def entries(conn):
    return fetch_all(conn, 'SELECT sha256, phash, category, source FROM moderation.moderation_hash_blocklist '
                           'ORDER BY sha256 NULLS LAST, phash')


def test_la_comanda_viu_a_apps_moderation_i_l_alias_per_defecte_es_migrator():
    assert get_commands()['load_hash_blocklist'] == 'apps.moderation'
    from django.core.management import load_command_class
    parser = load_command_class('apps.moderation', 'load_hash_blocklist').create_parser('manage.py', 'load_hash_blocklist')
    args = parser.parse_args(['fitxer.csv'])
    assert args.database == 'migrator'


def test_carrega_les_entrades_amb_phash_amb_signe(blocklist, tmp_path):
    path = csv_file(tmp_path, [f'{SHA},,csam,NCMEC', ',ffffffffffffffff,other,llista interna', f'{"cd" * 32},8000000000000001,,IWF'])
    out = load(path)
    assert 'Entrades afegides: 3' in out and 'Ja existents: 0' in out
    assert entries(blocklist) == [
        (SHA, None, 'csam', 'NCMEC'), ('cd' * 32, signed(0x8000000000000001), 'csam', 'IWF'),
        (None, -1, 'other', 'llista interna')]


def test_la_categoria_buida_es_csam_i_els_hex_es_normalitzen_a_minuscules(blocklist, tmp_path):
    load(csv_file(tmp_path, [f'{"AB" * 32},ABCDEF0123456789,,font']))
    [(sha, phash, category, source)] = entries(blocklist)
    assert sha == 'ab' * 32 and phash == signed(0xabcdef0123456789) and category == 'csam'


def test_es_idempotent(blocklist, tmp_path):
    path = csv_file(tmp_path, [f'{SHA},,csam,NCMEC', ',0000000000000007,csam,NCMEC', f'{SHA},0000000000000009,csam,NCMEC'])
    assert 'Entrades afegides: 3' in load(path)
    out = load(path)
    assert 'Entrades afegides: 0' in out and 'Ja existents: 3' in out
    assert len(entries(blocklist)) == 3


def test_files_repetides_dins_del_mateix_fitxer_no_es_dupliquen(blocklist, tmp_path):
    out = load(csv_file(tmp_path, [f'{SHA},,csam,A', f'{SHA},,csam,A', ',0000000000000007,csam,A',
                                   ',0000000000000007,csam,A']))
    assert 'Entrades afegides: 2' in out and len(entries(blocklist)) == 2


def test_un_hash_carregat_es_detecta_amb_fn_hash_match_amb_el_rol_app(blocklist, tmp_path, app_db):
    load(csv_file(tmp_path, [f'{SHA},,csam,NCMEC', ',00000000000000ff,csam,NCMEC']))
    assert fetch_all(app_db, 'SELECT category, match_type FROM moderation.fn_hash_match(%s, NULL)', [SHA]) == [
        ('csam', 'sha256')]
    assert fetch_all(app_db, 'SELECT match_type FROM moderation.fn_hash_match(NULL, %s)', [0xfe]) == [('phash',)]


@pytest.mark.parametrize('row', [
    ',,csam,font',                              # cap hash
    f'{SHA[:-1]},,csam,font',                   # sha256 de 63 caràcters
    f'{"zz" * 32},,csam,font',                  # no és hexadecimal
    ',12345678901234567,csam,font',             # phash de 17 dígits
    ',nothex,csam,font',
    f'{SHA},,terror,font',                      # categoria desconeguda
    f'{SHA},,csam,',                            # sense origen
    f'{SHA},,csam,{"x" * 101}',                 # origen massa llarg
])
def test_una_fila_invalida_es_commandError_i_no_s_escriu_res(blocklist, tmp_path, row):
    path = csv_file(tmp_path, [f'{"11" * 32},,csam,ok', row])
    with pytest.raises(CommandError) as err:
        load(path)
    assert 'línia 3' in str(err.value)
    assert entries(blocklist) == []


def test_capcalera_incorrecta_o_fitxer_inexistent(blocklist, tmp_path):
    bad = csv_file(tmp_path, [f'{SHA},csam,font'], header='hash,category,source')
    with pytest.raises(CommandError):
        load(bad)
    with pytest.raises(CommandError):
        load(str(tmp_path / 'no-existeix.csv'))
    assert entries(blocklist) == []


def test_un_fitxer_buit_no_afegeix_res(blocklist, tmp_path):
    assert 'Entrades afegides: 0' in load(csv_file(tmp_path, []))
    assert entries(blocklist) == []


def test_fitxer_amb_bom_i_crlf(blocklist, tmp_path):
    path = tmp_path / 'excel.csv'
    path.write_bytes(('﻿sha256,phash,category,source\r\n' + f'{SHA},,csam,NCMEC\r\n').encode('utf-8'))
    assert 'Entrades afegides: 1' in load(str(path))
