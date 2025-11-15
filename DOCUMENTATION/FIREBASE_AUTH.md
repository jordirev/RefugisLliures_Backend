# Autenticació amb Firebase JWT

## Descripció

Aquest backend utilitza Firebase Authentication per verificar els tokens JWT dels usuaris. Els endpoints d'usuaris estan protegits i requereixen un token vàlid per accedir-hi.

## Flux d'autenticació

1. L'aplicació client autentica l'usuari amb Firebase Authentication
2. Firebase retorna un token JWT (ID Token)
3. El client envia el token a l'API en el header `Authorization`
4. El middleware del backend verifica el token amb Firebase Admin SDK
5. Si el token és vàlid, la petició continua; sinó, retorna un error 401

## Format del header

```
Authorization: Bearer <firebase_jwt_token>
```

## Endpoints protegits

Els següents endpoints requereixen autenticació:

- `GET /api/users/{uid}/` - Obté un usuari (només el propi usuari)
- `PUT /api/users/{uid}/` - Actualitza un usuari (només el propi usuari)
- `DELETE /api/users/{uid}/` - Elimina un usuari (només el propi usuari)

**Important**: Els usuaris només poden accedir a les seves pròpies dades. El `uid` de la URL ha de coincidir amb el `uid` del token JWT.

## Endpoints públics

Els següents endpoints NO requereixen autenticació:

- `GET /api/health/` - Health check
- `GET /api/refugis/` - Llistar refugis
- `GET /api/refugis/{id}/` - Obtenir detalls d'un refugi
- `POST /api/users/` - Crear un nou usuari
- Endpoints de cache (`/api/cache/*`)

## Respostes d'error

### 401 Unauthorized

Retornat quan:
- No s'ha proporcionat cap token
- El format del token és invàlid
- El token ha expirat
- El token ha estat revocat
- El token no és vàlid

Exemple:
```json
{
    "error": "No autoritzat",
    "message": "Token expirat"
}
```

### 403 Forbidden

Retornat quan:
- L'usuari està autenticat però intenta accedir a dades d'un altre usuari

## Implementació

### Middleware

El middleware `FirebaseAuthenticationMiddleware` intercepta les peticions als endpoints protegits i:

1. Extreu el token del header `Authorization`
2. Verifica el token amb Firebase Admin SDK
3. Afegeix la informació de l'usuari a `request.firebase_user` i `request.user_uid`
4. Permet que la petició continuï o retorna un error 401

### Authentication Backend

La classe `FirebaseAuthentication` proporciona integració amb Django REST Framework per a l'autenticació basada en tokens JWT de Firebase.

### Permissions

La classe `IsSameUser` verifica que l'usuari autenticat només accedeixi a les seves pròpies dades comparant el `uid` de la URL amb el `uid` del token.

## Configuració

### Variables d'entorn necessàries

Ja configurades en el projecte:
- `GOOGLE_APPLICATION_CREDENTIALS` - Ruta al fitxer de credencials de Firebase
- `FIREBASE_SERVICE_ACCOUNT_KEY` - Clau JSON del compte de servei (opcional, per a producció)

### Settings de Django

```python
MIDDLEWARE = [
    ...
    'api.middleware.FirebaseAuthenticationMiddleware',
    ...
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'api.authentication.FirebaseAuthentication',
    ],
    ...
}
```

## Exemple d'ús amb cURL

### Obtenir el token de Firebase (exemple)

```javascript
// Frontend JavaScript
const user = firebase.auth().currentUser;
const token = await user.getIdToken();
```

### Cridar l'API amb el token

```bash
# Obtenir les dades del propi usuari
curl -X GET \
  http://localhost:8000/api/users/USER_UID/ \
  -H "Authorization: Bearer YOUR_FIREBASE_JWT_TOKEN"

# Actualitzar les dades del propi usuari
curl -X PUT \
  http://localhost:8000/api/users/USER_UID/ \
  -H "Authorization: Bearer YOUR_FIREBASE_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "nom": "Nou Nom",
    "bio": "Nova biografia"
  }'
```

## Swagger/OpenAPI

La documentació interactiva de l'API està disponible a:
- Swagger UI: http://localhost:8000/swagger/
- ReDoc: http://localhost:8000/redoc/

Per provar els endpoints protegits a Swagger:
1. Obtén un token JWT de Firebase
2. Clica el botó "Authorize" a Swagger UI
3. Introdueix: `Bearer YOUR_TOKEN`
4. Ara pots provar els endpoints protegits

## Consideracions de seguretat

1. **Tokens JWT**: Els tokens de Firebase tenen una durada limitada (per defecte 1 hora)
2. **HTTPS**: En producció, sempre utilitza HTTPS per protegir els tokens en trànsit
3. **Revocació**: Firebase permet revocar tokens d'usuaris específics
4. **Verificació**: El SDK de Firebase verifica automàticament la signatura del token

## Testing

Per provar l'autenticació en desenvolupament, necessites:

1. Un projecte Firebase configurat
2. Un usuari creat a Firebase Authentication
3. Obtenir un token JWT vàlid d'aquest usuari

Alternativament, pots crear un script de test que generi tokens per a proves.
