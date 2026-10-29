# Guia — Gestionar administradors i usar els endpoints admin

> **[FET]** comprovat al codi · **[INFERÈNCIA]** deducció · **[NO VERIFICAT]** depèn de config externa.
> Context: [integrations/firebase-auth.md §Custom claims](../integrations/firebase-auth.md#custom-claims) · [flux 11 (health)](../flows/11-admin-cache-health.md) · [flux 5 (revisió de propostes)](../flows/05-refuge-proposals.md).

## Com es decideix qui és admin
Un usuari és admin si el seu ID token porta el **custom claim `role == 'admin'`** (`apps/auth/permissions.py:10-21`). El permís `IsFirebaseAdmin` llegeix `request.user_claims`, que el middleware omple amb el token decodificat.

> ⚠️ Les docs antigues parlaven de `admin: true` o de la variable `FIREBASE_ADMIN_UIDS`: **tots dos són obsolets**. La llista d'UIDs a `.env` es va substituir per custom claims (nov. 2025) i `FIREBASE_ADMIN_UIDS` ja no es llegeix enlloc.

Endpoints que el requereixen: `GET /api/refuges-proposals/`, `POST /api/refuges-proposals/{id}/approve|reject/` (vegeu [ARCHITECTURE §4](../ARCHITECTURE.md)). L'esborrat d'un mitjà de refugi també deixa passar admins (comprovació de propietat a `apps/refuges/services.py: delete_media`).

## 1. Obtenir l'UID de l'usuari
- Firebase Console → **Authentication** → cerca l'usuari → copia l'UID.
- Des del client: `auth.currentUser.uid`.

## 2. Afegir / treure / consultar admins (`scripts/manage_admins.py`)
Requereix credencials locals (el script fa `django.setup()` i, si cal, inicialitza Firebase amb `settings.GOOGLE_APPLICATION_CREDENTIALS`) — vegeu [firebase-credentials.md](firebase-credentials.md).
```bash
python scripts/manage_admins.py add <uid>      # posa role='admin' (conserva la resta de claims) i crea la fila de users + perfil a PostgreSQL
python scripts/manage_admins.py remove <uid>   # elimina el claim 'role'
python scripts/manage_admins.py check <uid>    # mostra email, si és admin i tots els claims
python scripts/manage_admins.py list           # taula de tots els usuaris amb el rol
```
**Perfil a PostgreSQL (chunk 3).** Tot endpoint autenticat exigeix fila a `users.users` (`HasProfile`, 403 `profile_required`), i això també val per als admins (inclosos `/api/refuges-proposals/` i `/api/admin/media-reports/`; no `/api/cache/*`). Per això `add` també crea la fila d'usuari + perfil públic amb `services.ensure_user` dins `system_context()` (`INSERT … ON CONFLICT DO NOTHING`: no trepitja un perfil existent; idempotent). Requereix `DATABASE_URL_APP` (rol `app`) a l'entorn del script; si falla el pas de PostgreSQL, el claim ja s'ha posat: torna a executar `add`. `remove` **no** esborra la fila d'usuari. L'admin pot, alternativament, fer `POST /api/users/` des de l'app.

Alternativa puntual (`python manage.py shell`; **no** crea el perfil):
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

## 4. Provar un endpoint d'admin
Els endpoints de cache (`/api/cache/*`) han desaparegut al chunk 11 (D43). Exemple amb un endpoint d'admin vigent:
```bash
curl -H "Authorization: Bearer <token_admin>" http://localhost:8000/api/refuges-proposals/
```
A Swagger (`/swagger/`): botó **Authorize** → `Bearer <token>` → *Authorize* → prova l'endpoint.

## 5. Tests unitaris
Mocka els claims a la request:
```python
request.user_claims = {'role': 'admin', 'uid': 'test-admin-uid'}
request.user_uid = 'test-admin-uid'
```
(patró de les vistes d'admin de `apps/proposals/tests/`).

## Errors habituals
| Símptoma | Causa / solució |
|---|---|
| 403 just després de fer admin un usuari | Token antic: refresca'l (pas 3) |
| 403 `profile_required` a un endpoint d'admin | L'admin no té fila a `users.users`: torna a executar `manage_admins.py add <uid>` o `POST /api/users/` |
| 403 amb token refrescat | `check <uid>`: el claim ha de ser exactament `role: "admin"` |
| 401 | Token absent, mal format o caducat ([flux 0](../flows/00-auth-request-pipeline.md)) |
| 400 a `invalidate` | Falta `pattern` |

## Seguretat i bones pràctiques
- Els claims viatgen dins el JWT: el client els pot **llegir** (no modificar). Límit de 1000 bytes.
- Mantén el nombre d'admins al mínim i revisa'l periòdicament (`list`).
- Revocar permisos no és immediat: el token vigent manté el claim fins que caduca. El backend no fa `check_revoked` ([TECH_DEBT B9](../TECH_DEBT.md)).
- Ampliacions possibles (no implementades): més rols (`moderator`), auditoria de canvis de rol, Cloud Function per gestionar rols des d'un super-admin.
