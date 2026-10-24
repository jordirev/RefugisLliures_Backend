"""
Generador d'identificadors UUID v7 (RFC 9562).

Disseny: `docs/design/postgres-schema.md` §1.4. És l'únic generador d'ID de les claus primàries
substitutes (`default=uuid7` a tots els models).

Format (128 bits): 48 bits de `unix_ts_ms` | 4 bits de versió (7) | 12 bits `rand_a` | 2 bits de variant (10) |
62 bits `rand_b`. La monotonicitat dins del procés s'obté amb el mètode 1 de la RFC (§6.2): `rand_a` fa de
comptador de 12 bits dins el mateix mil·lisegon. Si el comptador desborda, s'avança artificialment 1 ms; si el
rellotge retrocedeix poc (correccions NTP, fins a `_MAX_BACKWARDS_MS`), es continua amb l'últim timestamp perquè
l'ordre no es trenqui. Un salt enrere més gran es considera un canvi de rellotge i se'n segueix el valor.
"""
import os
import threading
import time
import uuid

_lock = threading.Lock()
_last_ms = -1
_counter = 0

_COUNTER_MAX = 0xFFF  # 12 bits
_MAX_BACKWARDS_MS = 10_000


def uuid7() -> uuid.UUID:
    """Retorna un UUID v7 estrictament creixent dins el procés (thread-safe)."""
    global _last_ms, _counter
    with _lock:
        now_ms = time.time_ns() // 1_000_000
        if now_ms > _last_ms or now_ms < _last_ms - _MAX_BACKWARDS_MS:
            _last_ms = now_ms
            # Inici del comptador amb marge per a incrementar dins el ms (bit alt a 0).
            _counter = int.from_bytes(os.urandom(2), 'big') & 0x7FF
        else:
            # Mateix mil·lisegon o rellotge enrere: es continua amb l'últim timestamp.
            _counter += 1
            if _counter > _COUNTER_MAX:
                _last_ms += 1
                _counter = int.from_bytes(os.urandom(2), 'big') & 0x7FF
        ts_ms, counter = _last_ms, _counter

    rand_b = int.from_bytes(os.urandom(8), 'big') & ((1 << 62) - 1)
    value = (ts_ms & ((1 << 48) - 1)) << 80
    value |= 0x7 << 76
    value |= counter << 64
    value |= 0b10 << 62
    value |= rand_b
    return uuid.UUID(int=value)
