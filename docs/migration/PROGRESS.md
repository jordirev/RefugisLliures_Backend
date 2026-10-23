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
| 0 | Disseny BD | `migracio/disseny-bd` | en curs | Agent Sonnet redactant `docs/design/postgres-schema.md` |
| 1 | Infraestructura | `migracio/infraestructura` | pendent | |
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

## Pendents / bloquejos
- Cap.
