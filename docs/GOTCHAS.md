# Gotchas / què NO fer

> **[FET]** comprovat al codi · **[INFERÈNCIA]** deducció · **[NO VERIFICAT]** depèn de config externa.

## Seguretat i permisos

1. **NO afegeixis un `Is*Creator` a `permission_classes` pensant que protegeix el recurs.** `has_object_permission` només el crida `GenericAPIView.get_object()` / `check_object_permissions()`, i aquí no s'usen enlloc **[FET]** (cap ocurrència de `check_object_permissions` a `api/`). A més, `IsExperienceCreator`/`IsRenovationCreator` fan `instance.get(...)` sobre una dataclass i petarien si s'executessin (`api/permissions.py:146`, `190`). **Fes la comprovació de propietat al controller**, com `RenovationController.update_renovation` (`api/controllers/renovation_controller.py:118-120`).
2. **NO assumeixis que una ruta sota `/api/refuges/` és privada.** El middleware exclou per prefix (`startswith`) `/api/refuges/`, i això inclou `media/`, `visits/` i `renovations/` (`api/middleware/firebase_auth_middleware.py:20-25,98-103`). La protecció depèn **només** de `permission_classes` de la vista. Si crees una vista nova sota aquest prefix sense `IsAuthenticated`, serà pública (el default és `AllowAny`, `refugis_lliures/settings.py:161-163`).
3. **NO confiïs en el default de permisos**: és `AllowAny`. Declara sempre `permission_classes` o `get_permissions()`.
4. Un token caducat o mal format en una ruta pública (p. ex. `GET /api/refuges/`) dona **401**, no accés anònim: si hi ha header `Authorization` mal format a ruta exclosa es deixa passar, però si és un Bearer invàlid es rebutja (`api/middleware/firebase_auth_middleware.py:49-96`) **[FET]**.
5. Admin és el claim **`role == 'admin'`**, no `admin: true` (com deia la documentació antiga). Usa `scripts/manage_admins.py` **[FET]**.
6. **NO llegeixis ni imprimeixis** res de `env/` (service accounts, `.env.*`). No està versionat (`git ls-files env` buit) i ha de continuar així. `run_process_visits.sh` porta placeholders de credencials R2: no hi posis valors reals (ho avisa el mateix fitxer, L2).

## Firestore i consistència

7. **NO facis read-modify-write d'arrays o maps sencers.** El codi actual ho fa a molts llocs (`media_metadata`, `uploaded_photos_keys`, `visitors`, `participants_uids`, `coords_refugis/all_refugis_coords`…) i és una font de lost updates **[FET + INFERÈNCIA sobre la carrera]**. Usa `firestore.ArrayUnion` / `ArrayRemove` / `Increment` (ja usats a `api/daos/user_dao.py` per a comptadors i a `api/daos/experience_dao.py` per a `media_keys`) o una transacció.
8. **NO llegeixis des de cache abans d'escriure.** Diversos DAOs fan `get_by_id` (cache-first) i després sobreescriuen el document amb dades potencialment antigues (p. ex. `api/daos/user_dao.py:232`).
9. Els "check-then-create" (usuari, visita, solapament de renovations) **no són transaccionals** → duplicats possibles amb peticions concurrents **[INFERÈNCIA]**.
10. Desa les dates com a **string ISO** (`YYYY-MM-DD`) — les queries i l'ordenació depenen de comparar strings (`api/daos/renovation_dao.py:38-49`).
11. Si afegeixes una query amb diversos `where` + `order_by`, probablement necessites un **índex compost**: no hi ha `firestore.indexes.json` al repo, així que els índexs existents són **[NO VERIFICAT]**.

## Cache

12. **Invalida amb el prefix exacte de la clau, sense `:*` final.** `delete_pattern(p)` ja embolcalla amb `*p*` (`api/services/cache_service.py:159`). Les claus acaben en el valor (`proposal_detail:proposal_id:<id>`), així que `delete_pattern('proposal_detail:proposal_id:<id>:*')` **no fa match** (bug real a `api/daos/refuge_proposal_dao.py:770,806`) **[FET sobre el format de clau; INFERÈNCIA sobre el prefix de django-redis]**.
13. Quan una escriptura canvia camps que afecten llistes/cerques, invalida també les claus de llista (`*_list:`, `refugi_search:`, `user_refugis_info:`), no només el detall.
14. Una mateixa clau de cache ha de tenir sempre **la mateixa forma**: `doubt_detail` es desa amb i sense `answers` (`api/daos/doubt_dao.py:86-88` vs `129-153`) **[FET]**.
15. Els errors de Redis s'empassen (`api/services/cache_service.py:106-108`, `144-146`, `162-164`): si Redis cau, tot "funciona" però va directe a Firestore. No ho facis servir per detectar problemes.
16. `DELETE /api/cache/clear/` fa `cache.clear()` → amb django-redis és `FLUSHDB` de tota la BD Redis, independentment de `KEY_PREFIX` **[INFERÈNCIA]**.

## Validació i errors

17. **Alinea serializer i model.** El serializer de renovations accepta `ini_date == fin_date` (`api/serializers/renovation_serializer.py:24`) però el model exigeix `ini < fin` (`api/models/renovation.py:32-33`); el DAO ja ha fet `set()` quan el model peta (`api/daos/renovation_dao.py:54,63`) → document invàlid persistit que trenca les llistes **[FET]**.
18. **NO posis `default=` en camps d'un serializer d'UPDATE.** `UserUpdateSerializer.language` té `default='ca'` (`api/serializers/user_serializer.py:150`) → un PATCH sense `language` el reseteja a `'ca'` **[FET]**.
19. **NO canviïs textos d'error** sense revisar les vistes: el codi HTTP es tria per subcadena (`'solapa'`, `'not found'`, `'ja existeix'`, `'no trobat'`…).
20. Compte amb `date` vs `datetime`: `Renovation.from_dict` crea `datetime` (`api/models/renovation.py:62-63`) i el serializer d'update dona `date` → comparar-los llança `TypeError` (`api/controllers/renovation_controller.py:124-128`) **[FET]**.

## R2 / media

21. **NO passis `filename=file.name`** a `R2MediaService.upload_file`: la clau queda `refugis-lliures/<refuge_id>/<nom original>` i dues pujades amb el mateix nom se sobreescriuen (`api/services/r2_media_service.py:196-203`; crides a `api/controllers/refugi_lliure_controller.py` i `api/controllers/user_controller.py`) **[FET]**. Deixa `filename=None` perquè generi un UUID.
22. `R2MediaService.delete_file` **retorna `False`, no llança**, en cas de `ClientError` (`api/services/r2_media_service.py:339-341`). Comprova el booleà; un `try/except` al voltant no detectarà la fallada.
23. No hi ha límit de mida de pujada ni validació per magic bytes; amb 1 worker gunicorn i timeout 30 s, fitxers grans poden bloquejar el servei **[INFERÈNCIA]**.
24. No desis URLs a Firestore: es desa la **clau** i la URL presignada (1 h) es genera en llegir (`api/services/r2_media_service.py:228-251`).

## Entorn i desplegament

25. Les variables R2 es llegeixen amb `os.getenv` (`api/r2_config.py:12-15`), però `settings.py` llegeix els `.env` amb `decouple.RepositoryEnv`, que **no** les posa a `os.environ`. En local només entren a `os.environ` les del `.env.development` via `load_dotenv` (`api/firebase_config.py:54-56`) — i aquest fitxer no defineix `R2_*`. Cal exportar-les a l'entorn **[FET]**.
26. `render.yaml` defineix `RENDER="1"` (`render.yaml:8-9`) però `firebase_config` compara `RENDER == 'true'` (`api/firebase_config.py:21,27`). Si Render no sobreescriu el valor, s'intentaria la inicialització local **[NO VERIFICAT]** (Render injecta `RENDER=true` per defecte segons la seva documentació, però no és confirmable des del repo).
27. Els `CRONJOBS` de `django-crontab` (`refugis_lliures/settings.py:275-278`) **no s'activen sols** (cal `manage.py crontab add`, que `build.sh` no fa). El procés diari real s'executa a GitHub Actions (`.github/workflows/process-visits.yml`) **[FET]**.
28. El workflow de visites no defineix `REDIS_URL` → el procés diari no pot invalidar la cache de producció; els canvis poden trigar fins a 10 min a veure's **[INFERÈNCIA]**.
29. `DEBUG` val `True`, `ALLOWED_HOSTS='*'` i `CORS_ALLOW_ALL_ORIGINS=True` **per defecte** (`refugis_lliures/settings.py:45-47,169`). En producció depèn de les variables de Render **[NO VERIFICAT]**. `CsrfViewMiddleware` està comentat (`refugis_lliures/settings.py:72`).

## Tests

30. Els tests de vistes fan `view.cls.permission_classes = []` i `view.cls.authentication_classes = []` (p. ex. `api/tests/renovation/test_views.py:101-102`), que **muta la classe** per a tota la sessió de pytest **[FET]**: un test posterior que comprovi permisos pot passar per error **[INFERÈNCIA]**. Usa `patch.object(Vista, 'permission_classes', [])`.
31. Fixa variables d'entorn (`TESTING`, `R2_*`) al `conftest.py` **arrel** abans de cap import de `api` (`conftest.py`); amb `TESTING=true` Firebase no s'inicialitza (`api/firebase_config.py:92-94`) i cal mockejar `FirestoreService`/`cache_service` al mòdul del DAO.
