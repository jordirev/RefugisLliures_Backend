# CLAUDE.md — RefugisLliures Backend

API REST (Django 5.1 + DRF) de l'app Refugis Lliures: refugis de muntanya, fotos, experiències, dubtes, visites, reformes ("renovations") i propostes de canvi revisades per admins.
Documentació detallada a [`docs/`](docs/README.md). Llegenda als docs: **[FET]** / **[INFERÈNCIA]** / **[NO VERIFICAT]**.

## Stack
- **Firestore** és la BD real (via `firebase-admin`). SQLite (`db.sqlite3`) només per a apps internes de Django; cap model de domini és un model Django.
- **Firebase Auth**: ID token `Bearer` verificat al middleware; admin = custom claim `role == 'admin'`.
- **Cloudflare R2** (boto3) per a media; bucket privat, URLs presignades d'1 h.
- **Redis** (django-redis) com a cache; errors de Redis s'empassen silenciosament.
- Deploy a **Render** (gunicorn, 1 worker); CI, ping i procés diari a **GitHub Actions**.

## Comandes
```bash
pip install -r requirements.txt
python manage.py runserver            # requereix env/ local + Redis + variables R2_* exportades
pytest                                # tots els tests (api/tests)
pytest api/tests/renovation -q        # un domini
pytest -m views                       # per marker (pytest.ini, --strict-markers)
tox                                   # com a CI: pytest + coverage.xml
python manage.py process_yesterday_visits
python scripts/manage_admins.py <add|remove|check|list> [uid]
```
Swagger: `/swagger/`, `/redoc/`. Totes les rutes de l'API sota `/api/` (`api/urls.py`).

## Capes (patró de referència: renovations)
```
View (APIView) → Serializer → Controller → DAO → CacheService / Firestore / R2MediaService
api/views  api/serializers  api/controllers  api/daos  api/services   + api/mappers, api/models
```
- **View**: declara `permission_classes` (el default global és `AllowAny`!), valida amb `XCreateSerializer`/`XUpdateSerializer`, usa `request.user_uid`, serialitza `XSerializer(model.to_dict())`.
- **Controller**: retorna `(success, data, error)` o `(success, error)`; captura excepcions → `"Error intern: ..."`; aquí van les **comprovacions de propietat**.
- **DAO**: `COLLECTION_NAME`, `FirestoreService().get_db()`, `cache_service` (get→Firestore→set; invalida en escriure).
- **Model**: `@dataclass` amb validació a `__post_init__`, `to_dict`/`from_dict`. **Mapper**: estàtic.
- La vista tria l'HTTP status **per subcadena del missatge d'error** (`'solapa'`→409, `'not found'`/`'no trobada'`→404…).

## Convencions
- Català a docstrings, comentaris i la majoria de missatges; identificadors en anglès (domini refugi en català: `RefugiLliureDAO`, `data_refugis_lliures`).
- Dates com a strings ISO; zona `Europe/Madrid` via `api/utils/timezone_utils.py`.
- IDs: auto-ID de Firestore, desat també com a camp `id`; `users/{uid}` usa l'UID de Firebase.
- Logs: nivells propis CACHE=21, FIRESTORE=22, DAO=23 (`logger.log(23, "Firestore READ: ...")`).
- Swagger: exemples a `api/utils/swagger_examples.py`, errors a `api/utils/swagger_error_responses.py`.
- Tests per domini a `api/tests/<domini>/test_{models,mappers,daos,serializers,controllers,views}.py`; es mocka `FirestoreService`/`cache_service` al mòdul del DAO i el controller al mòdul de la vista.

## Top gotchas (llista completa: docs/GOTCHAS.md)
1. `has_object_permission` **mai s'executa** (cap `check_object_permissions`): `Is*Creator` no protegeix res. Comprova la propietat al controller. Avui experiències, dubtes i respostes **no tenen control de propietari**.
2. El middleware exclou per prefix `/api/refuges/` (també media/visits/renovations): la protecció depèn només de `permission_classes`.
3. `cache_service.delete_pattern(p)` ja fa `*p*`: **no** afegeixis `:*` al final (bug a propostes → doble aprovació).
4. No facis read-modify-write d'arrays/maps: usa `ArrayUnion`/`ArrayRemove`/`Increment` o transaccions (no n'hi ha cap avui).
5. Serializer i `__post_init__` han d'aplicar les mateixes regles (cas `ini_date == fin_date` a renovations).
6. Cap `default=` en serializers d'update (PATCH d'usuari reseteja `language`).
7. `R2MediaService.delete_file` retorna `False`, no llança. No passis `filename=file.name` a `upload_file` (col·lisions).
8. Variables `R2_*` es llegeixen amb `os.getenv`; `decouple` no omple `os.environ` → exporta-les a l'entorn.
9. Canviar el text d'un error pot canviar el codi HTTP.
10. Els tests de vistes muten `view.cls.permission_classes`; usa `patch.object`.

## Seguretat
- **No llegeixis ni imprimeixis** fitxers de `env/` (service accounts, `.env.*`, `api-keys.env`). No estan versionats; només se'n poden esmentar els noms de variables.
- No posis credencials reals a `run_process_visits.sh` / `run_process_visits.bat`.
- Defaults inseguros a `refugis_lliures/settings.py` (`DEBUG=True`, `ALLOWED_HOSTS='*'`, CORS obert): en producció depenen de Render.

## Índex de docs
- `docs/ARCHITECTURE.md` — stack, capes, taula de rutes i permisos, auth, cache, convencions, excepcions, tests.
- `docs/GOTCHAS.md` — què NO fer · `docs/TECH_DEBT.md` — bugs i deute per severitat.
- `docs/flows/` — 00 auth · 01 perfil · 02 avatar · 03 fotos refugi · 04 cerca/detall · 05 propostes · 06 visites · 07 renovations · 08 experiències · 09 dubtes · 10 preferits/visitats · 11 admin cache/health.
- `docs/integrations/` — firebase-auth · firestore · cloudflare-r2 · redis-cache · render-deploy-ci.
- `docs/recipes/` — add-endpoint · add-service · add-model.
- `docs/guides/` — passos per executar/configurar: local-setup · testing · firebase-credentials · r2-render-setup · admin-management · client-auth-usage · daily-visits-process.
- `docs/design/` — patterns (detall dels patrons) · decisions (ADR: APIView, auth DRF+middleware, custom claims).
- `docs/deep-dives/` — condition-average · refuge-proposals-payload · user-deletion (enllaçats des dels fluxos pare).

## En canviar codi
**Regla general: `docs/` s'actualitza en el mateix canvi que el codi.** Abans de donar una tasca per acabada, revisa aquesta taula i edita els docs afectats (mantén la llegenda **[FET]** / **[INFERÈNCIA]** / **[NO VERIFICAT]**; si verifiques una inferència, passa-la a [FET]).

| Canvi al codi | Docs a actualitzar |
|---|---|
| Endpoint nou/modificat/eliminat (ruta, mètode, permisos, payload, codis HTTP) | `docs/recipes/add-endpoint.md` (guia); `docs/ARCHITECTURE.md §4` (taula de rutes i permisos); el flux afectat a `docs/flows/` |
| Model, mapper, serializer o regla de validació nova/canviada | El flux afectat; `docs/recipes/add-model.md` si canvia el patró; `docs/deep-dives/` relacionat (ex. `refuge-proposals-payload`, `condition-average`) |
| Servei nou o canvi a `api/services` (cache, R2, Firestore) | `docs/recipes/add-service.md` si canvia el patró; l'`docs/integrations/` corresponent |
| Canvi a middleware, autenticació, permisos o claims | `docs/flows/00-auth-request-pipeline.md`, `docs/integrations/firebase-auth.md`, `docs/ARCHITECTURE.md §5`, `docs/guides/client-auth-usage.md`, i ADR a `docs/design/decisions.md` si és una decisió d'arquitectura |
| Canvi a cache (claus, TTL, invalidació) | `docs/integrations/redis-cache.md`, `docs/ARCHITECTURE.md §6` |
| Nou patró, excepció al patró de capes o convenció | `docs/design/patterns.md`, `docs/ARCHITECTURE.md §7–9` |
| Canvi a deploy, CI, GitHub Actions, variables d'entorn, `render.yaml`, `tox.ini` | `docs/integrations/render-deploy-ci.md`, `docs/guides/local-setup.md`, `docs/guides/r2-render-setup.md`, `docs/guides/firebase-credentials.md` (només noms de variables) |
| Canvi a proves (markers, fixtures, estructura de tests) | `docs/guides/testing.md`, `docs/ARCHITECTURE.md §10` |
| Canvi a scripts o al procés diari (`process_yesterday_visits`, `manage_admins.py`) | `docs/guides/daily-visits-process.md` / `docs/guides/admin-management.md`, `docs/flows/06-refuge-visits.md` |
| Descobreixes un comportament perillós o contraintuïtiu | Afegeix-lo a `docs/GOTCHAS.md` (i al "Top gotchas" d'aquest fitxer si és crític) |
| Corregeixes un bug de `docs/TECH_DEBT.md` | Treu-lo o marca'l com a resolt; si també era un gotcha, actualitza `docs/GOTCHAS.md` |
| Detectes un bug o deute nou que no corregeixes | Afegeix-lo a `docs/TECH_DEBT.md` amb severitat |
| Fitxer de doc nou, reanomenat o eliminat | Actualitza `docs/README.md` i l'"Índex de docs" d'aquest fitxer; revisa enllaços trencats |
| Canvis a l'estructura de directoris, stack o comandes | `docs/ARCHITECTURE.md §1–2`, la secció "Stack"/"Comandes" d'aquest fitxer |

Després de modificar codi, executa també `graphify update .` (vegeu la secció graphify).

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
