# Custom Claims de Firebase Auth - Sistema de Rols

## Descripció

Aquest document explica com s'utilitzen els **Custom Claims de Firebase Auth (1a Generació)** per gestionar rols i permisos al backend de Refugis Lliures.

## Què són els Custom Claims?

Els Custom Claims són camps personalitzats que es poden afegir al token JWT de Firebase Auth. Aquests camps:
- S'inclouen automàticament al token JWT
- Són accessibles tant al client com al servidor
- Permeten implementar control d'accés basat en rols (RBAC)
- Es validen amb la signatura del token (són segurs)

## Arquitectura del Sistema

### 1. Flux d'Autenticació amb Custom Claims

```
┌─────────────┐
│   Client    │
│ (App/Web)   │
└──────┬──────┘
       │ 1. Login amb Firebase Auth
       │
       ▼
┌─────────────────────────────┐
│   Firebase Auth Service     │
│  - Autentica usuari         │
│  - Genera token JWT         │
│  - Inclou custom claims     │
└──────────┬──────────────────┘
           │ 2. Token JWT amb claims
           │    { uid, email, admin: true }
           ▼
┌─────────────────────────────┐
│   Backend Django            │
│  - FirebaseAuthMiddleware   │
│  - Extreu custom claims     │
│  - Valida permisos          │
└─────────────────────────────┘
```

### 2. Components del Backend

#### **Middleware**: `firebase_auth_middleware.py`
```python
# Extreu els custom claims del token
decoded_token = auth.verify_id_token(token)
request.user_claims = decoded_token  # Inclou tots els claims
request.user_uid = decoded_token.get('uid')
```

#### **Authentication**: `authentication.py`
```python
# Afegeix claims a l'objecte user
user = type('FirebaseUser', (), {
    'uid': decoded_token.get('uid'),
    'email': decoded_token.get('email'),
    'claims': decoded_token,  # Custom claims disponibles
    'is_authenticated': True,
})()
```

#### **Permissions**: `permissions.py`
```python
class IsFirebaseAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        user_claims = getattr(request, 'user_claims', {})
        return user_claims.get('admin', False) is True
```

## Gestió d'Administradors

### Mètode 1: Script Python (Recomanat)

Crea un fitxer `scripts/manage_admins.py`:

```python
#!/usr/bin/env python3
"""
Script per gestionar administradors del sistema mitjançant Custom Claims de Firebase
"""
import sys
import os
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'refugis_lliures.settings')
django.setup()

from firebase_admin import auth
import firebase_admin

# Inicialitzar Firebase (si no està ja inicialitzat)
if not firebase_admin._apps:
    from django.conf import settings
    import firebase_admin
    from firebase_admin import credentials
    
    cred = credentials.Certificate(settings.GOOGLE_APPLICATION_CREDENTIALS)
    firebase_admin.initialize_app(cred)


def add_admin(uid):
    """Afegeix permisos d'administrador a un usuari"""
    try:
        # Obtenir claims actuals
        user = auth.get_user(uid)
        current_claims = user.custom_claims or {}
        
        # Afegir rol admin
        current_claims['admin'] = True
        auth.set_custom_user_claims(uid, current_claims)
        
        print(f"✓ Usuari {uid} ({user.email}) ara és administrador")
        print("⚠️  L'usuari ha de renovar el seu token (logout/login)")
        return True
    except auth.UserNotFoundError:
        print(f"✗ Error: Usuari {uid} no trobat")
        return False
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        return False


def remove_admin(uid):
    """Elimina permisos d'administrador d'un usuari"""
    try:
        user = auth.get_user(uid)
        current_claims = user.custom_claims or {}
        
        # Eliminar rol admin
        current_claims['admin'] = False
        auth.set_custom_user_claims(uid, current_claims)
        
        print(f"✓ Permisos d'admin eliminats per {uid} ({user.email})")
        print("⚠️  L'usuari ha de renovar el seu token (logout/login)")
        return True
    except auth.UserNotFoundError:
        print(f"✗ Error: Usuari {uid} no trobat")
        return False
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        return False


def check_admin(uid):
    """Comprova si un usuari és administrador"""
    try:
        user = auth.get_user(uid)
        claims = user.custom_claims or {}
        is_admin = claims.get('admin', False)
        
        print(f"Usuari: {user.email}")
        print(f"UID: {uid}")
        print(f"Admin: {'✓ Sí' if is_admin else '✗ No'}")
        print(f"Custom Claims: {claims}")
        return is_admin
    except auth.UserNotFoundError:
        print(f"✗ Error: Usuari {uid} no trobat")
        return False
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        return False


def list_users():
    """Llista tots els usuaris amb els seus rols"""
    try:
        page = auth.list_users()
        users_info = []
        
        while page:
            for user in page.users:
                claims = user.custom_claims or {}
                is_admin = claims.get('admin', False)
                users_info.append({
                    'uid': user.uid,
                    'email': user.email,
                    'admin': is_admin
                })
            page = page.get_next_page()
        
        # Imprimir taula
        print(f"\n{'UID':<30} {'Email':<35} {'Admin':<10}")
        print("-" * 80)
        for user_info in users_info:
            admin_status = '✓ Sí' if user_info['admin'] else '✗ No'
            print(f"{user_info['uid']:<30} {user_info['email']:<35} {admin_status:<10}")
        
        # Resum
        total = len(users_info)
        admins = sum(1 for u in users_info if u['admin'])
        print(f"\nTotal usuaris: {total}")
        print(f"Administradors: {admins}")
        
        return users_info
    except Exception as e:
        print(f"✗ Error llistant usuaris: {str(e)}")
        return []


def main():
    """Funció principal"""
    if len(sys.argv) < 2:
        print("Gestió d'Administradors - Refugis Lliures")
        print("\nÚs:")
        print("  python manage_admins.py add <uid>       - Afegir admin")
        print("  python manage_admins.py remove <uid>    - Eliminar admin")
        print("  python manage_admins.py check <uid>     - Comprovar admin")
        print("  python manage_admins.py list            - Llistar tots els usuaris")
        print("\nExemples:")
        print("  python manage_admins.py add abc123def456")
        print("  python manage_admins.py check abc123def456")
        print("  python manage_admins.py list")
        sys.exit(1)
    
    action = sys.argv[1].lower()
    
    if action == "add":
        if len(sys.argv) != 3:
            print("✗ Error: Especifica el UID de l'usuari")
            sys.exit(1)
        uid = sys.argv[2]
        add_admin(uid)
    
    elif action == "remove":
        if len(sys.argv) != 3:
            print("✗ Error: Especifica el UID de l'usuari")
            sys.exit(1)
        uid = sys.argv[2]
        remove_admin(uid)
    
    elif action == "check":
        if len(sys.argv) != 3:
            print("✗ Error: Especifica el UID de l'usuari")
            sys.exit(1)
        uid = sys.argv[2]
        check_admin(uid)
    
    elif action == "list":
        list_users()
    
    else:
        print(f"✗ Error: Acció '{action}' no reconeguda")
        print("Accions vàlides: add, remove, check, list")
        sys.exit(1)


if __name__ == "__main__":
    main()
```

#### Ús del Script

```bash
# Afegir administrador
python scripts/manage_admins.py add abc123def456

# Eliminar administrador
python scripts/manage_admins.py remove abc123def456

# Comprovar si un usuari és admin
python scripts/manage_admins.py check abc123def456

# Llistar tots els usuaris i els seus rols
python scripts/manage_admins.py list
```

### Mètode 2: Cloud Function (Firebase)

Per a un sistema més automatitzat, pots crear una Cloud Function:

```javascript
const functions = require('firebase-functions');
const admin = require('firebase-admin');

// Inicialitzar Firebase Admin
if (!admin.apps.length) {
  admin.initializeApp();
}

/**
 * Cloud Function per afegir rol d'admin
 * Només pot ser cridat per super-admins
 */
exports.addAdminRole = functions.https.onCall(async (data, context) => {
  // Verificar autenticació
  if (!context.auth) {
    throw new functions.https.HttpsError(
      'unauthenticated',
      'Cal estar autenticat'
    );
  }

  // Verificar que qui crida és super-admin
  if (context.auth.token.superAdmin !== true) {
    throw new functions.https.HttpsError(
      'permission-denied',
      'Només super-admins poden assignar rols'
    );
  }

  const { uid } = data;
  
  if (!uid) {
    throw new functions.https.HttpsError(
      'invalid-argument',
      'Cal especificar el UID'
    );
  }

  try {
    // Assignar rol admin
    await admin.auth().setCustomUserClaims(uid, { role: 'admin' });
    
    // Opcional: Guardar log a Firestore
    await admin.firestore().collection('admin_logs').add({
      action: 'add_admin',
      targetUid: uid,
      performedBy: context.auth.uid,
      timestamp: admin.firestore.FieldValue.serverTimestamp()
    });

    return { 
      success: true,
      message: `Usuari ${uid} ara és administrador` 
    };
  } catch (error) {
    throw new functions.https.HttpsError(
      'internal',
      `Error assignant rol: ${error.message}`
    );
  }
});

/**
 * Cloud Function per eliminar rol d'admin
 */
exports.removeAdminRole = functions.https.onCall(async (data, context) => {
  if (!context.auth) {
    throw new functions.https.HttpsError('unauthenticated', 'Cal estar autenticat');
  }

  if (context.auth.token.superAdmin !== true) {
    throw new functions.https.HttpsError('permission-denied', 'No autoritzat');
  }

  const { uid } = data;
  
  try {
    // Eliminar el claim 'role' o assignar un altre rol
    await admin.auth().setCustomUserClaims(uid, { role: null });
    
    await admin.firestore().collection('admin_logs').add({
      action: 'remove_admin',
      targetUid: uid,
      performedBy: context.auth.uid,
      timestamp: admin.firestore.FieldValue.serverTimestamp()
    });

    return { success: true, message: `Rol admin eliminat per ${uid}` };
  } catch (error) {
    throw new functions.https.HttpsError('internal', error.message);
  }
});
```

### Mètode 3: Consola Interactiva de Django

```bash
python manage.py shell
```

```python
from firebase_admin import auth

# Afegir admin
auth.set_custom_user_claims('abc123def456', {'role': 'admin'})

# Comprovar claims
user = auth.get_user('abc123def456')
print(user.custom_claims)

# Eliminar admin
auth.set_custom_user_claims('abc123def456', {'role': None})
```

## Renovació del Token

**Important:** Després de modificar els custom claims, l'usuari **ha de renovar el seu token JWT**.

### Al Client (JavaScript/TypeScript)

```javascript
// Forçar refresh del token
const user = firebase.auth().currentUser;
if (user) {
  const newToken = await user.getIdToken(true); // true = forçar refresh
  console.log('Token renovat:', newToken);
}
```

### Al Client (Flutter/Dart)

```dart
final user = FirebaseAuth.instance.currentUser;
if (user != null) {
  final newToken = await user.getIdToken(true); // forçar refresh
  print('Token renovat: $newToken');
}
```

## Rols Múltiples (Extensió Futura)

El sistema està dissenyat per suportar múltiples rols fàcilment:

```python
# Definir rol d'admin
auth.set_custom_user_claims(uid, {'role': 'admin'})

# Definir rol de moderador
auth.set_custom_user_claims(uid, {'role': 'moderator'})

# Definir rol d'usuari verificat
auth.set_custom_user_claims(uid, {'role': 'verified_user'})

# També pots afegir múltiples claims
custom_claims = {
    'role': 'admin',
    'verified': True,
    'permissions': ['read', 'write', 'delete']
}
auth.set_custom_user_claims(uid, custom_claims)
```

Exemple de permís per múltiples rols:

```python
class IsModeratorOrAdmin(permissions.BasePermission):
    """Permet accés a moderadors i admins"""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        user_claims = getattr(request, 'user_claims', {})
        role = user_claims.get('role')
        return role in ['admin', 'moderator']
```

## Seguretat i Bones Pràctiques

### ✅ Bones Pràctiques

1. **Limita els Administradors**: Només assigna permisos d'admin als usuaris necessaris
2. **Auditoria**: Registra qui assigna/elimina rols d'admin
3. **Validació al Backend**: Mai confiïs només en els claims del client
4. **Renovació de Tokens**: Informa als usuaris que han de renovar el token
5. **Super-Admin**: Considera tenir un super-admin que gestioni altres admins

### ⚠️ Consideracions de Seguretat

1. **Els claims són visibles**: El token JWT es pot descodificar al client (però no modificar)
2. **Límit de mida**: Els custom claims tenen un límit de 1000 bytes
3. **Propagació**: Els canvis de claims no són immediats (cal renovar token)
4. **Revocació**: Si cal revocar permisos immediatament, revoca el token sencer

### 🔒 Recomanacions de Producció

```python
# Implementar auditoria
import logging
audit_logger = logging.getLogger('security.audit')

def log_admin_action(action, target_uid, performed_by):
    audit_logger.info(
        f"Admin action: {action} | Target: {target_uid} | By: {performed_by}"
    )

# Exemple d'ús
log_admin_action('add_admin', 'abc123', request.user.uid)
auth.set_custom_user_claims('abc123', {'admin': True})
```

## Testing

### Tests Unitaris

```python
import pytest
from unittest.mock import Mock

@pytest.fixture
def mock_admin_claims():
    return {'role': 'admin', 'uid': 'test-admin-uid'}

@pytest.fixture
def mock_regular_claims():
    return {'role': 'user', 'uid': 'test-user-uid'}

def test_admin_can_access(api_factory, mock_admin_claims):
    request = api_factory.get('/api/admin/endpoint/')
    request.user_claims = mock_admin_claims
    request.user_uid = mock_admin_claims['uid']
    # ... test logic
```

### Test Manual

1. Crea un usuari de test a Firebase
2. Assigna-li rol d'admin: `python scripts/manage_admins.py add <uid>`
3. Al client, autentica't i obtén el token
4. Crida un endpoint protegit amb el token
5. Verifica l'accés

## Troubleshooting

### Error 403 després d'afegir admin

**Problema**: L'usuari segueix rebent 403 Forbidden després d'afegir-lo com admin.

**Solució**:
```javascript
// Client: Forçar refresh del token
const newToken = await firebase.auth().currentUser.getIdToken(true);
```

### Custom claims no apareixen al token

**Problema**: El token no conté els custom claims.

**Diagnòstic**:
```python
# Backend: Verifica els claims
print(request.user_claims)
```

**Solució**: Verifica que el token s'ha renovat després d'assignar els claims.

### Error "Token has expired"

**Problema**: El token JWT ha caducat.

**Solució**: Els tokens Firebase caduquen cada hora. El client ha de renovar-los automàticament.

## Migració des de FIREBASE_ADMIN_UIDS

Si migres des del sistema anterior amb UIDs al `.env`:

1. **Copia els UIDs actuals**:
   ```bash
   # Al fitxer .env.development
   FIREBASE_ADMIN_UIDS=uid1,uid2,uid3
   ```

2. **Assigna custom claims**:
   ```python
   uids = ['uid1', 'uid2', 'uid3']
   for uid in uids:
       auth.set_custom_user_claims(uid, {'role': 'admin'})
       print(f"✓ {uid}")
   ```

3. **Elimina la variable d'entorn** (ja fet als canvis)

4. **Notifica als admins** que han de renovar el token

## Referències

- [Firebase Custom Claims Documentation](https://firebase.google.com/docs/auth/admin/custom-claims)
- [Firebase Admin SDK Python](https://firebase.google.com/docs/reference/admin/python)
- Django REST Framework Permissions: `api/permissions.py`
- Middleware: `api/middleware/firebase_auth_middleware.py`

---

**Última actualització**: 29 de novembre de 2025
