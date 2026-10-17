# Guia — Executar el procés diari de visites

> **[FET]** comprovat al codi · **[INFERÈNCIA]** deducció · **[NO VERIFICAT]** depèn de config externa.
> Què fa el procés i els seus bugs: [flux 6](../flows/06-refuge-visits.md). On s'executa: [render-deploy-ci §Tasques programades](../integrations/render-deploy-ci.md#tasques-programades-què-està-actiu).

`process_yesterday_visits` agafa les visites d'**ahir** (hora de Madrid): esborra les buides i afegeix els visitants a `visitors` del refugi i a `visited_refuges` de cada usuari. Les visites amb visitants **no** s'esborren.

## Opció A — GitHub Actions (mecanisme real)
- Workflow `.github/workflows/process-visits.yml`, cron `0 3 * * *` (UTC).
- Execució manual: GitHub → **Actions** → *Process Yesterday Visits* → **Run workflow** (`workflow_dispatch`).
- Secrets necessaris: `FIREBASE_SERVICE_ACCOUNT_KEY`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_ENDPOINT`, `R2_BUCKET_NAME`. No defineix `REDIS_URL` → no invalida la cache de producció ([GOTCHAS #28](../GOTCHAS.md)).

## Opció B — Manual en local
```bash
# amb credencials locals de Firebase i R2 exportades (vegeu local-setup.md)
python manage.py process_yesterday_visits
```
O bé `run_process_visits.sh` / `run_process_visits.bat`, que exporten `R2_*` i criden la comanda. Porten **placeholders**: substitueix-los només en local i **no** facis commit amb valors reals.

Sortida esperada:
```
Visites d'ahir processades correctament
Visites processades: N
Visites buides eliminades: N
Refugis actualitzats: N
Total visitants afegits: N
```

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
- Els UIDs no es dupliquen a `visitors` del refugi (unió de conjunts).
