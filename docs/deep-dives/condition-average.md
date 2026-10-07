# Deep dive — Condició d'un refugi com a mitjana de contribucions

> **[FET]** comprovat al codi · **[INFERÈNCIA]** deducció · **[NO VERIFICAT]** depèn de config externa.
> Document pare: [flux 5 — Propostes](../flows/05-refuge-proposals.md). Relacionat: [flux 4 — Cerca](../flows/04-refuge-search-detail.md), [TECH_DEBT M5](../TECH_DEBT.md).

## Idea
La `condition` d'un refugi no és un valor que s'edita directament: és la **mitjana** de totes les condicions aportades pels usuaris a través de propostes aprovades.

## Camps a Firestore (`data_refugis_lliures/{id}`)
| Camp | Tipus | Significat |
|---|---|---|
| `condition` | float | Mitjana de les contribucions |
| `num_contributed_conditions` | int | Nombre de contribucions |

## `ConditionService` (`api/services/condition_service.py`)
Servei amb mètodes estàtics: **només calcula**, no escriu a Firestore. El DAO/Strategy fa un únic `update()` amb la resta de camps.

| Mètode | Retorna |
|---|---|
| `calculate_condition_average(current, n, contributed)` | `{condition: (current·n + contributed)/(n+1), num_contributed_conditions: n+1}`; si `current is None` → inicialitza |
| `initialize_condition(contributed)` | `{condition: float(contributed), num_contributed_conditions: 1}` |
| `validate_condition_value(v)` | `0 ≤ v ≤ 3` |

## On s'aplica
| Moment | Codi | Què passa |
|---|---|---|
| Aprovar proposta **create** amb `condition` | `CreateRefugeStrategy` (`api/daos/refuge_proposal_dao.py`) | `initialize_condition` |
| Aprovar proposta **update** amb `condition` | `UpdateRefugeStrategy` | llegeix `condition` i `num_contributed_conditions` actuals → `calculate_condition_average` → un sol `update()` |
| Seeding | comanda `assign_conditions` | condició inicial a partir d'`info_comp` |
| Lectura | `RefugiSerializer.to_representation` | `round(condition)` → el client veu un enter |

Validació d'entrada: `RefugeProposalPayloadSerializer.condition` (enter 0–3). Si el valor no és vàlid a l'estratègia, no s'actualitza i es registra un warning.

## Exemple
| Pas | Estat abans | Aportació | Càlcul | Estat després | Client veu |
|---|---|---|---|---|---|
| Creació | — | 2 | — | 2.0 / 1 | 2 |
| Update 1 | 2.0 / 1 | 3 | (2·1+3)/2 | 2.5 / 2 | **2** (`round(2.5) == 2`) |
| Update 2 | 2.5 / 2 | 1 | (2.5·2+1)/3 | 2.0 / 3 | 2 |

> ⚠️ Python fa arrodoniment bancari: `round(2.5) == 2`, `round(1.5) == 2` **[FET, comportament de Python]**. La doc antiga deia que 2.5 es mostrava com 3.

## Incoherències conegudes
- El model i les propostes treballen amb **0–3**, però el filtre de cerca només accepta **0, 1, 2** exactes i compara contra el float desat → refugis amb mitjana no entera no surten mai filtrant per condició ([flux 4](../flows/04-refuge-search-detail.md), [TECH_DEBT M5](../TECH_DEBT.md)).
- Les experiències no aporten condició: només les propostes ([flux 8](../flows/08-experiences.md)).
- Una proposta aprovada dues vegades (bug de cache [TECH_DEBT C2](../TECH_DEBT.md)) compta la contribució dos cops.
