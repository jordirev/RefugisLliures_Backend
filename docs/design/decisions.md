# Decisions de disseny (ADR)

> **[FET]** comprovat al codi · **[INFERÈNCIA]** deducció · **[NO VERIFICAT]** depèn de config externa.
> Registre de decisions preses durant el desenvolupament, amb el motiu i l'estat actual al codi. Patrons resultants: [patterns.md](patterns.md).

## ADR-1 — Vistes basades en classe (`APIView`) en lloc de funcions (`@api_view`)

**Estat:** adoptada. Totes les vistes són `APIView`, excepte `api/views/cache_views.py` (`@api_view`) **[FET]**.

**Context.** Les primeres vistes (`users_collection`, `user_detail`, `health_check`, `refugis_collection`, `refugi_detail`) eren funcions amb `if request.method == ...`. Per aplicar permisos diferents per mètode calia instanciar-los a mà i fins i tot crear objectes artificials per simular la vista:
```python
@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def user_detail(request, uid):
    if request.method in ['PATCH', 'DELETE']:
        view_like = type('ViewLike', (), {'kwargs': {'uid': uid}})()
        if not IsSameUser().has_permission(request, view_like):
            return Response({'error': 'Permís denegat'}, status=403)
```

**Decisió.** Una classe per recurs amb un mètode per verb i permisos per mètode amb `get_permissions()`:
```python
class UserDetailAPIView(APIView):
    def get_permissions(self):
        if self.request.method == 'GET':
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsSameUser()]
    def get(self, request, uid): ...
    def patch(self, request, uid): ...
    def delete(self, request, uid): ...
```

**Conseqüències.**
- ✅ DRF executa els permisos sol i té accés a `self.kwargs` (necessari per a `IsSameUser`).
- ✅ Un handler per verb, `@swagger_auto_schema` per mètode, tests per mètode; canvi transparent per al client.
- ⚠️ Es va triar `APIView` i **no** `GenericAPIView`: no hi ha `get_object()` ni `check_object_permissions()`, per això els permisos `Is*Creator` (`has_object_permission`) **mai s'executen** ([GOTCHAS #1](../GOTCHAS.md), [TECH_DEBT C1](../TECH_DEBT.md)). L'argument original esmentava "fàcil passar a `GenericAPIView`"; no s'ha fet.

## ADR-2 — Middleware + classe d'autenticació DRF

**Estat:** adoptada parcialment. Conviuen `FirebaseAuthenticationMiddleware` i `api.authentication.FirebaseAuthentication` (a `DEFAULT_AUTHENTICATION_CLASSES`) **[FET]**.

**Context.** Inicialment l'autenticació era només un middleware que posava `request.user`. Es va argumentar seguir l'"estàndard DRF" (`BaseAuthentication.authenticate()` → `(user, auth)`) perquè:

| Aspecte | Només middleware | Classe d'autenticació DRF |
|---|---|---|
| `APIClient.force_authenticate()` als tests | no funciona | funciona |
| Combinar mètodes (Session, Token…) | difícil | llista de classes |
| Errors 401/403 i `WWW-Authenticate` | manuals | automàtics |
| Throttling per usuari, Browsable API, Swagger | parcial | integrat |
| Abast | tot Django | només DRF |

**Decisió.** Afegir `FirebaseAuthentication` (DRF) **mantenint** el middleware. La classe DRF reaprofita el que ha posat el middleware i només verifica el token si no hi és (`api/authentication.py:18-70`).

**Allò que es va proposar i NO s'ha aplicat** **[FET]**:
- `DEFAULT_PERMISSION_CLASSES = [IsAuthenticated]` → el default és `AllowAny`; cada vista declara permisos ([GOTCHAS #3](../GOTCHAS.md)).
- `ModelViewSet` → no n'hi ha cap; tot són `APIView` (ADR-1).

**Conseqüències.** Lògica de verificació duplicada ([TECH_DEBT B10](../TECH_DEBT.md)); el middleware decideix 401 abans que DRF, i les rutes excloses per prefix depenen només de `permission_classes` ([GOTCHAS #2](../GOTCHAS.md)).

## ADR-3 — Admins amb custom claims de Firebase

**Estat:** adoptada (nov. 2025). Admin ⇔ claim `role == 'admin'` **[FET]**.

**Context.** Abans, els admins eren una llista d'UIDs a la variable `FIREBASE_ADMIN_UIDS` (`.env`), llegida per `IsFirebaseAdmin`. Afegir-ne un requeria canviar config i redesplegar.

**Decisió.** Custom claims signats per Firebase dins el token; gestió amb `scripts/manage_admins.py`. `FIREBASE_ADMIN_UIDS` es va eliminar de settings. (Una primera versió usava `admin: true`; es va unificar a `role: 'admin'`, que permet més rols en el futur.)

**Conseqüències.** No cal redesplegar per canviar admins; el canvi arriba quan el client refresca el token. Procediment: [guides/admin-management.md](../guides/admin-management.md).
