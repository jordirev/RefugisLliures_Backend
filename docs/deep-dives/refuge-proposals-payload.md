# Deep dive — Payload de les propostes i sincronització de `coords_refugis`

> **[FET]** comprovat al codi · **[INFERÈNCIA]** deducció · **[NO VERIFICAT]** depèn de config externa.
> Document pare: [flux 5 — Propostes](../flows/05-refuge-proposals.md). Relacionat: [condition-average.md](condition-average.md), [integrations/firestore.md](../integrations/firestore.md).

## 1. Regles per acció (`RefugeProposalCreateSerializer.validate`)
| Acció | `refuge_id` | `payload` | Obligatori dins el payload |
|---|---|---|---|
| `create` | **no** | sí | `name` (no buit), `coord` |
| `update` | sí | sí | — |
| `delete` | sí | **no** | — |

`comment` és opcional en tots els casos. Per a `update`/`delete` el controller comprova que el refugi existeix i en desa `refuge_snapshot`.

## 2. Camps del payload (`api/serializers/refuge_proposal_serializer.py`)
Permesos (`ALLOWED_REFUGE_FIELDS`): `name`, `coord {lat, long}`, `altitude` (0–8848), `places` (≥0), `remarque`, `info_comp`, `description`, `links` (URLs), `type`, `region`, `departement`, `condition` (0–3, vegeu [condition-average.md](condition-average.md)).

- `type` ∈ `non gardé`, `fermée`, `cabane ouverte mais ocupee par le berger l ete`, `orri`, `emergence`, `key_needed`.
- `info_comp` només accepta: `manque_un_mur`, `cheminee`, `poele`, `couvertures`, `latrines`, `bois`, `eau`, `matelas`, `couchage`, `bas_flancs`, `lits`, `mezzanine_etage`.
- Qualsevol altre camp (incloent `images_metadata`, `visitors`, `id`, `modified_at`) es rebutja. Com que el control de "camps desconeguts" s'executa primer, el missatge és el genèric `Camps no permesos al payload: ...` i no l'específic de camp prohibit **[FET]**.
- El serializer niat **valida** però el payload es desa **en brut** (sense coerció de tipus) — [TECH_DEBT M9](../TECH_DEBT.md).

## 3. Exemples
Crear:
```json
POST /api/refuges-proposals/
{ "action": "create",
  "payload": { "name": "Refugi Nou", "coord": {"long": 1.234, "lat": 42.567},
               "altitude": 1800, "places": 15, "type": "non gardé",
               "info_comp": {"cheminee": 1, "eau": 1, "lits": 1} },
  "comment": "Descobert durant una excursió" }
```
Actualitzar: `{"action": "update", "refuge_id": "<id>", "payload": {"places": 45}, "comment": "..."}`
Esborrar: `{"action": "delete", "refuge_id": "<id>", "comment": "Destruït per una allau"}`
Rebutjar (admin): `POST /api/refuges-proposals/<id>/reject/` amb `{"reason": "Cal més evidència"}`.

Respostes d'error de validació (400):
```json
{ "error": "Invalid data",
  "details": { "payload": "El camp 'name' és obligatori al payload per a l'acció 'create'" } }
```
```json
{ "error": "Invalid data",
  "details": { "payload": { "coord": { "long": ["This field is required."], "lat": ["This field is required."] } } } }
```
Èxit d'aprovar/rebutjar: `200 {"message": "Proposal approved successfully"}` / `{"message": "Proposal rejected successfully"}`.

## 4. Sincronització de `coords_refugis/all_refugis_coords`
El document únic que serveix `GET /api/refuges/` sense filtres es manté des de les estratègies d'aprovació (`api/daos/refuge_proposal_dao.py:62-209`):
```json
{ "created_at": "<timestamp>", "last_updated": "<timestamp>", "total_refugis": 150,
  "refugis_coordinates": [ { "id": "...", "coord": {"lat": 42.5, "long": 1.2}, "geohash": "sp4g2", "name": "...", "surname": "(opcional)" } ] }
```
| Acció aprovada | Funció | Efecte |
|---|---|---|
| create | `add_refuge_to_coords_refugis` | afegeix entrada (crea el document si no existeix) i recalcula `total_refugis` |
| update | `update_refuge_from_coords_refugis` | només si el payload porta `name` o `coord`; regenera `geohash` si canvia `coord` |
| delete | `delete_refuge_from_coords_refugis` | filtra l'entrada; warning si no hi era |

`geohash` = `generate_simple_geohash(lat, lng, precision=5)` (base32 `0123456789bcdefghjkmnpqrstuvwxyz`), la mateixa lògica que la comanda `extract_coords_to_firestore`.

> ⚠️ Totes tres fan read-modify-write de l'array sencer (sense transacció) → aprovacions concurrents poden perdre entrades ([TECH_DEBT A3](../TECH_DEBT.md)). El document creix amb cada refugi (límit d'1 MiB de Firestore).

## 5. Logs útils
Nivell DAO (23): `Firestore WRITE: collection=refuges_proposals ...`, `Firestore UPDATE: collection=coords_refugis document=all_refugis_coords (ADD refuge <id>)`. Els `logger.info` (p. ex. "Coordenades del refugi ... afegides") no surten amb la configuració de logging actual ([ARCHITECTURE §8](../ARCHITECTURE.md)).
