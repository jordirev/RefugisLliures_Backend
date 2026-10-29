# Flux 7 — Renovations (reformes) i participants

> **[FET]** comprovat al codi · **[INFERÈNCIA]** deducció · **[NO VERIFICAT]** depèn de config externa.

**Migrat a PostgreSQL (chunk 5).** App `apps/renovations` (`views`, `serializers`, `selectors`, `services`, `models`, `urls`, `migrations/0001_initial.py`), esquema `activity`. Disseny: [postgres-schema.md](../design/postgres-schema.md) §2.12–§2.14 i §5.2; decisions D32–D35 de [DECISIONS_AUTONOMES](../migration/DECISIONS_AUTONOMES.md). Ja no hi ha controller, DAO, mapper ni cache Redis per a les reformes (el codi legacy que en queda, vegeu [TECH_DEBT R15](../TECH_DEBT.md)). Ja no és el «domini de referència» del patró de Firestore: el patró nou és `apps/refuges` ([ARCHITECTURE §3](../ARCHITECTURE.md)).

## Endpoints
`/renovations/…` és a `apps/renovations/urls.py` (inclòs des d'`refugis_lliures/urls.py`); `refuges/{id}/renovations/` viu a `apps/renovations/views.py` però la ruta és a `refugis_lliures/urls.py` **[FET]**.

| Mètode | URL | Vista | Permisos (en ordre) |
|---|---|---|---|
| GET | `/api/renovations/` (**només vigents**: `fin_date >= avui` de Madrid) | `RenovationListAPIView.get` | IsAuthenticated, HasProfile |
| POST | `/api/renovations/` | `.post` | IsAuthenticated, HasProfile, **IsNotBlocked, IsAgeConfirmed** (D35) |
| GET | `/api/renovations/{id}/` (també les acabades) | `RenovationAPIView.get` | IsAuthenticated, HasProfile |
| PATCH | `/api/renovations/{id}/` | `.patch` | IsAuthenticated, HasProfile, **IsNotBlocked, IsAgeConfirmed**; propietat al service |
| DELETE | `/api/renovations/{id}/` | `.delete` | IsAuthenticated, HasProfile (un bloquejat pot esborrar la seva); propietat al service |
| POST | `/api/renovations/{id}/participants/` (unir-se) | `RenovationParticipantsAPIView.post` | IsAuthenticated, HasProfile, **IsNotBlocked, IsAgeConfirmed** |
| DELETE | `/api/renovations/{id}/participants/{uid}/` (sortir / expulsar) | `RenovationParticipantDetailAPIView.delete` | IsAuthenticated, HasProfile; propietat al service |
| GET | `/api/refuges/{id}/renovations/?active_only=` | `RefugeRenovationsAPIView.get` | IsAuthenticated, HasProfile |

- Els permisos d'escriptura es trien per mètode a `get_permissions()` de cada vista; `apps/auth/permissions.py` no canvia (D35). **Només l'escriptura de contingut** (crear, editar, unir-se) exigeix no estar bloquejat i tenir l'edat confirmada; `GET` i `DELETE` no, perquè un bloquejat pugui llegir i retirar el que és seu **[FET]**.
- `IsRenovationCreator` ja no s'usa: la propietat es comprova als *services* (a més de la RLS) **[FET]**.
- `GET /refuges/{id}/renovations/`: **`active_only` (D32)** — `true`, `True` i `1` filtren les vigents; absent, `false` o `0` retornen totes (comportament d'abans). Resol [TECH_DEBT B1](../TECH_DEBT.md) (abans la query s'ignorava). Refugi inexistent o ID que no és UUID → 404 «Refugi no trobat» **[FET]**.
- Els IDs de reforma i de refugi són **UUID v7** opacs; un ID que no és UUID (p. ex. un antic de Firestore) dona 404, no 500 **[FET]**.

## Forma JSON
```json
{"id": "<uuid>", "creator_uid": "<uid>|unknown", "refuge_id": "<uuid>",
 "ini_date": "YYYY-MM-DD", "fin_date": "YYYY-MM-DD", "description": "…",
 "materials_needed": "…|null", "participants_uids": ["…"], "group_link": "https://…"}
```
- `participants_uids`: ordenats per `(created_at, user_uid)` (ordre d'arribada). El creador no hi és mai.
- **`group_link` s'omet (la clau no hi és) per a qui no hi té dret**: només el veuen el creador, els participants i els admins. No és `null`: el serializer només l'emet si no és `None` **[FET]**. El comportament és d'abans (el `group_link` apuntava a un grup privat).
- **`expelled_uids` no s'emet mai**; els expulsats viuen a `activity.renovation_expelled` i només els veuen el creador, l'admin, el sistema i l'expulsat mateix (RLS) **[FET]**.
- `creator_uid` és `'unknown'` si el creador s'ha esborrat (reforma passada anònima) **[FET]**.
- `materials_needed` és opcional (`null` o buit). Els camps desconeguts del cos (`creator_uid`, `participants_uids`…) s'ignoren.

## Dades i regles a la BD
| Taula | Contingut | Regles |
|---|---|---|
| `activity.renovations` | `id`, `refuge_id`, `creator_uid` (nullable), `ini_date`, `fin_date`, `description`, `materials_needed`, `created_at` | `CHECK ini_date <= fin_date`, `CHECK btrim(description) <> ''` (D34), `EXCLUDE` de solapaments, FK `refuge_id` `ON DELETE CASCADE`, FK `creator_uid` `ON DELETE SET NULL` |
| `activity.renovation_group_links` | `renovation_id` (PK), `group_link` | `CHECK` http/https i ≤ 2048 caràcters; privada per RLS |
| `activity.renovation_participants` | PK composta `(renovation_id, user_uid)`, `created_at` | `INSERT … ON CONFLICT DO NOTHING` |
| `activity.renovation_expelled` | PK composta `(renovation_id, user_uid)`, `expelled_at` | mai a l'API |

### Reformes d'un dia
`ini_date == fin_date` és **vàlid** a serializer, model i BD (el rang és inclusiu als dos extrems: `daterange(ini, fin, '[]')`). Abans, el serializer l'acceptava però el model no, i la llista d'actives quedava buida per a tothom ([TECH_DEBT A1](../TECH_DEBT.md), resolt) **[FET]**.

### Solapaments: `EXCLUDE` → 409
`EXCLUDE USING gist (refuge_id WITH =, daterange(ini_date, fin_date, '[]') WITH &&)` (`renovations_no_overlap`) impedeix dues reformes del mateix refugi amb dates que se solapin (límits inclosos; també compten les acabades i les anònimes). El *service* fa primer una comprovació prèvia (`find_overlapping`) per poder retornar la reforma en conflicte, i **si hi ha una carrera ho agafa l'`EXCLUDE`**: `IntegrityError` → es tradueix per `constraint_name` (mai pel text) → `OverlappingRenovation`. La resposta és `409 {error, overlapping_renovation}`; ja no es detecta per la subcadena `'solapa'` **[FET]**.

### Triggers (tots `SECURITY DEFINER`, `search_path` fixat; tots a `0001_initial`)
| Trigger | Quan | Què fa |
|---|---|---|
| `renovations_requires_link` | **`CONSTRAINT TRIGGER` diferit** (`AFTER INSERT`, `DEFERRABLE INITIALLY DEFERRED`) | Al `COMMIT` exigeix que una reforma amb creador tingui fila a `renovation_group_links` (si no, `check_violation`). Per això reforma i enllaç es creen a la mateixa transacció. D33: relegeix la fila actual, de manera que una reforma creada i esborrada/anonimitzada a la mateixa transacció no falla |
| `renovations_anonymize` | `AFTER UPDATE OF creator_uid` | Quan el creador passa a `NULL` (esborrat d'usuari, `SET NULL`), esborra l'enllaç del grup (privacitat) |
| `renovation_participants_guard` | `BEFORE INSERT` a participants | Rebutja un expulsat (`renovation_participants_not_expelled_ck`) i el creador (`renovation_participants_not_creator_ck`) |
| `renovation_expelled_guard` | `BEFORE INSERT` a expulsats | Rebutja expulsar algú que encara és participant (`renovation_expelled_not_participant_ck`): primer s'ha de treure |

Les FK són reals (`DEFERRABLE INITIALLY DEFERRED`) i es creen per `RunSQL`; la RLS (polítiques `renov_*`, `rlinks_*`, `rparts_*`, `rexp_*`) i els grants (`app`: `renovation_expelled` només `SELECT, INSERT`; l'enllaç sense `DELETE`) també són a la migració **[FET]**.

## Passos
- **Llegir** (`selectors.py`): una consulta per cas d'ús, sense cache. `annotated()` afegeix `participants_uids` (`ArraySubquery`) i `group_link` (**`LEFT JOIN` a `renovation_group_links`**: la RLS filtra la fila de l'enllaç, no la reforma, així que a qui no hi té dret li arriba `NULL` i la reforma es veu igualment). Vigents: `fin_date >= get_madrid_today()` (l'última inclosa), ordenades per `(ini_date, id)`. `GET /refuges/{id}/renovations/` fa 2 consultes (existència del refugi + dades) per distingir «sense reformes» de 404 **[FET]**.
- **Crear** (`services.create_renovation`): refugi existent (si no, 404) → comprovació de solapament (409) → `INSERT` reforma + `INSERT` enllaç dins un *savepoint* → relectura anotada. 201. L'`EXCLUDE` cobreix la carrera.
- **Editar** (`update_renovation`): `transaction.atomic`; només el creador (si no, 403; **un admin tampoc**, perquè és la RLS d'`UPDATE` i el service que comparen `creator_uid`); `SELECT … FOR UPDATE`; les dates noves es **combinen amb les desades** abans de validar (`ini > fin` → 400 «La data d'inici no pot ser posterior…»; resol [TECH_DEBT M2](../TECH_DEBT.md), abans PATCH amb una sola data donava 500); si les dates canvien, es torna a comprovar el solapament excloent la pròpia reforma (409). `group_link` s'actualitza a la seva taula. Al PATCH, `ini_date` ha de ser ≥ avui (Madrid).
- **Esborrar** (`delete_renovation`): només el creador; la BD cascadeja participants, expulsats i enllaç. 204.
- **Unir-se** (`add_participant`): el creador no pot (400); `INSERT … ON CONFLICT DO NOTHING` (la PK resol la carrera: [TECH_DEBT A3](../TECH_DEBT.md), resolt a reformes); si el *trigger* diu «expulsat» → 403; si no s'insereix res → 409 (ja participant). **Unir-se a una reforma ja acabada continua permès** (D35). 200 amb la reforma.
- **Sortir / expulsar** (`remove_participant`): el propi participant surt (pot tornar) o el creador l'expulsa (`DELETE` de participants + `INSERT` d'expulsats a la mateixa transacció). Un tercer → 403 «No tens permís…». Si no és participant → 403 «L'usuari no és participant…» i **no es crea cap expulsió**.
- **Comptador del perfil**: `num_renovated_refuges` = `selectors.count_renovated_refuges(uid)`: reformes creades **+** reformes on participa, passades incloses; els expulsats no compten. **1 consulta SQL**; el perfil propi fa 3 consultes com a màxim (D35). `apps/accounts/selectors.get_legacy_counts` en depèn **[FET]**.
- **Esborrat d'usuari**: vegeu sota i [deep-dive](../deep-dives/user-deletion.md).

## Errors
| Cas | HTTP | Cos |
|---|---|---|
| Validació (camp, dates, `group_link`) | 400 | `{error: "Dades invàlides", details}` |
| PATCH: `ini > fin` un cop combinades amb les desades | 400 | `{error}` |
| Creador intenta unir-se | 400 | `{error}` |
| No autenticat | 401 | |
| Sense perfil / bloquejat / edat no confirmada (només POST, PATCH, unir-se) | 403 | segons el permís (`profile_required`, bloqueig, `age_not_confirmed`) |
| No és el creador (PATCH/DELETE, també un admin) / no pot treure aquest participant / no és participant / expulsat | 403 | `{error}` |
| Reforma, refugi o ID no UUID inexistents | 404 | `{error}` |
| Solapament (`EXCLUDE`) / ja participant | 409 | `{error[, overlapping_renovation]}` |
| Error intern | 500 | `{error, error_id}` (`server_error`, mai `str(e)`) |
| DELETE reforma OK | 204 | |

## Anonimització en esborrar un usuari (§8.4)
`accounts.services.delete_user` crida `renovations.services.delete_current_by_creator(uid)` **dins el mateix *savepoint*** que el `DELETE users.users` **[FET]**:
1. **Vigents creades** (`fin_date >= avui`): s'esborren (cascada a participants, expulsats i enllaç).
2. **Passades creades**: la FK `SET NULL` deixa `creator_uid = NULL` (l'API emet `'unknown'`) i `renovations_anonymize` en treu l'enllaç del grup.
3. **Participacions i expulsions** de l'usuari: cascada de les FK a `users.users`.
Els 4 passos de Firestore que ho feien abans han desaparegut de `_firestore_steps`.

## Gotchas
- [GOTCHAS #17](../GOTCHAS.md): serializer, model i `CHECK` apliquen la mateixa regla de dates.
- [GOTCHAS #9](../GOTCHAS.md): el solapament i «unir-se» són atòmics a la BD.
- Constraint trigger diferit i `LEFT JOIN` de `group_link` sota RLS: [GOTCHAS #66–68](../GOTCHAS.md).
