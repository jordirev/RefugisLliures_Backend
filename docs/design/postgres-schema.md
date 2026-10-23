# Disseny físic de la BD PostgreSQL (Neon)

> **[FET]** comprovat al codi, a les dades (`api/utils/final_data_refuges.json`) o a la documentació del projecte · **[INFERÈNCIA]** deducció raonada, no executada · **[NO VERIFICAT]** depèn de Neon, del pooler o d'una decisió pendent. Vegeu la [llegenda del README](../README.md).
>
> Document **normatiu** per als agents que implementen la migració Firestore → PostgreSQL (chunks 1–11 de [`../migration/PLAN.md`](../migration/PLAN.md)). Les decisions de l'usuari del PLAN són vinculants; aquí s'hi afegeixen les decisions de disseny que el PLAN deixava obertes i la llista de [dubtes oberts](#11-dubtes-oberts) per al product owner.
> Entrades: [`PLAN.md`](../migration/PLAN.md), [`arquitectura-neon-cloudrun-upstash.md`](../migration/arquitectura-neon-cloudrun-upstash.md) (§4.1, 4.4, 4.6, 5.1, 5.2), [`uml-conceptual.md`](../migration/uml-conceptual.md) (completat des del codi), [`integrations/neon.md`](../integrations/neon.md).
> Cap secret ni valor de variable d'entorn apareix aquí; només noms de rols i d'objectes.

## Índex
0. [Resum de decisions](#0-resum-de-decisions)
1. [Visió general: schemas, convencions, IDs, mapatge a Django](#1-visió-general)
2. [Especificació per taula](#2-especificació-per-taula)
3. [Enumeracions](#3-enumeracions)
4. [Valors derivats i vistes](#4-valors-derivats-i-vistes)
5. [Mapatge Firestore → SQL, contracte de l'API i receptes de consulta](#5-mapatge-firestore--sql-contracte-de-lapi-i-receptes)
6. [Apps Django i models](#6-apps-django-i-models)
7. [Rols, grants i mecanisme de RLS](#7-rols-grants-i-mecanisme-de-rls)
8. [RGPD](#8-rgpd)
9. [Pla de càrrega de `final_data_refuges.json`](#9-pla-de-càrrega-de-final_data_refugesjson)
10. [UML físic (Mermaid)](#10-uml-físic-mermaid)
11. [Dubtes oberts](#11-dubtes-oberts)

---

## 0. Resum de decisions

| # | Decisió | On |
|---|---|---|
| 1 | **24 taules + 3 vistes** en 6 schemas de domini (`users`, `refuges`, `activity`, `proposals`, `moderation`, `audit`) + schema `core` només de funcions (context RLS, `unaccent` immutable, arrodoniment). | §1.1 |
| 2 | **PK `uuid`** (`gen_random_uuid()`) per a les entitats; `users.uid` (text, UID de Firebase) com a PK natural; `refuge_media.key` (clau R2) com a PK natural; **`bigint identity`** per a taules d'unió i de registre. L'API continua exposant IDs com a *string* opac (UUID canònic en minúscules). | §1.4 |
| 3 | Mapatge de schema a Django amb **`db_table = 'schema"."taula'`** (no `search_path`): és independent de la connexió i funciona amb PgBouncer en mode transacció. | §1.5 |
| 4 | **`type` = `text` + `CHECK`** (no `ENUM` natiu); tots els enums del domini són `CHECK ... IN (...)` + `models.TextChoices`. | §3 |
| 5 | `refuge_amenities` 1–1 amb 12 `boolean NOT NULL DEFAULT false`; `info_couchage`/`info_eau` s'ignoren; l'API continua emetent **0/1 enters** a `info_comp` (el frontend espera `number`). | §2.2 |
| 6 | **Cap comptador desat.** `num_shared_experiences`, `num_renovated_refuges`, `answers_count`, `total_visitors`, `uploaded_photos_keys`, `visitors` i `condition` es **deriven** (agregació/vistes); cada un té el seu índex de suport. `total_visitors` i `condition` passen per **vistes** perquè la RLS amagaria files d'altres usuaris a un `SUM`/`AVG` directe. | §4 |
| 7 | `condition` = `AVG(value)` de `refuge_condition_votes` amb **arrodoniment half-to-even** (idèntic a `round()` de Python, que és el que fa l'API avui) mitjançant `core.round_half_even()`; el filtre és `round_half_even(avg) IN (...)`. Cada refugi carregat del JSON rep un **vot llavor** (regla de `assign_conditions`). | §2.5, §4 |
| 8 | Reformes: `CHECK (ini_date < fin_date)` + **`EXCLUDE USING gist (refuge_id WITH =, daterange(ini_date, fin_date, '[]') WITH &&)`** sobre **totes** les files (el predicat «només actives» no es pot expressar en un índex perquè `CURRENT_DATE` no és immutable, i no cal: les passades mai poden solapar-se amb una de nova). | §2.10 |
| 9 | Aprovar/rebutjar propostes: `SELECT ... FOR UPDATE` amb `status='pending'` + `UPDATE ... WHERE status='pending'` + `UNIQUE(source_proposal_id)` als vots → la doble aprovació (C2) és impossible a la BD. Regles `create/update/delete` del payload com a `CHECK` (inclosa la llista tancada de claus del JSONB). | §2.16 |
| 10 | **RLS activada a les 24 taules** (rol `app`, sense `FORCE`); context per **`set_config(..., true)`** (local a la transacció) dins una transacció per petició. Lectura pública (`USING (true)`) a refugis, perfils públics, experiències, dubtes i respostes; mitjans: `visible` per a tothom, la resta autor/admin. Les crides «de sistema» (jobs, efectes creuats de moderació) usen un `system_context()` explícit amb `app.is_system`. | §7 |
| 11 | Esborrat d'usuari en **una transacció** amb `ON DELETE` (CASCADE / SET NULL segons el PLAN) + una **cua d'esborrat de R2** alimentada per triggers (`moderation.media_deletion_queue`) perquè el pas R2 sigui reintentable i no quedin fitxers orfes. | §2.20, §8 |
| 12 | `users` privada i minimitzada; dades públiques a `user_public_profiles`. Cap email ni data de naixement. `audit_logs` caduca a 365 dies, `upload_intents` a 1 dia (jobs de purga). | §2.1, §8 |
| 13 | Càrrega del JSON idempotent amb **IDs deterministes (UUIDv5)** de `(name, lat, long)`; 1.542 refugis, 1.542 `refuge_amenities`, 2.075 enllaços, 1.542 vots llavor. | §9 |
| 14 | Una **app Django per domini**, amb ordre de migracions explícit per evitar dependències circulars (`users` abans de `refuges`; les FK cap a `experiences` i `proposals` s'afegeixen en migracions posteriors de `refuges`). | §6 |

---

## 1. Visió general

### 1.1 Schemas, taules, apps i chunks

| Schema | Taules / vistes | App Django | Chunk |
|---|---|---|---|
| `core` | Només funcions: `uid()`, `is_admin()`, `is_system()`, `immutable_unaccent()`, `norm_name()`, `round_half_even()` | `core` | 1 |
| `users` | `users`, `user_public_profiles`, `user_favourite_refuges`, `user_visited_refuges` | `accounts` | 2 (`0001`: `users` + perfils, perquè `refuges` hi depèn) i 3 (`0002`: llistes) |
| `refuges` | `refuges`, `refuge_amenities`, `refuge_links`, `refuge_media`, `refuge_condition_votes`; vistes `refuge_condition`, `refuge_map` | `refuges` | 2 (+7: FK `refuge_media.experience_id`; +8: FK `refuge_condition_votes.source_proposal_id`) |
| `activity` | `refuge_visits`, `refuge_visit_participants` (+ vista `refuge_visit_totals`), `renovations`, `renovation_participants`, `renovation_expelled`, `experiences`, `doubts`, `answers` | `visits` (4), `renovations` (5), `doubts` (6), `experiences` (7) | 4–7 |
| `proposals` | `refuge_proposals` | `proposals` | 8 |
| `moderation` | `upload_intents` (app `uploads`, chunk 7); `media_reports`, `moderation_notices`, `moderation_hash_blocklist`, `media_deletion_queue` (app `moderation`, chunk 9) | `uploads`, `moderation` | 7, 9 |
| `audit` | `audit_logs` | `audit` | 9 |

`coords_refugis` **no té taula**: és la vista `refuges.refuge_map` (§4). El `visitors` del refugi i `visited_refuges` de l'usuari són **la mateixa** taula `users.user_visited_refuges` (decisió del PLAN).

### 1.2 Convencions

- Noms `snake_case`; taules en plural; PK `id`; FK cap a usuaris com a `<rol>_uid` (`creator_uid`, `reporter_uid`, `user_uid`…), la resta `<entitat>_id`.
- Tots els instants són **`timestamptz`** (UTC, `DEFAULT now()` / Django `db_default=Now()`); les dates de negoci (`ini_date`, `fin_date`, `visit_date`, `modified_at` del refugi) són **`date`** i les calcula l'aplicació amb `get_madrid_today()`. L'API continua emetent *strings* ISO amb la zona `Europe/Madrid` com ara **[FET]** (`api/utils/timezone_utils.py`): el serializer fa `astimezone(Madrid)`.
- **Sentinelles fora de la BD**: `'unknown'` (creador anonimitzat) i `'system'` (actor/denunciant automàtic) es desen com a **`NULL`**; l'API els torna a emetre com a `'unknown'`/`'system'` per mantenir el contracte.
- Text lliure: `CHECK (btrim(col) <> '')` quan és obligatori i límit de longitud igual al del serializer (`char_length(col) <= N`).
- Tota FK té `ON DELETE` explícit **i un índex** que comença per la columna de la FK (necessari per a les cascades i per a la RLS).
- Noms d'objectes **explícits** (obligatori a Django amb `name=`; màxim 63 caràcters): `<taula>_<cols>_pk|fk|uq|ck|idx|gist|gin|excl`.
- Cap `default=` als serializers d'actualització (gotcha 6 / M1): l'`UPDATE` només toca els camps enviats.
- `BEGIN … COMMIT` per petició (§7.3): totes les restriccions `DEFERRABLE` es comproven al `COMMIT`.

### 1.3 Extensions i *bootstrap* (una vegada per branca de Neon, pel propietari)

`migrator` **no** pot fer `CREATE EXTENSION` **[FET, `integrations/neon.md`]**; ho fa el propietari de la BD (`refugisdb_owner`) abans de la primera migració. `postgis`, `pg_trgm` i `unaccent` ja hi són (PostGIS 3.5, Postgres 17). **Falta `btree_gist`** (necessària per a `refuge_id WITH =` a l'`ExclusionConstraint` d'`uuid`):

```sql
-- Propietari (refugisdb_owner), un cop per branca (production i dev):
CREATE EXTENSION IF NOT EXISTS postgis;      -- ja existeix [FET]
CREATE EXTENSION IF NOT EXISTS pg_trgm;      -- ja existeix [FET]
CREATE EXTENSION IF NOT EXISTS unaccent;     -- ja existeix [FET]
CREATE EXTENSION IF NOT EXISTS btree_gist;   -- NOVA
GRANT CREATE ON DATABASE refugisdb TO migrator;   -- perquè core.0001 pugui fer CREATE SCHEMA (el migrator en serà el propietari)
ALTER ROLE app      NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
ALTER ROLE migrator NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
ALTER ROLE app SET statement_timeout = '20s';
ALTER ROLE app SET lock_timeout = '5s';
ALTER ROLE app SET idle_in_transaction_session_timeout = '30s';
```

Les extensions viuen a `public` (on les espera `django.contrib.gis` i on resolen `similarity()`, `%`, `gin_trgm_ops`, `ST_*`). Les funcions pròpies viuen a `core` i es **qualifiquen sempre** (`core.norm_name(...)`). L'entorn de proves (Docker `postgis/postgis:16`) ha de reproduir aquest *bootstrap* (script a `docker-entrypoint-initdb.d`, feina del chunk 1). El PLAN fixa Postgres+PostGIS 16 per als tests i Neon és 17: cap funcionalitat d'aquest disseny requereix >16 (`UNIQUE NULLS NOT DISTINCT` és de la 15, `bit_count` de la 14, `gen_random_uuid` del nucli des de la 13).

### 1.4 Identificadors: UUID vs. id de text estil Firestore → **UUID**

| Criteri | `text` (auto-ID Firestore, 20 car.) | **`uuid`** (recomanat) |
|---|---|---|
| Dades heretades | Cap: la BD és buida i els refugis es recarreguen | Cap restricció |
| Mida a les ~15 FK i índexs | ≥ 21 B per valor | 16 B |
| Validació de tipus | Qualsevol cadena entra com a id | Un id mal format és rebutjat pel tipus |
| Generació | Cal l'SDK de Firestore (que es retira) | `gen_random_uuid()` a la BD o `uuid4()` a Python; el *loader* pot generar UUIDv5 deterministes |
| Contracte API | *string* opac | *string* opac (36 car.); els serializers actuals accepten `max_length` 100/255 |
| Claus R2 | `refugis-lliures/{refuge_id}/{uuid}.ext` | idem (el `refuge_id` passa a ser un UUID) |

Regles:
- **Entitats** (`refuges`, `renovations`, `experiences`, `doubts`, `answers`, `refuge_visits`, `refuge_proposals`, `upload_intents`, `media_reports`, `moderation_notices`): `id uuid PRIMARY KEY DEFAULT gen_random_uuid()`. Django: `UUIDField(primary_key=True, default=uuid.uuid4, db_default=Func(function='gen_random_uuid'))` (el `db_default` fa que també funcionin els `INSERT` de SQL pla).
- `users.users.uid`: `varchar(128)` PK (UID de Firebase, ≤128 car.), amb `CHECK (char_length(uid) BETWEEN 1 AND 128 AND uid NOT IN ('system','unknown'))` perquè les sentinelles antigues no puguin ser un usuari real.
- `refuges.refuge_media.key`: `text` PK natural (clau R2, ja única i amb UUID dins). Cap altra taula hi apunta amb FK (les denúncies han de sobreviure a l'esborrat del mitjà).
- Taules d'unió/registre sense identitat de domini (`user_favourite_refuges`, `user_visited_refuges`, participants, vots, `audit_logs`, cua d'R2): `id bigint GENERATED ALWAYS AS IDENTITY` (Django 5.1 no té PK compostes: la 5.2 afegeix `CompositePrimaryKey`) + `UNIQUE` sobre les columnes naturals.
- **Ids mal formats a la URL** han de donar **404**, no 500: convertidor `<uuid:...>` a `api/urls.py` o captura de `ValidationError`/`DataError` a la capa de controller.
- Ids de refugis carregats del JSON: UUIDv5 determinista (§9); la resta, UUIDv4.

### 1.5 Mapatge schema ↔ Django: `db_table` amb cometes (decisió) vs. `search_path`

| Opció | Avantatges | Inconvenients |
|---|---|---|
| **A. `Meta.db_table = 'refuges"."refuges'`** (Django ho cita com `"refuges"."refuges"`) | Explícit i **independent de la connexió**: funciona amb el pooler de Neon (PgBouncer, mode transacció), amb el rol `migrator` per l'endpoint directe i amb la BD de proves. Les FK entre schemas funcionen. Els noms d'índex/constraint es netegen sols (Django treu `"` i `.` en generar-los). | Cal posar `name=` a tot índex/constraint (els noms autogenerats serien llargs); el SQL pla ha de qualificar sempre; `inspectdb` no és usable. |
| B. `OPTIONS: {'options': '-c search_path=...'}` | Models nets | El pooler en mode transacció **no admet** el paràmetre d'arrencada `options` **[INFERÈNCIA: error «unsupported startup parameter»; el chunk 1 ho ha de comprovar]**. |
| C. `ALTER ROLE app SET search_path = ...` | Funciona amb el pooler | Amaga el schema, genera col·lisions de noms entre schemas i **no** serveix per al DDL del `migrator` (cada app crea taules a un schema diferent). |

**Decisió: A.** El `search_path` es deixa per defecte (inclou `public`, on són PostGIS/`pg_trgm`/`unaccent`). Les funcions `SECURITY DEFINER` fixen el seu propi `SET search_path = pg_catalog, <schema>`.

**Precaucions amb PgBouncer en mode transacció** (aplicables a tot el disseny):
1. Cap estat de sessió: `SET`/`set_config(..., false)` es perd o **es filtra** a un altre client. Tot context és `set_config(name, value, true)` (local a la transacció) dins una transacció oberta (§7.3).
2. `DISABLE_SERVER_SIDE_CURSORS = True` (ja a `settings.py`); psycopg 3: `prepare_threshold=None` a `OPTIONS` fins que es verifiqui el suport de sentències preparades del pooler de Neon **[NO VERIFICAT]**.
3. Cap `pg_advisory_lock` de sessió: usar `pg_advisory_xact_lock`. Cap `LISTEN/NOTIFY`, cap taula temporal fora de la transacció.
4. `SELECT … FOR UPDATE` i `INSERT … ON CONFLICT` són segurs (dins de la transacció).
5. Les **migracions** i la càrrega de dades van per l'endpoint **directe** (`neon_migrator`), on la sessió és real.
6. Després d'una transacció amb `set_config(..., true)`, `current_setting('app.uid', true)` pot retornar **`''`** (no `NULL`) a la mateixa connexió; per això `core.uid()` fa `NULLIF(..., '')`.

---

## 2. Especificació per taula

**Com llegir cada fitxa.** *Columnes* (tipus PostgreSQL → camp Django), *restriccions* (PK, FK + `on_delete`, `UNIQUE`, `CHECK`), *índexs* (cadascun amb la consulta real que el justifica), *RLS* (decisió + SQL exacte) i *grants*. Els índexs de les FK són obligatoris i s'hi indiquen quan no queden coberts per un altre.

**Macros de les polítiques de RLS** (s'expandeixen **literalment** al generar la migració; són text, no funcions):

| Macro | Expansió |
|---|---|
| `{U}` | `(SELECT core.uid())` — UID de Firebase de la petició o `NULL` si és anònima |
| `{ADM}` | `(SELECT core.is_admin())` — el token porta el claim `role == 'admin'` |
| `{SYS}` | `(SELECT core.is_system())` — només dins `system_context()` (jobs, efectes creuats de moderació; §7.4) |

El `(SELECT …)` fa que el planificador avaluï la funció **una sola vegada per sentència** (*InitPlan*). Totes les polítiques són `PERMISSIVE` i `TO app`; el propietari (`migrator`) no hi està subjecte i no es fa servir `FORCE`. **Sense política per a una ordre = ordre denegada per a `app`.** Recordatori: `INSERT … RETURNING`, `UPDATE/DELETE … WHERE` i `ON CONFLICT DO UPDATE` també exigeixen que la fila passi la política de `SELECT`; per això cada taula té un `SELECT` que cobreix els casos d'escriptura. Les accions referencials (`ON DELETE CASCADE/SET NULL`) s'executen amb els privilegis del propietari de la taula referenciant **[INFERÈNCIA, comportament de Postgres: `ri_triggers.c` canvia a l'owner amb `SECURITY_NOFORCE_RLS`; cal un test amb el rol `app`]**: les cascades **no** queden bloquejades per la RLS.

### 2.0 Schema `core`: funcions (app `core`, chunk 1)

```sql
CREATE SCHEMA core;

-- Context de la petició (valors que posa l'aplicació amb set_config(..., true), §7.3)
CREATE FUNCTION core.uid() RETURNS text LANGUAGE sql STABLE PARALLEL SAFE
  AS $$ SELECT NULLIF(current_setting('app.uid', true), '') $$;
CREATE FUNCTION core.is_admin() RETURNS boolean LANGUAGE sql STABLE PARALLEL SAFE
  AS $$ SELECT COALESCE(current_setting('app.is_admin', true), '') = 'true' $$;
CREATE FUNCTION core.is_system() RETURNS boolean LANGUAGE sql STABLE PARALLEL SAFE
  AS $$ SELECT COALESCE(current_setting('app.is_system', true), '') = 'true' $$;

-- unaccent NO és IMMUTABLE (depèn del diccionari). Embolcall IMMUTABLE amb el diccionari fixat per OID de nom:
-- permet índexs d'expressió. Risc acceptat: si es canvia el fitxer de regles d'unaccent cal REINDEX.
CREATE FUNCTION core.immutable_unaccent(text) RETURNS text
  LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT
  AS $$ SELECT public.unaccent('public.unaccent'::regdictionary, $1) $$;

-- Forma normalitzada per a la cerca per nom (sense accents, minúscules). Mateixa expressió a l'índex i a les consultes.
CREATE FUNCTION core.norm_name(text) RETURNS text
  LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT
  AS $$ SELECT core.immutable_unaccent(lower($1)) $$;

-- Arrodoniment half-to-even (== round() de Python 3, el que fa RefugiSerializer.to_representation).
-- round(numeric) de Postgres arrodoneix .5 cap a fora (2.5 -> 3); Python dóna 2.
CREATE FUNCTION core.round_half_even(numeric) RETURNS integer
  LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT
  AS $$ SELECT CASE WHEN $1 - floor($1) = 0.5 THEN (2 * round($1 / 2))::integer
                    ELSE round($1)::integer END $$;

GRANT USAGE ON SCHEMA core TO app;
GRANT EXECUTE ON FUNCTION core.uid(), core.is_admin(), core.is_system(),
  core.immutable_unaccent(text), core.norm_name(text), core.round_half_even(numeric) TO app;
```

`AVG(smallint)` retorna `numeric` exacte (p. ex. `2.5000000000000000`), de manera que la detecció de `.5` és exacta; el càlcul incremental en `float` de Python podia donar `2.4999999999999996` en alguns casos (mitjanes de ≥6 vots) **[INFERÈNCIA]**, de manera que la versió SQL és més correcta que l'actual. Canviar a *half-up* és una línia (dubte 2).

---

### 2.1 `users.users` (app `accounts`; **RLS sí**)

Dades **privades i minimitzades** (decisió del PLAN): sense email ni data de naixement. Els camps públics són a [`user_public_profiles`](#22-usersuser_public_profiles-app-accounts-rls-sí).

| Columna | Tipus → Django | Null | Default | Notes |
|---|---|---|---|---|
| `uid` | `varchar(128)` → `CharField(max_length=128, primary_key=True)` | NO | — | UID de Firebase |
| `language` | `varchar(2)` → `CharField(choices=Language)` | NO | `'ca'` | `ca/es/en/fr` |
| `created_at` | `timestamptz` → `DateTimeField` | NO | `now()` | |
| `age_confirmed_at` | `timestamptz` | SÍ | — | només es desa si s'ha confirmat; mai la data de naixement |
| `age_threshold` | `smallint` | SÍ | — | llindar vigent en confirmar (avui 16) |
| `moderation_strikes` | `smallint` | NO | `0` | |
| `is_blocked` | `boolean` | NO | `false` | |
| `blocked_reason` | `varchar(32)` | SÍ | — | `csam_confirmed`/`strikes`/`moderation_hash_match` |
| `blocked_at` | `timestamptz` | SÍ | — | |

Restriccions:
- `users_uid_ck`: `char_length(uid) BETWEEN 1 AND 128 AND uid NOT IN ('system','unknown')`
- `users_language_ck`: `language IN ('ca','es','en','fr')`
- `users_age_pair_ck`: `(age_confirmed_at IS NULL) = (age_threshold IS NULL)`; `users_age_threshold_ck`: `age_threshold IS NULL OR age_threshold BETWEEN 13 AND 21`
- `users_strikes_ck`: `moderation_strikes >= 0`
- `users_blocked_ck`: `is_blocked OR (blocked_reason IS NULL AND blocked_at IS NULL)`; `users_blocked_reason_ck`: `blocked_reason IS NULL OR blocked_reason IN ('csam_confirmed','strikes','moderation_hash_match')`

Índexs: només la PK (totes les consultes són per `uid`: `UserDAO.get_user_by_uid`, `user_exists`, `IsNotBlocked`, `IsAgeConfirmed`).

RLS:
```sql
ALTER TABLE users.users ENABLE ROW LEVEL SECURITY;
CREATE POLICY users_select ON users.users FOR SELECT TO app
  USING (uid = {U} OR {ADM} OR {SYS});
CREATE POLICY users_insert ON users.users FOR INSERT TO app    -- POST /users/: només el propi compte i sense moderació prèvia
  WITH CHECK ((uid = {U} AND moderation_strikes = 0 AND NOT is_blocked
               AND blocked_reason IS NULL AND blocked_at IS NULL) OR {SYS});
CREATE POLICY users_update ON users.users FOR UPDATE TO app    -- PATCH propi; l'admin/sistema (strikes, bloqueig d'altres)
  USING (uid = {U} OR {ADM} OR {SYS})
  WITH CHECK (uid = {U} OR {ADM} OR {SYS});
CREATE POLICY users_delete ON users.users FOR DELETE TO app    -- IsSameUser (sense bypass d'admin, com ara)
  USING (uid = {U} OR {SYS});

-- Les columnes de moderació només les canvia un admin/sistema (la RLS no és per columna):
CREATE FUNCTION users.fn_users_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NOT (core.is_admin() OR core.is_system()) AND (
       NEW.uid IS DISTINCT FROM OLD.uid
    OR NEW.created_at IS DISTINCT FROM OLD.created_at
    OR NEW.moderation_strikes IS DISTINCT FROM OLD.moderation_strikes
    OR NEW.is_blocked IS DISTINCT FROM OLD.is_blocked
    OR NEW.blocked_reason IS DISTINCT FROM OLD.blocked_reason
    OR NEW.blocked_at IS DISTINCT FROM OLD.blocked_at) THEN
    RAISE EXCEPTION 'users: columna de moderació/immutable només modificable per admin/sistema'
      USING ERRCODE = 'insufficient_privilege';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER users_guard BEFORE UPDATE ON users.users
  FOR EACH ROW EXECUTE FUNCTION users.fn_users_guard();
```
Grants: `GRANT SELECT, INSERT, UPDATE, DELETE ON users.users TO app;`

Nota: el bloqueig automàtic per coincidència de hash (`_handle_moderation_block`) bloqueja **el mateix usuari** dins la seva petició: s'ha de fer dins `system_context()` (el *trigger* ho impediria altrament).

### 2.2 `users.user_public_profiles` (app `accounts`; **RLS sí**, lectura oberta)

1–1 amb `users`; creada a la mateixa transacció que l'usuari. Substitueix `username` i `media_metadata` (avatar) del document de Firestore.

| Columna | Tipus | Null | Default | Notes |
|---|---|---|---|---|
| `uid` | `varchar(128)` | NO | — | **PK i FK** → `users.users(uid)` `ON DELETE CASCADE` (`OneToOneField(primary_key=True)`) |
| `username` | `varchar(255)` | NO | `''` | el serializer permet buit; si no és buit ≥2 car. |
| `avatar_key` | `text` | SÍ | — | clau R2 `users-avatars/{uid}/{uuid}.webp` |
| `avatar_thumb_key` | `text` | SÍ | — | |
| `avatar_content_type` | `varchar(100)` | SÍ | — | |
| `avatar_width`, `avatar_height` | `integer` | SÍ | — | `> 0` |
| `avatar_size_bytes` | `bigint` | SÍ | — | `> 0` |
| `avatar_blurhash` | `varchar(100)` | SÍ | — | |
| `avatar_uploaded_at` | `timestamptz` | SÍ | — | |
| `updated_at` | `timestamptz` | NO | `now()` | |

Restriccions: `upp_username_ck`: `username = '' OR char_length(btrim(username)) >= 2`; `upp_avatar_all_or_none_ck`: `(avatar_key IS NULL) = (avatar_uploaded_at IS NULL)` i `avatar_thumb_key IS NULL OR avatar_key IS NOT NULL`; `upp_avatar_dims_ck`: dimensions i mida `> 0` si no són `NULL`. `UNIQUE (avatar_key)` parcial `WHERE avatar_key IS NOT NULL`.
Índexs: PK. (Futur: `gin (core.norm_name(username) gin_trgm_ops)` per cercar usuaris; no hi ha cap consulta avui.)

RLS:
```sql
ALTER TABLE users.user_public_profiles ENABLE ROW LEVEL SECURITY;
CREATE POLICY upp_select ON users.user_public_profiles FOR SELECT TO app USING (true);      -- lectura oberta
CREATE POLICY upp_insert ON users.user_public_profiles FOR INSERT TO app
  WITH CHECK (uid = {U} OR {SYS});
CREATE POLICY upp_update ON users.user_public_profiles FOR UPDATE TO app
  USING (uid = {U} OR {SYS}) WITH CHECK (uid = {U} OR {SYS});
-- sense DELETE: només per cascada des de users
```
Grants: `SELECT, INSERT, UPDATE ON users.user_public_profiles TO app`.

Trigger de neteja d'R2 (àvatar canviat/esborrat): `AFTER UPDATE OF avatar_key, avatar_thumb_key` i `AFTER DELETE` → insereix les claus antigues a `moderation.media_deletion_queue` (§2.23) quan canvien o desapareixen (`fn_profile_enqueue_r2()`, `SECURITY DEFINER`).

### 2.3 `users.user_favourite_refuges` (app `accounts`; **RLS sí**, privada)

Substitueix `users.favourite_refuges[]`.

| Columna | Tipus | Null | Default | Notes |
|---|---|---|---|---|
| `id` | `bigint identity` | NO | — | PK |
| `user_uid` | `varchar(128)` | NO | — | FK → `users.users` `CASCADE` |
| `refuge_id` | `uuid` | NO | — | FK → `refuges.refuges` `CASCADE` |
| `created_at` | `timestamptz` | NO | `now()` | conserva l'ordre d'inserció (Firestore `ArrayUnion`) |

Restriccions: `UNIQUE (user_uid, refuge_id)` (`favourites_user_refuge_uq`; afegir dues vegades és un `ON CONFLICT DO NOTHING`, no una carrera).
Índexs:
| Índex | Consulta |
|---|---|
| `(user_uid, refuge_id)` UNIQUE | `GET /users/{uid}/favorite-refuges/`, `DELETE …/{refuge_id}/`, perfil (`favourite_refuges`), FK usuari |
| `(user_uid, created_at DESC, id DESC)` | llista paginada per cursor (*keyset*) |
| `(refuge_id)` | FK/cascada en esborrar un refugi |

RLS:
```sql
ALTER TABLE users.user_favourite_refuges ENABLE ROW LEVEL SECURITY;
CREATE POLICY fav_select ON users.user_favourite_refuges FOR SELECT TO app USING (user_uid = {U} OR {SYS});
CREATE POLICY fav_insert ON users.user_favourite_refuges FOR INSERT TO app WITH CHECK (user_uid = {U} OR {SYS});
CREATE POLICY fav_delete ON users.user_favourite_refuges FOR DELETE TO app USING (user_uid = {U} OR {SYS});
```
Grants: `SELECT, INSERT, DELETE`.

### 2.4 `users.user_visited_refuges` (app `accounts`; **RLS sí**)

Única font de veritat de «refugis visitats d'un usuari» **i** de `refuge.visitors` (decisió del PLAN). S'omple per `POST /users/{uid}/visited-refuges/` i pel job diari (`process_yesterday_visits`).

Columnes: `id bigint identity PK`, `user_uid` FK `users` `CASCADE`, `refuge_id` FK `refuges` `CASCADE`, `created_at timestamptz DEFAULT now()`.
Restriccions: `UNIQUE (user_uid, refuge_id)`.
Índexs: `(user_uid, refuge_id)` UNIQUE (perfil i llista); `(user_uid, created_at DESC, id DESC)` (keyset); **`(refuge_id, user_uid)`** (llista `visitors` del refugi i FK/cascada).

RLS (privada; l'admin pot veure `visitors`, vegeu dubte 5):
```sql
ALTER TABLE users.user_visited_refuges ENABLE ROW LEVEL SECURITY;
CREATE POLICY visited_select ON users.user_visited_refuges FOR SELECT TO app
  USING (user_uid = {U} OR {ADM} OR {SYS});
CREATE POLICY visited_insert ON users.user_visited_refuges FOR INSERT TO app
  WITH CHECK (user_uid = {U} OR {SYS});                 -- el job diari insereix per a molts usuaris amb {SYS}
CREATE POLICY visited_delete ON users.user_visited_refuges FOR DELETE TO app
  USING (user_uid = {U} OR {SYS});
```
Grants: `SELECT, INSERT, DELETE`.

---

### 2.5 `refuges.refuges` (app `refuges`; **RLS sí**, lectura pública)

| Columna | Tipus → Django | Null | Default | Notes |
|---|---|---|---|---|
| `id` | `uuid` | NO | `gen_random_uuid()` | PK |
| `name` | `varchar(255)` | NO | — | màx. real 61 |
| `surname` | `varchar(255)` | SÍ | — | àlies; 487 refugis en tenen. **El backend actual no l'emet a `GET /refuges/{id}/`** però sí a la llista de coordenades; es passarà a emetre al detall (additiu; el DTO del frontend ja el té) |
| `type` | `varchar(64)` → `CharField(choices=RefugeType)` | NO | `'non gardé'` | vegeu §3 |
| `coord` | `geography(Point,4326)` → `PointField(geography=True, srid=4326, spatial_index=False)` | NO | — | **x = long, y = lat** |
| `altitude` | `integer` | SÍ | — | m |
| `places` | `integer` | SÍ | — | 405 refugis sense dada → `NULL` (no 0) |
| `remarque` | `text` | NO | `''` | |
| `description` | `text` | NO | `''` | 39 buides al JSON |
| `region` | `varchar(255)` | SÍ | — | `''` → `NULL` |
| `departement` | `varchar(255)` | SÍ | — | `''` → `NULL` |
| `modified_at` | `date` | SÍ | — | data de negoci (per a refugis nous = data de la proposta aprovada); 885 refugis del JSON sense dada |
| `created_at` | `timestamptz` | NO | `now()` | tècnica |

Restriccions:
- `refuges_name_ck`: `btrim(name) <> ''`; `refuges_surname_ck`: `surname IS NULL OR btrim(surname) <> ''`
- `refuges_type_ck`: `type IN ('non gardé','fermée','cabane ouverte mais ocupee par le berger l ete','orri','emergence','key_needed')` **[FET: `VALID_TYPES`/`ALLOWED_REFUGE_TYPES`; el JSON només usa els 4 primers]**
- `refuges_altitude_ck`: `altitude IS NULL OR altitude BETWEEN 0 AND 8848`
- `refuges_places_ck`: `places IS NULL OR places >= 0`
- `refuges_coord_ck`: `ST_Y(coord::geometry) BETWEEN -90 AND 90 AND ST_X(coord::geometry) BETWEEN -180 AND 180` (el tipus ja ho garanteix per a `geography`; es deixa com a documentació/defensa davant coordenades 0,0 → `NOT (ST_X(...) = 0 AND ST_Y(...) = 0)`)
- **Sense `UNIQUE(name)`**: el JSON té 8 noms repetits (p. ex. «Cabane de la Plagne» ×3) i una parella de coordenades compartida **[FET]**. La comanda del frontend/`search_by_name` que assumia «el nom és únic» era errònia (B2).

Índexs:
| Índex | Definició | Consulta que el justifica |
|---|---|---|
| `refuges_coord_gist` | `GIST (coord)` | proximitat: `ST_DWithin(coord, :p, 200)` en crear una proposta (duplicats); caixa del mapa `coord && ST_MakeEnvelope(...)::geography` |
| `refuges_name_trgm_gin` | `GIN (core.norm_name(name) gin_trgm_ops)` | cerca per nom: `core.norm_name(name) % core.norm_name(:q)` i `… LIKE '%'||core.norm_name(:q)||'%'` (B2) |
| `refuges_surname_trgm_gin` | `GIN (core.norm_name(surname) gin_trgm_ops) WHERE surname IS NOT NULL` | idem sobre l'àlies |
| `refuges_type_idx` | `(type)` | filtre `type IN (...)` (`TypeOnly*`, `Type*Strategy`) |
| `refuges_places_idx` | `(places) WHERE places IS NOT NULL` | filtre `places >= / <=` |
| `refuges_altitude_idx` | `(altitude) WHERE altitude IS NOT NULL` | filtre `altitude >= / <=` |

Les 15 estratègies de Firestore existien només per als índexs compostos de Firestore: a SQL és **una sola consulta dinàmica** (§5.3). Amb ~1,5 mil files el planificador farà `Seq Scan` als filtres numèrics (i és correcte); els tres índexs `btree` són barats i es mantenen pel creixement, però **el GIST i el GIN són els que importen**. `ANALYZE` després de la càrrega.

RLS:
```sql
ALTER TABLE refuges.refuges ENABLE ROW LEVEL SECURITY;
CREATE POLICY refuges_select ON refuges.refuges FOR SELECT TO app USING (true);   -- lectura pública (anònims inclosos)
CREATE POLICY refuges_insert ON refuges.refuges FOR INSERT TO app WITH CHECK ({ADM} OR {SYS});   -- aprovar proposta create
CREATE POLICY refuges_update ON refuges.refuges FOR UPDATE TO app USING ({ADM} OR {SYS}) WITH CHECK ({ADM} OR {SYS});
CREATE POLICY refuges_delete ON refuges.refuges FOR DELETE TO app USING ({ADM} OR {SYS});
```
Grants: `SELECT, INSERT, UPDATE, DELETE`. Vistes `refuge_condition` i `refuge_map`: §4.

### 2.6 `refuges.refuge_amenities` (app `refuges`; **RLS sí**, lectura pública)

1–1 amb `refuges` (`info_comp`). `info_couchage` i `info_eau` **s'ignoren** (decisió del PLAN).

| Columna | Tipus | Null | Default |
|---|---|---|---|
| `refuge_id` | `uuid` | NO | PK i FK → `refuges.refuges` `CASCADE` (`OneToOneField(primary_key=True, related_name='amenities')`) |
| `manque_un_mur`, `cheminee`, `poele`, `couvertures`, `latrines`, `bois`, `eau`, `matelas`, `couchage`, `bas_flancs`, `lits`, `mezzanine_etage` | `boolean` | NO | `false` |

Índexs: PK (tot s'accedeix per `refuge_id`; cap filtre per serveis a l'API actual). Si algun dia es filtra per serveis: índexs parcials `WHERE eau` etc.
Invariant «tot refugi té fila d'amenities»: l'aplicació la crea a la mateixa transacció (el *loader* i l'aprovació de propostes `create`); les lectures fan `LEFT JOIN` i tracten l'absència com a tot `false`.
RLS: igual que `refuges` (`USING (true)` per a `SELECT`; `INSERT/UPDATE/DELETE` només `{ADM} OR {SYS}`), polítiques `amen_select/insert/update/delete`. Grants: `SELECT, INSERT, UPDATE, DELETE`.

### 2.7 `refuges.refuge_links` (app `refuges`; **RLS sí**, lectura pública)

| Columna | Tipus | Null | Notes |
|---|---|---|---|
| `id` | `bigint identity` | NO | PK |
| `refuge_id` | `uuid` | NO | FK → `refuges.refuges` `CASCADE` |
| `position` | `smallint` | NO | ordre (0..n); `CHECK (position >= 0)` |
| `url` | `text` | NO | `CHECK (url ~* '^https?://' AND char_length(url) <= 2048)`; el JSON té màx. 171 car., 0 duplicats per refugi, 2.075 enllaços |

Restriccions: `UNIQUE (refuge_id, position) DEFERRABLE INITIALLY DEFERRED` (permet reordenar a la mateixa transacció) i `UNIQUE (refuge_id, url)` (sense enllaços duplicats).
Índexs: els dos `UNIQUE` (el primer serveix també com a índex de la FK i per a `ORDER BY position`).
RLS: com `refuges` (`links_select/insert/update/delete`). Grants: `SELECT, INSERT, UPDATE, DELETE`.

### 2.8 `refuges.refuge_media` (app `refuges`; **RLS sí**)

Substitueix el *map* `media_metadata` del document del refugi. Un mitjà és una imatge o un vídeo d'un refugi, i opcionalment forma part d'una experiència (`experience_id`; substitueix `experiences.media_keys`).

| Columna | Tipus → Django | Null | Default | Notes |
|---|---|---|---|---|
| `key` | `text` | NO | — | **PK** (clau R2 `refugis-lliures/{refuge_id}/{uuid}.ext`) |
| `refuge_id` | `uuid` | NO | — | FK → `refuges.refuges` `CASCADE` |
| `creator_uid` | `varchar(128)` | NO | — | FK → `users.users` `CASCADE` (les fotos d'un usuari s'esborren amb ell) |
| `experience_id` | `uuid` | SÍ | — | FK → `activity.experiences` `CASCADE` (afegida al chunk 7; abans, columna `uuid` sense FK no és possible a Django: el camp s'afegeix aleshores) |
| `media_type` | `varchar(5)` | NO | — | `image`/`video` |
| `content_type` | `varchar(100)` | NO | — | |
| `status` | `varchar(24)` | NO | `'visible'` | `visible`/`hidden_pending_review`/`removed` |
| `uploaded_at` | `timestamptz` | NO | `now()` | |
| `taken_at` | `timestamptz` | SÍ | — | data EXIF (no es treu; les coordenades EXIF sí que s'eliminen al processar) |
| `width`, `height` | `integer` | SÍ | — | `> 0` |
| `size_bytes` | `bigint` | SÍ | — | `> 0` |
| `thumb_key` | `text` | SÍ | — | `UNIQUE` parcial `WHERE thumb_key IS NOT NULL` |
| `blurhash` | `varchar(100)` | SÍ | — | |
| `rights_confirmed_at` | `timestamptz` | NO | — | la pujada exigeix `rights_confirmed = true` |

Restriccions: `refuge_media_status_ck`, `refuge_media_type_ck` (valors de §3); `key <> ''`; `thumb_key IS NULL OR thumb_key <> key`. **No hi ha FK cap a aquesta taula** (denúncies i avisos desen `media_key` com a text perquè han de sobreviure a la retenció de l'evidència, `moderation-hold/`).

Índexs:
| Índex | Consulta |
|---|---|
| `(refuge_id, uploaded_at, key)` | `GET /refuges/{id}/media/` (ordre determinista; el «primer» mitjà de la llista de preferits/visitats = el primer `visible` per `uploaded_at`), imatges del detall, FK/cascada del refugi. *Keyset*: `(uploaded_at, key) > (:t, :k)` |
| `(creator_uid, uploaded_at)` | `uploaded_photos_keys` del perfil; esborrat d'usuari; política RLS «propi»; FK |
| `(experience_id) WHERE experience_id IS NOT NULL` | imatges d'una experiència; FK/cascada |
| `(thumb_key) UNIQUE WHERE thumb_key IS NOT NULL` | integritat |

(Amb Firestore el «primer» mitjà era arbitrari: les claus del *map* són UUIDs. L'ordre `uploaded_at, key` fa el resultat determinista; és un canvi benigne.)

RLS:
```sql
ALTER TABLE refuges.refuge_media ENABLE ROW LEVEL SECURITY;
CREATE POLICY media_select ON refuges.refuge_media FOR SELECT TO app       -- visible per a tothom; la resta autor/admin
  USING (status = 'visible' OR creator_uid = {U} OR {ADM} OR {SYS});
CREATE POLICY media_insert ON refuges.refuge_media FOR INSERT TO app       -- upload-intents/confirm
  WITH CHECK (
    ( creator_uid = {U} AND status = 'visible'
      AND (experience_id IS NULL OR EXISTS (SELECT 1 FROM activity.experiences e
                                            WHERE e.id = experience_id AND e.creator_uid = {U})) )
    OR {ADM} OR {SYS});
CREATE POLICY media_update ON refuges.refuge_media FOR UPDATE TO app       -- canvi d'estat: només moderació
  USING ({ADM} OR {SYS}) WITH CHECK ({ADM} OR {SYS});
CREATE POLICY media_delete ON refuges.refuge_media FOR DELETE TO app       -- IsMediaUploader: autor o admin
  USING (creator_uid = {U} OR {ADM} OR {SYS});
```
Grants: `SELECT, INSERT, UPDATE, DELETE`.

Trigger de cua d'R2: `AFTER DELETE ... FOR EACH ROW` → `moderation.media_deletion_queue (r2_key, reason)` amb `OLD.key` i `OLD.thumb_key` (`fn_media_enqueue_r2()`, `SECURITY DEFINER`, `ON CONFLICT DO NOTHING`). **Excepció** (retenció d'evidència, `_hold_media`): si `current_setting('app.skip_r2_queue', true) = 'true'` no encua (el flux de retenció mou els fitxers a `moderation-hold/` en comptes d'esborrar-los; només `system_context()` pot posar-ho). Això cobreix **totes** les vies d'esborrat (usuari, experiència, refugi, moderació) sense codi a cada controller.

### 2.9 `refuges.refuge_condition_votes` (app `refuges`; **RLS sí**)

Substitueix `condition` + `num_contributed_conditions` (semàntica de [`deep-dives/condition-average.md`](../deep-dives/condition-average.md): la condició és la **mitjana** de totes les aportacions; cada proposta aprovada amb `condition` suma una).

| Columna | Tipus | Null | Default | Notes |
|---|---|---|---|---|
| `id` | `bigint identity` | NO | — | PK |
| `refuge_id` | `uuid` | NO | — | FK → `refuges.refuges` `CASCADE` |
| `value` | `smallint` | NO | — | `CHECK (value BETWEEN 0 AND 3)` (0 pobre · 1 correcte · 2 bé · 3 excel·lent) |
| `source_proposal_id` | `uuid` | SÍ | — | FK → `proposals.refuge_proposals` `SET NULL` (afegida al chunk 8). `NULL` = vot llavor (`assign_conditions`) |
| `user_uid` | `varchar(128)` | SÍ | — | FK → `users.users` **`SET NULL`**: el vot continua comptant a la mitjana (és l'anàleg de l'anonimització `'unknown'` de les propostes) |
| `created_at` | `timestamptz` | NO | `now()` | |

Restriccions: `UNIQUE (source_proposal_id) WHERE source_proposal_id IS NOT NULL` (una proposta aporta com a màxim **un** vot: segona barrera contra la doble aprovació C2).
Índexs: **`(refuge_id) INCLUDE (value)`** → `AVG/COUNT` per refugi amb *index-only scan* (vista `refuge_condition`, filtre per condició); `(user_uid) WHERE user_uid IS NOT NULL` (FK); l'`UNIQUE` parcial.

RLS (privada; l'agregat públic surt de la vista `refuge_condition`, que s'executa com a propietari i no depèn d'aquestes polítiques):
```sql
ALTER TABLE refuges.refuge_condition_votes ENABLE ROW LEVEL SECURITY;
CREATE POLICY votes_select ON refuges.refuge_condition_votes FOR SELECT TO app USING (user_uid = {U} OR {ADM} OR {SYS});
CREATE POLICY votes_insert ON refuges.refuge_condition_votes FOR INSERT TO app WITH CHECK ({ADM} OR {SYS});  -- aprovació d'una proposta
-- sense UPDATE/DELETE: només per cascada
```
Grants: `SELECT, INSERT`. Consulta de *seeding* i de lectura: §4 i §9.

---

### 2.10 `activity.refuge_visits` (app `visits`; **RLS sí**)

Una fila per (refugi, dia). Els visitants són a `refuge_visit_participants`; **`total_visitors` no es desa** (M3 desapareix).

| Columna | Tipus | Null | Default | Notes |
|---|---|---|---|---|
| `id` | `uuid` | NO | `gen_random_uuid()` | PK |
| `refuge_id` | `uuid` | NO | — | FK → `refuges.refuges` `CASCADE` |
| `visit_date` | `date` | NO | — | API: camp `date` |
| `created_at` | `timestamptz` | NO | `now()` | |

Restriccions: **`UNIQUE (refuge_id, visit_date)`** (`visits_refuge_date_uq`; fixa M4: «comprova i crea» passa a `INSERT … ON CONFLICT (refuge_id, visit_date) DO NOTHING` + `SELECT`; a Django `bulk_create([...], ignore_conflicts=True)` o `get_or_create`). La regla «la data ha de ser ≥ avui» **no** és un `CHECK` (`CURRENT_DATE` no és immutable i cal una data relativa al moment de la creació): es manté al serializer/controller.
Índexs:
| Índex | Consulta |
|---|---|
| `(refuge_id, visit_date)` UNIQUE | `get_visit_by_refuge_and_date`; `GET /refuges/{id}/visits/` (`visit_date >= avui ORDER BY visit_date`); FK |
| `(visit_date)` | `get_visits_by_date(ahir)` del job diari |

RLS (qualsevol usuari autenticat veu les visites d'un refugi; els participants són privats, §2.11):
```sql
ALTER TABLE activity.refuge_visits ENABLE ROW LEVEL SECURITY;
CREATE POLICY visits_select ON activity.refuge_visits FOR SELECT TO app USING ({U} IS NOT NULL OR {SYS});
CREATE POLICY visits_insert ON activity.refuge_visits FOR INSERT TO app WITH CHECK ({U} IS NOT NULL OR {SYS});
CREATE POLICY visits_delete ON activity.refuge_visits FOR DELETE TO app USING ({SYS});   -- només el job (visites buides d'ahir)
```
Grants: `SELECT, INSERT, DELETE`.

### 2.11 `activity.refuge_visit_participants` (app `visits`; **RLS sí**)

Substitueix `visitors[{uid, num_visitors}]`.

| Columna | Tipus | Null | Default | Notes |
|---|---|---|---|---|
| `id` | `bigint identity` | NO | — | PK |
| `visit_id` | `uuid` | NO | — | FK → `activity.refuge_visits` `CASCADE` |
| `user_uid` | `varchar(128)` | NO | — | FK → `users.users` `CASCADE` |
| `num_visitors` | `integer` | NO | — | `CHECK (num_visitors >= 1)` (el serializer ja té `min_value=1`; **afegir `max_value`** al serializer per evitar valors absurds) |
| `created_at` | `timestamptz` | NO | `now()` | |

Restriccions: **`UNIQUE (visit_id, user_uid) INCLUDE (num_visitors)`** (`participants_visit_user_uq`).
Índexs:
| Índex | Consulta |
|---|---|
| `(visit_id, user_uid) INCLUDE (num_visitors)` UNIQUE | `total_visitors = SUM(num_visitors)` per *index-only scan*; «ja estàs registrat»; `is_visitor`/`num_visitors` de l'usuari; PATCH/DELETE de la seva fila |
| `(user_uid) INCLUDE (visit_id, num_visitors)` | `GET /users/{uid}/visits/` (B5: ja no cal recórrer tota la col·lecció); esborrat d'usuari; FK |

RLS (privada: només l'usuari veu **la seva** fila; els totals passen per la vista `activity.refuge_visit_totals`, §4):
```sql
ALTER TABLE activity.refuge_visit_participants ENABLE ROW LEVEL SECURITY;
CREATE POLICY vparts_select ON activity.refuge_visit_participants FOR SELECT TO app
  USING (user_uid = {U} OR {ADM} OR {SYS});
CREATE POLICY vparts_insert ON activity.refuge_visit_participants FOR INSERT TO app
  WITH CHECK (user_uid = {U} OR {SYS});
CREATE POLICY vparts_update ON activity.refuge_visit_participants FOR UPDATE TO app
  USING (user_uid = {U} OR {SYS}) WITH CHECK (user_uid = {U} OR {SYS});
CREATE POLICY vparts_delete ON activity.refuge_visit_participants FOR DELETE TO app
  USING (user_uid = {U} OR {SYS});
```
Grants: `SELECT, INSERT, UPDATE, DELETE`.
⚠ **Un `Sum('participants__num_visitors')` directe sota RLS només comptaria la fila de l'usuari.** Tots els totals han d'usar el model no gestionat de la vista `refuge_visit_totals` (§5.3).

### 2.12 `activity.renovations` (app `renovations`; **RLS sí**)

| Columna | Tipus | Null | Default | Notes |
|---|---|---|---|---|
| `id` | `uuid` | NO | `gen_random_uuid()` | PK |
| `refuge_id` | `uuid` | NO | — | FK → `refuges.refuges` `CASCADE` |
| `creator_uid` | `varchar(128)` | SÍ | — | FK → `users.users` **`SET NULL`** (reformes passades queden anònimes; API: `'unknown'`) |
| `ini_date`, `fin_date` | `date` | NO | — | rang **inclusiu** per als dos extrems |
| `description` | `text` | NO | — | |
| `materials_needed` | `text` | SÍ | — | |
| `group_link` | `text` | SÍ | — | enllaç a un grup privat (WhatsApp/Telegram); `NULL` només si el creador ha estat anonimitzat |
| `created_at` | `timestamptz` | NO | `now()` | |

Restriccions:
- `renovations_dates_ck`: **`ini_date < fin_date`** (`CHECK`; coincideix amb el `__post_init__` i amb el controller; el serializer actual deixa passar `ini == fin` → A1; vegeu dubte 1).
- `renovations_description_ck`: `btrim(description) <> ''`
- `renovations_group_link_ck`: `group_link IS NULL OR (group_link ~* '^https?://' AND char_length(group_link) <= 2048)`
- `renovations_anonymized_ck`: `group_link IS NOT NULL OR creator_uid IS NULL` (equival al `__post_init__`: l'enllaç és obligatori llevat de reformes anonimitzades)
- **`renovations_no_overlap`**: `EXCLUDE USING gist (refuge_id WITH =, daterange(ini_date, fin_date, '[]') WITH &&)` — **`btree_gist`** (§1.3).

**Per què una restricció d'exclusió sobre totes les files i no només les «actives».** El codi actual (`check_overlapping_renovations`) només compara amb reformes del refugi amb `fin_date >= avui` i amb límits inclusius: `[a,b]` i `[c,d]` se solapen sii `a <= d AND c <= b`, que és exactament `daterange(…,'[]') &&`. Una condició «activa» depèn de la data d'avui (`CURRENT_DATE` no és immutable, no es pot usar al predicat d'una restricció ni d'un índex). No cal: la creació exigeix `ini_date >= avui`, de manera que una reforma nova mai pot solapar-se amb una de passada (`fin_date < avui`); l'única diferència amb el comportament actual és el cas marginal d'editar les dates d'una reforma **en curs** perquè solapin amb una d'ja acabada, que ara es rebutja (més correcte). Les reformes anònimes (creador `NULL`) continuen comptant. Mapatge d'errors: un `IntegrityError` amb `constraint_name == 'renovations_no_overlap'` → 409 (el text que conté `'solapa'`, gotcha 9). La comprovació prèvia del controller (per retornar la reforma en conflicte) s'ha de fer **a la mateixa transacció**, però ja no és l'únic mecanisme: la carrera entre dues creacions concurrents la resol la BD. Django: `ExclusionConstraint(name='renovations_no_overlap', expressions=[('refuge', RangeOperators.EQUAL), (Func(F('ini_date'), F('fin_date'), Value('[]'), function='daterange', output_field=DateRangeField()), RangeOperators.OVERLAPS)])` (cal `django.contrib.postgres` a `INSTALLED_APPS`).

Trigger d'anonimització (el `SET NULL` de la FK dispara un `UPDATE`):
```sql
CREATE FUNCTION activity.fn_renovation_anonymize() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.creator_uid IS NOT NULL AND NEW.creator_uid IS NULL THEN NEW.group_link := NULL; END IF;  -- privacitat: el grup és privat
  RETURN NEW;
END $$;
CREATE TRIGGER renovations_anonymize BEFORE UPDATE OF creator_uid ON activity.renovations
  FOR EACH ROW EXECUTE FUNCTION activity.fn_renovation_anonymize();
```

Índexs:
| Índex | Consulta |
|---|---|
| `renovations_no_overlap` (GIST `refuge_id, daterange`) | solapaments; FK `refuge_id` |
| `(refuge_id, fin_date, ini_date)` | `get_renovations_by_refuge` (`refuge_id = ? [AND fin_date >= avui] ORDER BY ini_date`) |
| `(fin_date, ini_date)` | `get_all_renovations` (`fin_date >= avui ORDER BY ini_date`) |
| `(creator_uid, fin_date) WHERE creator_uid IS NOT NULL` | `delete_current_renovations_by_creator` (`creator_uid = ? AND fin_date >= avui`); `num_renovated_refuges`; FK |

RLS (el detall i les llistes són per a qualsevol usuari autenticat, com ara; només el creador edita/esborra):
```sql
ALTER TABLE activity.renovations ENABLE ROW LEVEL SECURITY;
CREATE POLICY renov_select ON activity.renovations FOR SELECT TO app USING ({U} IS NOT NULL OR {SYS});
CREATE POLICY renov_insert ON activity.renovations FOR INSERT TO app WITH CHECK (creator_uid = {U} OR {SYS});
CREATE POLICY renov_update ON activity.renovations FOR UPDATE TO app
  USING (creator_uid = {U} OR {SYS}) WITH CHECK (creator_uid = {U} OR {SYS});
CREATE POLICY renov_delete ON activity.renovations FOR DELETE TO app USING (creator_uid = {U} OR {SYS});
```
Grants: `SELECT, INSERT, UPDATE, DELETE`.

### 2.13 `activity.renovation_participants` i 2.14 `activity.renovation_expelled` (app `renovations`; **RLS sí**)

Substitueixen `participants_uids[]` i `expelled_uids[]`.

| Columna | `renovation_participants` | `renovation_expelled` |
|---|---|---|
| `id` | `bigint identity` PK | `bigint identity` PK |
| `renovation_id` | `uuid` NOT NULL FK → `activity.renovations` `CASCADE` | idem |
| `user_uid` | `varchar(128)` NOT NULL FK → `users.users` `CASCADE` | idem |
| `created_at` / `expelled_at` | `timestamptz NOT NULL DEFAULT now()` | `timestamptz NOT NULL DEFAULT now()` |

Restriccions: `UNIQUE (renovation_id, user_uid)` a les dues (afegir-se dues vegades = `ON CONFLICT DO NOTHING` o 409, ja no una carrera A3).
Invariants entre taules (trigger `BEFORE INSERT`, `SECURITY DEFINER` perquè llegeix l'altra taula saltant la RLS):
```sql
CREATE FUNCTION activity.fn_renovation_member_guard() RETURNS trigger
  LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, activity AS $$
BEGIN
  IF TG_TABLE_NAME = 'renovation_participants' THEN
    IF EXISTS (SELECT 1 FROM activity.renovation_expelled e
               WHERE e.renovation_id = NEW.renovation_id AND e.user_uid = NEW.user_uid) THEN
      RAISE EXCEPTION 'user expelled' USING ERRCODE = 'check_violation', CONSTRAINT = 'renovation_participants_not_expelled_ck';
    END IF;
    IF EXISTS (SELECT 1 FROM activity.renovations r
               WHERE r.id = NEW.renovation_id AND r.creator_uid = NEW.user_uid) THEN
      RAISE EXCEPTION 'creator cannot join' USING ERRCODE = 'check_violation', CONSTRAINT = 'renovation_participants_not_creator_ck';
    END IF;
  ELSE  -- renovation_expelled: cal haver sortit de participants abans (el DELETE i l'INSERT van a la mateixa transacció)
    IF EXISTS (SELECT 1 FROM activity.renovation_participants p
               WHERE p.renovation_id = NEW.renovation_id AND p.user_uid = NEW.user_uid) THEN
      RAISE EXCEPTION 'participant must be removed first' USING ERRCODE = 'check_violation', CONSTRAINT = 'renovation_expelled_not_participant_ck';
    END IF;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER renovation_participants_guard BEFORE INSERT ON activity.renovation_participants
  FOR EACH ROW EXECUTE FUNCTION activity.fn_renovation_member_guard();
CREATE TRIGGER renovation_expelled_guard BEFORE INSERT ON activity.renovation_expelled
  FOR EACH ROW EXECUTE FUNCTION activity.fn_renovation_member_guard();
```
(Els tres errors s'han de mapar als missatges actuals: «expulsat», «el creador no pot unir-se», 409.)

Índexs: `(renovation_id, user_uid)` UNIQUE (detall de la reforma); `(user_uid, renovation_id)` a cada taula (`num_renovated_refuges`, esborrat d'usuari — substitueix les consultes `array_contains` —, FK).

RLS:
```sql
ALTER TABLE activity.renovation_participants ENABLE ROW LEVEL SECURITY;
CREATE POLICY rparts_select ON activity.renovation_participants FOR SELECT TO app USING ({U} IS NOT NULL OR {SYS});
CREATE POLICY rparts_insert ON activity.renovation_participants FOR INSERT TO app WITH CHECK (user_uid = {U} OR {SYS});
CREATE POLICY rparts_delete ON activity.renovation_participants FOR DELETE TO app   -- sortir un mateix o expulsar el creador
  USING (user_uid = {U} OR {SYS}
         OR EXISTS (SELECT 1 FROM activity.renovations r WHERE r.id = renovation_id AND r.creator_uid = {U}));

ALTER TABLE activity.renovation_expelled ENABLE ROW LEVEL SECURITY;
CREATE POLICY rexp_select ON activity.renovation_expelled FOR SELECT TO app USING ({U} IS NOT NULL OR {SYS});
CREATE POLICY rexp_insert ON activity.renovation_expelled FOR INSERT TO app
  WITH CHECK ({SYS} OR EXISTS (SELECT 1 FROM activity.renovations r WHERE r.id = renovation_id AND r.creator_uid = {U}));
-- sense DELETE: una expulsió és definitiva (només per cascada)
```
Grants: participants `SELECT, INSERT, DELETE`; expelled `SELECT, INSERT`. (`expelled_uids` és visible per a tots els autenticats per mantenir el contracte; vegeu dubte 20.)

### 2.15 `activity.experiences` (app `experiences`; **RLS sí**, lectura pública)

| Columna | Tipus | Null | Default | Notes |
|---|---|---|---|---|
| `id` | `uuid` | NO | `gen_random_uuid()` | PK |
| `refuge_id` | `uuid` | NO | — | FK → `refuges.refuges` `CASCADE` |
| `creator_uid` | `varchar(128)` | NO | — | FK → `users.users` `CASCADE` |
| `comment` | `text` | NO | — | `CHECK (btrim(comment) <> '' AND char_length(comment) <= 2000)` |
| `created_at` | `timestamptz` | NO | `now()` | |
| `modified_at` | `timestamptz` | NO | `now()` | l'aplicació l'actualitza en editar (com ara) |

Els mitjans de l'experiència són `refuge_media.experience_id = id` (substitueix `media_keys`); en esborrar l'experiència es **cascaden** els mitjans i el trigger d'§2.8 encua els fitxers d'R2.
Índexs:
| Índex | Consulta |
|---|---|
| `(refuge_id, modified_at DESC, id DESC)` | `get_experiences_by_refuge_id` (`modified_at DESC`); *keyset* `(modified_at, id) < (:t, :i)`; FK |
| `(creator_uid, modified_at DESC)` | `num_shared_experiences`; `delete_experiences_by_creator`; FK |

RLS (lectura pública per decisió; l'API segueix exigint autenticació; l'admin pot editar/esborrar, com al controller):
```sql
ALTER TABLE activity.experiences ENABLE ROW LEVEL SECURITY;
CREATE POLICY exp_select ON activity.experiences FOR SELECT TO app USING (true);
CREATE POLICY exp_insert ON activity.experiences FOR INSERT TO app WITH CHECK (creator_uid = {U} OR {SYS});
CREATE POLICY exp_update ON activity.experiences FOR UPDATE TO app
  USING (creator_uid = {U} OR {ADM} OR {SYS}) WITH CHECK (creator_uid = {U} OR {ADM} OR {SYS});
CREATE POLICY exp_delete ON activity.experiences FOR DELETE TO app USING (creator_uid = {U} OR {ADM} OR {SYS});
```
Grants: `SELECT, INSERT, UPDATE, DELETE`.

### 2.16 `activity.doubts` (app `doubts`; **RLS sí**, lectura pública)

| Columna | Tipus | Null | Default | Notes |
|---|---|---|---|---|
| `id` | `uuid` | NO | `gen_random_uuid()` | PK |
| `refuge_id` | `uuid` | NO | — | FK → `refuges.refuges` `CASCADE` |
| `creator_uid` | `varchar(128)` | NO | — | FK → `users.users` `CASCADE` |
| `message` | `text` | NO | — | `CHECK (btrim(message) <> '' AND char_length(message) <= 2000)` |
| `created_at` | `timestamptz` | NO | `now()` | |

`answers_count` **no es desa** (§4). Índexs: `(refuge_id, created_at DESC, id DESC)` (`get_doubts_by_refuge_id`, *keyset*, FK), `(creator_uid)` (`delete_doubts_by_creator`, FK).

RLS (corregeix C1 també a la BD: només el creador o un admin poden esborrar):
```sql
ALTER TABLE activity.doubts ENABLE ROW LEVEL SECURITY;
CREATE POLICY doubts_select ON activity.doubts FOR SELECT TO app USING (true);
CREATE POLICY doubts_insert ON activity.doubts FOR INSERT TO app WITH CHECK (creator_uid = {U} OR {SYS});
CREATE POLICY doubts_delete ON activity.doubts FOR DELETE TO app USING (creator_uid = {U} OR {ADM} OR {SYS});
```
Grants: `SELECT, INSERT, DELETE` (no hi ha endpoint d'edició).

### 2.17 `activity.answers` (app `doubts`; **RLS sí**, lectura pública)

Subcol·lecció `doubts/{id}/answers` → taula plana amb arbre per `parent_answer_id`.

| Columna | Tipus | Null | Default | Notes |
|---|---|---|---|---|
| `id` | `uuid` | NO | `gen_random_uuid()` | PK |
| `doubt_id` | `uuid` | NO | — | FK → `activity.doubts` `CASCADE` |
| `creator_uid` | `varchar(128)` | NO | — | FK → `users.users` `CASCADE` |
| `parent_answer_id` | `uuid` | SÍ | — | `NULL` = resposta directa al dubte |
| `message` | `text` | NO | — | `CHECK (btrim(message) <> '' AND char_length(message) <= 2000)` |
| `created_at` | `timestamptz` | NO | `now()` | |

Restriccions:
- `answers_doubt_id_uq`: `UNIQUE (doubt_id, id)` (objectiu de la FK composta).
- **`answers_parent_same_doubt_fk`**: `FOREIGN KEY (doubt_id, parent_answer_id) REFERENCES activity.answers (doubt_id, id) ON DELETE CASCADE` (`MATCH SIMPLE`: si `parent_answer_id IS NULL` no es comprova). Garanteix que el pare **existeix i és del mateix dubte** (avui es comprova al controller i una resposta esborrada deixa fills orfes). Django 5.1 no té FK compostes: el model declara `parent_answer = ForeignKey('self', null=True, on_delete=CASCADE, db_constraint=False, related_name='replies')` i la restricció real es crea amb `RunSQL`.
- `answers_not_self_parent_ck`: `parent_answer_id IS NULL OR parent_answer_id <> id` (un cicle és impossible: el pare ha d'existir en inserir i `parent_answer_id` no s'actualitza).
- En esborrar una resposta s'esborra **tot el seu subarbre** (dubte 7).

Índexs:
| Índex | Consulta |
|---|---|
| `(doubt_id, created_at, id)` | `_get_answers_by_doubt_id` (`created_at ASC`); `answers_count`; FK `doubt_id` |
| `(doubt_id, parent_answer_id)` | cascada de la FK composta |
| `(creator_uid)` | `delete_answers_by_creator` (substitueix la *collection group query*); FK |

RLS:
```sql
ALTER TABLE activity.answers ENABLE ROW LEVEL SECURITY;
CREATE POLICY answers_select ON activity.answers FOR SELECT TO app USING (true);
CREATE POLICY answers_insert ON activity.answers FOR INSERT TO app WITH CHECK (creator_uid = {U} OR {SYS});
CREATE POLICY answers_delete ON activity.answers FOR DELETE TO app USING (creator_uid = {U} OR {ADM} OR {SYS});
```
Grants: `SELECT, INSERT, DELETE`.

---

### 2.18 `proposals.refuge_proposals` (app `proposals`; **RLS sí**)

| Columna | Tipus → Django | Null | Default | Notes |
|---|---|---|---|---|
| `id` | `uuid` | NO | `gen_random_uuid()` | PK |
| `refuge_id` | `uuid` | SÍ | — | FK → `refuges.refuges` **`SET NULL`** (decisió del PLAN). `NULL` en `create` pendent; s'omple en aprovar (`UPDATE … SET refuge_id = <nou>`); torna a `NULL` si el refugi s'esborra |
| `action` | `varchar(6)` | NO | — | `create`/`update`/`delete` |
| `status` | `varchar(8)` | NO | `'pending'` | `pending`/`approved`/`rejected` |
| `payload` | `jsonb` → `JSONField` | SÍ | — | camps del refugi tal com els valida `RefugeProposalPayloadSerializer` (`info_comp` en 0/1) |
| `refuge_snapshot` | `jsonb` | SÍ | — | còpia del refugi en forma d'API (sense `visitors` ni mitjans) en crear `update`/`delete` |
| `comment` | `text` | SÍ | — | `CHECK (char_length(comment) <= 4000)` (**afegir `max_length=4000` al serializer**) |
| `creator_uid` | `varchar(128)` | SÍ | — | FK → `users.users` **`SET NULL`** (API: `'unknown'`) |
| `created_at` | `timestamptz` | NO | `now()` | |
| `reviewer_uid` | `varchar(128)` | SÍ | — | FK → `users.users` **`SET NULL`** (admin; `NULL` també en el rebuig automàtic per esborrat del refugi) |
| `reviewed_at` | `timestamptz` | SÍ | — | |
| `rejection_reason` | `text` | SÍ | — | `CHECK (char_length(rejection_reason) <= 2000)` |

`CHECK`s (**`RunSQL`**: l'ORM no sap expressar `jsonb - text[]` ni `?`; `Meta.constraints` només n'ha de portar els simples):
```sql
ALTER TABLE proposals.refuge_proposals
  ADD CONSTRAINT refuge_proposals_action_ck CHECK (action IN ('create','update','delete')),
  ADD CONSTRAINT refuge_proposals_status_ck CHECK (status IN ('pending','approved','rejected')),
  -- regles de forma per acció (deep-dive refuge-proposals-payload §1)
  ADD CONSTRAINT refuge_proposals_shape_ck CHECK (
        (action = 'create' AND payload IS NOT NULL AND refuge_snapshot IS NULL
           AND jsonb_typeof(payload) = 'object' AND payload ? 'name' AND payload ? 'coord'
           AND jsonb_typeof(payload->'name') = 'string' AND btrim(payload->>'name') <> '')
     OR (action = 'update' AND payload IS NOT NULL AND refuge_snapshot IS NOT NULL
           AND jsonb_typeof(payload) = 'object' AND payload <> '{}'::jsonb)
     OR (action = 'delete' AND payload IS NULL AND refuge_snapshot IS NOT NULL)),
  -- refuge_id: create sense id fins que s'aprova; update/delete amb id mentre estan pendents
  ADD CONSTRAINT refuge_proposals_refuge_ref_ck CHECK (
        (action = 'create' AND (refuge_id IS NULL OR status = 'approved'))
     OR (action IN ('update','delete') AND (refuge_id IS NOT NULL OR status <> 'pending'))),
  -- estat de revisió coherent
  ADD CONSTRAINT refuge_proposals_review_ck CHECK (
        (status = 'pending'  AND reviewer_uid IS NULL AND reviewed_at IS NULL AND rejection_reason IS NULL)
     OR (status = 'approved' AND reviewed_at IS NOT NULL AND rejection_reason IS NULL)
     OR (status = 'rejected' AND reviewed_at IS NOT NULL)),
  -- llista tancada de claus (ALLOWED_REFUGE_FIELDS) i valors estructurals
  ADD CONSTRAINT refuge_proposals_payload_keys_ck CHECK (payload IS NULL OR
        (payload - ARRAY['name','coord','altitude','places','remarque','info_comp','description',
                         'links','type','region','departement','condition']) = '{}'::jsonb),
  ADD CONSTRAINT refuge_proposals_payload_type_ck CHECK (payload IS NULL OR payload->>'type' IS NULL OR
        payload->>'type' IN ('non gardé','fermée','cabane ouverte mais ocupee par le berger l ete','orri','emergence','key_needed')),
  ADD CONSTRAINT refuge_proposals_payload_coord_ck CHECK (payload IS NULL OR NOT (payload ? 'coord') OR
        (jsonb_typeof(payload->'coord') = 'object' AND payload->'coord' ?& ARRAY['lat','long'])),
  ADD CONSTRAINT refuge_proposals_size_ck CHECK (pg_column_size(payload) < 65536 AND pg_column_size(refuge_snapshot) < 65536);
```
Les validacions de valor (rang d'`altitude`/`places`/`condition`, URLs, 0/1 d'`info_comp`) continuen al serializer: el `CHECK` cobreix l'**estructura** (acció, forma, claus, tipus) i evita que una escriptura que salti el serializer deixi una proposta que després no es pugui aprovar (M9). Aquesta restricció (`refuge_proposals_refuge_ref_ck`) implica un **ordre obligatori** en esborrar un refugi: primer es **rebutgen** les propostes pendents d'aquell refugi (`UPDATE … SET status='rejected', reviewed_at=now(), rejection_reason='refuge has been deleted', reviewer_uid=NULL WHERE refuge_id=:id AND status='pending' AND id<>:esta`) i després s'esborra el refugi; altrament el `SET NULL` violaria el `CHECK` i la transacció falla (és el comportament desitjat: cap proposta pendent apunta a un refugi inexistent).

Índexs:
| Índex | Consulta |
|---|---|
| `(created_at DESC, id DESC) WHERE status = 'pending'` | cua de l'admin: `GET /refuges-proposals/?status=pending` |
| `(status, created_at DESC, id DESC)` | `list_all` amb `status` (aprovades/rebutjades) |
| `(creator_uid, created_at DESC, id DESC)` | `GET /my-refuges-proposals/`; esborrat d'usuari (`SET NULL`); FK |
| `(refuge_id, status)` | propostes d'un refugi (`filters={'status':'pending','refuge_id':…}` en esborrar-lo); FK |
| `(reviewer_uid) WHERE reviewer_uid IS NOT NULL` | FK |

**Aprovació bloquejable (C2)**:
```sql
BEGIN;                                                       -- transaction.atomic()
SELECT * FROM proposals.refuge_proposals
 WHERE id = :id AND status = 'pending' FOR UPDATE;           -- select_for_update(of=('self',)); 0 files => 404 o «already approved/rejected» (2n SELECT sense bloqueig per distingir-ho)
-- … aplicar l'acció (INSERT/UPDATE/DELETE de refuges, amenities, links, vot; cascades) …
INSERT INTO refuges.refuge_condition_votes (refuge_id, value, source_proposal_id, user_uid)
  VALUES (:rid, :cond, :id, :creator) ON CONFLICT (source_proposal_id) WHERE source_proposal_id IS NOT NULL DO NOTHING;
UPDATE proposals.refuge_proposals
   SET status = 'approved', reviewer_uid = :admin, reviewed_at = now(), refuge_id = COALESCE(:new_refuge_id, refuge_id)
 WHERE id = :id AND status = 'pending';                      -- rowcount = 1 o es desfà tot
COMMIT;
```
Semàntica **idèntica a l'actual** (`UpdateRefugeStrategy`): `modified_at` del refugi = data de **creació** de la proposta; `info_comp` en un `update` **substitueix** els 12 indicadors (els absents passen a `false`, com `InfoComplementaria.from_dict`); `links` es substitueixen sencers; `coord` → `Point(long, lat)`; `condition` afegeix un vot (ja no es recalcula cap mitjana).

RLS:
```sql
ALTER TABLE proposals.refuge_proposals ENABLE ROW LEVEL SECURITY;
CREATE POLICY proposals_select ON proposals.refuge_proposals FOR SELECT TO app     -- pròpies o admin
  USING (creator_uid = {U} OR {ADM} OR {SYS});
CREATE POLICY proposals_insert ON proposals.refuge_proposals FOR INSERT TO app
  WITH CHECK ((creator_uid = {U} AND status = 'pending') OR {SYS});
CREATE POLICY proposals_update ON proposals.refuge_proposals FOR UPDATE TO app     -- aprovar/rebutjar (+ rebuig automàtic)
  USING ({ADM} OR {SYS}) WITH CHECK ({ADM} OR {SYS});
-- sense DELETE: l'historial de propostes no s'esborra
```
Grants: `SELECT, INSERT, UPDATE`.

---

### 2.19 `moderation.upload_intents` (app `uploads`; **RLS sí**, privada)

Intents de pujada directa (URL PUT prefirmada a `quarantine/{id}`). TTL funcional d'1 dia (job de purga).

| Columna | Tipus | Null | Default | Notes |
|---|---|---|---|---|
| `id` | `uuid` | NO | `gen_random_uuid()` | PK (`upload_id`) |
| `user_uid` | `varchar(128)` | NO | — | FK → `users.users` `CASCADE` (API/Firestore: `uid`) |
| `target` | `varchar(10)` | NO | — | `refuge`/`experience`/`avatar` |
| `content_type` | `varchar(100)` | NO | — | |
| `size` | `bigint` | NO | — | `CHECK (size > 0)` |
| `quarantine_key` | `text` | NO | — | `UNIQUE` |
| `refuge_id` | `uuid` | SÍ | — | FK → `refuges.refuges` `CASCADE` |
| `experience_id` | `uuid` | SÍ | — | FK → `activity.experiences` `CASCADE` |
| `status` | `varchar(9)` | NO | `'pending'` | `pending`/`confirmed`/`failed` |
| `rights_confirmed_at` | `timestamptz` | NO | — | |
| `created_at` | `timestamptz` | NO | `now()` | |
| `expire_at` | `timestamptz` | NO | `now() + interval '1 day'` | |
| `result_key` | `text` | SÍ | — | clau final publicada |
| `failure_reason` | `varchar(24)` | SÍ | — | §3 |

Restriccions: `upload_intents_target_ck`, `_status_ck`, `_failure_reason_ck` (§3);
`upload_intents_shape_ck`: `(target='avatar' AND refuge_id IS NULL AND experience_id IS NULL) OR (target='refuge' AND refuge_id IS NOT NULL AND experience_id IS NULL) OR (target='experience' AND refuge_id IS NOT NULL AND experience_id IS NOT NULL)` (és `UploadIntent.__post_init__`);
`upload_intents_state_ck`: `(status = 'confirmed') = (result_key IS NOT NULL) AND (status = 'failed') = (failure_reason IS NOT NULL)`; `upload_intents_expire_ck`: `expire_at > created_at`.
Índexs: `(expire_at)` (purga: `DELETE … WHERE expire_at < now()`); `(user_uid, created_at DESC)` (FK; intents de l'usuari); `(refuge_id) WHERE refuge_id IS NOT NULL` i `(experience_id) WHERE experience_id IS NOT NULL` (FK/cascada); `quarantine_key` UNIQUE.

RLS:
```sql
ALTER TABLE moderation.upload_intents ENABLE ROW LEVEL SECURITY;
CREATE POLICY intents_select ON moderation.upload_intents FOR SELECT TO app USING (user_uid = {U} OR {SYS});
CREATE POLICY intents_insert ON moderation.upload_intents FOR INSERT TO app
  WITH CHECK (( user_uid = {U} AND status = 'pending'
                AND (experience_id IS NULL OR {ADM}
                     OR EXISTS (SELECT 1 FROM activity.experiences e WHERE e.id = experience_id AND e.creator_uid = {U})) )
              OR {SYS});
CREATE POLICY intents_update ON moderation.upload_intents FOR UPDATE TO app          -- mark_confirmed / mark_failed
  USING (user_uid = {U} OR {SYS}) WITH CHECK (user_uid = {U} OR {SYS});
CREATE POLICY intents_delete ON moderation.upload_intents FOR DELETE TO app USING ({SYS});   -- job de purga
```
Grants: `SELECT, INSERT, UPDATE, DELETE`. Retenció: purga diària `DELETE … WHERE expire_at < now()` en lots de 1.000 (`system_context()`).

### 2.20 `moderation.media_reports` (app `moderation`; **RLS sí**, privada: denunciant + admin)

Denúncies de mitjans (DSA art. 16). L'id determinista SHA-256 desapareix: la unicitat és una restricció (`UNIQUE`); l'`id` passa a ser `uuid` opac (l'admin l'usa a `PATCH /admin/media-reports/{id}/`).

| Columna | Tipus | Null | Default | Notes |
|---|---|---|---|---|
| `id` | `uuid` | NO | `gen_random_uuid()` | PK |
| `refuge_id` | `uuid` | SÍ | — | FK → `refuges.refuges` `CASCADE`. `NULL` a les denúncies **automàtiques** d'un avatar (el codi hi posava el `target` com a pseudo-refugi) |
| `media_key` | `varchar(500)` | NO | — | **sense FK** (pot ser `moderation-hold/...` o un mitjà ja esborrat) |
| `reporter_uid` | `varchar(128)` | SÍ | — | FK → `users.users` **`CASCADE`** (decisió del PLAN). `NULL` ⇔ `source='automatic'` (abans `'system'`) |
| `reason` | `varchar(32)` | NO | — | 16 motius (§3) |
| `details` | `text` | SÍ | — | ≤ 1000 |
| `media_creator_uid` | `varchar(128)` | SÍ | — | FK → `users.users` **`SET NULL`** (dubte 9): la denúncia es conserva anonimitzada |
| `status` | `varchar(8)` | NO | `'pending'` | `pending`/`resolved` |
| `priority` | `varchar(6)` | NO | `'normal'` | `high`/`normal` |
| `created_at` | `timestamptz` | NO | `now()` | |
| `resolved_at` | `timestamptz` | SÍ | — | |
| `resolved_by` | `varchar(128)` | SÍ | — | FK → `users.users` `SET NULL` |
| `action` | `varchar(20)` | SÍ | — | `dismiss`/`remove`/`remove_and_strike` |
| `statement` | `text` | SÍ | — | ≤ 2000 |
| `source` | `varchar(9)` | NO | `'user'` | `user`/`automatic` |

Restriccions (nom `media_reports_*`):
- `UNIQUE NULLS NOT DISTINCT (refuge_id, media_key, reporter_uid)` — `media_reports_unique_reporter_uq` (Django: `UniqueConstraint(..., nulls_distinct=False)`, PG ≥ 15): **una denúncia per (refugi, mitjà, denunciant)**; el 409 «already_reported» és un `IntegrityError` d'aquesta restricció.
- `reason IN (…16…)`; `status`, `priority`, `action`, `source` amb els seus `IN`.
- `media_reports_other_details_ck`: `reason <> 'other' OR (details IS NOT NULL AND btrim(details) <> '')`; `details IS NULL OR char_length(details) <= 1000`.
- `media_reports_source_ck`: `(source = 'user' AND reporter_uid IS NOT NULL) OR (source = 'automatic' AND reporter_uid IS NULL)`.
- `media_reports_resolution_ck`: `(status = 'pending' AND resolved_at IS NULL AND resolved_by IS NULL AND action IS NULL AND statement IS NULL) OR (status = 'resolved' AND resolved_at IS NOT NULL AND action IS NOT NULL AND statement IS NOT NULL)`.
- `media_reports_not_own_ck`: `reporter_uid IS NULL OR media_creator_uid IS NULL OR reporter_uid <> media_creator_uid` (`own_media`).

Índexs:
| Índex | Consulta |
|---|---|
| `(refuge_id, media_key, reporter_uid)` UNIQUE | `list_reports_for_media`, `count_distinct_pending_reporters` (`COUNT(DISTINCT reporter_uid) … status='pending'`), FK `refuge_id` |
| `(status, priority, created_at, id)` | `list_reports(status)`: `ORDER BY priority, created_at, id` (`'high' < 'normal'` alfabèticament: high primer; cal un test que ho fixi). Cobreix també `resolved` |
| `(reporter_uid)` | FK/cascada en esborrar el denunciant |
| `(media_creator_uid) WHERE media_creator_uid IS NOT NULL`; `(resolved_by) WHERE resolved_by IS NOT NULL` | FK `SET NULL` |

Una sola consulta per a la llista d'admin (sense N+1 de `get_raw_media_metadata` per refugi): `SELECT r.*, m.* FROM moderation.media_reports r LEFT JOIN refuges.refuge_media m ON m.key = r.media_key WHERE r.status = %s ORDER BY r.priority, r.created_at, r.id`.

RLS:
```sql
ALTER TABLE moderation.media_reports ENABLE ROW LEVEL SECURITY;
CREATE POLICY reports_select ON moderation.media_reports FOR SELECT TO app USING (reporter_uid = {U} OR {ADM} OR {SYS});
CREATE POLICY reports_insert ON moderation.media_reports FOR INSERT TO app
  WITH CHECK ((reporter_uid = {U} AND source = 'user' AND status = 'pending') OR {SYS});   -- automàtiques: {SYS}
CREATE POLICY reports_update ON moderation.media_reports FOR UPDATE TO app               -- resolució
  USING ({ADM} OR {SYS}) WITH CHECK ({ADM} OR {SYS});
CREATE POLICY reports_delete ON moderation.media_reports FOR DELETE TO app USING ({SYS}); -- purga de retenció
```
Grants: `SELECT, INSERT, UPDATE, DELETE`.
⚠ **Efectes creuats de moderació** (la petició del denunciant ha de tocar files d'altres usuaris): auto-ocultar el mitjà (`refuge_media.status`), comptar denunciants **diferents** (la RLS només deixaria veure les pròpies), inserir l'avís (`moderation_notices`) a l'autor. Han d'executar-se dins un únic bloc `system_context()` curt i acotat (§7.4); l'admin que resol (`{ADM}`) ja ho veu tot.

### 2.21 `moderation.moderation_notices` (app `moderation`; **RLS sí**, privada)

Declaració de motius (art. 17 DSA) adreçada a un usuari.

| Columna | Tipus | Null | Default | Notes |
|---|---|---|---|---|
| `id` | `uuid` | NO | `gen_random_uuid()` | PK |
| `user_uid` | `varchar(128)` | NO | — | FK → `users.users` **`CASCADE`** (API: `uid`) |
| `type` | `varchar(20)` | NO | — | 6 tipus (§3) |
| `statement` | `text` | NO | — | |
| `created_at` | `timestamptz` | NO | `now()` | |
| `refuge_id` | `uuid` | SÍ | — | FK → `refuges.refuges` **`SET NULL`** (l'avís s'ha de poder consultar encara que el refugi desaparegui) |
| `media_key` | `varchar(500)` | SÍ | — | sense FK |
| `reason` | `varchar(32)` | SÍ | — | motius de §3 |
| `action` | `varchar(20)` | SÍ | — | `dismiss`/`remove`/`remove_and_strike`/`auto_hide`/`upload_blocked` |
| `report_id` | `uuid` | SÍ | — | FK → `moderation.media_reports` `SET NULL` |
| `automated` | `boolean` | NO | `false` | |
| `strikes` | `smallint` | SÍ | — | `>= 0` |

`redress` de l'API és un text constant (no es desa). Índexs: `(user_uid, created_at DESC, id DESC)` (`list_by_uid`, FK); `(report_id) WHERE report_id IS NOT NULL` i `(refuge_id) WHERE refuge_id IS NOT NULL` (FK).
RLS:
```sql
ALTER TABLE moderation.moderation_notices ENABLE ROW LEVEL SECURITY;
CREATE POLICY notices_select ON moderation.moderation_notices FOR SELECT TO app USING (user_uid = {U} OR {ADM} OR {SYS});
CREATE POLICY notices_insert ON moderation.moderation_notices FOR INSERT TO app WITH CHECK ({ADM} OR {SYS});
CREATE POLICY notices_delete ON moderation.moderation_notices FOR DELETE TO app USING ({SYS});    -- purga de retenció
```
Grants: `SELECT, INSERT, DELETE`.

### 2.22 `moderation.moderation_hash_blocklist` (app `moderation`; **RLS sí, sense cap política per a `app`**)

Llista de hashes prohibits (CSAM). Substitueix la col·lecció carregada sencera a memòria (I5).

| Columna | Tipus | Null | Default | Notes |
|---|---|---|---|---|
| `id` | `bigint identity` | NO | — | PK |
| `sha256` | `char(64)` | SÍ | — | `CHECK (sha256 ~ '^[0-9a-f]{64}$')`; `UNIQUE` parcial `WHERE sha256 IS NOT NULL` |
| `phash` | `bigint` | SÍ | — | pHash de 64 bits (ImageHash) desat com a enter amb signe (`n - 2^64` si `n >= 2^63`) |
| `category` | `varchar(16)` | NO | `'csam'` | `CHECK (category IN ('csam','other'))` |
| `source` | `varchar(100)` | NO | — | |
| `added_at` | `timestamptz` | NO | `now()` | |

`CHECK (sha256 IS NOT NULL OR phash IS NOT NULL)`. La coincidència aproximada és a la BD: `bit_count((phash # :q)::bit(64)) <= 6` (`PHASH_MAX_DISTANCE`). Cost: *seq scan* amb distància de Hamming; correcte fins a desenes de milers d'entrades; per a milions caldria *multi-index hashing* (8 blocs de 8 bits; amb distància ≤ 6 el principi del colomar garanteix un bloc idèntic) o un servei extern **[INFERÈNCIA]**.

**La taula és il·legible per a `app`** (ni `SELECT`): només hi ha una funció `SECURITY DEFINER` que respon sí/no, de manera que ni una fuita de credencials de l'aplicació ni una injecció SQL poden bolcar la llista:
```sql
ALTER TABLE moderation.moderation_hash_blocklist ENABLE ROW LEVEL SECURITY;   -- sense polítiques = denegat per a app
CREATE FUNCTION moderation.fn_hash_match(p_sha256 text, p_phash bigint, p_max_distance integer DEFAULT 6)
  RETURNS TABLE (entry_id bigint, category text, match_type text)
  LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, moderation AS $$
    SELECT id, category, 'sha256'::text FROM moderation.moderation_hash_blocklist WHERE sha256 = p_sha256
    UNION ALL
    SELECT id, category, 'phash'::text  FROM moderation.moderation_hash_blocklist
     WHERE p_phash IS NOT NULL AND phash IS NOT NULL AND bit_count((phash # p_phash)::bit(64)) <= p_max_distance
    LIMIT 1 $$;
REVOKE ALL ON FUNCTION moderation.fn_hash_match(text, bigint, integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION moderation.fn_hash_match(text, bigint, integer) TO app;
```
Grants a taula: **cap**. L'alta d'entrades es fa amb una comanda d'administració per l'alias `neon_migrator` (propietari).
Índexs: `UNIQUE (sha256) WHERE sha256 IS NOT NULL` (consulta exacta).

### 2.23 `moderation.media_deletion_queue` (app `moderation`; **RLS sí**; taula afegida pel disseny, dubte 19)

Cua *outbox* d'objectes d'R2 pendents d'esborrar. **Només la poblen triggers** (`SECURITY DEFINER`, propietari `migrator`) a `refuge_media` (§2.8) i `user_public_profiles` (§2.2); un worker/job la buida amb `system_context()`. Fa que l'esborrat d'usuari/experiència/refugi sigui **transaccional a la BD i reintentable a R2** (arquitectura §4.2) sense orfes.

| Columna | Tipus | Null | Default | Notes |
|---|---|---|---|---|
| `id` | `bigint identity` | NO | — | PK |
| `r2_key` | `text` | NO | — | `UNIQUE` (idempotent: `ON CONFLICT DO NOTHING`) |
| `source` | `varchar(32)` | NO | — | `TG_TABLE_NAME` d'origen (`refuge_media`, `user_public_profiles`) |
| `enqueued_at` | `timestamptz` | NO | `now()` | |
| `attempts` | `smallint` | NO | `0` | |
| `next_attempt_at` | `timestamptz` | NO | `now()` | *backoff* |
| `last_error` | `text` | SÍ | — | sense dades personals |

Procés: `SELECT … FROM moderation.media_deletion_queue WHERE next_attempt_at <= now() ORDER BY id LIMIT 50 FOR UPDATE SKIP LOCKED` → `R2MediaService.delete_file` (esborrar una clau inexistent és èxit) → `DELETE` de la fila, o `attempts+1` i *backoff*; a partir de 20 intents es deixa per a revisió humana.
Índexs: `(next_attempt_at, id)`; `UNIQUE (r2_key)`.
RLS i grants (l'aplicació no insereix: només els triggers):
```sql
ALTER TABLE moderation.media_deletion_queue ENABLE ROW LEVEL SECURITY;
CREATE POLICY mdq_select ON moderation.media_deletion_queue FOR SELECT TO app USING ({SYS});
CREATE POLICY mdq_update ON moderation.media_deletion_queue FOR UPDATE TO app USING ({SYS}) WITH CHECK ({SYS});
CREATE POLICY mdq_delete ON moderation.media_deletion_queue FOR DELETE TO app USING ({SYS});
```
Grants: `SELECT, UPDATE, DELETE` (cap `INSERT`).

### 2.24 `audit.audit_logs` (app `audit`; **RLS sí**)

Registre d'accés i accions (art. 32 RGPD / DSA). Només s'hi escriu (cap endpoint el llegeix avui).

| Columna | Tipus | Null | Default | Notes |
|---|---|---|---|---|
| `id` | `bigint identity` | NO | — | PK |
| `actor_uid` | `varchar(128)` | SÍ | — | FK → `users.users` **`CASCADE`** (decisió del PLAN). `NULL` = sistema (abans `'system'`) |
| `subject_uid` | `varchar(128)` | SÍ | — | FK → `users.users` **`CASCADE`**: usuari **sobre el qual** es fa l'acció (p. ex. `moderation.user_blocked`, `user.age_confirmed`); permet esborrar-lo declarativament sense deixar UIDs a `target_id`/`metadata` |
| `action` | `varchar(48)` | NO | — | `CHECK (action ~ '^[a-z_]+\.[a-z_]+$')` (format, no llista: afegir una acció no ha de requerir migració) |
| `target_type` | `varchar(32)` | SÍ | — | |
| `target_id` | `varchar(500)` | SÍ | — | |
| `metadata` | `jsonb` | NO | `'{}'` | `CHECK (jsonb_typeof(metadata) = 'object' AND pg_column_size(metadata) < 16384)`; **sense dades personals** (ni `uid`, ni bytes, ni URLs, ni dates de naixement) |
| `created_at` | `timestamptz` | NO | `now()` | (Firestore: `timestamp`) |
| `expire_at` | `timestamptz` | NO | `now() + interval '365 days'` | `CHECK (expire_at > created_at)`; substitueix el TTL de Firestore |

Índexs: `(expire_at)` (purga diària `DELETE … WHERE expire_at < now()` en lots, `system_context()`); `(actor_uid, created_at DESC)` (FK; consulta forense per actor); `(subject_uid) WHERE subject_uid IS NOT NULL` (FK). No hi ha índex per `target_*`: cap consulta de l'aplicació el necessita (si l'admin ho vol cercar, `BRIN (created_at)` o un índex en aquell moment).
RLS (`SELECT` propi perquè `INSERT … RETURNING` de Django també exigeix passar la política de lectura; evitable amb `bulk_create` sense `RETURNING`):
```sql
ALTER TABLE audit.audit_logs ENABLE ROW LEVEL SECURITY;
CREATE POLICY audit_select ON audit.audit_logs FOR SELECT TO app USING (actor_uid = {U} OR {ADM} OR {SYS});
CREATE POLICY audit_insert ON audit.audit_logs FOR INSERT TO app WITH CHECK (actor_uid = {U} OR {SYS});   -- no es pot falsificar un actor ni escriure com a «sistema» sense {SYS}
CREATE POLICY audit_delete ON audit.audit_logs FOR DELETE TO app USING ({SYS});                           -- purga
```
Grants: `SELECT, INSERT, DELETE` (**cap `UPDATE`**: registre immutable).
`AuditLogService.log` «mai ha de trencar el flux»: sota una transacció per petició, una excepció SQL **avorta la transacció**; l'`INSERT` s'ha d'embolicar en un `transaction.atomic()` niuat (*savepoint*) que s'empassa l'error.

---

## 3. Enumeracions

Tots els enums són **`varchar` + `CHECK ... IN (...)`** amb el seu `models.TextChoices` (un `ENUM` natiu de Postgres obliga a `ALTER TYPE … ADD VALUE` i no es pot treure un valor; el `CHECK` es canvia amb una migració normal). Els valors són els del codi **[FET]**.

| Enum (`TextChoices`) | Columna(es) | Valors | Origen |
|---|---|---|---|
| `Language` | `users.language` | `ca`, `es`, `en`, `fr` | `UserValidatorMixin.VALID_LANGUAGES` |
| `RefugeType` | `refuges.type`, `payload.type` | `non gardé`, `fermée`, `cabane ouverte mais ocupee par le berger l ete`, `orri`, `emergence`, `key_needed` | `VALID_TYPES` / `ALLOWED_REFUGE_TYPES` (el JSON només porta els 4 primers). Equivalència amb l'UML: `non gardé` = *No guardat*, `fermée` = *Tancat*, `cabane ouverte…` = *Ocupat als estius per pastor*, `orri` = *Orri*, `emergence` = *Emergència*; `key_needed` (refugi amb clau) **no és a l'UML** |
| (smallint) `condition value` | `refuge_condition_votes.value` | `0` pobre, `1` correcte, `2` bé, `3` excel·lent | `ConditionService.validate_condition_value` |
| `MediaStatus` | `refuge_media.status` | `visible`, `hidden_pending_review`, `removed` | `media_metadata.MEDIA_STATUSES` |
| `MediaType` | `refuge_media.media_type` | `image`, `video` | `MEDIA_TYPE_*` |
| `ProposalAction` | `refuge_proposals.action` | `create`, `update`, `delete` | `RefugeProposalCreateSerializer` |
| `ProposalStatus` | `refuge_proposals.status` | `pending`, `approved`, `rejected` | `RefugeProposalController.list_proposals` |
| `UploadTarget` | `upload_intents.target` | `refuge`, `experience`, `avatar` | `UPLOAD_TARGETS` |
| `UploadStatus` | `upload_intents.status` | `pending`, `confirmed`, `failed` | `INTENT_STATUSES` |
| `UploadFailureReason` | `upload_intents.failure_reason` | `missing_object`, `too_large`, `invalid_type`, `processing_error`, `moderation_blocked` | `FAILURE_REASONS` |
| `ReportReason` | `media_reports.reason`, `moderation_notices.reason` | `child_sexual_abuse`, `child_endangerment`, `sexual_nonconsensual`, `violence_gore`, `terrorism_extremism`, `hate_speech`, `harassment_bullying`, `animal_cruelty`, `self_harm`, `illegal_goods`, `my_image`, `privacy_personal_data`, `intellectual_property`, `fraud_scam_spam`, `misleading_irrelevant`, `other` | `REPORT_REASONS` (alta prioritat/auto-ocultació: `child_sexual_abuse`, `child_endangerment`, `sexual_nonconsensual`, `terrorism_extremism`, `my_image`) |
| `ReportStatus` | `media_reports.status` | `pending`, `resolved` | `REPORT_STATUSES` |
| `ReportPriority` | `media_reports.priority` | `high`, `normal` | |
| `ReportAction` | `media_reports.action` | `dismiss`, `remove`, `remove_and_strike` | `REPORT_ACTIONS` |
| `ReportSource` | `media_reports.source` | `user`, `automatic` | |
| `NoticeType` | `moderation_notices.type` | `content_hidden`, `content_restored`, `content_removed`, `strike`, `account_blocked`, `upload_blocked` | `NOTICE_TYPES` |
| `NoticeAction` | `moderation_notices.action` | `dismiss`, `remove`, `remove_and_strike`, `auto_hide`, `upload_blocked` | valors usats al codi |
| `BlockedReason` | `users.blocked_reason` | `csam_confirmed`, `strikes`, `moderation_hash_match` | `MediaReportController`, `MediaUploadController` |
| `HashCategory` | `moderation_hash_blocklist.category` | `csam`, `other` | `ModerationService` (docstring) |
| `AuditAction` (no es força) | `audit_logs.action` | `media.upload_intent`, `media.upload_confirm`, `media.delete`, `media.list`, `media.report`, `moderation.resolve`, `moderation.auto_hide`, `moderation.hash_block`, `moderation.user_blocked`, `moderation.reports_list`, `avatar.upload`, `user.age_confirmed` | `audit_log_service.py`; la BD només comprova el format `^[a-z_]+\.[a-z_]+$` |

---

## 4. Valors derivats i vistes

Cap d'aquests valors es desa. Cada fila indica **com es calcula** i **quin índex el sosté**. En tots els casos és una agregació sobre files d'un sol usuari/refugi/visita, de manera que cost = O(files d'aquell propietari).

| Valor (camp API) | Càlcul SQL | Índex de suport |
|---|---|---|
| `condition` (refugi; enter 0–3 o `null`) | vista `refuges.refuge_condition` (a baix) | `refuge_condition_votes (refuge_id) INCLUDE (value)` |
| `num_shared_experiences` (usuari) | `SELECT count(*) FROM activity.experiences WHERE creator_uid = :uid` | `experiences (creator_uid, modified_at DESC)` |
| `num_renovated_refuges` (usuari) | `(SELECT count(*) FROM activity.renovations WHERE creator_uid = :uid) + (SELECT count(*) FROM activity.renovation_participants WHERE user_uid = :uid)` — **compta reformes (creades + unides), com el comptador actual** (`increment` en crear i en unir-se; dubte 14) | `renovations (creator_uid, fin_date)`, `renovation_participants (user_uid, renovation_id)` |
| `uploaded_photos_keys` (usuari, només el propi) | `SELECT array_agg(key ORDER BY uploaded_at, key) FROM refuges.refuge_media WHERE creator_uid = :uid` (**tots els estats**, com l'array actual) | `refuge_media (creator_uid, uploaded_at)` |
| `favourite_refuges` / `visited_refuges` (usuari, només el propi) | `array_agg(refuge_id ORDER BY created_at, id)` | `UNIQUE (user_uid, refuge_id)` + `(user_uid, created_at DESC, id DESC)` |
| `visitors` (refugi; només admins, dubte 5) | `array_agg(user_uid) FROM users.user_visited_refuges WHERE refuge_id = :id` | `user_visited_refuges (refuge_id, user_uid)` |
| `answers_count` (dubte) | `count(*)` d'`answers` del dubte | `answers (doubt_id, created_at, id)` |
| `total_visitors` (visita) | vista `activity.refuge_visit_totals` (a baix) | `UNIQUE (visit_id, user_uid) INCLUDE (num_visitors)` |
| `is_visitor`, `num_visitors` (visita, de l'usuari actual) | `EXISTS`/`SELECT num_visitors` a `refuge_visit_participants` amb `user_uid = :me` (la RLS ja filtra) | `UNIQUE (visit_id, user_uid)` |
| `geohash` (llista de coordenades) | `ST_GeoHash(coord::geometry, 5)` (mateixa base32 i precisió 5 que `generate_simple_geohash`) **[INFERÈNCIA: comprovar amb els 1.542 punts]** | — |
| `age_confirmed` (usuari) | `age_confirmed_at IS NOT NULL` | — |
| `images_metadata` (refugi/experiència/preferits) | `refuge_media` filtrat per estat visible (o autor/admin) + URLs prefirmades generades a l'aplicació | `refuge_media (refuge_id, uploaded_at, key)`, `(experience_id)` |

### 4.1 Vistes

Les vistes s'executen amb els privilegis del **propietari** (`migrator`, no subjecte a la RLS; sense `security_invoker`). Això és **intencionat**: exposen només agregats o dades ja públiques. Qualsevol vista nova s'ha de revisar amb aquest criteri. Cada una es mapeja a Django com un model **`managed = False`** amb `db_table = 'schema"."vista'` i `OneToOneField(primary_key=True)` cap a l'entitat.

```sql
-- Condició d'un refugi: mitjana de vots amb arrodoniment half-to-even (== round() de Python que fa l'API avui)
CREATE VIEW refuges.refuge_condition AS
SELECT v.refuge_id,
       count(*)::integer                    AS votes_count,
       avg(v.value)                         AS avg_value,    -- numeric exacte
       core.round_half_even(avg(v.value))   AS condition     -- 0..3
  FROM refuges.refuge_condition_votes v
 GROUP BY v.refuge_id;
GRANT SELECT ON refuges.refuge_condition TO app;
-- Refugis sense cap vot: no surten a la vista (LEFT JOIN => condition NULL, com ara; no coincideixen amb cap filtre).

-- Substitueix coords_refugis/all_refugis_coords (cap document d'1 MiB, cap escriptura de sincronització)
CREATE VIEW refuges.refuge_map AS
SELECT r.id, r.name, r.surname,
       ST_Y(r.coord::geometry) AS lat, ST_X(r.coord::geometry) AS lng,
       ST_GeoHash(r.coord::geometry, 5) AS geohash, r.coord
  FROM refuges.refuges r;
GRANT SELECT ON refuges.refuge_map TO app;

-- Totals de visitants sense exposar qui hi va (els participants són privats per RLS)
CREATE VIEW activity.refuge_visit_totals AS
SELECT p.visit_id,
       sum(p.num_visitors)::integer AS total_visitors,
       count(*)::integer            AS participants_count
  FROM activity.refuge_visit_participants p
 GROUP BY p.visit_id;
GRANT SELECT ON activity.refuge_visit_totals TO app;
```

**Semàntica de `condition` conservada** (deep-dive `condition-average.md`): la mitjana d'**totes** les aportacions; cada proposta aprovada amb `condition` afegeix un vot; el client veu `round(avg)`; els refugis sense vots tenen `condition = null`; el filtre de cerca és `core.round_half_even(avg) IN (:valors)` (**corregeix M5**: ja no compara contra el *float* desat). *Seeding*: la comanda `assign_conditions` posava a cada refugi amb `info_comp` una condició inicial (`determine_condition`) amb `num_contributed_conditions = 1`; ara és **un vot llavor** per refugi amb `source_proposal_id = NULL` i `user_uid = NULL` (§9), de manera que la mitjana incremental d'abans i `AVG` donen el mateix resultat. Distribució llavor del JSON actual: 0 → 872, 1 → 428, 2 → 213, 3 → 29 **[FET, calculada]**.

**Escalabilitat.** A ~1,5 mil refugis i uns quants vots per refugi, `AVG` per agrupació és trivial (índex *covering*). Si el volum de vots creixés (>1 M) es pot convertir `refuge_condition` en `MATERIALIZED VIEW` amb `REFRESH … CONCURRENTLY` en aprovar propostes; **no ara** (evita files calentes i la invalidació que va causar C2/M5/M6).

---

## 5. Mapatge Firestore → SQL, contracte de l'API i receptes

### 5.1 Camp a camp

**`users/{uid}`** → `users.users` + `users.user_public_profiles` (+ taules d'unió)
| Firestore | SQL | Nota |
|---|---|---|
| id del document = `uid` | `users.users.uid` (PK) | |
| `username` | `user_public_profiles.username` | `''` permès |
| `language` | `users.language` | |
| `created_at` (ISO) | `users.created_at` | |
| `media_metadata` `{key, uploaded_at, width, height, blurhash, size, content_type, thumb_key}` (avatar) | `user_public_profiles.avatar_key`, `avatar_uploaded_at`, `avatar_width`, `avatar_height`, `avatar_blurhash`, `avatar_size_bytes`, `avatar_content_type`, `avatar_thumb_key` | tot o res |
| `favourite_refuges[]` | `user_favourite_refuges` (una fila per refugi) | |
| `visited_refuges[]` | `user_visited_refuges` | també cobreix `data_refugis_lliures.visitors[]` |
| `uploaded_photos_keys[]` | **derivat** de `refuge_media` (`creator_uid`) | |
| `num_shared_experiences`, `num_renovated_refuges` | **derivats** (§4) | |
| `age_confirmed_at`, `age_threshold` | `users.age_confirmed_at`, `users.age_threshold` | |
| `moderation_strikes`, `is_blocked`, `blocked_reason`, `blocked_at` | mateix nom a `users.users` | |
| *(`email`, `birth_date`)* | **mai es desen** | la data de naixement només serveix per validar l'edat |

**`data_refugis_lliures/{id}`** → `refuges.*`
| Firestore | SQL | Nota |
|---|---|---|
| `id` (auto-ID) | `refuges.id` (`uuid`) | UUIDv5 al *loader*, UUIDv4 a proposals |
| `name`, `surname`, `type`, `altitude`, `places`, `remarque`, `description`, `region`, `departement` | columnes homònimes de `refuges.refuges` | `region`/`departement`/`surname` blancs → `NULL`; `remarque`/`description` `NULL` → `''` |
| `coord {lat, long}` | `refuges.coord` `geography(Point,4326)` | `Point(long, lat)` |
| `modified_at` (string `YYYY-MM-DD`) | `refuges.modified_at` (`date`) | |
| `info_comp {12 claus 0/1}` | `refuge_amenities` (12 `boolean`) | `0/1` → `false/true`; clau absent → `false` |
| `info_couchage`, `info_eau` | — | **s'ignoren** |
| `links[]` | `refuge_links` (`position`, `url`) | |
| `condition` (float), `num_contributed_conditions` | `refuge_condition_votes` (un vot per aportació) | derivat per `refuge_condition` |
| `visitors[]` | `user_visited_refuges` | |
| `media_metadata{<key>: {creator_uid, uploaded_at, taken_at, experience_id, media_type, content_type, width, height, size, thumb_key, blurhash, status, rights_confirmed_at}}` | `refuge_media` (`key` = clau del map; la resta de camps, columnes) | `size` → `size_bytes` |
| `images_metadata` (només sortida) | derivat de `refuge_media` + URL prefirmada | |

**`coords_refugis/all_refugis_coords`** → vista `refuges.refuge_map` (cap taula, cap sincronització; desapareixen `add/update/delete_refuge_from/to_coords_refugis`, A3 per a aquesta col·lecció i el límit d'1 MiB).

**`refuge_visits/{id}`** → `activity.refuge_visits` + `refuge_visit_participants`
| Firestore | SQL |
|---|---|
| `id` | `refuge_visits.id` |
| `date` (`YYYY-MM-DD`) | `refuge_visits.visit_date` (`date`) |
| `refuge_id` | `refuge_visits.refuge_id` |
| `visitors[{uid, num_visitors}]` | `refuge_visit_participants (user_uid, num_visitors)` |
| `total_visitors` | **derivat** (`refuge_visit_totals`) |

**`renovations/{id}`** → `activity.renovations` + `renovation_participants` + `renovation_expelled`
| Firestore | SQL | Nota |
|---|---|---|
| `id`, `refuge_id`, `description`, `materials_needed` | homònims | |
| `creator_uid` (`'unknown'` si anonimitzat) | `creator_uid` (`NULL` si anonimitzat) | l'API torna a emetre `'unknown'` |
| `ini_date`, `fin_date` (ISO, a l'API només data) | `date` | |
| `group_link` (`None` si anonimitzat) | `group_link` | el *trigger* el posa a `NULL` |
| `participants_uids[]`, `expelled_uids[]` | taules d'unió | |

**`experiences/{id}`** → `activity.experiences`
| Firestore | SQL |
|---|---|
| `id`, `refuge_id`, `creator_uid`, `comment` | homònims |
| `modified_at` (ISO) | `modified_at` (`timestamptz`) (+ `created_at` nou) |
| `media_keys[]` | `refuge_media.experience_id = experiences.id` |
| `images_metadata` (només sortida) | derivat |

**`doubts/{id}` i `doubts/{id}/answers/{id}`** → `activity.doubts`, `activity.answers`
| Firestore | SQL |
|---|---|
| `doubts.id/refuge_id/creator_uid/message/created_at` | homònims |
| `doubts.answers_count` | **derivat** |
| `answers.id/creator_uid/message/created_at/parent_answer_id` | homònims; `doubt_id` = id del document pare |

**`refuges_proposals/{id}`** → `proposals.refuge_proposals`
| Firestore | SQL | Nota |
|---|---|---|
| `id`, `action`, `status`, `comment`, `rejection_reason` | homònims | |
| `refuge_id` | `refuge_id` | `SET NULL` en esborrar el refugi |
| `payload`, `refuge_snapshot` (maps) | `payload`, `refuge_snapshot` (`jsonb`) | |
| `creator_uid` (`'unknown'`), `reviewer_uid` | `NULL` si anonimitzat/automàtic | |
| `created_at`, `reviewed_at` (ISO) | `timestamptz` | |

**`media_reports/{sha}`** → `moderation.media_reports`: `id` (SHA-256 truncat) → `uuid` nou; `refuge_id` (a vegades el `target` com a pseudo-refugi) → `refuge_id` o `NULL`; `media_key`, `reason`, `details`, `status`, `priority`, `created_at`, `resolved_at`, `action`, `statement`, `source` → homònims; `reporter_uid` (`'system'`) → `NULL` amb `source='automatic'`; `media_creator_uid`, `resolved_by` → FK `SET NULL`.
**`moderation_notices/{id}`** → `moderation.moderation_notices`: `uid` → `user_uid`; la resta homònima; `report_id` → FK a `media_reports.id`; `redress` constant (no es desa).
**`upload_intents/{id}`** → `moderation.upload_intents`: `uid` → `user_uid`; la resta homònima; `expire_at` (Timestamp amb TTL de Firestore) → columna + job de purga.
**`moderation_hash_blocklist/{id}`** → `moderation.moderation_hash_blocklist`: `sha256`, `phash` (hex → `bigint`), `category`, `source`, `added_at`.
**`audit_logs/{id}`** → `audit.audit_logs`: `actor_uid` (`'system'`) → `NULL`; `action`, `target_type`, `target_id`, `metadata` → homònims; `timestamp` → `created_at`; `expire_at` (Timestamp) → `expire_at`; **nou** `subject_uid`.

### 5.2 Reconstrucció del contracte JSON (el frontend no ha de canviar)

| Resposta | Com es reconstrueix | Diferències respecte a avui |
|---|---|---|
| **Refugi** (detall/cerca) `{id, name, coord:{lat,long}, altitude, places, remarque, info_comp, description, links, type, modified_at, region, departement, condition, visitors, images_metadata}` | `coord` ← `refuge.coord.y/x`; **`info_comp` ← les 12 columnes de `refuge_amenities` com a enters `0/1`** (`int(bool)`: el DTO del frontend és `number`); `links` ← `refuge_links` ordenats per `position`; `condition` ← `refuge_condition.condition` (enter ja arrodonit half-to-even; `null` sense vots); `modified_at` ← `date.isoformat()`; `visitors` (només admins) ← `user_visited_refuges`; `images_metadata` (només autenticats) ← `refuge_media` visibles (+ propis/admin) amb URL prefirmada | Nou camp **`surname`** (additiu; el DTO ja el té). `visitors`: vegeu dubte 5. `remarque`/`description` mai `null` |
| **Llista sense filtres** `{count, has_filters:false, results:[{id, name, coord, geohash, surname?}]}` | vista `refuge_map` | `surname` només si no és `NULL` |
| **Llista amb filtres** `{count, has_filters:true, results:[Refugi]}` | consulta única de §5.3 | `type` i el filtre `condition` acceptarien `0–3` (dubte 3); la cerca per nom és parcial i sense accents (B2) |
| **Usuari** `{uid, username, avatar_metadata, language, favourite_refuges[], visited_refuges[], uploaded_photos_keys[], num_shared_experiences, num_renovated_refuges, created_at, age_confirmed}` | `users` + `user_public_profiles` (avatar → `MediaItem` amb URL prefirmada) + subconsultes de §4. NOTA: el serializer declara `num_uploaded_photos` però `to_representation` torna `uploaded_photos_keys` **[FET]** | Per a **altres usuaris**: només camps públics (dubte 4) |
| **Refugis d'una llista d'usuari** `{count, results:[{id, name, region, places, coord, images_metadata:[1a foto visible]\|null}]}` | `user_favourite_refuges`/`user_visited_refuges` JOIN `refuges` + 1a imatge visible per `LATERAL`/`Prefetch` | `places` `null` si no hi ha dada (avui el mapper posava `0`) |
| **Visita** `{date, refuge_id?, total_visitors, is_visitor, num_visitors}` | `refuge_visits` + `refuge_visit_totals` + fila de l'usuari | idèntic |
| **Reforma** `{id, creator_uid, refuge_id, ini_date, fin_date, description, materials_needed, group_link, participants_uids[], expelled_uids[]}` | `renovations` + `ArraySubquery` de les dues taules; `creator_uid` `NULL` → `'unknown'` | idèntic |
| **Experiència** `{id, refuge_id, creator_uid, modified_at, comment, images_metadata[]}` | `experiences` + `refuge_media` per `experience_id` visibles per a l'espectador | idèntic |
| **Dubte** `{id, refuge_id, creator_uid, message, created_at, answers_count, answers[{id, creator_uid, message, created_at, parent_answer_id}]}` | `doubts` + `Count('answers')` + `Prefetch('answers')` ordenat `created_at, id`; l'arbre el munta el client amb `parent_answer_id` com ara | idèntic |
| **Proposta** `{id, refuge_id, refuge_snapshot, action, payload, comment, status, creator_uid, created_at, reviewer_uid, reviewed_at, rejection_reason}` | columnes directes; `creator_uid` `NULL` → `'unknown'` | `created_at`/`reviewed_at` amb offset `Europe/Madrid` |
| **MediaItem** `{key, url, thumb_url, media_type, width, height, blurhash, creator_uid, uploaded_at, taken_at, experience_id}` | `refuge_media` + `R2MediaService.generate_presigned_url(key)`; `thumb_url = presign(thumb_key) or url` | idèntic |
| **Denúncia / avís** | columnes homònimes; `uid` ← `user_uid`; `reporter_uid` `NULL` → `'system'`; `media` de la llista d'admin ← `LEFT JOIN refuge_media` | l'`id` de denúncia passa a UUID |

Camps de text `region`/`departement` que avui poden ser `''` (38 refugis) passaran a `null` (dubte 15).

### 5.3 Receptes de consulta (esbós ORM; objectiu: cap N+1)

Convencions: `RefugeCondition`, `RefugeMapPoint` i `VisitTotal` són els models `managed=False` de les vistes; `RefugeCondition.refuge = OneToOneField(Refuge, primary_key=True, db_column='refuge_id', related_name='condition_agg', on_delete=DO_NOTHING)` (idem `VisitTotal.visit` → `totals`). **La RLS filtra les files abans d'agregar**: mai usar `Sum/Count` sobre taules privades (`participants`, `votes`) per obtenir un total global; es fa servir la vista.

**1. Detall de refugi (2 consultes; 3 per a admin)**
```python
links = ArraySubquery(RefugeLink.objects.filter(refuge=OuterRef('pk')).order_by('position').values('url'))
refuge = (Refuge.objects.select_related('amenities', 'condition_agg')   # LEFT JOIN a refuge_amenities i refuge_condition
          .annotate(links_list=links).get(pk=refuge_id))                # Q1 (404 si no existeix)
media = list(RefugeMedia.objects.filter(refuge_id=refuge_id).order_by('uploaded_at', 'key'))   # Q2, només autenticats
# filtre explícit a més de la RLS: Q(status='visible') | Q(creator_id=uid) (tots si admin)
visitors = list(VisitedRefuge.objects.filter(refuge_id=refuge_id).values_list('user_id', flat=True))  # Q3, només admin
```

**2. Perfil d'usuari amb comptadors (1 consulta)**
```python
def sub_count(model, **flt):   # subconsulta escalar sense GROUP BY exterior
    return Coalesce(Subquery(model.objects.filter(**flt).order_by().values(next(iter(flt)))
                             .annotate(c=Count('pk')).values('c')), 0)
user = (UserAccount.objects.select_related('public_profile').annotate(
          favourite_ids=ArraySubquery(FavouriteRefuge.objects.filter(user=OuterRef('pk')).order_by('created_at', 'id').values('refuge_id')),
          visited_ids=ArraySubquery(VisitedRefuge.objects.filter(user=OuterRef('pk')).order_by('created_at', 'id').values('refuge_id')),
          photo_keys=ArraySubquery(RefugeMedia.objects.filter(creator=OuterRef('pk')).order_by('uploaded_at', 'key').values('key')),
          n_experiences=sub_count(Experience, creator=OuterRef('pk')),
          n_renovations=sub_count(Renovation, creator=OuterRef('pk')) + sub_count(RenovationParticipant, user=OuterRef('pk')),
        ).get(pk=uid))
```
Per a un perfil **aliè**: `UserPublicProfile` + `n_experiences` + `n_renovations` (sense llistes privades).

**3. Dubtes d'un refugi amb respostes (2 consultes)**
```python
doubts = (Doubt.objects.filter(refuge_id=rid).annotate(answers_count=Count('answers'))
          .order_by('-created_at', '-id')
          .prefetch_related(Prefetch('answers', queryset=Answer.objects.order_by('created_at', 'id'))))  # Q1 + Q2
# keyset: .filter(Q(created_at__lt=t) | Q(created_at=t, id__lt=i))[:limit]
```

**4. Cerca amb filtres + similitud de nom (1 consulta + 1 `Prefetch` si autenticat)**
```python
def norm(e): return Func(e, function='core.norm_name', output_field=TextField())
qs = Refuge.objects.select_related('amenities', 'condition_agg')
if name:
    n = norm(Value(name))
    qs = (qs.annotate(name_n=norm(F('name')), sim=TrigramSimilarity(norm(F('name')), n))
            .filter(Q(name_n__trigram_similar=n) | Q(name_n__contains=n)).order_by('-sim', 'name', 'id'))
if types:      qs = qs.filter(type__in=types)
if places_min is not None: qs = qs.filter(places__gte=places_min)        # idem places_max, altitude_*
if conditions: qs = qs.filter(condition_agg__condition__in=conditions)   # IN exclou els NULL (sense vots)
if authenticated:
    qs = qs.prefetch_related(Prefetch('media', RefugeMedia.objects.order_by('uploaded_at', 'key'), to_attr='media_list'))
```
SQL equivalent de la part de nom (usa `refuges_name_trgm_gin`; `similarity_threshold` per defecte 0,3, es pot baixar amb `SET LOCAL pg_trgm.similarity_threshold = 0.25`):
`WHERE core.norm_name(name) % core.norm_name(:q) OR core.norm_name(name) LIKE '%' || core.norm_name(:q) || '%'`. Els `%…%` només usen el GIN per a patrons ≥ 3 caràcters. **El chunk 2 ha de verificar amb `EXPLAIN` que s'usa l'índex.**

**5. Llista de coordenades per al mapa (1 consulta, sense joins)**
```python
RefugeMapPoint.objects.order_by('name', 'id').values('id', 'name', 'surname', 'lat', 'lng', 'geohash')
# per vista de mapa: .filter(coord__intersects=Polygon.from_bbox((w, s, e, n)))  (usa refuges_coord_gist)
```

**6. Visites d'un refugi i de l'usuari (1 consulta cada una)**
```python
mine = VisitParticipant.objects.filter(visit=OuterRef('pk'), user_id=uid)
visits = (RefugeVisit.objects.filter(refuge_id=rid, visit_date__gte=get_madrid_today())
          .annotate(total=Coalesce(F('totals__total_visitors'), 0), is_visitor=Exists(mine),
                    my_num=Coalesce(Subquery(mine.values('num_visitors')[:1]), 0)).order_by('visit_date'))
my_visits = (VisitParticipant.objects.filter(user_id=uid).select_related('visit', 'visit__totals')
             .order_by('-visit__visit_date'))
```
Alta idempotent: `RefugeVisit.objects.bulk_create([RefugeVisit(refuge_id=rid, visit_date=d)], ignore_conflicts=True)` + `get(refuge_id=rid, visit_date=d)`; després `VisitParticipant.objects.create(...)` (el `UNIQUE` dóna «ja estàs registrat»).

**7. Reformes actives amb participants (1 consulta)**
```python
Renovation.objects.filter(fin_date__gte=today).order_by('ini_date').annotate(
    participants=ArraySubquery(RenovationParticipant.objects.filter(renovation=OuterRef('pk')).order_by('created_at').values('user_id')),
    expelled=ArraySubquery(RenovationExpelled.objects.filter(renovation=OuterRef('pk')).order_by('expelled_at').values('user_id')))
```

**8. Detecció de refugis propers/duplicats en crear una proposta**
```python
Refuge.objects.filter(Q(coord__dwithin=(Point(lng, lat, srid=4326), D(m=200))) | Q(name_n__trigram_similar=norm(Value(name))))
```
(`ST_DWithin` + `similarity`, arquitectura §5.1; avís, no bloqueig, dubte 16.)

**9. Procés diari d'ahir (set-based, `system_context()`)**
```sql
INSERT INTO users.user_visited_refuges (user_uid, refuge_id)
SELECT p.user_uid, v.refuge_id FROM activity.refuge_visits v
  JOIN activity.refuge_visit_participants p ON p.visit_id = v.id
 WHERE v.visit_date = :ahir
ON CONFLICT (user_uid, refuge_id) DO NOTHING;
DELETE FROM activity.refuge_visits v WHERE v.visit_date = :ahir
   AND NOT EXISTS (SELECT 1 FROM activity.refuge_visit_participants p WHERE p.visit_id = v.id);   -- visites buides
```
Dues sentències en lloc d'un bucle de crides per visita/usuari. (Les visites processades **no** s'esborren; vegeu dubte 13 sobre retenció.)

**Pressupost de consultes per endpoint** (per a `django_assert_num_queries`; **no compten** la sentència `set_config` de context, §7.3):
| Endpoint | Consultes |
|---|---|
| `GET /refuges/` sense filtres | 1 |
| `GET /refuges/` amb filtres | 1 (+1 mitjans si autenticat) |
| `GET /refuges/{id}/` | 1 (+1 mitjans autenticat, +1 visitors admin) |
| `GET /users/{uid}/` | 1 |
| `GET /users/{uid}/favorite-refuges/` (o visited) | 1 (+1 primera imatge per refugi amb `Prefetch` limitat) |
| `GET /refuges/{id}/visits/`, `GET /users/{uid}/visits/` | 1 |
| `GET /renovations/`, `GET /refuges/{id}/renovations/` | 1 |
| `GET /experiences/?refuge_id=` | 2 (experiències + mitjans amb `Prefetch`) |
| `GET /doubts/?refuge_id=` | 2 |
| `GET /admin/media-reports/` | 1 |
| `POST /refuges-proposals/{id}/approve/` | transacció única (bloqueig + escriptures) |

---

## 6. Apps Django i models

### 6.1 Una app per domini (cap conflicte de migracions entre chunks paral·lels)

Paquet nou **`domain/`** a l'arrel del repo (germà d'`api/` i `refugis_lliures/`), una app per domini amb `models.py`, `querysets.py` (substitueix el DAO), `migrations/`. Els controllers de `api/controllers/` hi criden; les vistes, serializers i permisos continuen a `api/`. Les classes `@dataclass` d'`api/models/` es mantenen fins al chunk 11 (no hi ha col·lisió: mòduls diferents).

| App (`INSTALLED_APPS`) | Models → taula | Schema | Chunk |
|---|---|---|---|
| `domain.core` | — (funcions, rols, grants, helpers de migració) | `core` | 1 |
| `domain.accounts` | `UserAccount` → `users.users`; `UserPublicProfile` → `users.user_public_profiles` (`0001`); `FavouriteRefuge`, `VisitedRefuge` (`0002`) | `users` | 2 / 3 |
| `domain.refuges` | `Refuge`, `RefugeAmenities`, `RefugeLink`, `RefugeMedia`, `RefugeConditionVote`; no gestionats `RefugeCondition`, `RefugeMapPoint` | `refuges` | 2 (+7, +8) |
| `domain.visits` | `RefugeVisit`, `VisitParticipant`; no gestionat `VisitTotal` | `activity` | 4 |
| `domain.renovations` | `Renovation`, `RenovationParticipant`, `RenovationExpelled` | `activity` | 5 |
| `domain.doubts` | `Doubt`, `Answer` | `activity` | 6 |
| `domain.experiences` | `Experience` | `activity` | 7 |
| `domain.uploads` | `UploadIntent` | `moderation` | 7 |
| `domain.proposals` | `RefugeProposal` | `proposals` | 8 |
| `domain.moderation` | `MediaReport`, `ModerationNotice`, `HashBlocklistEntry`, `MediaDeletionQueueItem` | `moderation` | 9 |
| `domain.audit` | `AuditLog` | `audit` | 9 |

També cal a `INSTALLED_APPS`: `django.contrib.gis` i `django.contrib.postgres` (`ExclusionConstraint`, `ArraySubquery`, `TrigramSimilarity`), i `DATABASES` amb el motor `django.contrib.gis.db.backends.postgis` (toggle `NEON_USE_POSTGIS_ENGINE` ja existent; Docker de proves amb GDAL/GEOS). Quin alias és `default` és decisió del chunk 1.

### 6.2 Ordre de migracions (graf aciclic; evita dependències circulars entre apps)

```
core.0001  (schemas, funcions, grants base, helpers)
  └─ accounts.0001  (users + user_public_profiles)            ← abans de refuges: refuge_media.creator_uid → users
       └─ refuges.0001  (refuges, amenities, links, media SENSE experience_id, votes SENSE source_proposal_id, vistes, RLS)
            ├─ accounts.0002   (favourites, visited)           ← chunk 3
            ├─ visits.0001 · renovations.0001 · doubts.0001    ← chunks 4/5/6 (paral·lels)
            └─ experiences.0001                                ← chunk 7
                 ├─ refuges.0002  (refuge_media.experience_id → experiences + trigger de la cua d'R2)
                 └─ uploads.0001  (upload_intents)
            proposals.0001                                      ← chunk 8
                 └─ refuges.0003  (refuge_condition_votes.source_proposal_id → proposals)
            moderation.0001 (media_reports, notices, blocklist, deletion queue) · audit.0001   ← chunk 9
```
`accounts.0001` s'ha de crear al **començament del chunk 2** (o al final del 1): és l'únic tros del chunk 3 que el 2 necessita. Els chunks 4, 5 i 6 no toquen cap migració d'una altra app. Els chunks 7 i 8 afegeixen una migració a `refuges` (seqüencials, sense paral·lelisme).

### 6.3 Els `ON DELETE` són del DDL, **no** de Django 5.1 (decisió crítica)

A Django 5.1 `on_delete=CASCADE/SET_NULL` s'**emula en Python** (el *collector* fa `DELETE`/`UPDATE` des de l'aplicació, amb el rol `app`, **subjecte a RLS i a molts viatges**) i la FK que crea Django **no té `ON DELETE`** (`DEFERRABLE INITIALLY DEFERRED` simple). Aquest disseny necessita les cascades **a la BD** (atòmiques, amb els privilegis del propietari, reintentables, vàlides també per a un `DELETE` de SQL pla). Per tant, **a tots els models**:

```python
creator = models.ForeignKey(UserAccount, on_delete=models.DO_NOTHING, db_constraint=False,
                            db_index=False, db_column='creator_uid', related_name='+')
```
i la restricció real es crea a la migració amb `RunSQL` (amb `reverse_sql`), p. ex.:
`ALTER TABLE activity.experiences ADD CONSTRAINT experiences_creator_uid_fk FOREIGN KEY (creator_uid) REFERENCES users.users (uid) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED;` (les **accions** referencials no són diferibles: `CASCADE`/`SET NULL` s'executen immediatament; només el control d'integritat es difereix al `COMMIT`). Els índexs de FK es declaren a `Meta.indexes` amb nom explícit (§2). Amb `DO_NOTHING`, `UserAccount.objects.filter(pk=uid).delete()` emet **un sol `DELETE`** i la BD fa la resta; no es fan `pre/post_delete` signals ni es depèn d'`Collector`. Django 6 afegeix `DB_CASCADE`/`DB_SET_NULL` **[NO VERIFICAT]**, però no és utilitzable aquí (Python 3.10 a CI, Django pinat a 5.1).

**Matriu completa de FK** (cada fila és una `RunSQL` `ADD CONSTRAINT`; nom `<taula>_<columna>_fk`; totes `DEFERRABLE INITIALLY DEFERRED`):

| Taula · columna | → Destí | `ON DELETE` |
|---|---|---|
| `user_public_profiles.uid` | `users.users.uid` | CASCADE |
| `user_favourite_refuges.user_uid` / `.refuge_id` | `users.users` / `refuges.refuges` | CASCADE / CASCADE |
| `user_visited_refuges.user_uid` / `.refuge_id` | `users.users` / `refuges.refuges` | CASCADE / CASCADE |
| `refuge_amenities.refuge_id`, `refuge_links.refuge_id` | `refuges.refuges` | CASCADE |
| `refuge_media.refuge_id` / `.creator_uid` / `.experience_id` | `refuges.refuges` / `users.users` / `activity.experiences` | CASCADE / CASCADE / CASCADE |
| `refuge_condition_votes.refuge_id` / `.source_proposal_id` / `.user_uid` | `refuges.refuges` / `proposals.refuge_proposals` / `users.users` | CASCADE / **SET NULL** / **SET NULL** |
| `refuge_visits.refuge_id` | `refuges.refuges` | CASCADE |
| `refuge_visit_participants.visit_id` / `.user_uid` | `activity.refuge_visits` / `users.users` | CASCADE / CASCADE |
| `renovations.refuge_id` / `.creator_uid` | `refuges.refuges` / `users.users` | CASCADE / **SET NULL** |
| `renovation_participants.renovation_id` / `.user_uid`; `renovation_expelled.…` | `activity.renovations` / `users.users` | CASCADE / CASCADE |
| `experiences.refuge_id` / `.creator_uid` | `refuges.refuges` / `users.users` | CASCADE / CASCADE |
| `doubts.refuge_id` / `.creator_uid` | `refuges.refuges` / `users.users` | CASCADE / CASCADE |
| `answers.doubt_id` / `.creator_uid` | `activity.doubts` / `users.users` | CASCADE / CASCADE |
| `answers (doubt_id, parent_answer_id)` | `activity.answers (doubt_id, id)` | CASCADE |
| `refuge_proposals.refuge_id` / `.creator_uid` / `.reviewer_uid` | `refuges.refuges` / `users.users` / `users.users` | **SET NULL** ×3 |
| `upload_intents.user_uid` / `.refuge_id` / `.experience_id` | `users.users` / `refuges.refuges` / `activity.experiences` | CASCADE ×3 |
| `media_reports.refuge_id` / `.reporter_uid` / `.media_creator_uid` / `.resolved_by` | `refuges.refuges` / `users.users` ×3 | CASCADE / CASCADE / **SET NULL** / **SET NULL** |
| `moderation_notices.user_uid` / `.refuge_id` / `.report_id` | `users.users` / `refuges.refuges` / `moderation.media_reports` | CASCADE / **SET NULL** / **SET NULL** |
| `audit_logs.actor_uid` / `.subject_uid` | `users.users` | CASCADE / CASCADE |

### 6.4 Tipus de camp i constraints a Django 5.1

| Necessitat | Django |
|---|---|
| `geography(Point,4326)` | `gis_models.PointField(geography=True, srid=4326, spatial_index=False)` + `GistIndex(fields=['coord'], name='refuges_coord_gist')` |
| `uuid` PK amb default de BD | `UUIDField(primary_key=True, default=uuid.uuid4, db_default=Func(function='gen_random_uuid'))` |
| `timestamptz` / `date` | `DateTimeField(db_default=Now())` (amb `USE_TZ=True`) / `DateField` |
| `boolean NOT NULL DEFAULT false` | `BooleanField(db_default=False)` |
| enum | `CharField(max_length=n, choices=XChoices.choices)` + `CheckConstraint(condition=Q(col__in=XChoices.values), name=...)` (**Django 5.1 usa `condition=`; `check=` és obsolet**) |
| jsonb | `JSONField` (CHECKs complexos per `RunSQL`, §2.18) |
| `UNIQUE` parcial / amb `INCLUDE` / `NULLS NOT DISTINCT` | `UniqueConstraint(fields=…, condition=Q(...), include=[...], nulls_distinct=False, name=...)` |
| `EXCLUDE USING gist` | `ExclusionConstraint` (+ `django.contrib.postgres`; la `btree_gist` la crea el propietari, §1.3, **no** `BtreeGistExtension()` perquè `migrator` no pot) |
| GIN trigram sobre expressió | `GinIndex(OpClass(Func(F('name'), function='core.norm_name', output_field=TextField()), name='gin_trgm_ops'), name='refuges_name_trgm_gin')` |
| Índex `INCLUDE` | `Index(fields=['refuge'], include=['value'], name=...)` |
| FK composta (`answers`) | no suportada: `RunSQL` (§2.17), camp amb `db_constraint=False` |
| Vistes | `managed = False`, `db_table = 'refuges"."refuge_condition'`, `on_delete=DO_NOTHING` |
| Funcions, triggers, polítiques, grants, vistes | `migrations.RunSQL(sql, reverse_sql)`; les polítiques passen per un helper de `domain.core` que **expandeix les macros** `{U}/{ADM}/{SYS}` |

Esbós de `Meta` (no és codi final; fixa noms i tipus):
```python
class Renovation(models.Model):
    class Meta:
        db_table = 'activity"."renovations'
        constraints = [
            models.CheckConstraint(condition=Q(ini_date__lt=F('fin_date')), name='renovations_dates_ck'),
            models.CheckConstraint(condition=Q(group_link__isnull=False) | Q(creator__isnull=True), name='renovations_anonymized_ck'),
            ExclusionConstraint(name='renovations_no_overlap',
                expressions=[('refuge', RangeOperators.EQUAL),
                             (Func(F('ini_date'), F('fin_date'), Value('[]'), function='daterange',
                                   output_field=DateRangeField()), RangeOperators.OVERLAPS)]),
        ]
        indexes = [models.Index(fields=['refuge', 'fin_date', 'ini_date'], name='renovations_refuge_fin_idx'), ...]

class MediaReport(models.Model):
    class Meta:
        db_table = 'moderation"."media_reports'
        constraints = [models.UniqueConstraint(fields=['refuge', 'media_key', 'reporter'], nulls_distinct=False,
                                               name='media_reports_unique_reporter_uq'), ...]
```

### 6.5 Convencions de migració i de transaccions

- Cada migració que crea una taula inclou, **a la mateixa migració**, les `FK` (§6.3), els `GRANT` (matriu §7.2), la RLS (`ENABLE ROW LEVEL SECURITY` + polítiques) i els triggers; amb `reverse_sql` per a tot.
- Un test d'arquitectura compara `information_schema.role_table_grants`, `pg_policies` i `pg_class.relrowsecurity` del rol `app` amb aquest document (falla si hi ha una taula sense RLS, un grant de més o de menys).
- Les migracions s'apliquen amb `neon_migrator` (endpoint directe); l'aplicació s'executa amb `neon` (rol `app`, pooler). Les proves d'integració **han de** córrer com a `app` (si no, el propietari ignora la RLS).
- `bulk_create(ignore_conflicts=True)` no retorna PK (no fa `RETURNING`): és el que es vol per a «ja existeix → ignora» sota RLS.
- `select_for_update(of=('self',))` només dins `transaction.atomic()` (a PgBouncer de transacció, sempre és així).

---

## 7. Rols, grants i mecanisme de RLS

### 7.1 Rols **[FET: ja creats a Neon, `integrations/neon.md`; aquí s'hi afegeixen els schemas nous]**

| Rol | Atributs | Pot | No pot |
|---|---|---|---|
| `refugisdb_owner` | propietari de la BD (membre de `neon_superuser`) | `CREATE EXTENSION`, *bootstrap* (§1.3) | s'usa només per administrar |
| `migrator` | `NOLOGIN`-no: `LOGIN`; sense `SUPERUSER`/`BYPASSRLS`; **propietari** de tots els objectes de domini | DDL, `ALTER TABLE … ENABLE RLS`, `CREATE POLICY/TRIGGER/FUNCTION/VIEW`, `GRANT` | `CREATE EXTENSION`; connectar pel pooler (només endpoint directe) |
| `app` | `LOGIN`, `NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS`, **no propietari de res** | DML segons la matriu §7.2; `EXECUTE` de les funcions de §2.0 i `fn_hash_match` | DDL, `TRUNCATE`, `REFERENCES`, `TRIGGER`, llegir `moderation_hash_blocklist`; saltar la RLS |

Com `app` no és propietari, **la RLS s'aplica sense `FORCE`**; i com `migrator` és propietari, les migracions, el *loader* i les accions referencials (cascades) **no** hi estan subjectes. Proves/CI que usin `migrator` **no** exerciten la RLS.

Grants comuns (a `core.0001`, executats pel `migrator`):
```sql
GRANT USAGE ON SCHEMA core, refuges, users, activity, proposals, moderation, audit TO app;
GRANT USAGE ON SCHEMA public TO app;                        -- ja concedit [FET]: PostGIS, pg_trgm, unaccent
ALTER DEFAULT PRIVILEGES FOR ROLE migrator IN SCHEMA refuges, users, activity, proposals, moderation, audit
  GRANT USAGE, SELECT ON SEQUENCES TO app;
ALTER DEFAULT PRIVILEGES FOR ROLE migrator REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;   -- les SECURITY DEFINER no han de ser cridables per PUBLIC
-- No hi ha ALTER DEFAULT PRIVILEGES per a TAULES als schemas nous: cada migració concedeix explícitament el que toca (matriu).
```
(Els `ALTER DEFAULT PRIVILEGES` de `public` ja existents no afecten els schemas nous.)

### 7.2 Matriu de grants per a `app` (mínim privilegi; coherent amb §2)

| Taula / objecte | `SELECT` | `INSERT` | `UPDATE` | `DELETE` | Nota |
|---|---|---|---|---|---|
| `users.users` | ✔ | ✔ | ✔ | ✔ | |
| `users.user_public_profiles` | ✔ | ✔ | ✔ | — | esborrat només per cascada |
| `users.user_favourite_refuges`, `users.user_visited_refuges` | ✔ | ✔ | — | ✔ | |
| `refuges.refuges`, `refuge_amenities`, `refuge_links` | ✔ | ✔ | ✔ | ✔ | escriure = només `{ADM}/{SYS}` per RLS |
| `refuges.refuge_media` | ✔ | ✔ | ✔ | ✔ | |
| `refuges.refuge_condition_votes` | ✔ | ✔ | — | — | |
| vistes `refuge_condition`, `refuge_map`, `refuge_visit_totals` | ✔ | — | — | — | |
| `activity.refuge_visits` | ✔ | ✔ | — | ✔ | |
| `activity.refuge_visit_participants` | ✔ | ✔ | ✔ | ✔ | |
| `activity.renovations`, `experiences` | ✔ | ✔ | ✔ | ✔ | |
| `activity.renovation_participants` | ✔ | ✔ | — | ✔ | |
| `activity.renovation_expelled` | ✔ | ✔ | — | — | |
| `activity.doubts`, `activity.answers` | ✔ | ✔ | — | ✔ | |
| `proposals.refuge_proposals` | ✔ | ✔ | ✔ | — | |
| `moderation.upload_intents`, `moderation.media_reports` | ✔ | ✔ | ✔ | ✔ | |
| `moderation.moderation_notices` | ✔ | ✔ | — | ✔ | |
| `moderation.moderation_hash_blocklist` | — | — | — | — | només `EXECUTE moderation.fn_hash_match(...)` |
| `moderation.media_deletion_queue` | ✔ | — | ✔ | ✔ | només `{SYS}`; l'omplen els triggers |
| `audit.audit_logs` | ✔ | ✔ | — | ✔ | **sense `UPDATE`**: registre immutable |
| funcions `core.*` | — | — | — | — | `EXECUTE` (§2.0) |

Seqüències d'`identity`: `USAGE, SELECT` per defecte (els `INSERT` d'una columna *identity* no exigeixen privilegi sobre la seqüència, però es concedeix per seguretat davant `setval/currval`). Cap `TRUNCATE`: els tests fan servir `DELETE`/transaccions amb *rollback*.

### 7.3 Context de la petició (per transacció, compatible amb PgBouncer en mode transacció)

1. `ATOMIC_REQUESTS = True` a l'alias de l'aplicació (cada petició és **una transacció**; DRF també marca *rollback* amb el seu `set_rollback`, que només actua amb aquest paràmetre).
2. A `APIView.initial()` (**després** de `perform_authentication`, ja dins de la transacció d'`ATOMIC_REQUESTS`) s'executa **una** sentència:
   ```sql
   SELECT set_config('app.uid',       %s, true),   -- request.user_uid o '' si anònima
          set_config('app.is_admin',  %s, true),   -- 'true' si el token verificat té role == 'admin'
          set_config('app.is_system', 'false', true);
   ```
   `is_local = true` ⇒ el valor mor al `COMMIT/ROLLBACK`: **mai** es filtra a una altra petició que reutilitzi la connexió del pooler. Les rutes anònimes (`/api/refuges/`, `/health/`) fixen `uid=''`; les polítiques de lectura pública `USING (true)` continuen funcionant.
3. **Fail-closed**: sense context, `core.uid()` és `NULL` ⇒ tot el que no és `USING (true)` es denega (una vista que oblidi fixar el context falla en lloc de filtrar dades).
4. Fora de peticions HTTP (comandes, tasques de Cloud Run, tests) s'usa el *context manager* `rls_context(uid=None, is_admin=False, system=False)` de `domain.core`, que obre `transaction.atomic()` i executa la mateixa sentència.
5. Els instruments de comptatge de consultes (`django_assert_num_queries`) han d'excloure aquesta sentència (§5.3).
6. `app.is_admin` es deriva **sempre** del token ja verificat pel middleware (`request.user_claims['role'] == 'admin'`), mai d'un camp de la petició.

### 7.4 Context de sistema (`app.is_system`): quan i com

`system_context()` posa `set_config('app.is_system','true', true)` dins la transacció en curs i el restableix a `'false'` en sortir (si la transacció es desfà, el valor local també). **Només s'usa en blocs curts, acotats i revisats** per a:

| Cas | Per què no és «de l'usuari» |
|---|---|
| Jobs programats: `process_yesterday_visits`, purga d'`audit_logs` (`expire_at`), d'`upload_intents` (`expire_at`), de visites/denúncies/avisos caducats, cua d'R2 | No hi ha usuari |
| Efectes creuats de moderació **en una petició d'un usuari**: auto-ocultar el mitjà d'un altre, comptar denunciants diferents, crear l'avís per a l'autor, `set_blocked` de l'usuari que puja contingut CSAM | Toquen files d'altres usuaris |
| Entrades d'auditoria amb actor «sistema» | `actor_uid = NULL` només amb `{SYS}` |
| Esborrat d'usuari reintentat per una tasca (Cloud Tasks) sense la petició de l'usuari | |

Mai per llegir dades per a un usuari «per comoditat». Cada ús ha de tenir un test que n'acoti l'abast.

**Alternatives per als jobs** (recomanació: usar `app` + `system_context()`): (a) executar-los amb l'alias `neon_migrator` (propietari ⇒ saltaria la RLS, però dóna credencials de DDL a un procés periòdic: **no recomanat**); (b) un tercer rol `app_jobs` amb `BYPASSRLS` i grants mínims **[NO VERIFICAT: cal comprovar que Neon permet crear rols amb `BYPASSRLS`]**. La càrrega inicial del JSON, les migracions i l'alta de hashes de la *blocklist* sí que van amb `neon_migrator` (són operacions d'administració puntuals).

**Model d'amenaça (honest)**: la RLS per GUC protegeix contra **errors de lògica** (una vista que oblida comprovar la propietat, un IDOR com C1) i dona defensa en profunditat; **no** protegeix davant d'execució arbitrària de SQL amb el rol `app` (qui pot executar SQL pot fer `set_config('app.is_system','true',false)`). La defensa contra injecció és l'ORM/consultes parametritzades; la de la *blocklist* és que `app` ni la pot llegir (§2.22).

### 7.5 Pla de proves de la RLS (rol `app`, Postgres Docker efímer)
1. Per a cada taula: anònim, usuari propi, usuari aliè, admin, sistema × `SELECT/INSERT/UPDATE/DELETE` (taula de veritat generada des de §2).
2. Cascades i `SET NULL` amb el rol `app`: `DELETE FROM users.users WHERE uid = …` esborra/anonimitza tot el previst **sense** que la RLS ho bloquegi (verifica la inferència de §2).
3. Sense context (`app.uid` no fixat, o `''` després d'una transacció anterior) tot el que no és públic és invisible.
4. `UPDATE users.users SET is_blocked = true` com a usuari normal falla (`fn_users_guard`).
5. `moderation_hash_blocklist`: `SELECT` denegat, `fn_hash_match` funciona; `audit_logs`: `UPDATE` denegat.
6. Reformes: dos `INSERT` que se solapen → `renovations_no_overlap`; `ini_date >= fin_date` → `renovations_dates_ck`; proposta `delete` amb `payload` → `refuge_proposals_shape_ck`.
7. `ON CONFLICT`/`RETURNING` sota RLS per a cada flux d'escriptura (favorits, visites, denúncies, auditoria).
