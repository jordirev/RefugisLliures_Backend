"""
`puntua_refugi(info_comp)` (§9.1): valor inicial de la condició del refugi en la càrrega (substitueix
`assign_conditions`/`determine_condition`). Funció pura, sense BD.

Contracte: `puntua_refugi(info) -> (nota, total)` viu al mòdul de la comanda
(`apps.refuges.management.commands.load_refuges`, decisió del PO), amb `nota` enter 0-3 i `total` el punt brut
(màxim 9,5). Les claus que falten valen 0.
"""
import importlib
from collections import Counter

import pytest

from apps.refuges.tests.helpers import AMENITY_FIELDS, load_json

pytestmark = [pytest.mark.unit]


@pytest.fixture(scope='module')
def puntua():
    return importlib.import_module('apps.refuges.management.commands.load_refuges').puntua_refugi


FULL = {'lits': 1, 'matelas': 1, 'couvertures': 1, 'eau': 1, 'latrines': 1, 'poele': 1, 'bois': 1}


@pytest.mark.parametrize('info,nota,total', [
    ({}, 0, 0),
    ({'poele': 1}, 0, 1.5),                          # escalfor 1,5 → 0,47 → 0
    ({'cheminee': 1}, 0, 1),
    ({'cheminee': 1, 'bois': 1}, 0, 1.5),            # la llenya suma 0,5 només si hi ha foc
    ({'bois': 1}, 0, 0),                             # llenya sense foc: no suma
    ({'poele': 1, 'cheminee': 1, 'bois': 1}, 1, 2),  # escalfor topa a 2 → 2/9,5·3 = 0,63 → 1
    ({'couchage': 1, 'eau': 1}, 1, 4),               # 1,5 + 2,5 = 4 → 1,26 → 1
    ({'lits': 1}, 1, 3),                             # 3/9,5·3 = 0,95 → 1
    ({'bas_flancs': 1, 'matelas': 1}, 1, 3),
    ({'lits': 1, 'matelas': 1, 'couvertures': 1, 'mezzanine_etage': 1}, 1, 4),     # dormir 5,5 topa a 4
    (FULL, 3, 9.5),
    ({'eau': 1, 'latrines': 1}, 1, 3.5),
])
def test_casos_coneguts(puntua, info, nota, total):
    got_nota, got_total = puntua(info)
    assert got_nota == nota
    assert got_total == pytest.approx(total)


def test_manque_un_mur_resta_3_punts_i_limita_la_nota_a_1(puntua):
    nota, total = puntua({**FULL, 'manque_un_mur': 1})
    assert total == pytest.approx(6.5) and nota == 1       # sense el límit seria round(2,05) = 2


def test_manque_un_mur_sense_res_mes_es_zero(puntua):
    assert puntua({'manque_un_mur': 1}) == (0, 0)


def test_les_claus_que_falten_valen_zero_i_el_resultat_es_enter(puntua):
    nota, _ = puntua({'eau': 1})
    assert isinstance(nota, int) and nota == 1               # 2,5/9,5·3 = 0,79 → 1


@pytest.mark.parametrize('field', AMENITY_FIELDS)
def test_nota_sempre_entre_0_i_3(puntua, field):
    nota, total = puntua({field: 1})
    assert 0 <= nota <= 3 and 0 <= total <= 9.5


def test_distribucio_sobre_el_json_real(puntua):
    """§9.2 [FET]: 0 → 605 · 1 → 565 · 2 → 332 · 3 → 40 (1.542 refugis)."""
    dist = Counter(puntua(r['info_comp'])[0] for r in load_json())
    assert dict(dist) == {0: 605, 1: 565, 2: 332, 3: 40}


def test_no_modifica_l_entrada(puntua):
    info = dict(FULL)
    puntua(info)
    assert info == FULL
