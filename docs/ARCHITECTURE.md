# Arquitectura del backend

> Llegenda: **[FET]** comprovat al codi · **[INFERÈNCIA]** deducció · **[NO VERIFICAT]** depèn de config externa. Vegeu [README](README.md).

## 1. Stack

| Peça | Detall | Font |
|---|---|---|
| Framework | Django 5.2.18 LTS + Django REST Framework 3.16.1, Python 3.14 | `requirements.txt`, `.python-version` |
| Base de dades del domini (encara) | **Cloud Firestore** via `firebase-admin` 6.5.0 (fins als chunks de la migració) | `api/services/firestore_service.py` |
| Base de dades relacional (migració) | **PostgreSQL 17 + PostGIS** (Neon) com a BD `default` de Django amb el rol `app` (`ATOMIC_REQUESTS`, subjecte a RLS) i l'àlies `migrator` (DDL); `psycopg[binary]` 3.2.9, GeoDjango | `refugis_lliures/settings.py` (`DATABASES`), [integrations/neon.md](integrations/neon.md) |
| Autenticació | Firebase Auth (ID tokens JWT) + custom claim `role` | `api/middleware/firebase_auth_middleware.py`, `api/permissions.py` |
| Media | Cloudflare R2 (API S3) via `boto3` | `api/r2_config.py`, `api/services/r2_media_service.py` |
| Cache | Redis via `django-redis` | `refugis_lliures/settings.py:183-202` |
| Docs API | `drf_yasg` → `/swagger/`, `/redoc/`, `/swagger.json` | `refugis_lliures/urls.py:45-47` |
| Servidor | gunicorn (1 worker sync, timeout 30 s) + whitenoise | `gunicorn.conf.py:12-19`, `refugis_lliures/settings.py:68` |
| Deploy | Render (`render.yaml`), CI a GitHub Actions | vegeu [integrations/render-deploy-ci.md](integrations/render-deploy-ci.md) |

**Migració Firestore → PostgreSQL en curs** ([migration/PLAN.md](migration/PLAN.md), [migration/PROGRESS.md](migration/PROGRESS.md)). Chunk 1 (infraestructura), **chunk 2 (refugis)**, **chunk 3 (usuaris)**, **chunk 4 (visites)**, **chunk 5 (reformes)**, **chunk 6 (dubtes i respostes)**, **chunk 7 (experiències i pujades)** i **chunk 8 (propostes de refugi)** fets: `default` és Postgres/PostGIS amb el rol `app` i `ATOMIC_REQUESTS=True`; `migrator` és l'àlies per a DDL (`python manage.py migrate --database=migrator`); `django.contrib.gis` sempre actiu → **el runtime necessita GDAL/GEOS** (pendent de desplegament, [TECH_DEBT.md](TECH_DEBT.md) P1) **[FET]**. **Els refugis (catàleg, serveis, enllaços i mitjans) ja viuen a PostgreSQL** a l'app `apps/refuges`; **els usuaris (`users`, perfil públic, avatar, preferits, visitats, moderació d'usuari) ja viuen a PostgreSQL** a `apps/accounts` (chunk 3; `api/models/user.py`, `UserDAO`, `UserController`, `UserMapper` i `user_serializer` s'han eliminat). **Les visites (`activity.refuge_visits`, `refuge_visit_participants` i la vista `refuge_visit_totals`) ja viuen a PostgreSQL** a `apps/visits` (chunk 4; `RefugeVisitController`, `RefugeVisitDAO`, mapper, model i serializer legacy eliminats; el job diari és `apps/visits/management/commands/process_yesterday_visits`). **Les reformes (`activity.renovations`, enllaç del grup, participants i expulsats) ja viuen a PostgreSQL** a `apps/renovations` (chunk 5; les vistes i el serializer de `api/` s'han eliminat; el codi legacy de Firestore s'ha eliminat al chunk 8, [TECH_DEBT R15](TECH_DEBT.md)). **Els dubtes i respostes (`activity.doubts`, `activity.answers`) ja viuen a PostgreSQL** a `apps/doubts` (chunk 6; el codi legacy `DoubtController`/`DoubtDAO` s'ha eliminat al chunk 8, [TECH_DEBT D1](TECH_DEBT.md)). **Les experiències (`activity.experiences`, amb la mitjana de condició del refugi mantinguda per un *trigger*) i les pujades de mitjans (`moderation.upload_intents`; el mitjà publicat va a `refuges.refuge_media`, també amb `experience_id`, o a `users.user_avatars`) ja viuen a PostgreSQL** a `apps/experiences` i `apps/uploads` (chunk 7; `ExperienceController`/`ExperienceDAO`/model/mapper, `MediaUploadController`, `UploadIntentDAO` i `IsExperienceCreator` a les vistes han desaparegut; `purge_upload_intents` és el job horari d'intents, [TECH_DEBT R18](TECH_DEBT.md)). **Les propostes de refugi (`proposals.refuge_proposals`) ja viuen a PostgreSQL** a `apps/proposals` (chunk 8: `jsonb` amb `payload` i `refuge_snapshot`, FK `SET NULL`, RLS; aprovar és **una transacció** amb `SELECT … FOR UPDATE` de la proposta que escriu el catàleg `refuges`/`refuge_amenities`/`refuge_links`, que el rol `app` només pot escriure sota RLS com a admin o sistema; `RefugeProposalController`/`DAO`/estratègies, `DoubtController`/`DAO`, `RenovationController`/`DAO`, `ConditionService` i `IsRenovationCreator` s'han eliminat). La resta de models de `api/models/` continuen sent `@dataclass` persistits a Firestore (moderació: denúncies, avisos i hash-blocklist, auditoria), i només la **moderació** (`MediaReportController`) i el **health check** conserven el `RefugiLliureDAO`/`RefugiLliureController` legacy de Firestore ([TECH_DEBT R1, R5](TECH_DEBT.md)) **[FET]**. Estat intermedi (D19–D22, D38): el perfil propi ja compta experiències i reformes per SQL i l'esborrat d'usuari ja no executa cap pas de Firestore (`_firestore_steps` buida; [TECH_DEBT U2](TECH_DEBT.md)) **[FET]**. Postgres també el fan servir el health check i el hook de RLS **[FET]**. `api/admin.py` no registra cap model **[FET]**.

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
  permissions.py        HasProfile, IsNotBlocked, IsAgeConfirmed (lectura de `users.users`), IsSameUser, IsFirebaseAdmin, Is*Creator...
  management/commands/  check_neon (les comandes antigues de refugis s'han eliminat al chunk 2)
  utils/                swagger_examples, swagger_error_responses, timezone_utils, JSON de dades (els UUID v7 els genera la BD: `uuidv7()`)
  tests/<domini>/       test_models/daos/mappers/serializers/controllers/views(/integration); els de les apps a apps/<feature>/tests/
apps/                   features migrades a PostgreSQL: una app Django per feature (estil HackSoft; substitueix `api/` feature a feature)
  core/                 nucli de la BD: errors.py (`server_error`: 500 amb `error_id`), rls.py (rls_context, system_context, helpers de polítiques RLS), db_functions.py (`TransactionNow`), migration_utils.py, testing.py, migracions core.0001/0002 (schemas, funcions core.*, grants)
  accounts/             usuaris (chunk 3): models (UserAccount, UserPublicProfile, UserAvatar, Language, FavouriteRefuge, VisitedRefuge), selectors, services, serializers, views, urls (`users/`), migracions 0001–0002, tests/
  refuges/              models, selectors (lectures), services (escriptures), serializers, views, urls, management/commands/load_refuges.py, migrations, tests/
  experiences/          experiències (chunk 7): models (Experience), selectors, services, serializers, views, urls (`experiences/`), migració 0001 (FK, RLS, trigger de condició), tests/
  proposals/            propostes de refugi (chunk 8): models (RefugeProposal), selectors (llistes), services (crear amb duplicats, aprovar/rebutjar en transacció, esborrat amb R2), serializers (payload validat), views, urls (`refuges-proposals/`, `my-refuges-proposals/`), migració 0001 (CHECK `jsonb`, FK `SET NULL`, RLS, escriptura del catàleg per a admin/sistema), tests/
  uploads/              pujada directa de mitjans (chunk 7): models (UploadIntent), services (intents, confirmació, `process_and_publish`, purga), serializers, views (rutes a `api/urls.py`), management/commands/purge_upload_intents.py, migració 0001, tests/
scripts/                manage_admins.py (custom claims), dev/setup_local_postgres.sh (Postgres local de proves)
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
| **View** (`views.py`) | `APIView` fina: declara `permission_classes`, valida l'entrada amb el serializer, crida un *selector* o un *service*, tradueix les excepcions de domini a HTTP i serialitza. Sense accés directe a l'ORM. Errors 500: `apps.core.errors.server_error(missatge específic, exc)` → `{error, error_id}` (mateix `error_id` al log amb la traça; mai el text de l'excepció). |
| **Selectors** (`selectors.py`) | Lectures (substitueixen el DAO): funcions que retornen models, llistes o `QuerySet`. Una consulta (o un `Prefetch`/`ArraySubquery`) per cas d'ús, cap N+1. Sense cache de dades. |
| **Services** (`services.py`) | Escriptures amb regles de negoci (substitueixen el controller): `transaction.atomic`, `select_for_update`, R2. Llancen excepcions de domini (`MediaForbidden`, `MediaNotFound`…), no tuples. |
| **Models** (`models.py`) | `django.db.models` amb `db_table = 'schema"."taula'`, FK `DO_NOTHING` + `db_constraint=False` (les cascades i la RLS són del DDL a la migració). |
| **Serializers** (`serializers.py`) | Contracte JSON (entrada i sortida); sense `ModelSerializer`. |
| **Migracions** | `RunSQL` amb `reverse_sql` per a FK reals, RLS, grants, triggers i vistes (`apps.core.migration_utils`). |

### 3.2 Features encara a Firestore (legacy; moderació i health check; el patró s'exemplifica amb el codi que queda a `api/`)

```
HTTP → FirebaseAuthenticationMiddleware → DRF (FirebaseAuthentication + permission_classes)
     → View (APIView) → Serializer (entrada) → Controller → DAO → (CacheService, Firestore, R2)
     ← View serialitza model.to_dict() amb XSerializer ← Controller retorna tupla
```

| Capa | Contracte | Exemple |
|---|---|---|
| **View** | Subclasse `APIView`; `permission_classes` o `get_permissions()` per mètode; `@swagger_auto_schema` amb constants de `api/utils/`. Valida amb `XCreateSerializer`/`XUpdateSerializer`, llegeix `request.user_uid`, crida el controller i tradueix la tupla a `Response`. | `api/views/media_views.py` |
| **Controller** | Classe amb DAOs instanciats a `__init__`. Cada mètode retorna `(success, data, error_msg)` o `(success, error_msg)`; captura qualsevol `Exception` i retorna `"Error intern: ..."`. Fa les comprovacions de propietat i de regles de negoci. | `api/controllers/media_report_controller.py` |
| **DAO** | `COLLECTION_NAME` (o `self.collection_name`), `FirestoreService().get_db()`, `cache_service` (get → miss → Firestore → set), invalida cache en escriure. Retorna model, `None`, `bool` o tuples segons el cas. | `api/daos/refugi_lliure_dao.py:15-109` |
| **Mapper** | Mètodes `@staticmethod` `firestore_to_model`, `model_to_firestore`, `*_list_*`. Normalment delega a `Model.from_dict/to_dict`. | `api/mappers/refugi_lliure_mapper.py` |
| **Model** | `@dataclass`; `__post_init__` llança `ValueError`; `to_dict()` / `from_dict()`. | `api/models/refugi_lliure.py` |
| **Serializer** | `serializers.Serializer` pla; mixins de validació compartida. Sortida: `XSerializer(model.to_dict())`. | `api/serializers/refugi_lliure_serializer.py` |

### Mapatge error → HTTP (convenció implícita) [FET]
El controller retorna un **missatge en text**; la vista tria el codi HTTP **buscant subcadenes** al missatge:
- `'not found' in error.lower()` → 404 (ja no aplica als dubtes: són a `apps/doubts`, amb excepcions de domini)
(Usuaris i avatar ja no ho fan: són a `apps/accounts`, amb excepcions de domini; vegeu [flows/01](flows/01-user-profile.md), [flows/02](flows/02-user-avatar.md).)

Conseqüència: **canviar el text d'un missatge pot canviar el codi HTTP retornat**. Els missatges barregen català i anglès ("no trobada" vs "not found") segons el domini.

## 4. Rutes (`api/urls.py`, prefix `/api/`)

| Ruta | Vista | Mètodes | Permisos efectius |
|---|---|---|---|
| `health/` | `HealthCheckAPIView` | GET | públic |
| `refuges/` | `apps.refuges.views.RefugeCollectionAPIView` | GET | públic (token opcional: `images_metadata`; `visitors` només admins) |
| `refuges/<id>/` | `apps.refuges.views.RefugeDetailAPIView` | GET | públic (id UUID; un altre format → 404) |
| `refuges/<id>/renovations/` | `apps.renovations.views.RefugeRenovationsAPIView` | GET | IsAuthenticated + HasProfile; `?active_only=true` o `1` només vigents (D32); refugi inexistent o id no UUID → 404 |
| `refuges/<refuge_id>/visits/` | `apps.visits.views.RefugeVisitsAPIView` | GET | IsAuthenticated + HasProfile |
| `refuges/<refuge_id>/visits/<visit_date>/` | `apps.visits.views.RefugeVisitDetailAPIView` | POST, PATCH, DELETE | IsAuthenticated + HasProfile; POST/PATCH a més IsNotBlocked + IsAgeConfirmed |
| `refuges/<id>/media/` | `apps.refuges.views.RefugeMediaListAPIView` | GET | IsAuthenticated + HasProfile |
| `refuges/<id>/media/<path:key>/` | `apps.refuges.views.RefugeMediaDetailAPIView` | DELETE | IsAuthenticated + HasProfile; propietat al service (autor o admin: 403; mitjà inexistent: 403 / 404 si admin; R2 falla: 500 i la fila es conserva) |
| `media/upload-intents/` | `apps.uploads.views.UploadIntentsAPIView` | POST | IsAuthenticated + HasProfile + IsNotBlocked + IsAgeConfirmed (+ propietat d'experiència al service: 403 `not_owner`; quota de 40 intents pendents: 429 `too_many_pending_uploads`) |
| `media/upload-intents/confirm/` | `apps.uploads.views.UploadIntentsConfirmAPIView` | POST | IsAuthenticated + HasProfile + IsNotBlocked + IsAgeConfirmed |
| `media/reports/` | `MediaReportsAPIView` | POST | IsAuthenticated + HasProfile + IsNotBlocked + IsAgeConfirmed |
| `admin/media-reports/` | `AdminMediaReportsAPIView` | GET | IsAuthenticated + HasProfile + IsFirebaseAdmin |
| `admin/media-reports/<id>/` | `AdminMediaReportDetailAPIView` | PATCH | IsAuthenticated + HasProfile + IsFirebaseAdmin |
| `experiences/` | `apps.experiences.views.ExperienceListAPIView` | GET, POST (només JSON) | IsAuthenticated + HasProfile; POST: + IsNotBlocked + IsAgeConfirmed |
| `experiences/<experience_id>/` | `apps.experiences.views.ExperienceDetailAPIView` | PATCH, DELETE | IsAuthenticated + HasProfile; PATCH: + IsNotBlocked + IsAgeConfirmed (DELETE no, D38); propietat al service (creador o admin; si no, 403 `not_owner`); id inexistent o no UUID → 404; R2 falla en DELETE → 500 i es conserva |
| `doubts/` | `apps.doubts.views.DoubtListAPIView` | GET, POST | IsAuthenticated + HasProfile; POST: + IsNotBlocked + IsAgeConfirmed |
| `doubts/<doubt_id>/` | `apps.doubts.views.DoubtDetailAPIView` | DELETE | IsAuthenticated + HasProfile; propietat al service (creador o admin; si no, 403 `not_owner`) |
| `doubts/<doubt_id>/answers/` | `apps.doubts.views.AnswerListAPIView` | POST | IsAuthenticated + HasProfile + IsNotBlocked + IsAgeConfirmed |
| `doubts/<doubt_id>/answers/<answer_id>/` | `apps.doubts.views.AnswerReplyAPIView` | POST, DELETE | POST: + IsNotBlocked + IsAgeConfirmed; DELETE: propietat al service (creador de la resposta o admin: 403 `not_owner`; esborra el subarbre) |
| `users/` | `apps.accounts.views.UsersCollectionAPIView` | POST | IsAuthenticated (**sense** `HasProfile`: crea el perfil) |
| `users/<uid>/` | `apps.accounts.views.UserDetailAPIView` | GET, PATCH, DELETE | IsAuthenticated + HasProfile; PATCH/DELETE: + IsSameUser. GET d'un altre: només `{uid, username, avatar_metadata}` |
| `users/<uid>/avatar/` | `apps.accounts.views.UserAvatarAPIView` | DELETE | IsAuthenticated + HasProfile + IsSameUser |
| `users/<uid>/age-confirmation/` | `apps.accounts.views.UserAgeConfirmationAPIView` | PATCH | IsAuthenticated + HasProfile + IsSameUser |
| `users/<uid>/moderation-notices/` | `UserModerationNoticesAPIView` (`api/views/user_views.py`, Firestore) | GET | IsAuthenticated + HasProfile + IsSameUser |
| `users/<uid>/favorite-refuges/` (+ `<refuge_id>/`) | `apps.accounts.views.UserFavouriteRefuges*APIView` | GET, POST / DELETE | IsAuthenticated + HasProfile + IsSameUser |
| `users/<uid>/visited-refuges/` (+ `<refuge_id>/`) | `apps.accounts.views.UserVisitedRefuges*APIView` | GET, POST / DELETE | IsAuthenticated + HasProfile + IsSameUser |
| `users/<uid>/visits/` | `apps.visits.views.UserVisitsAPIView` | GET | IsAuthenticated + HasProfile + IsSameUser |
| `renovations/` | `apps.renovations.views.RenovationListAPIView` | GET (vigents), POST | IsAuthenticated + HasProfile; POST: + IsNotBlocked + IsAgeConfirmed (D35) |
| `renovations/<id>/` | `apps.renovations.views.RenovationAPIView` | GET, PATCH, DELETE | IsAuthenticated + HasProfile; PATCH: + IsNotBlocked + IsAgeConfirmed; PATCH/DELETE només el creador (service + RLS; un admin tampoc: 403) |
| `renovations/<id>/participants/` | `apps.renovations.views.RenovationParticipantsAPIView` | POST | IsAuthenticated + HasProfile + IsNotBlocked + IsAgeConfirmed (unir-se; creador: 400; expulsat: 403; ja participant: 409) |
| `renovations/<id>/participants/<uid>/` | `apps.renovations.views.RenovationParticipantDetailAPIView` | DELETE | IsAuthenticated + HasProfile; service: el propi participant (surt) o el creador (expulsa) |
| `refuges-proposals/` | `apps.proposals.views.ProposalCollectionAPIView` | POST / GET | IsAuthenticated + HasProfile; POST: + IsNotBlocked + IsAgeConfirmed (409 `possible_duplicates`); GET: + IsFirebaseAdmin |
| `my-refuges-proposals/` | `apps.proposals.views.MyProposalCollectionAPIView` | GET | IsAuthenticated + HasProfile (un admin hi veu només les seves) |
| `refuges-proposals/<id>/approve/` · `reject/` | `apps.proposals.views.Proposal{Approve,Reject}APIView` | POST | IsAuthenticated + HasProfile + IsFirebaseAdmin (un admin pot aprovar la seva; aprovar pot donar 409 per proposta ja revisada o enllaç d'un altre refugi) |
| `cache/stats/` · `cache/clear/` · `cache/invalidate/` | `cache_stats`, `cache_clear`, `cache_invalidate` (`@api_view`) | GET / DELETE / DELETE | IsFirebaseAdmin (**sense** `HasProfile`) |

Fora de `/api/`: `admin/` (Django admin), `swagger/`, `swagger.json|yaml`, `redoc/` (`refugis_lliures/urls.py:40-48`).

**`HasProfile`** [FET]: tot endpoint autenticat llevat de `POST /users/` i `/api/cache/*` exigeix fila a `users.users` (403 `profile_required`); el rep abans d'`IsNotBlocked`/`IsAgeConfirmed`. Els admins també necessiten perfil (`scripts/manage_admins.py add` el crea).

Notes de nomenclatura **[FET]**: URLs en anglès (`refuges`, `favorite-refuges` amb ortografia americana) però noms de vista `Favourite` (britànica) i dominis interns en català (`refugi_lliure`, `RefugiLliureDAO`, col·lecció `data_refugis_lliures`). Les proposals usen `refuges-proposals` (amb "s" a refuges).

## 5. Autenticació i autorització (resum)

Detall complet a [flows/00-auth-request-pipeline.md](flows/00-auth-request-pipeline.md) i [integrations/firebase-auth.md](integrations/firebase-auth.md).

1. `FirebaseAuthenticationMiddleware` (`refugis_lliures/settings.py:74`) verifica `Authorization: Bearer <idToken>` amb `auth.verify_id_token` i posa `request.user_uid`, `request.user_claims`, `request.firebase_user`, `request.user`. Rutes amb prefix `EXCLUDED_PATHS` (`/api/health/`, `/api/refuges/`, `/swagger/`, `/redoc/`) poden anar sense token (`api/middleware/firebase_auth_middleware.py:20-25`).
2. `FirebaseAuthentication` (DRF, `api/authentication.py`) reaprofita el que ha posat el middleware.
3. Permís per defecte: `AllowAny` (`refugis_lliures/settings.py:161-163`) — **cada vista ha de declarar els seus permisos**.
4. Admin = custom claim `role == 'admin'` (`api/permissions.py:10-21`). Es gestiona amb `scripts/manage_admins.py`.
5. Gestió d'admins: [guides/admin-management.md](guides/admin-management.md). Per què hi ha middleware **i** classe DRF: [design/decisions.md](design/decisions.md).
6. **[FET]** Permisos basats en `users.users` (PostgreSQL, chunk 3): `HasProfile` (403 `profile_required`), `IsNotBlocked` (403 `user_blocked`) i `IsAgeConfirmed` (403 `age_not_confirmed`), tots a `has_permission`. Llegeixen la fila amb `selectors.get_user` **una sola vegada per petició** (cau a `request._account_cache`, sense Redis; la RLS limita la lectura a la pròpia fila). Un bloqueig té efecte immediat (cap cache de 10 min). Els errors amb codi tenen la forma `{error, code, message}` (`coded_error`, `api/permissions.py`). Detall: [flows/12-media-moderation.md](flows/12-media-moderation.md).
7. **[FET] Context de RLS per petició**: `api/rls_hook.py` (instal·lat a `ApiConfig.ready`) embolcalla `APIView.perform_authentication` i, després d'autenticar i abans de `check_permissions`, fixa amb **un sol** `set_config(..., true)` (local a la transacció d'`ATOMIC_REQUESTS`) `app.uid` (de l'usuari verificat), `app.is_admin` (només si el claim verificat `role == 'admin'`) i `app.is_system=false`, a totes les vistes DRF. Detall: [flows/00-auth-request-pipeline.md](flows/00-auth-request-pipeline.md).
8. **[FET] Firebase Auth Emulator**: amb `FIREBASE_AUTH_EMULATOR_HOST` Firebase Admin s'inicialitza sense credencials (`projectId` de `GCLOUD_PROJECT`/`GOOGLE_CLOUD_PROJECT` o `demo-refugis-lliures`); prohibit amb `RENDER`/`PRODUCTION` = `true` (Django no arrenca). Només per a e2e locals: [integrations/firebase-auth.md](integrations/firebase-auth.md).
9. **[FET]** Cap vista crida `check_object_permissions()`, i totes hereten d'`APIView` (no `GenericAPIView`) → **`has_object_permission` d'`IsOwnerOrReadOnly` mai s'executa** (`IsRenovationCreator` s'ha eliminat al chunk 8; reformes comprova la propietat al service) (`IsDoubtCreator` i `IsAnswerCreator` s'han eliminat al chunk 6 i `IsExperienceCreator` al chunk 7: dubtes, respostes i experiències comproven la propietat al service). Només funcionen els permisos basats en `has_permission`: `HasProfile`, `IsNotBlocked`, `IsAgeConfirmed`, `IsSameUser`, `IsFirebaseAdmin`.

## 6. Cache (resum)

Redis amb `KEY_PREFIX='refugis'` i TTL per defecte 300 s (`refugis_lliures/settings.py:185-202`), però `CacheService` aplica els seus propis TTL (600 s gairebé tot, 3600 s coords) (`api/services/cache_service.py:20-48`). Claus `prefix:k1:v1:k2:v2` amb kwargs ordenats (`api/services/cache_service.py:63-85`). Patró **"ID caching"** per a llistes (`get_or_fetch_list`, `api/services/cache_service.py:208`). Errors de Redis s'empassen → fallback silenciós a Firestore. **Les features migrades a PostgreSQL (refugis, usuaris) no usen cache de dades**: els prefixos `refugi_search` i `refugi_coords` ja no els escriu ningú (només els invalida el DAO de propostes), `refugi_detail` només el fa servir el `RefugiLliureDAO` legacy, i `user_detail`/`user_refugis_info` han desaparegut. Detall: [integrations/redis-cache.md](integrations/redis-cache.md).

## 7. Patrons de disseny presents [FET]

Detall amb diagrames i motivació: [design/patterns.md](design/patterns.md).


| Patró | On |
|---|---|
| Singleton | `FirestoreService` (`api/services/firestore_service.py:13-22`), `CacheService` (`api/services/cache_service.py:14-53`) |
| DAO | `api/daos/*_dao.py` |
| Data Mapper | `api/mappers/*_mapper.py` |
| Cerca de refugis | una sola consulta SQL (`apps/refuges/selectors.py: search_queryset`), sense estratègies |
| Aprovació de propostes | `apps/proposals/services.py: approve_proposal`: una transacció amb bloqueig `FOR UPDATE` i `_apply_create/_apply_update/_apply_delete` (les estratègies de Firestore han desaparegut al chunk 8) |
| Strategy (paths R2) | `RefugiMediaStrategy`, `UserAvatarStrategy` (`api/services/r2_media_service.py:44-145`) |
| Llistes d'usuari (preferits/visitats) | `_UserRefugeList` abstracta amb PK composta + funcions `_add`/`_remove` compartides (`apps/accounts/models.py`, `services.py`); el Template method d'`UserController` ha desaparegut |

## 8. Convencions

- **Idioma**: docstrings, comentaris i missatges d'error majoritàriament en **català**; alguns dominis (refugis, dubtes, propostes, ja a PostgreSQL) retornen errors en **anglès** ("Refugi not found", "Proposal not found"). Identificadors en anglès excepte el domini refugi (`refugi`, `refugis_preferits`, `visitats`).
- **Dates**: `settings.TIME_ZONE = 'Europe/Madrid'` i `USE_TZ = True` (decisió del PO, 26/10) **[FET]**. Els instants es desen com a `timestamptz` (UTC) amb el **rellotge de la BD** (`db_default=Now()`, `Now()` als `UPDATE`; l'aplicació no envia `timezone.now()` per a aquestes columnes) i l'API els emet en ISO amb el desplaçament de Madrid (`isoformat_madrid`). Les dates de negoci (`visit_date`, `ini_date`, `fin_date`, `modified_at` del refugi) les calcula l'aplicació amb `get_madrid_today()` (= `timezone.localdate()`); `__date`/`Trunc*` de l'ORM ja converteixen a Madrid. La sessió de Postgres de Django continua en UTC (Django la hi força), de manera que el SQL no pot calcular «avui» (`CURRENT_DATE`): ho vigila `apps/core/tests/test_timezone.py`. Neon és en `GMT` i el Docker local/CI en `Etc/UTC`, cosa que no afecta res perquè cap consulta en depèn. Els dominis encara a Firestore desen strings ISO amb el desplaçament de Madrid (`get_madrid_now().isoformat()`).
- **IDs**: auto-ID de Firestore (`collection().document()`) i es desa també dins el document com a camp `id` (p. ex. `api/daos/refugi_lliure_dao.py`). Excepció: `users/{uid}` usa l'UID de Firebase.
- **Logging**: nivells personalitzats `CACHE=21`, `FIRESTORE=22`, `DAO=23` (`refugis_lliures/settings.py:211-218`); els DAOs fan `logger.log(23, "Firestore READ: ...")`. El logger `api` en general només mostra `WARNING`+ (`refugis_lliures/settings.py:251-255`), així que **els `logger.info` dels controllers no surten** **[INFERÈNCIA]**.
- **Instanciació del controller** (només la moderació, encara a Firestore): el crea dins de cada mètode. Les vistes de les apps migrades no tenen controller: criden `selectors`/`services` com a funcions de mòdul.
- **Serializers**: noms `XSerializer` (sortida), `XCreateSerializer`/`XUpdateSerializer` (entrada). Excepcions: `CreateDoubtSerializer`, `CreateAnswerSerializer`, `CreateRefugeVisitSerializer`, `UpdateRefugeVisitSerializer` (prefix en lloc de sufix) (`apps/doubts/serializers.py`, `apps/visits/serializers.py`).
- **Swagger**: exemples a `api/utils/swagger_examples.py`, respostes d'error com a `openapi.Response` a `api/utils/swagger_error_responses.py`.

## 9. Excepcions al patró [FET]

| Excepció | On |
|---|---|
| Vistes funció `@api_view` en lloc d'`APIView` | `api/views/cache_views.py:51-151` |
| Permisos que criden DAO/Controller | `HasProfile`/`IsNotBlocked`/`IsAgeConfirmed` criden un selector d'`apps.accounts` (`get_user_for_permissions`), no un DAO |
| DAO amb `self.collection_name` en lloc de `COLLECTION_NAME` | `api/daos/refugi_lliure_dao.py:19` |
| Body d'error amb un objecte Swagger (`{'error': ERROR_500_INTERNAL_ERROR}`) | ocurrències als models antics (`api/views/`). `ERROR_500_INTERNAL_ERROR` és un `openapi.Response` (`api/utils/swagger_error_responses.py:316`). Com es serialitza a JSON: **[NO VERIFICAT]** |
| Errors 500 que exposen el text de l'excepció | `"Error intern: {str(e)}"` als controllers (les features migrades usen `apps.core.errors.server_error`: missatge específic + `error_id`, sense text d'excepció) |
| Imports erronis de `logger` | resolt als models (B7); `api/models/experience.py` ja no existeix |

## 10. Tests

Guia pràctica (comandes, coverage, per què Firebase no s'inicialitza): [guides/testing.md](guides/testing.md).


- Config: `pytest.ini` (`DJANGO_SETTINGS_MODULE=refugis_lliures.settings`, `testpaths=api/tests apps`, `--strict-markers`, markers `unit, integration, views, serializers, controller(s), daos, mappers, models, edge_cases, slow, db_infra, rls, real_audit_log, real_permissions`).
- **Tests contra PostgreSQL (chunk 1)** [FET]: `TEST_DATABASE_URL_APP` / `TEST_DATABASE_URL_MIGRATOR` (Postgres local bootstrapat amb `scripts/dev/setup_local_postgres.sh`, o el servei `postgis/postgis:18-3.6` de CI) tenen prioritat sobre `DATABASE_URL_*` dins pytest (o amb `USE_TEST_DATABASE=1`; fora, s'ignoren: D37); `django_db_setup` (`api/tests/conftest.py`) migra amb `migrator` sobre la BD de proves sense crear `test_*`, i els tests corren com a `app` (RLS activa). La fixture `autouse` `_rls_hook_sense_bd` desactiva el hook als tests sense BD (sense markers `rls`/`django_db`/`db_infra`). Calen GDAL/GEOS; a Windows, contenidor Linux ([guides/testing.md](guides/testing.md)).
- `conftest.py` (arrel: també `django_db_setup`, `app_db`/`migrator_db`, bloqueig de Firestore, mocks d'audit/permisos (`get_user_for_permissions` retorna un `UserAccount` confirmat i no bloquejat) i `_restore_view_policies`, que restaura `permission_classes`/`authentication_classes` de totes les vistes després de cada test; compartits amb `apps/*/tests`) i `api/tests/conftest.py` fixen `TESTING=true` i variables R2 falses **abans** d'importar res; amb `TESTING`/`pytest` carregat, Firebase **no s'inicialitza** (`api/firebase_config.py:15-17,92-94`).
- Mocks habituals: `patch('api.services.firestore_service.FirestoreService')`, `patch('api.services.cache_service.cache_service')` (`api/tests/conftest.py:266-286`); a les vistes es mocka el controller al mòdul de la vista, p. ex. `@patch('api.views.media_views.MediaReportController')` (patró dels tests antics; les apps migrades ja no el segueixen: `apps/renovations/tests/` va contra Postgres amb el rol `app`).
- Estructura per domini: `api/tests/<domini>/test_{models,mappers,daos,serializers,controllers,views}.py` (el domini `user` s'ha migrat: `api/tests/user/` només conserva `test_age_and_moderation.py`); les features migrades tenen els tests a `apps/<feature>/tests/` (esquema, RLS, models, cerca, vistes de contracte contra Postgres, recomptes de consultes; `apps/accounts/tests/`, `apps/visits/tests/`, `apps/renovations/tests/`, `apps/doubts/tests/`, `apps/experiences/tests/` i `apps/uploads/tests/` en són més exemples (`apps/experiences/tests/` hi afegeix el trigger de condició, la concurrència i l'esborrat d'usuari; `apps/uploads/tests/`, la comanda de purga i la confirmació d'intents): esquema, constraints, RLS, serializers, selectors i services, vistes de contracte, recomptes de consultes, errors 500 i permisos d'escriptura) (+ `test_integration.py` a refugi_lliure). Transversals: `api/tests/test_auth_middleware_permissions.py`, `api/tests/test_cache_views.py`, `api/tests/management_commands/` (buit des del chunk 4: la comanda és a `apps/visits`). `api/tests/refugi_lliure/` conserva només els tests del codi legacy que encara viu a `api/` (DAO/controller/mapper/models de refugi i el health check).
- Execució: `pytest`, `pytest apps/renovations`, `pytest -m views`, `tox` (`tox.ini`: `envlist=py314`, genera `coverage.xml`), `python run_tests.py`.
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
Llista completa per severitat: [TECH_DEBT.md](TECH_DEBT.md). Resum: permisos d'objecte inoperants (crític; parcialment resolt), escriptures multi-document no atòmiques (`ATOMIC_REQUESTS` només cobreix Postgres), runtime sense GDAL/GEOS encara no desplegable (P1), claus R2 amb nom de fitxer del client, `delete_file` que amaga errors, configuració insegura per defecte (`DEBUG=True`, `ALLOWED_HOSTS='*'`, CORS obert).
