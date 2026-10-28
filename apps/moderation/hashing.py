"""Conversió dels hashes perceptuals (pHash d'`imagehash`: 64 bits en hexadecimal) al `bigint` amb signe de la BD."""
import re

_PHASH_HEX = re.compile(r'^[0-9a-fA-F]{1,16}$')
PHASH_BITS = 64


def phash_hex_to_signed(value: str) -> int:
    """
    64 bits en hexadecimal -> enter amb signe (`n - 2**64` si `n >= 2**63`), com es desa a `phash` (§2.22).
    `ValueError` si no és hexadecimal o supera els 64 bits; `TypeError` si no és text.
    """
    if not isinstance(value, str):
        raise TypeError('El pHash ha de ser text hexadecimal')
    text = value.strip()
    if not _PHASH_HEX.match(text):
        raise ValueError('pHash no vàlid: calen 1-16 dígits hexadecimals')
    number = int(text, 16)
    return number - (1 << PHASH_BITS) if number >= (1 << (PHASH_BITS - 1)) else number
