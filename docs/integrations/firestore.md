# Integració — Cloud Firestore

> **[FET]** comprovat al codi · **[INFERÈNCIA]** deducció · **[NO VERIFICAT]** depèn de config externa.

Firestore és la **base de dades real** del domini **excepte els refugis**, que des del chunk 2 viuen a PostgreSQL (`apps/refuges`). Les col·leccions `data_refugis_lliures` i `coords_refugis` són **legacy**: ja no s'alimenten (la càrrega inicial és `load_refuges` a PostgreSQL) i els dominis encara a Firestore (experiències, dubtes, visites, propostes, usuaris, pujada de mitjans) les segueixen llegint/escrivint amb el `RefugiLliureDAO` fins que els migri el seu chunk ([GOTCHAS #41](../GOTCHAS.md)). No hi ha ORM per a Firestore: els DAOs fan servir el client de `firebase_admin.firestore`.

## Client
- `FirestoreService` singleton (`api/services/firestore_service.py:13-22`), instància global `firestore_service` (L78). `get_db()` (L24-38) reaprofita l'app de Firebase ja inicialitzada o la inicialitza.
- Els DAOs fan `FirestoreService()` a `__init__` i `self.firestore_service.get_db()` a cada mètode (p. ex. `api/daos/renovation_dao.py:20-23,36`).
- (`IsMediaUploader`, que feia servir `firestore_service.get_db()` directament, s'ha eliminat al chunk 2.)

## Col·leccions [FET]
| Col·lecció | DAO / definició | ID del document | Notes |
|---|---|---|---|
| `data_refugis_lliures` **(legacy)** | `RefugiLliureDAO.collection_name` (`api/daos/refugi_lliure_dao.py:19`) | auto-ID (o el del JSON de seeding), també camp `id` | conté el map `media_metadata` i l'array `visitors` |
| `coords_refugis` **(legacy)** | `RefugiLliureDAO.coords_collection_name` (L20) | document únic `all_refugis_coords` | array `refugis_coordinates[]` amb `{id, coord, geohash, name}`, `total_refugis`, `last_updated` |
| `users` | `UserDAO.COLLECTION_NAME` (`api/daos/user_dao.py:19`) | UID de Firebase | |
| `renovations` | `api/daos/renovation_dao.py:18` | auto-ID + camp `id` | |
| `experiences` | `api/daos/experience_dao.py:18` | auto-ID + camp `id` | |
| `doubts` + subcol·lecció `answers` | `api/daos/doubt_dao.py:18-19` | auto-ID | `answers` també es consulta amb `collection_group` |
| `refuges_proposals` | `api/daos/refuge_proposal_dao.py:579` | auto-ID + camp `id` | |
| `refuge_visits` | `api/daos/refuge_visit_dao.py:19` | auto-ID | un per (refugi, data) |

### Col·leccions noves (feature images) [FET]
| Col·lecció | Contingut | Notes |
|---|---|---|
| `upload_intents` | intents de pujada directa | **TTL** sobre `expire_at` (Timestamp, +1 dia) — crear la política a la consola |
| `media_reports` | denúncies de mitjans | ID determinista per (refugi, mitjà, denunciant); queries només d'igualtat |
| `moderation_notices` | avisos de moderació per usuari | query `uid ==`, ordenació en Python |
| `moderation_hash_blocklist` | hashes prohibits (sha256 / pHash) | manteniment manual |
| `audit_logs` | registre d'auditoria | **TTL** sobre `expire_at` (Timestamp, +12 mesos) |
Camps nous a `users/{uid}`: `age_confirmed_at`, `age_threshold`, `moderation_strikes`, `is_blocked`, `blocked_reason`, `blocked_at`. A `data_refugis_lliures/{id}.media_metadata[key]`: `status`, `thumb_key`, `width`, `height`, `size`, `blurhash`, `taken_at`, `media_type`, `content_type`, `rights_confirmed_at` ([flux 3](../flows/03-refuge-media-upload.md)).

## Operacions especials [FET] (grep a `api/`, excloent tests)
| Operació | On |
|---|---|
| `Increment` | `api/daos/user_dao.py` (comptadors), `api/daos/doubt_dao.py` (`answers_count`) |
| `ArrayUnion` | `api/daos/user_dao.py` (llistes de refugis), `api/daos/experience_dao.py` (`media_keys`) |
| `ArrayRemove` | `api/daos/experience_dao.py`, `api/daos/refugi_lliure_dao.py`, `api/daos/renovation_dao.py` |
| `SERVER_TIMESTAMP` | `api/daos/refuge_proposal_dao.py` |
| `batch()` | cap (les comandes de gestió que l'usaven — `assign_conditions`, `upload_refugis_to_firestore`, `extract_coords_to_firestore` — s'han eliminat al chunk 2) |
| `collection_group('answers')` | `api/daos/doubt_dao.py` |
| **Transaccions** | **cap** a `api/` |

## Queries que probablement requereixen índex compost [INFERÈNCIA]
No hi ha `firestore.indexes.json` al repo → l'estat dels índexs és **[NO VERIFICAT]**. La documentació antiga (quan es van crear les estratègies de cerca) afirmava que hi havia índexs compostos `type+places` i `type+altitude` creats a la consola, i en llistava com a pendents `type+condition+places`, `type+condition+altitude`, `condition+places`, `condition+altitude` **[NO VERIFICAT]**. Candidates:
- `renovations`: `where fin_date >=` + `order_by ini_date` (`api/daos/renovation_dao.py:131-133`), i variants amb `refuge_id ==` (L291-294, L372-375).
- `refuges_proposals`: diversos `where` + `order_by created_at desc` (`api/daos/refuge_proposal_dao.py:646-734`).
- `refuge_visits`: `refuge_id ==` + `date >=` + `order_by date`.
- `experiences`: `refuge_id ==` + `order_by modified_at desc`; `doubts`: `refuge_id ==` + `order_by created_at desc`.
- (La cerca de refugis ja no usa Firestore: viu a PostgreSQL des del chunk 2, `apps/refuges/selectors.py`.)
- `answers` (collection group) per `creator_uid` (esborrat d'usuari).

## Dades inicials (seeding)
| Comanda | Què fa |
|---|---|
| ~~`upload_refugis_to_firestore`~~ | **Eliminada (chunk 2)**: substituïda per `load_refuges` (PostgreSQL, d'un sol ús; vegeu [local-setup](../guides/local-setup.md)). |
| ~~`extract_coords_to_firestore`~~ | **Eliminada (chunk 2)**: la llista de coordenades és la vista `refuges.refuge_map` |
| ~~`assign_conditions`~~ / ~~`verify_conditions`~~ | `assign_conditions` eliminada (la condició inicial la fixa `puntua_refugi` a `load_refuges`); `verify_conditions` també eliminada |
| `process_yesterday_visits` | Procés diari (vegeu [flux 6](../flows/06-refuge-visits.md) i [guia](../guides/daily-visits-process.md)) |

Ordre d'execució en una BD nova: [guides/local-setup.md §5](../guides/local-setup.md).

## Gotchas
- Cap escriptura multi-document és atòmica; diversos arrays/maps es reescriuen sencers → vegeu [GOTCHAS](../GOTCHAS.md) #7-9.
- Dates com a strings ISO; l'ordre lexicogràfic n'és l'ordre cronològic només si el format és homogeni (`YYYY-MM-DD`).
- (Legacy) El document `coords_refugis/all_refugis_coords` creix amb cada refugi: límit d'1 MiB per document de Firestore **[INFERÈNCIA]**.
