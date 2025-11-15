# Canvis implementats: Autenticació Firebase JWT

## Resum

S'ha implementat un sistema d'autenticació complet basat en tokens JWT de Firebase per protegir els endpoints d'usuaris.

## Fitxers creats

### 1. `api/middleware/firebase_auth_middleware.py`
Middleware que intercepta les peticions i valida els tokens JWT de Firebase abans que arribin a les vistes.

**Característiques:**
- Valida tokens JWT amb Firebase Admin SDK
- Verifica signatura, expiració i revocació
- Afegeix informació de l'usuari autenticat a la request
- Permet endpoints públics sense autenticació
- Retorna errors 401 adequats per tokens invàlids

### 2. `api/authentication.py`
Backend d'autenticació personalitzat per a Django REST Framework.

**Característiques:**
- Integració amb DRF
- Verifica tokens JWT de Firebase
- Crea objectes d'usuari temporals amb informació del token
- Gestió d'errors d'autenticació

### 3. `api/permissions.py`
Classes de permisos personalitzades per controlar l'accés als recursos.

**Classes incloses:**
- `IsOwnerOrReadOnly`: Permet llegir a tots, escriure només al propietari
- `IsOwner`: Només permet accés al propietari
- `IsSameUser`: Verifica que l'usuari accedeix a les seves pròpies dades (compara UID de la URL amb UID del token)

### 4. `FIREBASE_AUTH.md`
Documentació completa sobre:
- Com funciona l'autenticació
- Format dels headers
- Endpoints protegits vs públics
- Respostes d'error
- Exemples d'ús
- Configuració
- Testing

### 5. `test_firebase_auth.py`
Script d'utilitat per testejar l'autenticació:
- Tests d'endpoints públics
- Tests d'endpoints protegits amb/sense token
- Tests d'actualització d'usuaris
- Exemples pràctics d'ús

## Fitxers modificats

### 1. `refugis_lliures/settings.py`

**Canvis:**
- Afegit `drf_yasg` a `INSTALLED_APPS` per a Swagger
- Afegit `FirebaseAuthenticationMiddleware` a `MIDDLEWARE`
- Afegit `FirebaseAuthentication` a `REST_FRAMEWORK['DEFAULT_AUTHENTICATION_CLASSES']`

### 2. `refugis_lliures/urls.py`

**Canvis:**
- Afegida configuració de Swagger/OpenAPI
- Endpoints de documentació:
  - `/swagger/` - Swagger UI
  - `/redoc/` - ReDoc
  - `/swagger.json` - Schema JSON
  - `/swagger.yaml` - Schema YAML

### 3. `api/views/user_views.py`

**Canvis:**
- Importat `IsAuthenticated` i `IsSameUser`
- Aplicats decoradors `@permission_classes([IsAuthenticated, IsSameUser])` als endpoints d'usuaris
- Actualitzats decoradors `@swagger_auto_schema` amb:
  - Paràmetre `Authorization` al header
  - Respostes 401 i 403
  - Descripcions actualitzades

### 4. `api/middleware/__init__.py`
Creat per exportar el middleware.

## Endpoints protegits

Els següents endpoints **REQUEREIXEN autenticació**:

- `GET /api/users/{uid}/` - Obtenir usuari (només el propi)
- `PUT /api/users/{uid}/` - Actualitzar usuari (només el propi)
- `DELETE /api/users/{uid}/` - Eliminar usuari (només el propi)

**Important:** Els usuaris només poden accedir a les seves pròpies dades. El `{uid}` ha de coincidir amb el UID del token JWT.

## Endpoints públics

Els següents endpoints **NO requereixen autenticació**:

- `GET /api/health/` - Health check
- `GET /api/refugis/` - Llistar refugis
- `GET /api/refugis/{id}/` - Obtenir refugi
- `POST /api/users/` - Crear usuari
- `/api/cache/*` - Endpoints de cache
- `/admin/*` - Django admin
- `/swagger/*` - Documentació Swagger
- `/redoc/` - Documentació ReDoc

## Format d'autenticació

### Header requerit
```
Authorization: Bearer <firebase_jwt_token>
```

### Exemple amb cURL
```bash
curl -X GET \
  http://localhost:8000/api/users/USER_UID/ \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIsImtpZCI6I..."
```

### Exemple amb JavaScript
```javascript
// Obtenir el token
const user = firebase.auth().currentUser;
const token = await user.getIdToken();

// Fer la petició
fetch('http://localhost:8000/api/users/USER_UID/', {
  method: 'GET',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  }
});
```

## Respostes d'error

### 401 Unauthorized
```json
{
  "error": "No autoritzat",
  "message": "Token expirat"
}
```

Causes:
- Token no proporcionat
- Token expirat
- Token invàlid
- Token revocat
- Format incorrecte

### 403 Forbidden
Retornat quan l'usuari autenticat intenta accedir a dades d'un altre usuari.

## Flux d'autenticació

```
Client                    Backend                    Firebase
  |                          |                           |
  |-- 1. Login ------------->|                           |
  |                          |                           |
  |<------------------------ TOKEN ---------------------|
  |                          |                           |
  |-- 2. Request amb token ->|                           |
  |                          |                           |
  |                          |-- 3. Verificar token ---->|
  |                          |                           |
  |                          |<-- 4. Token vàlid --------|
  |                          |                           |
  |<-- 5. Response ----------|                           |
```

## Com provar

### 1. Executar el servidor
```bash
python manage.py runserver
```

### 2. Accedir a Swagger
```
http://localhost:8000/swagger/
```

### 3. Executar tests
```bash
python test_firebase_auth.py
```

### 4. Test manual amb cURL
Necessites obtenir un token JWT de Firebase primer:

```bash
# Endpoint públic (funciona sense token)
curl http://localhost:8000/api/health/

# Endpoint protegit (requereix token)
curl -H "Authorization: Bearer YOUR_TOKEN" \
     http://localhost:8000/api/users/YOUR_UID/
```

## Consideracions de seguretat

1. **Tokens JWT**: Durada limitada (1 hora per defecte)
2. **HTTPS**: Utilitzar sempre en producció
3. **Revocació**: Tokens poden ser revocats per Firebase
4. **Verificació**: Signatura verificada automàticament per Firebase Admin SDK
5. **Isolació**: Usuaris només poden accedir a les seves pròpies dades

## Dependències

Totes les dependències ja estan instal·lades:
- `firebase-admin==6.5.0` - Per verificar tokens
- `djangorestframework==3.15.2` - Framework REST
- `drf_yasg` - Documentació OpenAPI/Swagger

## Configuració Firebase

Les credencials de Firebase ja estan configurades:
- Fitxers de credencials a `env/firebase-service-account*.json`
- Variables d'entorn configurades a `settings.py`

## Següents passos recomanats

1. **Testing exhaustiu**: Provar tots els casos límit
2. **Logging**: Revisar logs per detectar intents d'accés no autoritzat
3. **Monitoring**: Implementar alertes per errors d'autenticació
4. **Rate limiting**: Considerar limitar peticions per usuari
5. **Documentació frontend**: Documentar com obtenir i enviar tokens des del frontend

## Suport

Per qualsevol dubte o problema, consultar:
- `FIREBASE_AUTH.md` - Documentació detallada
- `test_firebase_auth.py` - Exemples pràctics
- Swagger UI - Documentació interactiva de l'API
