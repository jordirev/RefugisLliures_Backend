# Guia — Cridar l'API amb un token de Firebase (client, cURL, Swagger)

> **[FET]** comprovat al codi · **[INFERÈNCIA]** deducció · **[NO VERIFICAT]** depèn de config externa.
> Com es verifica el token al backend: [flux 0](../flows/00-auth-request-pipeline.md). Quins endpoints són públics o privats: [ARCHITECTURE §4](../ARCHITECTURE.md).

## Resum
1. El client fa login amb **Firebase Auth** (el backend no crea comptes).
2. Obté l'**ID token** (JWT, caduca en ≈1 h).
3. L'envia a cada petició: `Authorization: Bearer <idToken>`.
4. El backend el verifica; si no és vàlid → 401. Si és vàlid però no té permís → 403.

Públics (sense token): `GET /api/health/`, `GET /api/refuges/`, `GET /api/refuges/{id}/`, `/swagger/`, `/redoc/`. Tota la resta requereix token (i alguns, a més, `IsSameUser` o admin).

> ⚠️ Un token **caducat o invàlid** a una ruta pública també dona 401: no s'ignora ([GOTCHAS #4](../GOTCHAS.md)).

## 1. Obtenir el token (JS / Firebase v9)
```javascript
import { getAuth, signInWithEmailAndPassword } from 'firebase/auth';
const auth = getAuth(app);
const cred = await signInWithEmailAndPassword(auth, email, password);
const token = await cred.user.getIdToken();          // getIdToken(true) força refresc
```

## 2. Fer peticions
```javascript
async function callAPI(path, options = {}) {
  const user = auth.currentUser;
  if (!user) throw new Error('No autenticat');
  const token = await user.getIdToken();              // el SDK el renova si cal
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: { ...options.headers, Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
  });
  if (res.status === 401) throw new Error('Token invàlid o expirat');   // refrescar / login
  if (res.status === 403) throw new Error('Permís denegat');            // p. ex. uid d'un altre usuari
  if (!res.ok) throw new Error(`Error ${res.status}`);
  return res.status === 204 ? null : res.json();
}

const me = await callAPI(`/api/users/${auth.currentUser.uid}/`);
```
Per a pujades (`/media/`, `/avatar/`, experiències) envia `multipart/form-data` i **no** fixis `Content-Type` a mà.

## 3. Provar amb cURL
```bash
curl http://localhost:8000/api/health/                                   # públic → 200
curl http://localhost:8000/api/users/<uid>/                              # sense token → 401
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/users/<uid>/   # → 200
curl -X PATCH -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
     -d '{"username": "nou_nom"}' http://localhost:8000/api/users/<uid>/   # només el propi uid
```

## 4. Provar amb Swagger
1. `http://localhost:8000/swagger/` → botó **Authorize**.
2. Valor: `Bearer <token>` → *Authorize* → *Close*.
3. Obre l'endpoint → *Try it out* → *Execute*.

## Errors d'autenticació
| HTTP | Missatge (`message`) | Què fer |
|---|---|---|
| 401 | `Token d'autenticació no proporcionat` | Afegir el header |
| 401 | `Format de token invàlid` | Format exacte `Bearer <token>` |
| 401 | `Token expirat` | `getIdToken(true)` i reintentar |
| 401 | `Token invàlid` | Token d'un altre projecte Firebase o corrupte |
| 403 | (DRF) | L'`uid` de la URL no és el teu (`IsSameUser`) o no ets admin |
| 500 | — | Backend sense credencials de Firebase ([firebase-credentials.md](firebase-credentials.md)) |

Llista completa i línies de codi: [flux 0 §Errors](../flows/00-auth-request-pipeline.md#errors).
