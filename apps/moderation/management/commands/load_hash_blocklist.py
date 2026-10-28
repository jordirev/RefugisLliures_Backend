"""
Càrrega de la llista de hashes prohibits (CSAM) des d'un CSV (decisió del PO, 28/10; docs/design/postgres-schema.md §2.22).

    python manage.py load_hash_blocklist <fitxer.csv> [--database migrator]

La taula és il·legible per a `app`: s'escriu amb el rol propietari (`migrator`). Format: capçalera `sha256,phash,category,
source`; `sha256` (64 hexadecimals) i/o `phash` (1–16 hexadecimals de 64 bits; es desa com a enter amb signe), `category`
`csam`|`other` (buida = `csam`) i `source` obligatori (≤ 100). **Tot o res**: qualsevol fila invàlida és un `CommandError`
amb el número de línia i no s'escriu res. **Idempotent**: una entrada ja present (mateix `sha256`, o mateix `phash` sense
`sha256`) no es duplica. Accepta BOM i salts de línia CRLF (Excel).
"""
import csv
import re
from typing import List, Optional, Tuple

from django.core.management.base import BaseCommand, CommandError
from django.db import connections, transaction

from apps.moderation.hashing import phash_hex_to_signed
from apps.moderation.models import HashCategory

HEADER = ['sha256', 'phash', 'category', 'source']
SOURCE_MAX = 100
_SHA256 = re.compile(r'^[0-9a-f]{64}$')

_INSERT_SHA_SQL = (
    'INSERT INTO moderation.moderation_hash_blocklist (sha256, phash, category, source) VALUES (%s, %s::bigint, %s, %s) '
    'ON CONFLICT (sha256) WHERE sha256 IS NOT NULL DO NOTHING')
_INSERT_PHASH_SQL = (
    'INSERT INTO moderation.moderation_hash_blocklist (phash, category, source) '
    'SELECT %s::bigint, %s::varchar, %s::varchar WHERE NOT EXISTS (SELECT 1 FROM moderation.moderation_hash_blocklist '
    'WHERE sha256 IS NULL AND phash = %s::bigint)')

Entry = Tuple[Optional[str], Optional[int], str, str]


def _parse_row(row: List[str], line: int) -> Entry:
    if len(row) != len(HEADER):
        raise CommandError(f'línia {line}: calen {len(HEADER)} columnes ({",".join(HEADER)})')
    sha_text, phash_text, category, source = (cell.strip() for cell in row)
    sha256 = sha_text.lower() or None
    if sha256 is not None and not _SHA256.match(sha256):
        raise CommandError(f'línia {line}: sha256 no vàlid (calen 64 hexadecimals)')
    phash = None
    if phash_text:
        try:
            phash = phash_hex_to_signed(phash_text)
        except ValueError:
            raise CommandError(f'línia {line}: phash no vàlid (calen 1-16 hexadecimals)') from None
    if sha256 is None and phash is None:
        raise CommandError(f'línia {line}: cal un sha256 i/o un phash')
    category = category.lower() or HashCategory.CSAM.value
    if category not in HashCategory.values:
        raise CommandError(f'línia {line}: categoria desconeguda (csam|other)')
    if not source or len(source) > SOURCE_MAX or not source.isprintable():
        raise CommandError(f'línia {line}: l\'origen és obligatori i ha de fer com a màxim {SOURCE_MAX} caràcters')
    return sha256, phash, category, source


def read_entries(path: str) -> List[Entry]:
    """Llegeix i valida tot el fitxer (sense tocar la BD)."""
    try:
        handle = open(path, encoding='utf-8-sig', newline='')
    except OSError as exc:
        raise CommandError(f"No es pot llegir el fitxer: {exc.strerror or 'error'}") from None
    entries: List[Entry] = []
    with handle:
        reader = csv.reader(handle)
        try:
            header = next(reader, None)
            if header is None or [c.strip().lower() for c in header] != HEADER:
                raise CommandError(f'La capçalera ha de ser: {",".join(HEADER)}')
            for row in reader:
                if not any(cell.strip() for cell in row):
                    continue                                    # línia en blanc
                entries.append(_parse_row(row, reader.line_num))
        except csv.Error as exc:
            raise CommandError(f'línia {reader.line_num}: CSV no vàlid ({exc})') from None
        except UnicodeDecodeError:
            raise CommandError('El fitxer ha de ser UTF-8') from None
    return entries


class Command(BaseCommand):
    help = 'Carrega la llista de hashes prohibits (CSAM) des d\'un CSV amb el rol migrator (idempotent, tot o res)'

    def add_arguments(self, parser):
        parser.add_argument('file', help='CSV amb capçalera sha256,phash,category,source')
        parser.add_argument('--database', default='migrator',
                            help='Alies de la BD amb privilegis sobre la taula (per defecte migrator)')

    def handle(self, *args, **options):
        entries = read_entries(options['file'])
        alias = options['database']
        added = existing = 0
        with transaction.atomic(using=alias):
            with connections[alias].cursor() as cur:
                for sha256, phash, category, source in entries:
                    text = None if phash is None else str(phash)         # text: -2**63 com a `int` no cap al literal
                    if sha256 is not None:
                        cur.execute(_INSERT_SHA_SQL, [sha256, text, category, source])
                    else:
                        cur.execute(_INSERT_PHASH_SQL, [text, category, source, text])
                    if cur.rowcount:
                        added += 1
                    else:
                        existing += 1
        self.stdout.write(f'Entrades afegides: {added}')
        self.stdout.write(f'Ja existents: {existing}')
