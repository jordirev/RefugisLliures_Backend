# Endpoints d'Administració de Cache

## Descripció

Els endpoints de cache (`/api/cache/*`) permeten administrar la cache Redis del sistema. Aquests endpoints estan **restringits només a administradors**.

## Autenticació i Autorització

### 1. **Autenticació Firebase**
Tots els endpoints de cache requereixen:
- Token JWT de Firebase vàlid a la capçalera `Authorization: Bearer <token>`

### 2. **Permís IsFirebaseAdmin**
A més de l'autenticació, el UID de l'usuari ha d'estar configurat com a administrador.

### Configuració d'Administradors

Els UIDs dels usuaris administradors es defineixen a la variable d'entorn `FIREBASE_ADMIN_UIDS`:

#### Fitxer `.env.development` o `.env.production`:
```bash
# Format: UIDs separats per comes (sense espais)
FIREBASE_ADMIN_UIDS=abc123def456,xyz789ghi012,otro123uid456
```

#### Variables d'entorn a Render/producció:
```
FIREBASE_ADMIN_UIDS=abc123def456,xyz789ghi012
```

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
**Causa:** El teu UID no està a `FIREBASE_ADMIN_UIDS`

**Solució:**
1. Comprova el teu UID de Firebase
2. Afegeix-lo a la variable d'entorn `FIREBASE_ADMIN_UIDS`
3. Reinicia el servidor Django

### Error 401: No autoritzat
**Causa:** Token JWT invàlid o no proporcionat

**Solució:**
1. Verifica que el token és vàlid
2. Comprova que la capçalera és: `Authorization: Bearer <token>`
3. El token no pot haver caducat

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
- Mai comparteixis els UIDs d'administrador públicament
- Limita els administradors al mínim necessari
- Revisa regularment qui té accés d'administrador
- Els UIDs són sensibles i donen accés a operacions crítiques

## Testing

Per testejar aquests endpoints en desenvolupament:

1. Crea un usuari de test a Firebase
2. Afegeix el seu UID a `.env.development`:
   ```
   FIREBASE_ADMIN_UIDS=uid_del_usuari_de_test
   ```
3. Reinicia el servidor
4. Autentica't amb aquest usuari i obtén el token
5. Utilitza el token per cridar els endpoints
