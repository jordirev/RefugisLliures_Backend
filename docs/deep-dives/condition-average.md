# Deep dive — Condició d'un refugi com a mitjana de contribucions

> **[FET]** comprovat al codi · **[INFERÈNCIA]** deducció · **[NO VERIFICAT]** depèn de config externa.
> Documents pare: [flux 8 — Experiències](../flows/08-experiences.md) i [flux 5 — Propostes](../flows/05-refuge-proposals.md). Relacionat: [flux 4 — Cerca](../flows/04-refuge-search-detail.md), [TECH_DEBT M5](../TECH_DEBT.md), [postgres-schema §2.9](../design/postgres-schema.md).

## Idea
La `condition` d'un refugi no és un valor que s'edita directament: és la **mitjana** de les condicions aportades pels usuaris. Des del **chunk 7** hi aporten dues vies: **les experiències** (cada experiència porta una `condition` 0–3 obligatòria i és un vot; mitjana mantinguda per un *trigger* de la BD) i **les propostes aprovades** (chunk 8): una proposta amb `condition` no és un vot més, sinó que **reinicia** la mitjana (§2.9).

## Camps a PostgreSQL (`refuges.refuges`, chunk 2) [FET]
| Camp | Tipus | Significat |
|---|---|---|
| `condition` | `double precision` (0–3, nullable) | Mitjana de les contribucions |
| `num_contributed_conditions` | int | Nombre de contribucions (*n*) |
| `condition_reset_at` | `timestamptz` (nullable) | Instant de l'últim *reset* per una proposta aprovada amb `condition` (`TransactionNow()` a `apps/proposals/services.py`; `NULL` si mai n'hi ha hagut) |

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

## Propostes: *reset* de la mitjana (chunk 8)

`ConditionService` (mitjana incremental `new=(cur·n+v)/(n+1)`) **ha desaparegut** amb el DAO de propostes. Ara, en aprovar una proposta (`create` o `update`) amb `condition` **no nul·la**, `apps.proposals.services._refuge_columns` fa part de l'`UPDATE`/`INSERT` del refugi: `condition = valor`, `num_contributed_conditions = 1`, `condition_reset_at = now()` de la transacció (§2.9, D39). Una `condition` absent o `null` no toca la mitjana. Així una proposta d'un admin que corregeix l'estat del refugi substitueix la mitjana antiga en lloc de diluir-s'hi; les experiències posteriors tornen a fer la mitjana a partir d'aquest valor (el *trigger* no ha canviat).

## On s'aplica
| Moment | Codi | Què passa |
|---|---|---|
| Crear / editar una **experiència** (chunk 7) | *trigger* `activity.fn_experience_condition` | vot nou / ajust del vot a `refuges.refuges` (vegeu dalt) |
| Aprovar proposta **create** o **update** amb `condition` (chunk 8) | `apps/proposals/services.py: _refuge_columns` | *reset*: `c = valor`, `n = 1`, `condition_reset_at = now()` |
| Seeding | `puntua_refugi` a `load_refuges` (`apps/refuges/management/commands/load_refuges.py`; substitueix `assign_conditions`) | nota 0–3 a partir d'`info_comp`, desada com a decimal amb `num_contributed_conditions = 0` |
| Lectura i filtre (PostgreSQL, chunk 2) | `RefugiSerializer.to_representation` (`apps/refuges/serializers.py`) i `core.round_half_even(condition)` | `round()` half-to-even → el client veu un enter 0–3; el filtre de cerca fa el mateix a SQL (2,5 → 2, 1,5 → 2) |

Validació d'entrada: `PayloadSerializer.condition` (enter 0–3 o `null`).

## Exemple
| Pas | Estat abans | Aportació | Càlcul | Estat després | Client veu |
|---|---|---|---|---|---|
| Proposta create | — | 2 | *reset* | 2.0 / 1 | 2 |
| Experiència | 2.0 / 1 | 3 | (2·1+3)/2 (trigger) | 2.5 / 2 | **2** (`round(2.5) == 2`) |
| Proposta update | 2.5 / 2 | 1 | *reset* | 1.0 / 1 | 1 |

> Edició d'una experiència: amb 2.5 / 2, canviar un vot de 3 a 1 dona `c = 2.5 + (1−3)/2 = 1.5`, `n = 2` **[FET, fórmula del trigger]**.

> ⚠️ Python fa arrodoniment bancari: `round(2.5) == 2`, `round(1.5) == 2` **[FET, comportament de Python]**. La doc antiga deia que 2.5 es mostrava com 3.

## Incoherències conegudes
- El model i les propostes treballen amb **0–3**, però el filtre de cerca només accepta **0, 1, 2** exactes i compara contra el float desat → refugis amb mitjana no entera no surten mai filtrant per condició ([flux 4](../flows/04-refuge-search-detail.md), [TECH_DEBT M5](../TECH_DEBT.md)).
- Dos mecanismes: les **experiències** sumen vots (trigger) i les **propostes** reinicien la mitjana (codi d'aprovació). El *reset* no manté cap historial dels vots anteriors.
- Una experiència **editada** ajusta el seu vot (no en suma un de nou), però esborrar-la no el retira: la mitjana pot reflectir vots d'experiències que ja no existeixen.
- La doble aprovació és impossible (`FOR UPDATE … WHERE status='pending'`, [TECH_DEBT C2](../TECH_DEBT.md) resolt al chunk 8).
