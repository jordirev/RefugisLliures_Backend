# Patrons arquitectònics i de disseny (detall)

> **[FET]** comprovat al codi · **[INFERÈNCIA]** deducció · **[NO VERIFICAT]** depèn de config externa.
> Resum en una taula: [ARCHITECTURE §3 i §7](../ARCHITECTURE.md). Aquest document amplia cada patró amb on viu, per què hi és i un diagrama.

## Arquitectònics

### 1. Arquitectura en capes
`View → Serializer → selectors (lectures) / services (escriptures) → models (ORM + RLS) [+ R2MediaService]`. Contractes de cada capa: [ARCHITECTURE §3](../ARCHITECTURE.md). Després de la neteja (chunk 11, D43) tots els dominis són apps (`apps/<feature>/`); a `api/` només queda infraestructura compartida.

```
CLIENT (app mòbil)
   │
MIDDLEWARE  firebase_auth_middleware.py  (verifica JWT, injecta user_uid/user_claims)
   │
VIEWS       apps/<feature>/views.py  (APIView + @swagger_auto_schema, serializers d'entrada, permisos)
   │
   ├── SELECTORS apps/<feature>/selectors.py  (lectures, una consulta per cas d'ús)
   └── SERVICES  apps/<feature>/services.py   (escriptures, transaction.atomic, propietat)
   │           └── api/services: r2_media_service (Strategy+Factory) · image_processing · moderation
   │
EXTERNS     PostgreSQL (Neon) · Cloudflare R2 · Firebase Auth
```
Excepcions al patró: [ARCHITECTURE §9](../ARCHITECTURE.md).

### 2. REST
Recursos a `api/urls.py` (`/refuges/`, `/users/`, `/experiences/`…), verbs GET/POST/PATCH/DELETE, Swagger a `/swagger/`. Hi ha desviacions de codis HTTP respecte a Swagger ([TECH_DEBT B8](../TECH_DEBT.md)).

### 3. Middleware pipeline
`FirebaseAuthenticationMiddleware` intercepta totes les peticions abans de DRF ([flux 0](../flows/00-auth-request-pipeline.md)). Per què conviu amb una classe d'autenticació DRF: [decisions.md](decisions.md#adr-2--middleware--classe-dautenticació-drf).

## De disseny

### Selectors i services per feature (apps migrades a PostgreSQL)
Les features migrades (`apps/<feature>/`) són **`selectors.py`** (lectures; una consulta per cas d'ús, sense cache de dades) i **`services.py`** (escriptures amb `transaction.atomic`; excepcions de domini). La resta de capes (vista fina, serializers, models amb RLS i FK del DDL) i el flux estan a [ARCHITECTURE §3.1](../ARCHITECTURE.md). Referència: `apps/refuges`.

### Errors 500 amb traçabilitat (apps migrades)
**Errors 500 amb traçabilitat** (política del PO per a les features migrades): la resposta és `{"error": "<missatge específic del punt que ha fallat>", "error_id": "<uuid>"}` i el mateix `error_id` es desa al log amb la traça completa (`logger.exception`). **Mai** es retorna `str(e)` ni el nom/text de l'excepció (pot dur SQL, hosts, bucket, claus o rutes). Ho fa el helper `apps.core.errors.server_error(message, exc, logger=logger)`; el missatge és un text fix per punt ("Error en esborrar el fitxer a R2", "Error de base de dades en cercar refugis", "Error en generar la URL de la imatge"…). Tests de referència: `apps/core/tests/test_errors.py` i `apps/refuges/tests/test_server_errors.py` (forma de la resposta, `error_id` coincident amb el log, cap text d'excepció a la resposta).

### Strategy
| On | Interfície | Concrets | Selector |
|---|---|---|---|
| Cerca de refugis | _(eliminat al chunk 2: era `api/daos/search_strategies.py` amb 15 estratègies; ara és una sola consulta SQL a `apps/refuges/selectors.py`)_ | — | — |
| Paths de media — `api/services/r2_media_service.py` | `MediaPathStrategy` (`get_base_path`, `get_allowed_content_types`, `validate_file`, `generate_media_metadata_from_dict`) | `RefugiMediaStrategy`, `UserAvatarStrategy` | factories (vegeu Factory) |
| Aprovació de propostes — `apps/proposals/services.py` | una transacció amb bloqueig pessimista; una funció per acció | `_apply_create/_apply_update/_apply_delete` | `approve_proposal` (les estratègies de Firestore van desaparèixer al chunk 8) |

**Strategy de moderació (feature images)**: `ModerationProvider` (interfície) amb `HashBlocklistProvider` actiu i stubs desactivats `PhotoDNAProvider` / `GoogleContentSafetyProvider`; `ModerationService` els executa en ordre i el primer que bloqueja guanya (fail-closed si un falla). `api/services/moderation_service.py`, [flux 12](../flows/12-media-moderation.md).

### Singleton
Cap des del chunk 11: `CacheService` i `FirestoreService` han desaparegut.

### Factory
- **Funcions factory** de R2: `get_refugi_media_service()` → `R2MediaService(RefugiMediaStrategy())`; `get_user_avatar_service()` → `R2MediaService(UserAvatarStrategy())`.

### Template Method (+ hook)
- (Eliminat al chunk 3: `UserController._manage_refugi_list` i el seu hook de `visitors`. Els preferits i els visitats comparteixen ara la classe abstracta `_UserRefugeList` i les funcions `_add`/`_remove` d'`apps/accounts/services.py`; no hi ha hook: `visitors` surt de `user_visited_refuges`.)
- `to_dict()` de `RefugeMediaMetadata` crida `super().to_dict()` i hi afegeix `creator_uid`/`experience_id`: la base dona la plantilla, la subclasse l'especialitza.

### Decorator
- `@swagger_auto_schema` a totes les vistes (totes són `APIView`; `cache_views.py` i `@api_view` han desaparegut).
- `@cache_result` ha desaparegut amb `cache_service` (chunk 11).
