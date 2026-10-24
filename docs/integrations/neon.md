# Integració — Neon (Postgres + PostGIS)

> **[FET]** comprovat al codi o a Neon · **[INFERÈNCIA]** deducció · **[NO VERIFICAT]** depèn de config externa.
> Estat: **migració Firestore → PostgreSQL, chunk 1 (Infraestructura) fet**. Postgres/PostGIS ja és la BD `default` de Django amb el rol `app`, però **Firestore continua sent la BD de domini** fins als chunks següents: cap DAO llegeix ni escriu a Postgres encara **[FET]**. Pla: [migration/PLAN.md](../migration/PLAN.md); disseny físic: [design/postgres-schema.md](../design/postgres-schema.md) §1 i §7.

## Projecte
- Projecte `refugislliures`, regió AWS Frankfurt (`aws-eu-central-1`), BD `refugisdb`, **Postgres 17** (Django 5.1 no dona suport oficial a la 18) **[FET]**.
- Branques: `production` (per defecte) i `dev` (creada amb `neon checkout dev --create`, sense caducitat: `neon.ts` n'exclou `dev` del TTL de 7 dies i s'ha tret l'expiració amb `neon branches set-expiration dev`) **[FET]**.
- Només el servei Postgres; Auth/Storage/Functions/AI gateway/Realtime desactivats (Firebase Auth, R2 i Cloud Run els cobreixen) **[FET]**.
- Extensions a `production` i `dev`: `postgis` 3.5, `pg_trgm`, `unaccent`, `pg_stat_statements` **[FET]**. El *bootstrap* de §1.3 del disseny (`btree_gist`, `GRANT CREATE ON DATABASE`, timeouts dels rols) s'ha executat a `dev` pel PO amb el rol propietari (24/10/2026; [migration/PROGRESS.md](../migration/PROGRESS.md)); a `production` encara no **[NO VERIFICAT]**.

## Rols (least privilege) [FET]
Creats amb SQL (no amb el CLI, que els faria membres de `neon_superuser`) a `production` i `dev`, cadascuna amb contrasenyes pròpies. El propietari (`refugisdb_owner`) queda només per a administració.
- `app`: `CONNECT`, `USAGE` a `public` i als schemas de domini, DML (`SELECT/INSERT/UPDATE/DELETE`) i seqüències de les taules creades pel `migrator` (via `ALTER DEFAULT PRIVILEGES` executat com a `migrator`), `SELECT` a `spatial_ref_sys`. Sense DDL ni `CREATE ROLE`. **Subjecte a RLS** (la RLS només s'aplica a `app`: el propietari la salta, per això els tests corren com a `app`).
- `migrator`: `USAGE, CREATE` a `public` (DDL). Només per a migracions, amb endpoint directe. No pot fer `CREATE EXTENSION` (ho fa el propietari).
- Verificat a totes dues branques: `app` no pot fer `CREATE/DROP TABLE` ni `CREATE ROLE`; sí pot fer DML a taules del `migrator` i consultes PostGIS.
- **`GRANT CREATE ON SCHEMA public TO migrator` (PG15+)**: PG15 treu `CREATE` a `PUBLIC` sobre `public`, i Django ha de crear-hi `django_migrations` i les taules de `auth`/`admin`/`sessions`. L'script local (`scripts/dev/setup_local_postgres.sh`) ja ho fa **[FET]**; a Neon `dev` **encara no s'ha verificat** que `migrator` pugui crear-hi taules abans del primer `migrate` **[NO VERIFICAT]** (vegeu [TECH_DEBT.md](../TECH_DEBT.md) P2).

## Fitxers i variables
- `neon.ts` (política de branques), `.neon` (branca activa, ignorat per git), `package.json` (només per al CLI de Neon), `.claude/skills/neon*` i `skills-lock.json`.
- Variables a `env/.env.development` (branca `dev`) i `env/.env.production` (branca `production`), llegides amb `decouple` com la resta: `DATABASE_URL_APP` (rol `app`, pooler), `DATABASE_URL_MIGRATOR` (rol `migrator`, directa), `NEON_BRANCH`. A `.env.development` hi queden també `DATABASE_URL` / `DATABASE_URL_UNPOOLED` (propietari) per a administració: `settings.py` no les fa servir. No s'imprimeixen mai. El CLI (`neon deploy` / `neon env pull`) escriu `.env.local`: no cal conservar-lo; mou-ne les variables a `env/` i esborra'l **[FET]**.
- `TEST_DATABASE_URL_APP` / `TEST_DATABASE_URL_MIGRATOR` (Postgres local de proves, [guides/testing.md](../guides/testing.md)): **tenen prioritat** sobre `DATABASE_URL_APP` / `DATABASE_URL_MIGRATOR` **[FET]**.
- `NEON_USE_POSTGIS_ENGINE` **ja no existeix** (el motor PostGIS és l'únic) **[FET]**.

## Django (`refugis_lliures/settings.py`)
- **`DATABASES['default']`** = PostGIS (`django.contrib.gis.db.backends.postgis`) amb el rol `app` (`TEST_DATABASE_URL_APP` o `DATABASE_URL_APP`), `ATOMIC_REQUESTS=True` (una transacció per petició: el context de RLS viu a la transacció, [flow 00](../flows/00-auth-request-pipeline.md)), `DISABLE_SERVER_SIDE_CURSORS=True`, `CONN_MAX_AGE=60` i `CONN_HEALTH_CHECKS=True` (suposa el pooler) **[FET]**.
- **`DATABASES['migrator']`** = mateix motor amb el rol `migrator` (`TEST_DATABASE_URL_MIGRATOR` o `DATABASE_URL_MIGRATOR`), endpoint directe, sense `ATOMIC_REQUESTS`, `CONN_MAX_AGE=0` **[FET]**. Només es defineix si la variable és present.
- Els àlies `neon` i `neon_migrator` i el `TEST: {'MIRROR': 'default'}` s'han **eliminat** **[FET]**: ara els tests no creen cap `test_*` sinó que `django_db_setup` migra amb `migrator` sobre la BD de proves ([guides/testing.md](../guides/testing.md)).
- **`sslmode`**: es respecta el de la URL; si no n'hi ha i el host no és local (`localhost`, `127.0.0.1`, `::1`, `host.docker.internal`, `*.localhost`) s'afegeix `sslmode=require` **[FET]**.
- **`connect_timeout=10`** a `OPTIONS`: libpq no té cap timeout de connexió per defecte; sense límit, un host inabastable (o un *cold start* de Neon fallit) deixaria el worker penjat, també el health check **[FET]**.
- **`prepare_threshold=None`** (sense sentències preparades) i **cap `options`** a l'arrencada: el pooler de Neon (PgBouncer, mode transacció) no admet ni les preparades ni el paràmetre d'arrencada `options` (§1.5 del disseny) **[FET]**. Per això el context RLS es fixa amb `set_config(..., true)` dins la transacció, no amb `options`.
- **Sense cap URL definida**, `default` continua sent SQLite (`db.sqlite3`): només perquè els tests amb mocks (que no toquen la BD) puguin carregar la configuració. Qualsevol petició real sense URL fallaria en el `set_config` del hook de RLS **[FET sobre la configuració; INFERÈNCIA sobre la fallada del hook]** (vegeu [TECH_DEBT.md](../TECH_DEBT.md) P3).
- `INSTALLED_APPS` afegeix `django.contrib.gis`, `django.contrib.postgres` i `apps.core` **[FET]**. **`django.contrib.gis` sempre és actiu: el runtime necessita GDAL/GEOS** (a Windows local no hi són; s'executa en un contenidor Linux, [guides/local-setup.md](../guides/local-setup.md)). Instal·lar-los a Render/Cloud Run és **pendent de desplegament** ([TECH_DEBT.md](../TECH_DEBT.md) P1).
- Dependència: `psycopg[binary]==3.2.9`.

## Migracions (sempre amb `--database=migrator`) [FET]
```bash
python manage.py migrate --database=migrator
```
El rol `app` no té permisos de DDL: un `migrate` sense `--database=migrator` fallaria (i, si algú li donés DDL, deixaria objectes que no són del propietari). `domain/core` (`core.0001`) crea els schemas (`core`, `refuges`, `users`, `activity`, `proposals`, `moderation`, `audit`), les funcions de `core` (`uid()`, `is_admin()`, `is_system()`, `immutable_unaccent`, `norm_name`, `round_half_even`; disseny §2.0) i els grants base de `app` (§7.1), amb `reverse_sql`. Requereix el *bootstrap* previ del propietari (§1.3).

## RLS i context de la petició [FET]
- `domain/core/rls.py`: `rls_context(uid, is_admin, system, using)` i `system_context()` (reexportats a `apps.core`) i helpers de polítiques (`expand_macros`, `create_policy_sql`, `drop_policy_sql`) per a les migracions dels chunks següents.
- El context (`app.uid`, `app.is_admin`, `app.is_system`) es fixa **sempre amb `set_config(..., true)`**, és a dir, **local a la transacció**: mor al `COMMIT`/`ROLLBACK` i no es filtra a altres clients quan el pooler reutilitza la connexió. Per a peticions HTTP el fixa el hook de `api/rls_hook.py` ([flux 00](../flows/00-auth-request-pipeline.md)); fora d'HTTP (comandes, jobs, tests) s'usa `rls_context`.

## Identificadors
`api/utils/ids.py: uuid7()` genera els UUID v7 (RFC 9562) de les claus primàries substitutes (disseny §1.4): monòton dins el procés i thread-safe **[FET]**. Encara no hi ha cap model que l'usi.

## Verificació
```bash
python manage.py check_neon --alias migrator   # rol migrator, endpoint directe (per defecte)
python manage.py check_neon --alias default    # rol app, endpoint amb pooler
```
Mostra la versió de Postgres i PostGIS, `similarity` amb `unaccent` i una consulta `ST_DWithin`; usa una taula temporal i la neteja **[FET]**. Els àlies vàlids són `default` i `migrator` (abans `neon`/`neon_migrator`). A més comprova el *bootstrap* del propietari (§1.3 del disseny) i **avisa** (`Bootstrap incomplet: ...`) si falten extensions (`postgis`, `pg_trgm`, `unaccent`, `btree_gist`), `GRANT CREATE ON DATABASE` o `GRANT CREATE ON SCHEMA public`: **executa'l amb `--alias migrator` abans del primer `migrate` a Neon** **[FET]**.

## Pendent
- Executar `check_neon --alias migrator` (avisa del *bootstrap* incomplet), verificar el `GRANT CREATE ON SCHEMA public` a Neon `dev` i executar el primer `migrate --database=migrator` **[NO VERIFICAT]**.
- Validar contra Neon (pooler PgBouncer, PG17) el que només s'ha provat en local (Postgres 16/17 sense pooler): el PO ha d'executar `scripts/e2e/` des d'una màquina amb accés TCP ([migration/DECISIONS_AUTONOMES.md](../migration/DECISIONS_AUTONOMES.md) D3) **[NO VERIFICAT]**.
- Imatge/entorn de desplegament amb GDAL/GEOS, pas a Launch i compute 0,25–2 CU **[NO VERIFICAT]**.
