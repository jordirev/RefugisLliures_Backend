# Decisions preses per l'orquestrador sense validació del PO

> Des del 24/10/2026 el PO ha delegat les decisions: quan hi ha un dubte, l'orquestrador tria l'opció recomanada i l'apunta aquí amb les alternatives perquè el PO la pugui revisar i revertir.
> Format: **Decisió** · context · alternatives descartades · com revertir-la. Les decisions validades explícitament pel PO són a [`PLAN.md`](PLAN.md) i a `docs/design/postgres-schema.md` §11.

| # | Data | Chunk | Decisió presa | Alternatives | Impacte / com revertir |
|---|---|---|---|---|---|
| D1 | 2026-10-23 | 0 | Tests locals sobre **PostgreSQL 16 natiu + PostGIS 3** (apt) en lloc de Docker `postgis/postgis` | Arrencar `dockerd` dins el contenidor; Testcontainers | El daemon de Docker no estava actiu. Mateix aïllament (BD efímera local, mai Neon). Neon `dev` és PG17: les funcions específiques de 17 no es poden fer servir. |
| D2 | 2026-10-24 | 0 | Interpretació de la regla del "vot antic": una experiència compta com a vot nou si `condition_counted_at < condition_reset_at` (no `created_at`). | Comparar amb `created_at` (podria recomptar a cada PATCH) | Confirmada pel PO el 24/10 (es manté aquí com a traça). |
