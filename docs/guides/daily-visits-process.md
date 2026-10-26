# Guia — Executar el procés diari de visites

> **[FET]** comprovat al codi · **[INFERÈNCIA]** deducció · **[NO VERIFICAT]** depèn de config externa.
> Què fa el procés i els seus bugs: [flux 6](../flows/06-refuge-visits.md). On s'executa: [render-deploy-ci §Tasques programades](../integrations/render-deploy-ci.md#tasques-programades-què-està-actiu).

`process_yesterday_visits` (`apps/visits/management/commands/`, chunk 4) agafa les visites d'**ahir** (hora de Madrid, `get_madrid_today()`): copia els participants a **`users.user_visited_refuges`** (una `INSERT ... SELECT ... ON CONFLICT DO NOTHING`, idempotent), esborra les visites d'ahir sense participants i **purga les visites de més de 12 mesos** (§8.3; els participants cauen en cascada). Tot dins `system_context()` i només contra PostgreSQL: ja no toca Firestore. Les visites amb participants no s'esborren fins a la purga **[FET]**.

## Opció A — GitHub Actions (mecanisme real)
- Workflow `.github/workflows/process-visits.yml`, cron `0 3 * * *` (UTC).
- Execució manual: GitHub → **Actions** → *Process Yesterday Visits* → **Run workflow** (`workflow_dispatch`).
- El job només necessita `DATABASE_URL_APP` (PostgreSQL; el workflow ja la declara des de `secrets.DATABASE_URL_APP`). **U3 ajornat (D29)**: el PO encara no ha creat el secret de GitHub i pot moure els jobs a Cloud Run; mentre no hi sigui, el job no pot arribar a Neon i **falla** ([TECH_DEBT U3](../TECH_DEBT.md)) **[FET sobre el workflow; NO VERIFICAT l'estat del secret]**. El workflow no es modifica per al chunk 4: crida la mateixa comanda. No defineix `REDIS_URL` → no invalida la cache de producció ([GOTCHAS #28](../GOTCHAS.md)).

## Opció B — Manual en local
```bash
# amb DATABASE_URL_APP (Postgres local) i migracions aplicades (vegeu local-setup.md)
python manage.py process_yesterday_visits
```
O bé `run_process_visits.sh` / `run_process_visits.bat`, que exporten variables i criden la comanda. Porten **placeholders**: substitueix-los només en local i **no** facis commit amb valors reals.

Sortida esperada:
```
Visites d'ahir processades correctament
Visites processades: N
Visites buides eliminades: N
Refugis actualitzats: N
Total visitants afegits: N
Visites antigues purgades: N
```
(Només PostgreSQL: en local calen `DATABASE_URL_APP`, GDAL i les migracions aplicades.)

**Codi de sortida (D28)**: si el procés o la purga fallen, la comanda llança `CommandError` (missatge fix; la traça va al log) i surt amb **codi != 0**, de manera que el job de GitHub Actions queda en vermell. Abans imprimia l'error i sortia amb 0 **[FET]**.

## Opció C — django-crontab (inactiu)
`settings.CRONJOBS` declara `('0 3 * * *', ... process_yesterday_visits)`, però no s'instal·la enlloc (`build.sh` no ho fa). Si mai es volgués fer servir en un servidor propi:
```bash
python manage.py crontab add      # instal·la
python manage.py crontab show     # llista
python manage.py crontab remove   # treu
```
A Render no té efecte (no hi ha cron del sistema) **[INFERÈNCIA]**.

## Notes
- Només processa **ahir**: si un dia falla, aquell dia no es reprocessa automàticament.
- Els visitats no es dupliquen a `user_visited_refuges` (`ON CONFLICT DO NOTHING`, conserva el `created_at` original); reexecutar el mateix dia és segur.
