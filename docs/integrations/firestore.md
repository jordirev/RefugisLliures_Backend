# Integració — Cloud Firestore

> **[FET]** comprovat al codi · **[INFERÈNCIA]** deducció · **[NO VERIFICAT]** depèn de config externa.

Firestore és la **base de dades real** de tot el domini. No hi ha ORM: els DAOs fan servir el client de `firebase_admin.firestore`.

## Client
- `FirestoreService` singleton (`api/services/firestore_service.py:13-22`), instància global `firestore_service` (L78). `get_db()` (L24-38) reaprofita l'app de Firebase ja inicialitzada o la inicialitza.
- Els DAOs fan `FirestoreService()` a `__init__` i `self.firestore_service.get_db()` a cada mètode (p. ex. `api/daos/renovation_dao.py:20-23,36`).
- Excepció: `IsMediaUploader` usa `firestore_service.get_db()` directament (`api/permissions.py:248`).

## Col·leccions [FET]
| Col·lecció | DAO / definició | ID del document | Notes |
|---|---|---|---|
| `data_refugis_lliures` | `RefugiLliureDAO.collection_name` (`api/daos/refugi_lliure_dao.py:18`) | auto-ID (o el del JSON de seeding), també camp `id` | conté el map `media_metadata` i l'array `visitors` |
| `coords_refugis` | `RefugiLliureDAO.coords_collection_name` (L19) | document únic `all_refugis_coords` | array `refugis_coordinates[]` amb `{id, coord, geohash, name}`, `total_refugis`, `last_updated` |
| `users` | `UserDAO.COLLECTION_NAME` (`api/daos/user_dao.py:19`) | UID de Firebase | |
| `renovations` | `api/daos/renovation_dao.py:18` | auto-ID + camp `id` | |
| `experiences` | `api/daos/experience_dao.py:18` | auto-ID + camp `id` | |
| `doubts` + subcol·lecció `answers` | `api/daos/doubt_dao.py:18-19` | auto-ID | `answers` també es consulta amb `collection_group` |
| `refuges_proposals` | `api/daos/refuge_proposal_dao.py:579` | auto-ID + camp `id` | |
| `refuge_visits` | `api/daos/refuge_visit_dao.py:19` | auto-ID | un per (refugi, data) |

## Operacions especials [FET] (grep a `api/`, excloent tests)
| Operació | On |
|---|---|
| `Increment` | `api/daos/user_dao.py` (comptadors), `api/daos/doubt_dao.py` (`answers_count`) |
| `ArrayUnion` | `api/daos/user_dao.py` (llistes de refugis), `api/daos/experience_dao.py` (`media_keys`) |
| `ArrayRemove` | `api/daos/experience_dao.py`, `api/daos/refugi_lliure_dao.py`, `api/daos/renovation_dao.py` |
| `SERVER_TIMESTAMP` | `api/daos/refuge_proposal_dao.py`, `api/management/commands/extract_coords_to_firestore.py` |
| `batch()` | només a comandes de gestió (`assign_conditions.py`, `extract_coords_to_firestore.py`, `upload_refugis_to_firestore.py`) |
| `collection_group('answers')` | `api/daos/doubt_dao.py` |
| **Transaccions** | **cap** a `api/` |

## Queries que probablement requereixen índex compost [INFERÈNCIA]
No hi ha `firestore.indexes.json` al repo → l'estat dels índexs és **[NO VERIFICAT]**. Candidates:
- `renovations`: `where fin_date >=` + `order_by ini_date` (`api/daos/renovation_dao.py:131-133`), i variants amb `refuge_id ==` (L291-294, L372-375).
- `refuges_proposals`: diversos `where` + `order_by created_at desc` (`api/daos/refuge_proposal_dao.py:646-734`).
- `refuge_visits`: `refuge_id ==` + `date >=` + `order_by date`.
- `experiences`: `refuge_id ==` + `order_by modified_at desc`; `doubts`: `refuge_id ==` + `order_by created_at desc`.
- `data_refugis_lliures`: estratègies amb `type in` + `condition in` + rang (`api/daos/search_strategies.py`).
- `answers` (collection group) per `creator_uid` (esborrat d'usuari).

## Dades inicials (seeding)
| Comanda | Què fa |
|---|---|
| `upload_refugis_to_firestore` | Carrega `api/utils/final_data_refuges.json` a `data_refugis_lliures` amb batches. **Només s'ha d'executar una vegada** (avís a les L10-16 del fitxer). |
| `extract_coords_to_firestore` | Construeix `coords_refugis/all_refugis_coords` a partir dels refugis |
| `assign_conditions` / `verify_conditions` | Assigna/verifica `condition` inicial a partir d'`info_comp` |
| `process_yesterday_visits` | Procés diari (vegeu [flux 6](../flows/06-refuge-visits.md)) |

## Gotchas
- Cap escriptura multi-document és atòmica; diversos arrays/maps es reescriuen sencers → vegeu [GOTCHAS](../GOTCHAS.md) #7-9.
- Dates com a strings ISO; l'ordre lexicogràfic n'és l'ordre cronològic només si el format és homogeni (`YYYY-MM-DD`).
- El document `coords_refugis/all_refugis_coords` creix amb cada refugi: límit d'1 MiB per document de Firestore **[INFERÈNCIA]**.
