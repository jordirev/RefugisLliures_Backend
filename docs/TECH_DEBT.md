# Deute tècnic detectat

> **[FET]** comprovat al codi · **[INFERÈNCIA]** deducció (carreres, comportament de llibreries) · **[NO VERIFICAT]** depèn de config externa.
> Ordenat per severitat. Els punts marcats **RESOLT** s'han corregit a la feature *images* (branca `feature/images`).

## Crític

| # | Problema | Evidència | Tipus |
|---|---|---|---|
| C1 | **(Parcialment RESOLT: experiències comproven la propietat al controller, 403 `not_owner`; dubtes i respostes pendents)** **Permisos d'objecte inoperants**: `has_object_permission` mai s'executa. Qualsevol usuari autenticat pot fer PATCH/DELETE de **qualsevol experiència** (incloent esborrar les fotes del creador a R2) i DELETE de **qualsevol dubte o resposta**. Renovations se salva perquè el controller comprova el creador. | `api/permissions.py:104-190,279-373`; cap `check_object_permissions` a `api/`; `ExperienceController.update_experience/delete_experience` (`api/controllers/experience_controller.py:132,196`) i `DoubtController.delete_doubt` (`api/controllers/doubt_controller.py:144`) no reben l'UID de l'usuari | FET |
| C2 | **Invalidació de cache de propostes trencada**: després d'aprovar/rebutjar, la proposta segueix `pending` a cache fins a 600 s → es pot **aprovar dues vegades** (refugi duplicat, vot de condició comptat dos cops). | clau `proposal_detail:proposal_id:<id>` (`api/daos/refuge_proposal_dao.py:620`) vs patró `...:<id>:*` (`:770`, `:806`) embolcallat en `*…*` (`api/services/cache_service.py:159`) | FET (format) + INFERÈNCIA (efecte) |

## Alt

| # | Problema | Evidència | Tipus |
|---|---|---|---|
| A1 | Renovation amb `ini_date == fin_date` passa el serializer, es desa a Firestore i després el model peta → `get_all_renovations` retorna `[]` per a tothom mentre existeixi. | `api/serializers/renovation_serializer.py:24`, `api/models/renovation.py:32-33`, `api/daos/renovation_dao.py:54,63,174-176` | FET |
| A2 | **RESOLT** (claus UUID; `upload_file` ignora `filename`). Claus R2 amb el nom original del fitxer → col·lisions i sobreescriptura entre usuaris; `creator_uid` del media canvia de mans. | `api/services/r2_media_service.py:196-203` + crides amb `filename=file.name` | FET |
| A3 | **Parcialment RESOLT** (`media_metadata` amb FieldPath/DELETE_FIELD; `uploaded_photos_keys` i les llistes de preferits/visitats ja no són arrays: chunk 3; la resta pendent). Read-modify-write sense transacció sobre `media_metadata`, `visitors` (refugi legacy i visita), `participants_uids`, `expelled_uids`, `coords_refugis/all_refugis_coords` → lost updates. | `api/daos/refugi_lliure_dao.py:105-192,406-487`, `api/daos/renovation_dao.py:404-507`, `api/daos/refuge_visit_dao.py:250-385`, `api/daos/refuge_proposal_dao.py:62-209` | FET (patró) + INFERÈNCIA (carrera) |
| A4 | **RESOLT als callers** (esborrat de mitjans, avatar i rollbacks comproven el booleà; l'avatar antic s'esborra després del nou). `delete_file` retorna `False` en lloc de llançar → els rollbacks dins `try/except` dels callers són codi mort; un esborrat fallit a R2 es reporta com a èxit (objecte orfe). | `api/services/r2_media_service.py:339-341` | FET |
| A5 | Aprovar una proposta d'esborrat falla a mitges si totes les fotos del refugi eren d'experiències (claus llegides abans d'esborrar-les). | `api/daos/refuge_proposal_dao.py:409,486-498`, `api/daos/refugi_lliure_dao.py:344-404` | FET |
| A6 | Escriptures multi-document no atòmiques a fluxos llargs: esborrat d'usuari (9 passos de Firestore + R2 + PostgreSQL, vegeu U2), aprovació de propostes, experiència + media. | `apps/accounts/services.py: delete_user`, `api/daos/refuge_proposal_dao.py:231-556` | FET |

## Mitjà

| # | Problema | Evidència | Tipus |
|---|---|---|---|
| M1 | ~~PATCH d'usuari reseteja `language` a `'ca'`; el `validate()` "almenys un camp" mai falla.~~ **RESOLT (chunk 3)**: `UserUpdateSerializer` no té `default=` i exigeix almenys un camp (`{}` o camps desconeguts → 400; `username=''` és vàlid, D23). | `apps/accounts/serializers.py` | FET |
| M2 | PATCH de renovation amb només una data → `TypeError` (`date` vs `datetime`) → 500. | `api/controllers/renovation_controller.py:124-128`, `api/models/renovation.py:62-63` | FET |
| M3 | Esborrar un usuari decrementa `total_visitors` en 1 i no en `num_visitors`. | `api/daos/refuge_visit_dao.py:529` | FET |
| M4 | Visites duplicades possibles per (refugi, data): check-then-create sense transacció; `limit(1)` n'amaga una. | `api/controllers/refuge_visit_controller.py:105-147`, `api/daos/refuge_visit_dao.py:96-136` | INFERÈNCIA |
| M5 | **RESOLT al chunk 2**: `condition` es desa com a mitjana decimal i es mostra/filtra arrodonida half-to-even; el filtre accepta 0–3 (`core.round_half_even`). | `apps/refuges/selectors.py`, `apps/refuges/serializers.py` | FET |
| M6 | **Obsolet en part (chunk 2)**: `refugi_search` ja no existeix (la cerca no té cache), però actualitzar un refugi via proposta continua sense invalidar `user_refugis_info`, i ara l'actualització va a Firestore, no a PostgreSQL (R2). | `api/daos/refuge_proposal_dao.py:373-378` | FET |
| M7 | `doubt_detail` es desa amb dues formes (amb/sense `answers`). | `api/daos/doubt_dao.py:86-88` vs `129-153` | FET |
| M8 | Error path del PATCH d'experiència fa `None.to_dict()`. | `api/views/experience_views.py:310-312` | FET |
| M9 | Payload de proposta es desa en brut (sense coerció de tipus del serializer niat). | `api/serializers/refuge_proposal_serializer.py:160-166` | FET |
| M10 | **Parcialment RESOLT (chunk 3)**: l'esborrat d'usuari ja no retorna 404 per a qualsevol fallada (500 `{error, error_id}`; 404 només si no existeix). Continua pendent: el compte de Firebase Auth no s'esborra al backend. | `apps/accounts/views.py: UserDetailAPIView.delete`; cap `auth.delete_user` a `api/` | FET |
| M11 | Configuració insegura per defecte: `DEBUG=True`, `ALLOWED_HOSTS='*'`, CORS obert, CSRF middleware comentat. **Severitat mitjana: cal un default segur (`DEBUG=False`, `ALLOWED_HOSTS` explícit) abans de desplegar a Cloud Run**, on no hi ha l'`env/` ni el dashboard de Render que avui ho sobreescriuen (detectat per l'agent de seguretat del chunk 1). | `refugis_lliures/settings.py:45-47,72,169` | FET (valors en producció: NO VERIFICAT) |

## Baix

| # | Problema | Evidència | Tipus |
|---|---|---|---|
| B1 | `active_only` de `GET /refuges/{id}/renovations/` és paràmetre del mètode, no es llegeix de la query → sempre `False`. | `api/views/renovation_views.py` (`RefugeRenovationsAPIView.get`) | FET |
| B2 | **RESOLT al chunk 2**: la cerca per nom és parcial, sense accents ni majúscules, sobre nom i `surname` (`pg_trgm` + `core.norm_name`), i admet noms repetits. | `apps/refuges/selectors.py` | FET |
| B3 | ~~Qualsevol usuari autenticat pot llegir el perfil complet d'un altre (llistes, claus de fotos).~~ **RESOLT (chunk 3)**: el perfil d'un altre (també per a un admin, D23) és `{uid, username, avatar_metadata}`. | `apps/accounts/selectors.py: get_public_profile`, `serializers.py` | FET |
| B4 | **RESOLT al chunk 1 de la migració** (el client R2 de `RefugiLliureController` es crea sota demanda: el health check ja no depèn de `R2_*`, i comprova Postgres amb `SELECT 1`). Continua sense comprovar Redis (decisió: l'error de Redis s'empassa a propòsit). | `api/controllers/refugi_lliure_controller.py` (propietat `media_service`, `health_check`), `api/services/database_health.py` | FET |
| B5 | `get_visits_by_user` fa scan de tota la col·lecció `refuge_visits`; els documents processats mai s'esborren. | `api/daos/refuge_visit_dao.py:207-248` | FET |
| B6 | ~~DAOs de llistes d'usuari retornen tuples truthy → el controller no detecta fallades.~~ **RESOLT (chunk 3)**: `UserDAO` eliminat; els services llancen excepcions de domini. | `apps/accounts/services.py` | FET |
| B7 | **RESOLT** (models usen `logging`; `api/models/user.py` ja no existeix). Imports `from venv import logger` / `from asyncio.log import logger` als models. | `api/models/experience.py:9`, `api/models/refugi_lliure.py:4` | FET |
| B8 | Codis HTTP diferents dels documentats a Swagger (media DELETE 200 vs 204, favorits POST 200 vs 201, visita DELETE 200). | vistes corresponents | FET (segons informe de fluxos) |
| B9 | `verify_id_token` sense `check_revoked=True` → la branca `RevokedIdTokenError` mai s'activa. | `api/middleware/firebase_auth_middleware.py:60,86` | FET + INFERÈNCIA (SDK) |
| B10 | Lògica d'autenticació duplicada entre middleware i `FirebaseAuthentication`. | `api/middleware/firebase_auth_middleware.py`, `api/authentication.py` | FET |
| B11 | Dues rutes d'inicialització de Firebase amb criteris diferents (`firebase_config.py` usa el fitxer fix `env/firebase-service-account.json`; `FirestoreService._initialize_firebase` usa `settings.GOOGLE_APPLICATION_CREDENTIALS`). | `api/firebase_config.py:60`, `api/services/firestore_service.py:57` | FET |
| B12 | `settings.py` tria `.env.production` amb `RENDER`/`PRODUCTION` però `firebase_config` també considera `CI=true` com a producció → a CI s'usen settings de dev i Firebase de prod. | `refugis_lliures/settings.py:21`, `api/firebase_config.py:24-30` | FET |
| B13 | `tox.ini` declara `envlist=py39`; CI usa Python 3.10 amb `tox -e py`. | `tox.ini`, `.github/workflows/django.yml:16,31` | FET |
| B14 | Comentaris contradictoris d'horari del procés diari ("3:00 Madrid" a settings vs "3:00 UTC" al workflow). | `refugis_lliures/settings.py:276`, `.github/workflows/process-visits.yml:5-6` | FET |

## Nou deute (feature images)

| # | Problema | Evidència | Tipus |
|---|---|---|---|
| I1 | El processament de `confirm` és síncron dins la petició (1 worker a Render); vídeos grans o 10 fitxers poden superar el timeout de gunicorn. Moure'l a una cua/worker. | `MediaUploadController.confirm_upload_intents` | INFERÈNCIA |
| I2 | **RESOLT**: els camins multipart antics (`POST /api/refuges/{id}/media/`, `PATCH /api/users/{uid}/avatar/`, `files[]` a experiències) s'han eliminat (ara 405); l'única via de pujada és upload-intents, que exigeix `IsAgeConfirmed`. | `api/views/refugi_media_views.py`, `api/views/experience_views.py`, `api/views/user_views.py` | FET |
| I3 | En esborrar un usuari no s'anonimitza `reporter_uid` a `media_reports` ni s'esborren `moderation_notices`; `audit_logs` caduca per TTL (12 mesos). Cal decidir la retenció (obligació legal vs. dret a l'oblit); es resol al chunk 9/10. | `apps/accounts/services.py: delete_user` | FET |
| I4 | **RESOLT (chunk 3)**: `IsNotBlocked`/`IsAgeConfirmed`/`HasProfile` llegeixen `users.users` de PostgreSQL (una vegada per petició, sense cache): un bloqueig té efecte immediat. | `api/permissions.py: _request_account` | FET |
| I5 | `moderation_hash_blocklist` es carrega sencera (pHash) a memòria/cache: no escala a llistes grans; caldria un índex BK-tree o un servei extern. | `HashBlocklistProvider._load_phashes` | FET |

## Nou deute (migració Firestore → PostgreSQL, chunk 1: infraestructura)

| # | Problema | Evidència | Tipus |
|---|---|---|---|
| P1 | **Runtime sense GDAL/GEOS**: `django.contrib.gis` és sempre a `INSTALLED_APPS`, així que qualsevol procés Django (gunicorn a Render, `manage.py`, jobs d'Actions com `process-visits.yml`) necessita GDAL/GEOS al sistema. `build.sh`/`render.yaml` no els instal·len ni defineixen `DATABASE_URL_APP`; el pla és Cloud Run amb imatge Docker amb GDAL (fora de l'abast del chunk). Fins llavors el desplegament actual no arrencaria amb aquesta branca. `process-visits.yml` també caldria que instal·lés GDAL. | `refugis_lliures/settings.py` (`INSTALLED_APPS`), `render.yaml`, `build.sh`, `.github/workflows/process-visits.yml` | FET (config) + INFERÈNCIA (efecte a Render) |
| P2 | `GRANT CREATE ON SCHEMA public TO migrator` (PG15+) afegit a l'script local perquè Django creï `django_migrations` i les taules de `auth`/`admin`/`sessions`; **no s'ha verificat a Neon `dev`** (el *bootstrap* de §1.3 del disseny no ho incloïa). Cal fer-ho amb el rol propietari abans del primer `migrate --database=migrator`. | `scripts/dev/setup_local_postgres.sh`, `docs/design/postgres-schema.md` §1.3 | FET (local) + NO VERIFICAT (Neon) |
| P3 | Sense `DATABASE_URL_APP`/`TEST_DATABASE_URL_APP`, `default` cau a SQLite en silenci (només per carregar la configuració als tests sense BD): una instància mal configurada arrencaria i fallaria a la primera petició (hook de RLS) en lloc de fallar en arrencar. Millor fer-ho explícit quan hi hagi `DEBUG=False`/Render. | `refugis_lliures/settings.py` (`DATABASES`) | FET + INFERÈNCIA (efecte) |
| P4 | `ATOMIC_REQUESTS` només cobreix Postgres: les escriptures a Firestore/R2/Redis no es desfan si la petició acaba amb excepció. S'agreuja durant la migració (dominis a mitges entre Firestore i Postgres) i s'ha de tractar dins cada chunk (A6 continua obert per al que quedi a Firestore). | `refugis_lliures/settings.py` (`ATOMIC_REQUESTS`) | FET |
| P5 | Cost per petició: el hook fa un `set_config` (1 consulta) a **totes** les peticions, també a les anònimes i públiques, i `ATOMIC_REQUESTS` obre una transacció a Neon. Pot pesar en latència i en connexions del pooler mentre el domini encara és a Firestore. | `api/rls_hook.py`, `refugis_lliures/settings.py` | FET (patró) + INFERÈNCIA (impacte) |
| P6 | Validació només local: pooler PgBouncer i Postgres 17 de Neon no s'han provat (tests a Postgres local i CI `postgis:17-3.5` sense pooler); el PO ha d'executar `scripts/e2e/` contra Neon `dev` (D3 de `migration/DECISIONS_AUTONOMES.md`). | `docs/migration/PROGRESS.md` | NO VERIFICAT |
| P7 | Els tests dels chunks corren en local amb Python 3.13 (contenidor) i a CI amb 3.10; `tox.ini` declara `py39` (B13). Una divergència de versions podria amagar errors. | `.github/workflows/django.yml`, `tox.ini` | INFERÈNCIA |
| P8 | `django_db_setup` dona al rol `app` DML sobre les taules de Django de `public` només a la BD de proves (per a `force_authenticate` amb `auth.User`); a producció `app` no hi té grants (§7.2), així que codi que en depengui fallaria fora dels tests. | `conftest.py` (arrel) | FET |
| P9 | **Baixa**: `PUBLIC` té `TEMP` sobre la BD per defecte, de manera que `app` (i qualsevol rol) pot crear taules temporànies. Proposta: afegir `REVOKE TEMP ON DATABASE refugisdb FROM PUBLIC` al *bootstrap* del propietari (§1.3 del disseny) i a l'script local; `check_neon` la podria verificar. | `docs/design/postgres-schema.md` §1.3, `scripts/dev/setup_local_postgres.sh` | INFERÈNCIA (comportament per defecte de Postgres) |
| P10 | `check_neon` (comanda que usa taula temporal) i `django_db_setup` assumeixen que `TEMP` està permès; si s'aplica P9 caldrà `GRANT TEMP` només on calgui. | `api/management/commands/check_neon.py` | INFERÈNCIA |
| P11 | **Baixa**: `FirebaseAuthentication` (DRF) registra `str(e)` d'una excepció inesperada de verificació de token (`logger.error(f"Error verificant token: {str(e)}")`); el middleware ja només registra el tipus. | `api/authentication.py:69` | FET |

## Nou deute (migració Firestore → PostgreSQL, chunk 2: refugis) — estat intermedi fins als chunks 3–8

> Decisió del PO: s'accepta aquest estat intermedi fins que els dominis afectats es migrin. Tot el que segueix és **temporal** i desapareix amb el chunk indicat.

| # | Problema | Evidència | Tipus |
|---|---|---|---|
| R1 | **Dominis a Firestore llegeixen refugis d'un catàleg que ja no s'alimenta.** Experiències, dubtes, visites, propostes, pujada de mitjans i moderació comproven (els preferits/visitats d'usuari ja usen els refugis de PostgreSQL, chunk 3) l'existència del refugi i en llegeixen dades amb `RefugiLliureDAO` (col·lecció `data_refugis_lliures`). Els IDs de PostgreSQL (UUID v7) són nous i no coincideixen amb els de Firestore (**decisió del PO: no es migren dades d'usuari de Firestore; Postgres comença de zero**, només amb el catàleg), de manera que un `refuge_id` que el frontend obté de `/api/refuges/` pot donar «refugi no trobat» en aquells dominis. Es resol quan cada domini es migri (chunks 3–9). | `api/controllers/{doubt,experience,media_report,media_upload,refuge_proposal,refuge_visit}_controller.py` (`RefugiLliureDAO()`) | FET (codi) + INFERÈNCIA (efecte amb dades reals) |
| R2 | **Aprovar una proposta escriu només a Firestore**: crear/editar/esborrar un refugi via proposta (admins) no es veu a `/api/refuges/` (PostgreSQL) fins al chunk 8. | `api/daos/refuge_proposal_dao.py` (strategies, `RefugiLliureDAO`/`coords_refugis`) | FET |
| R3 | **Pujades noves de fotos no són visibles**: `upload-intents/confirm` publica a R2 i escriu `media_metadata` a Firestore; `GET /refuges/{id}/media/` i `images_metadata` llegeixen `refuges.refuge_media` (només hi ha mitjans si s'hi han inserit a mà). L'esborrat d'un mitjà no neteja `experiences.media_keys`; `users.uploaded_photos_keys` ja no existeix (el perfil el deriva de `refuge_media`, així que tampoc mostra les fotos noves escrites a Firestore). `MediaItem.experience_id` és sempre `null`. Fins al chunk 7. | `api/controllers/media_upload_controller.py` (`_publish_refuge_media`), `apps/refuges/services.py` | FET |
| R4 | ~~`visitors` (només admins) és sempre `[]`~~ **RESOLT (chunk 3)**: `get_visitor_uids` llegeix `users.user_visited_refuges` (RLS: només admin/sistema veuen totes les files). | `apps/refuges/selectors.py: get_visitor_uids` | FET |
| R5 | Codi legacy de refugis que encara es manté per als altres dominis: `RefugiLliureDAO`, `RefugiLliureController` (health + esborrat en bloc de mitjans), `RefugiLliureMapper`, models `Refugi*` i serializers de `api/`; prefixos de cache `refugi_detail`/`refugi_search`/`refugi_coords`. S'eliminen al chunk 11. | `api/daos/refugi_lliure_dao.py`, `api/controllers/refugi_lliure_controller.py`, `api/mappers/refugi_lliure_mapper.py` | FET |
| R6 | La política `media_insert` de `refuge_media` no té la clàusula `EXISTS(experiences)` ni hi ha trigger de cua d'R2 (`moderation.media_deletion_queue`) fins als chunks 7/9; l'esborrat de fitxers a R2 el fa el service directament. | `apps/refuges/migrations/0001_initial.py`, disseny §2.8 | FET |
| R7 | `load_refuges` encara no s'ha executat a Neon (cal el primer `migrate --database=migrator` i la càrrega única amb `migrator`). | [integrations/neon.md](integrations/neon.md) | NO VERIFICAT |
| R8 | ~~N+1 de `visitors` a la cerca d'un admin~~ **Resolt (chunk 3, 25/10)**: `selectors.get_visitor_uids_by_refuge(ids)` porta els visitants de tots els refugis de la cerca en 1 consulta (`IN` agrupat); el detall continua amb `get_visitor_uids` (1 consulta). | `apps/refuges/selectors.py`, `apps/refuges/views.py` | FET |
| R9 | Desfasament R2/commit a l'esborrat de mitjans: si R2 esborra el fitxer i després falla el `COMMIT` d'`ATOMIC_REQUESTS`, la fila apunta a un fitxer inexistent (rar). Es resol amb la cua `media_deletion_queue` + `on_commit` (chunk 9). | `apps/refuges/services.py: delete_media` | INFERÈNCIA |
| R10 | `creator_uid` als `MediaItem` el veu qualsevol usuari autenticat (contracte actual, però és un identificador personal). Valorar ocultar-lo o canviar-lo per `is_mine` en un chunk futur (decisió del PO). | `apps/refuges/serializers.py` | FET |
| R11 | Cerca: `name` sense `max_length` (una cadena molt llarga fa feina trigram innecessària; ho mitiga el límit de longitud d'URL) i `Prefetch('media')` amb `refuge_id IN (…)` de fins a 1.542 UUID en cerques amples (paginar si el catàleg creix). | `apps/refuges/serializers.py`, `apps/refuges/selectors.py` | INFERÈNCIA |
| R12 | ~~`load_refuges`: un enllaç repetit avorta amb `IntegrityError`~~ **Resolt (chunk 2, 25/10)**: amb la PK `url`, el loader detecta les URL repetides (dins i entre registres) abans d'escriure i dona un `CommandError` («enllaç repetit»). | `apps/refuges/management/commands/load_refuges.py` | FET |
| R13 | La RLS depèn de GUCs que qualsevol SQL executat com a `app` pot fixar (`set_config`): una injecció SQL futura equivaldria a escalar a sistema. Regla: cap SQL cru amb dades d'usuari. La vista `refuge_visit_totals` corre amb privilegis del propietari (sense `security_invoker`, intencionat: només agregats); la vista `refuge_map` s'elimina (decisió del PO, revisió del disseny 24/10). | `apps/core/rls.py`, `apps/refuges/migrations/0001_initial.py` | FET |
| R14 | ~~Pujar a Django 5.2 LTS i aplicar les PK compostes~~ **Resolt (chunk 2, 25/10)**: Django 5.2.18 + Python 3.14 + Postgres 18 (projecte Neon nou), `DEFAULT uuidv7()` i fora `api/utils/ids.py`. Les PK compostes de preferits, visitats, participants i expulsats de reformes i participants de visites `(visit_id, user_uid)` s'apliquen al crear aquestes taules (chunks 3–5); `refuge_visits` conserva `id` perquè hi apunta una FK. | `requirements.txt`, `docs/design/postgres-schema.md` §1.4 | FET |

## Nou deute (migració Firestore → PostgreSQL, chunk 3: usuaris) — estat intermedi fins als chunks 5, 7, 9 i 10

| # | Problema | Evidència | Tipus |
|---|---|---|---|
| U1 | **Comptadors del perfil propi via Firestore (D19)**: `num_shared_experiences` i `num_renovated_refuges` són 3 agregacions `count()` a Firestore a cada `GET/PATCH /users/{uid}/` propi; si Firestore falla, el perfil retorna 500 (acoblament de disponibilitat i cost). Es substitueix per SQL als chunks 5 (reformes) i 7 (experiències). | `apps/accounts/selectors.py: get_legacy_counts` | FET |
| U2 | **Esborrat d'usuari provisional (D21/D22)**: Firestore (9 passos) → R2 → `DELETE users.users` sense atomicitat entre magatzems; un fallada deixa passos aplicats (reintentable). No s'esborra `media_reports`/`moderation_notices` ni el compte de Firebase Auth (I3, M10). El chunk 10 el substitueix per un procediment únic i la cua `media_deletion_queue`. | `apps/accounts/services.py: delete_user` | FET |
| U3 | **El job diari de visites i PostgreSQL**: `process-visits.yml` ja declara `DATABASE_URL_APP` (secret de GitHub que **el PO ha de crear**; sense ell el job cau a SQLite i falla). El controller encara fa `continue` (sense afegir res a `user_visited_refuges`) si el refugi **legacy** de Firestore no existeix (entorn nou amb `data_refugis_lliures` buit). Es resol al chunk 4 (visites a PostgreSQL). | `.github/workflows/process-visits.yml`, `api/controllers/refuge_visit_controller.py` | PARCIAL |
| U4 | **Escriptures d'usuari amb `system_context()` (D20)**: moderació (strikes/bloqueig), avatar des de pujades i `add_visited` del job diari salten la RLS; la comprovació d'autorització és responsabilitat de qui crida i només la cobreixen els tests dels controllers. Revisar quan es migrin moderació i pujades (chunk 9). | `apps/accounts/services.py` | FET |
| U5 | ~~`manage_admins.py add` no atòmic~~ **Resolt (chunk 3, 25/10)**: primer crea la fila d'usuari i el perfil (idempotent) i després posa el claim; si falla el perfil no hi ha cap admin sense perfil. `remove` no toca PostgreSQL. | `scripts/manage_admins.py` | FET |
| U6 | `UserModerationNoticesAPIView` i `UserVisitsAPIView` continuen a Firestore però colguen sota `users/`; el nom `api/views/user_views.py` només conté la de moderació. Es mou/elimina amb els chunks 9 i 6. | `api/views/user_views.py`, `api/views/refuge_visit_views.py` | FET |
| U7 | **Evasió del bloqueig esborrant el compte**: un usuari bloquejat pot fer `DELETE /users/{uid}/` i tornar a fer `POST /users/` amb el mateix UID; perd `is_blocked` i `moderation_strikes` (ja passava amb Firestore). Solució possible: una llista de denegació d'UID bloquejats que sobrevisqui a l'esborrat (decisió de producte i RGPD: base legal i termini de conservació). **Pendent del PO.** | `apps/accounts/services.py: delete_user`, `create_user` | OBERT |

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
