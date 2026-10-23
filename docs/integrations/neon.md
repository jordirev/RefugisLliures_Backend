# Integració — Neon (Postgres + PostGIS)

> **[FET]** comprovat al codi o a Neon · **[INFERÈNCIA]** deducció · **[NO VERIFICAT]** depèn de config externa.
> Estat: **pas 1 de la migració** (`Arquitectura_Neon_CloudRun_Upstash.md` §6). Neon només està connectat i provat; **Firestore continua sent la BD de domini** i cap DAO usa Neon **[FET]**.

## Projecte
- Projecte `refugislliures`, regió AWS Frankfurt (`aws-eu-central-1`), BD `refugisdb`, **Postgres 17** (Django 5.1 no dona suport oficial a la 18) **[FET]**.
- Branques: `production` (per defecte) i `dev` (creada amb `neon checkout dev --create`, sense caducitat: `neon.ts` n'exclou `dev` del TTL de 7 dies i s'ha tret l'expiració amb `neon branches set-expiration dev`) **[FET]**.
- Només el servei Postgres; Auth/Storage/Functions/AI gateway/Realtime desactivats (Firebase Auth, R2 i Cloud Run els cobreixen) **[FET]**.
- Extensions a `production` i `dev`: `postgis` 3.5, `pg_trgm`, `unaccent`, `pg_stat_statements` **[FET]**.

## Rols (least privilege) [FET]
Creats amb SQL (no amb el CLI, que els faria membres de `neon_superuser`) a `production` i `dev`, cadascuna amb contrasenyes pròpies. El propietari (`refugisdb_owner`) queda només per a administració.
- `app`: `CONNECT`, `USAGE` a `public`, DML (`SELECT/INSERT/UPDATE/DELETE`) i seqüències de les taules creades pel `migrator` (via `ALTER DEFAULT PRIVILEGES` executat com a `migrator`), `SELECT` a `spatial_ref_sys`. Sense DDL ni `CREATE ROLE`.
- `migrator`: `USAGE, CREATE` a `public` (DDL). Només per a migracions, amb endpoint directe. No pot fer `CREATE EXTENSION` (ho fa el propietari).
- Verificat a totes dues branques: `app` no pot fer `CREATE/DROP TABLE` ni `CREATE ROLE`; sí pot fer DML a taules del `migrator` i consultes PostGIS.

## Fitxers i variables
- `neon.ts` (política de branques), `.neon` (branca activa, ignorat per git), `package.json` (només per al CLI de Neon), `.claude/skills/neon*` i `skills-lock.json`.
- Variables a `env/.env.development` (branca `dev`) i `env/.env.production` (branca `production`), llegides amb `decouple` com la resta: `DATABASE_URL_APP` (rol `app`, pooler), `DATABASE_URL_MIGRATOR` (rol `migrator`, directa), `NEON_BRANCH`. A `.env.development` hi queden també `DATABASE_URL` / `DATABASE_URL_UNPOOLED` (propietari) per a administració: `settings.py` no les fa servir. No s'imprimeixen mai. El CLI (`neon deploy` / `neon env pull`) escriu `.env.local`: no cal conservar-lo; mou-ne les variables a `env/` i esborra'l **[FET]**.
- `NEON_USE_POSTGIS_ENGINE` (opcional, `1`): veure «Motor» més avall.

## Django (`refugis_lliures/settings.py`)
- `default` segueix sent SQLite. Si hi ha `.env.local` s'afegeixen els alias `neon` (rol `app`, pooler) i `neon_migrator` (rol `migrator`, directa, per a migracions) **[FET]**.
- `sslmode=require`; amb pooler: `DISABLE_SERVER_SIDE_CURSORS=True`, `CONN_MAX_AGE=60`, `CONN_HEALTH_CHECKS=True` **[FET]**.
- Tots dos alias porten `TEST: {'MIRROR': 'default'}` perquè pytest-django **no** creï `test_refugisdb` a Neon **[FET]**.
- **Motor**: per defecte `django.db.backends.postgresql` (SQL pla, també amb funcions PostGIS). Amb `NEON_USE_POSTGIS_ENGINE=1` usa `django.contrib.gis.db.backends.postgis` (GeoDjango), que requereix GDAL/GEOS: no hi són a Windows local, i vindran a la imatge Docker de Cloud Run **[FET]**.
- Dependència: `psycopg[binary]==3.2.9`.

## Verificació
```bash
python manage.py check_neon                 # rol migrator, endpoint directe
python manage.py check_neon --alias neon    # rol app, endpoint amb pooler
```
Mostra la versió de Postgres i PostGIS, `similarity` amb `unaccent` i una consulta `ST_DWithin`; usa una taula temporal i la neteja **[FET]**.

## Pendent (segons el document d'arquitectura)
Tests de contracte dels DAOs, `models.py` amb invariants, imatge Docker amb GDAL, pas a Launch i compute 0,25–2 CU **[NO VERIFICAT]**.
