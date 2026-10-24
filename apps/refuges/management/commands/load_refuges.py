"""
`load_refuges`: càrrega **d'un sol ús** de `api/utils/final_data_refuges.json` a PostgreSQL
(docs/design/postgres-schema.md §9; substitueix `upload_refugis_to_firestore` i `assign_conditions`).

    python manage.py load_refuges [--json PATH] [--dry-run] [--database ALIAS]

- S'executa un sol cop per omplir la BD buida, per defecte amb l'àlies `migrator` (propietari: la RLS d'escriptura
  és només per a admin/sistema). Si ja hi ha refugis, acaba amb `CommandError` **sense escriure res** (no hi ha
  `--overwrite`: no es trepitgen les edicions fetes via propostes).
- Valida tot el JSON abans d'escriure: s'informa de **tots** els registres invàlids i l'execució s'atura.
- Tot en una transacció (`--dry-run` la desfà al final). Valor inicial de la condició: `puntua_refugi(info_comp)`
  (nota 0-3 desada com a decimal) amb `num_contributed_conditions = 0`.
"""
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

from django.conf import settings
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand, CommandError
from django.db import connections, transaction

from apps.refuges.models import Refuge, RefugeAmenities, RefugeLink, RefugeMedia, RefugeType

DEFAULT_JSON = Path(settings.BASE_DIR) / 'api' / 'utils' / 'final_data_refuges.json'
DEFAULT_ALIAS = 'migrator'
BATCH_SIZE = 500
_URL_RE = re.compile(r'^https?://', re.IGNORECASE)


# ---------- Valor inicial de la condició ----------

def puntua_refugi(info):
    """
    Nota inicial 0-3 d'un refugi a partir de `info_comp` (les claus que falten valen 0).

    Escalfor (0-2) + dormir (0-4) + aigua i higiene (0-3,5); `manque_un_mur` resta 3 punts i limita la nota a 1.
    Es normalitza a 0-3 sobre el màxim de 9,5 amb `round()` de Python (half-to-even).
    Retorna `(nota, total)`.
    """
    g = lambda k: info.get(k, 0)           # noqa: E731
    font = max(g('poele') * 1.5, g('cheminee') * 1)
    escalfor = min(2, font + (0.5 if g('bois') and font > 0 else 0))
    base = max(g('lits') * 3, g('bas_flancs') * 2, g('couchage') * 1.5)
    dormir = min(4, base + g('matelas') * 1 + g('couvertures') * 1 + g('mezzanine_etage') * 0.5)
    aigua = g('eau') * 2.5 + g('latrines') * 1
    total = escalfor + dormir + aigua
    total -= g('manque_un_mur') * 3
    total = max(0, total)
    nota = round(total / 9.5 * 3)
    if g('manque_un_mur'):
        nota = min(nota, 1)
    return nota, total


# ---------- Validació i conversió ----------

def _clean(value):
    """Text opcional: `strip()`; buit -> `None`."""
    if value is None:
        return None
    return str(value).strip() or None


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def parse_record(rec):
    """Valida un registre del JSON amb les regles de la BD. Retorna `(valors, errors)`."""
    errors = []
    if not isinstance(rec, dict):
        return None, ['el registre no és un objecte']
    name = _clean(rec.get('name'))
    if not name:
        errors.append('nom buit')
    elif len(name) > 255:
        errors.append('nom massa llarg (>255)')

    coord = rec.get('coord') if isinstance(rec.get('coord'), dict) else {}
    lat, lng = coord.get('lat'), coord.get('long')
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in (lat, lng)):
        errors.append('coord.lat/coord.long no són números')
    else:
        if not -90 <= lat <= 90:
            errors.append(f'latitud fora de rang ({lat})')
        if not -180 <= lng <= 180:
            errors.append(f'longitud fora de rang ({lng})')
        if lat == 0 and lng == 0:
            errors.append('coordenades (0, 0)')

    altitude, places = rec.get('altitude'), rec.get('places')
    if altitude is not None and not (_is_int(altitude) and 0 <= altitude <= 8848):
        errors.append(f'altitud fora de rang ({altitude})')
    if places is not None and not (_is_int(places) and places >= 0):
        errors.append(f'places invàlides ({places})')

    rtype = rec.get('type')
    if rtype not in RefugeType.values:
        errors.append(f'tipus no vàlid ({rtype!r})')

    links = rec.get('links') or []
    if not isinstance(links, list):
        errors.append('links no és una llista')
        links = []
    for url in links:
        if not (isinstance(url, str) and _URL_RE.match(url) and len(url) <= 2048):
            errors.append(f'enllaç no vàlid ({url!r})')

    info = rec.get('info_comp') or {}
    if not isinstance(info, dict):
        errors.append('info_comp no és un objecte')
        info = {}
    for key, value in info.items():
        if key not in RefugeAmenities.AMENITY_FIELDS:
            errors.append(f'info_comp: clau desconeguda ({key!r})')
        elif value not in (0, 1):
            errors.append(f'info_comp.{key}: ha de ser 0 o 1 ({value!r})')

    modified_at = rec.get('modified_at')
    if modified_at in (None, ''):
        modified_at = None
    else:
        try:
            modified_at = date.fromisoformat(str(modified_at))
        except ValueError:
            errors.append(f'modified_at no és una data ISO ({modified_at!r})')

    if errors:
        return None, errors
    return {
        'name': name, 'surname': _clean(rec.get('surname')), 'type': rtype, 'lat': lat, 'long': lng,
        'altitude': altitude, 'places': places, 'description': rec.get('description') or '',
        'region': _clean(rec.get('region')), 'departement': _clean(rec.get('departement')),
        'modified_at': modified_at, 'links': list(links), 'info': {k: bool(v) for k, v in info.items()},
        'condition': float(puntua_refugi(info)[0]),
    }, []


def read_records(path):
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
    except FileNotFoundError:
        raise CommandError(f'No existeix el fitxer: {path}')
    except (OSError, ValueError) as exc:
        raise CommandError(f'No es pot llegir el JSON ({path}): {exc}')
    if not isinstance(data, list):
        raise CommandError('El JSON ha de ser una llista de refugis')
    return data


class Command(BaseCommand):
    help = "Càrrega d'un sol ús del catàleg de refugis (final_data_refuges.json) a PostgreSQL."

    def add_arguments(self, parser):
        parser.add_argument('--json', default=str(DEFAULT_JSON), help='Fitxer JSON (per defecte el del repo)')
        parser.add_argument('--dry-run', action='store_true', help="Valida i compta, però no escriu res")
        parser.add_argument('--database', default=DEFAULT_ALIAS,
                            help=f"Àlies de la BD (per defecte `{DEFAULT_ALIAS}`, el rol propietari)")

    def handle(self, *args, json=None, dry_run=False, database=DEFAULT_ALIAS, **options):
        db = database
        records = read_records(json)

        parsed, problems = [], []
        for index, rec in enumerate(records):
            values, errors = parse_record(rec)
            if errors:
                label = rec.get('name') if isinstance(rec, dict) else None
                problems.append(f'#{index} {label!r}: ' + '; '.join(errors))
            else:
                parsed.append(values)
        if problems:
            raise CommandError(f'{len(problems)} registres invàlids (no s\'ha escrit res):\n' + '\n'.join(problems))

        if Refuge.objects.using(db).exists():
            raise CommandError("La BD ja té refugis: aquesta càrrega és d'un sol ús i no escriu res (no hi ha "
                               "--overwrite).")

        with transaction.atomic(using=db):
            n_refuges, n_amenities, n_links = self._write(db, parsed)
            self._verify(db, n_refuges, n_amenities, n_links)
            if dry_run:
                transaction.set_rollback(True, using=db)

        if not dry_run:
            self._analyze(db)

        dist = Counter(int(v['condition']) for v in parsed)
        self.stdout.write(
            f"{'[dry-run] ' if dry_run else ''}Llegits: {len(records)} · nous: {n_refuges} · "
            f"amenities: {n_amenities} · enllaços: {n_links} · "
            f"condició inicial: " + ', '.join(f'{k} → {dist[k]}' for k in sorted(dist)))

    def _write(self, db, parsed):
        refuges, amenities, links = [], [], []
        for v in parsed:
            refuge = Refuge(
                name=v['name'], surname=v['surname'], type=v['type'], coord=Point(v['long'], v['lat'], srid=4326),
                altitude=v['altitude'], places=v['places'], remarque='', description=v['description'],
                region=v['region'], departement=v['departement'], modified_at=v['modified_at'],
                condition=v['condition'], num_contributed_conditions=0)
            refuges.append(refuge)
            amenities.append(RefugeAmenities(refuge=refuge, **v['info']))
            links.extend(RefugeLink(refuge=refuge, position=i, url=url) for i, url in enumerate(v['links']))
        Refuge.objects.using(db).bulk_create(refuges, batch_size=BATCH_SIZE)
        RefugeAmenities.objects.using(db).bulk_create(amenities, batch_size=BATCH_SIZE)
        RefugeLink.objects.using(db).bulk_create(links, batch_size=BATCH_SIZE)
        return len(refuges), len(amenities), len(links)

    def _verify(self, db, n_refuges, n_amenities, n_links):
        """Comprovacions dins la transacció: si fallen, es desfà tot."""
        actual = (Refuge.objects.using(db).count(), RefugeAmenities.objects.using(db).count(),
                  RefugeLink.objects.using(db).count())
        if actual != (n_refuges, n_amenities, n_links):
            raise CommandError(f'Verificació fallida: esperats {(n_refuges, n_amenities, n_links)}, hi ha {actual}')
        bad = Refuge.objects.using(db).exclude(condition__in=[0, 1, 2, 3]).exclude(condition__isnull=True).count()
        if bad:
            raise CommandError(f'Verificació fallida: {bad} refugis amb condició fora de 0-3')

    def _analyze(self, db):
        """`ANALYZE` de les taules (estadístiques per al planificador). Només té efecte per al propietari."""
        with connections[db].cursor() as cursor:
            for model in (Refuge, RefugeAmenities, RefugeLink, RefugeMedia):
                cursor.execute(f'ANALYZE "{model._meta.db_table}"')       # nom constant (`schema"."taula`)
