# Guia — Gestionar administradors i usar els endpoints admin

> **[FET]** comprovat al codi · **[INFERÈNCIA]** deducció · **[NO VERIFICAT]** depèn de config externa.
> Context: [integrations/firebase-auth.md §Custom claims](../integrations/firebase-auth.md#custom-claims) · [flux 11 (cache/health)](../flows/11-admin-cache-health.md) · [flux 5 (revisió de propostes)](../flows/05-refuge-proposals.md).

## Com es decideix qui és admin
Un usuari és admin si el seu ID token porta el **custom claim `role == 'admin'`** (`api/permissions.py:10-21`). El permís `IsFirebaseAdmin` llegeix `request.user_claims`, que el middleware omple amb el token decodificat.

> ⚠️ Les docs antigues parlaven de `admin: true` o de la variable `FIREBASE_ADMIN_UIDS`: **tots dos són obsolets**. La llista d'UIDs a `.env` es va substituir per custom claims (nov. 2025) i `FIREBASE_ADMIN_UIDS` ja no es llegeix enlloc.

Endpoints que el requereixen: `GET /api/refuges-proposals/`, `POST /api/refuges-proposals/{id}/approve|reject/`, `/api/cache/*` (vegeu [ARCHITECTURE §4](../ARCHITECTURE.md)). `IsMediaUploader` també deixa passar admins.

## 1. Obtenir l'UID de l'usuari
- Firebase Console → **Authentication** → cerca l'usuari → copia l'UID.
- Des del client: `auth.currentUser.uid`.

## 2. Afegir / treure / consultar admins (`scripts/manage_admins.py`)
Requereix credencials locals (el script fa `django.setup()` i, si cal, inicialitza Firebase amb `settings.GOOGLE_APPLICATION_CREDENTIALS`) — vegeu [firebase-credentials.md](firebase-credentials.md).
```bash
python scripts/manage_admins.py add <uid>      # posa role='admin' (conserva la resta de claims)
python scripts/manage_admins.py remove <uid>   # elimina el claim 'role'
python scripts/manage_admins.py check <uid>    # mostra email, si és admin i tots els claims
python scripts/manage_admins.py list           # taula de tots els usuaris amb el rol
```
Alternativa puntual (`python manage.py shell`):
```python
from firebase_admin import auth
auth.set_custom_user_claims('<uid>', {'role': 'admin'})   # ⚠️ sobreescriu els altres claims
print(auth.get_user('<uid>').custom_claims)
```

## 3. Refrescar el token (obligatori)
Els claims només arriben al backend amb un **token nou**. Sense refresc, l'usuari continua rebent 403 fins que el token caduca (≈1 h).
```javascript
await auth.currentUser.getIdToken(true);   // JS
```
```dart
await FirebaseAuth.instance.currentUser?.getIdToken(true);   // Flutter
```
O bé logout + login.

## 4. Provar els endpoints de cache
```bash
curl -H "Authorization: Bearer <token_admin>" http://localhost:8000/api/cache/stats/
curl -X DELETE -H "Authorization: Bearer <token_admin>" http://localhost:8000/api/cache/clear/
curl -X DELETE -H "Authorization: Bearer <token_admin>" "http://localhost:8000/api/cache/invalidate/?pattern=refugi_search"
```
Respostes: `stats` → `{connected, keys, memory_used, hits, misses}`; `clear` → `{"message": "Cache netejada correctament"}`; `invalidate` → `{"message": "Claus amb patró \"...\" eliminades correctament"}`.
- `pattern` és una **subcadena**: el servei ja l'embolcalla amb `*…*`. No hi afegeixis `*` ni `:*` ([GOTCHAS #12](../GOTCHAS.md)).
- `clear` esborra **tota** la BD Redis, no només les claus del projecte ([GOTCHAS #16](../GOTCHAS.md)).

A Swagger (`/swagger/`, tag **Cache Admin**): botó **Authorize** → `Bearer <token>` → *Authorize* → prova l'endpoint.

## 5. Tests unitaris
Mocka els claims a la request:
```python
request.user_claims = {'role': 'admin', 'uid': 'test-admin-uid'}
request.user_uid = 'test-admin-uid'
```
(patró usat a `api/tests/test_cache_views.py`).

## Errors habituals
| Símptoma | Causa / solució |
|---|---|
| 403 just després de fer admin un usuari | Token antic: refresca'l (pas 3) |
| 403 amb token refrescat | `check <uid>`: el claim ha de ser exactament `role: "admin"` |
| 401 | Token absent, mal format o caducat ([flux 0](../flows/00-auth-request-pipeline.md)) |
| 400 a `invalidate` | Falta `pattern` |

## Seguretat i bones pràctiques
- Els claims viatgen dins el JWT: el client els pot **llegir** (no modificar). Límit de 1000 bytes.
- Mantén el nombre d'admins al mínim i revisa'l periòdicament (`list`).
- Revocar permisos no és immediat: el token vigent manté el claim fins que caduca. El backend no fa `check_revoked` ([TECH_DEBT B9](../TECH_DEBT.md)).
- Ampliacions possibles (no implementades): més rols (`moderator`), auditoria de canvis de rol, Cloud Function per gestionar rols des d'un super-admin.
