# Guia — Executar i escriure tests

> **[FET]** comprovat al codi · **[INFERÈNCIA]** deducció · **[NO VERIFICAT]** depèn de config externa.
> Convencions de tests (mocks, estructura, fixtures mortes): [ARCHITECTURE §10](../ARCHITECTURE.md). Gotchas: [GOTCHAS #30-31](../GOTCHAS.md).

## Requisits
`pip install -r requirements.txt` ja inclou `pytest`, `pytest-django`, `pytest-cov`, `pytest-mock` i `coverage`. No cal Firebase, Firestore, Redis ni R2: tot es mocka.

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
Markers declarats a `pytest.ini` (amb `--strict-markers`, un marker no declarat fa fallar): `unit, integration, views, serializers, controller, controllers, daos, mappers, models, edge_cases, slow`.

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

## Estructura
```
api/tests/
  conftest.py                       fixtures compartides i mocks
  <domini>/test_{models,mappers,daos,serializers,controllers,views}.py   (+ test_integration.py a refugi_lliure, renovation, user)
  test_auth_middleware_permissions.py, test_cache_views.py
  management_commands/
```
Dominis: `doubts`, `experiences`, `refuge_proposal`, `refuge_visit`, `refugi_lliure`, `renovation`, `user`.

## Escriure tests (resum)
- DAO: `@patch('api.daos.<domini>_dao.FirestoreService')` + `@patch('api.daos.<domini>_dao.cache_service')`.
- Vista: mocka el controller **al mòdul de la vista** (`@patch('api.views.<domini>_views.<X>Controller')`) i usa `APIRequestFactory`; posa `request.user_uid`.
- Desactiva permisos amb `patch.object(Vista, 'permission_classes', [])`, **no** assignant `view.cls.permission_classes = []` (muta la classe per a tota la sessió).
- Admin: `request.user_claims = {'role': 'admin', ...}`.
- Detall pas a pas per a un endpoint nou: [recipes/add-endpoint.md §6](../recipes/add-endpoint.md).

## Objectius orientatius de coverage per capa
Models i mappers ~100 %, serializers ~95 %, DAOs i controllers ~90 %, vistes ~85 %. (Objectius històrics del projecte, no forçats per CI.)
