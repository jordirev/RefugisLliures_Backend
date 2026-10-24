# Arquitectura del backend

> Llegenda: **[FET]** comprovat al codi · **[INFERÈNCIA]** deducció · **[NO VERIFICAT]** depèn de config externa. Vegeu [README](README.md).

## 1. Stack

| Peça | Detall | Font |
|---|---|---|
| Framework | Django 5.1.12 + Django REST Framework 3.15.2 | `requirements.txt` |
| Base de dades del domini (encara) | **Cloud Firestore** via `firebase-admin` 6.5.0 (fins als chunks de la migració) | `api/services/firestore_service.py` |
| Base de dades relacional (migració) | **PostgreSQL 17 + PostGIS** (Neon) com a BD `default` de Django amb el rol `app` (`ATOMIC_REQUESTS`, subjecte a RLS) i l'àlies `migrator` (DDL); `psycopg[binary]` 3.2.9, GeoDjango | `refugis_lliures/settings.py` (`DATABASES`), [integrations/neon.md](integrations/neon.md) |
| Autenticació | Firebase Auth (ID tokens JWT) + custom claim `role` | `api/middleware/firebase_auth_middleware.py`, `api/permissions.py` |
| Media | Cloudflare R2 (API S3) via `boto3` | `api/r2_config.py`, `api/services/r2_media_service.py` |
| Cache | Redis via `django-redis` | `refugis_lliures/settings.py:183-202` |
| Docs API | `drf_yasg` → `/swagger/`, `/redoc/`, `/swagger.json` | `refugis_lliures/urls.py:45-47` |
| Servidor | gunicorn (1 worker sync, timeout 30 s) + whitenoise | `gunicorn.conf.py:12-19`, `refugis_lliures/settings.py:68` |
| Deploy | Render (`render.yaml`), CI a GitHub Actions | vegeu [integrations/render-deploy-ci.md](integrations/render-deploy-ci.md) |

**Migració Firestore → PostgreSQL en curs** ([migration/PLAN.md](migration/PLAN.md), [migration/PROGRESS.md](migration/PROGRESS.md)). Chunk 1 (infraestructura) i **chunk 2 (refugis)** fets: `default` és Postgres/PostGIS amb el rol `app` i `ATOMIC_REQUESTS=True`; `migrator` és l'àlies per a DDL (`python manage.py migrate --database=migrator`); `django.contrib.gis` sempre actiu → **el runtime necessita GDAL/GEOS** (pendent de desplegament, [TECH_DEBT.md](TECH_DEBT.md) P1) **[FET]**. **Els refugis (catàleg, serveis, enllaços i mitjans) ja viuen a PostgreSQL** a l'app `apps/refuges` (amb el mínim d'`apps/accounts` que necessita: `users` i `user_public_profiles`); la resta de models de `api/models/` continuen sent `@dataclass` persistits a Firestore, i els dominis que encara llegeixen un refugi (experiències, dubtes, visites, propostes, usuaris…) ho fan amb el `RefugiLliureDAO` legacy de Firestore fins que els migri el seu chunk **[FET]**. Postgres també el fan servir el health check i el hook de RLS **[FET]**. `api/admin.py` no registra cap model **[FET]**.

Si no hi ha cap URL de Postgres (`DATABASE_URL_APP` / `TEST_DATABASE_URL_APP`), `default` cau a SQLite (`db.sqlite3`), només perquè els tests sense BD puguin carregar la configuració **[FET]**.

## 2. Estructura de directoris

```
refugis_lliures/        settings.py, urls.py (arrel: admin/, api/, swagger/), wsgi/asgi
api/
  urls.py               totes les rutes /api/...
  views/                APIView per domini (+ cache_views.py amb @api_view)
  serializers/          validació d'entrada i format de sortida (Serializer, mai ModelSerializer)
  controllers/          lògica de negoci; retornen tuples
  daos/                 accés a Firestore + cache
  mappers/              dict Firestore <-> model
  models/               @dataclass amb validació a __post_init__
  services/             singletons: firestore_service, cache_service; R2MediaService, ConditionService
  middleware/           FirebaseAuthenticationMiddleware, HealthDatabaseErrorMiddleware (503 del health si Postgres cau)
  rls_hook.py           hook de RLS: set_config local a la transacció (uid, is_admin, is_system) per petició DRF
  authentication.py     FirebaseAuthentication (DRF)
  permissions.py        IsSameUser, IsFirebaseAdmin, Is*Creator...
  management/commands/  process_yesterday_visits, check_neon, comandes antigues de Firestore
  utils/                swagger_examples, swagger_error_responses, timezone_utils, ids.py (uuid7), JSON de dades
  tests/<domini>/       test_models/daos/mappers/serializers/controllers/views(/integration); els de les apps a apps/<feature>/tests/
apps/                   features migrades a PostgreSQL: una app Django per feature (estil HackSoft; substitueix `api/` feature a feature)
  core/                 nucli de la BD: rls.py (rls_context, system_context, helpers de polítiques RLS), migration_utils.py, testing.py, migracions core.0001/0002 (schemas, funcions core.*, grants)
  accounts/             models UserAccount i UserPublicProfile (mínim del chunk 2; la resta al chunk 3)
  refuges/              models, selectors (lectures), services (escriptures), serializers, views, urls, management/commands/load_refuges.py, migrations, tests/
scripts/                manage_admins.py (custom claims), verify_conditions.py, dev/setup_local_postgres.sh (Postgres local de proves)
docs/                   documentació (aquesta carpeta): flows, integrations, recipes, guides, design, deep-dives
env/                    .env.* i service accounts — NO versionat, NO llegir valors
```

## 3. Capes i contractes

### 3.1 Features migrades a PostgreSQL (patró nou: `apps/<feature>/`, referència: `apps/refuges`)

```
HTTP → FirebaseAuthenticationMiddleware → hook de RLS (set_config) → View (APIView) + permission_classes
     → Serializer (entrada) → selectors (lectures) / services (escriptures) → models (ORM + RLS) [+ R2MediaService]
```

| Capa | Contracte |
|---|---|
| **View** (`views.py`) | `APIView` fina: declara `permission_classes`, valida l'entrada amb el serializer, crida un *selector* o un *service*, tradueix les excepcions de domini a HTTP i serialitza. Sense accés directe a l'ORM. |
| **Selectors** (`selectors.py`) | Lectures (substitueixen el DAO): funcions que retornen models, llistes o `QuerySet`. Una consulta (o un `Prefetch`/`ArraySubquery`) per cas d'ús, cap N+1. Sense cache de dades. |
| **Services** (`services.py`) | Escriptures amb regles de negoci (substitueixen el controller): `transaction.atomic`, `select_for_update`, R2. Llancen excepcions de domini (`MediaForbidden`, `MediaNotFound`…), no tuples. |
| **Models** (`models.py`) | `django.db.models` amb `db_table = 'schema"."taula'`, FK `DO_NOTHING` + `db_constraint=False` (les cascades i la RLS són del DDL a la migració). |
| **Serializers** (`serializers.py`) | Contracte JSON (entrada i sortida); sense `ModelSerializer`. |
| **Migracions** | `RunSQL` amb `reverse_sql` per a FK reals, RLS, grants, triggers i vistes (`apps.core.migration_utils`). |

### 3.2 Features encara a Firestore (patró de referència: Renovations)

```
HTTP → FirebaseAuthenticationMiddleware → DRF (FirebaseAuthentication + permission_classes)
     → View (APIView) → Serializer (entrada) → Controller → DAO → (CacheService, Firestore, R2)
     ← View serialitza model.to_dict() amb XSerializer ← Controller retorna tupla
```

| Capa | Contracte | Exemple |
|---|---|---|
| **View** | Subclasse `APIView`; `permission_classes` o `get_permissions()` per mètode; `@swagger_auto_schema` amb constants de `api/utils/`. Valida amb `XCreateSerializer`/`XUpdateSerializer`, llegeix `request.user_uid`, crida el controller i tradueix la tupla a `Response`. | `api/views/renovation_views.py:49-170` |
| **Controller** | Classe amb DAOs instanciats a `__init__`. Cada mètode retorna `(success, data, error_msg)` o `(success, error_msg)`; captura qualsevol `Exception` i retorna `"Error intern: ..."`. Fa les comprovacions de propietat i de regles de negoci. | `api/controllers/renovation_controller.py:13-61` |
| **DAO** | `COLLECTION_NAME` (o `self.collection_name`), `FirestoreService().get_db()`, `cache_service` (get → miss → Firestore → set), invalida cache en escriure. Retorna model, `None`, `bool` o tuples segons el cas. | `api/daos/renovation_dao.py:15-109` |
| **Mapper** | Mètodes `@staticmethod` `firestore_to_model`, `model_to_firestore`, `*_list_*`. Normalment delega a `Model.from_dict/to_dict`. | `api/mappers/renovation_mapper.py` |
| **Model** | `@dataclass`; `__post_init__` llança `ValueError`; `to_dict()` / `from_dict()`. | `api/models/renovation.py:8-69` |
| **Serializer** | `serializers.Serializer` pla; mixins de validació compartida. Sortida: `XSerializer(model.to_dict())`. | `api/serializers/renovation_serializer.py:9-207` |

### Mapatge error → HTTP (convenció implícita) [FET]
El controller retorna un **missatge en text**; la vista tria el codi HTTP **buscant subcadenes** al missatge:
- `'solapa' in error.lower()` → 409 (`api/views/renovation_views.py:150`)
- `'not found' in error.lower()` → 404 (`api/views/doubt_views.py:240`)
- `'ja existeix'` → 409 a usuaris; `'no permès'` → 400 a avatar (vegeu [flows/01](flows/01-user-profile.md), [flows/02](flows/02-user-avatar.md)).

Conseqüència: **canviar el text d'un missatge pot canviar el codi HTTP retornat**. Els missatges barregen català i anglès ("no trobada" vs "not found") segons el domini.

## 4. Rutes (`api/urls.py`, prefix `/api/`)

| Ruta | Vista | Mètodes | Permisos efectius |
|---|---|---|---|
| `health/` | `HealthCheckAPIView` | GET | públic |
| `refuges/` | `apps.refuges.views.RefugeCollectionAPIView` | GET | públic (token opcional: `images_metadata`; `visitors` només admins) |
| `refuges/<id>/` | `apps.refuges.views.RefugeDetailAPIView` | GET | públic (id UUID; un altre format → 404) |
| `refuges/<id>/renovations/` | `RefugeRenovationsAPIView` | GET | IsAuthenticated |
| `refuges/<refuge_id>/visits/` | `RefugeVisitsAPIView` | GET | IsAuthenticated |
| `refuges/<refuge_id>/visits/<visit_date>/` | `RefugeVisitDetailAPIView` | POST, PATCH, DELETE | IsAuthenticated |
| `refuges/<id>/media/` | `apps.refuges.views.RefugeMediaListAPIView` | GET | IsAuthenticated |
| `refuges/<id>/media/<path:key>/` | `apps.refuges.views.RefugeMediaDetailAPIView` | DELETE | IsAuthenticated; propietat al service (autor o admin: 403; mitjà inexistent: 403 / 404 si admin; R2 falla: 500 i la fila es conserva) |
| `media/upload-intents/` | `UploadIntentsAPIView` | POST | IsAuthenticated + IsNotBlocked + IsAgeConfirmed (+ propietat d'experiència al controller) |
| `media/upload-intents/confirm/` | `UploadIntentsConfirmAPIView` | POST | IsAuthenticated + IsNotBlocked + IsAgeConfirmed |
| `media/reports/` | `MediaReportsAPIView` | POST | IsAuthenticated + IsNotBlocked + IsAgeConfirmed |
| `admin/media-reports/` | `AdminMediaReportsAPIView` | GET | IsAuthenticated + IsFirebaseAdmin |
| `admin/media-reports/<id>/` | `AdminMediaReportDetailAPIView` | PATCH | IsAuthenticated + IsFirebaseAdmin |
| `experiences/` | `ExperienceListAPIView` | GET, POST (només JSON) | GET: IsAuthenticated; POST: + IsNotBlocked |
| `experiences/<experience_id>/` | `ExperienceDetailAPIView` | PATCH, DELETE | IsAuthenticated + IsNotBlocked; propietat comprovada al controller (403 `not_owner`, admins permesos) |
| `doubts/` | `DoubtListAPIView` | GET, POST | IsAuthenticated |
| `doubts/<doubt_id>/` | `DoubtDetailAPIView` | DELETE | IsAuthenticated (*IsDoubtCreator no s'executa*) |
| `doubts/<doubt_id>/answers/` | `AnswerListAPIView` | POST | IsAuthenticated |
| `doubts/<doubt_id>/answers/<answer_id>/` | `AnswerReplyAPIView` | POST, DELETE | IsAuthenticated (*IsAnswerCreator no s'executa*) |
| `users/` | `UsersCollectionAPIView` | POST | IsAuthenticated |
| `users/<uid>/` | `UserDetailAPIView` | GET, PATCH, DELETE | GET: IsAuthenticated; PATCH/DELETE: + IsSameUser |
| `users/<uid>/avatar/` | `UserAvatarAPIView` | DELETE | IsAuthenticated + IsSameUser |
| `users/<uid>/age-confirmation/` | `UserAgeConfirmationAPIView` | PATCH | IsAuthenticated + IsSameUser |
| `users/<uid>/moderation-notices/` | `UserModerationNoticesAPIView` | GET | IsAuthenticated + IsSameUser |
| `users/<uid>/favorite-refuges/` (+ `<refuge_id>/`) | `UserFavouriteRefuges*APIView` | GET, POST / DELETE | IsAuthenticated + IsSameUser |
| `users/<uid>/visited-refuges/` (+ `<refuge_id>/`) | `UserVisitedRefuges*APIView` | GET, POST / DELETE | IsAuthenticated + IsSameUser |
| `users/<uid>/visits/` | `UserVisitsAPIView` | GET | IsAuthenticated + IsSameUser |
| `renovations/` | `RenovationListAPIView` | GET, POST | IsAuthenticated |
| `renovations/<id>/` | `RenovationAPIView` | GET, PATCH, DELETE | IsAuthenticated (propietat comprovada al controller) |
| `renovations/<id>/participants/` | `RenovationParticipantsAPIView` | POST | IsAuthenticated |
| `renovations/<id>/participants/<uid>/` | `RenovationParticipantDetailAPIView` | DELETE | IsAuthenticated (controller: creador o el mateix participant) |
| `refuges-proposals/` | `RefugeProposalCollectionAPIView` | POST / GET | POST: IsAuthenticated; GET: IsFirebaseAdmin |
| `my-refuges-proposals/` | `MyRefugeProposalCollectionAPIView` | GET | IsAuthenticated |
| `refuges-proposals/<id>/approve/` · `reject/` | `RefugeProposal{Approve,Reject}APIView` | POST | IsFirebaseAdmin |
| `cache/stats/` · `cache/clear/` · `cache/invalidate/` | `cache_stats`, `cache_clear`, `cache_invalidate` (`@api_view`) | GET / DELETE / DELETE | IsFirebaseAdmin |

Fora de `/api/`: `admin/` (Django admin), `swagger/`, `swagger.json|yaml`, `redoc/` (`refugis_lliures/urls.py:40-48`).

Notes de nomenclatura **[FET]**: URLs en anglès (`refuges`, `favorite-refuges` amb ortografia americana) però noms de vista `Favourite` (britànica) i dominis interns en català (`refugi_lliure`, `RefugiLliureDAO`, col·lecció `data_refugis_lliures`). Les proposals usen `refuges-proposals` (amb "s" a refuges).

## 5. Autenticació i autorització (resum)

Detall complet a [flows/00-auth-request-pipeline.md](flows/00-auth-request-pipeline.md) i [integrations/firebase-auth.md](integrations/firebase-auth.md).

1. `FirebaseAuthenticationMiddleware` (`refugis_lliures/settings.py:74`) verifica `Authorization: Bearer <idToken>` amb `auth.verify_id_token` i posa `request.user_uid`, `request.user_claims`, `request.firebase_user`, `request.user`. Rutes amb prefix `EXCLUDED_PATHS` (`/api/health/`, `/api/refuges/`, `/swagger/`, `/redoc/`) poden anar sense token (`api/middleware/firebase_auth_middleware.py:20-25`).
2. `FirebaseAuthentication` (DRF, `api/authentication.py`) reaprofita el que ha posat el middleware.
3. Permís per defecte: `AllowAny` (`refugis_lliures/settings.py:161-163`) — **cada vista ha de declarar els seus permisos**.
4. Admin = custom claim `role == 'admin'` (`api/permissions.py:10-21`). Es gestiona amb `scripts/manage_admins.py`.
5. Gestió d'admins: [guides/admin-management.md](guides/admin-management.md). Per què hi ha middleware **i** classe DRF: [design/decisions.md](design/decisions.md).
6. **[FET]** Permisos nous de la feature *images*: `IsNotBlocked` (403 `user_blocked`) i `IsAgeConfirmed` (403 `age_not_confirmed`), basats en `has_permission` i en `users/{uid}` (cache-first). Els errors amb codi tenen la forma `{error, code, message}` (`coded_error`, `api/permissions.py`). Detall: [flows/12-media-moderation.md](flows/12-media-moderation.md).
7. **[FET] Context de RLS per petició**: `api/rls_hook.py` (instal·lat a `ApiConfig.ready`) embolcalla `APIView.perform_authentication` i, després d'autenticar i abans de `check_permissions`, fixa amb **un sol** `set_config(..., true)` (local a la transacció d'`ATOMIC_REQUESTS`) `app.uid` (de l'usuari verificat), `app.is_admin` (només si el claim verificat `role == 'admin'`) i `app.is_system=false`, a totes les vistes DRF. Detall: [flows/00-auth-request-pipeline.md](flows/00-auth-request-pipeline.md).
8. **[FET] Firebase Auth Emulator**: amb `FIREBASE_AUTH_EMULATOR_HOST` Firebase Admin s'inicialitza sense credencials (`projectId` de `GCLOUD_PROJECT`/`GOOGLE_CLOUD_PROJECT` o `demo-refugis-lliures`); prohibit amb `RENDER`/`PRODUCTION` = `true` (Django no arrenca). Només per a e2e locals: [integrations/firebase-auth.md](integrations/firebase-auth.md).
9. **[FET]** Cap vista crida `check_object_permissions()`, i totes hereten d'`APIView` (no `GenericAPIView`) → **`has_object_permission` de `IsExperienceCreator`, `IsRenovationCreator`, `IsDoubtCreator`, `IsAnswerCreator`, `IsOwnerOrReadOnly` mai s'executa**. Només funcionen els permisos basats en `has_permission`: `IsSameUser`, `IsFirebaseAdmin`.

## 6. Cache (resum)

Redis amb `KEY_PREFIX='refugis'` i TTL per defecte 300 s (`refugis_lliures/settings.py:185-202`), però `CacheService` aplica els seus propis TTL (600 s gairebé tot, 3600 s coords) (`api/services/cache_service.py:20-48`). Claus `prefix:k1:v1:k2:v2` amb kwargs ordenats (`api/services/cache_service.py:63-85`). Patró **"ID caching"** per a llistes (`get_or_fetch_list`, `api/services/cache_service.py:208`). Errors de Redis s'empassen → fallback silenciós a Firestore. Detall: [integrations/redis-cache.md](integrations/redis-cache.md).

## 7. Patrons de disseny presents [FET]

Detall amb diagrames i motivació: [design/patterns.md](design/patterns.md).


| Patró | On |
|---|---|
| Singleton | `FirestoreService` (`api/services/firestore_service.py:13-22`), `CacheService` (`api/services/cache_service.py:14-53`) |
| DAO | `api/daos/*_dao.py` |
| Data Mapper | `api/mappers/*_mapper.py` |
| Cerca de refugis | una sola consulta SQL (`apps/refuges/selectors.py: search_queryset`), sense estratègies |
| Strategy (propostes) | `CreateRefugeStrategy`/`UpdateRefugeStrategy`/`DeleteRefugeStrategy` + `ProposalStrategySelector` (`api/daos/refuge_proposal_dao.py:231-570`) |
| Strategy (paths R2) | `RefugiMediaStrategy`, `UserAvatarStrategy` (`api/services/r2_media_service.py:44-145`) |
| Template method | `UserController._manage_refugi_list` (`api/controllers/user_controller.py:279-342`) |

## 8. Convencions

- **Idioma**: docstrings, comentaris i missatges d'error majoritàriament en **català**; alguns dominis (refugis, dubtes, propostes) retornen errors en **anglès** ("Refugi not found", "Proposal not found"). Identificadors en anglès excepte el domini refugi (`refugi`, `refugis_preferits`, `visitats`).
- **Dates**: zona `Europe/Madrid` via `api/utils/timezone_utils.py` (`get_madrid_now`, `get_madrid_today`). Es desen a Firestore com a **strings ISO** (`YYYY-MM-DD` per a dates; ISO datetime per a `created_at`, `modified_at`...). `settings.TIME_ZONE='UTC'` (`refugis_lliures/settings.py:135`) no s'usa per a la lògica de domini.
- **IDs**: auto-ID de Firestore (`collection().document()`) i es desa també dins el document com a camp `id` (p. ex. `api/daos/renovation_dao.py:52-54`). Excepció: `users/{uid}` usa l'UID de Firebase.
- **Logging**: nivells personalitzats `CACHE=21`, `FIRESTORE=22`, `DAO=23` (`refugis_lliures/settings.py:211-218`); els DAOs fan `logger.log(23, "Firestore READ: ...")`. El logger `api` en general només mostra `WARNING`+ (`refugis_lliures/settings.py:251-255`), així que **els `logger.info` dels controllers no surten** **[INFERÈNCIA]**.
- **Instanciació del controller**: renovations, users, proposals, visits la creen dins de cada mètode; `doubt_views.py` i `experience_views.py` la creen a `__init__` de la vista (`api/views/doubt_views.py:46`, `api/views/experience_views.py:34`). Les dues opcions són equivalents perquè DRF instancia la vista per petició **[INFERÈNCIA]**.
- **Serializers**: noms `XSerializer` (sortida), `XCreateSerializer`/`XUpdateSerializer` (entrada). Excepcions: `CreateDoubtSerializer`, `CreateAnswerSerializer`, `CreateRefugeVisitSerializer`, `UpdateRefugeVisitSerializer` (prefix en lloc de sufix) (`api/serializers/doubt_serializer.py:27-33`, `api/serializers/refuge_visit_serializer.py:86-95`).
- **Swagger**: exemples a `api/utils/swagger_examples.py`, respostes d'error com a `openapi.Response` a `api/utils/swagger_error_responses.py`.

## 9. Excepcions al patró [FET]

| Excepció | On |
|---|---|
| Vistes funció `@api_view` en lloc d'`APIView` | `api/views/cache_views.py:51-151` |
| Permisos que criden DAO/Controller | `api/permissions.py:141-146`, `185-190`, `316-324`, `365-373` (codi mort, vegeu §5) |
| DAO amb `self.collection_name` en lloc de `COLLECTION_NAME` | `api/daos/refugi_lliure_dao.py:18-19`, `api/daos/refuge_proposal_dao.py:579` |
| Lògica de negoci (strategies) dins el DAO | `api/daos/refuge_proposal_dao.py:231-570` (crida controllers d'altres dominis des del DAO) |
| Body d'error amb un objecte Swagger (`{'error': ERROR_500_INTERNAL_ERROR}`) | 14 ocurrències a `api/views/renovation_views.py`, 4 a `api/views/user_views.py`. `ERROR_500_INTERNAL_ERROR` és un `openapi.Response` (`api/utils/swagger_error_responses.py:316`). Com es serialitza a JSON: **[NO VERIFICAT]** |
| Errors 500 que exposen el text de l'excepció | `"Error intern: {str(e)}"` als controllers |
| DAO de llistes d'usuari que retorna tuples truthy com a "èxit" | `api/daos/user_dao.py:199,235,245,260` |
| Imports erronis de `logger` | `api/models/user.py:6` (`from venv import logger`), `api/models/experience.py:9` i `api/models/refugi_lliure.py:4` (`from asyncio.log import logger`) |

## 10. Tests

Guia pràctica (comandes, coverage, per què Firebase no s'inicialitza): [guides/testing.md](guides/testing.md).


- Config: `pytest.ini` (`DJANGO_SETTINGS_MODULE=refugis_lliures.settings`, `testpaths=api/tests apps`, `--strict-markers`, markers `unit, integration, views, serializers, controller(s), daos, mappers, models, edge_cases, slow, db_infra, rls, real_audit_log, real_permissions`).
- **Tests contra PostgreSQL (chunk 1)** [FET]: `TEST_DATABASE_URL_APP` / `TEST_DATABASE_URL_MIGRATOR` (Postgres local bootstrapat amb `scripts/dev/setup_local_postgres.sh`, o el servei `postgis/postgis:17-3.5` de CI) tenen prioritat sobre `DATABASE_URL_*`; `django_db_setup` (`api/tests/conftest.py`) migra amb `migrator` sobre la BD de proves sense crear `test_*`, i els tests corren com a `app` (RLS activa). La fixture `autouse` `_rls_hook_sense_bd` desactiva el hook als tests sense BD (sense markers `rls`/`django_db`/`db_infra`). Calen GDAL/GEOS; a Windows, contenidor Linux ([guides/testing.md](guides/testing.md)).
- `conftest.py` (arrel: també `django_db_setup`, `app_db`/`migrator_db`, bloqueig de Firestore i mocks d'audit/permisos, compartits amb `apps/*/tests`) i `api/tests/conftest.py` fixen `TESTING=true` i variables R2 falses **abans** d'importar res; amb `TESTING`/`pytest` carregat, Firebase **no s'inicialitza** (`api/firebase_config.py:15-17,92-94`).
- Mocks habituals: `patch('api.services.firestore_service.FirestoreService')`, `patch('api.services.cache_service.cache_service')` (`api/tests/conftest.py:266-286`); a les vistes es mocka el controller al mòdul de la vista, p. ex. `@patch('api.views.renovation_views.RenovationController')` (`api/tests/renovation/test_views.py:91`).
- Estructura per domini: `api/tests/<domini>/test_{models,mappers,daos,serializers,controllers,views}.py`; les features migrades tenen els tests a `apps/<feature>/tests/` (esquema, RLS, models, cerca, vistes de contracte contra Postgres, recomptes de consultes) (+ `test_integration.py` a refugi_lliure, renovation, user). Transversals: `api/tests/test_auth_middleware_permissions.py`, `api/tests/test_cache_views.py`, `api/tests/management_commands/`.
- Execució: `pytest`, `pytest api/tests/renovation`, `pytest -m views`, `tox` (`tox.ini`: `envlist=py39`, genera `coverage.xml`), `python run_tests.py`.
- Coverage (`.coveragerc`) **exclou `services/` i `utils/`** → `cache_service`, `r2_media_service`, `firestore_service` no compten al coverage.
- Fixtures probablement mortes **[INFERÈNCIA]**: `authenticated_client` fa patch de `api.permissions.IsAuthenticated`, que no existeix a `api/permissions.py` (`api/tests/conftest.py:323`); `mock_refugi_dao` fa patch de `RefugiLliureDao` però la classe és `RefugiLliureDAO` (`api/tests/conftest.py:398` vs `api/daos/refugi_lliure_dao.py:14`). Cap test sembla usar-les.

## 11. Gotchas / què NO fer
Llista completa: [GOTCHAS.md](GOTCHAS.md). Les més importants:
1. No confiïs en `has_object_permission`: comprova la propietat al controller.
2. No canviïs textos d'error sense revisar la vista que en depèn per triar l'HTTP status.
3. No facis read-modify-write d'arrays/maps sencers: usa `ArrayUnion`/`ArrayRemove`/`Increment` o transaccions.
4. Invalida la cache amb el prefix exacte de la clau (sense `:*` final).
5. Mantén la validació del serializer i del `__post_init__` del model alineades.

## 12. Deute tècnic detectat
Llista completa per severitat: [TECH_DEBT.md](TECH_DEBT.md). Resum: permisos d'objecte inoperants (crític), invalidació de cache de propostes trencada (crític), escriptures multi-document no atòmiques (`ATOMIC_REQUESTS` només cobreix Postgres), runtime sense GDAL/GEOS encara no desplegable (P1), claus R2 amb nom de fitxer del client, `delete_file` que amaga errors, configuració insegura per defecte (`DEBUG=True`, `ALLOWED_HOSTS='*'`, CORS obert).
