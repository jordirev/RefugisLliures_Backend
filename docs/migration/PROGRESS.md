# Migració Firestore → PostgreSQL (Neon) — estat

> Document viu mantingut per l'orquestrador. Si la feina s'atura, un altre LLM ha de poder continuar llegint només aquest fitxer, [`PLAN.md`](PLAN.md) i els docs enllaçats.
> Mai s'escriuen credencials aquí: les variables `DATABASE_URL_APP`, `DATABASE_URL_MIGRATOR` i `R2_*` es llegeixen de l'entorn.

## Documents d'entrada
- [`PLAN.md`](PLAN.md) — pla aprovat (decisions, metodologia, chunks).
- [`arquitectura-neon-cloudrun-upstash.md`](arquitectura-neon-cloudrun-upstash.md) — document d'arquitectura (abast acordat: només capa de dades).
- [`uml-conceptual.md`](uml-conceptual.md) — UML conceptual de partida (incomplet).
- `../design/postgres-schema.md` — disseny físic de la BD (pas 0, en curs).

## Branques
- Integració: `migration` (inclou `develop` a `e5a56e6`). Chunks: `migracio/<chunk>` → PR a `migration`. Final: una PR `migration` → `develop` que fusiona l'usuari.

## Estat dels chunks
| # | Chunk | Branca | Estat | Notes |
|---|---|---|---|---|
| 0 | Disseny BD | `migracio/disseny-bd` | fet | `docs/design/postgres-schema.md` tancat (`e611fe3`), PR a `migration` |
| 1 | Infraestructura | `migracio/infraestructura` | en curs | equip: tests |
| 2 | Refugis | `migracio/refugis` | pendent | |
| 3 | Usuaris | `migracio/usuaris` | pendent | |
| 4 | Visites | `migracio/visites` | pendent | paral·lel amb 5, 6 |
| 5 | Renovations | `migracio/renovations` | pendent | paral·lel amb 4, 6 |
| 6 | Dubtes | `migracio/dubtes` | pendent | paral·lel amb 4, 5 |
| 7 | Experiències + pujades | `migracio/experiencies` | pendent | |
| 8 | Propostes | `migracio/propostes` | pendent | |
| 9 | Moderació + audit | `migracio/moderacio` | pendent | |
| 10 | Esborrat d'usuari | `migracio/esborrat-usuari` | pendent | |
| 11 | Neteja Firestore/cache | `migracio/neteja` | pendent | |

## Registre
- 2026-10-23 — Pla aprovat. Branca `migration` posada al dia amb `develop`. Iniciat el pas 0.
- 2026-10-23 — Decisió: PK subrogades com a UUID v7 (comunicada a l’agent de disseny).
- 2026-10-23 — Esborrany del disseny físic acabat (24 taules, 3 vistes, 6 schemas). Pendent: resposta del PO als dubtes de §11 abans de tancar el chunk 0.
- 2026-10-24 — PO ha respost els dubtes de §11 (vegeu PLAN.md, "Decisions sobre els dubtes"). Condition passa a ser atribut de l’experiència (sense taula de vots); llavor amb `puntua_refugi`, n=0. Tests locals: Postgres 16 natiu + PostGIS (apt), no Docker (daemon no disponible). Agent de disseny revisant el doc.

- 2026-10-24 — Disseny tancat (N1–N3 resolts pel PO). El PO delega les decisions: registre a [`DECISIONS_AUTONOMES.md`](DECISIONS_AUTONOMES.md).

## Pendents / bloquejos
- **Neon inaccessible des de l'entorn cloud** (el proxy no admet TCP de BD): e2e en local (D3). El PO ha d'executar `scripts/e2e/` i el bootstrap de §1.3 del disseny a Neon `dev` (D4).
