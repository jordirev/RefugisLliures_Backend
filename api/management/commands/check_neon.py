"""
Management command per verificar la connexió a Neon (Postgres) i el funcionament de PostGIS.
Només fa servir una taula temporal: no deixa res a la base de dades.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import connections


class Command(BaseCommand):
    help = 'Comprova la connexió a Neon, PostGIS, pg_trgm/unaccent i una consulta ST_DWithin'

    def add_arguments(self, parser):
        parser.add_argument('--alias', default='neon_migrator', choices=['neon', 'neon_migrator'],
                            help="Alias de DATABASES a provar (per defecte el rol migrator, endpoint directe)")

    def handle(self, *args, **options):
        alias = options['alias']
        if alias not in connections.databases:
            raise CommandError(f"L'alias '{alias}' no existeix: falta DATABASE_URL_APP / DATABASE_URL_MIGRATOR a env/.env.*")

        with connections[alias].cursor() as cur:
            cur.execute('SHOW server_version')
            self.stdout.write(f'Postgres: {cur.fetchone()[0]}')

            cur.execute('SELECT postgis_version()')
            self.stdout.write(f'PostGIS: {cur.fetchone()[0]}')

            cur.execute("SELECT similarity(unaccent('Refugi de Cap de Llauset'), 'refugi cap llauset')")
            self.stdout.write(f'pg_trgm + unaccent: similarity = {cur.fetchone()[0]:.2f}')

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
