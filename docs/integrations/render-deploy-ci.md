# Integració — Render, GitHub Actions, SonarCloud i Codecov

> **[FET]** comprovat al codi · **[INFERÈNCIA]** deducció · **[NO VERIFICAT]** depèn de config externa.

## Render (`render.yaml`)
- Servei web `refugis-lliures-backend`, `env: python` (L1-4).
- Build: `./build.sh` → `pip install -r requirements.txt` + `python manage.py collectstatic --no-input` (`build.sh`). **No** executa migracions ni `crontab add` **[FET]**.
- Start: `gunicorn --config=gunicorn.conf.py refugis_lliures.wsgi:application` (L6).
- Variables definides al YAML: `RENDER="1"`, `DJANGO_SETTINGS_MODULE` (L7-11). La resta (comentades a L12-22) es configuren al dashboard → **[NO VERIFICAT]**: `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `CORS_*`, `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `GOOGLE_APPLICATION_CREDENTIALS`; a més el codi necessita `FIREBASE_SERVICE_ACCOUNT_KEY` (només Auth) i `R2_*`. `REDIS_URL` ja no cal (D43).
- URL pública: `https://refugislliures-backend.onrender.com` (segons `.github/workflows/ping-website.yml:16-17`) **[FET]**.

## Gunicorn (`gunicorn.conf.py`)
`bind 0.0.0.0:$PORT`, **1 worker** `sync`, `timeout 30`, `max_requests 1000` (+jitter 100), `preload_app=True`, logs a stdout/stderr (L7-37).

## Selecció d'entorn (`refugis_lliures/settings.py:20-34`)
Si `RENDER` o `PRODUCTION` valen `true`/`1`/`yes`/`on` (sense distingir majúscules; `PRODUCTION=false` **no** compta, igual que a `firebase_config`) → `env/.env.production`; si no → `env/.env.development`; si el fitxer no existeix → `decouple.config` normal (variables d'entorn). A Render, `env/` no existeix (no versionat) → es llegeixen les variables d'entorn del servei **[INFERÈNCIA]**.

Variables (noms) a `env/.env.development` i `env/.env.production`: `SECRET_KEY, DEBUG, ALLOWED_HOSTS, CORS_ALLOW_ALL_ORIGINS, CORS_ALLOWED_ORIGINS, GOOGLE_APPLICATION_CREDENTIALS` (`REDIS_URL` ja no cal: eliminada al chunk 11). `env/api-keys.env` conté les mateixes claus i **cap fitxer del codi el referencia** **[FET]**.

## GitHub Actions (`.github/workflows/`)
| Workflow | Disparador | Què fa |
|---|---|---|
| `django.yml` | push/PR a `main`, `develop`, `migration` | Servei `postgis/postgis:18-3.6` → `apt-get install gdal-bin libgdal-dev postgresql-client` → Python 3.14 (`actions/setup-python@v5`) → `pip install tox` → *bootstrap* de la BD de proves (`scripts/dev/setup_local_postgres.sh`, amb `PGHOST=localhost`, `PG_START_CLUSTER=0`; exporta `TEST_DATABASE_URL_*` a `$GITHUB_ENV`) → `tox -e py` (pytest + coverage XML) → Codecov (`CODECOV_TOKEN`) → SonarQube scan (`SONAR_TOKEN`) |
| `ping-website.yml` | cron `*/9 * * * *` + manual | `curl` a `/swagger/`; falla si no és 200/301/302 |
| `process-visits.yml` | cron `0 3 * * *` (UTC) + manual | `pip install -r requirements.txt` → `python manage.py process_yesterday_visits` amb secrets `R2_*`, `FIREBASE_SERVICE_ACCOUNT_KEY` i `PRODUCTION='true'` |

### CI i PostgreSQL (migració, chunk 1) [FET]
- El servei de Postgres és efímer (contrasenya de superusuari només per a CI, no secreta) i de la **mateixa versió major que Neon (17)**. La Neon real **no** s'usa mai a CI.
- El *bootstrap* de la BD de proves escriu la sortida de l'script a un fitxer (`$RUNNER_TEMP/pg.env`) abans de fer `eval`, de manera que si falla **el pas falla en veu alta** (dins d'`eval "$(...)"` l'error s'ignoraria i els tests caurien a SQLite sense avisar), i després comprova que `TEST_DATABASE_URL_APP` i `TEST_DATABASE_URL_MIGRATOR` no són buides **[FET]**.
- GDAL/GEOS són necessaris perquè `django.contrib.gis` sempre és actiu (vegeu [neon.md](neon.md)).
- `tox.ini` té `passenv = TEST_DATABASE_URL_APP, TEST_DATABASE_URL_MIGRATOR`: sense això tox no hi passaria les variables i els tests de BD se saltarien/fallarien.
- La branca d'integració `migration` és als dos disparadors (`push` i `pull_request`) perquè les PR de cada chunk (`migracio/<chunk>` → `migration`) passin la CI.

## SonarCloud (`sonar-project.properties`)
`projectKey=jordirev_RefugisLliures_Backend`, `organization=jordirev`, `sources=api,apps`, coverage de `coverage.xml` (tox: `--cov=api --cov=apps`; `.coveragerc` també amb `source = api, apps`). Exclou tests, settings, urls, `__init__`, i del coverage també `services/**` i `utils/**`.

## Tasques programades: què està actiu
| Mecanisme | Estat |
|---|---|
| GitHub Actions `process-visits.yml` | **Actiu** (és el mecanisme real) **[FET]**; execució correcta depèn dels secrets **[NO VERIFICAT]** |
| `CRONJOBS` amb django-crontab (`refugis_lliures/settings.py:275-278`) | Inactiu: ningú executa `manage.py crontab add` **[FET]** |
| `run_process_visits.sh` / `.bat` | Manual, amb placeholders |

## Dependències de mitjans (feature images) [FET]
`requirements.txt` afegeix `Pillow`, `pillow-heif`, `imageio-ffmpeg` (porta el binari estàtic d'ffmpeg, ~70 MB; no cal apt), `ImageHash` (numpy/scipy/PyWavelets) i `blurhash` (pur Python). El build de Render les instal·la amb `build.sh`. El processament d'imatges/vídeos és síncron i usa ~50–100 MB de RAM per imatge **[INFERÈNCIA]**: vigila la memòria del pla de Render. CI (Python 3.10) executa també els tests reals amb ffmpeg.

## Gotchas
- `RENDER="1"` vs `RENDER=='true'` a `apps/auth/firebase_config.py:21,27` **[NO VERIFICAT]** si Render el sobreescriu.
- 1 worker sync + timeout 30 s + pujades sense límit → una pujada lenta bloqueja tot el servei **[INFERÈNCIA]**.
- `tox.ini` declara `py314` i CI executa `tox -e py` amb Python 3.14 **[FET]**; `process-visits.yml` també fixa 3.14. `.python-version` (`3.14`) fixa la versió de Python de Render **[INFERÈNCIA: Render llegeix `.python-version`]**. Els tests locals en contenidor i l'entorn `.venv` també són 3.14 ([guides/testing.md](../guides/testing.md)).
- Comentari "3:00 Madrid" a `refugis_lliures/settings.py:276` vs "3:00 UTC" al workflow: el que s'executa és el del workflow (UTC) **[FET]**; com que el procés calcula "ahir" en hora de Madrid, a les 3:00 UTC (4-5 h a Madrid) "ahir" és correcte **[INFERÈNCIA]**.

## Neon (variables d'entorn) [FET]
`DATABASE_URL_APP` (rol `app`, pooler), `DATABASE_URL_MIGRATOR` (rol `migrator`, directa) i `NEON_BRANCH`. Es llegeixen de `env/.env.*` (o de l'entorn) amb `decouple`; `TEST_DATABASE_URL_APP` / `TEST_DATABASE_URL_MIGRATOR` (Postgres de proves) tenen prioritat només dins pytest o amb `USE_TEST_DATABASE=1` (D37). `default` és Postgres si hi ha alguna URL `app`; l'àlies `migrator` només existeix si hi ha la URL del migrator. CI defineix només les `TEST_*` (cap secret). `NEON_USE_POSTGIS_ENGINE` ja no existeix. Detall: [neon.md](neon.md).

**Pendent de desplegament [NO VERIFICAT]**: ni `build.sh` ni `render.yaml` instal·len GDAL/GEOS ni defineixen `DATABASE_URL_APP`; amb `django.contrib.gis` sempre actiu, un desplegament a Render sense GDAL no arrencaria. El PO ha decidit (30/10/2026) desplegar a **Cloud Run o Oracle**, no a Render: GDAL/GEOS entren al Dockerfile del nou entorn i Render deixa de ser el destí. El desplegament queda fora del chunk 1 ([TECH_DEBT.md](../TECH_DEBT.md) P1). Les migracions no s'executen al build: `python manage.py migrate --database=migrator`.

## Accions pendents del PO (neteja, chunk 11, D43)
El codi ja no usa Redis ni Firestore; aquestes accions són a la consola/dashboard i no es poden fer des del codi:
1. **Render**: eliminar la variable `REDIS_URL` i l'add-on/instància de Redis, si n'hi ha. **Fet pel PO el 30/10/2026.**
2. **Firebase Console**: quan es consideri oportú (després de validar la migració), esborrar les dades de Firestore (col·leccions antigues). Només després d'una còpia si es vol conservar l'històric. **Fet pel PO el 30/10/2026.**
3. **Mantenir** les credencials de Firebase Auth (`FIREBASE_SERVICE_ACCOUNT_KEY`, o el fitxer local): `firebase-admin` encara verifica tokens i gestiona usuaris i claims.

## Guies relacionades
[firebase-credentials.md](../guides/firebase-credentials.md) · [r2-render-setup.md](../guides/r2-render-setup.md) · [daily-visits-process.md](../guides/daily-visits-process.md) · [testing.md](../guides/testing.md)
