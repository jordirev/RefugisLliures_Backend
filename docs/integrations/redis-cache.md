# Integració — Redis (cache)

> **[FET]** comprovat al codi · **[INFERÈNCIA]** deducció · **[NO VERIFICAT]** depèn de config externa.

## Configuració (`refugis_lliures/settings.py:183-202`)
- Backend `django_redis.cache.RedisCache`, `LOCATION = REDIS_URL` (default `redis://localhost:6379/1`).
- `KEY_PREFIX='refugis'`, `TIMEOUT=300`, compressió zlib, pool de 50 connexions, timeouts de socket de 5 s.
- `REDIS_URL` és a `env/.env.development` i `env/.env.production` (només nom) **[FET]**. Proveïdor de Redis a producció: **[NO VERIFICAT]**.
- No hi ha backend alternatiu (locmem) per a dev: cal Redis local o les operacions de cache fallaran silenciosament **[FET + INFERÈNCIA]**.

> **Reformes sense cache (chunk 5).** `apps/renovations` no usa Redis: ni `renovation_detail`, ni `renovation_list`, ni `renovation_refuge` (lectures directes a PostgreSQL, sense llistes velles després d'un PATCH). Les entrades de `CACHE_TIMEOUTS` i el `RenovationDAO` legacy continuen al repo fins al chunk 8 ([TECH_DEBT R15](../TECH_DEBT.md)), però ningú escriu aquestes claus **[FET]**.

> **Refugis sense cache (chunk 2).** Les lectures de refugis (`apps/refuges`) van directes a PostgreSQL, sense Redis; la cerca, la llista de coordenades i el detall ja no es cachegen **[FET]**. Dels prefixos de refugi només `refugi_detail` continua en ús, pel `RefugiLliureDAO` legacy (que fan servir altres dominis, p. ex. per comprovar que un refugi existeix). `refugi_search` i `refugi_coords` ja no els escriu ningú: el DAO de propostes que els invalidava ha desaparegut (chunk 8). El `CACHE_TIMEOUTS` conserva les tres entrades fins al chunk 11.

> **Moderació i auditoria sense cache (chunk 9).** `apps/moderation` i `apps/audit` van directes a PostgreSQL: ja no hi ha la cache de 10 min dels pHash de la blocklist (la comprovació és `moderation.fn_hash_match`, sense Redis). Des d'aquest chunk **cap feature de dades usa Redis**: `CacheService` només el fan servir `RefugiLliureDAO` (health check/legacy, fins al chunk 11) i els endpoints admin `cache/*` **[FET]**.

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
`refugi_detail` 600 · `refugi_search` 600 · `refugi_coords` 3600 · ~~`renovation_detail/list` 600~~ (sense ús, chunk 5) · ~~`experience_detail/list` 600~~ (sense ús, chunk 7) · ~~`proposal_detail/list` 600~~ (sense ús, chunk 8) · ~~`refuge_visit_detail` / `refuge_visits_list` 600~~ (sense ús, chunk 4) · `doubt_detail/list` 600 (en desús: els dubtes són a PostgreSQL i no usen cache des del chunk 6). (`user_detail` s'ha eliminat de `CACHE_TIMEOUTS` al chunk 3.) Prefixos sense entrada (`renovation_refuge`) → 600 per defecte.

### ID caching
Per a llistes: es desa la **llista d'IDs** a la clau de llista i cada element a `<detail_prefix>:<id_param>:<id>`. En un hit, es llegeix cada detall i, si falta, es recupera amb `fetch_single_fn`. Llistes i GET individual **comparteixen** les claus de detall. Implementat a `get_or_fetch_list`, sense cap ús actiu (experiències, propostes i la cerca de refugis ja no en fan servir).

### Claus en ús (exemples reals)
`refugi_detail:refugi_id:<id>` (només DAO legacy) · ~~`renovation_detail:renovation_id:<id>` · `renovation_list:date:<avui>:list_type:active`~~ (ja no s'escriuen) · ~~`proposal_detail:proposal_id:<id>`~~ (ja no s'escriu; si en queda a Redis caduca sola).

> **Usuaris (chunk 3): sense cache.** Les claus `user_detail:uid:<uid>` i `user_refugis_info:*` ja no s'escriuen ni es llegeixen (usuari, perfil, llistes i permisos van directes a PostgreSQL). Les claus d'aquests prefixos que quedin a Redis són orfes i caduquen soles (TTL 600 s) **[FET]**. La lectura d'usuari per als permisos es fa una vegada per petició i es desa a l'objecte `request`, no a Redis.

## Comportament si Redis cau
Totes les excepcions s'empassen → les lectures fan miss i van a Firestore; les invalidacions no es fan però tampoc hi ha res cachejat **[FET]**. Els endpoints admin `cache/stats` retornen `connected:false` amb 200.

Les visites (chunk 4) no usen cache: les claus `refuge_visit_detail` / `refuge_visits_list` i els seus TTL han desaparegut.

## Endpoints admin
Vegeu [flows/11-admin-cache-health.md](../flows/11-admin-cache-health.md) i, per usar-los, [guides/admin-management.md](../guides/admin-management.md).

## Gotchas
- `delete_pattern` ja afegeix `*` als dos costats; **no** afegeixis `:*` al final (bug que tenia el DAO de propostes; [TECH_DEBT C2](../TECH_DEBT.md) resolt al chunk 8).
- django-redis desa claus com `refugis:1:<clau>` (prefix + versió) **[INFERÈNCIA]**; per això el patró ha d'anar embolcallat.
- `cache.clear()` = `FLUSHDB` de tota la BD Redis **[INFERÈNCIA]**.
- `TIMEOUT=300` de settings rarament s'aplica: `CacheService` sempre passa el seu TTL **[FET]**.
- El procés diari a GitHub Actions no té `REDIS_URL` → no pot invalidar la cache de producció **[INFERÈNCIA]**.
- `.coveragerc` exclou `services/` → `cache_service` no compta al coverage **[FET]**.

> **Dubtes (chunk 6): sense cache.** `doubt_detail:*` i `doubt_list:refuge_id:*` ja no s'escriuen ni es llegeixen (`apps/doubts/selectors.py` va directe a PostgreSQL; la llista són 2 consultes constants). Les claus que quedin a Redis són orfes i caduquen soles (TTL 600 s) **[FET]**. `DoubtDAO` legacy les escriuria si es cridés, però només el crida l'esborrat de refugis per proposta ([TECH_DEBT D1](../TECH_DEBT.md)).
