# Deep dive — Payload de les propostes (validació, jsonb i aplicació al catàleg)

> **[FET]** comprovat al codi · **[INFERÈNCIA]** deducció · **[NO VERIFICAT]** depèn de config externa.
> Document pare: [flux 5 — Propostes](../flows/05-refuge-proposals.md). Relacionat: [condition-average.md](condition-average.md), [postgres-schema §2.18](../design/postgres-schema.md). Migrat a PostgreSQL al chunk 8 (`apps/proposals`).

## 1. Regles per acció (`apps/proposals/serializers.py: CreateProposalSerializer.validate`)
| Acció | `refuge_id` | `payload` | Obligatori dins el payload |
|---|---|---|---|
| `create` | **no** | sí | `name` (no buit), `coord` |
| `update` | sí | sí | — |
| `delete` | sí | **no** | — |

`comment` és opcional en tots els casos. Per a `update`/`delete` el service (`create_proposal`) comprova que el refugi existeix i en desa `refuge_snapshot`.

## 2. Camps del payload (`PayloadSerializer`)
Permesos (`ALLOWED_REFUGE_FIELDS`, sense `remarque`): `name` (≤ 255), `coord {lat, long}` (en rang i diferent de (0,0)), `altitude` (0–8848, nullable), `places` (0–2³¹−1, nullable), `info_comp`, `description`, `links` (URLs http(s) úniques, ≤ 2048), `type`, `region`/`departement` (≤ 255), `condition` (0–3, vegeu [condition-average.md](condition-average.md)). Límits afegits per la D39 perquè una aprovació no acabi en un 500.

- `type` ha d'existir al catàleg `refuges.refuge_types` (una consulta; els codis ja no són una llista fixa al serializer).
- `info_comp` només accepta les 12 claus d'`apps.refuges.models.RefugeAmenities.AMENITY_FIELDS` (`manque_un_mur`, `cheminee`, `poele`, `couvertures`, `latrines`, `bois`, `eau`, `matelas`, `couchage`, `bas_flancs`, `lits`, `mezzanine_etage`), valors 0/1.
- Qualsevol altre camp (incloent `images_metadata`, `visitors`, `id`, `modified_at`, `remarque`) es rebutja amb `Camps no permesos al payload: ...` (el control s'executa primer).
- El payload desat és el **validat**: només les **claus enviades** (en un `update`, «absent» ≠ `null`: `null` = «buida'l») i amb els tipus coercits (`"1200"` → `1200`, [TECH_DEBT M9](../TECH_DEBT.md)). No s'hi injecta cap valor per defecte.
- La BD ho reforça amb `CHECK`s `jsonb` a `proposals.0001`: forma per acció (`shape_ck`), claus permeses (`payload_keys_ck`), `coord` amb `lat`/`long` (`payload_coord_ck`) i mida < 64 KiB (`size_ck`).
- Efecte en aprovar: `description: null` → `''`; `region`/`departement` `''` → NULL; `info_comp` d'un `update` substitueix els 12 indicadors (els absents → `false`); `links` se substitueixen sencers; `condition` present reinicia la mitjana ([condition-average.md](condition-average.md)).

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

Respostes d'error de validació (400; format DRF: llista per als errors de `validate()`, diccionari per camp per als del serializer niat, [TECH_DEBT P7](../TECH_DEBT.md)):
```json
{ "error": "Invalid data",
  "details": { "payload": ["El camp 'name' és obligatori al payload per a l'acció 'create'"] } }
```
```json
{ "error": "Invalid data",
  "details": { "payload": { "coord": { "long": ["This field is required."], "lat": ["This field is required."] } } } }
```
Èxit d'aprovar/rebutjar: `200 {"message": "Proposal approved successfully"}` / `{"message": "Proposal rejected successfully"}`.

## 4. Duplicats en crear (409)
`POST` d'una proposta `create` amb un refugi existent **a ≤ 500 m i amb un nom semblant** (calen les dues condicions; decisió del PO, 28/10) → 409 i no es desa res:
```json
{ "error": "possible_duplicates", "code": "possible_duplicates",
  "message": "Hi ha refugis a menys de 500 m amb un nom semblant. Comprova que no sigui el mateix.",
  "possible_duplicates": [ {"id": "<uuid>", "name": "Refugi de Colomers", "distance_m": 120} ] }
```
Nom semblant = la regla de la cerca (`core.norm_name` sense accents ni majúscules + `pg_trgm` `trigram_similar` o subcadena, sobre `name` i `surname`). Màxim 20 candidats, per distància ascendent; `distance_m` arrodonit. El tall exacte és `ST_Distance <= 500` (vegeu [GOTCHAS #78](../GOTCHAS.md)). Només es compara contra refugis existents ([TECH_DEBT P6](../TECH_DEBT.md)).

## 5. El catàleg ja no té cap document de coordenades
`coords_refugis/all_refugis_coords` i el geohash manual han desaparegut: el mapa surt de la vista `refuge_map` de PostgreSQL ([flux 4](../flows/04-refuge-search-detail.md)). Aprovar una proposta només toca `refuges`, `refuge_amenities` i `refuge_links` en una transacció amb `SELECT … FOR UPDATE` de la proposta, així que les aprovacions concurrents ja no perden dades ([TECH_DEBT A3](../TECH_DEBT.md)).
