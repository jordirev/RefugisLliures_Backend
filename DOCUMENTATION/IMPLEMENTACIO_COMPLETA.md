# Implementació d'Autenticació JWT amb Firebase

## 📋 Resum de la Implementació

S'ha implementat amb èxit un sistema complet d'autenticació basat en tokens JWT de Firebase per protegir els endpoints d'usuaris del backend.

## ✅ Estat de la Implementació

**COMPLETAT** - Tots els components estan implementats i verificats.

## 🔧 Components Implementats

### 1. Middleware d'Autenticació
**Fitxer:** `api/middleware/firebase_auth_middleware.py`

- ✅ Intercepta peticions als endpoints protegits
- ✅ Verifica tokens JWT amb Firebase Admin SDK
- ✅ Gestiona errors d'autenticació (401 Unauthorized)
- ✅ Permet endpoints públics sense autenticació
- ✅ Afegeix informació d'usuari a la request

### 2. Backend d'Autenticació DRF
**Fitxer:** `api/authentication.py`

- ✅ Integració amb Django REST Framework
- ✅ Verificació de tokens JWT
- ✅ Creació d'objectes d'usuari temporals
- ✅ Gestió d'errors d'autenticació

### 3. Sistema de Permisos
**Fitxer:** `api/permissions.py`

- ✅ `IsSameUser`: Verifica accés a dades pròpies
- ✅ `IsOwner`: Permís només per al propietari
- ✅ `IsOwnerOrReadOnly`: Lectura pública, escriptura propietari

### 4. Configuració Django
**Fitxers modificats:**
- `refugis_lliures/settings.py`
- `refugis_lliures/urls.py`
- `api/views/user_views.py`

- ✅ Middleware afegit a MIDDLEWARE
- ✅ Authentication class configurada a REST_FRAMEWORK
- ✅ Swagger/OpenAPI configurat
- ✅ Endpoints d'usuaris protegits amb permisos

### 5. Documentació
**Fitxers creats:**
- ✅ `FIREBASE_AUTH.md` - Documentació completa d'ús
- ✅ `FIREBASE_AUTH_CHANGES.md` - Resum de canvis
- ✅ `test_firebase_auth.py` - Script de testing
- ✅ `test_auth_setup.py` - Verificació de configuració

## 🔐 Endpoints Protegits

Els següents endpoints **requereixen autenticació**:

| Endpoint | Mètode | Descripció | Permís |
|----------|--------|------------|--------|
| `/api/users/{uid}/` | GET | Obtenir usuari | Només el propi usuari |
| `/api/users/{uid}/` | PUT | Actualitzar usuari | Només el propi usuari |
| `/api/users/{uid}/` | DELETE | Eliminar usuari | Només el propi usuari |

**Nota:** El `{uid}` de la URL ha de coincidir amb el `uid` del token JWT.

## 🌐 Endpoints Públics

Els següents endpoints **NO requereixen autenticació**:

- ✅ `GET /api/health/` - Health check
- ✅ `GET /api/refuges/` - Llistar refugis
- ✅ `GET /api/refuges/{id}/` - Obtenir refugi
- ✅ `POST /api/users/` - Crear nou usuari
- ✅ `/api/cache/*` - Gestió de cache
- ✅ `/swagger/` - Documentació Swagger
- ✅ `/redoc/` - Documentació ReDoc
- ✅ `/admin/` - Django admin

## 📝 Format d'Autenticació

### Header Requerit
```
Authorization: Bearer <firebase_jwt_token>
```

### Exemple de Petició
```bash
curl -X GET \
  http://localhost:8000/api/users/USER_UID/ \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIsImtpZCI6I..."
```

### Exemple amb JavaScript (Frontend)
```javascript
// 1. Obtenir el token de Firebase
const user = firebase.auth().currentUser;
const token = await user.getIdToken();

// 2. Fer la petició a l'API
const response = await fetch('http://localhost:8000/api/users/USER_UID/', {
  method: 'GET',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  }
});

const data = await response.json();
```

## 🔍 Com Provar la Implementació

### 1. Verificar la Instal·lació
```bash
python test_auth_setup.py
```

**Sortida esperada:**
```
✅ Tots els tests han passat!
```

### 2. Executar el Servidor
```bash
python manage.py runserver
```

### 3. Accedir a Swagger
Obre el navegador i ves a:
```
http://localhost:8000/swagger/
```

### 4. Provar Endpoint Públic
```bash
curl http://localhost:8000/api/health/
```

**Resposta esperada:** Status 200 OK

### 5. Provar Endpoint Protegit sense Token
```bash
curl http://localhost:8000/api/users/USER_UID/
```

**Resposta esperada:** Status 401 Unauthorized
```json
{
  "error": "No autoritzat",
  "message": "Token d'autenticació no proporcionat"
}
```

### 6. Provar Endpoint Protegit amb Token
```bash
curl -H "Authorization: Bearer YOUR_FIREBASE_TOKEN" \
     http://localhost:8000/api/users/YOUR_UID/
```

**Resposta esperada:** Status 200 OK amb dades de l'usuari

### 7. Tests Automatitzats
```bash
python test_firebase_auth.py
```

Aquest script et guiarà per executar diferents tests d'autenticació.

## 🚨 Respostes d'Error

### 401 Unauthorized

**Causes possibles:**
- Token no proporcionat
- Token expirat
- Token invàlid o malformat
- Token revocat
- Format incorrecte del header

**Exemple:**
```json
{
  "error": "No autoritzat",
  "message": "Token expirat"
}
```

### 403 Forbidden

**Causa:**
- L'usuari autenticat intenta accedir a dades d'un altre usuari

**Exemple:**
```json
{
  "error": "Permís denegat"
}
```

## 🔄 Flux d'Autenticació

```
┌─────────┐                 ┌─────────┐                 ┌──────────┐
│ Client  │                 │ Backend │                 │ Firebase │
└────┬────┘                 └────┬────┘                 └────┬─────┘
     │                           │                           │
     │ 1. Login amb Firebase     │                           │
     ├──────────────────────────────────────────────────────>│
     │                           │                           │
     │ 2. Retorna JWT Token      │                           │
     │<──────────────────────────────────────────────────────┤
     │                           │                           │
     │ 3. Request + Token        │                           │
     ├──────────────────────────>│                           │
     │                           │                           │
     │                           │ 4. Verifica Token         │
     │                           ├──────────────────────────>│
     │                           │                           │
     │                           │ 5. Token Vàlid            │
     │                           │<──────────────────────────┤
     │                           │                           │
     │ 6. Response amb Dades     │                           │
     │<──────────────────────────┤                           │
     │                           │                           │
```

## 📚 Documentació Addicional

### Documentació Creada

1. **FIREBASE_AUTH.md**
   - Guia completa d'ús
   - Configuració detallada
   - Exemples de codi
   - Troubleshooting

2. **FIREBASE_AUTH_CHANGES.md**
   - Resum de tots els canvis
   - Fitxers creats i modificats
   - Instruccions de configuració

3. **Swagger UI**
   - Accessible a `/swagger/`
   - Documentació interactiva de tots els endpoints
   - Possibilitat de provar l'API directament

4. **ReDoc**
   - Accessible a `/redoc/`
   - Documentació alternativa més visual

## 🔒 Consideracions de Seguretat

### Implementades

✅ **Verificació de Signatures**: Firebase Admin SDK verifica automàticament la signatura dels tokens

✅ **Validació d'Expiració**: Els tokens expirats són rebutjats automàticament (durada per defecte: 1 hora)

✅ **Detecció de Revocació**: Els tokens revocats són detectats i rebutjats

✅ **Isolació d'Usuaris**: Cada usuari només pot accedir a les seves pròpies dades

✅ **Endpoints Públics Controlats**: Els endpoints públics estan clarament definits i separats

### Recomanacions per a Producció

⚠️ **HTTPS Obligatori**: En producció, utilitzar sempre HTTPS per protegir els tokens en trànsit

⚠️ **Rate Limiting**: Considerar implementar limitació de peticions per usuari

⚠️ **Monitoring**: Implementar alertes per intents d'accés no autoritzat

⚠️ **Logging**: Revisar regularment els logs per detectar patrons sospitosos

⚠️ **Token Refresh**: Implementar un sistema per renovar tokens abans que expirint

## 🧪 Testing

### Tests de Configuració
```bash
python test_auth_setup.py
```

### Tests Funcionals
```bash
python test_firebase_auth.py
```

### Tests Manuals amb cURL

**Endpoint públic:**
```bash
curl http://localhost:8000/api/health/
```

**Endpoint protegit sense token:**
```bash
curl http://localhost:8000/api/users/USER_UID/
# Esperat: 401 Unauthorized
```

**Endpoint protegit amb token:**
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
     http://localhost:8000/api/users/YOUR_UID/
# Esperat: 200 OK
```

**Actualitzar usuari:**
```bash
curl -X PUT \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"nom": "Nou Nom", "bio": "Nova bio"}' \
     http://localhost:8000/api/users/YOUR_UID/
```

## 🎯 Integració amb el Frontend

### Obtenció del Token

```javascript
import { getAuth } from 'firebase/auth';

// Obtenir el token de l'usuari actual
const auth = getAuth();
const user = auth.currentUser;

if (user) {
  const token = await user.getIdToken();
  // Utilitzar el token en les peticions API
}
```

### Petició API amb Token

```javascript
async function getUserData(uid, token) {
  const response = await fetch(`${API_URL}/api/users/${uid}/`, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    }
  });
  
  if (response.status === 401) {
    // Token expirat o invàlid - fer login de nou
    console.error('Autenticació fallida');
    return null;
  }
  
  return await response.json();
}
```

### Gestió d'Errors

```javascript
async function apiRequest(url, options = {}) {
  try {
    // Obtenir token fresc
    const user = firebase.auth().currentUser;
    const token = await user.getIdToken(true); // force refresh
    
    // Afegir token als headers
    options.headers = {
      ...options.headers,
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    };
    
    const response = await fetch(url, options);
    
    if (response.status === 401) {
      throw new Error('Autenticació fallida');
    }
    
    if (response.status === 403) {
      throw new Error('Permís denegat');
    }
    
    return await response.json();
    
  } catch (error) {
    console.error('Error en petició API:', error);
    throw error;
  }
}
```

## 📦 Dependències

Totes les dependències necessàries ja estan instal·lades:

- ✅ `firebase-admin==6.5.0` - SDK de Firebase per al servidor
- ✅ `djangorestframework==3.15.2` - Framework REST
- ✅ `drf_yasg` - Documentació OpenAPI/Swagger
- ✅ `django-cors-headers==4.4.0` - CORS

## ✨ Funcionalitats Destacades

### Middleware Intel·ligent
- Només s'aplica als endpoints que ho necessiten
- Gestió eficient d'errors
- Logging detallat per debugging

### Permisos Granulars
- Control d'accés a nivell d'usuari
- Protecció contra accés no autoritzat a dades d'altres usuaris
- Flexibilitat per afegir nous nivells de permisos

### Documentació Swagger
- API completament documentada
- Possibilitat de provar endpoints directament
- Informació sobre autenticació integrada

### Tests Automatitzats
- Verificació de configuració
- Tests funcionals d'autenticació
- Exemples pràctics d'ús

## 🚀 Següents Passos Recomanats

1. **Testing Exhaustiu**
   - Provar tots els casos límit
   - Tests d'integració amb el frontend
   - Tests de càrrega

2. **Monitoring**
   - Configurar alertes per errors d'autenticació
   - Tracking d'intents d'accés no autoritzat
   - Métriques d'ús de l'API

3. **Optimització**
   - Cache de verificació de tokens (si cal)
   - Rate limiting per usuari
   - Compressió de respostes

4. **Documentació**
   - Guia per al frontend
   - Runbook per operacions
   - Troubleshooting guide

## ❓ Suport i Ajuda

### Documentació
- **Guia d'ús**: `FIREBASE_AUTH.md`
- **Canvis**: `FIREBASE_AUTH_CHANGES.md`
- **API Docs**: http://localhost:8000/swagger/

### Testing
- **Setup**: `python test_auth_setup.py`
- **Functional**: `python test_firebase_auth.py`

### Problemes Comuns

**Problema:** 401 Unauthorized amb token vàlid
**Solució:** Verificar que Firebase Admin SDK està correctament inicialitzat

**Problema:** 403 Forbidden
**Solució:** Verificar que l'UID de la URL coincideix amb l'UID del token

**Problema:** Token expirat constantment
**Solució:** Implementar renovació automàtica de tokens al frontend

## ✅ Checklist Final

- [x] Middleware implementat i configurat
- [x] Authentication backend creat
- [x] Sistema de permisos implementat
- [x] Endpoints protegits correctament
- [x] Endpoints públics accessibles
- [x] Swagger configurat
- [x] Documentació completa
- [x] Scripts de testing creats
- [x] Tests de verificació passats
- [x] Respostes d'error adequades
- [x] Logging implementat

## 🎉 Conclusió

La implementació d'autenticació JWT amb Firebase està **completament funcional** i llesta per a l'ús. Tots els components estan correctament integrats i verificats.

Per començar a utilitzar-la, simplement:

1. Executa el servidor: `python manage.py runserver`
2. Accedeix a Swagger: http://localhost:8000/swagger/
3. Prova els endpoints amb un token JWT de Firebase

**Implementació completada amb èxit! 🚀**

