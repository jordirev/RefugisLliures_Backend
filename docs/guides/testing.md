# Guia — Executar i escriure tests

> **[FET]** comprovat al codi · **[INFERÈNCIA]** deducció · **[NO VERIFICAT]** depèn de config externa.
> Convencions de tests (mocks, estructura, fixtures mortes): [ARCHITECTURE §10](../ARCHITECTURE.md). Gotchas: [GOTCHAS #30-31](../GOTCHAS.md).

## Requisits
`pip install -r requirements.txt` ja inclou `pytest`, `pytest-django`, `pytest-cov`, `pytest-mock` i `coverage`. No cal Firebase, Redis (ja no n'hi ha) ni R2: tot es mocka. Des del chunk 1 de la migració calen a més **GDAL/GEOS** al sistema (`django.contrib.gis` és sempre actiu) i, per als tests de BD, un **PostgreSQL + PostGIS local** (vegeu més avall); sense Postgres els tests amb BD se salten i els que no toquen la BD funcionen amb el SQLite de reserva **[FET]**.

## Executar
```bash
pytest                                   # tots (testpaths = apps)
pytest apps/refuges -q                   # una app migrada (tests a apps/<feature>/tests/)
pytest apps/renovations -q                # una app migrada (esquema, constraints, RLS, vistes, consultes)
pytest apps/accounts/tests/test_views_users.py      # un fitxer
pytest apps/accounts/tests/test_views_users.py::test_y   # un test
pytest -k "create"                       # per nom
pytest -m views                          # per marker
tox                                      # com a CI: pytest + coverage.xml
```
Markers declarats a `pytest.ini` (amb `--strict-markers`, un marker no declarat fa fallar): vegeu el fitxer; els que s'usen de debò són `views`, `slow`, `db_infra`, `rls`, `real_audit_log` i `real_permissions`. Els markers de la capa legacy (`controller(s)`, `daos`, `mappers`) i `real_legacy_counts` ja no tenen cap test (chunk 11).

Depuració: `pytest -x` (atura al primer error), `--maxfail=3`, `--tb=long`, `-s` (mostra `print`), `--pdb`.

## Coverage
```bash
pytest --cov=apps --cov-report=term-missing      # línies no cobertes
pytest --cov=apps --cov-report=html              # informe a htmlcov/index.html
```
`.coveragerc` i Sonar **exclouen `services/` i `utils/`**. CI puja `coverage.xml` a Codecov i SonarCloud ([render-deploy-ci](../integrations/render-deploy-ci.md)).

`run_tests.py` (menú interactiu antic) s'ha eliminat **[FET]**.

## Per què Firebase no s'inicialitza als tests
`FirebaseAuthConfig.ready()` (`apps/auth/apps.py`) crida `initialize_firebase()` en carregar Django, abans que comencin els tests. Per evitar que busqui credencials (i falli a CI):
1. `conftest.py` (arrel) fixa `TESTING=true` i `R2_*` falses **abans de qualsevol import**, i ho reforça a `pytest_configure`.
2. `apps/auth/firebase_config.py` no inicialitza res si `'pytest' in sys.modules` o `TESTING=='true'`.

Per a un test d'integració amb Firebase real caldria `TESTING=false` i credencials (no n'hi ha cap avui).

## Tests contra PostgreSQL local (migració, chunk 1) [FET]
- Bootstrap idempotent: `scripts/dev/setup_local_postgres.sh` (arrenca el clúster apt si cal; crea els rols `migrator` i `app` amb els atributs de `docs/design/postgres-schema.md` §1.3, la BD `refugisdb_test` i les extensions `postgis`, `pg_trgm`, `unaccent`, `btree_gist`). Imprimeix les dues URLs locals (no secretes); a CI es parametritza amb `PGHOST`, `PGPORT`, `PG_SUPERUSER`, `PGPASSWORD`, `PG_START_CLUSTER=0`.
- Exporta-les: `eval "$(scripts/dev/setup_local_postgres.sh | grep ^export)"` → `TEST_DATABASE_URL_MIGRATOR` / `TEST_DATABASE_URL_APP`.
- Marker `db_infra`: necessita aquestes variables i **se salta** (amb motiu) si falten; marker `rls`: tests del context RLS i del hook (executen el `set_config` de debò). Les migracions les aplica `migrator` i els tests corren com a `app` (la RLS només s'aplica a `app`).
- **`django_db_setup`** (`conftest.py` de l'arrel, compartit per tots els `apps/*/tests`) sobreescriu el de pytest-django: amb `migrator` definit **no crea cap BD `test_*`**; executa `migrate --database=migrator` sobre la BD de proves (idempotent) i dona al rol `app` DML sobre les taules de Django de `public` (només a la BD de proves: alguns tests creen un `auth.User` per a `force_authenticate`; no formen part dels grants de producció). Sense `migrator` (sense Postgres) es manté el comportament per defecte sobre SQLite.
- **Dins pytest, `TEST_DATABASE_URL_APP` / `TEST_DATABASE_URL_MIGRATOR` tenen prioritat** sobre `DATABASE_URL_*` a `settings.py` (pytest ≥ 8.2 defineix `PYTEST_VERSION`): els tests mai van a Neon encara que `env/` en tingui les URL. Fora de pytest s'ignoren llevat de `USE_TEST_DATABASE=1` (D37; test: `apps/core/tests/test_settings_databases.py`).
- **Fixture `_rls_hook_sense_bd`** (`autouse`): als tests que **no** porten cap dels markers `rls`, `django_db`, `db_infra` (vistes sense BD) fa `patch('api.rls_hook.apply_context')`, perquè el hook de RLS no intenti executar `set_config` sense connexió a Postgres. Els tests de BD l'executen de debò. Si un test de vista sense BD vol comprovar el hook, ha de dur el marker `rls`.
- Les fixtures `app_db` / `migrator_db` (`conftest.py` de l'arrel) i els helpers `fetch_all` / `fetch_one` (`apps/core/testing.py`) donen connexions en autocommit fora de la transacció de pytest-django, necessàries per provar contextos locals a la transacció.
- **Guarda de host**: `django_db_setup` fa `pytest.exit` (codi 2) si el `HOST` de `TEST_DATABASE_URL_MIGRATOR` no és local (`localhost`, `127.0.0.1`, `::1`, `host.docker.internal`, `*.localhost`): els tests mai poden córrer contra Neon, encara que s'hi apunti per error **[FET]**.
- Tests de seguretat a `apps/core/tests/` i `apps/auth/tests/`: rol `app` (sense atributs privilegiats ni propietat d'objectes, no pot crear objectes als schemas ni escalar privilegis ni substituir `core.*`; `core.*` no executables per `PUBLIC`, `SECURITY DEFINER` amb `search_path` fixat), hook de RLS (context local a la transacció, avís fora de transacció, `is_system` reiniciat, contextos interns que no escalen l'extern, `uid` no-string = anònim, `role` no exacte no dona admin), respostes d'auth (el 401 no filtra detalls ni l'UID als logs) i guarda de l'emulador de Firebase (plataformes, hosts locals, variants booleanes) **[FET]**.
- **Tests de les apps migrades** a `apps/<feature>/tests/` (chunk 2: `apps/refuges/tests/`): esquema físic (`test_schema`), constraints i models, RLS amb el rol `app` (anònim, propi, aliè, admin, sistema), cerca i índexs (`EXPLAIN`), contracte HTTP contra Postgres real, recomptes de consultes (`django_assert_num_queries` equivalent: `QueryCounter`) i la comanda `load_refuges` (que fa `COMMIT` de debò amb `migrator`; la fixture `wipe_catalog` neteja). `apps/refuges/tests/helpers.py` crea dades amb `system_context()`. Les fixtures compartides (bloqueig de Firebase Admin real, mocks d'audit i de permisos, `django_db_setup`) són al `conftest.py` de l'arrel, de manera que els tests nous no depenen d'`api/tests`.
- Tests d'infraestructura a `apps/core/tests/`, `apps/auth/tests/` i `apps/health/tests/` (settings de BD, hook de RLS, health, arquitectura RLS, emulador, middleware del health) i `apps/core/tests/` (context RLS, helpers de polítiques, funcions SQL de `core`).
- **Rol de proves `test_fixtures`** (només a les BD locals/CI que crea `setup_local_postgres.sh`, mai a Neon): `NOLOGIN BYPASSRLS`, escriptura sobre les taules dels schemas de domini. `app` el pot activar (`GRANT test_fixtures TO app WITH INHERIT FALSE, SET TRUE`, sense heretar-ne res) i `apps/refuges/tests/helpers.py: as_owner()` el fa servir per crear el catàleg de refugis, que `app` no pot escriure fins al chunk 8. La RLS i els grants d'`app` que proven els tests no canvien i `app` continua sense poder assumir `migrator` **[FET]**.
- Execució a CI: servei `postgis/postgis:18-3.6` (Python 3.14) + `setup_local_postgres.sh` amb `PGHOST=localhost PG_START_CLUSTER=0`; `tox.ini` fa `passenv` de les `TEST_DATABASE_URL_*` ([render-deploy-ci.md](../integrations/render-deploy-ci.md)).

### Windows: tests en un contenidor Linux [FET]
No hi ha GDAL natiu a Windows, així que els tests s'executen en un contenidor (`python:3.14-slim-bookworm` + `gdal-bin libgdal-dev libgeos-dev libproj-dev`, `pip install -r requirements.txt`) contra un contenidor `postgis/postgis:18-3.6` (Postgres 18.6, PostGIS 3.6.4) **[FET]**. Si una migració `0001` es reescriu (com al chunk 2), cal tornar a crear la BD de proves (`DROP DATABASE refugisdb_test` + l'script): `migrate` és idempotent i no reaplica una migració amb el mateix nom. El Dockerfile, l'arrencada del Postgres i el *bootstrap* són a [local-setup.md § PostgreSQL](local-setup.md). Les proves, amb el repo muntat a `/app`:
```powershell
docker run --rm -v "${PWD}:/app" -w /app --add-host=host.docker.internal:host-gateway `
  -e PGHOST=host.docker.internal -e PG_START_CLUSTER=0 -e PGPASSWORD=<contrasenya-local> rl-backend `
  bash -c 'eval "$(scripts/dev/setup_local_postgres.sh | grep ^export)" && pytest -q'
```
Alternativa: `TEST_DATABASE_URL_APP` i `TEST_DATABASE_URL_MIGRATOR` a `env/.env.development` amb host `host.docker.internal` (no cal l'`eval`; no imprimeixis els valors). El contenidor, CI i l'entorn local (`.venv` amb `py -3.14`) corren Python 3.14 **[FET]**.

**Diverses suites en paral·lel (un worktree per chunk) [FET]**: `scripts/dev/run_tests_docker.sh <nom_bd> [args de pytest]` (Git Bash) munta el directori actual a `/app`, pren les `TEST_DATABASE_URL_*` de `env/.env.development` del checkout principal dins el contenidor (sense imprimir-les), comparteix la xarxa de `rl-postgres` i fixa `TEST_DATABASE_NAME=<nom_bd>`, que a `settings.py` substitueix només el nom de la BD de les URL `TEST_*` (mai `DATABASE_URL_*`). Cada worktree fa servir una BD pròpia (`refugisdb_test_<chunk>`), creada amb les extensions i els grants de `setup_local_postgres.sh` (`TEST_DB_NAME=<nom_bd>`); així dues suites no es trepitgen les dades ni les migracions.

## E2E local (servidor real + Firebase Emulators) [FET]
Script: `scripts/e2e/e2e_chunk1.sh` (health amb `database`, 401/403/404/200 amb tokens d'usuari normal i d'admin; surt amb 1 si algun cas falla). Així s'ha validat el chunk 1 el 24/10/2026 contra un Postgres local migrat (12/12).
1. Emuladors: carpeta amb `firebase.json` (`{"emulators":{"auth":{"port":9099,"host":"0.0.0.0"},"ui":{"enabled":false}}}`) i `npx -y firebase-tools emulators:start --only auth --project demo-refugis-lliures` (cal Node i Java).
2. BD: `TEST_DB_NAME=refugisdb_e2e scripts/dev/setup_local_postgres.sh` (o la BD a provar, p. ex. Neon `dev`) i `python manage.py migrate --database=migrator`.
3. Servidor amb, com a mínim: `DATABASE_URL_APP`/`DATABASE_URL_MIGRATOR` de la BD a provar, `TEST_DATABASE_URL_*` buides o sense `USE_TEST_DATABASE` (si no, tenen prioritat), `FIREBASE_AUTH_EMULATOR_HOST`, `GCLOUD_PROJECT=demo-refugis-lliures`, `R2_*` ficticis amb un endpoint inabastable (`users/{uid}` i `admin/media-reports` creen el client R2 encara que no el facin servir).
4. `bash scripts/e2e/e2e_chunk1.sh` (`BASE_URL`, `AUTH_EMULATOR` configurables).
5. Chunk 2 (refugis): `python manage.py load_refuges` (un sol cop) i `bash scripts/e2e/e2e_chunk2.sh`: llista/mapa, cerca (accents, `surname`, `%`), filtres i 400, detall (anònim/usuari/admin, 404), catàleg no escrivible (405), mitjans (401/403/404). Opcionals: `E2E_SQL_CMD` (ordre `psql` com a propietari que llegeix per stdin) per inserir un mitjà de prova i provar l'esborrat amb R2 inabastable (500 `{error, error_id}`, la fila es conserva), i `E2E_LOG_CMD` (p. ex. `docker logs <contenidor>`) per comprovar que l'`error_id` surt al log. Validat el 24/10/2026: 31/31.
- **Credencials amb l'emulador d'Auth**: `firebase_admin` s'inicialitza sense credencial; el health check només comprova que l'app estigui inicialitzada (`firebase: true`) i no fa cap crida de xarxa, així que no cal cap service account.
- Amb Postgres inabastable, `/api/health/` torna 503 `unhealthy` en ~10 s (`connect_timeout`).

## Estructura
```
conftest.py                         (arrel) django_db_setup, app_db/migrator_db, bloqueig de Firebase Admin real, mocks d'audit i permisos
apps/<feature>/tests/               tests de les features migrades (apps/core, apps/refuges, apps/accounts, apps/proposals, apps/moderation, apps/audit…: Postgres real, rol app; els de `apps/moderation` i `apps/audit` cobreixen esquema, RLS, denunciar/resoldre (concurrència, retenció CSAM amb R2 simulat), llista de hashes (`load_hash_blocklist`, `fn_hash_match`), bloqueig de pujades, avisos, esborrat d'usuari/refugi amb `legal_hold`, purgues i `server_error`; sense markers ni fixtures noves (usen `real_audit_log` per provar `AuditLogService` de debò, ja que el `conftest.py` de l'arrel el mocka); els de `apps/proposals` cobreixen esquema, RLS, CHECK `jsonb`, duplicats, concurrència de l'aprovació, esborrat amb R2 i esborrat d'usuari)
```
Cada test viu amb el seu codi, a `apps/<app>/tests/`; la infraestructura compartida és a `apps/core/tests/` (RLS, rol `app`, settings, CI), `apps/auth/tests/` (autenticació, permisos, emulador de Firebase), `apps/health/tests/` i `apps/uploads/tests/` (R2, imatge, `MediaMetadata`); `apps/health/tests/test_health_check.py` cobreix el health check (`{status, message, firebase, database}`). Les comandes antigues de refugis s'han eliminat; `load_refuges` es prova a `apps/refuges/tests/test_load_refuges.py`.

## Aïllament automàtic (feature images) [FET]
El `conftest.py` de l'arrel (compartit per tots els `apps/*/tests`) té quatre fixtures `autouse`:
- `_block_real_firebase`: `firebase_admin.get_app` falla (`ValueError('no app')`) → cap test inicialitza ni usa Firebase Admin real encara que `env/` tingui credencials; el health check surt «unhealthy» (`firebase: false`) llevat que el test ho mocki (`apps/health/tests/test_health_check.py`). Substitueix l'antic `_block_real_firestore` (chunk 11).
- `_mock_audit_log`: `AuditLogService.log` mockat. Marker `@pytest.mark.real_audit_log` per provar el servei.
- `_mock_permission_user_lookup`: `get_user_for_permissions` retorna un `UserAccount` (no desat) amb edat confirmada i no bloquejat, així que `HasProfile`, `IsNotBlocked` i `IsAgeConfirmed` passen **sense tocar PostgreSQL**. Marker `@pytest.mark.real_permissions` per provar-los de veritat contra la BD (`apps/accounts/tests/test_permissions.py` el fa servir) o patcheja tu `apps.auth.permissions.get_user_for_permissions`.
- `_restore_view_policies`: desa `permission_classes` i `authentication_classes` de totes les subclasses d'`APIView` abans de cada test i les restaura després. Els tests antics muten `view.cls.permission_classes = []` i abans la mutació es filtrava als tests següents (segons l'ordre d'execució, els de permisos d'`apps/accounts` fallaven). **No et refiïs-hi per a codi nou**: usa `patch.object` ([GOTCHAS #54](../GOTCHAS.md)).

Tests de media a `apps/uploads/tests/`: processament real amb Pillow/ffmpeg (imatges JPEG amb GPS generades en memòria i MP4 generats amb el ffmpeg d'imageio-ffmpeg, marker `slow`) i `media_helpers.fake_r2_service()`, un `R2MediaService` real amb el client boto3 mockat sobre un dict.

## Tests d'`apps/accounts` (chunk 3) [FET]
`apps/accounts/tests/`: `test_schema` (DDL, FK, índexs, grants), `test_models_constraints`, `test_rls` (anònim, propi, aliè, admin, sistema), `test_serializers`, `test_selectors_services`, `test_views_users`, `test_views_lists`, `test_permissions` (`real_permissions`), `test_query_counts` (`django_assert_num_queries`), `test_refuge_visitors` i `test_security_review`. Corren contra Postgres real amb el rol `app`; Firebase Auth i R2 es mocken (fixture `firebase_accounts`, el servei R2).

## Tests d'`apps/experiences` i `apps/uploads` (chunk 7) [FET]
`pytest apps/experiences apps/uploads -q` (Postgres real amb el rol `app`; R2 i `ModerationService` mockats).
- `apps/experiences/tests/`: `test_schema` (DDL, FK, índexs, grants), `test_models_constraints` (CHECK de comentari i condició), `test_rls`, `test_condition_trigger` (vot, ajust, vot antic després d'un reset, esborrat sense efecte, `app` no pot fer `UPDATE refuges`), `test_concurrency` (vots concurrents), `test_selectors_services`, `test_serializers`, `test_permissions` (permisos per mètode), `test_views_contract` (contracte HTTP), `test_query_counts` (llista 2 consultes, constant), `test_server_errors` (500 amb `error_id`, R2 caigut), `test_user_deletion` (cascada i fitxers d'R2), `test_security_review` i `apps/accounts/tests/test_experience_counts_and_deletion.py` (comptadors del perfil ≤ 3 consultes).
- `apps/uploads/tests/`: `test_schema`, `test_models_constraints` (shape/state/expire), `test_rls` (intents privats), `test_views_intents` / `test_views_confirm` (idempotència, `missing_object`, rollback d'R2, moderació), `test_purge_command` (lots, `CommandError`), `test_user_deletion`, `test_security_review`.
- `apps/refuges/tests/test_experience_media.py`: `refuge_media.experience_id` i la política `media_insert`.
- Les fixtures i helpers (`make_user`, `make_refuge`, `make_experience`…) són a `tests/helpers.py` i `conftest.py` de cada app. Els tests de BD porten `pytest.mark.real_permissions` quan han de passar pels permisos reals.
- Els tests legacy d'experiències i els d'intents de media han estat substituïts pels nous (D38).

## Escriure tests (resum)
- Vista: contracte HTTP contra Postgres real (rol `app`) amb `APIClient`/`APIRequestFactory`; Firebase Auth es mocka amb la fixture `firebase_accounts`.
- Desactiva permisos amb `patch.object(Vista, 'permission_classes', [])`, **no** assignant `view.cls.permission_classes = []` (muta la classe; `_restore_view_policies` ho restaura després de cada test, però no t'hi basis). Per a una vista amb `get_permissions()` cal patchejar `get_permissions`, no `permission_classes`.
- Admin: `request.user_claims = {'role': 'admin', ...}`.
- Detall pas a pas per a un endpoint nou: [recipes/add-endpoint.md](../recipes/add-endpoint.md).

## Objectius orientatius de coverage per capa
Models ~100 %, serializers ~95 %, selectors i services ~90 %, vistes ~85 %. (Objectius històrics del projecte, no forçats per CI.)
