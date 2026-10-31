# Integració — Neon (Postgres + PostGIS)

> **[FET]** comprovat al codi o a Neon · **[INFERÈNCIA]** deducció · **[NO VERIFICAT]** depèn de config externa.
> Estat: **migració Firestore → PostgreSQL, chunks 1 (Infraestructura) i 2 (Refugis) fets**. Postgres/PostGIS és la BD `default` de Django amb el rol `app`; els **refugis** (catàleg, serveis, enllaços i mitjans) i el mínim d'`accounts` viuen a PostgreSQL (`apps/refuges`, `apps/accounts`), mentre que la resta del domini es va migrar als chunks següents; **des del chunk 11 (D43) Firestore ja no s'usa enlloc** **[FET]**. El **projecte Neon és el de Postgres 18** (`refugislliures`): `dev` i `production` tenen el *bootstrap*, les 33 migracions i els 1.542 refugis carregats (`dev`: PO; `production`: 30/10/2026, amb `PRODUCTION=true`, vegeu «Migracions») **[FET]**. El projecte antic de PG17 existeix encara a Neon i les seves credencials ja no són a `env/` **[FET]**. Pla: [migration/PLAN.md](../migration/PLAN.md); disseny físic: [design/postgres-schema.md](../design/postgres-schema.md) §1 i §7.

## Projecte
- Projecte `refugislliures`, regió AWS Frankfurt (`aws-eu-central-1`), BD `refugisdb`, **Postgres 18.6**, PostGIS 3.6.4 (projecte `jolly-wind-01114119`; el de PG17, `calm-sun-72437063`, queda abandonat) **[FET]**.
- Branques: `production` (per defecte) i `dev` (creada amb `neon checkout dev --create`, sense caducitat: `neon.ts` n'exclou `dev` del TTL de 7 dies i s'ha tret l'expiració amb `neon branches set-expiration dev`) **[FET]**.
- Només el servei Postgres; Auth/Storage/Functions/AI gateway/Realtime desactivats (Firebase Auth, R2 i Cloud Run els cobreixen) **[FET]**.
- Extensions a `production` i `dev` (projecte PG18): `postgis` 3.6.4, `pg_trgm` 1.6, `unaccent` 1.1, `btree_gist` 1.8, `pg_stat_statements` **[FET]**. Al projecte PG18 s'ha executat el *bootstrap* de §1.3 del disseny a `production` i `dev` (25/10/2026): extensions (`postgis` 3.6.4, `pg_trgm`, `unaccent`, `btree_gist` 1.8, `pg_stat_statements`), `GRANT CREATE ON DATABASE` i `GRANT CREATE ON SCHEMA public` a `migrator`, i `statement_timeout=20s`, `lock_timeout=5s`, `idle_in_transaction_session_timeout=30s` a `app`. La branca `dev` es va crear a partir de `production` **[FET]**.

## Rols (least privilege) [FET]
Creats amb SQL (no amb el CLI, que els faria membres de `neon_superuser`) a `production` i `dev`, cadascuna amb contrasenyes pròpies. El propietari (`refugisdb_owner`) queda només per a administració.
- `app`: `CONNECT`, `USAGE` a `public` i als schemas de domini, DML (`SELECT/INSERT/UPDATE/DELETE`) i seqüències de les taules creades pel `migrator` (via `ALTER DEFAULT PRIVILEGES` executat com a `migrator`), `SELECT` a `spatial_ref_sys`. Sense DDL ni `CREATE ROLE`. **Subjecte a RLS** (la RLS només s'aplica a `app`: el propietari la salta, per això els tests corren com a `app`).
- `migrator`: `USAGE, CREATE` a `public` i `CREATE` sobre la BD (DDL, `CREATE SCHEMA`). Només per a migracions, amb endpoint directe. No pot instal·lar extensions no *trusted*, però **sí les *trusted*** (p. ex. `hstore`) pel `GRANT CREATE ON DATABASE`: les extensions les gestiona el propietari **[FET]**. A PG16+ el propietari no pot fer `ALTER ROLE … NOSUPERUSER`; els rols creats per SQL ja són `NOSUPERUSER/NOBYPASSRLS` i es verifica a `pg_roles` **[FET]**.
- Verificat a totes dues branques: `app` no pot fer `CREATE/DROP TABLE` ni `CREATE ROLE`; sí pot fer DML a taules del `migrator` i consultes PostGIS.
- **`GRANT CREATE ON SCHEMA public TO migrator` (PG15+)**: PG15 treu `CREATE` a `PUBLIC` sobre `public`, i Django ha de crear-hi `django_migrations` i les taules de `auth`/`admin`/`sessions`. L'script local (`scripts/dev/setup_local_postgres.sh`) ja ho fa **[FET]**; al projecte PG18 s'ha verificat (`dev` i `production`) que `migrator` pot crear-hi taules i schemas **[FET]** (vegeu [TECH_DEBT.md](../TECH_DEBT.md) P2).

## Fitxers i variables
- `neon.ts` (política de branques), `.neon` (branca activa, ignorat per git), `package.json` (només per al CLI de Neon), `.claude/skills/neon*` i `skills-lock.json`.
- Variables a `env/.env.development` (branca `dev`) i `env/.env.production` (branca `production`), llegides amb `decouple` com la resta: `DATABASE_URL_APP` (rol `app`, pooler), `DATABASE_URL_MIGRATOR` (rol `migrator`, directa), `NEON_BRANCH`. A `.env.development` hi queden també `DATABASE_URL` / `DATABASE_URL_UNPOOLED` (propietari) per a administració: `settings.py` no les fa servir. No s'imprimeixen mai. El CLI (`neon deploy` / `neon env pull`) escriu `.env.local`: no cal conservar-lo; mou-ne les variables a `env/` i esborra'l **[FET]**.
- `TEST_DATABASE_URL_APP` / `TEST_DATABASE_URL_MIGRATOR` (Postgres local de proves, [guides/testing.md](../guides/testing.md)): **tenen prioritat** sobre `DATABASE_URL_APP` / `DATABASE_URL_MIGRATOR` només dins pytest o amb `USE_TEST_DATABASE=1` (D37); `runserver`, `migrate` i els jobs les ignoren **[FET]**.
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
**Neon `production` des d'un entorn local [FET, 30/10/2026]**: `PRODUCTION=true` fa que `settings.py` llegeixi `env/.env.production` (sense llegir-lo ni imprimir-lo):
```bash
PRODUCTION=true python manage.py check_neon --alias migrator      # ha de mostrar el host ep-…(production)
PRODUCTION=true python manage.py migrate --database=migrator
PYTHONUTF8=1 PRODUCTION=true python manage.py load_refuges --dry-run   # i, si quadra, sense --dry-run (una sola vegada)
```
`FirebaseAuthConfig.ready()` llegeix `FIREBASE_SERVICE_ACCOUNT_KEY` via `settings` (`decouple`), així que amb el JSON a `env/.env.production` totes les comandes, `migrate` inclòs, hi funcionen; sense la clau fallen abans de connectar ([firebase-credentials.md](../guides/firebase-credentials.md)).

El rol `app` no té permisos de DDL: un `migrate` sense `--database=migrator` fallaria (i, si algú li donés DDL, deixaria objectes que no són del propietari). `apps/core` (`core.0001`, `core.0002`) crea els schemas (`core`, `refuges`, `users`, `activity`, `proposals`, `moderation`, `audit`), les funcions de `core` (`uid()`, `is_admin()`, `is_system()`, `immutable_unaccent`, `norm_name`, `round_half_even`; disseny §2.0) i els grants base de `app` (§7.1), amb `reverse_sql`. Requereix el *bootstrap* previ del propietari (§1.3).

## RLS i context de la petició [FET]
- `apps/core/rls.py`: `rls_context(uid, is_admin, system, using)` i `system_context()` (reexportats a `apps.core`) i helpers de polítiques (`expand_macros`, `create_policy_sql`, `drop_policy_sql`) per a les migracions dels chunks següents.
- El context (`app.uid`, `app.is_admin`, `app.is_system`) es fixa **sempre amb `set_config(..., true)`**, és a dir, **local a la transacció**: mor al `COMMIT`/`ROLLBACK` i no es filtra a altres clients quan el pooler reutilitza la connexió. Per a peticions HTTP el fixa el hook de `apps/core/rls_hook.py` ([flux 00](../flows/00-auth-request-pipeline.md)); fora d'HTTP (comandes, jobs, tests) s'usa `rls_context`.

## Apps i migracions actuals [FET]
`core.0001` (schemas, funcions, grants) i `core.0002` (SELECT de `app` a `django_migrations`) → `accounts.0001` (`users.languages`, `users.users`, `users.user_public_profiles`, `users.user_avatars`) → `refuges.0001` (`refuges.refuge_types`, `refuges.refuges`, `refuge_amenities`, `refuge_links`, `refuge_media`; sense vista `refuge_map`; índexs GIN trigram, RLS, grants) → `accounts.0002` (chunk 3: `users.user_favourite_refuges` i `users.user_visited_refuges`, PK composta, FK reals `ON DELETE CASCADE` per `RunSQL`, RLS i grants `SELECT, INSERT, DELETE` a `app`). Les taules les crea `migrator`; `app` només fa DML subjecte a RLS.

## Càrrega inicial del catàleg [FET]
`python manage.py load_refuges [--dry-run]` (rol `migrator` per defecte) carrega `apps/refuges/data/final_data_refuges.json` (1.542 refugis) **una sola vegada**: si ja hi ha refugis acaba amb `CommandError` sense escriure res. Ja s'ha executat una vegada a Neon `dev` (PO) i a `production` (30/10/2026: 1.542 refugis, 1.542 *amenities*, 2.075 enllaços; condició inicial 0→605, 1→565, 2→332, 3→40); **no s'ha de repetir** **[FET]**. A Windows cal `PYTHONUTF8=1`: el resum imprimeix `→` i la consola `cp1252` fa saltar `UnicodeEncodeError` (després de validar, abans d'escriure res en `--dry-run`).

## Identificadors
Les PK substitutes són UUID v7 (RFC 9562) generats per la BD amb `DEFAULT uuidv7()` de Postgres 18 (`db_default` a Django 5.2; disseny §1.4; l'helper `api/utils/ids.py` s'ha eliminat, chunk 2) **[FET]**. `Refuge` n'és un exemple; `RefugeLink` té PK `url`, `RefugeAmenities` reutilitza la PK del refugi, `RefugeMedia` i `UserAvatar` tenen la clau R2 i `UserAccount` l'UID de Firebase; les taules d'unió sense FK entrant tenen PK composta (disseny §1.4) **[FET]**. L'API exposa els UUID com a *string* opac; **no coincideixen** amb els IDs de Firestore.

## Verificació
```bash
python manage.py check_neon --alias migrator   # rol migrator, endpoint directe (per defecte)
python manage.py check_neon --alias default    # rol app, endpoint amb pooler
```
Mostra la versió de Postgres i PostGIS, `similarity` amb `unaccent` i una consulta `ST_DWithin`; usa una taula temporal i la neteja **[FET]**. Els àlies vàlids són `default` i `migrator` (abans `neon`/`neon_migrator`). **Es connecta sempre a Neon** amb `DATABASE_URL_APP` / `DATABASE_URL_MIGRATOR` (ignora `TEST_DATABASE_URL_*`, que apunten al Docker local i, dins pytest o amb `USE_TEST_DATABASE=1`, tenen prioritat a `DATABASES`), mostra el host i la versió, i **avisa si el servidor és < Postgres 18** **[FET]**. A més comprova el *bootstrap* del propietari (§1.3 del disseny) i **avisa** (`Bootstrap incomplet: ...`) si falten extensions (`postgis`, `pg_trgm`, `unaccent`, `btree_gist`), `GRANT CREATE ON DATABASE` o `GRANT CREATE ON SCHEMA public`: **executa'l amb `--alias migrator` abans del primer `migrate` a Neon** **[FET]**.

## Pendent
- **Validat contra Neon `dev` (30/10/2026) [FET]**: `check_neon` (pooler i directe), les 33 migracions, 1.542 refugis i els e2e `scripts/e2e/e2e_chunk1..10.sh` amb servidor local + Firebase Auth Emulator contra la branca `dev` (pooler PgBouncer, PG18; vegeu [guides/testing.md](../guides/testing.md)). `production` té les mateixes migracions i dades; els e2e no s'hi executen mai. El PO ha comprovat (31/10/2026) que el rol `app` té a les dues branques els límits del *bootstrap* (`statement_timeout=20s`, `lock_timeout=5s`, `idle_in_transaction_session_timeout=30s`), com a local **[FET]**.
- Credencials: el PO ja les va rotar (després que s'enviessin pel xat) i el 30/10/2026 va decidir **no fer-ne una segona rotació**: cap connector pot rotar-les sense que les contrasenyes noves passin per la conversa. En desplegar, `DATABASE_URL_APP` / `DATABASE_URL_MIGRATOR` s'han de posar als secrets del nou entorn (Cloud Run / Oracle) i a GitHub Actions si es manté el job de visites (TECH_DEBT U3) **[NO VERIFICAT]**.
- Imatge/entorn de desplegament amb GDAL/GEOS: decisió del PO (30/10/2026) de desplegar a **Cloud Run o Oracle** (Dockerfile amb GDAL), no a Render; pas a Launch i compute 0,25–2 CU **[NO VERIFICAT]**.
