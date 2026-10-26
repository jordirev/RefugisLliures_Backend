# CLAUDE.md — RefugisLliures Backend

API REST (Django 5.2 LTS + DRF, Python 3.14) de l'app Refugis Lliures: refugis de muntanya, fotos, experiències, dubtes, visites, reformes ("renovations") i propostes de canvi revisades per admins.
Documentació detallada a [`docs/`](docs/README.md). Llegenda als docs: **[FET]** / **[INFERÈNCIA]** / **[NO VERIFICAT]**.

## Stack
- **PostgreSQL + PostGIS (Neon)** és la BD `default` de Django (rol `app`, `ATOMIC_REQUESTS`, RLS; àlies `migrator` per a DDL) des del chunk 1 de la migració; **requereix GDAL/GEOS** (`django.contrib.gis` sempre actiu). Sense URL de Postgres, `default` cau a SQLite (només per a tests sense BD).
- **Refugis (chunk 2), usuaris (chunk 3), visites (chunk 4) i dubtes i respostes (chunk 6) ja són a PostgreSQL** (`apps/refuges`, `apps/accounts`: usuari, perfil públic, avatar, preferits, visitats, moderació d'usuari; `apps/visits`: visites, participants i job diari; `apps/doubts`: dubtes i respostes); **Firestore** (via `firebase-admin`) continua sent la BD de la resta del domini (reformes, experiències, propostes, notificacions de moderació…) fins als chunks següents (`docs/migration/`). Els dominis encara a Firestore llegeixen els refugis amb el `RefugiLliureDAO` legacy (que ja no s'alimenta) fins que els migri el seu chunk; el perfil propi encara compta experiències i reformes a Firestore (D19) i l'esborrat d'usuari encara toca Firestore (D21).
- **Firebase Auth**: ID token `Bearer` verificat al middleware; admin = custom claim `role == 'admin'`. Un hook (`api/rls_hook.py`) fixa el context de RLS (`app.uid`, `app.is_admin`) a la transacció de cada petició. Per a e2e locals, `FIREBASE_AUTH_EMULATOR_HOST` (mai en producció).
- **Cloudflare R2** (boto3) per a media; bucket privat, URLs presignades d'1 h.
- **Redis** (django-redis) com a cache de les features encara a Firestore; errors de Redis s'empassen silenciosament. Les features migrades (refugis, usuaris, visites, dubtes) no usen cache de dades (`user_detail` ha desaparegut).
- Deploy a **Render** (gunicorn, 1 worker); CI, ping i procés diari a **GitHub Actions**.

## Comandes
```bash
py -3.14 -m venv .venv && .venv\Scripts\activate   # Windows; Python 3.14 també a CI i producció
pip install -r requirements.txt
python manage.py runserver            # requereix env/ local + Postgres (DATABASE_URL_APP) + Redis + GDAL; R2_* només per als endpoints de media
python manage.py migrate --database=migrator   # SEMPRE amb el rol migrator (app no té DDL)
python manage.py check_neon --alias default    # (o migrator) comprova Postgres/PostGIS
python manage.py load_refuges [--dry-run]      # UNA sola vegada: càrrega del catàleg de refugis (1.542) amb el rol migrator; error si ja hi ha refugis
pytest                                # tots els tests (api/tests + apps); els de BD volen TEST_DATABASE_URL_APP/MIGRATOR (scripts/dev/setup_local_postgres.sh); a Windows, en un contenidor Linux amb GDAL (docs/guides/testing.md)
pytest api/tests/renovation -q        # un domini (Firestore)
pytest apps/refuges -q                # una app migrada (també apps/accounts, apps/visits)
pytest -m views                       # per marker (pytest.ini, --strict-markers)
tox                                   # com a CI: pytest + coverage.xml
python manage.py process_yesterday_visits   # apps/visits: visites d'ahir -> user_visited_refuges + purga >12 mesos; CommandError (codi != 0) si falla (D28)
python scripts/manage_admins.py <add|remove|check|list> [uid]
```
Swagger: `/swagger/`, `/redoc/`. Totes les rutes de l'API sota `/api/` (`api/urls.py`).

## Capes
**Features migrades a PostgreSQL** (una app Django per feature a `apps/`, estil HackSoft; referència: `apps/refuges`):
```
View (APIView) → Serializer → selectors (lectures) / services (escriptures) → models (ORM + RLS) [+ R2MediaService]
apps/<feature>/{views, serializers, selectors, services, models, urls, migrations, management/commands, tests}
```
- **View**: fina; declara `permission_classes` (el default global és `AllowAny`!; tot endpoint autenticat porta `IsAuthenticated, HasProfile, …`, llevat de `POST /users/` i `/api/cache/*`), valida amb el serializer, crida un selector o un service i mapa les excepcions de domini a HTTP. El context de RLS el posa el hook.
- **Errors 500 amb traçabilitat** (política del PO per a les features migrades): la resposta és `{"error": "<missatge específic del punt que ha fallat>", "error_id": "<uuid>"}` i el mateix `error_id` es desa al log amb la traça completa (`logger.exception`). **Mai** es retorna `str(e)` ni el nom/text de l'excepció (pot dur SQL, hosts, bucket, claus o rutes). Ho fa el helper `apps.core.errors.server_error(message, exc, logger=logger)`; el missatge és un text fix per punt ("Error en esborrar el fitxer a R2", "Error de base de dades en cercar refugis", "Error en generar la URL de la imatge"…).
- **selectors.py**: lectures (substitueixen el DAO); una consulta per cas d'ús (`select_related`/`Prefetch`/`ArraySubquery`), filtres al `WHERE`, **sense cache**. Els tests comproven el nombre de consultes.
- **services.py**: escriptures (substitueixen el controller); `transaction.atomic`, `select_for_update` si cal, R2; llancen excepcions de domini (no tuples). Aquí van les **comprovacions de propietat** (a més de la RLS).
- **models.py + migracions**: `db_table = 'schema"."taula'`, FK `DO_NOTHING` + `db_constraint=False` i la restricció real (`ON DELETE`), la RLS, els grants i els triggers per `RunSQL` a la mateixa migració (`apps.core.migration_utils`). Les rutes de la feature estan a `apps/<feature>/urls.py` i s'inclouen des d'`api/urls.py`.

**Features encara a Firestore** (patró de referència: renovations):
```
View (APIView) → Serializer → Controller → DAO → CacheService / Firestore / R2MediaService
api/views  api/serializers  api/controllers  api/daos  api/services   + api/mappers, api/models
```
- **View**: declara `permission_classes`, valida amb `XCreateSerializer`/`XUpdateSerializer`, usa `request.user_uid`, serialitza `XSerializer(model.to_dict())`.
- **Controller**: retorna `(success, data, error)` o `(success, error)`; captura excepcions → `"Error intern: ..."`; aquí van les **comprovacions de propietat**.
- **DAO**: `COLLECTION_NAME`, `FirestoreService().get_db()`, `cache_service` (get→Firestore→set; invalida en escriure).
- **Model**: `@dataclass` amb validació a `__post_init__`, `to_dict`/`from_dict`. **Mapper**: estàtic.
- La vista tria l'HTTP status **per subcadena del missatge d'error** (`'solapa'`→409, `'not found'`/`'no trobada'`→404…).

## Convencions
- Català a docstrings, comentaris i la majoria de missatges; identificadors en anglès (el domini refugi legacy en català: `RefugiLliureDAO`, `data_refugis_lliures`; a `apps/refuges` tot en anglès).
- Dates: `TIME_ZONE = 'Europe/Madrid'` (decisió del PO, 26/10): «avui» amb `get_madrid_today()`/`timezone.localdate()`, mai `CURRENT_DATE`/`now()::date` al SQL (la sessió de Postgres és UTC; test de guarda `apps/core/tests/test_timezone.py`). Instants `timestamptz` amb el rellotge de la BD (`Now()`/`db_default`); durades amb `madrid_after()` (GOTCHAS #60–62). L'API emet ISO amb desplaçament de Madrid.
- IDs: a les apps migrades, UUID v7 generat per la BD (`DEFAULT uuidv7()`, Postgres 18; `db_default` als models) exposat com a string opac; a Firestore, auto-ID desat també com a camp `id`; `users/{uid}` usa l'UID de Firebase.
- Logs: nivells propis CACHE=21, FIRESTORE=22, DAO=23 (`logger.log(23, "Firestore READ: ...")`).
- Swagger: exemples a `api/utils/swagger_examples.py`, errors a `api/utils/swagger_error_responses.py`.
- Tests per domini a `api/tests/<domini>/test_{models,mappers,daos,serializers,controllers,views}.py` (dominis `user` i `doubts` ja no: són a `apps/accounts/tests/` i `apps/doubts/tests/`); es mocka `FirestoreService`/`cache_service` al mòdul del DAO i el controller al mòdul de la vista. Les apps migrades tenen els tests a `apps/<feature>/tests/` (contra Postgres real amb el rol `app`: esquema, RLS, models, cerca, contracte HTTP, recomptes de consultes); les fixtures compartides són al `conftest.py` de l'arrel.

## Top gotchas (llista completa: docs/GOTCHAS.md)
1. `has_object_permission` **mai s'executa** (cap `check_object_permissions`): `Is*Creator` no protegeix res. Comprova la propietat al controller (experiències ho fan al controller; dubtes i respostes, al service des del chunk 6).
2. El middleware exclou per prefix `/api/refuges/` (també media/visits/renovations): la protecció depèn només de `permission_classes`.
3. `cache_service.delete_pattern(p)` ja fa `*p*`: **no** afegeixis `:*` al final (bug a propostes → doble aprovació).
4. No facis read-modify-write d'arrays/maps: usa `ArrayUnion`/`ArrayRemove`/`Increment` o `FieldPath('media_metadata', key).to_api_repr()` / `DELETE_FIELD` (les claus R2 porten `/` i `.`).
5. Serializer i `__post_init__` han d'aplicar les mateixes regles (cas `ini_date == fin_date` a renovations).
6. Cap `default=` en serializers d'update (el bug del PATCH d'usuari que reseteja `language` es va corregir al chunk 3; la regla segueix vigent als dominis a Firestore).
7. `R2MediaService.delete_file` retorna `False`, no llança: comprova el booleà. Tota pujada (única via: upload-intents + `confirm`) ha de passar per `MediaUploadController.process_and_publish` (neteja EXIF, tipus real, claus UUID); no facis `put_object` de bytes de l'usuari directament.
8. Variables `R2_*` es llegeixen amb `os.getenv`; `decouple` no omple `os.environ` → exporta-les a l'entorn.
9. Canviar el text d'un error pot canviar el codi HTTP.
10. El context de RLS (`set_config(..., true)`) és local a la transacció i només el posa el hook a peticions HTTP; en comandes/jobs usa `rls_context()`/`system_context()`. Migracions sempre `--database=migrator`. `ATOMIC_REQUESTS` no desfà escriptures a Firestore/R2.
11. Els tests de vistes muten `view.cls.permission_classes`; usa `patch.object` (el `conftest.py` de l'arrel restaura `permission_classes`/`authentication_classes` de totes les vistes després de cada test: `_restore_view_policies`). El mateix `conftest.py` bloqueja Firestore real i mocka `AuditLogService.log` i `get_user_for_permissions` (markers `real_audit_log`, `real_permissions` per desactivar-ho).
12. A les apps migrades les FK són `DO_NOTHING` + `db_constraint=False`: les cascades i `SET NULL` són del DDL (migració `RunSQL`), no de Django; no depenguis de `on_delete` ni de signals. `load_refuges` és d'un sol ús (sense `--overwrite`). `bulk_create` no recupera els PK de `db_default` (`uuidv7()`): demana'ls abans a la BD (GOTCHAS #48).
13. **Estat intermedi (chunk 2 → 7)**: els dominis encara a Firestore comproven els refugis amb el `RefugiLliureDAO` legacy (catàleg antic, IDs diferents dels UUID de PostgreSQL); les fotos noves i les propostes aprovades escriuen a Firestore i no es veuen a `/api/refuges/`. No usis el DAO legacy en codi nou (GOTCHAS #41–42, TECH_DEBT R1–R7).
14. Errors 500 a les apps migrades: sempre `server_error(...)` (`{error, error_id}`), mai `str(e)`.
15. **`HasProfile`** (403 `profile_required`) va just després d'`IsAuthenticated` a tot endpoint autenticat (excepte `POST /users/` i `/api/cache/*`) i **abans** d'`IsNotBlocked`/`IsAgeConfirmed`: un usuari sense fila rep `profile_required`, mai `age_not_confirmed`. Una vista nova autenticada l'ha d'incloure. Els permisos llegeixen `users.users` **una sola vegada per petició** (cau a `request`, no a Redis).
16. Les llistes d'usuari tenen **PK composta**: `obj.pk` és una tupla `(user_id, refuge_id)` i no hi ha `obj.id` (GOTCHAS #52). Moderació d'usuari (strikes/bloqueig) i avatar des d'altres dominis s'escriuen a PostgreSQL amb `system_context()` (`fn_users_guard` ho exigeix, D20).
17. **Visites (chunk 4)**: el total surt de la vista `refuge_visit_totals`, mai d'un `Sum` sota RLS (GOTCHAS #63); la data és estrictament `YYYY-MM-DD` (#64); POST/PATCH exigeixen `IsNotBlocked` + `IsAgeConfirmed`, DELETE no; el job ha de sortir amb codi != 0 si falla (#65).

## Seguretat
- **No llegeixis ni imprimeixis** fitxers de `env/` (service accounts, `.env.*`, `api-keys.env`). No estan versionats; només se'n poden esmentar els noms de variables.
- No posis credencials reals a `run_process_visits.sh` / `run_process_visits.bat`.
- Defaults inseguros a `refugis_lliures/settings.py` (`DEBUG=True`, `ALLOWED_HOSTS='*'`, CORS obert): en producció depenen de Render.

## Índex de docs
- `docs/ARCHITECTURE.md` — stack, capes, taula de rutes i permisos, auth, cache, convencions, excepcions, tests.
- `docs/GOTCHAS.md` — què NO fer · `docs/TECH_DEBT.md` — bugs i deute per severitat.
- `docs/flows/` — 00 auth · 01 perfil · 02 avatar · 03 fotos refugi · 04 cerca/detall · 05 propostes · 06 visites · 07 renovations · 08 experiències · 09 dubtes · 10 preferits/visitats · 11 admin cache/health · 12 denúncies/moderació/edat/auditoria.
- `docs/integrations/` — firebase-auth · firestore · cloudflare-r2 · neon · redis-cache · render-deploy-ci.
- `docs/recipes/` — add-endpoint · add-service · add-model (cadascuna amb el patró nou `apps/<feature>/` i el legacy de Firestore).
- `docs/guides/` — passos per executar/configurar: local-setup · testing · firebase-credentials · r2-render-setup · admin-management · client-auth-usage · daily-visits-process · cloudflare-domain-csam (futur: domini + CSAM).
- `docs/design/` — patterns (detall dels patrons) · decisions (ADR: APIView, auth DRF+middleware, custom claims) · postgres-schema (disseny físic de la BD PostgreSQL/Neon de la migració).
- `docs/migration/` — PLAN · PROGRESS (estat dels chunks) · DECISIONS_AUTONOMES · EQUIP (rols dels agents) · documents d'arquitectura i UML de la migració Firestore → PostgreSQL.
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
