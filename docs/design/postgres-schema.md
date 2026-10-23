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
