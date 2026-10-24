# Pla de migració Firestore → PostgreSQL (Neon) — RefugisLliures Backend

## Context
El backend (Django 5.1 + DRF a l'origen; objectiu: Django 5.2 LTS + DRF 3.16 + Python 3.14 + Postgres 18, decisió S-1 del PO) desa tot el domini a Firestore amb DAOs/mappers fets a mà i una cache Redis a cada DAO. Gran part de `docs/TECH_DEBT.md` (C2 doble aprovació, A3 races en arrays, A6 fluxos no atòmics, M3/M4/M5, B2, B5) ve de no tenir transaccions, FK ni UNIQUE. El document `Arquitectura_Neon_CloudRun_Upstash.md` decideix **Neon Postgres + PostGIS + pg_trgm + unaccent** via l'ORM de Django i **eliminar la cache de dades**. Abast acordat: **només la capa de dades** (sense Cloud Run, media-worker, Upstash ni GeoJSON a CDN). L'API manté el contracte (IDs string, `coord: {lat, long}`), de manera que el frontend no hauria de canviar. La BD és buida: les 1.542 fitxes de `api/utils/final_data_refuges.json` es carreguen de nou (sense `info_couchage` ni `info_eau`).

`settings.py` ja té els àlies `neon` (rol `app`, pooler) i `neon_migrator` (rol `migrator`, directe) i el toggle `NEON_USE_POSTGIS_ENGINE`; es reutilitzen.

## Decisions preses amb l'usuari
- **users** privat i minimitzat: uid (PK), language (FK al catàleg `users.languages`, per defecte `'en'`), created_at, age_confirmed_at, age_threshold, moderation_strikes, is_blocked, blocked_reason/at. Sense email ni data de naixement. **user_public_profiles**: uid, username (lectura oberta); l'avatar viu a la taula `users.user_avatars` (PK `key`).
- **RLS**: polítiques amb `migrations.RunSQL` (executades pel rol `migrator`, amb `reverse_sql`); a cada petició, dins la transacció, `SELECT set_config('app.uid', %s, true)` i `app.is_admin` (sempre local a la transacció pel pooler en mode transacció). El rol `app` no és propietari → sense `FORCE`. Se suma als permisos de Django.
- **condition**: ~~taula de vots~~. Substituït per la decisió del 24/10 (vegeu més avall).
- **Visitats**: taula d'unió única `user_visited_refuges` (fi de les còpies `visitors`/`visited_refuges`).
- **Esborrat d'usuari**: CASCADE de denúncies, avisos de moderació i audit logs de l'usuari (propostes i reformes passades: SET NULL, com l'actual anonimització).
- **Tests**: unitaris/integració contra Postgres+PostGIS **efímer en Docker** (**`postgis/postgis:18-3.6`** (Postgres 18.6, PostGIS 3.6.4), contenidor `rl-postgres`, **[FET]**; CI amb la mateixa imatge i Python 3.14; a Windows els tests corren en un contenidor Linux `python:3.14-slim-bookworm` + GDAL; vegeu `docs/design/postgres-schema.md` §1.4), mai Neon. **E2E de Claude contra la branca Neon `dev`**, amb tokens del **Firebase Auth Emulator** (usuari normal + admin amb claim `role=admin`).
- **Branques**: branca d'integració `migration` (ja existeix a origin; primer s'hi porta `develop` amb un merge). Cada chunk a `migracio/<chunk>` creada des de `migration`, PR a `migration`; l'orquestrador la fusiona quan l'equip valida i CI és verd (si només fallen SonarQube/Codecov, també). Al final, **una sola PR `migration` → `develop`**, que només fusiona l'usuari.
- **Credencials de Neon**: mai per xat. L'usuari les afegeix a la configuració de l'entorn cloud (menú de l'entorn al títol de la sessió → Edit → secrets / variables d'entorn) com a `DATABASE_URL_APP` i `DATABASE_URL_MIGRATOR` (branca `dev`); les agafa una sessió nova. Fins llavors es treballa en tot el que no les necessita (disseny, tests i codi contra Docker).

## Decisions sobre els dubtes del disseny (§11 de `docs/design/postgres-schema.md`), 24/10
Estat: esborrany del disseny fet a `migracio/disseny-bd` (commit `0ce1fbe`). Cal que l'agent de disseny el revisi amb això:
- **Perfil obligatori (#6)**: 403 `profile_required` a tot endpoint autenticat, excepte `POST /users/`, si no hi ha fila a `users`. Les lectures públiques no canvien. `manage_admins.py add` crea la fila de l'admin. **Frontend**: davant `profile_required`, mostra "Hi ha hagut un problema, torna a iniciar sessió" i fa logout; en tornar a entrar, el flux de login crea el perfil. Si torna a passar, es repeteix el mateix.
- **Perfil d'un altre usuari (#4)**: `GET /users/{uid}/` d'un altre retorna només `uid`, `username`, `avatar_metadata`. El perfil propi no canvia.
- **CSAM (#9)**: cascada general, però les denúncies i l'audit relacionats amb CSAM es conserven anonimitzats (SET NULL). El mitjà a `moderation-hold/` es manté.
- **#1**: es permeten reformes d'un dia: `CHECK (ini_date <= fin_date)`, la mateixa regla al serializer i al model (tanca A1).
- **Condition, que substitueix la taula de vots (#2, #21, #24)**: **no hi ha entitat vot.**
  - El refugi desa `condition` (float, la mitjana) i `num_contributed_conditions` (n).
  - L'experiència té un atribut `condition` smallint **obligatori**, 0–3.
  - POST d'experiència, dins la transacció i amb `select_for_update` del refugi o `UPDATE` atòmic: c=(c·n+v)/(n+1), n+1.
  - PATCH que canvia v→v': c=c+(v'−v)/n, n igual.
  - Esborrar una experiència o un compte **no toca** el refugi: el valor no és una dada personal.
  - Proposta aprovada amb `condition`: c=valor directament, n=1. Una experiència creada abans d'aquest reset i que després canviï la condition per PATCH compta com a vot nou (n+1) [INFERÈNCIA del PO; queda documentat].
  - Arrodoniment **només en serialitzar**: half-to-even (`round()` de Python).
  - El filtre de cerca accepta 0–3 sobre el valor arrodonit.
- **Valor inicial en la càrrega**: funció `puntua_refugi(info_comp)` (escalfor, dormir, aigua; normalitzat a 0–3; `manque_un_mur` ⇒ ≤1) amb **n=0**. Substitueix la lògica d'`assign_conditions`.
- **#13**: purga de les **visites de data concreta** (`visits` + participants) de més de 12 mesos. `user_visited_refuges` no es purga mai.
- **#18 surname**: es desa, però de moment no surt a l'API.
- **#20**: `expelled_uids` no s'exposa; el backend valida en unir-se i retorna error o èxit. `group_link` només és visible per al creador i els participants.
- **La resta** (#3, 5, 7, 8, 10, 11, 12, 14, 15, 16, 17, 19, 22, 23): s'accepten els defaults de §11.
- **Canvis al frontend** (agent en paral·lel quan arribi el chunk corresponent):
  - logout amb `profile_required` (chunk 3);
  - perfil aliè reduït (chunk 3);
  - `condition` obligatòria en crear o editar una experiència (chunk 7);
  - `group_link` i `expelled_uids` no sempre presents (chunk 5);
  - `surname` absent.

## Metodologia (per chunk)
Equip: orquestrador (Opus) + agents Sonnet. Pipeline seqüencial:
1. **Tests** escriu tests (unitaris: models/serializers/serveis; integració: views+ORM contra Postgres Docker; tests de contracte de l'API actual) → els executa i comprova que **fallen**.
2. **Implementador(s)** (1-2) fa passar els tests mantenint el comportament: ORM/GeoDjango, `select_related`/`prefetch_related`, `annotate`, `transaction.atomic` + `select_for_update`, `INSERT … ON CONFLICT` (`bulk_create(update_conflicts=…)`), constraints (`UniqueConstraint`, `CheckConstraint`, `ExclusionConstraint` per solapaments de reformes), índexs (FK, compostos, GiST, GIN trgm), cap SQL concatenat. Unifica crides controller→DAO en consultes úniques. Elimina la cache del domini tocat.
3. En paral·lel: **Revisor** (SQL senior: EXPLAIN, N+1 amb `django_assert_num_queries`, eines de Django infrautilitzades, RGPD), **Seguretat** (injecció, permisos de cada vista, propietat al controller, RLS provat amb el rol `app`), **Documentació** (`docs/` segons la taula del CLAUDE.md).
4. Correccions → tests verds → **e2e de Claude** contra Neon `dev` (crides reals a l'API, èxit i errors) → eliminació del codi Firestore d'aquella feature (si no el necessita un chunk posterior) → `graphify update .` → commits `[Feature] títol: comentari` → PR a `migration` → merge.

**Seguiment**: `docs/migration/PROGRESS.md` (estat de cada chunk, decisions, pendents, com continuar) s'actualitza i es fa push a cada pas, de manera que si s'acaben els crèdits un altre LLM pugui continuar; es complementa amb un resum final.

## Pas 0 — Disseny de la BD (agent Sonnet, ara)
Sortida a `docs/design/postgres-schema.md` (+ entrada al `docs/README.md`, el CLAUDE.md i `docs/migration/PROGRESS.md`):
- **Schemas de Neon**: `refuges` (refuge_types [catàleg], refuges, refuge_amenities, refuge_links, refuge_media; **sense taula de vots**), `users` (languages [catàleg], users, user_public_profiles, user_avatars, favourites, visited), `activity` (visits, visit_participants, renovations, renovation_participants/expelled, experiences, doubts, answers), `proposals`, `moderation` (upload_intents, media_reports, moderation_notices, hash_blocklist), `audit` (audit_logs). Django: una app per domini (evita conflictes de migracions entre chunks paral·lels) amb `db_table='"schema"."taula"'` o `search_path`.
- **Refugi**: `coord geography(Point,4326)` + GiST; `refuge_amenities` 1-1 amb 12 booleans `NOT NULL DEFAULT false` (`manque_un_mur … mezzanine_etage`); `type` = FK al catàleg `refuges.refuge_types` (`non gardé, fermée, cabane ouverte…, orri, emergence, key_needed`; afegir un tipus és un `INSERT`); links en taula (PK `url`); GIN `gin_trgm_ops` sobre `unaccent(lower(name))`; `condition` = mitjana desada al refugi (`num_contributed_conditions`, alimentada per l'atribut `condition` de les experiències; sense vots ni vista); sense vista `refuge_map` (el mapa és una consulta directa a `refuges`) i sense columna `remarque`. PK `uuid` per defecte `uuidv7()` de Postgres 18; PK compostes on cap FK hi apunta (preferits, visitats, participants i expulsats de reformes, participants de visites).
- Per a cada taula: PK, FK + `on_delete`, UNIQUE, NOT NULL, CHECK, defaults, índexs i la consulta que el justifica, **RLS sí/no** i polítiques, GRANTs dels rols `app`/`migrator`.
- Mapeig Firestore→SQL de cada camp (fitxers: `api/models/*.py`, `api/daos/*.py`, `api/daos/search_strategies.py`), com es manté el contracte JSON, i pla de càrrega del JSON.
- **Diagrama UML** (Mermaid `classDiagram` al doc) amb PK, FK, UNIQUE, NOT NULL, CHECK i multiplicitats.
- Llista de dubtes oberts → l'orquestrador els porta a l'usuari abans de tancar el disseny.

## Chunks (1 feature = 1 chunk)
| # | Branca | Contingut | Depèn de |
|---|---|---|---|
| 1 | `migracio/infraestructura` | Postgres default (Docker en tests, Neon en runtime), extensions, schemas, rols i GRANTs, middleware/hook `set_config` RLS, fixtures pytest-django, `health` amb Postgres, CI amb servei postgis | 0 |
| 2 | `migracio/refugis` | refuges+refuge_types+amenities+links+media(taula) (sense taula de vots: `condition` és una columna del refugi), comanda de càrrega del JSON, detall, cerca (trgm, filtres en SQL, `round(condition)`), coordenades en lloc de `coords_refugis` | 1 |
| 3 | `migracio/usuaris` | users/public_profiles, creació amb edat, PATCH (arregla M1), preferits, visitats, avatar | 2 |
| 4 | `migracio/visites` | visits + participants, `UNIQUE(refuge,date)`, ON CONFLICT, total per agregació, `process_yesterday_visits` | 3 |
| 5 | `migracio/renovations` | reformes, participants/expulsats, `CHECK (ini_date <= fin_date)` (reformes d'un dia permeses), exclusió de solapaments | 3 |
| 6 | `migracio/dubtes` | dubtes + respostes en arbre, propietat al controller (C1), `answers_count` per agregació | 3 |
| 7 | `migracio/experiencies` | experiències + `refuge_media.experience_id`, pujades (upload-intents/confirm) | 3 |
| 8 | `migracio/propostes` | propostes JSONB, aprovar/rebutjar amb `atomic`+`select_for_update` (C2), `condition` de la proposta aprovada reinicia la mitjana del refugi (c=valor, n=1), delete en cascada (A5) | 2,7 |
| 9 | `migracio/moderacio` | media_reports (UNIQUE), notices, hash blocklist indexada, audit logs (+purga expire_at) | 7 |
| 10 | `migracio/esborrat-usuari` | esborrat en una transacció amb cascades, després R2 i Firebase Auth, idempotent | 4–9 |
| 11 | `migracio/neteja` | treure Firestore (excepte Auth), `cache_service`, django-redis, rutes `cache/*`, DAOs/mappers morts; docs i CLAUDE.md | 10 |

Final: PR `migration` → `develop` amb el resum, que fusiona l'usuari.

Paral·lel: 4, 5 i 6 (dominis i apps independents); la resta seqüencial. Si algun canvi afecta el contracte de l'API, s'obre en paral·lel un agent al repo frontend (no s'espera).

## Verificació
- `pytest` complet contra Postgres Docker (tests que primer fallen i després passen), `tox` com a CI, `django_assert_num_queries` a les llistes, tests de RLS amb el rol `app`.
- `python manage.py migrate` + comanda de càrrega: 1.542 refugis, amenities correctes.
- E2E de Claude a cada chunk contra Neon `dev`: cada endpoint amb èxit i errors (401/403/404/409), comparant amb el comportament actual.

## Què necessito de tu
- Ja tinc `DATABASE_URL_APP`, `DATABASE_URL_MIGRATOR` i `R2_*` a l'entorn. Com que les de Neon també s'han enviat pel xat, recomano rotar-les en acabar la migració.
- Mai s'escriuen credencials a cap fitxer del repo, a `PROGRESS.md` ni als prompts dels agents; només es llegeixen de l'entorn.
