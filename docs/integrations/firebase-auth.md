# Integració — Firebase Admin SDK / Firebase Auth

> **[FET]** comprovat al codi · **[INFERÈNCIA]** deducció · **[NO VERIFICAT]** depèn de config externa.

## Què fa
- Verifica els **ID tokens** que envia el client (`Authorization: Bearer`).
- Llegeix els **custom claims** per decidir qui és admin (`role == 'admin'`).
- Gestiona els claims d'admin amb un script local.
- **No** crea comptes d'Auth (els crea el client). **Sí que els esborra**: `apps.accounts.services.delete_user` crida `auth.delete_user(uid)` com a últim pas de `DELETE /users/{uid}/`, **després del `COMMIT`** de l'esborrat de dades (D42; `UserNotFoundError` = èxit; si falla, 500 i el client reintenta el `DELETE`, que dóna 204), i `create_user` crida `auth.get_user(uid)` per rebutjar (401 `account_not_found`) un `POST /users/` amb el token d'un compte ja esborrat (U7) **[FET]**. Als tests, el `conftest.py` arrel mocka totes dues crides (fixture autouse `firebase_accounts`).

## Fitxers
| Fitxer | Rol |
|---|---|
| `api/apps.py` | `ApiConfig.ready()` instal·la el hook de RLS (`api/rls_hook.py`) i crida `initialize_firebase()` en arrencar Django |
| `api/firebase_config.py` | Inicialització per entorn |
| `api/services/firestore_service.py:40-75` | **Segona** ruta d'inicialització (si `get_app()` falla) |
| `api/middleware/firebase_auth_middleware.py` | `auth.verify_id_token` per petició |
| `api/authentication.py` | Classe d'autenticació DRF (reaprofita el middleware) |
| `api/rls_hook.py` | Llegeix `uid` i `role == 'admin'` de la identitat verificada i fixa el context de RLS a la transacció ([flux 00](../flows/00-auth-request-pipeline.md)) |
| `api/permissions.py:10-21,86-101` | `is_firebase_admin`, `IsFirebaseAdmin` |
| `scripts/manage_admins.py` | Afegir/treure/consultar/llistar admins via custom claims |

## Inicialització (`api/firebase_config.py:80-106`)
| Entorn (detecció) | Credencials | Línies |
|---|---|---|
| Tests: `'pytest' in sys.modules` o `TESTING=true` | **No s'inicialitza** | L15-17, L92-94 |
| **Firebase Auth Emulator**: `FIREBASE_AUTH_EMULATOR_HOST` definida (té prioritat sobre la resta, excepte tests) | Cap credencial: només un `projectId` | vegeu «Firebase Auth Emulator» |
| Producció: `RENDER=='true'` o `PRODUCTION=='true'` o `CI=='true'` | JSON a la variable `FIREBASE_SERVICE_ACCOUNT_KEY` | L24-47 |
| Local (resta) | `load_dotenv(env/.env.development)` + fitxer fix `env/firebase-service-account.json` | L50-77 |

`FirestoreService._initialize_firebase` (fallback) usa `settings.FIREBASE_SERVICE_ACCOUNT_KEY` o `settings.GOOGLE_APPLICATION_CREDENTIALS` (default `env/firebase-service-account.json`, `refugis_lliures/settings.py:173-174`) **[FET]**.

Variables (només noms): `FIREBASE_SERVICE_ACCOUNT_KEY`, `GOOGLE_APPLICATION_CREDENTIALS`, `RENDER`, `PRODUCTION`, `CI`, `TESTING`. Fitxers presents a `env/` (no versionats): `firebase-service-account.json`, `firebase-service-account-dev.json`, `firebase-service-account-prod.json`. Quin projecte Firebase apunta cadascun: **[NO VERIFICAT]** (no s'han llegit els valors).

## Firebase Auth Emulator (e2e locals) [FET]
- Amb `FIREBASE_AUTH_EMULATOR_HOST` (p. ex. `localhost:9099`) `initialize_firebase()` crida `firebase_admin.initialize_app(options={'projectId': ...})` **sense service account** (`_initialize_firebase_emulator`, `api/firebase_config.py`). El `projectId` ve de `GCLOUD_PROJECT`, si no de `GOOGLE_CLOUD_PROJECT`, si no `demo-refugis-lliures`. L'SDK detecta la variable i verifica els tokens contra l'emulador (sense signatura).
- **Guarda (`_initialize_firebase_emulator`)** **[FET]**: l'emulador accepta tokens sense signatura (qui en controli el host pot fer-se passar per qualsevol usuari, admin inclòs), així que `initialize_firebase()` **llança `ValueError` i Django no arrenca** (`ApiConfig.ready`) si:
  - s'executa en una plataforma gestionada: `RENDER`, `PRODUCTION` (booleans `true`/`1`/`yes`/`on`, sense distingir majúscules) o qualsevol de `K_SERVICE`, `K_REVISION` (Cloud Run), `CLOUD_RUN_JOB`, `RENDER_SERVICE_ID` (només cal que estiguin definides); o
  - el host de `FIREBASE_AUTH_EMULATOR_HOST` no és local: només `localhost`, `127.0.0.1`, `::1` o `host.docker.internal` (admet `host:port`, `[::1]:9099` i URLs amb esquema).
  `CI=true` **no** bloqueja l'emulador (els e2e poden córrer-hi) **[FET]**. Tests: `api/tests/security/test_security_emulator_guard.py`. Tot i la guarda, no definiu mai `FIREBASE_AUTH_EMULATOR_HOST` a Render, Cloud Run ni Actions.
- Els tests continuen sense inicialitzar Firebase (`TESTING`/`pytest`) encara que la variable existeixi.
- Els e2e locals (`scripts/e2e/`, orquestrador) usen aquest emulador amb tokens d'usuari normal i d'admin (claim `role: 'admin'`); com es creen és responsabilitat d'aquells scripts **[NO VERIFICAT]**.

## Custom claims
- Admin ⇔ `decoded_token['role'] == 'admin'` (`api/permissions.py:21`) **[FET]**. El mateix criteri (només el claim verificat, igualtat exacta) alimenta `app.is_admin` de la RLS (`api/rls_hook.py: is_admin_claims`) **[FET]**.
- `scripts/manage_admins.py`: `add_admin` posa `role='admin'` (L27-36), `remove_admin` elimina `role` (L49-58), `check_admin`, `list_users` (L71-117). Ús per línia d'ordres (`sys.argv`, L127-148).
- Els claims nous **només arriben al backend quan el client refresca el token** **[INFERÈNCIA, comportament estàndard de Firebase]**.

## Flux
Vegeu [flows/00-auth-request-pipeline.md](../flows/00-auth-request-pipeline.md).

## Gotchas
- `render.yaml` posa `RENDER="1"` però `firebase_config` compara amb `'true'`; si Render no el sobreescriu, s'aniria a la ruta local i petaria per falta del fitxer **[NO VERIFICAT]**.
- `_is_render_environment` i `_is_production_environment` ara interpreten `RENDER`/`PRODUCTION`/`CI` com a booleans (`true`, `1`, `yes`, `on`), de manera que el `RENDER="1"` de `render.yaml` ja compta com a Render **[FET]** (això matisa el primer gotcha d'aquesta llista).
- `settings.py` considera producció només `RENDER`/`PRODUCTION` (`refugis_lliures/settings.py:21`), però `firebase_config` també `CI` → a GitHub Actions CI els settings carreguen `.env.development` mentre Firebase espera `FIREBASE_SERVICE_ACCOUNT_KEY` (als tests no importa perquè no s'inicialitza) **[FET]**.
- `verify_id_token` sense `check_revoked=True`: un token revocat continua sent vàlid fins que caduca (≈1 h) **[INFERÈNCIA sobre l'SDK]**.
- Dues rutes d'inicialització amb criteris diferents → possible confusió de credencials **[FET]**.
- Versions antigues de la documentació parlaven de `admin: true` o de `FIREBASE_ADMIN_UIDS`: **obsolet** ([design/decisions.md ADR-3](../design/decisions.md)).

## Guies relacionades
[firebase-credentials.md](../guides/firebase-credentials.md) (configurar el service account) · [admin-management.md](../guides/admin-management.md) (fer/treure admins) · [client-auth-usage.md](../guides/client-auth-usage.md) (enviar el token des del client).

## Edat i bloqueig (feature images) [FET]
No són custom claims: l'edat confirmada (`age_confirmed_at`) i el bloqueig (`is_blocked`) viuen a `users.users` de PostgreSQL (chunk 3) i els comproven `IsAgeConfirmed` / `IsNotBlocked`; tot endpoint autenticat exigeix a més fila a `users.users` (`HasProfile`, 403 `profile_required`) ([flux 12](../flows/12-media-moderation.md), [flux 1](../flows/01-user-profile.md)). El backend no deshabilita el compte de Firebase Auth en bloquejar un usuari.
