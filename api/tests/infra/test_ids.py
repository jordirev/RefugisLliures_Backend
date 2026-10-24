"""Tests de `api/utils/ids.py: uuid7()` (RFC 9562, monotonia dins el mateix mil·lisegon)."""
import re
import threading
import time
import uuid
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.unit


@pytest.fixture
def uuid7():
    from api.utils.ids import uuid7 as fn
    return fn


def _ts_ms(u: uuid.UUID) -> int:
    return u.int >> 80


def test_retorna_uuid_versio_7_i_variant_rfc(uuid7):
    u = uuid7()
    assert isinstance(u, uuid.UUID)
    assert u.version == 7
    assert u.variant == uuid.RFC_4122
    # bits de variant 10xx
    assert (u.int >> 62) & 0b11 == 0b10


def test_format_canonic_minuscules(uuid7):
    s = str(uuid7())
    assert re.fullmatch(r'[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}', s)


def test_timestamp_proper_a_ara(uuid7):
    before = int(time.time() * 1000)
    u = uuid7()
    after = int(time.time() * 1000)
    assert before - 1 <= _ts_ms(u) <= after + 1


def test_ordenable_creixent_en_bucle_estret(uuid7):
    ids = [uuid7() for _ in range(20000)]
    assert len(set(ids)) == len(ids)
    assert all(a < b for a, b in zip(ids, ids[1:])), "uuid7 ha de ser estrictament creixent dins el procés"
    strs = [str(i) for i in ids]
    assert strs == sorted(strs), "l'ordre lexicogràfic del text ha de coincidir amb l'ordre de generació"


def test_monotonic_amb_rellotge_congelat(uuid7):
    """Mateix mil·lisegon: el comptador de rand_a fa que segueixin creixent."""
    fixed = 1_700_000_000_123 * 1_000_000
    with patch('time.time_ns', return_value=fixed):
        ids = [uuid7() for _ in range(200)]
    assert all(_ts_ms(i) == 1_700_000_000_123 for i in ids)
    assert all(a < b for a, b in zip(ids, ids[1:]))
    assert len(set(ids)) == 200


def test_monotonic_si_el_comptador_desborda(uuid7):
    """Més de 4096 crides al mateix ms: no es pot repetir ni retrocedir (el timestamp avança artificialment)."""
    fixed = 1_700_000_000_123 * 1_000_000
    with patch('time.time_ns', return_value=fixed):
        ids = [uuid7() for _ in range(6000)]
    assert len(set(ids)) == 6000
    assert all(a < b for a, b in zip(ids, ids[1:]))
    assert all(i.version == 7 and i.variant == uuid.RFC_4122 for i in ids)


def test_monotonic_si_el_rellotge_retrocedeix(uuid7):
    t0 = 1_700_000_000_500 * 1_000_000
    seq = iter([t0, t0 + 3_000_000, t0 - 5_000_000, t0 - 5_000_000, t0 + 10_000_000])
    with patch('time.time_ns', side_effect=lambda: next(seq)):
        ids = [uuid7() for _ in range(5)]
    assert all(a < b for a, b in zip(ids, ids[1:]))


def test_avanca_amb_el_temps(uuid7):
    a = uuid7()
    time.sleep(0.01)
    b = uuid7()
    assert b > a
    assert _ts_ms(b) - _ts_ms(a) >= 9


def test_unic_amb_fils(uuid7):
    out, lock = [], threading.Lock()

    def work():
        local = [uuid7() for _ in range(2000)]
        with lock:
            out.extend(local)

    threads = [threading.Thread(target=work) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(out) == 16000
    assert len(set(out)) == 16000


def test_es_cridable_sense_arguments_com_a_default_de_django(uuid7):
    from django.db import models
    field = models.UUIDField(primary_key=True, default=uuid7)
    assert field.get_default().version == 7


def test_bits_aleatoris_no_constants(uuid7):
    """Els 62 bits baixos han de variar entre crides de ms diferents (no un valor fix)."""
    vals = set()
    for _ in range(20):
        vals.add(uuid7().int & ((1 << 62) - 1))
        time.sleep(0.002)
    assert len(vals) > 15
