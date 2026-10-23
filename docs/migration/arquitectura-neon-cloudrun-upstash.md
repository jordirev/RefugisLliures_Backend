# Refugis Lliures — Arquitectura de producció: Cloud Run + Neon + Upstash

> Data: 22/10/2026 · Estat: proposta (no implementada). L'app encara no és a producció: totes les dades són de prova i els 1.542 refugis es tornen a carregar des de `INFO/final_data_refuges.json`.
> Preus en **USD sense IVA** (a Espanya, +21%), consultats a les webs oficials de Neon, Google Cloud (Cloud Run, Cloud SQL, Memorystore), Upstash, Cloudflare R2, Render i Fly.io en la data indicada.

---

## 1. Resum de la decisió

| Capa | Abans (TFG) | Proposta | Motiu |
|---|---|---|---|
| Base de dades | Cloud Firestore (via `firebase-admin`), sense ORM | **Neon Postgres + PostGIS + pg_trgm**, via l'ORM de Django (GeoDjango) | Transaccions, claus foranes, `UNIQUE`, consultes geoespacials i cerca difusa; elimina els DAOs i mappers fets a mà |
| Backend | Render, 1 worker gunicorn | **Google Cloud Run** (contenidor Docker) | Escalat automàtic de 0 a N, pla gratuït generós, mateix projecte que Firebase |
| Cache | Redis (django-redis) com a cache de dades a tots els DAOs | **Sense cache de dades.** **Upstash Redis** només per al rate limit | Amb Postgres, la cache no estalvia ni temps ni diners, i ha estat la font de diversos bugs (C2, M6, I4) |
| Mitjans | Cloudflare R2 (privat, URLs presignades) | **Cloudflare R2** (igual) + **CDN de Cloudflare** per al mapa | El mapa és la lectura més freqüent i deixa de passar pel backend |
| Autenticació | Firebase Auth | **Firebase Auth** (igual) | Sense canvis |
| Notificacions | — | Fora d'aquest abast | No entra en el càlcul |

Decisió presa després d'un "council" de 5 assessors i 5 revisors. Tots van recomanar Postgres + PostGIS per unanimitat. Neon i Cloud Run es van triar comparant preu, rendiment i escalabilitat amb Cloud SQL, Render Postgres, Render (allotjament), Fly.io, Supabase, Scaleway, DigitalOcean i Aiven.

### Per què no Firestore
Gairebé tot el deute tècnic de `docs/TECH_DEBT.md` correspon a funcions que una base de dades relacional ja té:

| Problema actual | Solució a Postgres |
|---|---|
| Actualitzacions perdudes en arrays/maps (A3) | Taules relacionals + `transaction.atomic` / `select_for_update` |
| Fluxos de diversos documents no atòmics: esborrat d'usuari en 11 passos, aprovació de propostes (A6) | Una sola transacció ACID + `on_delete=CASCADE` |
| Visites duplicades per (refugi, data) (M4) | `UNIQUE(refuge_id, date)` + `INSERT … ON CONFLICT` |
| Registres orfes (visites d'un refugi esborrat, `reviewer_uid`) | Claus foranes `CASCADE` / `SET NULL` |
| Recorregut de tota la col·lecció per obtenir les visites d'un usuari (B5) | Índex a la clau forana |
| Cerca de nom exacta (B2) | `pg_trgm` + `unaccent` |
| Document desnormalitzat `coords_refugis/all_refugis_coords` (límit d'1 MiB, ~1 escriptura/s) | Columna `geography(Point)` amb índex GiST |
| Doble aprovació per la cache (C2) | Desapareix en treure la cache de dades |

El roadmap del Trello demana el mateix: comprovar si ja hi ha un refugi a prop o amb nom semblant (`ST_DWithin` + `similarity()`), cerca per pobles i pics, punts d'aigua, paginació, fòrum i respostes en fil, historial de reformes, perfils públics i cascades del RGPD.

> ⚠️ **Avís del Contrarian (la resposta més ben valorada a la revisió):** canviar de base de dades no arregla sol els bugs de lògica. Si es porta el patró "comprovar i després crear" tal com està, els races continuaran a SQL. **Primer s'han de definir les invariants com a restriccions de la base de dades** (secció 4.1).

---

## 2. Diagrama

```
                        ┌──────────────────────────────┐
  App mòbil (Expo) ────▶│ Cloudflare CDN               │◀── map/refuges.v<hash>.geojson (bucket R2 públic)
     │   │              └──────────────────────────────┘
     │   │ Firebase ID token (Bearer)
     │   ▼
     │  ┌────────────────────────────────────────────────┐
     │  │ Cloud Run · servei "api" (Django + DRF)        │── Secret Manager
     │  │ europe-west3 (Frankfurt) o la regió UE més     │
     │  │ propera · min 1 / max N instàncies             │
     │  └───┬──────────────┬──────────────┬──────────────┘
     │      │ TLS          │ TLS          │ encua feina
     │      ▼              ▼              ▼
     │  ┌────────────┐ ┌─────────────┐ ┌───────────────────────────┐
     │  │ Neon       │ │ Upstash     │ │ Cloud Tasks ──▶ Cloud Run │
     │  │ Postgres   │ │ Redis (EU)  │ │ servei "media-worker"     │
     │  │ Frankfurt  │ │ rate limit, │ │ (Pillow/ffmpeg, escala    │
     │  │ PostGIS,   │ │ APIs        │ │ a zero)                   │
     │  │ pg_trgm    │ │ externes    │ └─────────────┬─────────────┘
     │  │ (pooler)   │ └─────────────┘               │
     │  └────────────┘                               ▼
     │                                    Cloudflare R2 (bucket privat)
     └──── URLs presignades ─────────────────────────┘
  Cloud Scheduler ──▶ Cloud Run Jobs (pg_dump a R2, tasques diàries)
  Firebase Auth (fora d'aquest abast)
```

---

## 3. Components i configuració

### 3.1 Neon (base de dades)
| Paràmetre | Valor recomanat | Motiu |
|---|---|---|
| Pla | **Launch** (pagament per ús, sense mínim) | 0,106 $/CU-h, 0,35 $/GB-mes |
| Regió | `aws-eu-central-1` (Frankfurt) | RGPD; al costat de Cloud Run |
| Compute | Mínim **0,25 CU**, màxim **2 CU**, **sense aturada quan no hi ha activitat** en producció | Evita l'arrencada en fred (uns centenars de ms); el màxim funciona com a límit de despesa |
| Extensions | `postgis`, `pg_trgm`, `unaccent`, `pg_stat_statements` (opcional: `vector`) | Geoespacial, cerca difusa amb accents catalans, consultes lentes, futures funcions d'IA |
| Connexions | Endpoint **amb pooler** (`-pooler`, PgBouncer en mode transacció, fins a 10.000) per a l'app; endpoint **directe** per a les migracions | Cloud Run pot obrir moltes instàncies |
| PITR | Historial de **7 dies** (el màxim de Launch; per defecte és 1 dia) | Recuperació d'errors humans |
| Branques | Una branca `dev` i branques temporals per provar migracions | Proves amb dades reals sense tocar producció |
| Rèpliques de lectura | Quan calgui (sense cost extra d'emmagatzematge) | Escalat de lectures |
| Pas a Scale | Quan calguin **regles d'IP permeses**, xarxa privada o SOC 2 | 0,222 $/CU-h |

### 3.2 Cloud Run (backend)
| Paràmetre | Valor recomanat | Motiu |
|---|---|---|
| Regió | La regió de Google més propera a Frankfurt (p. ex. `europe-west3`). Mesura la latència fins a Neon i comprova el *tier* de preu de la regió al calculador | Les consultes de Django fan diversos viatges a la base de dades: la latència es multiplica |
| Facturació | **Per petició** | El pla gratuït (180.000 vCPU-s, 360.000 GiB-s i 2M de peticions al mes) cobreix tota la feina fins a 5.000 MAU |
| Servei `api` | 1 vCPU, 1 GiB, **min-instances = 1**, **max-instances = 10** (límit de cost i protecció contra abusos), *startup CPU boost* | Sense arrencades en fred per als usuaris |
| Servidor | gunicorn amb `gthread` (p. ex. 2 workers × 4 fils), concurrència de Cloud Run ~20–40 | Diverses peticions per instància |
| Servei `media-worker` | 2 vCPU, 2 GiB, **min = 0**, invocat per **Cloud Tasks**, timeout de diversos minuts | Treu el processament de vídeos de la petició (deute I1) |
| Imatge | Dockerfile amb `gdal-bin`, `libgeos`, `libproj` (requisit de GeoDjango) i ffmpeg | La instal·lació de GDAL era el risc principal de desplegament a Render; amb Docker queda controlada |
| Tasques programades | **Cloud Scheduler → Cloud Run Jobs** (no dins de les instàncies) | `pg_dump`, neteja, la tasca diària (si encara cal) |
| Secrets | **Secret Manager** (cadena de connexió de Neon, token d'Upstash, claus de R2, `SECRET_KEY`) | Res a `env/` ni al repositori |

### 3.3 Upstash Redis
| Paràmetre | Valor recomanat |
|---|---|
| Pla | **Pay as You Go** (0,20 $/100.000 comandes; el pla gratuït inclou 500.000 comandes/mes, 256 MB i 10 GB d'ample de banda) |
| Regió | UE (Frankfurt) |
| Ús **exclusiu** | 1) **rate limit** per UID/IP (targeta "RATE LIMIT API" del Trello); |
| No s'hi guarda | Dades de domini (refugis, usuaris, permisos). Postgres és la font de veritat |
| Connexió | `rediss://` (TLS), token a Secret Manager |
| Prod Pack (+200 $/mes: SLA, multi-AZ, xifratge en repòs, SOC 2) | **No cal**: si Upstash cau, el rate limit ha de deixar passar les peticions (*fail-open*) i l'app continua funcionant |

### 3.4 Cloudflare R2 + CDN
- **Bucket privat** (igual que ara) per a fotos i vídeos, amb URLs presignades d'1 h. El flux d'upload-intents + `confirm` amb `MediaUploadController.process_and_publish` (neteja d'EXIF, tipus real, claus UUID) es manté.
- **Bucket públic** separat amb domini propi i **CDN de Cloudflare**, només amb dades no personals:
  - `map/refuges.v<hash>.geojson`: coordenades, nom, tipus i estat de tots els refugis.
  - Es regenera en aprovar una proposta de creació, edició o esborrat, i en carregar les dades inicials.
  - Un `map/manifest.json` petit (amb `Cache-Control` curt) indica la versió actual; el GeoJSON versionat té `Cache-Control: immutable`.
  - També serveix per a la funció de descàrrega offline.
- R2 no cobra la sortida de dades: les fotos i el mapa no generen cost de trànsit.

---

## 4. Requisits d'implementació: seguretat

### 4.1 Integritat de dades (invariants com a restriccions)
- [ ] `users.uid` (UID de Firebase) com a **clau primària** de la taula d'usuaris; totes les claus foranes d'usuari hi apunten.
- [ ] `UNIQUE(refuge_id, date)` a les visites i `INSERT … ON CONFLICT DO UPDATE` en lloc de comprovar i després crear (M4).
- [ ] Claus foranes amb `on_delete=CASCADE` (visites, experiències, dubtes i respostes d'un refugi o usuari esborrat) i `SET NULL` (`reviewer_uid` a les propostes, `reporter_uid` a les denúncies).
- [ ] `CHECK (ini_date < fin_date)` a les reformes, la mateixa regla al serializer i al model (A1 i gotcha 5).
- [ ] Aprovar o rebutjar propostes dins de `transaction.atomic()` amb `select_for_update()` sobre la proposta i comprovant `status = 'pending'`: impossible aprovar-la dues vegades (C2).
- [ ] Preferits, visitats i participants de reformes com a **taules d'unió** amb `UNIQUE`, no arrays (A3).
- [ ] Comptadors (`total_visitors`, mitjana de `condition`) calculats per **agregació** o amb una vista materialitzada que es refresca, no amb `UPDATE` a cada escriptura (evita files calentes i M3/M5).
- [ ] **Tests de contracte** sobre els DAOs actuals **abans** de substituir-los; substituir-los d'un en un, amb la mateixa interfície cap als controllers.

### 4.2 Autenticació i autorització
- [ ] Firebase Auth es manté; `verify_id_token(..., check_revoked=True)` almenys a les operacions sensibles: esborrar el compte, accions d'administrador (B9).
- [ ] Comprovar la **propietat al controller** per a dubtes i respostes, com ja fan les experiències (C1).
- [ ] Revisar els `permission_classes` de cada vista: el permís per defecte global és `AllowAny`.
- [ ] Esborrat d'usuari: transacció a Postgres (cascades), després esborrar els objectes de R2 i després `auth.delete_user` a Firebase (M10). Ha de ser **idempotent i reintentable** (Cloud Tasks), perquè les tres peces no comparteixen una transacció.
- [ ] Decidir la retenció de `audit_logs`, `moderation_notices` i l'anonimització de `reporter_uid` (I3).

### 4.3 Configuració de Django en producció (M11)
- [ ] `DEBUG=False`, `ALLOWED_HOSTS` amb el domini de Cloud Run i el propi, `CORS_ALLOWED_ORIGINS` restringit, middleware CSRF actiu per a l'admin.
- [ ] `SECURE_PROXY_SSL_HEADER`, `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, HSTS.
- [ ] Una sola manera d'inicialitzar Firebase (B11) i entorns ben separats; corregir que a CI s'utilitzi Firebase de producció (B12).
- [ ] L'admin de Django (que ara té models de veritat) només per a usuaris `is_staff` i protegit; valorar posar-lo en un servei o ruta restringida.

### 4.4 Base de dades
- [ ] Connexió amb `sslmode=require` (millor `verify-full`).
- [ ] **Dos rols de Postgres**: `app` (només DML a les taules del domini) i `migrator` (DDL, només s'utilitza al pas de migració del desplegament).
- [ ] Contrasenyes llargues i rotades a Secret Manager. Amb el pla Launch no hi ha regles d'IP; si cal, passar a **Scale** i donar a Cloud Run una IP de sortida fixa (Cloud NAT, cost addicional no inclòs a la secció 7).
- [ ] **Còpia de seguretat independent**: un Cloud Run Job setmanal que fa `pg_dump` xifrat cap a R2, a més del PITR de Neon. Protegeix davant d'un error del proveïdor o d'un compte compromès.

### 4.5 Xarxa i abús
- [ ] **Rate limit** a Upstash per UID (autenticat) i per IP (anònim, des de `X-Forwarded-For`), amb límits més estrictes a les escriptures: propostes, pujades, denúncies, creació d'usuari.
- [ ] `max-instances` a Cloud Run per limitar el cost d'un atac.
- [ ] Mida màxima de petició i timeouts a l'API; els vídeos només passen per upload-intents a R2.
- [ ] (Opcional, de pagament) Cloud Armor davant de Cloud Run si apareixen abusos.

### 4.6 RGPD i privacitat
- [ ] Totes les dades a la **UE**: Neon (Frankfurt), Cloud Run (regió UE), Upstash (UE), R2 amb *location hint* o *jurisdiction* UE.
- [ ] Signar o acceptar el **DPA** de cada proveïdor (Google, Neon, Upstash, Cloudflare).
- [ ] Les crides a APIs externes (meteo, rutes, geocodificació) **passen pel backend**, per no exposar la IP de l'usuari (targeta del Trello).
- [ ] Els logs no poden contenir tokens ni dades personals (ja fet en part); definir la retenció a Cloud Logging.
- [ ] Termes del servei i política de privacitat (targetes del Trello) on surtin els encarregats del tractament anteriors.

### 4.7 Mitjans
- [ ] Mantenir el pipeline actual (EXIF, tipus real, claus UUID, URLs presignades) i moure'l al `media-worker` (I1).
- [ ] La llista de bloqueig pHash surt de la memòria de cada procés (I5) i passa a una taula de Postgres amb índex; amb diverses instàncies de Cloud Run, la còpia a memòria no és coherent.
- [ ] El bucket públic de la CDN només pot contenir dades no personals.

---

## 5. Requisits d'implementació: rendiment i escalabilitat

### 5.1 Model de dades i consultes
- [ ] Coordenades com a `geography(Point, 4326)` amb **índex GiST**; els punts d'aigua, pics i pobles com a taules amb geometria pròpia.
- [ ] **Índex GIN `gin_trgm_ops`** sobre `unaccent(lower(name))` (refugis, i cognoms d'usuari si cal).
- [ ] Índexs a totes les claus foranes i índexs compostos (`refuge_id, date` a visites, `user_id, created_at` a experiències).
- [ ] Consultes clau:
  - refugis a prop o amb nom semblant en crear-ne un: `ST_DWithin(coord, :p, 200) OR similarity(name, :n) > 0.4`;
  - refugis dins de la vista del mapa: `coord && ST_MakeEnvelope(...)`;
  - sortida en GeoJSON: `ST_AsGeoJSON`, o `djangorestframework-gis`.
- [ ] **Paginació per cursor** (*keyset*) per a fotos, preferits, visitats i experiències (targetes del Trello).
- [ ] Mantenir el contracte de l'API: IDs de tipus string i `coord: {lat, long}` a les respostes actuals, perquè el frontend no hagi de canviar.
- [ ] Activar `pg_stat_statements` i revisar les consultes lentes abans de pensar a afegir cache.

### 5.2 Django amb el pooler
- [ ] `ENGINE = django.contrib.gis.db.backends.postgis`, psycopg 3.
- [ ] Amb PgBouncer en mode transacció: `DISABLE_SERVER_SIDE_CURSORS = True`; les migracions per l'endpoint directe.
- [ ] `CONN_MAX_AGE` > 0 cap al pooler (reutilitzar connexions) i `CONN_HEALTH_CHECKS = True`.

### 5.3 Cloud Run
- [ ] `min-instances = 1` al servei `api` (no hi ha arrencada en fred) i *startup CPU boost*.
- [ ] Imports pesants (Pillow, ffmpeg, boto3) carregats només quan es necessiten, perquè la imatge `api` arrenqui ràpid; el processament de mitjans va al `media-worker`.
- [ ] Sense estat a la memòria de les instàncies: res de caches `LocMem` amb dades que han de ser coherents entre instàncies.
- [ ] Endpoint `/api/health/` que comprovi Postgres (i no depengui de R2: B4).

### 5.4 Cache: només on aporta
| On | Com | Motiu |
|---|---|---|
| Mapa amb tots els refugis | **GeoJSON estàtic a R2 + CDN** (secció 3.4) | La resposta més gran i més freqüent; no passa pel backend |
| Detall de refugi, llistes | Capçaleres `ETag` / `Last-Modified` + `Cache-Control: private, max-age=60` | L'app no torna a baixar el que ja té; cost 0 |
| APIs externes | Upstash amb TTL (p. ex. meteo 30 min, geocodificació 30 dies) | Lentes i amb límit de crides |
| Rate limit | Upstash (`INCR` + `EXPIRE` en un sol viatge) | Comptador compartit entre instàncies |
| Dades de domini | **Cap cache.** Postgres amb índexs | Elimina C2, M6 i I4 i el codi d'invalidació dels DAOs |

Cal treure `django-redis` com a cache per defecte dels DAOs, i també les rutes `cache/stats`, `cache/clear` i `cache/invalidate` (o deixar-les només per a Upstash).

### 5.5 Observabilitat i control de costos
- [ ] Cloud Monitoring: latència p95, errors 5xx i nombre d'instàncies; alertes.
- [ ] Neon: mètriques de CU, connexions i *spending notifications*.
- [ ] **Pressupostos amb alertes** a Google Cloud (p. ex. 30, 60 i 100 $) i límit de despesa a Upstash.
- [ ] Logs estructurats (targeta "Sistema de Logs útil") sense dades personals.

---

## 6. Pla de migració (ordre recomanat)
1. **Prova de desplegament (el primer pas):** un Django mínim amb GeoDjango a Cloud Run (Dockerfile amb GDAL), connectat a Neon (Frankfurt), que respongui una consulta `ST_DWithin` sobre els refugis carregats. És l'única peça que pot bloquejar tot el pla.
2. Tests de contracte sobre els DAOs actuals (Firestore).
3. `models.py` amb les invariants de la secció 4.1, migracions i càrrega des del JSON.
4. Substituir els DAOs d'un en un amb la mateixa interfície. Començar per **visites i preferits**, que és on hi ha els bugs; els controllers no canvien.
5. Eliminar el document `coords_refugis`, generar el GeoJSON de la CDN i treure la cache de dades.
6. Moure el processament de mitjans al `media-worker` amb Cloud Tasks.
7. Configuració de producció (secció 4.3), rate limit, pressupostos i alertes.
8. Treure el codi de Firestore i `firebase-admin` (excepte Auth).
9. Actualitzar `docs/` i `CLAUDE.md` del backend (regla del repositori: els docs canvien en el mateix canvi que el codi).

Esforç estimat amb Claude: 1–2 setmanes de vespres per a la migració de dades i DAOs, més la configuració de Google Cloud.

---

## 7. Cost aproximat al mes segons els usuaris

### 7.1 Supòsits
| Paràmetre | Valor |
|---|---|
| Sessions | 10 per MAU i mes, fent servir filtres |
| Crides a l'API per sessió | 15 (el mapa ja no passa pel backend) |
| CPU facturable per crida | 0,2 s (1 vCPU) |
| Sortida de l'API per sessió | 0,4 MB (JSON comprimit) |
| Pujades | 0,5 per MAU i mes, 3 s × 2 vCPU al `media-worker` |
| Mitjans nous | 0,25 MB per MAU i mes (emmagatzematge calculat al mes 12) |
| Fotos vistes | 20 per sessió (lectures de R2) |
| Comandes a Upstash | 2 per crida (rate limit) |
| Neon | Sempre encès a 0,25 CU; uns quants CU-h més a mesura que creix la càrrega |
| Fora del càlcul | Firebase Auth, notificacions, IVA, domini, Cloud NAT, Cloud Armor, plans de suport |

| MAU | Crides a l'API/mes | CPU API (vCPU-s) | CPU worker (vCPU-s) | Sortida | Comandes Upstash | R2 (mes 12) | Lectures R2 |
|---|---|---|---|---|---|---|---|
| 200 | 30.000 | 6.000 | 600 | 0,8 GB | 60.000 | 0,6 GB | 40.000 |
| 500 | 75.000 | 15.000 | 1.500 | 2,0 GB | 150.000 | 1,5 GB | 100.000 |
| 1.000 | 150.000 | 30.000 | 3.000 | 3,9 GB | 300.000 | 2,9 GB | 200.000 |
| 2.000 | 300.000 | 60.000 | 6.000 | 7,8 GB | 600.000 | 5,9 GB | 400.000 |
| 5.000 | 750.000 | 150.000 | 15.000 | 19,5 GB | 1.500.000 | 14,6 GB | 1.000.000 |

### 7.2 Desglossament (USD/mes, sense IVA)
| Concepte | Tarifa oficial | 200 | 500 | 1.000 | 2.000 | 5.000 |
|---|---|---|---|---|---|---|
| **Cloud Run** · instància mínima inactiva del servei `api` (1 vCPU + 1 GiB, 730 h) | 0,0000025 $/vCPU-s + 0,0000025 $/GiB-s | 13,14 | 13,14 | 13,14 | 13,14 | 13,14 |
| Cloud Run · CPU activa (API + worker) per sobre de 180.000 vCPU-s | 0,000024 $/vCPU-s | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| Cloud Run · memòria activa per sobre de 360.000 GiB-s | 0,0000025 $/GiB-s | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| Cloud Run · peticions per sobre de 2M | 0,40 $/milió | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| Cloud Run · sortida a internet (aprox., 1 GB gratuït) | ~0,12 $/GB | 0,00 | 0,11 | 0,35 | 0,82 | 2,22 |
| Artifact Registry, Cloud Build, Secret Manager, Scheduler, Tasks | majoritàriament dins dels plans gratuïts | 0,50 | 0,50 | 0,50 | 0,50 | 0,50 |
| **Neon** · compute (182,5 → 245 CU-h) | 0,106 $/CU-h | 19,34 | 19,34 | 20,14 | 21,20 | 25,97 |
| Neon · emmagatzematge (1 → 3 GB) | 0,35 $/GB-mes | 0,35 | 0,35 | 0,52 | 0,70 | 1,05 |
| Neon · historial PITR de 7 dies (~0,5 GB) | 0,20 $/GB-mes | 0,10 | 0,10 | 0,10 | 0,10 | 0,10 |
| **Upstash** · comandes per sobre de 500.000 | 0,20 $/100.000 | 0,00 | 0,00 | 0,00 | 0,20 | 2,00 |
| **Cloudflare R2** · emmagatzematge per sobre de 10 GB | 0,015 $/GB-mes | 0,00 | 0,00 | 0,00 | 0,00 | 0,07 |
| Cloudflare R2 · lectures per sobre de 10M / escriptures per sobre d'1M | 0,36 $ / 4,50 $ per milió | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| Cloudflare CDN (GeoJSON del mapa) i sortida de R2 | gratuït | 0,00 | 0,00 | 0,00 | 0,00 | 0,00 |
| **TOTAL al mes (sense IVA)** | | **33,4** | **33,6** | **34,8** | **36,7** | **45,1** |
| **TOTAL al mes (amb 21% d'IVA)** | | **40,5** | **40,6** | **42,0** | **44,4** | **54,5** |
| **Total a l'any (sense IVA)** | | **401** | **403** | **417** | **440** | **541** |

### 7.3 Lectura dels números
- **El cost és gairebé fix fins a 5.000 MAU.** El ~95% són dues "reserves de capacitat": la instància mínima de Cloud Run (13 $) i Neon sempre encès (19 $). La feina real cap dins dels plans gratuïts.
- **La primera línia que creixerà** serà la CPU de Cloud Run. A 5.000 MAU es fan servir ~165.000 dels 180.000 vCPU-s gratuïts. Cada 100.000 vCPU-s addicionals costen uns 2,4 $, de manera que a 10.000 MAU el total seria d'uns 50–55 $.
- Les tarifes de Cloud Run són les de les regions *Tier 1*. Si la regió triada al costat de Neon és *Tier 2*, el compute és més car: s'ha de comprovar al calculador de Google abans de decidir la regió.

### 7.4 Palanques de cost
| Palanca | Efecte al mes | Contrapartida |
|---|---|---|
| Cloud Run `min-instances = 0` | −13 $ | Arrencada en fred de Django (3–8 s) per al primer usuari després d'una estona sense activitat |
| Deixar que Neon s'aturi quan no hi ha activitat (amb pocs usuaris) | −8 a −10 $ fins a ~500 MAU | Uns centenars de ms per arrencar la base de dades |
| Neon Free durant el desenvolupament | Neon a 0 $ | No apte per a producció (sense garanties) |
| Passar a Neon **Scale** (regles d'IP, xarxa privada, SOC 2) | Compute ×2,1 (+20–30 $) | Més seguretat a nivell de xarxa |
| Passar més endavant a **Cloud SQL** amb vCPU dedicada i SLA | +30 a +80 $ (HA ×2) | Màxim rendiment i seguretat, tot dins de Google |

### 7.5 Comparativa amb les altres opcions estudiades (total al mes, sense IVA)
| Escenari | 200 | 500 | 1.000 | 2.000 | 5.000 |
|---|---|---|---|---|---|
| **Cloud Run + Neon + Upstash (aquest informe)** | **33** | **34** | **35** | **37** | **45** |
| Tot a Google (Cloud Run + Memorystore Valkey + Cloud SQL) | 50 | 50 | 70 | 71 | 73 |
| Tot a Render (web + Key Value + Postgres) | 24 | 24 | 37 | 56 | 58 |
| Render web + Key Value + Neon | 27 | 33 | 38 | 58 | 64 |
| Fly.io + Neon + Upstash | 17 | 22 | 28 | 37 | 43 |

Els escenaris de comparació venen del model anterior (16 crides per sessió i mapa servit pel backend), i per això els números no coincideixen exactament amb la secció 7.2. Amb pocs usuaris, Render i Fly.io surten més barats, perquè no paguen una instància sempre activa a 13 $ ni Neon sempre encès. A partir de ~2.000 MAU, aquesta arquitectura és la que escala millor i amb menys esforç d'operació.

---

## 8. Riscos oberts
| Risc | Mitigació |
|---|---|
| GDAL/GEOS a la imatge de Docker | Prova de desplegament (pas 1) abans de res més |
| Latència entre Cloud Run i Neon (núvols diferents) | Mateixa ciutat; mesurar a la prova; si és alta, Cloud SQL amb IP privada |
| Coordinar l'esborrat d'usuari entre Firebase Auth, Postgres i R2 | Tasca idempotent amb reintents (Cloud Tasks) |
| Sense regles d'IP a Neon Launch | TLS, credencials fortes i rotades; passar a Scale si cal |
| Disponibilitat d'Upstash | El rate limit deixa passar si Upstash no respon (*fail-open*); l'app no en depèn per funcionar |
| Les estimacions de càrrega són supòsits | Revisar-les amb mètriques reals el primer mes i ajustar `min/max-instances` i els CU de Neon |
