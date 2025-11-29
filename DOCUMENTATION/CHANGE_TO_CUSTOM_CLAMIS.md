# Migració a Custom Claims de Firebase Auth

**Data**: 29 de novembre de 2025  
**Branch**: feature/renovations

## Resum dels Canvis

S'ha migrat el sistema d'autenticació d'administradors de **UIDs al fitxer `.env`** a **Custom Claims de Firebase Auth (1a Generació)**. Això proporciona un sistema més flexible, segur i escalable per gestionar rols i permisos.

## Fitxers Modificats

### 1. Backend Core

#### `api/middleware/firebase_auth_middleware.py`
- ✅ Afegit: Extracció dels custom claims del token JWT
- ✅ Afegit: `request.user_claims` conté tots els claims de l'usuari

#### `api/authentication.py`
- ✅ Modificat: L'objecte `FirebaseUser` ara inclou `claims` amb els custom claims
- ✅ Garanteix que els claims estan disponibles a `request.user.claims`

#### `api/permissions.py`
- ✅ Modificat: `IsFirebaseAdmin` ara comprova el custom claim `admin: true`
- ✅ Eliminada: Dependència de `settings.FIREBASE_ADMIN_UIDS`

#### `refugis_lliures/settings.py`
- ✅ Eliminat: Variable `FIREBASE_ADMIN_UIDS`
- ✅ Eliminat: Lectura de la variable d'entorn `FIREBASE_ADMIN_UIDS`

### 2. Views

#### `api/views/cache_views.py`
- ✅ Actualitzat: Descripcions d'operació per reflectir l'ús de custom claims
- ✅ Canviat: Referències de "UID a FIREBASE_ADMIN_UIDS" a "custom claim 'admin': true"

### 3. Tests

#### `api/tests/test_cache_views.py`
- ✅ Modificat: Fixture `mock_admin_uid` → `mock_admin_claims`
- ✅ Actualitzat: Tots els tests ara utilitzen `request.user_claims = mock_admin_claims`
- ✅ Eliminades: Referències a `settings.FIREBASE_ADMIN_UIDS`

### 4. Documentació

#### `DOCUMENTATION/CACHE_ADMIN_ENDPOINTS.md`
- ✅ Actualitzat: Secció de configuració d'administradors
- ✅ Afegit: Instruccions per afegir admins amb custom claims
- ✅ Afegit: Scripts i exemples de Python
- ✅ Actualitzat: Secció d'errors comuns

#### `DOCUMENTATION/CUSTOM_CLAIMS.md` (NOU)
- ✅ Creat: Document complet sobre Custom Claims
- ✅ Inclou: Arquitectura del sistema
- ✅ Inclou: Script `manage_admins.py` amb documentació
- ✅ Inclou: Exemples de Cloud Functions
- ✅ Inclou: Guia de renovació de tokens
- ✅ Inclou: Bones pràctiques i seguretat
- ✅ Inclou: Troubleshooting i testing

#### `DOCUMENTATION/README.md`
- ✅ Actualitzat: Afegida secció de documentació addicional amb enllaços

### 5. Scripts

#### `scripts/manage_admins.py` (NOU)
- ✅ Creat: Script per gestionar administradors
- ✅ Comandes: `add`, `remove`, `check`, `list`
- ✅ Integració amb Django i Firebase Admin SDK

## Canvis Tècnics

### Abans (Sistema antic)

```python
# settings.py
FIREBASE_ADMIN_UIDS = ['uid1', 'uid2', 'uid3']

# permissions.py
class IsFirebaseAdmin:
    def has_permission(self, request, view):
        admin_uids = settings.FIREBASE_ADMIN_UIDS
        return request.user_uid in admin_uids
```

### Després (Sistema nou)

```python
# middleware
decoded_token = auth.verify_id_token(token)
request.user_claims = decoded_token  # Inclou custom claims

# permissions.py
class IsFirebaseAdmin:
    def has_permission(self, request, view):
        user_claims = getattr(request, 'user_claims', {})
        return user_claims.get('role') == 'admin'
```

## Avantatges del Nou Sistema

### ✅ Seguretat
- Claims signats per Firebase (no es poden falsificar)
- No cal gestionar llistes d'UIDs al servidor
- Validació automàtica amb el token JWT

### ✅ Flexibilitat
- Fàcil d'estendre amb més rols (moderator, verified, etc.)
- Claims disponibles al client i servidor
- Sistema estàndard de la indústria

### ✅ Escalabilitat
- No cal reiniciar el servidor per afegir admins
- Script `manage_admins.py` per gestió ràpida
- Possibilitat de Cloud Functions per gestió automatitzada

### ✅ Mantenibilitat
- Menys configuració al servidor
- Codi més net i desacoblat
- Millor separació de preocupacions

## Com Utilitzar el Nou Sistema

### Afegir un Administrador

```bash
python scripts/manage_admins.py add <uid>
```

### Eliminar un Administrador

```bash
python scripts/manage_admins.py remove <uid>
```

### Comprovar si un Usuari és Admin

```bash
python scripts/manage_admins.py check <uid>
```

### Llistar Tots els Usuaris

```bash
python scripts/manage_admins.py list
```

### Renovar Token (Client)

```javascript
// Després de canviar els claims, el client ha de renovar el token
const newToken = await firebase.auth().currentUser.getIdToken(true);
```

## Breaking Changes

### ⚠️ Variables d'Entorn

**Eliminat**: `FIREBASE_ADMIN_UIDS` ja no s'utilitza.

**Acció requerida**:
1. Si tens administradors configurats al `.env`, copia els UIDs
2. Executa el script per afegir-los amb custom claims:
   ```bash
   python scripts/manage_admins.py add <uid1>
   python scripts/manage_admins.py add <uid2>
   ```
3. Notifica als administradors que han de renovar el token (logout/login)
4. Elimina `FIREBASE_ADMIN_UIDS` dels fitxers `.env`

### ⚠️ Tests

Els tests que utilitzaven `mock_admin_uid` ara han de utilitzar `mock_admin_claims`:

```python
# Abans
@pytest.fixture
def mock_admin_uid():
    with patch('django.conf.settings.FIREBASE_ADMIN_UIDS', ['test-uid']):
        yield 'test-uid'

# Després
@pytest.fixture
def mock_admin_claims():
    return {'role': 'admin', 'uid': 'test-uid'}
```

## Verificació

### Checklist de Verificació

- ✅ Middleware extreu custom claims
- ✅ Authentication afegeix claims a l'objecte user
- ✅ Permissions comprova custom claim 'admin'
- ✅ Settings no conté FIREBASE_ADMIN_UIDS
- ✅ Tests actualitzats
- ✅ Views actualitzades
- ✅ Documentació completa
- ✅ Script de gestió creat

### Executar Tests

```bash
pytest api/tests/test_cache_views.py -v
```

### Verificar Permisos

```python
# Prova manual
python manage.py shell

from firebase_admin import auth
uid = "abc123"
auth.set_custom_user_claims(uid, {'admin': True})
user = auth.get_user(uid)
print(user.custom_claims)  # {'admin': True}
```

## Roadmap Futur

### Millores Potencials

1. **Rols Múltiples**
   ```python
   # Diferents rols
   auth.set_custom_user_claims(uid, {'role': 'admin'})
   auth.set_custom_user_claims(uid, {'role': 'moderator'})
   auth.set_custom_user_claims(uid, {'role': 'verified_user'})
   ```

2. **Auditoria**
   - Registrar qui afegeix/elimina admins
   - Logs de seguretat per accions d'admin

3. **Interface Web**
   - Panel d'administració per gestionar rols
   - Integració amb Django Admin

4. **Permisos Granulars**
   ```python
   claims = {
       'role': 'admin',
       'permissions': ['read:users', 'write:cache', 'delete:refugis']
   }
   ```

## Referències

- [Custom Claims Documentation](DOCUMENTATION/CUSTOM_CLAIMS.md)
- [Cache Admin Endpoints](DOCUMENTATION/CACHE_ADMIN_ENDPOINTS.md)
- [Firebase Custom Claims](https://firebase.google.com/docs/auth/admin/custom-claims)

## Autors

- **Jordi** - Implementació inicial de Custom Claims

---

**Última actualització**: 29 de novembre de 2025
