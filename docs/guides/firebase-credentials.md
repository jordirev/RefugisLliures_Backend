# Guia — Configurar les credencials de Firebase

> **[FET]** comprovat al codi · **[INFERÈNCIA]** deducció · **[NO VERIFICAT]** depèn de config externa.
> Com funciona per dins (detecció d'entorn, emulador): [integrations/firebase-auth.md](../integrations/firebase-auth.md).

El backend necessita un **service account** de Firebase per verificar tokens i gestionar usuaris i claims de Firebase Auth (Firestore ja no s'usa des del chunk 11, D43). `apps/auth/firebase_config.py` té **un sol camí** **[FET]**:

| Entorn | Es detecta si… | D'on llegeix les credencials |
|---|---|---|
| Tests | `pytest` importat o `TESTING=true` | No s'inicialitza Firebase |
| Firebase Auth Emulator (e2e locals) | `FIREBASE_AUTH_EMULATOR_HOST` | Cap credencial; mai en producció |
| La resta (dev, producció, CI, scripts) | — | `FIREBASE_SERVICE_ACCOUNT_KEY`: el **JSON complet** en una sola línia |

`settings.FIREBASE_SERVICE_ACCOUNT_KEY` (`decouple`) la busca primer a les variables d'entorn reals (Render, Cloud Run, GitHub Actions) i, si no hi és, a `env/.env.development` o, amb `PRODUCTION=true`/`RENDER=true`, a `env/.env.production`. Així el mateix nom serveix a tot arreu i `PRODUCTION=true python manage.py migrate` o `PRODUCTION=true python scripts/manage_admins.py` des de l'ordinador funcionen contra producció sense passar pel servidor.

## Local (desenvolupament) i producció des de l'ordinador
1. Firebase Console → *Project settings* → *Service accounts* → **Generate new private key** (un service account per projecte: dev i producció haurien de ser de projectes Firebase diferents **[NO VERIFICAT]**).
2. Posa el JSON en **una sola línia** i entre cometes simples a `env/.env.development` (o `env/.env.production`): `FIREBASE_SERVICE_ACCOUNT_KEY='{"type":"service_account",...}'`. `decouple` treu les cometes exteriors i no interpreta els `\n` de `private_key`, que han de quedar escapats.
3. Ja no cal `env/firebase-service-account*.json` ni `GOOGLE_APPLICATION_CREDENTIALS` (el codi no els llegeix).
4. Arrenca el servidor o l'script: el log mostra `Firebase inicialitzat amb project_id: …`.

## Producció (Render / Cloud Run) i GitHub Actions
1. Copia **tot** el contingut del JSON del service account.
2. Render → servei → **Environment** → afegeix `FIREBASE_SERVICE_ACCOUNT_KEY` amb el JSON com a valor (una sola línia; els `\n` de `private_key` s'han de mantenir escapats). A Cloud Run, com a secret.
3. GitHub Actions: secret `FIREBASE_SERVICE_ACCOUNT_KEY` (usat per `process-visits.yml`, que posa `PRODUCTION='true'`).

## Problemes habituals
| Error | Solució |
|---|---|
| `Variable d'entorn FIREBASE_SERVICE_ACCOUNT_KEY no trobada` | Falta la variable (ni a l'entorn ni a `env/.env.<entorn>`). Qualsevol procés que arrenqui Django la necessita, també `migrate`. |
| Error parsejant el JSON de `FIREBASE_SERVICE_ACCOUNT_KEY` (`JSONDecodeError`) | JSON mal enganxat, sense cometes simples exteriors o caràcters mal escapats |
| "Firebase already initialized" | Inofensiu: l'app ja estava inicialitzada (`get_app()` la reaprofita) |
