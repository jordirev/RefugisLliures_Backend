# Equip de cada chunk: rols i regles comunes

> Brief que l'orquestrador passa a cada agent. Si la migració la continua un altre LLM, ha de fer servir aquest document per llançar els agents.

## Regles comunes (tots els rols)
- Llegir primer: `CLAUDE.md`, `docs/migration/PLAN.md`, `docs/migration/PROGRESS.md`, `docs/migration/DECISIONS_AUTONOMES.md` i les seccions del disseny (`docs/design/postgres-schema.md`) que afecten el chunk. **El disseny és vinculant**. Si cal desviar-se'n, s'explica a l'orquestrador i no es fa en silenci.
- **Seguretat**:
  - No llegir ni imprimir `env/` ni valors de variables d'entorn (`DATABASE_URL_*`, `R2_*`, tokens).
  - Mai accedir a Neon ni a Firestore reals (tampoc hi ha xarxa TCP cap a Neon). Els tests van contra el Postgres 16 local (`scripts/dev/setup_local_postgres.sh`) o amb mocks.
- Treballar només a la branca del chunk (`migracio/<chunk>`), que ja està creada. Commits `[<Feature>] <tipus>: <comentari>` acabats amb:
  ```
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01P13FxMyQLUYAtHf8BFdnXW
  ```
  `git push origin migracio/<chunk>` després de cada commit, amb reintents (2 s, 4 s, 8 s i 16 s) si falla la xarxa.
- Fer commit i push sovint, perquè la feina no es perdi si s'acaben els crèdits.
- Català a comentaris, docstrings i docs; identificadors en anglès.
- L'objectiu és **migrar mantenint el comportament** (més les decisions del PO), no fer passar els tests a qualsevol preu.
- Informe final a l'orquestrador: breu, amb ordres executades, resultats (passa/falla amb números) i pendents.

## Tests
- Escriu primer els tests del chunk:
  - unitaris: models, serializers, helpers;
  - integració: vistes + ORM contra el Postgres local **amb el rol `app`** (perquè la RLS s'apliqui);
  - contracte: forma JSON de les respostes actuals;
  - casos d'èxit i d'error (400/401/403/404/409) i RLS (anònim, propi, aliè, admin, sistema).
- Executa'ls i **demostra que fallen** (enganxa el resum de pytest). No implementis codi de producció; com a molt, fixtures i infraestructura de test.
- Markers de `pytest.ini` (`--strict-markers`: si en cal un de nou, s'hi declara).

## Implementador
- Fa passar els tests amb les millors pràctiques:
  - ORM i GeoDjango, `select_related`/`prefetch_related`, `annotate`/`Subquery`, cap N+1 (`django_assert_num_queries`);
  - `transaction.atomic` + `select_for_update` on hi ha races; `INSERT … ON CONFLICT`;
  - constraints i índexs del disseny; FK reals per `RunSQL` (§6.3);
  - RLS, grants i triggers a la mateixa migració, amb `reverse_sql`;
  - cap SQL concatenat (sempre paràmetres).
- Simplifica els fluxos controller→DAO en menys consultes. Treu la cache Redis del domini tocat.
- RGPD: minimització, cascades i retenció segons el disseny §8.
- Si un test està malament (contradiu el disseny o el comportament), ho diu i el corregeix justificant-ho.

## Revisor (SQL senior)
- Revisa el diff del chunk: EXPLAIN de les consultes noves, índexs, N+1, transaccions i bloquejos, races, ús d'eines de Django pensades per a SQL (constraints, `F()`, `Exists`, `bulk_*`, `QuerySet.alias`, `Window`…), lint (`python -m pyflakes` o `ruff` si hi és) i RGPD.
- Aplica directament les correccions petites. Les grans, les reporta amb una proposta.

## Seguretat
- Revisa: injecció SQL (raw, `extra`, `RawSQL`, formatació de cadenes), `permission_classes` de cada vista, comprovacions de propietat, IDOR, polítiques RLS i grants (prova'ls amb el rol `app`), filtracions de dades personals a respostes i logs, i que el context RLS sigui local a la transacció.
- Escriu tests per a cada forat que trobi i corregeix el que sigui segur de corregir.

## Documentació
- Actualitza `docs/` segons la taula "En canviar codi" del `CLAUDE.md` (fluxos, ARCHITECTURE, integracions, guies, GOTCHAS, TECH_DEBT) i la llegenda [FET]/[INFERÈNCIA]/[NO VERIFICAT].
- No toquis `docs/migration/PROGRESS.md`: el manté l'orquestrador.
- Executa `graphify update .` si `graphify` està instal·lat. Si no hi és, digues-ho.

## E2E (orquestrador)
- Servidor local (`runserver`) contra el Postgres local amb rols reals i Firebase Auth Emulator, amb tokens d'usuari normal i d'admin. Es prova cada endpoint del chunk (èxit i error) amb `curl` i s'anota el resultat a `PROGRESS.md`.
