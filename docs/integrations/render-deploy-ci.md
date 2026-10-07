# Integració — Render, GitHub Actions, SonarCloud i Codecov

> **[FET]** comprovat al codi · **[INFERÈNCIA]** deducció · **[NO VERIFICAT]** depèn de config externa.

## Render (`render.yaml`)
- Servei web `refugis-lliures-backend`, `env: python` (L1-4).
- Build: `./build.sh` → `pip install -r requirements.txt` + `python manage.py collectstatic --no-input` (`build.sh`). **No** executa migracions ni `crontab add` **[FET]**.
- Start: `gunicorn --config=gunicorn.conf.py refugis_lliures.wsgi:application` (L6).
- Variables definides al YAML: `RENDER="1"`, `DJANGO_SETTINGS_MODULE` (L7-11). La resta (comentades a L12-22) es configuren al dashboard → **[NO VERIFICAT]**: `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `CORS_*`, `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `GOOGLE_APPLICATION_CREDENTIALS`; a més el codi necessita `FIREBASE_SERVICE_ACCOUNT_KEY`, `REDIS_URL` i `R2_*`.
- URL pública: `https://refugislliures-backend.onrender.com` (segons `.github/workflows/ping-website.yml:16-17`) **[FET]**.

## Gunicorn (`gunicorn.conf.py`)
`bind 0.0.0.0:$PORT`, **1 worker** `sync`, `timeout 30`, `max_requests 1000` (+jitter 100), `preload_app=True`, logs a stdout/stderr (L7-37).

## Selecció d'entorn (`refugis_lliures/settings.py:20-34`)
Si existeix `RENDER` o `PRODUCTION` → `env/.env.production`; si no → `env/.env.development`; si el fitxer no existeix → `decouple.config` normal (variables d'entorn). A Render, `env/` no existeix (no versionat) → es llegeixen les variables d'entorn del servei **[INFERÈNCIA]**.

Variables (noms) a `env/.env.development` i `env/.env.production`: `SECRET_KEY, DEBUG, ALLOWED_HOSTS, CORS_ALLOW_ALL_ORIGINS, CORS_ALLOWED_ORIGINS, GOOGLE_APPLICATION_CREDENTIALS, REDIS_URL`. `env/api-keys.env` conté les mateixes claus i **cap fitxer del codi el referencia** **[FET]**.

## GitHub Actions (`.github/workflows/`)
| Workflow | Disparador | Què fa |
|---|---|---|
| `django.yml` | push/PR a `main`, `develop` | Python 3.10 → `pip install tox` → `tox -e py` (pytest + coverage XML) → Codecov (`CODECOV_TOKEN`) → SonarQube scan (`SONAR_TOKEN`) |
| `ping-website.yml` | cron `*/9 * * * *` + manual | `curl` a `/swagger/`; falla si no és 200/301/302 |
| `process-visits.yml` | cron `0 3 * * *` (UTC) + manual | `pip install -r requirements.txt` → `python manage.py process_yesterday_visits` amb secrets `R2_*`, `FIREBASE_SERVICE_ACCOUNT_KEY` i `PRODUCTION='true'` |

## SonarCloud (`sonar-project.properties`)
`projectKey=jordirev_RefugisLliures_Backend`, `organization=jordirev`, `sources=api`, coverage de `coverage.xml`. Exclou tests, settings, urls, `__init__`, i del coverage també `services/**` i `utils/**`.

## Tasques programades: què està actiu
| Mecanisme | Estat |
|---|---|
| GitHub Actions `process-visits.yml` | **Actiu** (és el mecanisme real) **[FET]**; execució correcta depèn dels secrets **[NO VERIFICAT]** |
| `CRONJOBS` amb django-crontab (`refugis_lliures/settings.py:275-278`) | Inactiu: ningú executa `manage.py crontab add` **[FET]** |
| `run_process_visits.sh` / `.bat` | Manual, amb placeholders |

## Gotchas
- `RENDER="1"` vs `RENDER=='true'` a `api/firebase_config.py:21,27` **[NO VERIFICAT]** si Render el sobreescriu.
- 1 worker sync + timeout 30 s + pujades sense límit → una pujada lenta bloqueja tot el servei **[INFERÈNCIA]**.
- `tox.ini` declara `py39` però CI executa `tox -e py` amb 3.10 **[FET]**.
- `process-visits.yml` no posa `REDIS_URL` → no invalida la cache de producció **[INFERÈNCIA]**.
- Comentari "3:00 Madrid" a `refugis_lliures/settings.py:276` vs "3:00 UTC" al workflow: el que s'executa és el del workflow (UTC) **[FET]**; com que el procés calcula "ahir" en hora de Madrid, a les 3:00 UTC (4-5 h a Madrid) "ahir" és correcte **[INFERÈNCIA]**.

## Guies relacionades
[firebase-credentials.md](../guides/firebase-credentials.md) · [r2-render-setup.md](../guides/r2-render-setup.md) · [daily-visits-process.md](../guides/daily-visits-process.md) · [testing.md](../guides/testing.md)
