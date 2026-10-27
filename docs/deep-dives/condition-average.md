# Deep dive — Condició d'un refugi com a mitjana de contribucions

> **[FET]** comprovat al codi · **[INFERÈNCIA]** deducció · **[NO VERIFICAT]** depèn de config externa.
> Documents pare: [flux 8 — Experiències](../flows/08-experiences.md) i [flux 5 — Propostes](../flows/05-refuge-proposals.md). Relacionat: [flux 4 — Cerca](../flows/04-refuge-search-detail.md), [TECH_DEBT M5](../TECH_DEBT.md), [postgres-schema §2.9](../design/postgres-schema.md).

## Idea
La `condition` d'un refugi no és un valor que s'edita directament: és la **mitjana** de les condicions aportades pels usuaris. Des del **chunk 7** hi aporten dues vies: **les experiències** (cada experiència porta una `condition` 0–3 obligatòria i és un vot; mitjana mantinguda per un *trigger* de la BD) i **les propostes aprovades** (encara a Firestore, `ConditionService`, fins al chunk 8).

## Camps a PostgreSQL (`refuges.refuges`, chunk 2) [FET]
| Camp | Tipus | Significat |
|---|---|---|
| `condition` | `double precision` (0–3, nullable) | Mitjana de les contribucions |
| `num_contributed_conditions` | int | Nombre de contribucions (*n*) |
| `condition_reset_at` | `timestamptz` (nullable) | Instant de l'últim *reset* per una proposta aprovada amb `condition` (el posarà el chunk 8; avui sempre `NULL`) |

No hi ha entitat vot ni taula de vots: l'estat és només aquesta mitjana i, per experiència, `activity.experiences.condition` + `condition_counted_at`.

## Experiències: *trigger* de la BD (chunk 7) [FET]
`activity.fn_experience_condition()` (`apps/experiences/migrations/0001_initial.py`) és `SECURITY DEFINER` (el rol `app` no pot fer `UPDATE refuges.refuges`; el propietari és `migrator`), amb `search_path` fixat, `REVOKE ALL … FROM PUBLIC`. Bloqueja la fila del refugi (`SELECT … FOR UPDATE`) perquè dos vots concurrents no es trepitgin, i usa els valors reals de la fila `NEW` (ja validats per la RLS i el `CHECK` d'`experiences`). Dos *triggers* `BEFORE`: `experiences_condition_ins` (`INSERT`) i `experiences_condition_upd` (`UPDATE OF condition … WHEN (OLD.condition IS DISTINCT FROM NEW.condition)`).

| Esdeveniment | Efecte al refugi |
|---|---|
| `INSERT` amb valor *v* | vot nou: `c = (coalesce(c,0)·n + v)/(n+1)`, `n = n+1`; `NEW.condition_counted_at := now()` |
| `UPDATE` de `condition` *v → v'* (valor diferent) | ajusta el vot: `c = clamp(c + (v'−v)/n, 0, 3)`, `n` igual |
| `UPDATE` d'un valor «antic» (`OLD.condition_counted_at < condition_reset_at`) o amb `n = 0` | compta com a **vot nou** (com l'`INSERT`) i `condition_counted_at := now()` |
| `UPDATE` sense canvi de valor (p. ex. només el comentari) | cap efecte |
| Esborrar l'experiència o el compte de l'usuari | **no** toca el refugi (el vot no es retira; el valor no és dada personal) |

L'aplicació **no calcula mai la mitjana**: `services.create_experience`/`update_experience` només fan `INSERT`/`UPDATE` ([flux 8](../flows/08-experiences.md)). Proves: `apps/experiences/tests/test_condition_trigger.py` i `test_concurrency.py`.

## Propostes: `ConditionService` (encara Firestore, fins al chunk 8)

`ConditionService` (`api/services/condition_service.py`) és un servei amb mètodes estàtics: **només calcula**, no escriu a Firestore. El DAO/Strategy fa un únic `update()` amb la resta de camps. Escriu a `data_refugis_lliures` (Firestore, catàleg antic): **no** arriba a `refuges.refuges` ni, per tant, al que serveix `/api/refuges/` ([TECH_DEBT R2](../TECH_DEBT.md)); el chunk 8 el substituirà per un `UPDATE` SQL amb `condition_reset_at = now()` (§2.9).

| Mètode | Retorna |
|---|---|
| `calculate_condition_average(current, n, contributed)` | `{condition: (current·n + contributed)/(n+1), num_contributed_conditions: n+1}`; si `current is None` → inicialitza |
| `initialize_condition(contributed)` | `{condition: float(contributed), num_contributed_conditions: 1}` |
| `validate_condition_value(v)` | `0 ≤ v ≤ 3` |

## On s'aplica
| Moment | Codi | Què passa |
|---|---|---|
| Crear / editar una **experiència** (chunk 7) | *trigger* `activity.fn_experience_condition` | vot nou / ajust del vot a `refuges.refuges` (vegeu dalt) |
| Aprovar proposta **create** amb `condition` | `CreateRefugeStrategy` (`api/daos/refuge_proposal_dao.py`) | `initialize_condition` |
| Aprovar proposta **update** amb `condition` | `UpdateRefugeStrategy` | llegeix `condition` i `num_contributed_conditions` actuals → `calculate_condition_average` → un sol `update()` |
| Seeding | `puntua_refugi` a `load_refuges` (`apps/refuges/management/commands/load_refuges.py`; substitueix `assign_conditions`) | nota 0–3 a partir d'`info_comp`, desada com a decimal amb `num_contributed_conditions = 0` |
| Lectura i filtre (PostgreSQL, chunk 2) | `RefugiSerializer.to_representation` (`apps/refuges/serializers.py`) i `core.round_half_even(condition)` | `round()` half-to-even → el client veu un enter 0–3; el filtre de cerca fa el mateix a SQL (2,5 → 2, 1,5 → 2) |

Validació d'entrada: `RefugeProposalPayloadSerializer.condition` (enter 0–3). Si el valor no és vàlid a l'estratègia, no s'actualitza i es registra un warning.

## Exemple
| Pas | Estat abans | Aportació | Càlcul | Estat després | Client veu |
|---|---|---|---|---|---|
| Creació | — | 2 | — | 2.0 / 1 | 2 |
| Update 1 | 2.0 / 1 | 3 | (2·1+3)/2 | 2.5 / 2 | **2** (`round(2.5) == 2`) |
| Update 2 | 2.5 / 2 | 1 | (2.5·2+1)/3 | 2.0 / 3 | 2 |

> Edició d'una experiència: amb 2.5 / 2, canviar un vot de 3 a 1 dona `c = 2.5 + (1−3)/2 = 1.5`, `n = 2` **[FET, fórmula del trigger]**.

> ⚠️ Python fa arrodoniment bancari: `round(2.5) == 2`, `round(1.5) == 2` **[FET, comportament de Python]**. La doc antiga deia que 2.5 es mostrava com 3.

## Incoherències conegudes
- El model i les propostes treballen amb **0–3**, però el filtre de cerca només accepta **0, 1, 2** exactes i compara contra el float desat → refugis amb mitjana no entera no surten mai filtrant per condició ([flux 4](../flows/04-refuge-search-detail.md), [TECH_DEBT M5](../TECH_DEBT.md)).
- Dos mecanismes fins al chunk 8: la mitjana de PostgreSQL només rep els vots de les **experiències** (trigger); les propostes aprovades continuen escrivint a Firestore i no la modifiquen ni en fan el *reset*.
- Una experiència **editada** ajusta el seu vot (no en suma un de nou), però esborrar-la no el retira: la mitjana pot reflectir vots d'experiències que ja no existeixen.
- Una proposta aprovada dues vegades (bug de cache [TECH_DEBT C2](../TECH_DEBT.md)) compta la contribució dos cops.
