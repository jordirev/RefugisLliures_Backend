# Guia — Configurar les credencials de Firebase

> **[FET]** comprovat al codi · **[INFERÈNCIA]** deducció · **[NO VERIFICAT]** depèn de config externa.
> Com funciona per dins (detecció d'entorn, doble ruta d'inicialització): [integrations/firebase-auth.md](../integrations/firebase-auth.md).

El backend necessita un **service account** de Firebase per verificar tokens i accedir a Firestore. `api/firebase_config.py` tria d'on llegir-lo segons l'entorn:

| Entorn | Es detecta si… | D'on llegeix les credencials |
|---|---|---|
| Tests | `pytest` importat o `TESTING=true` | No s'inicialitza Firebase |
| Producció / CI | `RENDER=='true'`, `PRODUCTION=='true'` o `CI=='true'` | Variable `FIREBASE_SERVICE_ACCOUNT_KEY` (JSON complet) |
| Local | la resta | Fitxer **fix** `env/firebase-service-account.json` (+ `load_dotenv(env/.env.development)`) |

## Local (desenvolupament)
1. Firebase Console → *Project settings* → *Service accounts* → **Generate new private key**.
2. Desa el JSON com a `env/firebase-service-account.json` (la ruta és fixa a `api/firebase_config.py`; el nom no es pot canviar per variable).
3. Opcional: a `env/` també hi poden conviure `firebase-service-account-dev.json` / `-prod.json`; només el fitxer anterior el llegeix `firebase_config` **[FET]**. `GOOGLE_APPLICATION_CREDENTIALS` només el fa servir la ruta de fallback de `FirestoreService` i `scripts/manage_admins.py`.
4. Arrenca el servidor: el log mostra `🏠 Entorn: LOCAL` i el `project_id`.

## Producció (Render) i GitHub Actions
1. Copia **tot** el contingut del JSON del service account.
2. Render → servei → **Environment** → afegeix `FIREBASE_SERVICE_ACCOUNT_KEY` amb el JSON com a valor (una sola línia; els `\n` de `private_key` s'han de mantenir escapats).
3. Comprova que Render exposa `RENDER=true` (el `render.yaml` posa `RENDER="1"`, vegeu [GOTCHAS #26](../GOTCHAS.md)) **[NO VERIFICAT]**.
4. GitHub Actions: secret `FIREBASE_SERVICE_ACCOUNT_KEY` (usat per `process-visits.yml`, que posa `PRODUCTION='true'`).

## Problemes habituals
| Error | Solució |
|---|---|
| `FileNotFoundError: Fitxer de credencials no trobat: .../env/firebase-service-account.json` | Falta el fitxer en local, o s'està en un entorn (p. ex. CI sense `TESTING`) que no hauria d'arribar a la ruta local |
| `Variable d'entorn FIREBASE_SERVICE_ACCOUNT_KEY no trobada` | Entorn detectat com a producció sense la variable |
| Error parsejant el JSON de `FIREBASE_SERVICE_ACCOUNT_KEY` | JSON mal enganxat o caràcters mal escapats |
| "Firebase already initialized" | Inofensiu: l'app ja estava inicialitzada (`get_app()` la reaprofita) |
