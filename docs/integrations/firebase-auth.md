# Integració — Firebase Admin SDK / Firebase Auth

> **[FET]** comprovat al codi · **[INFERÈNCIA]** deducció · **[NO VERIFICAT]** depèn de config externa.

## Què fa
- Verifica els **ID tokens** que envia el client (`Authorization: Bearer`).
- Llegeix els **custom claims** per decidir qui és admin (`role == 'admin'`).
- Gestiona els claims d'admin amb un script local.
- **No** crea ni esborra comptes d'Auth (cap `auth.create_user`/`auth.delete_user` a `api/`) **[FET]**.

## Fitxers
| Fitxer | Rol |
|---|---|
| `api/apps.py:8-14` | `ApiConfig.ready()` crida `initialize_firebase()` en arrencar Django |
| `api/firebase_config.py` | Inicialització per entorn |
| `api/services/firestore_service.py:40-75` | **Segona** ruta d'inicialització (si `get_app()` falla) |
| `api/middleware/firebase_auth_middleware.py` | `auth.verify_id_token` per petició |
| `api/authentication.py` | Classe d'autenticació DRF (reaprofita el middleware) |
| `api/permissions.py:10-21,86-101` | `is_firebase_admin`, `IsFirebaseAdmin` |
| `scripts/manage_admins.py` | Afegir/treure/consultar/llistar admins via custom claims |

## Inicialització (`api/firebase_config.py:80-106`)
| Entorn (detecció) | Credencials | Línies |
|---|---|---|
| Tests: `'pytest' in sys.modules` o `TESTING=true` | **No s'inicialitza** | L15-17, L92-94 |
| Producció: `RENDER=='true'` o `PRODUCTION=='true'` o `CI=='true'` | JSON a la variable `FIREBASE_SERVICE_ACCOUNT_KEY` | L24-47 |
| Local (resta) | `load_dotenv(env/.env.development)` + fitxer fix `env/firebase-service-account.json` | L50-77 |

`FirestoreService._initialize_firebase` (fallback) usa `settings.FIREBASE_SERVICE_ACCOUNT_KEY` o `settings.GOOGLE_APPLICATION_CREDENTIALS` (default `env/firebase-service-account.json`, `refugis_lliures/settings.py:173-174`) **[FET]**.

Variables (només noms): `FIREBASE_SERVICE_ACCOUNT_KEY`, `GOOGLE_APPLICATION_CREDENTIALS`, `RENDER`, `PRODUCTION`, `CI`, `TESTING`. Fitxers presents a `env/` (no versionats): `firebase-service-account.json`, `firebase-service-account-dev.json`, `firebase-service-account-prod.json`. Quin projecte Firebase apunta cadascun: **[NO VERIFICAT]** (no s'han llegit els valors).

## Custom claims
- Admin ⇔ `decoded_token['role'] == 'admin'` (`api/permissions.py:21`) **[FET]**.
- `scripts/manage_admins.py`: `add_admin` posa `role='admin'` (L27-36), `remove_admin` elimina `role` (L49-58), `check_admin`, `list_users` (L71-117). Ús per línia d'ordres (`sys.argv`, L127-148).
- Els claims nous **només arriben al backend quan el client refresca el token** **[INFERÈNCIA, comportament estàndard de Firebase]**.

## Flux
Vegeu [flows/00-auth-request-pipeline.md](../flows/00-auth-request-pipeline.md).

## Gotchas
- `render.yaml` posa `RENDER="1"` però `firebase_config` compara amb `'true'`; si Render no el sobreescriu, s'aniria a la ruta local i petaria per falta del fitxer **[NO VERIFICAT]**.
- `settings.py` considera producció només `RENDER`/`PRODUCTION` (`refugis_lliures/settings.py:21`), però `firebase_config` també `CI` → a GitHub Actions CI els settings carreguen `.env.development` mentre Firebase espera `FIREBASE_SERVICE_ACCOUNT_KEY` (als tests no importa perquè no s'inicialitza) **[FET]**.
- `verify_id_token` sense `check_revoked=True`: un token revocat continua sent vàlid fins que caduca (≈1 h) **[INFERÈNCIA sobre l'SDK]**.
- Dues rutes d'inicialització amb criteris diferents → possible confusió de credencials **[FET]**.
- Versions antigues de la documentació parlaven de `admin: true` o de `FIREBASE_ADMIN_UIDS`: **obsolet** ([design/decisions.md ADR-3](../design/decisions.md)).

## Guies relacionades
[firebase-credentials.md](../guides/firebase-credentials.md) (configurar el service account) · [admin-management.md](../guides/admin-management.md) (fer/treure admins) · [client-auth-usage.md](../guides/client-auth-usage.md) (enviar el token des del client).
