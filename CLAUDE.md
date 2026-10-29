# CLAUDE.md — RefugisLliures Backend

API REST (Django 5.2 LTS + DRF, Python 3.14) de l'app Refugis Lliures: refugis de muntanya, fotos, experiències, dubtes, visites, reformes ("renovations") i propostes de canvi revisades per admins.
Documentació detallada a [`docs/`](docs/README.md). Llegenda als docs: **[FET]** / **[INFERÈNCIA]** / **[NO VERIFICAT]**.

## Stack
- **PostgreSQL + PostGIS (Neon)** és la BD `default` de Django (rol `app`, `ATOMIC_REQUESTS`, RLS; àlies `migrator` per a DDL) des del chunk 1 de la migració; **requereix GDAL/GEOS** (`django.contrib.gis` sempre actiu). Sense URL de Postgres, `default` cau a SQLite (només per a tests sense BD).
- **Refugis (chunk 2), usuaris (chunk 3), visites (chunk 4), reformes (chunk 5), dubtes i respostes (chunk 6), experiències i pujades (chunk 7), propostes (chunk 8) i moderació + auditoria (chunk 9) ja són a PostgreSQL** (`apps/refuges`, `apps/accounts`: usuari, perfil públic, avatar, preferits, visitats, moderació d'usuari; `apps/visits`: visites, participants i job diari; `apps/renovations`: reformes, enllaç del grup, participants i expulsats; `apps/doubts`: dubtes i respostes; `apps/experiences`: experiències amb la mitjana de condició del refugi per *trigger*; `apps/uploads`: intents de pujada, confirmació i purga, el mitjà publicat va a `refuges.refuge_media`/`users.user_avatars`; `apps/proposals`: propostes de refugi, aprovar = una transacció que escriu el catàleg; `apps/moderation`: denúncies, avisos, llista de hashes (`fn_hash_match`), retenció CSAM; `apps/audit`: `AuditLogService` a `audit.audit_logs`); **Firestore ja no s'usa enlloc** (chunk 11, D43: fora `RefugiLliureDAO`/`Controller`/`Mapper`, `firestore_service` i les rutes `/api/cache/*`); `firebase-admin` es queda només per a Firebase Auth; els comptadors del perfil propi són SQL i l'esborrat d'usuari (chunk 10) és un procediment únic: una transacció (bloqueig `FOR UPDATE`, R2 dins, `DELETE`, auditoria) i Firebase Auth després del `COMMIT` (vista `non_atomic_requests`).
- **Firebase Auth** (única dependència de Firebase; `firebase-admin` només per a Auth i `scripts/manage_admins.py`): ID token `Bearer` verificat al middleware; admin = custom claim `role == 'admin'`. Un hook (`apps/core/rls_hook.py`) fixa el context de RLS (`app.uid`, `app.is_admin`) a la transacció de cada petició. Per a e2e locals, `FIREBASE_AUTH_EMULATOR_HOST` (mai en producció).
- **Cloudflare R2** (boto3) per a media; bucket privat, URLs presignades d'1 h.
- **Sense Redis ni cache de dades** (D43): `CACHES` és un `LocMemCache` per defecte (Django en necessita un) i l'aplicació no hi desa res.
- Deploy a **Render** (gunicorn, 1 worker); CI, ping i procés diari a **GitHub Actions**.

## Comandes
```bash
py -3.14 -m venv .venv && .venv\Scripts\activate   # Windows; Python 3.14 també a CI i producció
pip install -r requirements.txt
python manage.py runserver            # requereix env/ local + Postgres (DATABASE_URL_APP) + GDAL; R2_* només per als endpoints de media
python manage.py migrate --database=migrator   # SEMPRE amb el rol migrator (app no té DDL)
python manage.py check_neon --alias default    # (o migrator) comprova Postgres/PostGIS
python manage.py load_refuges [--dry-run]      # UNA sola vegada: càrrega del catàleg de refugis (1.542) amb el rol migrator; error si ja hi ha refugis
pytest                                # tots els tests (apps/*/tests); els de BD volen TEST_DATABASE_URL_APP/MIGRATOR (scripts/dev/setup_local_postgres.sh); a Windows, en un contenidor Linux amb GDAL (docs/guides/testing.md)
pytest apps/core apps/auth apps/health -q   # infra compartida: RLS/BD, autenticació i health
pytest apps/refuges -q                # una app migrada (també apps/accounts, apps/visits, apps/renovations, apps/doubts, apps/experiences, apps/uploads, apps/proposals, apps/moderation, apps/audit)
pytest apps/experiences apps/uploads -q   # chunk 7 (Postgres real, rol app)
pytest -m views                       # per marker (pytest.ini, --strict-markers)
tox                                   # com a CI: pytest + coverage.xml
python manage.py process_yesterday_visits   # apps/visits: visites d'ahir -> user_visited_refuges + purga >12 mesos; CommandError (codi != 0) si falla (D28)
python manage.py purge_upload_intents      # apps/uploads: esborra els intents de pujada caducats en lots de 1.000; horària; CommandError si falla; NO està planificada a cap workflow (TECH_DEBT R18)
python manage.py purge_audit_logs / purge_moderation   # chunk 9: retenció (audit 365 d / 5 anys legal_hold; denúncies i avisos 24 mesos / 5 anys); CommandError si falla; NO planificades (TECH_DEBT R18)
python manage.py load_hash_blocklist <fitxer.csv>     # chunk 9: llista de hashes CSAM (rol migrator, idempotent, tot o res)
python scripts/manage_admins.py <add|remove|check|list> [uid]
```
Swagger: `/swagger/`, `/redoc/`. Totes les rutes de l'API sota `/api/` (`refugis_lliures/urls.py`).

## Capes
**Totes les features són apps de PostgreSQL** (una app Django per feature a `apps/`, estil HackSoft; referència: `apps/refuges`):
```
View (APIView) → Serializer → selectors (lectures) / services (escriptures) → models (ORM + RLS) [+ R2MediaService]
apps/<feature>/{views, serializers, selectors, services, models, urls, migrations, management/commands, tests}
```
- **View**: fina; declara `permission_classes` (el default global és `AllowAny`!; tot endpoint autenticat porta `IsAuthenticated, HasProfile, …`, llevat de `POST /users/`), valida amb el serializer, crida un selector o un service i mapa les excepcions de domini a HTTP. El context de RLS el posa el hook.
- **Errors 500 amb traçabilitat** (política del PO per a les features migrades): la resposta és `{"error": "<missatge específic del punt que ha fallat>", "error_id": "<uuid>"}` i el mateix `error_id` es desa al log amb la traça completa (`logger.exception`). **Mai** es retorna `str(e)` ni el nom/text de l'excepció (pot dur SQL, hosts, bucket, claus o rutes). Ho fa el helper `apps.core.errors.server_error(message, exc, logger=logger)`; el missatge és un text fix per punt ("Error en esborrar el fitxer a R2", "Error de base de dades en cercar refugis", "Error en generar la URL de la imatge"…).
- **selectors.py**: lectures; una consulta per cas d'ús (`select_related`/`Prefetch`/`ArraySubquery`), filtres al `WHERE`, **sense cache**. Els tests comproven el nombre de consultes.
- **services.py**: escriptures; `transaction.atomic`, `select_for_update` si cal, R2; llancen excepcions de domini (no tuples). Aquí van les **comprovacions de propietat** (a més de la RLS).
- **models.py + migracions**: `db_table = 'schema"."taula'`, FK `DO_NOTHING` + `db_constraint=False` i la restricció real (`ON DELETE`), la RLS, els grants i els triggers per `RunSQL` a la mateixa migració (`apps.core.migration_utils`). Les rutes de la feature estan a `apps/<feature>/urls.py` i s'inclouen des de `refugis_lliures/urls.py`.

**Infraestructura compartida** (la carpeta `api/` ja no existeix; el PO en va ordenar l'eliminació, substitueix D43(4)): `apps/auth/` (label `firebase_auth`: `authentication.py`, `permissions.py`, `middleware.py` —`FirebaseAuthenticationMiddleware`—, `firebase_config.py`; `ready()` inicialitza Firebase Admin), `apps/core/` (`rls.py`, `rls_hook.py` instal·lat a `CoreConfig.ready()`, `timezone_utils.py`, `age_utils.py`, `swagger/{examples,error_responses}.py`, comanda `check_neon`), `apps/health/` (`GET /api/health/`: PostgreSQL + Firebase Admin inicialitzat; `{status, message, firebase, database}`, 200/503; middleware 503 `HealthDatabaseErrorMiddleware`), `apps/uploads/` (`r2_config.py`, `r2_media_service.py`, `image_processing_service.py`, `media_metadata.py`, `media_serializer.py`) i `apps/moderation/moderation_service.py`. Les rutes de l'API (prefix `/api/`) s'inclouen des de `refugis_lliures/urls.py` (cada app té el seu `urls.py`).

## Convencions
- Català a docstrings, comentaris i la majoria de missatges; identificadors en anglès.
- Dates: `TIME_ZONE = 'Europe/Madrid'` (decisió del PO, 26/10): «avui» amb `get_madrid_today()`/`timezone.localdate()`, mai `CURRENT_DATE`/`now()::date` al SQL (la sessió de Postgres és UTC; test de guarda `apps/core/tests/test_timezone.py`). Instants `timestamptz` amb el rellotge de la BD (`Now()`/`db_default`); durades (TTL d'auditoria, caducitat d'intents) **a la BD**, amb `now()`/`TransactionNow()` + interval (GOTCHAS #60–62). L'API emet ISO amb desplaçament de Madrid.
- IDs: a les apps migrades, UUID v7 generat per la BD (`DEFAULT uuidv7()`, Postgres 18; `db_default` als models) exposat com a string opac; l'usuari usa l'UID de Firebase.
- Logs: nivells estàndard de `logging` (els nivells propis CACHE/FIRESTORE/DAO han desaparegut amb la neteja).
- Swagger: exemples a `apps/core/swagger/examples.py`, errors a `apps/core/swagger/error_responses.py`.
- Tests: els de cada feature a `apps/<feature>/tests/` (contra Postgres real amb el rol `app`: esquema, RLS, models, cerca, contracte HTTP, recomptes de consultes); els d'infra compartida a `apps/{core,auth,health}/tests/` (RLS, rol `app`, settings, autenticació/permisos, Firebase, health) i els de media a `apps/uploads/tests/`; les fixtures compartides són al `conftest.py` de l'arrel (`_block_real_firebase`: cap test inicialitza Firebase Admin real).

## Top gotchas (llista completa: docs/GOTCHAS.md)
1. `has_object_permission` **mai s'executa** (cap `check_object_permissions`): `Is*Creator` no protegeix res. Comprova la propietat al service (`IsExperienceCreator` ja no existeix).
2. El middleware exclou per prefix `/api/refuges/` (també media/visits/renovations): la protecció depèn només de `permission_classes`.
3. Serializer, model i `CHECK` de la BD han d'aplicar les mateixes regles (cas `ini_date <= fin_date` a reformes: un dia és vàlid).
4. Cap `default=` en serializers d'update (el bug del PATCH d'usuari que reseteja `language` es va corregir al chunk 3).
5. `R2MediaService.delete_file` retorna `False`, no llança: comprova el booleà. Tota pujada (única via: upload-intents + `confirm`) ha de passar per `apps.uploads.services.process_and_publish` (neteja EXIF, tipus real, claus UUID); no facis `put_object` de bytes de l'usuari directament.
6. Variables `R2_*` es llegeixen amb `os.getenv`; `decouple` no omple `os.environ` → exporta-les a l'entorn.
7. Canviar el text d'un error pot canviar el codi HTTP.
8. El context de RLS (`set_config(..., true)`) és local a la transacció i només el posa el hook a peticions HTTP; en comandes/jobs usa `rls_context()`/`system_context()`. Migracions sempre `--database=migrator`. `ATOMIC_REQUESTS` no desfà escriptures a R2.
9. Els tests de vistes muten `view.cls.permission_classes`; usa `patch.object` (el `conftest.py` de l'arrel restaura `permission_classes`/`authentication_classes` de totes les vistes després de cada test: `_restore_view_policies`). El mateix `conftest.py` bloqueja Firebase Admin real (`_block_real_firebase`) i mocka `apps.audit.services.AuditLogService.log` i `get_user_for_permissions` (markers `real_audit_log`, `real_permissions` per desactivar-ho).
10. A les apps migrades les FK són `DO_NOTHING` + `db_constraint=False`: les cascades i `SET NULL` són del DDL (migració `RunSQL`), no de Django; no depenguis de `on_delete` ni de signals. `load_refuges` és d'un sol ús (sense `--overwrite`). `bulk_create` no recupera els PK de `db_default` (`uuidv7()`): demana'ls abans a la BD (GOTCHAS #48).
11. Errors 500 a les apps migrades: sempre `server_error(...)` (`{error, error_id}`), mai `str(e)`.
12. **`HasProfile`** (403 `profile_required`) va just després d'`IsAuthenticated` a tot endpoint autenticat (excepte `POST /users/`) i **abans** d'`IsNotBlocked`/`IsAgeConfirmed`: un usuari sense fila rep `profile_required`, mai `age_not_confirmed`. Una vista nova autenticada l'ha d'incloure. Els permisos llegeixen `users.users` **una sola vegada per petició** (cau a `request`).
13. Les llistes d'usuari tenen **PK composta**: `obj.pk` és una tupla `(user_id, refuge_id)` i no hi ha `obj.id` (GOTCHAS #52). Moderació d'usuari (strikes/bloqueig) i avatar des d'altres dominis s'escriuen a PostgreSQL amb `system_context()` (`fn_users_guard` ho exigeix, D20).
14. **Visites (chunk 4)**: el total surt de la vista `refuge_visit_totals`, mai d'un `Sum` sota RLS (GOTCHAS #63); la data és estrictament `YYYY-MM-DD` (#64); POST/PATCH exigeixen `IsNotBlocked` + `IsAgeConfirmed`, DELETE no; el job ha de sortir amb codi != 0 si falla (#65).
15. **Reformes (GOTCHAS #66–68)**: `renovations_requires_link` és un *constraint trigger* diferit (l'error surt al `COMMIT`: reforma i enllaç, a la mateixa transacció); `group_link` és un `LEFT JOIN` sota RLS (la clau s'omet a qui no hi té dret; mai `INNER JOIN`); els errors de domini es tradueixen per `constraint_name`, mai pel text.
16. **Experiències i pujades (chunk 7, GOTCHAS #71–75)**: la mitjana de condició del refugi la fa un *trigger* (`SECURITY DEFINER`); l'app mai la calcula i esborrar una experiència no la toca; esborrar-ne una llegeix les claus d'R2 amb `system_context()` i desfà tot si R2 falla; les FK són diferides (`SET CONSTRAINTS ALL IMMEDIATE` en un savepoint per fer-ne un 404/`processing_error`); `purge_upload_intents` encara no està planificada.
17. **Propostes (chunk 8, GOTCHAS #76–82)**: aprovar és una sola transacció (`select_for_update` + `WHERE status='pending'`; R2 dins en un `delete`); el rol `app` escriu el catàleg sota RLS (`{ADM} OR {SYS}`): un no-admin rep **0 files**, no error; crear `create` pot donar 409 `possible_duplicates` (≤ 500 m i nom semblant) i aprovar 409 per enllaç ja usat (`LinkAlreadyUsed`); el `jsonb` d'un cursor cru surt com a `str`; editar `proposals.0001` exigeix `migrate proposals zero` a les BD de test persistents; esborrar l'usuari anul·la el `comment`.
18. **Moderació i auditoria (chunk 9, GOTCHAS #83–86)**: denunciar és un `system_context()` curt amb el mitjà `FOR UPDATE`; `resolve_report` porta el seu `transaction.atomic()` i en CSAM copia a `moderation-hold/<clau>` *abans* d'esborrar (R2 falla = tot es desfà); `AuditLogService.log` mai llança; la llista de hashes és il·legible per a `app` (només `fn_hash_match`, càrrega amb `load_hash_blocklist`); esborrar usuari/refugi desvincula les files `legal_hold` amb triggers `SECURITY DEFINER` conservant `details`.
19. **Esborrat d'usuari (chunk 10, GOTCHAS #87–92)**: `DELETE /users/{uid}/` és `non_atomic_requests` (el `dispatch` embolcalla GET/PATCH en `atomic`); `delete_user` = UNA transacció amb `FOR UPDATE` de la fila + R2 dins (si falla, tot desfet) i Firebase Auth **després del COMMIT**; idempotent (sense `HasProfile`: sense fila → Firebase → 204); sense `media_deletion_queue`; el DELETE no passa pel hook de RLS (`skip_rls_hook`); `DELETE` d'usuari reintenta fins a 2 cops si Postgres tria la transacció com a víctima d'un deadlock.

## Seguretat
- **No llegeixis ni imprimeixis** fitxers de `env/` (service accounts, `.env.*`, `api-keys.env`). No estan versionats; només se'n poden esmentar els noms de variables.
- No posis credencials reals a `run_process_visits.sh` / `run_process_visits.bat`.
- Defaults inseguros a `refugis_lliures/settings.py` (`DEBUG=True`, `ALLOWED_HOSTS='*'`, CORS obert): en producció depenen de Render.

## Índex de docs
- `docs/ARCHITECTURE.md` — stack, capes, taula de rutes i permisos, auth, health check, convencions, excepcions, tests.
- `docs/GOTCHAS.md` — què NO fer · `docs/TECH_DEBT.md` — bugs i deute per severitat.
- `docs/flows/` — 00 auth · 01 perfil · 02 avatar · 03 fotos refugi · 04 cerca/detall · 05 propostes · 06 visites · 07 renovations · 08 experiències · 09 dubtes · 10 preferits/visitats · 11 health check · 12 denúncies/moderació/edat/auditoria.
- `docs/integrations/` — firebase-auth · cloudflare-r2 · neon · render-deploy-ci (`firestore` i `redis-cache` eliminats: només història a `docs/migration/`).
- `docs/recipes/` — add-endpoint · add-service · add-model (patró `apps/<feature>/`).
- `docs/guides/` — passos per executar/configurar: local-setup · testing · firebase-credentials · r2-render-setup · admin-management · client-auth-usage · daily-visits-process · hash-blocklist (`load_hash_blocklist` + purgues) · cloudflare-domain-csam (futur: domini + CSAM).
- `docs/design/` — patterns (detall dels patrons) · decisions (ADR: APIView, auth DRF+middleware, custom claims) · postgres-schema (disseny físic de la BD PostgreSQL/Neon de la migració).
- `docs/migration/` — PLAN · PROGRESS (estat dels chunks) · DECISIONS_AUTONOMES · EQUIP (rols dels agents) · documents d'arquitectura i UML de la migració Firestore → PostgreSQL.
- `docs/deep-dives/` — condition-average · refuge-proposals-payload · user-deletion (enllaçats des dels fluxos pare).

## En canviar codi
**Regla general: `docs/` s'actualitza en el mateix canvi que el codi.** Abans de donar una tasca per acabada, revisa aquesta taula i edita els docs afectats (mantén la llegenda **[FET]** / **[INFERÈNCIA]** / **[NO VERIFICAT]**; si verifiques una inferència, passa-la a [FET]).

| Canvi al codi | Docs a actualitzar |
|---|---|
| Endpoint nou/modificat/eliminat (ruta, mètode, permisos, payload, codis HTTP) | `docs/recipes/add-endpoint.md` (guia); `docs/ARCHITECTURE.md §4` (taula de rutes i permisos); el flux afectat a `docs/flows/` |
| Model, serializer o regla de validació nova/canviada | El flux afectat; `docs/recipes/add-model.md` si canvia el patró; `docs/deep-dives/` relacionat (ex. `refuge-proposals-payload`, `condition-average`) |
| Servei nou o canvi als serveis de media (`apps/uploads/r2_media_service.py`, imatge) o a `apps/moderation/moderation_service.py` | `docs/recipes/add-service.md` si canvia el patró; l'`docs/integrations/` corresponent |
| Canvi a middleware, autenticació, permisos o claims | `docs/flows/00-auth-request-pipeline.md`, `docs/integrations/firebase-auth.md`, `docs/ARCHITECTURE.md §5`, `docs/guides/client-auth-usage.md`, i ADR a `docs/design/decisions.md` si és una decisió d'arquitectura |
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
