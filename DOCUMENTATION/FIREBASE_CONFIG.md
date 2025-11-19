# Configuració de Firebase per RefugisLliures Backend

## Descripció
Aquest document explica com configurar les credencials de Firebase per al projecte RefugisLliures Backend tant en entorns de desenvolupament com de producció.

## Opcions de Configuració

### Opció 1: Fitxer JSON (Recomanat per desenvolupament)

1. Descarrega el fitxer de credencials de Firebase des de la consola de Firebase
2. Guarda'l a la carpeta `env/` amb el nom apropiat:
   - Desenvolupament: `firebase-service-account-dev.json`
   - Producció: `firebase-service-account-prod.json`
3. Configura la variable `GOOGLE_APPLICATION_CREDENTIALS` al fitxer `.env` corresponent

### Opció 2: Variable d'Entorn JSON (Recomanat per producció/Render)

1. Copia tot el contingut del fitxer JSON de credencials
2. Configura la variable d'entorn `FIREBASE_SERVICE_ACCOUNT_KEY` amb aquest contingut

#### Exemple per Render:
```bash
FIREBASE_SERVICE_ACCOUNT_KEY={"type":"service_account","project_id":"your-project","private_key_id":"...","private_key":"-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n","client_email":"...","client_id":"...","auth_uri":"...","token_uri":"...","auth_provider_x509_cert_url":"...","client_x509_cert_url":"..."}
```

## Ordre de Prioritat

El servei de Firebase buscarà les credencials en aquest ordre:

1. **Variable d'entorn** `FIREBASE_SERVICE_ACCOUNT_KEY` (JSON complet)
2. **Fitxer JSON** especificat a `GOOGLE_APPLICATION_CREDENTIALS`

## Avantatges de cada mètode

### Fitxer JSON:
- Més fàcil de gestionar en desenvolupament
- Millor per a control de versions (amb `.gitignore`)

### Variable d'entorn:
- Més segur per a producció
- Compatible amb serveis cloud com Render, Heroku, etc.
- No requereix gestió de fitxers

## Configuració de Render

Per configurar Firebase a Render:

1. Vés a les variables d'entorn del teu servei a Render
2. Afegeix la variable `FIREBASE_SERVICE_ACCOUNT_KEY`
3. Enganxa el contingut complet del fitxer JSON com a valor
4. Assegura't que la variable `RENDER=true` estigui configurada (per detectar l'entorn de producció)

## Resolució de Problemes

### Error: "Firebase credentials file not found"
- Verifica que el fitxer existeixi a la ruta especificada
- Comprova que `GOOGLE_APPLICATION_CREDENTIALS` apunti al fitxer correcte

### Error: "Error parsing Firebase credentials from environment variable"
- Verifica que el JSON de `FIREBASE_SERVICE_ACCOUNT_KEY` sigui vàlid
- Assegura't que no hi hagi caràcters especials mal escapats

### Error: "Firebase already initialized"
- Això és normal, el servei utilitza un patró singleton
- El missatge d'error no afecta el funcionament
