# Integració — Redis (cache)

> **[FET]** comprovat al codi · **[INFERÈNCIA]** deducció · **[NO VERIFICAT]** depèn de config externa.

## Configuració (`refugis_lliures/settings.py:183-202`)
- Backend `django_redis.cache.RedisCache`, `LOCATION = REDIS_URL` (default `redis://localhost:6379/1`).
- `KEY_PREFIX='refugis'`, `TIMEOUT=300`, compressió zlib, pool de 50 connexions, timeouts de socket de 5 s.
- `REDIS_URL` és a `env/.env.development` i `env/.env.production` (només nom) **[FET]**. Proveïdor de Redis a producció: **[NO VERIFICAT]**.
- No hi ha backend alternatiu (locmem) per a dev: cal Redis local o les operacions de cache fallaran silenciosament **[FET + INFERÈNCIA]**.

## `CacheService` (`api/services/cache_service.py`)
Singleton (L14-53), instància global `cache_service` (L317), exportat a `api/services/__init__.py`.

| Mètode | Comportament | Línies |
|---|---|---|
| `generate_key(prefix, **kw)` | `prefix:k1:v1:k2:v2` amb kwargs ordenats alfabèticament | L63-85 |
| `get_timeout(key_type)` | `CACHE_TIMEOUTS[key_type]` o 600 | L59-61 |
| `get` / `set` / `delete` | envolten `django.core.cache.cache`; errors → log + `None`/`False` | L87-146 |
| `delete_pattern(p)` | `cache.delete_pattern(f"*{p}*")` | L148-164 |
| `clear_all()` | `cache.clear()` | L166-179 |
| `get_stats()` | `INFO` + `DBSIZE` del client Redis | L181-206 |
| `get_or_fetch_list(...)` | **ID caching** (vegeu sota) | L208-281 |
| `get_or_fetch_detail(...)` / `cache_result` | definits, sense ús fora de tests | L283, L321 |

### TTL (`CACHE_TIMEOUTS`, L20-48)
`refugi_detail` 600 · `refugi_search` 600 · `refugi_coords` 3600 · `user_detail` 600 · `renovation_detail/list` 600 · `experience_detail/list` 600 · `proposal_detail/list` 600 · `refuge_visit_detail` / `refuge_visits_list` 600 · `doubt_detail/list` 600. Prefixos sense entrada (`user_refugis_info`, `renovation_refuge`) → 600 per defecte.

### ID caching
Per a llistes: es desa la **llista d'IDs** a la clau de llista i cada element a `<detail_prefix>:<id_param>:<id>`. En un hit, es llegeix cada detall i, si falta, es recupera amb `fetch_single_fn`. Llistes i GET individual **comparteixen** les claus de detall. Implementat a `get_or_fetch_list`, usat per `RenovationDAO.get_all_renovations` (`api/daos/renovation_dao.py:111-176`), experiències, dubtes, propostes, visites i cerca de refugis.

### Claus en ús (exemples reals)
`refugi_detail:refugi_id:<id>` · `refugi_coords:document:all` · `refugi_search:<filtres>` · `user_detail:uid:<uid>` · `user_refugis_info:list_name:<L>:uid:<uid>` · `renovation_detail:renovation_id:<id>` · `renovation_list:date:<avui>:list_type:active` · `proposal_detail:proposal_id:<id>` · `doubt_list:refuge_id:<id>`.

## Comportament si Redis cau
Totes les excepcions s'empassen → les lectures fan miss i van a Firestore; les invalidacions no es fan però tampoc hi ha res cachejat **[FET]**. Els endpoints admin `cache/stats` retornen `connected:false` amb 200.

## Endpoints admin
Vegeu [flows/11-admin-cache-health.md](../flows/11-admin-cache-health.md) i, per usar-los, [guides/admin-management.md](../guides/admin-management.md).

## Gotchas
- `delete_pattern` ja afegeix `*` als dos costats; **no** afegeixis `:*` al final (bug de propostes, [TECH_DEBT C2](../TECH_DEBT.md)).
- django-redis desa claus com `refugis:1:<clau>` (prefix + versió) **[INFERÈNCIA]**; per això el patró ha d'anar embolcallat.
- `cache.clear()` = `FLUSHDB` de tota la BD Redis **[INFERÈNCIA]**.
- `TIMEOUT=300` de settings rarament s'aplica: `CacheService` sempre passa el seu TTL **[FET]**.
- El procés diari a GitHub Actions no té `REDIS_URL` → no pot invalidar la cache de producció **[INFERÈNCIA]**.
- `.coveragerc` exclou `services/` → `cache_service` no compta al coverage **[FET]**.
