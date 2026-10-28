# Flux 5 — Propostes de refugi (crear / editar / esborrar) i revisió admin

> **[FET]** comprovat al codi · **[INFERÈNCIA]** deducció · **[NO VERIFICAT]** depèn de config externa.

> **Migrat a PostgreSQL (chunk 8).** El domini viu a l'app `apps/proposals` (taula `proposals.refuge_proposals`, disseny [§2.18](../design/postgres-schema.md)). `RefugeProposalController`, `RefugeProposalDAO` (amb les estratègies `Create/Update/DeleteRefugeStrategy`), el mapper, el model, el serializer i les vistes de `api/`, `ConditionService` i el document `coords_refugis` ja no existeixen. Aprovar una proposta **escriu a PostgreSQL** (`refuges`, `refuge_amenities`, `refuge_links`) i el canvi es veu a `/api/refuges/` ([TECH_DEBT R2](../TECH_DEBT.md)).

Els usuaris **no modifiquen refugis directament**: creen una *proposta* que un admin aprova o rebutja. En aprovar-la, el service aplica el canvi al catàleg dins **una sola transacció**.

## Endpoints (`apps/proposals/views.py`, rutes a `apps/proposals/urls.py`, incloses des d'`api/urls.py`)
| Mètode | URL | Vista | Permisos |
|---|---|---|---|
| POST | `/api/refuges-proposals/` | `ProposalCollectionAPIView.post` | IsAuthenticated + HasProfile + IsNotBlocked + IsAgeConfirmed |
| GET | `/api/refuges-proposals/?status=&refuge-id=` | `ProposalCollectionAPIView.get` | IsAuthenticated + HasProfile + IsFirebaseAdmin |
| GET | `/api/my-refuges-proposals/?status=` | `MyProposalCollectionAPIView.get` | IsAuthenticated + HasProfile (un admin hi veu només les seves) |
| POST | `/api/refuges-proposals/{id}/approve/` | `ProposalApproveAPIView.post` | IsAuthenticated + HasProfile + IsFirebaseAdmin (pot aprovar la seva) |
| POST | `/api/refuges-proposals/{id}/reject/` (`{reason?}`) | `ProposalRejectAPIView.post` | IsAuthenticated + HasProfile + IsFirebaseAdmin |

Ordre de les comprovacions: permisos (401/403) → validació (400) → existència (404) → estat (409).

Taula `proposals.refuge_proposals` = `{id (uuid v7), refuge_id (FK SET NULL), action(create|update|delete), status(pending|approved|rejected), payload jsonb, refuge_snapshot jsonb, comment, creator_uid (FK SET NULL), created_at, reviewer_uid (FK SET NULL), reviewed_at, rejection_reason}`. L'API la serialitza amb les mateixes claus que abans; `creator_uid` NULL surt com a `'unknown'`.

## Diagrama — crear i aprovar

```mermaid
sequenceDiagram
    autonumber
    participant U as Usuari
    participant A as Admin
    participant V as Proposal*APIView
    participant S as CreateProposalSerializer
    participant SV as services (apps/proposals)
    participant DB as PostgreSQL (rol app, RLS)
    participant R as R2

    U->>V: POST /api/refuges-proposals/ {action, refuge_id?, payload?, comment?}
    V->>S: validate (regles per action, llista blanca, límits)
    V->>SV: create_proposal(...)
    alt action = create
        SV->>DB: refugis a <= 500 m amb nom semblant?
        opt n'hi ha
            V-->>U: 409 possible_duplicates (no es desa res)
        end
    else update|delete
        SV->>DB: get_refuge (inexistent → 400), desa refuge_snapshot
    end
    SV->>DB: INSERT proposta (status='pending')
    V-->>U: 201

    A->>V: POST /{id}/approve/
    V->>SV: approve_proposal(id, reviewer_uid)
    SV->>DB: BEGIN; SELECT … FOR UPDATE WHERE status='pending'
    alt no és pendent
        V-->>A: 404 (inexistent) / 409 (ja revisada)
    end
    alt create
        SV->>DB: INSERT refuges + refuge_amenities + refuge_links
    else update
        SV->>DB: UPDATE refuges (només claus enviades) + amenities + links
    else delete
        SV->>DB: rebutja les altres pendents; llegeix claus R2 (system_context)
        SV->>DB: DELETE refuges (cascades de la BD)
        SV->>R: delete_files(claus)
    end
    SV->>DB: UPDATE proposta → approved; COMMIT
    opt delete
        SV->>R: delete_files(miniatures) després del COMMIT
    end
    V-->>A: 200
```

## Passos
> Detall: validació i exemples de payload → [deep-dives/refuge-proposals-payload.md](../deep-dives/refuge-proposals-payload.md) · mitjana de condició → [deep-dives/condition-average.md](../deep-dives/condition-average.md) · fer-se admin per revisar → [guides/admin-management.md](../guides/admin-management.md).

1. **Validació** (`CreateProposalSerializer`): `create` requereix payload amb `name` i `coord` i cap `refuge_id`; `update` requereix `refuge_id` + payload; `delete` requereix `refuge_id` i cap payload. Claus del payload ⊂ `ALLOWED_REFUGE_FIELDS`; límits que eviten un 500 en aprovar (D39): `name`/`region`/`departement` ≤ 255, `places` ≤ 2³¹−1, `lat`/`long` en rang i no (0,0), enllaços únics, http(s) i ≤ 2048, `info_comp` 0/1, `type` del catàleg, payload < 60 KiB, `comment` ≤ 4000, `reason` ≤ 2000. Es desen **només les claus enviades**, amb tipus coercits (M9).
2. **Crear** — `services.create_proposal`. `update`/`delete`: `refuge_selectors.get_refuge`; si no existeix, `RefugeNotFound` (400); es desa `refuge_snapshot` (el refugi en forma d'API, sense `visitors` ni mitjans). `create`: `find_possible_duplicates` (una consulta, `ST_DWithin` a 500 m + la regla de nom de la cerca: `core.norm_name` + `pg_trgm`/subcadena sobre `name` i `surname`; màxim 20 candidats; calen **les dues** condicions) → si en troba, `PossibleDuplicates` (409) i no es desa res.
3. **Llistar** — `selectors.list_proposals` (una consulta, `created_at DESC, id DESC`; sense cache). La RLS filtra: cadascú veu les seves, l'admin totes; `my-refuges-proposals` afegeix `creator_uid = actor`.
4. **Aprovar** — `services.approve_proposal`, tot dins `transaction.atomic`:
   - `_lock_pending`: `SELECT … FOR UPDATE … WHERE status = 'pending'`; si no hi és, 404 (inexistent / ID no UUID) o 409 (ja aprovada/rebutjada). La doble aprovació és impossible a la BD ([TECH_DEBT C2](../TECH_DEBT.md)).
   - `create`: `Refuge.objects.create` + fila d'amenities (12 indicadors) + enllaços; `modified_at` = data de Madrid del `created_at` de la proposta; `condition` present inicialitza la mitjana (`n=1`, `condition_reset_at`).
   - `update`: només s'escriuen les claus enviades (`description: null` → `''`; `region`/`departement` `''` → NULL); `info_comp` substitueix els 12 indicadors (els absents → `false`); `links` se substitueixen sencers; `condition` present **reinicia** la mitjana (§2.9), absent/`null` no la toca.
   - `delete`: rebutja les altres pendents del refugi (`rejection_reason = 'refuge has been deleted'`), llegeix les claus d'R2 de **tots** els mitjans amb `system_context()`, fa **un sol `DELETE`** del refugi (la BD cascadeja experiències, mitjans, dubtes, reformes, visites… i posa `refuge_id = NULL` a les propostes) i esborra els fitxers d'R2; si R2 falla, `MediaStorageError` → 500 i es desfà tot. Les miniatures s'esborren després del `COMMIT` (si fallen, només queden fitxers orfes; [TECH_DEBT P5](../TECH_DEBT.md)).
   - Un enllaç del payload que ja és d'un altre refugi (PK de `refuge_links`) → `LinkAlreadyUsed` (409) i tot desfet: la proposta continua pendent.
   - L'escriptura del catàleg la fa el rol `app` amb la RLS `{ADM} OR {SYS}` de `refuges`, `refuge_amenities` i `refuge_links` (migració `proposals.0001`).
5. **Rebutjar** — `services.reject_proposal`: mateix bloqueig; sense motiu `rejection_reason` queda NULL.

## Errors
| Cas | HTTP | Cos |
|---|---|---|
| Validació (acció, payload, `reason`) | 400 | `{"error":"Invalid data","details":{...}}` |
| Filtre `status` invàlid | 400 | `{"error":"Invalid status filter: x. Must be 'pending', 'approved', or 'rejected'"}` |
| `update`/`delete` d'un refugi inexistent (o ID no UUID) | 400 | `{"error":"Refuge does not exists"}` |
| Sense perfil / bloquejat / edat no confirmada / no admin | 403 | `profile_required` / `user_blocked` / `age_not_confirmed` / el 403 d'`IsFirebaseAdmin` |
| Proposta inexistent (o ID no UUID) en aprovar/rebutjar | 404 | `{"error":"Proposal not found"}` |
| Proposta ja aprovada/rebutjada | 409 | `{"error":"Proposal is already approved"}` (o `rejected`) |
| `create` amb possibles duplicats | 409 | `{"error":"possible_duplicates","code":"possible_duplicates","message":"Hi ha refugis a menys de 500 m amb un nom semblant. Comprova que no sigui el mateix.","possible_duplicates":[{"id","name","distance_m"}]}` |
| Aprovar amb un enllaç que ja és d'un altre refugi | 409 | `{"error":"A link of the proposal already belongs to another refuge"}` |
| BD / R2 caiguts | 500 | `{"error","error_id"}` (`server_error`) |

El frontend ha de gestionar el 409 `possible_duplicates` (mostrar els candidats `id`/`name`/`distance_m` perquè l'usuari comprovi que no és el mateix refugi). Cal adaptar-lo (decisió del PO, 28/10).

## Gotchas i notes
- **Esborrat d'usuari**: les propostes es conserven (historial) amb `creator_uid`/`reviewer_uid` NULL (FK `SET NULL`; l'API torna `'unknown'`), però el `comment` s'anul·la (RGPD, decisió del PO 28/10) a `accounts.services.delete_user`. Vegeu [deep-dives/user-deletion.md](../deep-dives/user-deletion.md).
- Aprovar un `delete` no tracta cap dada pel seu compte: visites, preferits, visitats, reformes, dubtes i experiències cauen per les FK `ON DELETE CASCADE` del refugi.
- Els fitxers d'intents de pujada pendents d'un refugi esborrat cauen per cascada a la BD però no s'esborren d'R2 ([TECH_DEBT P5](../TECH_DEBT.md)).
- Duplicats només contra refugis existents: dues propostes `create` pendents no es comparen entre elles ([TECH_DEBT P6](../TECH_DEBT.md)).
- Els límits i els `CHECK` de `jsonb` del payload viuen alhora al serializer i a la migració (GOTCHAS #5): si en toques un, toca l'altre.
- Pitfalls d'implementació: [GOTCHAS #76–82](../GOTCHAS.md).
