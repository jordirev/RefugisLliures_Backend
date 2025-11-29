# Endpoints d'Administració de Cache

## Descripció

Els endpoints de cache (`/api/cache/*`) permeten administrar la cache Redis del sistema. Aquests endpoints estan **restringits només a administradors**.

## Autenticació i Autorització

### 1. **Autenticació Firebase**
Tots els endpoints de cache requereixen:
- Token JWT de Firebase vàlid a la capçalera `Authorization: Bearer <token>`

### 2. **Permís IsFirebaseAdmin**
A més de l'autenticació, l'usuari ha d'tenir el **custom claim** `role` amb valor `"admin"`.

### Configuració d'Administradors

Els administradors es defineixen mitjançant **Custom Claims de Firebase Auth** (1a Generació). Un usuari és administrador si té el custom claim `role: "admin"` al seu token JWT.

#### Com afegir administradors

**Opció 1: Firebase Admin SDK (Recomanat)**

```python
from firebase_admin import auth

# Assignar rol d'admin a un usuari
uid = "abc123def456"
auth.set_custom_user_claims(uid, {'role': 'admin'})
print(f"Usuari {uid} ara és administrador")
```

**Opció 2: Firebase Console (Cloud Functions)**

Pots crear una Cloud Function per gestionar rols:

```javascript
const admin = require('firebase-admin');

exports.addAdminRole = functions.https.onCall(async (data, context) => {
  // Verificar que qui crida és super-admin
  if (context.auth.token.superAdmin !== true) {
    throw new functions.https.HttpsError('permission-denied', 'No autoritzat');
  }
  
  // Assignar rol admin
  await admin.auth().setCustomUserClaims(data.uid, {
    role: 'admin'
  });
  
  return { message: `Usuari ${data.uid} ara és admin` };
});
```

**Opció 3: Script d'administració**

Pots crear un script Python per gestionar administradors:

```python
# scripts/manage_admins.py
import firebase_admin
from firebase_admin import credentials, auth

cred = credentials.Certificate("env/firebase-service-account.json")
firebase_admin.initialize_app(cred)

def add_admin(uid):
    auth.set_custom_user_claims(uid, {'admin': True})
    print(f"✓ {uid} és ara administrador")

def remove_admin(uid):
    auth.set_custom_user_claims(uid, {'admin': False})
    print(f"✓ Permisos d'admin eliminats per {uid}")

def list_admins():
    # Nota: No hi ha API directa per llistar tots els admins
    # Cal iterar per tots els usuaris
    page = auth.list_users()
    admins = []
    while page:
        for user in page.users:
            claims = user.custom_claims or {}
            if claims.get('admin'):
                admins.append(user.uid)
        page = page.get_next_page()
    return admins

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Ús: python manage_admins.py [add|remove|list] [uid]")
        sys.exit(1)
    
    action = sys.argv[1]
    if action == "add" and len(sys.argv) == 3:
        add_admin(sys.argv[2])
    elif action == "remove" and len(sys.argv) == 3:
        remove_admin(sys.argv[2])
    elif action == "list":
        admins = list_admins()
        print(f"Administradors: {admins}")
```

⚠️ **Important:** Després d'afegir/eliminar custom claims, l'usuari ha de **renovar el seu token JWT** per que els canvis tinguin efecte. Els clients han de fer logout/login o forçar un refresh del token.

## Com obtenir el UID d'un usuari Firebase

1. **A la consola de Firebase:**
   - Ves a Authentication
   - Busca l'usuari
   - Copia el UID

2. **Des de l'aplicació client:**
   ```javascript
   const user = firebase.auth().currentUser;
   console.log(user.uid); // Aquest és el UID
   ```

3. **Des del backend (logs):**
   - El middleware Firebase registra el UID quan un usuari fa login

## Endpoints Disponibles

### 1. GET `/api/cache/stats/`
Obté estadístiques de la cache Redis.

**Resposta 200:**
```json
{
  "connected": true,
  "keys": 42,
  "memory_used": "1.5M",
  "hits": 1234,
  "misses": 56
}
```

### 2. DELETE `/api/cache/clear/`
Neteja tota la cache.

**Resposta 200:**
```json
{
  "message": "Cache netejada correctament"
}
```

### 3. DELETE `/api/cache/invalidate/?pattern=refugi_*`
Elimina claus que coincideixin amb un patró.

**Paràmetres:**
- `pattern` (query, requerido): Patró de Redis (ex: `refugi_*`, `user_*`)

**Resposta 200:**
```json
{
  "message": "Claus amb patró \"refugi_*\" eliminades correctament"
}
```

## Codis d'Error

- **401 Unauthorized**: Token JWT no vàlid o no proporcionat
- **403 Forbidden**: L'usuari està autenticat però no és administrador
- **400 Bad Request**: Paràmetres incorrectes (només per `/invalidate`)
- **500 Internal Server Error**: Error del servidor o Redis

## Documentació Swagger

A Swagger (`/swagger/`), aquests endpoints:
1. Mostren el candau 🔒 indicant que requereixen autenticació
2. Es poden provar proporcionant el token JWT
3. Tenen el tag "Cache Admin" per identificar-los fàcilment
4. Indiquen clarament a la descripció que requereixen ser administrador

### Com provar-los a Swagger:

1. Fes clic al botó **Authorize** (candau) a la part superior
2. Introdueix el token: `Bearer <el_teu_token_jwt>`
3. Fes clic a **Authorize** i després **Close**
4. Ara pots provar els endpoints de cache si el teu UID és administrador

## Errors Comuns

### Error 403: Permís denegat
**Causa:** L'usuari no té el custom claim `admin: true`

**Solució:**
1. Verifica que l'usuari té el custom claim admin assignat
2. Utilitza el script `manage_admins.py` o Firebase Admin SDK per assignar-lo
3. L'usuari ha de renovar el seu token JWT (logout/login)

### Error 401: No autoritzat
**Causa:** Token JWT invàlid o no proporcionat

**Solució:**
1. Verifica que el token és vàlid
2. Comprova que la capçalera és: `Authorization: Bearer <token>`
3. El token no pot haver caducat

### Els canvis de permisos no tenen efecte
**Causa:** El token JWT ja estava emès abans d'afegir els custom claims

**Solució:**
1. Força un refresh del token al client
2. O simplement fes logout i login de nou

## Exemple d'ús amb curl

```bash
# 1. Obtenir estadístiques
curl -X GET "http://localhost:8000/api/cache/stats/" \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIsImtpZCI6..."

# 2. Neteja completa
curl -X DELETE "http://localhost:8000/api/cache/clear/" \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIsImtpZCI6..."

# 3. Invalidar patró
curl -X DELETE "http://localhost:8000/api/cache/invalidate/?pattern=refugi_*" \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIsImtpZCI6..."
```

## Seguretat

⚠️ **Important:**
- Els custom claims s'inclouen al token JWT i són visibles al client
- Limita els administradors al mínim necessari
- Revisa regularment qui té permisos d'administrador
- Considera implementar un sistema d'auditoria per accions d'admin
- Els custom claims donen accés a operacions crítiques

## Testing

Per testejar aquests endpoints en desenvolupament:

1. Crea un usuari de test a Firebase
2. Assigna-li el rol d'admin amb el script `manage_admins.py`:
   ```bash
   python scripts/manage_admins.py add uid_del_usuari_de_test
   ```
3. Autentica't amb aquest usuari i obtén el token (hauràs de fer login)
4. Utilitza el token per cridar els endpoints

**Alternativa per tests unitaris:**

Als tests, pots mockejar els custom claims:
```python
request.user_claims = {'role': 'admin', 'uid': 'test-admin-uid'}
```
