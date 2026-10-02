# Deute tècnic detectat

> **[FET]** comprovat al codi · **[INFERÈNCIA]** deducció (carreres, comportament de llibreries) · **[NO VERIFICAT]** depèn de config externa.
> Ordenat per severitat. Cap d'aquests punts s'ha corregit: és un inventari.

## Crític

| # | Problema | Evidència | Tipus |
|---|---|---|---|
| C1 | **Permisos d'objecte inoperants**: `has_object_permission` mai s'executa. Qualsevol usuari autenticat pot fer PATCH/DELETE de **qualsevol experiència** (incloent esborrar les fotes del creador a R2) i DELETE de **qualsevol dubte o resposta**. Renovations se salva perquè el controller comprova el creador. | `api/permissions.py:104-190,279-373`; cap `check_object_permissions` a `api/`; `ExperienceController.update_experience/delete_experience` (`api/controllers/experience_controller.py:132,196`) i `DoubtController.delete_doubt` (`api/controllers/doubt_controller.py:144`) no reben l'UID de l'usuari | FET |
| C2 | **Invalidació de cache de propostes trencada**: després d'aprovar/rebutjar, la proposta segueix `pending` a cache fins a 600 s → es pot **aprovar dues vegades** (refugi duplicat, vot de condició comptat dos cops). | clau `proposal_detail:proposal_id:<id>` (`api/daos/refuge_proposal_dao.py:620`) vs patró `...:<id>:*` (`:770`, `:806`) embolcallat en `*…*` (`api/services/cache_service.py:159`) | FET (format) + INFERÈNCIA (efecte) |

## Alt

| # | Problema | Evidència | Tipus |
|---|---|---|---|
| A1 | Renovation amb `ini_date == fin_date` passa el serializer, es desa a Firestore i després el model peta → `get_all_renovations` retorna `[]` per a tothom mentre existeixi. | `api/serializers/renovation_serializer.py:24`, `api/models/renovation.py:32-33`, `api/daos/renovation_dao.py:54,63,174-176` | FET |
| A2 | Claus R2 amb el nom original del fitxer → col·lisions i sobreescriptura entre usuaris; `creator_uid` del media canvia de mans. | `api/services/r2_media_service.py:196-203` + crides amb `filename=file.name` | FET |
| A3 | Read-modify-write sense transacció sobre `media_metadata`, `uploaded_photos_keys`, `visitors` (refugi i visita), `participants_uids`, `expelled_uids`, `coords_refugis/all_refugis_coords` → lost updates. | `api/daos/refugi_lliure_dao.py:394-539`, `api/daos/user_dao.py:218-264,367-535`, `api/daos/renovation_dao.py:404-507`, `api/daos/refuge_visit_dao.py:250-385`, `api/daos/refuge_proposal_dao.py:62-209` | FET (patró) + INFERÈNCIA (carrera) |
| A4 | `delete_file` retorna `False` en lloc de llançar → els rollbacks dins `try/except` dels callers són codi mort; un esborrat fallit a R2 es reporta com a èxit (objecte orfe). | `api/services/r2_media_service.py:339-341` | FET |
| A5 | Aprovar una proposta d'esborrat falla a mitges si totes les fotos del refugi eren d'experiències (claus llegides abans d'esborrar-les). | `api/daos/refuge_proposal_dao.py:409,486-498`, `api/daos/refugi_lliure_dao.py:520-522` | FET |
| A6 | Escriptures multi-document no atòmiques a fluxos llargs: esborrat d'usuari (11 passos), aprovació de propostes, experiència + media + comptadors. | `api/controllers/user_controller.py:125-276`, `api/daos/refuge_proposal_dao.py:231-556` | FET |

## Mitjà

| # | Problema | Evidència | Tipus |
|---|---|---|---|
| M1 | PATCH d'usuari reseteja `language` a `'ca'`; el `validate()` "almenys un camp" mai falla. | `api/serializers/user_serializer.py:150,159-163` | FET |
| M2 | PATCH de renovation amb només una data → `TypeError` (`date` vs `datetime`) → 500. | `api/controllers/renovation_controller.py:124-128`, `api/models/renovation.py:62-63` | FET |
| M3 | Esborrar un usuari decrementa `total_visitors` en 1 i no en `num_visitors`. | `api/daos/refuge_visit_dao.py:529` | FET |
| M4 | Visites duplicades possibles per (refugi, data): check-then-create sense transacció; `limit(1)` n'amaga una. | `api/controllers/refuge_visit_controller.py:105-147`, `api/daos/refuge_visit_dao.py:96-136` | INFERÈNCIA |
| M5 | `condition` es desa com a mitjana float però el filtre de cerca només accepta 0/1/2 exactes. | `api/services/condition_service.py:39`, `api/serializers/refugi_lliure_serializer.py:82-164` | FET |
| M6 | Actualitzar un refugi via proposta no invalida `refugi_search` ni `user_refugis_info`. | `api/daos/refuge_proposal_dao.py:373-378` | FET |
| M7 | `doubt_detail` es desa amb dues formes (amb/sense `answers`). | `api/daos/doubt_dao.py:86-88` vs `129-153` | FET |
| M8 | Error path del PATCH d'experiència fa `None.to_dict()`. | `api/views/experience_views.py:310-312` | FET |
| M9 | Payload de proposta es desa en brut (sense coerció de tipus del serializer niat). | `api/serializers/refuge_proposal_serializer.py:160-166` | FET |
| M10 | Esborrat d'usuari: tota fallada es retorna com a 404; el compte de Firebase Auth no s'esborra al backend. | `api/views/user_views.py:268-271`; cap `auth.delete_user` a `api/` | FET |
| M11 | Configuració insegura per defecte: `DEBUG=True`, `ALLOWED_HOSTS='*'`, CORS obert, CSRF middleware comentat. | `refugis_lliures/settings.py:45-47,72,169` | FET (valors en producció: NO VERIFICAT) |

## Baix

| # | Problema | Evidència | Tipus |
|---|---|---|---|
| B1 | `active_only` de `GET /refuges/{id}/renovations/` és paràmetre del mètode, no es llegeix de la query → sempre `False`. | `api/views/refugi_lliure_views.py:282-286` | FET |
| B2 | Cerca per nom exacta (`==`) però Swagger diu parcial i case-insensitive. | `api/daos/refugi_lliure_dao.py:204-226` | FET |
| B3 | Qualsevol usuari autenticat pot llegir el perfil complet d'un altre (llistes, claus de fotos). | `api/views/user_views.py:155-156` | FET |
| B4 | Health check depèn de les variables R2 (el controller crea el client R2) i no comprova Redis. | `api/controllers/refugi_lliure_controller.py:22` | FET |
| B5 | `get_visits_by_user` fa scan de tota la col·lecció `refuge_visits`; els documents processats mai s'esborren. | `api/daos/refuge_visit_dao.py:207-248` | FET |
| B6 | DAOs de llistes d'usuari retornen tuples truthy → el controller no detecta fallades. | `api/daos/user_dao.py:199,235,245,260` | FET |
| B7 | Imports `from venv import logger` / `from asyncio.log import logger` als models. | `api/models/user.py:6`, `api/models/experience.py:9`, `api/models/refugi_lliure.py:4` | FET |
| B8 | Codis HTTP diferents dels documentats a Swagger (media DELETE 200 vs 204, favorits POST 200 vs 201, visita DELETE 200). | vistes corresponents | FET (segons informe de fluxos) |
| B9 | `verify_id_token` sense `check_revoked=True` → la branca `RevokedIdTokenError` mai s'activa. | `api/middleware/firebase_auth_middleware.py:60,86` | FET + INFERÈNCIA (SDK) |
| B10 | Lògica d'autenticació duplicada entre middleware i `FirebaseAuthentication`. | `api/middleware/firebase_auth_middleware.py`, `api/authentication.py` | FET |
| B11 | Dues rutes d'inicialització de Firebase amb criteris diferents (`firebase_config.py` usa el fitxer fix `env/firebase-service-account.json`; `FirestoreService._initialize_firebase` usa `settings.GOOGLE_APPLICATION_CREDENTIALS`). | `api/firebase_config.py:60`, `api/services/firestore_service.py:57` | FET |
| B12 | `settings.py` tria `.env.production` amb `RENDER`/`PRODUCTION` però `firebase_config` també considera `CI=true` com a producció → a CI s'usen settings de dev i Firebase de prod. | `refugis_lliures/settings.py:21`, `api/firebase_config.py:24-30` | FET |
| B13 | `tox.ini` declara `envlist=py39`; CI usa Python 3.10 amb `tox -e py`. | `tox.ini`, `.github/workflows/django.yml:16,31` | FET |
| B14 | Comentaris contradictoris d'horari del procés diari ("3:00 Madrid" a settings vs "3:00 UTC" al workflow). | `refugis_lliures/settings.py:276`, `.github/workflows/process-visits.yml:5-6` | FET |

## Codi mort o sense ús aparent

| Element | Evidència | Tipus |
|---|---|---|
| `IsOwnerOrReadOnly`, `SafeMethodsOnly` | definits a `api/permissions.py:25-84`, sense ús fora de tests | FET (grep) |
| Decorador `cache_result`, `CacheService.get_or_fetch_detail` | només s'exporten/defineixen (`api/services/cache_service.py:283,321`; `api/services/__init__.py:2`) | FET (grep) |
| Rollbacks basats en excepció de `delete_file` | vegeu A4 | FET |
| `CRONJOBS` (django-crontab) | mai s'instal·la el crontab (`build.sh`) | FET |
| `R2_* = None` de compatibilitat | `api/r2_config.py:44-49` | FET |
| Fixtures `authenticated_client`, `mock_refugi_dao` | patch targets inexistents (`api/tests/conftest.py:323,398`) | INFERÈNCIA |
| `htmlcov/` referencia `convert_mezzanine_field.py`, que ja no existeix | artefacte antic (ignorat per git) | FET |

## Artefactes al disc (no versionats, però presents)
`db.sqlite3`, `coverage.xml`, `.coverage`, `htmlcov/`, `.vs/`, `.pytest_cache/` — tots ignorats per `.gitignore` (`git check-ignore`: `.gitignore:10,43,50,64`) **[FET]**. `env/` conté credencials reals i **no** està versionat (`git ls-files env` buit); a l'historial només hi ha hagut `.env.example` amb noms de variables (commits `c1f5eee`, `5b73f15`).
