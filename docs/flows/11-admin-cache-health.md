# Flux 11 — Endpoints admin de cache i health check

> **[FET]** comprovat al codi · **[INFERÈNCIA]** deducció · **[NO VERIFICAT]** depèn de config externa.

## Endpoints
| Mètode | URL | Vista | Permisos | Comportament |
|---|---|---|---|---|
| GET | `/api/cache/stats/` | `cache_stats` (`api/views/cache_views.py:51-63`) | IsFirebaseAdmin | `cache_service.get_stats()` (`api/services/cache_service.py:181-206`): Redis `INFO` + `DBSIZE` → `{connected, keys, memory_used, hits, misses}` |
| DELETE | `/api/cache/clear/` | `cache_clear` (L82-101) | IsFirebaseAdmin | `cache.clear()` |
| DELETE | `/api/cache/invalidate/?pattern=...` | `cache_invalidate` (L126-151) | IsFirebaseAdmin | `cache_service.delete_pattern(pattern)` → `*pattern*` |
| GET | `/api/health/` | `HealthCheckAPIView.get` (`api/views/health_check_views.py`) | públic (exclòs del middleware) | `SELECT 1` a Postgres + llista col·leccions arrel de Firestore |

Són les úniques vistes funció (`@api_view` + `@permission_classes`) del projecte **[FET]**.

## Diagrama

```mermaid
sequenceDiagram
    autonumber
    participant A as Admin
    participant MW as FirebaseAuthMiddleware
    participant P as IsFirebaseAdmin
    participant CV as cache_views
    participant CS as CacheService
    participant R as Redis
    participant M as Monitor/Client
    participant H as HealthCheckAPIView
    participant RC as RefugiLliureController
    participant F as Firestore
    participant PG as Postgres (default)

    A->>MW: DELETE /api/cache/invalidate/?pattern=refugi_search
    MW->>P: request.user_claims.role == 'admin'?
    P-->>A: 403 si no
    P->>CV: cache_invalidate
    CV->>CS: delete_pattern('refugi_search')
    CS->>R: delete_pattern('*refugi_search*')
    CV-->>A: 200

    M->>H: GET /api/health/ (dins una transacció d'ATOMIC_REQUESTS)
    H->>RC: RefugiLliureController() — el client R2 es crea sota demanda (no aquí)
    RC->>PG: SELECT 1 (check_database)
    RC->>F: db.collections()
    alt Postgres i Firestore ok
        H-->>M: 200 {status:'healthy', firebase, firestore, collections_count, database:true}
    else Postgres o Firestore fallen
        H-->>M: 503 {status:'unhealthy', database:true/false, …}
    end
    Note over M,H: si Postgres cau abans de la vista, HealthDatabaseErrorMiddleware retorna 503 {database:false}
```

## Passos
- Fer-se admin, cURL i Swagger: [guides/admin-management.md](../guides/admin-management.md).
- Health: `RefugiLliureController.health_check` (`api/controllers/refugi_lliure_controller.py:102-127`) → `RefugiLliureDAO.health_check` (`api/daos/refugi_lliure_dao.py:229-243`).
- Ping extern: `.github/workflows/ping-website.yml` fa `curl` a `/swagger/` cada 9 minuts (no a `/api/health/`) per mantenir despert el servei de Render **[FET]**; el motiu (evitar l'*spin-down* del pla gratuït) és **[INFERÈNCIA]**.

## Errors
| Cas | HTTP |
|---|---|
| No admin | 403 |
| `pattern` absent | 400 |
| Error Redis a `stats` | **200** amb `{connected:false, error}` (el servei s'empassa l'excepció) |
| Error a `clear` | 500 |
| Health KO (Postgres o Firestore) | 503 `{status:'unhealthy', database, …}` |

## Gotchas
- `cache.clear()` amb django-redis = `FLUSHDB` de tota la BD Redis, no només claus `refugis:*` **[INFERÈNCIA]**.
- `pattern='*'` és acceptat i ho esborra tot **[FET]**.
- El health check **ja no depèn d'R2** (B4 resolt): `RefugiLliureController.media_service` és una propietat que crea el client sota demanda, així que `RefugiLliureController()` no necessita variables `R2_*` **[FET]**. Continua sense comprovar Redis **[FET]**.
- **Postgres** (nou): `check_database()` (`api/services/database_health.py`) executa `SELECT 1` amb `default` i retorna `False` en un `DatabaseError` (només es registra el tipus d'error, mai detalls ni credencials). Si Postgres falla o Firestore falla → **503** `status:'unhealthy'`; el camp `database` és `true`/`false` (afegit a `HealthCheckResponseSerializer` i als exemples de Swagger). Missatge `Database unavailable` quan és Postgres **[FET]**.
- `HealthDatabaseErrorMiddleware` cobreix el cas en què Postgres és inabastable **abans** de la vista: amb `ATOMIC_REQUESTS` la petició falla en obrir la transacció (i el hook de RLS també fa una consulta), de manera que la vista no arriba a informar `database:false`. El middleware retorna 503 només a `/api/health/` **[FET]**.
- Conseqüència operativa: `/api/health/` (i qualsevol monitor que l'usi) també desperta Neon (scale-to-zero) i ocupa una connexió del pooler **[INFERÈNCIA]**. El ping de Render/Actions apunta a `/swagger/`, no al health ([render-deploy-ci.md](../integrations/render-deploy-ci.md)).
- Missatges sense detalls interns: si Firestore falla, la resposta és `message: 'Health check failed'` (abans `Error: <excepció>`) i el log només porta el tipus d'excepció; el detall mai surt al client ni al log **[FET]**.
- Contracte: l'exemple d'èxit de Swagger afegeix `database: true`; els clients que ignoren camps desconeguts no es veuen afectats **[FET]**.
