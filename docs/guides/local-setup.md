# Guia — Posar en marxa el backend en local

> **[FET]** comprovat al codi · **[INFERÈNCIA]** deducció · **[NO VERIFICAT]** depèn de config externa.
> Context: [ARCHITECTURE §1](../ARCHITECTURE.md) (stack) · [integrations/render-deploy-ci.md](../integrations/render-deploy-ci.md) (selecció d'entorn).

## Requisits
- **Python ≥ 3.9** (`zoneinfo`, `api/utils/timezone_utils.py:5`); CI fa servir 3.10 (`.github/workflows/django.yml:16`) **[FET]**.
- **Redis** local a `redis://localhost:6379/1` (o `REDIS_URL`). Sense Redis l'API funciona però sense cache (errors empassats) — vegeu [redis-cache](../integrations/redis-cache.md).
- **PostgreSQL + PostGIS** (rol `app` i rol `migrator`): és la BD `default` de Django des del chunk 1 de la migració ([integrations/neon.md](../integrations/neon.md)). En local: el Postgres de proves de `scripts/dev/setup_local_postgres.sh` o Neon `dev` (variables `DATABASE_URL_APP` / `DATABASE_URL_MIGRATOR`). Sense cap URL, Django cau a SQLite i les peticions reals no funcionen **[FET]**.
- **GDAL/GEOS/PROJ** del sistema (`django.contrib.gis` sempre és actiu): `apt install gdal-bin libgdal-dev libgeos-dev libproj-dev` a Linux; **a Windows no n'hi ha de natiu** → vegeu «Windows: executar en un contenidor Linux» més avall **[FET]**.
- Accés a un projecte **Firebase** (service account) i a un bucket **Cloudflare R2**.

## 1. Clonar i crear l'entorn virtual
```bash
git clone https://github.com/jordirev/RefugisLliures_Backend.git
cd RefugisLliures_Backend

python -m venv venv
# Linux/macOS
source venv/bin/activate
# Windows
venv\Scripts\activate

pip install -r requirements.txt     # inclou pytest, coverage, boto3, django-redis
```

## 2. Configurar `env/` (no versionat)
`refugis_lliures/settings.py:20-34` llegeix `env/.env.development` (o `env/.env.production` si existeix `RENDER`/`PRODUCTION`) amb `decouple` **[FET]**.

| Fitxer | Contingut (només noms) |
|---|---|
| `env/.env.development` | `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `CORS_ALLOW_ALL_ORIGINS`, `CORS_ALLOWED_ORIGINS`, `GOOGLE_APPLICATION_CREDENTIALS`, `REDIS_URL`, `DATABASE_URL_APP`, `DATABASE_URL_MIGRATOR` (i, per a proves locals, `TEST_DATABASE_URL_APP`, `TEST_DATABASE_URL_MIGRATOR`) |
| `env/firebase-service-account.json` | Service account de Firebase. **Ruta fixa** que fa servir `api/firebase_config.py` en local |

Detall de credencials de Firebase: [firebase-credentials.md](firebase-credentials.md).

> ⚠️ No llegeixis ni comparteixis els valors de `env/`. No es versiona mai.

### PostgreSQL (migració en curs) [FET]
`settings.py` construeix `DATABASES['default']` (rol `app`, `ATOMIC_REQUESTS=True`) amb la primera variable definida entre `TEST_DATABASE_URL_APP` i `DATABASE_URL_APP`, i `DATABASES['migrator']` amb `TEST_DATABASE_URL_MIGRATOR` / `DATABASE_URL_MIGRATOR`. Les `TEST_*` tenen prioritat: si les tens definides, **les proves i el `runserver` van al Postgres local, no a Neon**. Hosts no locals reben `sslmode=require` automàticament. Detall: [neon.md](../integrations/neon.md). Verifica amb `python manage.py check_neon --alias default` (i `--alias migrator`). Requereix Node ≥ 22.20 per al CLI de Neon.

**Postgres local de proves** (Linux/macOS amb clúster apt o servei Docker):
```bash
eval "$(scripts/dev/setup_local_postgres.sh | grep ^export)"   # exporta TEST_DATABASE_URL_MIGRATOR / TEST_DATABASE_URL_APP
```
Crea els rols `migrator` i `app`, la BD `refugisdb_test`, les extensions i `GRANT CREATE ON SCHEMA public TO migrator` (PG15+). Amb un Postgres en Docker o remot: `PGHOST=... PG_START_CLUSTER=0 PGPASSWORD=<superusuari> scripts/dev/setup_local_postgres.sh`. Les contrasenyes que fixa l'script són d'ús exclusivament local.

**Windows: executar en un contenidor Linux** (no hi ha GDAL natiu) **[FET: és com s'han executat els tests del chunk 1]**. Un `Dockerfile` (fora del repo, p. ex. `rl-backend-tests.Dockerfile`):
```dockerfile
FROM python:3.13-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential gdal-bin libgdal-dev libgeos-dev libproj-dev postgresql-client \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
```
```powershell
# 1) Postgres + PostGIS 17 (mateixa versió major que Neon i que CI)
docker run -d --name rl-postgres -e POSTGRES_PASSWORD=<contrasenya-local> -p 5432:5432 postgis/postgis:17-3.5
# 2) Imatge amb GDAL (el requirements.txt s'instal·la a la imatge; el repo es munta a /app)
docker build -t rl-backend -f rl-backend-tests.Dockerfile .
# 3) Bootstrap + comanda dins del contenidor (apunta al Postgres del host)
docker run --rm -v "${PWD}:/app" -w /app --add-host=host.docker.internal:host-gateway `
  -e PGHOST=host.docker.internal -e PG_START_CLUSTER=0 -e PGPASSWORD=<contrasenya-local> rl-backend `
  bash -c 'eval "$(scripts/dev/setup_local_postgres.sh | grep ^export)" && python manage.py migrate --database=migrator'
```
Alternativa: defineix `TEST_DATABASE_URL_APP` i `TEST_DATABASE_URL_MIGRATOR` a `env/.env.development` (amb host `host.docker.internal`, que `settings.py` tracta com a local: sense `sslmode`) i el contenidor les llegirà del repo muntat. No imprimeixis ni comparteixis aquests valors. Per als tests, vegeu [testing.md](testing.md).

## 3. Exportar les variables R2
Les `R2_*` es llegeixen amb `os.getenv` i **no** entren a `os.environ` des dels `.env` ([GOTCHAS #25](../GOTCHAS.md)). Exporta-les a la shell:
```bash
export R2_ACCESS_KEY_ID=...  R2_SECRET_ACCESS_KEY=...  R2_ENDPOINT=...  R2_BUCKET_NAME=...
```
```powershell
$env:R2_ACCESS_KEY_ID="..."; $env:R2_SECRET_ACCESS_KEY="..."; $env:R2_ENDPOINT="..."; $env:R2_BUCKET_NAME="..."
```
Sense elles, qualsevol controller que creï `R2MediaService` falla. El health check ja **no** en depèn (el client R2 de `RefugiLliureController` es crea sota demanda) **[FET]**.

## 4. Migracions (sempre amb el rol `migrator`)
```bash
python manage.py migrate --database=migrator
```
El rol `app` (BD `default`) no té permisos de DDL: un `migrate` sense `--database=migrator` fallaria. Crea els schemas i les funcions de `domain/core` (`core.0001`) i les taules internes de Django a `public` (propietat del migrator). Cap model de domini és encara un model Django (el domini continua a Firestore fins als chunks següents) **[FET]**. Cal el *bootstrap* previ del propietari de la BD ([neon.md](../integrations/neon.md)). Sense Postgres configurat només s'afectaria `db.sqlite3`.

## 5. Dades inicials a Firestore (només si la BD és nova)
```bash
python manage.py upload_refugis_to_firestore     # UNA sola vegada (avís a l'inici del fitxer)
python manage.py extract_coords_to_firestore     # construeix coords_refugis/all_refugis_coords
python manage.py assign_conditions               # condició inicial a partir d'info_comp
```
Vegeu [integrations/firestore.md §Seeding](../integrations/firestore.md#dades-inicials-seeding).

## 6. Arrencar
```bash
python manage.py runserver
```
- API: `http://127.0.0.1:8000/api/` · Health: `/api/health/` (comprova Postgres, Firebase i Firestore; retorna 503 si algun falla)
- Per provar amb tokens sense un projecte Firebase real: Firebase Auth Emulator amb `FIREBASE_AUTH_EMULATOR_HOST` ([firebase-auth.md](../integrations/firebase-auth.md)); mai en producció.
- Swagger: `/swagger/` · ReDoc: `/redoc/`
- Per provar endpoints autenticats: [client-auth-usage.md](client-auth-usage.md).

## Problemes habituals
| Símptoma | Causa probable |
|---|---|
| `R2 configuration is incomplete` | Variables `R2_*` no exportades (pas 3) |
| `FileNotFoundError ... firebase-service-account.json` | Falta el fitxer de la ruta fixa (pas 2) |
| Respostes lentes i cap clau a Redis | Redis no arrencat; la cache falla en silenci |
| Health check 503 | Postgres inaccessible (`database: false`) **o** Firestore inaccessible ([flux 11](../flows/11-admin-cache-health.md)); la config R2 ja no hi influeix |
| `ImproperlyConfigured: Could not find the GDAL library` (o GEOS) | Falta GDAL/GEOS al sistema (Windows natiu): executa en un contenidor Linux (§ PostgreSQL) |
| `permission denied for schema public` en migrar | Falta `GRANT CREATE ON SCHEMA public TO migrator` (PG15+) al *bootstrap* |
| `permission denied` / `must be owner` amb `migrate` | S'ha usat el rol `app`: torna a executar amb `--database=migrator` |
| `OperationalError` a Postgres sense haver definit URL | Cap `DATABASE_URL_APP`/`TEST_DATABASE_URL_APP` → `default` és SQLite |
