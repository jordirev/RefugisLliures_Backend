# Integració — Cloud Firestore

> **[FET]** comprovat al codi · **[INFERÈNCIA]** deducció · **[NO VERIFICAT]** depèn de config externa.

Firestore és la **base de dades real** del domini **excepte els refugis (chunk 2), els usuaris (chunk 3), les visites (chunk 4) i els dubtes i respostes (chunk 6)**, que viuen a PostgreSQL (`apps/refuges`, `apps/accounts`, `apps/visits`, `apps/doubts`). Les col·leccions `data_refugis_lliures` i `coords_refugis` són **legacy**: ja no s'alimenten (la càrrega inicial és `load_refuges` a PostgreSQL) i els dominis encara a Firestore (experiències, propostes, pujada de mitjans) les segueixen llegint/escrivint amb el `RefugiLliureDAO` fins que els migri el seu chunk ([GOTCHAS #41](../GOTCHAS.md)). No hi ha ORM per a Firestore: els DAOs fan servir el client de `firebase_admin.firestore`.

## Client
- `FirestoreService` singleton (`api/services/firestore_service.py:13-22`), instància global `firestore_service` (L78). `get_db()` (L24-38) reaprofita l'app de Firebase ja inicialitzada o la inicialitza.
- Els DAOs fan `FirestoreService()` a `__init__` i `self.firestore_service.get_db()` a cada mètode (p. ex. `api/daos/refuge_proposal_dao.py`).
- (`IsMediaUploader`, que feia servir `firestore_service.get_db()` directament, s'ha eliminat al chunk 2.)

## Col·leccions [FET]
| Col·lecció | DAO / definició | ID del document | Notes |
|---|---|---|---|
| `data_refugis_lliures` **(legacy)** | `RefugiLliureDAO.collection_name` (`api/daos/refugi_lliure_dao.py:19`) | auto-ID (o el del JSON de seeding), també camp `id` | conté el map `media_metadata` i l'array `visitors` |
| `coords_refugis` **(legacy)** | `RefugiLliureDAO.coords_collection_name` (L20) | document únic `all_refugis_coords` | array `refugis_coordinates[]` amb `{id, coord, geohash, name}`, `total_refugis`, `last_updated` |
| ~~`users`~~ **(migrada, chunk 3)** | _`UserDAO` eliminat_ | — | Ara és `users.users` (PostgreSQL). **Què en queda a Firestore per a usuaris**: (a) ~~`count()` d'agregació sobre `experiences`~~ **(resolt, chunk 7: tots dos comptadors del perfil són SQL)**; (b) el pas de Firestore de l'esborrat d'usuari (només propostes; D21); (c) `moderation_notices`, `media_reports`, `audit_logs`… per `uid` (encara no migrats). Les col·leccions de dades d'usuari antigues no es migren (decisió del PO). |
| ~~`renovations`~~ **(migrada, chunk 5)** | `RenovationDAO` (legacy, sense cap ruta; només el fa servir `refuge_proposal_dao`, [TECH_DEBT R15](../TECH_DEBT.md)) | — | Ara són `activity.renovations`, `renovation_group_links`, `renovation_participants` i `renovation_expelled` (PostgreSQL). Les dades de Firestore no es migren (decisió del PO). |
| ~~`experiences`~~ **(migrada, chunk 7)** | — (`ExperienceDAO` eliminat) | — | Ara és `activity.experiences` (PostgreSQL); les fotos, `refuge_media.experience_id`. Les dades de Firestore no es migren |
| ~~`doubts` + subcol·lecció `answers`~~ **(migrades, chunk 6)** | `api/daos/doubt_dao.py:18-19` (només codi legacy, [TECH_DEBT D1](../TECH_DEBT.md)) | auto-ID | Ara són `activity.doubts`/`activity.answers`. Les dades de Firestore no es migren |
| `refuges_proposals` | `api/daos/refuge_proposal_dao.py:579` | auto-ID + camp `id` | |
| ~~`refuge_visits`~~ | — | — | **Migrada (chunk 4)** a `activity.refuge_visits` / `refuge_visit_participants` (PostgreSQL); la col·lecció ja no s'usa |

### Col·leccions noves (feature images) [FET]
| Col·lecció | Contingut | Notes |
|---|---|---|
| ~~`upload_intents`~~ | — | **Migrada (chunk 7)** a `moderation.upload_intents` (PostgreSQL; purga amb `purge_upload_intents`). La política TTL de Firestore sobre `expire_at` ja no cal |
| `media_reports` | denúncies de mitjans | ID determinista per (refugi, mitjà, denunciant); queries només d'igualtat |
| `moderation_notices` | avisos de moderació per usuari | query `uid ==`, ordenació en Python |
| `moderation_hash_blocklist` | hashes prohibits (sha256 / pHash) | manteniment manual |
| `audit_logs` | registre d'auditoria | **TTL** sobre `expire_at` (Timestamp, +12 mesos) |
(Els camps d'edat i moderació d'usuari ja són columnes de `users.users`.) A `data_refugis_lliures/{id}.media_metadata[key]`: `status`, `thumb_key`, `width`, `height`, `size`, `blurhash`, `taken_at`, `media_type`, `content_type`, `rights_confirmed_at` ([flux 3](../flows/03-refuge-media-upload.md)).

## Operacions especials [FET] (grep a `api/`, excloent tests)
| Operació | On |
|---|---|
| `Increment` | `api/daos/doubt_dao.py` (`answers_count`; només codi legacy, cap vista el crida) (els comptadors d'usuari han desaparegut, D19) |
| `ArrayUnion` | cap ús actiu (el de `media_keys` d'experiències ha desaparegut al chunk 7) |
| `ArrayRemove` | `api/daos/refugi_lliure_dao.py` (i el `renovation_dao.py` legacy, sense cap ruta) |
| `SERVER_TIMESTAMP` | `api/daos/refuge_proposal_dao.py` |
| `batch()` | cap (les comandes de gestió que l'usaven — `assign_conditions`, `upload_refugis_to_firestore`, `extract_coords_to_firestore` — s'han eliminat al chunk 2) |
| `collection_group('answers')` | `api/daos/doubt_dao.py` (només codi legacy; l'esborrat d'usuari ja no el crida) |
| **Transaccions** | **cap** a `api/` |

## Queries que probablement requereixen índex compost [INFERÈNCIA]
No hi ha `firestore.indexes.json` al repo → l'estat dels índexs és **[NO VERIFICAT]**. La documentació antiga (quan es van crear les estratègies de cerca) afirmava que hi havia índexs compostos `type+places` i `type+altitude` creats a la consola, i en llistava com a pendents `type+condition+places`, `type+condition+altitude`, `condition+places`, `condition+altitude` **[NO VERIFICAT]**. Candidates:
- ~~`renovations`~~: migrat a PostgreSQL (índexs `renovations_refuge_fin_idx` i `renovations_fin_ini_idx`); ja no cal cap índex de Firestore.
- `refuges_proposals`: diversos `where` + `order_by created_at desc` (`api/daos/refuge_proposal_dao.py:646-734`).
- ~~`experiences`~~: migrat a PostgreSQL (índexs `experiences_refuge_idx` i `experiences_creator_idx`); ja no cal cap índex de Firestore.
- (La cerca de refugis ja no usa Firestore: viu a PostgreSQL des del chunk 2, `apps/refuges/selectors.py`.)
- ~~**Aggregation queries `count()`**~~ (chunk 3, D19): han desaparegut del tot (reformes al chunk 5, experiències al chunk 7); el perfil propi ja no toca Firestore **[FET]**.

## Dades inicials (seeding)
| Comanda | Què fa |
|---|---|
| ~~`upload_refugis_to_firestore`~~ | **Eliminada (chunk 2)**: substituïda per `load_refuges` (PostgreSQL, d'un sol ús; vegeu [local-setup](../guides/local-setup.md)). |
| ~~`extract_coords_to_firestore`~~ | **Eliminada (chunk 2)**: la llista de coordenades és una consulta directa a `refuges.refuges` (sense vista; disseny §5.3, recepta 5) |
| ~~`assign_conditions`~~ / ~~`verify_conditions`~~ | `assign_conditions` eliminada (la condició inicial la fixa `puntua_refugi` a `load_refuges`); `verify_conditions` també eliminada |
| `process_yesterday_visits` | Procés diari, ja només PostgreSQL (vegeu [flux 6](../flows/06-refuge-visits.md) i [guia](../guides/daily-visits-process.md)) |

Ordre d'execució en una BD nova: [guides/local-setup.md §5](../guides/local-setup.md).

## Gotchas
- Cap escriptura multi-document és atòmica; diversos arrays/maps es reescriuen sencers → vegeu [GOTCHAS](../GOTCHAS.md) #7-9.
- Dates com a strings ISO; l'ordre lexicogràfic n'és l'ordre cronològic només si el format és homogeni (`YYYY-MM-DD`).
- (Legacy) El document `coords_refugis/all_refugis_coords` creix amb cada refugi: límit d'1 MiB per document de Firestore **[INFERÈNCIA]**.
