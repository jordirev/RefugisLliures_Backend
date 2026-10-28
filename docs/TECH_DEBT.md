# Deute tècnic detectat

> **[FET]** comprovat al codi · **[INFERÈNCIA]** deducció (carreres, comportament de llibreries) · **[NO VERIFICAT]** depèn de config externa.
> Ordenat per severitat. Els punts marcats **RESOLT** s'han corregit a la feature *images* (branca `feature/images`).

## Crític

| # | Problema | Evidència | Tipus |
|---|---|---|---|
| C1 | **(Parcialment RESOLT: experiències —chunk 7— i dubtes/respostes —chunk 6— comproven la propietat al service, 403 `not_owner` + RLS; la resta, pendent)** **Permisos d'objecte inoperants**: `has_object_permission` mai s'executa (no s'executarà mai a cap vista). Abans qualsevol usuari autenticat podia fer PATCH/DELETE de qualsevol experiència, dubte o resposta; ara les apps migrades ho comproven al service i la RLS ho reforça. Queda `IsRenovationCreator`/`IsOwnerOrReadOnly` com a codi mort a `api/permissions.py` (`IsExperienceCreator` s'ha eliminat al chunk 7). | `api/permissions.py`; cap `check_object_permissions` a `api/`; `apps/experiences/services.py: _check_owner` | FET |
| C2 | **RESOLT (chunk 8)**: la doble aprovació d'una proposta era possible per la cache trencada. Ara l'aprovació és una transacció que bloqueja la proposta `FOR UPDATE … WHERE status = 'pending'` (`apps/proposals/services.py`); no hi ha cache de propostes. | `apps/proposals/services.py: approve_proposal`, `apps/proposals/tests/test_concurrency.py` | FET |

## Alt

| # | Problema | Evidència | Tipus |
|---|---|---|---|
| A1 | ~~Renovation amb `ini_date == fin_date` passa el serializer, es desa a Firestore i després el model peta → la llista d'actives queda buida per a tothom~~ **RESOLT (chunk 5, 26/10)**: serializer, model i `CHECK renovations_dates_ck` (`ini_date <= fin_date`) coincideixen; una reforma d'un dia és vàlida. | `apps/renovations/serializers.py`, `apps/renovations/models.py`, `apps/renovations/tests/test_models_constraints.py` | FET |
| A2 | **RESOLT** (claus UUID; `upload_file` ignora `filename`). Claus R2 amb el nom original del fitxer → col·lisions i sobreescriptura entre usuaris; `creator_uid` del media canvia de mans. | `api/services/r2_media_service.py:196-203` + crides amb `filename=file.name` | FET |
| A3 | **Parcialment RESOLT** (reformes, chunk 5: `participants`/`expelled` són taules amb PK composta i `INSERT … ON CONFLICT DO NOTHING`; `media_metadata` amb FieldPath/DELETE_FIELD; `uploaded_photos_keys` i les llistes de preferits/visitats ja no són arrays: chunk 3; la resta pendent). Read-modify-write sense transacció sobre `media_metadata`, `visitors` (refugi legacy; el de visita, resolt al chunk 4), `coords_refugis/all_refugis_coords` → lost updates. | `api/daos/refugi_lliure_dao.py:105-192,406-487`, `api/daos/refuge_proposal_dao.py:62-209` | FET (patró) + INFERÈNCIA (carrera) |
| A4 | **RESOLT als callers** (esborrat de mitjans, avatar i rollbacks comproven el booleà; l'avatar antic s'esborra després del nou). `delete_file` retorna `False` en lloc de llançar → els rollbacks dins `try/except` dels callers són codi mort; un esborrat fallit a R2 es reporta com a èxit (objecte orfe). | `api/services/r2_media_service.py:339-341` | FET |
| A5 | **RESOLT (chunk 8)**: aprovar un `delete` fa un sol `DELETE` del refugi (la BD cascadeja experiències, mitjans, dubtes…), llegeix les claus d'R2 abans amb `system_context()` i, si R2 falla, desfà tot (500). | `apps/proposals/services.py: _apply_delete`, `apps/proposals/tests/test_refuge_deletion.py` | FET |
| A6 | Escriptures multi-document no atòmiques a fluxos llargs: esborrat d'usuari (R2 + PostgreSQL + Firebase Auth, vegeu U2). (Experiència + mitjans, i l'aprovació de propostes —chunk 8—, ja són atòmiques: `DELETE` + R2 en una sola transacció.) | `apps/accounts/services.py: delete_user` | FET |

## Mitjà

| # | Problema | Evidència | Tipus |
|---|---|---|---|
| M1 | ~~PATCH d'usuari reseteja `language` a `'ca'`; el `validate()` "almenys un camp" mai falla.~~ **RESOLT (chunk 3)**: `UserUpdateSerializer` no té `default=` i exigeix almenys un camp (`{}` o camps desconeguts → 400; `username=''` és vàlid, D23). | `apps/accounts/serializers.py` | FET |
| M2 | ~~PATCH de renovation amb només una data → `TypeError` (`date` vs `datetime`) → 500~~ **RESOLT (chunk 5, 26/10)**: `services.update_renovation` combina les dates enviades amb les desades i dona 400 si `ini > fin` (i 409 si se solapa). | `apps/renovations/services.py: update_renovation` | FET |
| M3 | ~~Esborrar un usuari decrementa `total_visitors` en 1 i no en `num_visitors`~~ **RESOLT (chunk 4)**: el total ja no es desa, surt de la vista `refuge_visit_totals` i les files de `refuge_visit_participants` cauen en cascada. | `apps/visits/migrations/0001_initial.py`, `apps/visits/tests/test_user_deletion.py` | FET |
| M4 | ~~Visites duplicades possibles per (refugi, data)~~ **RESOLT (chunk 4)**: `UNIQUE (refuge_id, visit_date)` + `INSERT … ON CONFLICT DO NOTHING` + `SELECT`; test de concurrència (`slow`). | `apps/visits/services.py`, `apps/visits/tests/test_concurrency.py` | FET |
| M5 | **RESOLT al chunk 2**: `condition` es desa com a mitjana decimal i es mostra/filtra arrodonida half-to-even; el filtre accepta 0–3 (`core.round_half_even`). | `apps/refuges/selectors.py`, `apps/refuges/serializers.py` | FET |
| M6 | **Obsolet en part (chunk 2)**: `refugi_search` ja no existeix (la cerca no té cache), però actualitzar un refugi via proposta continua sense invalidar `user_refugis_info`, i ara l'actualització va a Firestore, no a PostgreSQL (R2). | `api/daos/refuge_proposal_dao.py:373-378` | FET |
| M7 | ~~`doubt_detail` es desa amb dues formes~~ **RESOLT (chunk 6)**: els dubtes ja no usen cache. | `apps/doubts/selectors.py` | FET |
| M8 | **RESOLT (chunk 7)**: el PATCH d'experiència (`apps/experiences/views.py`) ja no fa `None.to_dict()`; el codi de `api/views/experience_views.py` ha desaparegut. | `apps/experiences/views.py` | FET |
| M9 | **RESOLT (chunk 8)**: el payload es desa amb només les claus enviades i els tipus coercits pel serializer (`"1200"` -> `1200`), i la BD ho reforça amb `CHECK`s `jsonb`. | `apps/proposals/serializers.py`, `apps/proposals/migrations/0001_initial.py` | FET |
| M10 | ~~L'esborrat d'usuari retornava 404 per a qualsevol fallada i no esborrava el compte de Firebase Auth.~~ **RESOLT**: 500 `{error, error_id}` (chunk 3) i el backend esborra el compte de Firebase Auth com a últim pas (U7, 26/10). | `apps/accounts/services.py: delete_user` | FET |
| M11 | Configuració insegura per defecte: `DEBUG=True`, `ALLOWED_HOSTS='*'`, CORS obert, CSRF middleware comentat. **Severitat mitjana: cal un default segur (`DEBUG=False`, `ALLOWED_HOSTS` explícit) abans de desplegar a Cloud Run**, on no hi ha l'`env/` ni el dashboard de Render que avui ho sobreescriuen (detectat per l'agent de seguretat del chunk 1). | `refugis_lliures/settings.py:45-47,72,169` | FET (valors en producció: NO VERIFICAT) |

## Baix

| # | Problema | Evidència | Tipus |
|---|---|---|---|
| B1 | ~~`active_only` de `GET /refuges/{id}/renovations/` no es llegia de la query~~ **RESOLT (chunk 5, D32)**: la vista llegeix `?active_only=` (`true`/`True`/`1` → només vigents; per defecte, totes). | `apps/renovations/views.py: RefugeRenovationsAPIView`, `selectors.list_refuge_renovations` | FET |
| B2 | **RESOLT al chunk 2**: la cerca per nom és parcial, sense accents ni majúscules, sobre nom i `surname` (`pg_trgm` + `core.norm_name`), i admet noms repetits. | `apps/refuges/selectors.py` | FET |
| B3 | ~~Qualsevol usuari autenticat pot llegir el perfil complet d'un altre (llistes, claus de fotos).~~ **RESOLT (chunk 3)**: el perfil d'un altre (també per a un admin, D23) és `{uid, username, avatar_metadata}`. | `apps/accounts/selectors.py: get_public_profile`, `serializers.py` | FET |
| B4 | **RESOLT al chunk 1 de la migració** (el client R2 de `RefugiLliureController` es crea sota demanda: el health check ja no depèn de `R2_*`, i comprova Postgres amb `SELECT 1`). Continua sense comprovar Redis (decisió: l'error de Redis s'empassa a propòsit). | `api/controllers/refugi_lliure_controller.py` (propietat `media_service`, `health_check`), `api/services/database_health.py` | FET |
| B5 | ~~`get_visits_by_user` feia scan de tota la col·lecció; les visites processades no s'esborraven~~ **RESOLT (chunk 4)**: índex `(user_uid) INCLUDE (visit_id, num_visitors)`; el job esborra les buides i purga les de més de 12 mesos. | `apps/visits/selectors.py`, `apps/visits/services.py` | FET |
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
| I1 | El processament de `confirm` és síncron dins la petició (1 worker a Render); vídeos grans o 10 fitxers poden superar el timeout de gunicorn. Moure'l a una cua/worker. | `apps/uploads/services.py: confirm_upload_intents` | INFERÈNCIA |
| I2 | **RESOLT**: els camins multipart antics (`POST /api/refuges/{id}/media/`, `PATCH /api/users/{uid}/avatar/`, `files[]` a experiències) s'han eliminat (ara 405); l'única via de pujada és upload-intents, que exigeix `IsAgeConfirmed`. | `apps/uploads`, `apps/experiences/views.py` (només JSON) | FET |
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
| R1 | **Dominis a Firestore llegeixen refugis d'un catàleg que ja no s'alimenta.** Des del chunk 8 només queda la **moderació** (denúncies: `MediaReportController` comprova el refugi amb `RefugiLliureDAO`, col·lecció `data_refugis_lliures`); propostes, preferits/visitats, visites, reformes, dubtes, experiències i pujades usen els refugis de PostgreSQL. Els IDs de PostgreSQL (UUID v7) no coincideixen amb els de Firestore (**decisió del PO: no es migren dades d'usuari de Firestore**), de manera que un `refuge_id` de `/api/refuges/` pot donar «refugi no trobat» a les denúncies. Es resol al chunk 9. | `api/controllers/media_report_controller.py` (`RefugiLliureDAO()`) | FET (codi) + INFERÈNCIA (efecte amb dades reals) |
| R2 | **RESOLT (chunk 8)**: aprovar una proposta escriu a PostgreSQL (`refuges`, `refuge_amenities`, `refuge_links`) i el canvi es veu a `/api/refuges/`. | `apps/proposals/services.py` | FET |
| R3 | **RESOLT (chunk 7)**: les pujades noves (`upload-intents/confirm`) publiquen a `refuges.refuge_media` (PostgreSQL), per tant surten a `GET /refuges/{id}/media/`, `images_metadata` i `uploaded_photos_keys`; `MediaItem.experience_id` ja s'omple i `media_keys` ha desaparegut. | `apps/uploads/services.py` | FET |
| R4 | ~~`visitors` (només admins) és sempre `[]`~~ **RESOLT (chunk 3)**: `get_visitor_uids` llegeix `users.user_visited_refuges` (RLS: només admin/sistema veuen totes les files). | `apps/refuges/selectors.py: get_visitor_uids` | FET |
| R5 | Codi legacy de refugis que encara es manté perquè en depenen la **moderació** i el **health check**: `RefugiLliureDAO` (`MediaReportController`), `RefugiLliureController` (`HealthCheckAPIView`, esborrat en bloc de mitjans), `RefugiLliureMapper`, models `Refugi*` i serializers de `api/`; prefixos de cache `refugi_detail`/`refugi_search`/`refugi_coords`. S'eliminen al chunk 9 (moderació) i 11 (health check). | `api/daos/refugi_lliure_dao.py`, `api/controllers/refugi_lliure_controller.py`, `api/mappers/refugi_lliure_mapper.py` | FET |
| D1 | **RESOLT (chunk 8)**: s'han eliminat `DoubtController`, `DoubtDAO`, `DoubtMapper`, el model `Doubt` de `api/` i els seus tests legacy (només els usava `RefugeProposalDAO`). | — | FET |
| D2 | **Baixa**: cap límit de respostes per dubte ni paginació de `GET /api/doubts/?refuge_id=` (revisió de seguretat del chunk 6: 5000 respostes ≈ 5 s de llistat). Un usuari no bloquejat amb edat confirmada pot fer créixer un dubte indefinidament. Proposta: paginar o limitar (decisió del PO). | `apps/doubts/selectors.py: list_doubts` | FET |
| R6 | **Parcialment RESOLT (chunk 7)**: la política `media_insert` de `refuge_media` ja té la clàusula `EXISTS(experiences)` (`refuges.0002`). Falta el trigger de cua d'R2 (`moderation.media_deletion_queue`, chunk 9/10): l'esborrat de fitxers a R2 el fan els services directament. | `apps/refuges/migrations/0002_refuge_media_experience.py`, disseny §2.8 | FET |
| R7 | `load_refuges` encara no s'ha executat a Neon (cal el primer `migrate --database=migrator` i la càrrega única amb `migrator`). | [integrations/neon.md](integrations/neon.md) | NO VERIFICAT |
| R8 | ~~N+1 de `visitors` a la cerca d'un admin~~ **Resolt (chunk 3, 25/10)**: `selectors.get_visitor_uids_by_refuge(ids)` porta els visitants de tots els refugis de la cerca en 1 consulta (`IN` agrupat); el detall continua amb `get_visitor_uids` (1 consulta). | `apps/refuges/selectors.py`, `apps/refuges/views.py` | FET |
| R9 | Desfasament R2/commit a l'esborrat de mitjans: si R2 esborra el fitxer i després falla el `COMMIT` d'`ATOMIC_REQUESTS`, la fila apunta a un fitxer inexistent (rar). Es resol amb la cua `media_deletion_queue` + `on_commit` (chunk 9). | `apps/refuges/services.py: delete_media` | INFERÈNCIA |
| R10 | `creator_uid` als `MediaItem` el veu qualsevol usuari autenticat (contracte actual, però és un identificador personal). Valorar ocultar-lo o canviar-lo per `is_mine` en un chunk futur (decisió del PO). | `apps/refuges/serializers.py` | FET |
| R11 | Cerca: `name` sense `max_length` (una cadena molt llarga fa feina trigram innecessària; ho mitiga el límit de longitud d'URL) i `Prefetch('media')` amb `refuge_id IN (…)` de fins a 1.542 UUID en cerques amples (paginar si el catàleg creix). | `apps/refuges/serializers.py`, `apps/refuges/selectors.py` | INFERÈNCIA |
| R12 | ~~`load_refuges`: un enllaç repetit avorta amb `IntegrityError`~~ **Resolt (chunk 2, 25/10)**: amb la PK `url`, el loader detecta les URL repetides (dins i entre registres) abans d'escriure i dona un `CommandError` («enllaç repetit»). | `apps/refuges/management/commands/load_refuges.py` | FET |
| R13 | La RLS depèn de GUCs que qualsevol SQL executat com a `app` pot fixar (`set_config`): una injecció SQL futura equivaldria a escalar a sistema. Regla: cap SQL cru amb dades d'usuari. La vista `refuge_visit_totals` corre amb privilegis del propietari (sense `security_invoker`, intencionat: només agregats); la vista `refuge_map` s'elimina (decisió del PO, revisió del disseny 24/10). | `apps/core/rls.py`, `apps/refuges/migrations/0001_initial.py` | FET |
| R14 | ~~Pujar a Django 5.2 LTS i aplicar les PK compostes~~ **Resolt (chunk 2, 25/10)**: Django 5.2.18 + Python 3.14 + Postgres 18 (projecte Neon nou), `DEFAULT uuidv7()` i fora `api/utils/ids.py`. Les PK compostes de preferits, visitats, participants i expulsats de reformes i participants de visites `(visit_id, user_uid)` s'apliquen al crear aquestes taules (chunks 3–5); `refuge_visits` conserva `id` perquè hi apunta una FK. | `requirements.txt`, `docs/design/postgres-schema.md` §1.4 | FET |

## Nou deute (migració Firestore → PostgreSQL, chunk 3: usuaris) — estat intermedi fins als chunks 8, 9 i 10

| # | Problema | Evidència | Tipus |
|---|---|---|---|
| U1 | **RESOLT (chunk 7)**: `num_shared_experiences` és un `count(*)` SQL (una sola consulta amb `num_renovated_refuges`); el perfil propi ja no depèn de Firestore. | `apps/accounts/selectors.py: get_legacy_counts` | FET |
| U2 | **Esborrat d'usuari provisional (D21/D22)**: R2 (cap pas de Firestore des del chunk 8: les propostes es conserven anonimitzades per la FK `SET NULL` i el `comment` s'anul·la dins la mateixa transacció; `_firestore_steps` és buida) → `DELETE users.users` sense atomicitat entre magatzems; un fallada deixa passos aplicats (reintentable). No s'esborra `media_reports`/`moderation_notices` (I3); el compte de Firebase Auth sí (últim pas, U7). Finestra residual: si el `COMMIT` falla després d'esborrar el compte, queden dades sense compte. El chunk 10 el substitueix per un procediment únic i la cua `media_deletion_queue`. | `apps/accounts/services.py: delete_user` | FET |
| U3 | **El job diari de visites i PostgreSQL (ajornat pel PO, 26/10)**: `process-visits.yml` declara `DATABASE_URL_APP`, però el secret de GitHub **no es crea de moment** (D29): el PO pot moure els jobs a Cloud Run i llavors el workflow no caldria. Mentre no hi sigui, el job cau a SQLite i falla (ara amb codi ≠ 0, D28). Les visites ja són a PostgreSQL (chunk 4) i el `continue` per refugi legacy ha desaparegut. Abans de posar el job en producció: crear el secret **o** moure'l a Cloud Run. | `.github/workflows/process-visits.yml`, `apps/visits/management/commands/process_yesterday_visits.py` | AJORNAT |
| U4 | **Escriptures d'usuari amb `system_context()` (D20)**: moderació (strikes/bloqueig), avatar des de pujades i `add_visited` del job diari salten la RLS; la comprovació d'autorització és responsabilitat de qui crida i només la cobreixen els tests dels controllers. Revisar quan es migrin moderació i pujades (chunk 9). | `apps/accounts/services.py` | FET |
| U5 | ~~`manage_admins.py add` no atòmic~~ **Resolt (chunk 3, 25/10)**: primer crea la fila d'usuari i el perfil (idempotent) i després posa el claim; si falla el perfil no hi ha cap admin sense perfil. `remove` no toca PostgreSQL. | `scripts/manage_admins.py` | FET |
| U6 | `UserModerationNoticesAPIView` continua a Firestore però penja de `users/`; el nom `api/views/user_views.py` només la conté a ella (`UserVisitsAPIView` ja és a `apps/visits`, chunk 4). Es mou amb el chunk 9. | `api/views/user_views.py` | FET |
| V1 | **Baixa (revisió de seguretat, chunk 4)**: `GRANT UPDATE` sobre `activity.refuge_visit_participants` cobreix totes les columnes; la RLS impedeix tocar files d'altri i cap endpoint ho explota, però es podria limitar a `GRANT UPDATE (num_visitors)` com a defensa en profunditat (cal una migració nova `visits.0002`). | `apps/visits/migrations/0001_initial.py` | FET |
| U7 | ~~**Evasió del bloqueig esborrant el compte**~~ **RESOLT (26/10, decisió del PO)**. Camí 1 (mateix compte via API): `DELETE /users/{uid}/` esborra ara també el compte de Firebase Auth (últim pas, dins el *savepoint* del `DELETE users.users`, D24) i `POST /users/` respon 401 `account_not_found` si el compte del token ja no existeix (token vigent fins a 1 h, D25): no es pot tornar amb el mateix UID. El frontend ja no fa `user.delete()`: reautentica, crida el DELETE i fa `signOut` local; si el backend falla, mostra un error i no esborra res (branca `feature/esborrat-compte-backend` del frontend, **s'ha de desplegar alhora** que aquest backend). Camí 2 (compte nou amb un altre email): **acceptat**; no es desa cap hash d'email (és dada personal pseudonimitzada i caldria justificar-ne la retenció després d'un esborrat), ni telèfon (cost) ni identificador de dispositiu (reiniciable i intrusiu). L'abús persistent es tracta bloquejant el compte nou quan reincideix. | `apps/accounts/services.py: delete_user`, `create_user`; frontend `src/services/AuthService.ts: deleteAccount` | FET |

## Nou deute (migració Firestore → PostgreSQL, chunk 5: reformes)

| # | Problema | Evidència | Tipus |
|---|---|---|---|
| R15 | **RESOLT (chunk 8)**: s'han eliminat `RenovationController`, `RenovationDAO`, `RenovationMapper`, el model `Renovation` (dataclass) i `IsRenovationCreator` (només l'usava `RefugeProposalDAO`). Queden a `api/services/cache_service.py` els TTL morts `renovation_*`, `doubt_*` i `proposal_*` (neteja del chunk 11). | — | FET |

## Nou deute (migració Firestore → PostgreSQL, chunk 7: experiències i pujades)

| # | Descripció | On | Estat |
|---|---|---|---|
| R16 | **Moderació encara a Firestore i buida de mitjans d'experiència**: la hash-blocklist, les denúncies, els avisos i `MediaReportController._hold_media` continuen a Firestore (chunk 9); `_hold_media` i `RefugiLliureController.delete_multiple_refugi_media` ja no toquen les experiències (el `ExperienceDAO` s'ha eliminat: `media_keys` ja no existeix, el vincle és `refuge_media.experience_id`). El chunk 9 ha de reescriure la retenció/denúncia sobre `refuges.refuge_media` (inclosos els mitjans d'experiència) i la cua d'R2 (`fn_media_enqueue_r2`). | `api/controllers/media_report_controller.py`, `api/controllers/refugi_lliure_controller.py`, `apps/uploads/services.py: _handle_moderation_block` | FET |
| R17 | **RESOLT (chunk 8)**: `DeleteRefugeStrategy` ha desaparegut; l'esborrat del refugi per proposta és un sol `DELETE` amb cascades a la BD. | `apps/proposals/services.py` | FET |
| R18 | **Purga d'intents sense planificar**: la comanda `python manage.py purge_upload_intents` (horària, §8.3) existeix però no hi ha cap workflow de GitHub Actions que la cridi; cal afegir-la al CI/cron del desplegament. Mentrestant els intents caducats només ocupen files (el lifecycle de `quarantine/` a R2 ja esborra els fitxers). | `apps/uploads/management/commands/purge_upload_intents.py` | FET |
| R19 | ~~Sense quota d'intents de pujada per usuari~~ **RESOLT (27/10, decisió del PO)**: com a molt 40 intents `pending` sense caducar per usuari (comptant els fitxers de la petició); si se supera, 429 `too_many_pending_uploads`. Bloqueig assessor per usuari contra peticions simultànies. El *rate limit* per temps queda per més endavant. | `apps/uploads/services.py: _check_pending_quota`, `apps/uploads/tests/test_pending_quota.py` | FET |
| R20 | **Càrregues massives d'experiències disparen el *trigger* de condició fila a fila** (~1,5k files/s: una càrrega de 30k va arribar al `statement_timeout`). Una importació futura ha de desactivar `experiences_condition_ins` com a `migrator` i escriure les mitjanes directament (com §9 per als refugis). | `apps/experiences/migrations/0001_initial.py` | FET (EXPLAIN del revisor SQL) |
| R21 | **Esborrat d'R2 dins la transacció** de `delete_experience` (manté els bloquejos de l'experiència i els mitjans durant la crida de xarxa) i `SET CONSTRAINTS ALL IMMEDIATE` (experiències, pujades, dubtes) en lloc del nom de la FK com a reformes. Acceptable amb el volum previst; es revisa al chunk 9 (`media_deletion_queue`). | `apps/experiences/services.py`, `apps/uploads/services.py`, `apps/doubts/services.py` | FET |

## Nou deute (migració Firestore → PostgreSQL, chunk 8: propostes)

| # | Descripció | On | Estat |
|---|---|---|---|
| P5 | **Esborrat d'R2 dins la transacció d'aprovació d'un `delete`** (com R21): manté els bloquejos de la proposta i del refugi durant la crida de xarxa; les miniatures es borren després del `COMMIT` (si fallen només queden fitxers orfes). El chunk 9 (`media_deletion_queue`) ho substitueix. Els fitxers d'intents de pujada pendents (`upload_intents`) d'un refugi esborrat cauen per cascada a la BD però no s'esborren d'R2 aquí. | `apps/proposals/services.py: _apply_delete` | FET |
| P6 | **Duplicats només contra refugis existents**: dues propostes `create` pendents del mateix refugi no es detecten entre elles (decisió del PO: només refugis). El límit és de 20 candidats per resposta. | `apps/proposals/services.py: find_possible_duplicates` | FET |
| P7 | Els errors de validació del payload (`details.payload`) segueixen el format de DRF (llista d'un missatge per als errors de `validate()`, diccionari per camp per als del serializer niat), com abans. | `apps/proposals/serializers.py` | FET |
| P8 | Neteja pendent del chunk 11: TTL morts de `cache_service` (`proposal_*`, `doubt_*`, `renovation_*`) i el pas buit `_firestore_steps` d'`apps.accounts.services`. | `api/services/cache_service.py`, `apps/accounts/services.py` | FET |


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
