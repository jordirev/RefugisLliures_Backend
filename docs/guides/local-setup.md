# Guia — Posar en marxa el backend en local

> **[FET]** comprovat al codi · **[INFERÈNCIA]** deducció · **[NO VERIFICAT]** depèn de config externa.
> Context: [ARCHITECTURE §1](../ARCHITECTURE.md) (stack) · [integrations/render-deploy-ci.md](../integrations/render-deploy-ci.md) (selecció d'entorn).

## Requisits
- **Python ≥ 3.9** (`zoneinfo`, `api/utils/timezone_utils.py:5`); CI fa servir 3.10 (`.github/workflows/django.yml:16`) **[FET]**.
- **Redis** local a `redis://localhost:6379/1` (o `REDIS_URL`). Sense Redis l'API funciona però sense cache (errors empassats) — vegeu [redis-cache](../integrations/redis-cache.md).
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
| `env/.env.development` | `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `CORS_ALLOW_ALL_ORIGINS`, `CORS_ALLOWED_ORIGINS`, `GOOGLE_APPLICATION_CREDENTIALS`, `REDIS_URL` |
| `env/firebase-service-account.json` | Service account de Firebase. **Ruta fixa** que fa servir `api/firebase_config.py` en local |

Detall de credencials de Firebase: [firebase-credentials.md](firebase-credentials.md).

> ⚠️ No llegeixis ni comparteixis els valors de `env/`. No es versiona mai.

## 3. Exportar les variables R2
Les `R2_*` es llegeixen amb `os.getenv` i **no** entren a `os.environ` des dels `.env` ([GOTCHAS #25](../GOTCHAS.md)). Exporta-les a la shell:
```bash
export R2_ACCESS_KEY_ID=...  R2_SECRET_ACCESS_KEY=...  R2_ENDPOINT=...  R2_BUCKET_NAME=...
```
```powershell
$env:R2_ACCESS_KEY_ID="..."; $env:R2_SECRET_ACCESS_KEY="..."; $env:R2_ENDPOINT="..."; $env:R2_BUCKET_NAME="..."
```
Sense elles, qualsevol controller que creï `R2MediaService` (incloent el health check) falla.

## 4. Migracions (només apps internes de Django)
```bash
python manage.py migrate
```
Cap model de domini és un model Django; això només crea les taules d'admin/sessions a `db.sqlite3` **[FET]**.

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
- API: `http://127.0.0.1:8000/api/` · Health: `/api/health/`
- Swagger: `/swagger/` · ReDoc: `/redoc/`
- Per provar endpoints autenticats: [client-auth-usage.md](client-auth-usage.md).

## Problemes habituals
| Símptoma | Causa probable |
|---|---|
| `R2 configuration is incomplete` | Variables `R2_*` no exportades (pas 3) |
| `FileNotFoundError ... firebase-service-account.json` | Falta el fitxer de la ruta fixa (pas 2) |
| Respostes lentes i cap clau a Redis | Redis no arrencat; la cache falla en silenci |
| Health check 503 | Firestore inaccessible **o** config R2 absent ([flux 11](../flows/11-admin-cache-health.md)) |
