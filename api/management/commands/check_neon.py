"""
Management command per verificar la connexió a Neon (Postgres) i el funcionament de PostGIS.
Només fa servir una taula temporal: no deixa res a la base de dades.

Es connecta sempre a les URL de Neon (`DATABASE_URL_APP` / `DATABASE_URL_MIGRATOR`), encara que hi hagi
`TEST_DATABASE_URL_*` definides: aquestes tenen prioritat a `DATABASES` (apunten al Postgres local de proves) i,
si la comanda usés `connections[alias]`, comprovaria el Docker local en lloc de Neon.
"""
import psycopg
from django.core.management.base import BaseCommand, CommandError

from refugis_lliures import settings as project_settings

NEON_URL_VARS = {'default': 'DATABASE_URL_APP', 'migrator': 'DATABASE_URL_MIGRATOR'}


class Command(BaseCommand):
    help = 'Comprova la connexió a Neon, PostGIS, pg_trgm/unaccent i una consulta ST_DWithin'

    def add_arguments(self, parser):
        parser.add_argument('--alias', default='migrator', choices=['default', 'migrator'],
                            help="Rol a provar: default = app (pooler), migrator = migrator (endpoint directe; per defecte)")

    def handle(self, *args, **options):
        alias = options['alias']
        url_var = NEON_URL_VARS[alias]
        db = project_settings._postgres_database((url_var,), pooled=alias == 'default', atomic_requests=False)
        if not db:
            raise CommandError(f'Falta {url_var} a env/.env.*')

        params = {k: v for k, v in db['OPTIONS'].items() if k != 'prepare_threshold'}
        try:
            conn = psycopg.connect(dbname=db['NAME'], user=db['USER'], password=db['PASSWORD'], host=db['HOST'],
                                   port=db['PORT'], prepare_threshold=None, autocommit=True, **params)
        except psycopg.Error as exc:
            raise CommandError(f"No s'ha pogut connectar a {db['HOST']} ({url_var}): {type(exc).__name__}") from None

        with conn, conn.cursor() as cur:
            self.stdout.write(f"Servidor: {db['HOST']} ({url_var})")
            cur.execute('SHOW server_version')
            self.stdout.write(f'Postgres: {cur.fetchone()[0]}')

            cur.execute('SELECT postgis_version()')
            self.stdout.write(f'PostGIS: {cur.fetchone()[0]}')

            cur.execute("SELECT similarity(unaccent('Refugi de Cap de Llauset'), 'refugi cap llauset')")
            self.stdout.write(f'pg_trgm + unaccent: similarity = {cur.fetchone()[0]:.2f}')

            self._check_bootstrap(cur)

            cur.execute(
                'CREATE TEMP TABLE _check_refuges '
                '(id serial PRIMARY KEY, name text, coord geography(Point, 4326))'
            )
            cur.execute('CREATE INDEX _check_refuges_gist ON _check_refuges USING GIST (coord)')
            cur.execute(
                "INSERT INTO _check_refuges (name, coord) VALUES "
                "('Refugi de prova A', ST_SetSRID(ST_MakePoint(0.9440, 42.5500), 4326)), "
                "('Refugi de prova B (lluny)', ST_SetSRID(ST_MakePoint(2.0, 41.5), 4326))"
            )
            cur.execute(
                "SELECT name, round(ST_Distance(coord, ST_SetSRID(ST_MakePoint(0.9445, 42.5502), 4326)::geography)::numeric) "
                "FROM _check_refuges "
                "WHERE ST_DWithin(coord, ST_SetSRID(ST_MakePoint(0.9445, 42.5502), 4326)::geography, 200)"
            )
            rows = cur.fetchall()
            self.stdout.write(f'ST_DWithin(200 m): {rows}')
            cur.execute('DROP TABLE _check_refuges')

        if len(rows) != 1 or rows[0][0] != 'Refugi de prova A':
            raise CommandError('ST_DWithin no ha retornat el resultat esperat')
        self.stdout.write(self.style.SUCCESS(f"Neon OK (alias '{alias}')"))

    def _check_bootstrap(self, cur):
        """Avisa si falta algun requisit del bootstrap del propietari (§1.3 del disseny)."""
        cur.execute("SELECT extname FROM pg_extension WHERE extname IN ('postgis', 'pg_trgm', 'unaccent', 'btree_gist')")
        missing = {'postgis', 'pg_trgm', 'unaccent', 'btree_gist'} - {row[0] for row in cur.fetchall()}
        # Els grants són del rol `migrator` (qui aplica les migracions), sigui quin sigui l'àlies connectat:
        # amb `default` (rol `app`) mirar `current_user` donava falsos avisos.
        cur.execute("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'migrator')")
        if cur.fetchone()[0]:
            cur.execute("SELECT has_database_privilege('migrator', current_database(), 'CREATE'), "
                        "has_schema_privilege('migrator', 'public', 'CREATE')")
            db_create, public_create = cur.fetchone()
        else:
            db_create = public_create = False
        cur.execute("SHOW server_version_num")
        pg18 = int(cur.fetchone()[0]) >= 180000
        for ok, msg in ((not missing, f'extensions que falten: {sorted(missing)}'),
                        (db_create, 'falta GRANT CREATE ON DATABASE (core.0001 no podra crear els schemas)'),
                        (public_create, 'falta GRANT CREATE ON SCHEMA public (PG15+: Django no podra crear django_migrations)'),
                        (pg18, 'cal Postgres 18 (DEFAULT uuidv7(), postgres-schema.md §1.4)')):
            if not ok:
                self.stdout.write(self.style.WARNING(f'Bootstrap incomplet: {msg}'))
