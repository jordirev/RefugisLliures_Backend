"""Substitut de `psql -tA` per als e2e contra Neon `dev` (`PSQL_E2E`): SQL per stdin, connexió `migrator`.

Ús (des del checkout que té `env/`, amb el servidor e2e i l'emulador d'Auth en marxa):

    export PSQL_E2E="python scripts/e2e/psql_neon.py"
    BASE_URL=http://localhost:8020 bash scripts/e2e/e2e_chunk9.sh

Fa servir la URL `DATABASE_URL_MIGRATOR` de `env/.env.development` (branca `dev`) a través del settings de Django; mai
imprimeix la URL ni cap credencial. Ignora els arguments de `psql` (`-tA`, `-q`...). Sortida com `psql -tA`: files separades
amb `|`, booleans `t`/`f` i NULL com a cadena buida. Rebutja el mode producció: els e2e no s'han d'executar mai contra la
branca `production`.
"""
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]

for _flag in ('PRODUCTION', 'RENDER'):
    if (os.environ.get(_flag) or '').strip().lower() in ('true', '1', 'yes', 'on'):
        sys.exit(f'psql_neon.py: {_flag} està activat; els e2e només s\'executen contra Neon dev')

os.chdir(BASE_DIR)
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'refugis_lliures.settings')
os.environ.setdefault('FIREBASE_AUTH_EMULATOR_HOST', 'localhost:9099')

import django  # noqa: E402

django.setup()
from django.db import connections  # noqa: E402


def fmt(value):
    if value is None:
        return ''
    if value is True:
        return 't'
    if value is False:
        return 'f'
    return str(value)


def main():
    sql = sys.stdin.read()
    with connections['migrator'].cursor() as cursor:
        raw = cursor.cursor           # cursor de psycopg: admet diverses sentències i `nextset()`
        raw.execute(sql)
        while True:
            if raw.description:
                for row in raw.fetchall():
                    print('|'.join(fmt(v) for v in row))
            if not raw.nextset():
                break


if __name__ == '__main__':
    main()
