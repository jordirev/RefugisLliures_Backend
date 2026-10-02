# Arquitectura del backend

> Llegenda: **[FET]** comprovat al codi · **[INFERÈNCIA]** deducció · **[NO VERIFICAT]** depèn de config externa. Vegeu [README](README.md).

## 1. Stack

| Peça | Detall | Font |
|---|---|---|
| Framework | Django 5.1.12 + Django REST Framework 3.15.2 | `requirements.txt` |
| Base de dades real | **Cloud Firestore** via `firebase-admin` 6.5.0 | `api/services/firestore_service.py` |
| Autenticació | Firebase Auth (ID tokens JWT) + custom claim `role` | `api/middleware/firebase_auth_middleware.py`, `api/permissions.py` |
| Media | Cloudflare R2 (API S3) via `boto3` | `api/r2_config.py`, `api/services/r2_media_service.py` |
| Cache | Redis via `django-redis` | `refugis_lliures/settings.py:183-202` |
| Docs API | `drf_yasg` → `/swagger/`, `/redoc/`, `/swagger.json` | `refugis_lliures/urls.py:45-47` |
| Servidor | gunicorn (1 worker sync, timeout 30 s) + whitenoise | `gunicorn.conf.py:12-19`, `refugis_lliures/settings.py:68` |
| Deploy | Render (`render.yaml`), CI a GitHub Actions | vegeu [integrations/render-deploy-ci.md](integrations/render-deploy-ci.md) |

**SQLite** (`db.sqlite3`, `refugis_lliures/settings.py:103-108`) està configurat però **cap model de domini és un model Django**: tots els models de `api/models/` són `@dataclass` i es persisteixen a Firestore **[FET]**. SQLite només serveix per a les apps internes de Django (admin, sessions) **[INFERÈNCIA]**. `api/admin.py` no registra cap model **[FET]**.

## 2. Estructura de directoris

```
refugis_lliures/        settings.py, urls.py (arrel: admin/, api/, swagger/), wsgi/asgi
api/
  urls.py               totes les rutes /api/...
  views/                APIView per domini (+ cache_views.py amb @api_view)
  serializers/          validació d'entrada i format de sortida (Serializer, mai ModelSerializer)
  controllers/          lògica de negoci; retornen tuples
  daos/                 accés a Firestore + cache; search_strategies.py (Strategy)
  mappers/              dict Firestore <-> model
  models/               @dataclass amb validació a __post_init__
  services/             singletons: firestore_service, cache_service; R2MediaService, ConditionService
  middleware/           FirebaseAuthenticationMiddleware
  authentication.py     FirebaseAuthentication (DRF)
  permissions.py        IsSameUser, IsFirebaseAdmin, IsMediaUploader, Is*Creator...
  management/commands/  seeding, condicions, process_yesterday_visits
  utils/                swagger_examples, swagger_error_responses, timezone_utils, JSON de dades
  tests/<domini>/       test_models/daos/mappers/serializers/controllers/views(/integration)
scripts/                manage_admins.py (custom claims), verify_conditions.py
DOCUMENTATION/          docs antigues (vegeu docs/README.md)
env/                    .env.* i service accounts — NO versionat, NO llegir valors
```

## 3. Capes i contractes (patró de referència: Renovations)

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
| `refuges/` | `RefugiLliureCollectionAPIView` | GET | públic (token opcional enriqueix resposta) |
| `refuges/<id>/` | `RefugiLliureDetailAPIView` | GET | públic |
| `refuges/<id>/renovations/` | `RefugeRenovationsAPIView` | GET | IsAuthenticated |
| `refuges/<refuge_id>/visits/` | `RefugeVisitsAPIView` | GET | IsAuthenticated |
| `refuges/<refuge_id>/visits/<visit_date>/` | `RefugeVisitDetailAPIView` | POST, PATCH, DELETE | IsAuthenticated |
| `refuges/<id>/media/` | `RefugiMediaAPIView` | GET, POST | IsAuthenticated |
| `refuges/<id>/media/<path:key>/` | `RefugiMediaDeleteAPIView` | DELETE | IsAuthenticated + IsMediaUploader |
| `experiences/` | `ExperienceListAPIView` | GET, POST | IsAuthenticated |
| `experiences/<experience_id>/` | `ExperienceDetailAPIView` | PATCH, DELETE | IsAuthenticated (*IsExperienceCreator no s'executa*) |
| `doubts/` | `DoubtListAPIView` | GET, POST | IsAuthenticated |
| `doubts/<doubt_id>/` | `DoubtDetailAPIView` | DELETE | IsAuthenticated (*IsDoubtCreator no s'executa*) |
| `doubts/<doubt_id>/answers/` | `AnswerListAPIView` | POST | IsAuthenticated |
| `doubts/<doubt_id>/answers/<answer_id>/` | `AnswerReplyAPIView` | POST, DELETE | IsAuthenticated (*IsAnswerCreator no s'executa*) |
| `users/` | `UsersCollectionAPIView` | POST | IsAuthenticated |
| `users/<uid>/` | `UserDetailAPIView` | GET, PATCH, DELETE | GET: IsAuthenticated; PATCH/DELETE: + IsSameUser |
| `users/<uid>/avatar/` | `UserAvatarAPIView` | PATCH, DELETE | IsAuthenticated + IsSameUser |
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
5. **[FET]** Cap vista crida `check_object_permissions()`, i totes hereten d'`APIView` (no `GenericAPIView`) → **`has_object_permission` de `IsExperienceCreator`, `IsRenovationCreator`, `IsDoubtCreator`, `IsAnswerCreator`, `IsOwnerOrReadOnly` mai s'executa**. Només funcionen els permisos basats en `has_permission`: `IsSameUser`, `IsFirebaseAdmin`, `IsMediaUploader`.

## 6. Cache (resum)

Redis amb `KEY_PREFIX='refugis'` i TTL per defecte 300 s (`refugis_lliures/settings.py:185-202`), però `CacheService` aplica els seus propis TTL (600 s gairebé tot, 3600 s coords) (`api/services/cache_service.py:20-48`). Claus `prefix:k1:v1:k2:v2` amb kwargs ordenats (`api/services/cache_service.py:63-85`). Patró **"ID caching"** per a llistes (`get_or_fetch_list`, `api/services/cache_service.py:208`). Errors de Redis s'empassen → fallback silenciós a Firestore. Detall: [integrations/redis-cache.md](integrations/redis-cache.md).

## 7. Patrons de disseny presents [FET]

| Patró | On |
|---|---|
| Singleton | `FirestoreService` (`api/services/firestore_service.py:13-22`), `CacheService` (`api/services/cache_service.py:14-53`) |
| DAO | `api/daos/*_dao.py` |
| Data Mapper | `api/mappers/*_mapper.py` |
| Strategy (cerca) | 15 estratègies + `SearchStrategySelector` (`api/daos/search_strategies.py:42-583`) |
| Strategy (propostes) | `CreateRefugeStrategy`/`UpdateRefugeStrategy`/`DeleteRefugeStrategy` + `ProposalStrategySelector` (`api/daos/refuge_proposal_dao.py:231-570`) |
| Strategy (paths R2) | `RefugiMediaStrategy`, `UserAvatarStrategy` (`api/services/r2_media_service.py:44-145`) |
| Template method | `UserController._manage_refugi_list` (`api/controllers/user_controller.py:279-342`) |

## 8. Convencions

- **Idioma**: docstrings, comentaris i missatges d'error majoritàriament en **català**; alguns dominis (refugis, dubtes, propostes) retornen errors en **anglès** ("Refugi not found", "Proposal not found"). Identificadors en anglès excepte el domini refugi (`refugi`, `refugis_preferits`, `visitats`).
- **Dates**: zona `Europe/Madrid` via `api/utils/timezone_utils.py` (`get_madrid_now`, `get_madrid_today`). Es desen a Firestore com a **strings ISO** (`YYYY-MM-DD` per a dates; ISO datetime per a `created_at`, `modified_at`...). `settings.TIME_ZONE='UTC'` (`refugis_lliures/settings.py:135`) no s'usa per a la lògica de domini.
- **IDs**: auto-ID de Firestore (`collection().document()`) i es desa també dins el document com a camp `id` (p. ex. `api/daos/renovation_dao.py:52-54`). Excepció: `users/{uid}` usa l'UID de Firebase.
- **Logging**: nivells personalitzats `CACHE=21`, `FIRESTORE=22`, `DAO=23` (`refugis_lliures/settings.py:211-218`); els DAOs fan `logger.log(23, "Firestore READ: ...")`. El logger `api` en general només mostra `WARNING`+ (`refugis_lliures/settings.py:251-255`), així que **els `logger.info` dels controllers no surten** **[INFERÈNCIA]**.
- **Instanciació del controller**: renovations, users, proposals, visits la creen dins de cada mètode; `doubt_views.py`, `experience_views.py`, `refugi_media_views.py` la creen a `__init__` de la vista (`api/views/doubt_views.py:46`, `api/views/experience_views.py:34`, `api/views/refugi_media_views.py:38`). Les dues opcions són equivalents perquè DRF instancia la vista per petició **[INFERÈNCIA]**.
- **Serializers**: noms `XSerializer` (sortida), `XCreateSerializer`/`XUpdateSerializer` (entrada). Excepcions: `CreateDoubtSerializer`, `CreateAnswerSerializer`, `CreateRefugeVisitSerializer`, `UpdateRefugeVisitSerializer` (prefix en lloc de sufix) (`api/serializers/doubt_serializer.py:27-33`, `api/serializers/refuge_visit_serializer.py:86-95`).
- **Swagger**: exemples a `api/utils/swagger_examples.py`, respostes d'error com a `openapi.Response` a `api/utils/swagger_error_responses.py`.

## 9. Excepcions al patró [FET]

| Excepció | On |
|---|---|
| Vistes funció `@api_view` en lloc d'`APIView` | `api/views/cache_views.py:51-151` |
| Permís que accedeix directament a Firestore (salta DAO i cache) | `IsMediaUploader`, `api/permissions.py:247-276` |
| Permisos que criden DAO/Controller | `api/permissions.py:141-146`, `185-190`, `316-324`, `365-373` (codi mort, vegeu §5) |
| DAO amb `self.collection_name` en lloc de `COLLECTION_NAME` | `api/daos/refugi_lliure_dao.py:18-19`, `api/daos/refuge_proposal_dao.py:579` |
| Lògica de negoci (strategies) dins el DAO | `api/daos/refuge_proposal_dao.py:231-570` (crida controllers d'altres dominis des del DAO) |
| Body d'error amb un objecte Swagger (`{'error': ERROR_500_INTERNAL_ERROR}`) | 14 ocurrències a `api/views/renovation_views.py`, 4 a `api/views/user_views.py`, 1 a `api/views/refugi_lliure_views.py`. `ERROR_500_INTERNAL_ERROR` és un `openapi.Response` (`api/utils/swagger_error_responses.py:316`). Com es serialitza a JSON: **[NO VERIFICAT]** |
| Errors 500 que exposen el text de l'excepció | `"Error intern: {str(e)}"` als controllers; `'Internal server error: ...'` a refugis |
| DAO de llistes d'usuari que retorna tuples truthy com a "èxit" | `api/daos/user_dao.py:199,235,245,260` |
| Imports erronis de `logger` | `api/models/user.py:6` (`from venv import logger`), `api/models/experience.py:9` i `api/models/refugi_lliure.py:4` (`from asyncio.log import logger`) |

## 10. Tests

- Config: `pytest.ini` (`DJANGO_SETTINGS_MODULE=refugis_lliures.settings`, `testpaths=api/tests`, `--strict-markers`, markers `unit, integration, views, serializers, controller(s), daos, mappers, models, edge_cases, slow`).
- `conftest.py` (arrel) i `api/tests/conftest.py` fixen `TESTING=true` i variables R2 falses **abans** d'importar res; amb `TESTING`/`pytest` carregat, Firebase **no s'inicialitza** (`api/firebase_config.py:15-17,92-94`).
- Mocks habituals: `patch('api.services.firestore_service.FirestoreService')`, `patch('api.services.cache_service.cache_service')` (`api/tests/conftest.py:266-286`); a les vistes es mocka el controller al mòdul de la vista, p. ex. `@patch('api.views.renovation_views.RenovationController')` (`api/tests/renovation/test_views.py:91`).
- Estructura per domini: `api/tests/<domini>/test_{models,mappers,daos,serializers,controllers,views}.py` (+ `test_integration.py` a refugi_lliure, renovation, user). Transversals: `api/tests/test_auth_middleware_permissions.py`, `api/tests/test_cache_views.py`, `api/tests/management_commands/`.
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
Llista completa per severitat: [TECH_DEBT.md](TECH_DEBT.md). Resum: permisos d'objecte inoperants (crític), invalidació de cache de propostes trencada (crític), escriptures multi-document no atòmiques, claus R2 amb nom de fitxer del client, `delete_file` que amaga errors, configuració insegura per defecte (`DEBUG=True`, `ALLOWED_HOSTS='*'`, CORS obert).
