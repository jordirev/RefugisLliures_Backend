# Guia — Executar i escriure tests

> **[FET]** comprovat al codi · **[INFERÈNCIA]** deducció · **[NO VERIFICAT]** depèn de config externa.
> Convencions de tests (mocks, estructura, fixtures mortes): [ARCHITECTURE §10](../ARCHITECTURE.md). Gotchas: [GOTCHAS #30-31](../GOTCHAS.md).

## Requisits
`pip install -r requirements.txt` ja inclou `pytest`, `pytest-django`, `pytest-cov`, `pytest-mock` i `coverage`. No cal Firebase, Firestore, Redis ni R2: tot es mocka. Des del chunk 1 de la migració calen a més **GDAL/GEOS** al sistema (`django.contrib.gis` és sempre actiu) i, per als tests de BD, un **PostgreSQL + PostGIS local** (vegeu més avall); sense Postgres els tests amb BD se salten i els que no toquen la BD funcionen amb el SQLite de reserva **[FET]**.

## Executar
```bash
pytest                                   # tots (testpaths = api/tests)
pytest api/tests/renovation -q           # un domini
pytest api/tests/user/test_views.py      # un fitxer
pytest api/tests/user/test_views.py::TestX::test_y   # un test
pytest -k "create"                       # per nom
pytest -m views                          # per marker
tox                                      # com a CI: pytest + coverage.xml
```
Markers declarats a `pytest.ini` (amb `--strict-markers`, un marker no declarat fa fallar): `unit, integration, views, serializers, controller, controllers, daos, mappers, models, edge_cases, slow, db_infra, rls, real_audit_log, real_permissions`.

Depuració: `pytest -x` (atura al primer error), `--maxfail=3`, `--tb=long`, `-s` (mostra `print`), `--pdb`.

## Coverage
```bash
pytest --cov=api --cov-report=term-missing      # línies no cobertes
pytest --cov=api --cov-report=html              # informe a htmlcov/index.html
```
`.coveragerc` i Sonar **exclouen `services/` i `utils/`**. CI puja `coverage.xml` a Codecov i SonarCloud ([render-deploy-ci](../integrations/render-deploy-ci.md)).

`run_tests.py` ofereix un menú interactiu, però les opcions per mòdul apunten a `api/tests/test_user.py` i `test_refugi_lliure.py`, que **ja no existeixen** (els tests ara són per carpeta de domini) **[FET]**.

## Per què Firebase no s'inicialitza als tests
`ApiConfig.ready()` crida `initialize_firebase()` en carregar Django, abans que comencin els tests. Per evitar que busqui credencials (i falli a CI):
1. `conftest.py` (arrel) fixa `TESTING=true` i `R2_*` falses **abans de qualsevol import**, i ho reforça a `pytest_configure`.
2. `api/tests/conftest.py` té la fixture `setup_test_environment` (`autouse`, scope `session`) que torna a posar `TESTING=true`.
3. `api/firebase_config.py` no inicialitza res si `'pytest' in sys.modules` o `TESTING=='true'`.

Per a un test d'integració amb Firebase real caldria `TESTING=false` i credencials (no n'hi ha cap avui).

## Tests contra PostgreSQL local (migració, chunk 1) [FET]
- Bootstrap idempotent: `scripts/dev/setup_local_postgres.sh` (arrenca el clúster apt si cal; crea els rols `migrator` i `app` amb els atributs de `docs/design/postgres-schema.md` §1.3, la BD `refugisdb_test` i les extensions `postgis`, `pg_trgm`, `unaccent`, `btree_gist`). Imprimeix les dues URLs locals (no secretes); a CI es parametritza amb `PGHOST`, `PGPORT`, `PG_SUPERUSER`, `PGPASSWORD`, `PG_START_CLUSTER=0`.
- Exporta-les: `eval "$(scripts/dev/setup_local_postgres.sh | grep ^export)"` → `TEST_DATABASE_URL_MIGRATOR` / `TEST_DATABASE_URL_APP`.
- Marker `db_infra`: necessita aquestes variables i **se salta** (amb motiu) si falten; marker `rls`: tests del context RLS i del hook (executen el `set_config` de debò). Les migracions les aplica `migrator` i els tests corren com a `app` (la RLS només s'aplica a `app`).
- **`django_db_setup`** (`api/tests/conftest.py`) sobreescriu el de pytest-django: amb `migrator` definit **no crea cap BD `test_*`**; executa `migrate --database=migrator` sobre la BD de proves (idempotent) i dona al rol `app` DML sobre les taules de Django de `public` (només a la BD de proves: alguns tests creen un `auth.User` per a `force_authenticate`; no formen part dels grants de producció). Sense `migrator` (sense Postgres) es manté el comportament per defecte sobre SQLite.
- **`TEST_DATABASE_URL_APP` / `TEST_DATABASE_URL_MIGRATOR` tenen prioritat** sobre `DATABASE_URL_*` a `settings.py`: els tests mai van a Neon encara que `env/` en tingui les URL.
- **Fixture `_rls_hook_sense_bd`** (`autouse`): als tests que **no** porten cap dels markers `rls`, `django_db`, `db_infra` (vistes amb controllers mockejats, sense BD) fa `patch('api.rls_hook.apply_context')`, perquè el hook de RLS no intenti executar `set_config` sense connexió a Postgres. Els tests de BD l'executen de debò. Si un test de vista sense BD vol comprovar el hook, ha de dur el marker `rls`.
- Les fixtures `app_db` / `migrator_db` (`api/tests/conftest.py`) donen connexions en autocommit fora de la transacció de pytest-django, necessàries per provar contextos locals a la transacció.
- **Guarda de host**: `django_db_setup` fa `pytest.exit` (codi 2) si el `HOST` de `TEST_DATABASE_URL_MIGRATOR` no és local (`localhost`, `127.0.0.1`, `::1`, `host.docker.internal`, `*.localhost`): els tests mai poden córrer contra Neon, encara que s'hi apunti per error **[FET]**.
- Tests de seguretat a `api/tests/security/`: rol `app` (sense atributs privilegiats ni propietat d'objectes, no pot crear objectes als schemas ni escalar privilegis ni substituir `core.*`; `core.*` no executables per `PUBLIC`, `SECURITY DEFINER` amb `search_path` fixat), hook de RLS (context local a la transacció, avís fora de transacció, `is_system` reiniciat, contextos interns que no escalen l'extern, `uid` no-string = anònim, `role` no exacte no dona admin), respostes d'auth (el 401 no filtra detalls ni l'UID als logs) i guarda de l'emulador de Firebase (plataformes, hosts locals, variants booleanes) **[FET]**.
- Tests d'infraestructura a `api/tests/infra/` (settings de BD, hook de RLS, health, arquitectura RLS, emulador, `uuid7`, middleware del health) i `api/tests/core/` (context RLS, helpers de polítiques, funcions SQL de `core`).
- Execució a CI: servei `postgis/postgis:17-3.5` + `setup_local_postgres.sh` amb `PGHOST=localhost PG_START_CLUSTER=0`; `tox.ini` fa `passenv` de les `TEST_DATABASE_URL_*` ([render-deploy-ci.md](../integrations/render-deploy-ci.md)).

### Windows: tests en un contenidor Linux [FET]
No hi ha GDAL natiu a Windows, així que els tests s'executen en un contenidor (així s'han passat els del chunk 1: `python:3.13-slim` + `gdal-bin libgdal-dev libgeos-dev libproj-dev`, `pip install -r requirements.txt`) contra un contenidor `postgis/postgis:17-3.5`. El Dockerfile, l'arrencada del Postgres i el *bootstrap* són a [local-setup.md § PostgreSQL](local-setup.md). Les proves, amb el repo muntat a `/app`:
```powershell
docker run --rm -v "${PWD}:/app" -w /app --add-host=host.docker.internal:host-gateway `
  -e PGHOST=host.docker.internal -e PG_START_CLUSTER=0 -e PGPASSWORD=<contrasenya-local> rl-backend `
  bash -c 'eval "$(scripts/dev/setup_local_postgres.sh | grep ^export)" && pytest -q'
```
Alternativa: `TEST_DATABASE_URL_APP` i `TEST_DATABASE_URL_MIGRATOR` a `env/.env.development` amb host `host.docker.internal` (no cal l'`eval`; no imprimeixis els valors). El contenidor corre Python 3.13 i CI 3.10: un test que depengui de la versió pot divergir **[INFERÈNCIA]**.

## Estructura
```
api/tests/
  conftest.py                       fixtures compartides i mocks
  <domini>/test_{models,mappers,daos,serializers,controllers,views}.py   (+ test_integration.py a refugi_lliure, renovation, user)
  test_auth_middleware_permissions.py, test_cache_views.py
  management_commands/
```
Dominis: `doubts`, `experiences`, `refuge_proposal`, `refuge_visit`, `refugi_lliure`, `renovation`, `user`.

## Aïllament automàtic (feature images) [FET]
`api/tests/conftest.py` té tres fixtures `autouse`:
- `_block_real_firestore`: `FirestoreService._initialize_firebase` llança → cap test pot connectar-se a Firestore real encara que `env/` tingui credencials. Si un test peta amb "Els tests no poden connectar-se a Firestore real", et falta un mock.
- `_mock_audit_log`: `AuditLogService.log` mockat. Marker `@pytest.mark.real_audit_log` per provar el servei.
- `_mock_permission_user_lookup`: `get_user_for_permissions` retorna un usuari amb edat confirmada i no bloquejat. Marker `@pytest.mark.real_permissions` per provar `IsNotBlocked`/`IsAgeConfirmed` (i patcheja tu `api.permissions.get_user_for_permissions`).

Domini `api/tests/media/`: processament real amb Pillow/ffmpeg (imatges JPEG amb GPS generades en memòria i MP4 generats amb el ffmpeg d'imageio-ffmpeg, marker `slow`) i `helpers.fake_r2_service()`, un `R2MediaService` real amb el client boto3 mockat sobre un dict.

## Escriure tests (resum)
- DAO: `@patch('api.daos.<domini>_dao.FirestoreService')` + `@patch('api.daos.<domini>_dao.cache_service')`.
- Vista: mocka el controller **al mòdul de la vista** (`@patch('api.views.<domini>_views.<X>Controller')`) i usa `APIRequestFactory`; posa `request.user_uid`.
- Desactiva permisos amb `patch.object(Vista, 'permission_classes', [])`, **no** assignant `view.cls.permission_classes = []` (muta la classe per a tota la sessió).
- Admin: `request.user_claims = {'role': 'admin', ...}`.
- Detall pas a pas per a un endpoint nou: [recipes/add-endpoint.md §6](../recipes/add-endpoint.md).

## Objectius orientatius de coverage per capa
Models i mappers ~100 %, serializers ~95 %, DAOs i controllers ~90 %, vistes ~85 %. (Objectius històrics del projecte, no forçats per CI.)
