# Migració Firestore → PostgreSQL (Neon) — estat

> Document viu mantingut per l'orquestrador. Si la feina s'atura, un altre LLM ha de poder continuar llegint només aquest fitxer, [`PLAN.md`](PLAN.md) i els docs enllaçats.
> Mai s'escriuen credencials aquí: les variables `DATABASE_URL_APP`, `DATABASE_URL_MIGRATOR` i `R2_*` es llegeixen de l'entorn.

## Documents d'entrada
- [`PLAN.md`](PLAN.md) — pla aprovat (decisions, metodologia, chunks).
- [`arquitectura-neon-cloudrun-upstash.md`](arquitectura-neon-cloudrun-upstash.md) — document d'arquitectura (abast acordat: només capa de dades).
- [`uml-conceptual.md`](uml-conceptual.md) — UML conceptual de partida (incomplet).
- `../design/postgres-schema.md` — disseny físic de la BD (pas 0, en curs).

## Branques
- Integració: `migration` (inclou `develop` a `e5a56e6`). Chunks: `migracio/<chunk>` → PR a `migration`. Final: una PR `migration` → `develop` que fusiona l'usuari.

## Estat dels chunks
| # | Chunk | Branca | Estat | Notes |
|---|---|---|---|---|
| 0 | Disseny BD | `migracio/disseny-bd` | fet | `docs/design/postgres-schema.md` tancat (`e611fe3`), PR a `migration` |
| 1 | Infraestructura | `migracio/infraestructura` | fet (PR [#42](https://github.com/jordirev/RefugisLliures_Backend/pull/42) fusionada, `7d9073f`) | 1666 tests; D9 confirmada a Neon `dev` |
| 2 | Refugis | `migracio/refugis` | tests en curs | |
| 3 | Usuaris | `migracio/usuaris` | pendent | |
| 4 | Visites | `migracio/visites` | pendent | paral·lel amb 5, 6 |
| 5 | Renovations | `migracio/renovations` | pendent | paral·lel amb 4, 6 |
| 6 | Dubtes | `migracio/dubtes` | pendent | paral·lel amb 4, 5 |
| 7 | Experiències + pujades | `migracio/experiencies` | pendent | |
| 8 | Propostes | `migracio/propostes` | pendent | |
| 9 | Moderació + audit | `migracio/moderacio` | pendent | |
| 10 | Esborrat d'usuari | `migracio/esborrat-usuari` | pendent | |
| 11 | Neteja Firestore/cache | `migracio/neteja` | pendent | |

## Registre
- 2026-10-23 — Pla aprovat. Branca `migration` posada al dia amb `develop`. Iniciat el pas 0.
- 2026-10-23 — Decisió: PK subrogades com a UUID v7 (comunicada a l’agent de disseny).
- 2026-10-23 — Esborrany del disseny físic acabat (24 taules, 3 vistes, 6 schemas). Pendent: resposta del PO als dubtes de §11 abans de tancar el chunk 0.
- 2026-10-24 — PO ha respost els dubtes de §11 (vegeu PLAN.md, "Decisions sobre els dubtes"). Condition passa a ser atribut de l’experiència (sense taula de vots); llavor amb `puntua_refugi`, n=0. Tests locals: Postgres 16 natiu + PostGIS (apt), no Docker (daemon no disponible). Agent de disseny revisant el doc.

- 2026-10-24 — Disseny tancat (N1–N3 resolts pel PO). El PO delega les decisions: registre a [`DECISIONS_AUTONOMES.md`](DECISIONS_AUTONOMES.md).

- 2026-10-24 — Chunk 1: tests escrits i fallant pels motius esperats (commits `51c925b`, `7b9d666`). Línia base: 1331 passen; ara 1339 passen, 130 fallen, 115 errors (fixtures de BD: `default` encara és sqlite). La sessió cloud s'atura per passar a una sessió local (accés a Neon).

- 2026-10-24 — Sessió local (Windows). Tests dins d'un contenidor Linux amb GDAL contra `rl-postgres` (`postgis/postgis:17-3.5`); línia base reproduïda (1339/130/115). El PO ha retirat D6 (sense workflow contra Neon). **Bootstrap SQL de Neon `dev` (§1.3: `btree_gist`, `GRANT CREATE`, timeouts) executat pel PO amb el rol propietari** (tanca D4). Implementador del chunk 1 en marxa.
- 2026-10-24 — Chunk 1 implementat (`d32a301`): 1590 passen, 0 fallen, 0 errors (verificat per l'orquestrador). Desviacions: (a) `GRANT CREATE ON SCHEMA public TO migrator` necessari perquè Django creï `django_migrations` i les taules de `auth`/`admin`/`sessions` (PG15+); afegit a l'script local, **cal verificar-ho a Neon `dev` abans del primer `migrate`**; (b) `django.contrib.gis` sempre actiu: el runtime necessita GDAL/GEOS (Render/Cloud Run, fora de l'abast; queda com a pendent de desplegament); (c) middleware `HealthDatabaseErrorMiddleware` (503 a `/api/health/` si Postgres cau abans de la vista, per `ATOMIC_REQUESTS`). Àlies `neon`/`neon_migrator` i `NEON_USE_POSTGIS_ENGINE` eliminats (ara `default`/`migrator`). Tests executats amb un contenidor Linux (`python:3.13` + GDAL) perquè Windows no té GDAL.
- 2026-10-24 — Revisor (`fe2278b`, `7c6e026`: `connect_timeout=10`, guarda de tests només locals, CI que falla en veu alta, `check_neon` comprova el bootstrap, health sense `str(e)`), seguretat (`52e3988`, `327631a`: guard de l'emulador per plataforma i host, 401 sense detalls ni UID als logs, avís del hook fora de transacció, 76 tests nous) i documentació (`c7e5719`). Cap forat greu. Deute nou a `docs/TECH_DEBT.md` (P1–P11: GDAL al runtime, `DEBUG`/`ALLOWED_HOSTS` per defecte, `REVOKE TEMP` de `PUBLIC`…).
- 2026-10-24 — **E2E local** (orquestrador): `runserver` en contenidor contra `refugisdb_e2e` (PG17, rols reals, migrat amb `migrator`) + Firebase Auth/Firestore Emulators. `scripts/e2e/e2e_chunk1.sh`: 12/12 (health amb `database`; 401 sense token o token invàlid; 403 usuari normal a rutes d'admin i PATCH aliè; 200 admin; 404 perfil inexistent). Al log de Postgres: `BEGIN` → un sol `set_config(app.uid, app.is_admin, app.is_system=false)` amb valors correctes (normal/admin/anònim) → `COMMIT`. Postgres caigut → 503 en 10 s; recuperació → 200. Troballes corregides: `runserver` no arrencava (D8, `core.0002`), comentari amb backticks dins d'un heredoc del bootstrap, fals avís de `check_neon --alias default`. Decisions D7–D9.
- 2026-10-24 — PR #42 fusionada a `migration` (CI: tests verds; només falla SonarCloud). Creada `migracio/refugis`; agent de tests del chunk 2 en marxa. **El PO retira la delegació de decisions**: `DECISIONS_AUTONOMES.md` en pausa; qualsevol dubte o desviació es pregunta al PO (notificació al mòbil via Remote Control).
- 2026-10-24 — El PO confirma a Neon `dev` que `migrator` té `CREATE` a `public` (D9 tancada).

## Traspàs a sessió local (24/10)
Proper pas: **implementador del chunk 1** (brief a [`EQUIP.md`](EQUIP.md); abast al prompt de tests, resumit aquí).
- Executar: venv amb `pip install -r requirements.txt` (a la cloud, `django-crontab` no compilava amb el setuptools del sistema: venv fora del repo); `eval "$(scripts/dev/setup_local_postgres.sh | grep ^export)"` (o Docker `postgis/postgis:17-3.5` + `PG_START_CLUSTER=0 PGHOST=... PGPASSWORD=...`); `pytest -q`.
- Contracte dels tests per a l'implementador:
  - Àlies `default` (rol `app`, `ATOMIC_REQUESTS=True`) i `migrator`. Cal sobreescriure `django_db_setup` per migrar amb `migrator` sobre la mateixa BD de test, sense crear `test_*`.
  - `TEST_DATABASE_URL_*` té prioritat sobre `DATABASE_URL_APP/MIGRATOR`. `sslmode` només per a hosts no locals. `prepare_threshold: None`. Sense `options`. `INSTALLED_APPS` += `domain.core`, `django.contrib.gis`, `django.contrib.postgres`.
  - `domain.core.rls`: `rls_context` i `system_context`, reexportats a `domain.core`. Un `rls_context` niat restaura el context exterior. Helpers `expand_macros`, `create_policy_sql(name, table, cmd, using=, with_check=, role='app')`, `drop_policy_sql`. Migració `core.0001`: schemas, funcions de §2.0 i grants de §7.1.
  - Hook RLS: exactament un `set_config` abans de `check_permissions`, a **totes** les vistes (incloses les `@api_view` de cache). `is_admin` surt només dels claims verificats.
  - `api/utils/ids.py: uuid7()`: crida `time.time_ns()` a través del mòdul `time` (els tests el pategen). Monòton amb el rellotge congelat, si el rellotge torna enrere i si desborda el comptador de 12 bits.
  - Health: `SELECT 1` literal, camp `database: True/False`, 503 i `status: unhealthy` si la BD falla. Sense R2 (B4). `HealthCheckResponseSerializer` amb el camp `database`.
  - Firebase Emulator: amb `FIREBASE_AUTH_EMULATOR_HOST`, `initialize_app` amb una credencial que no sigui `Certificate` i un `projectId` no buit (també amb `CI=true`).
  - CI: `passenv` a tox. Workflow amb servei postgis (**17**, D5), GDAL, l'script de bootstrap i la branca `migration` als dos triggers.
- Després: revisor, seguretat i documentació en paral·lel; e2e (ara sí contra Neon `dev` si la sessió local hi té accés: cal el bootstrap SQL de §1.3 del disseny amb el rol propietari, D4); PR `migracio/infraestructura` → `migration`.

## Pendents / bloquejos
- **Neon inaccessible des de l'entorn cloud** (el proxy no admet TCP de BD): e2e en local (D3). El PO ha d'executar `scripts/e2e/` a Neon `dev`. Bootstrap de §1.3 ja fet (D4 tancat, 24/10).
