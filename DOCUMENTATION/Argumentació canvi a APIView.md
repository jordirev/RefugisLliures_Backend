# Refactorització de Views: De Function-Based a Class-Based (APIView)

## Context del canvi

S'ha refactoritzat totes les views de l'API (tant d'usuaris com de refugis) passant de vistes basades en funcions (`@api_view`) a vistes basades en classes (`APIView`). Aquest canvi afecta els següents endpoints:

### Views d'usuaris
- `users_collection` → `UsersCollectionAPIView`
- `user_detail` → `UserDetailAPIView`

### Views de refugis
- `health_check` → `HealthCheckAPIView`
- `refugis_collection` → `RefugisCollectionAPIView`
- `refugi_detail` → `RefugiDetailAPIView`

## Motivació del canvi

### 1. Gestió de permisos per mètode HTTP

**Problema anterior:**
```python
@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def user_detail(request, uid):
    # Comprovació manual de permisos
    if request.method in ['PATCH', 'DELETE']:
        perm = IsSameUser()
        view_like = type('ViewLike', (), {'kwargs': {'uid': uid}})()
        if not perm.has_permission(request, view_like):
            return Response({'error': 'Permís denegat'}, status=403)
```

**Solució amb APIView:**
```python
class UserDetailAPIView(APIView):
    def get_permissions(self):
        if self.request.method == 'GET':
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsSameUser()]
```

**Beneficis:**
- ✅ Eliminació de comprovacions manuals de permisos
- ✅ No cal crear objectes artificials (`ViewLike`) per simular el context
- ✅ DRF executa automàticament les validacions de permisos
- ✅ Codi més net i idiomàtic

### 2. Separació clara de responsabilitats

**Abans:**
```python
@api_view(['GET', 'PATCH', 'DELETE'])
def user_detail(request, uid):
    if request.method == 'GET':
        return _get_user(request, uid)
    elif request.method == 'PATCH':
        return _update_user(request, uid)
    elif request.method == 'DELETE':
        return _delete_user(request, uid)
```

**Després:**
```python
class UserDetailAPIView(APIView):
    def get(self, request, uid):
        # Lògica GET
    
    def patch(self, request, uid):
        # Lògica PATCH
    
    def delete(self, request, uid):
        # Lògica DELETE
```

**Beneficis:**
- ✅ Cada mètode HTTP té el seu handler específic
- ✅ No calen condicionals `if request.method`
- ✅ Millor llegibilitat i mantenibilitat
- ✅ Més fàcil navegar pel codi

### 3. Encapsulació i cohesió

**Abans:** Funcions helper externes
```python
def user_detail(request, uid):
    return _get_user(request, uid)

def _get_user(request, uid):
    # Lògica separada del context
```

**Després:** Tot dins la classe
```python
class UserDetailAPIView(APIView):
    def get(self, request, uid):
        # Tota la lògica aquí dins
```

**Beneficis:**
- ✅ Tota la lògica relacionada està junta
- ✅ No hi ha funcions "orfes" fora de context
- ✅ Millor encapsulació seguint principis OOP
- ✅ Stack traces més nets en cas d'errors

### 4. Integració nativa amb DRF

**APIView proporciona:**
- ✅ Gestió automàtica de permisos (`permission_classes` i `get_permissions()`)
- ✅ Accés a `self.kwargs` per a permisos que depenen de paràmetres URL
- ✅ Millor integració amb serializers (`get_serializer_class()`)
- ✅ Suport per throttling, versioning, i renderer/parser classes
- ✅ Hooks per a comportaments personalitzats (`perform_update`, etc.)

### 5. Documentació Swagger més precisa

Amb APIView, els decoradors `@swagger_auto_schema` s'apliquen directament als mètodes individuals, resultant en una documentació més clara i específica per a cada operació HTTP.

## Beneficis generals

### Mantenibilitat
- Codi més net i organitzat
- Més fàcil afegir nous endpoints o modificar existents
- Reducció de codi boilerplate

### Extensibilitat
- Fàcil afegir mixins o heretar de GenericAPIView
- Possibilitat de crear classes base personalitzades
- Millor suport per a funcionalitats futures

### Testabilitat
- Més fàcil fer mock de mètodes individuals
- Tests més específics per mètode HTTP
- Millor aïllament de la lògica

### Consistència
- Totes les views segueixen el mateix patró
- Coherència amb les millors pràctiques de DRF
- Més familiar per a desenvolupadors amb experiència en DRF

## Exemple complet: UserDetailAPIView

```python
class UserDetailAPIView(APIView):
    """
    Gestiona operacions sobre un usuari específic:
    - GET: qualsevol usuari autenticat
    - PATCH/DELETE: només el mateix usuari
    """
    
    def get_permissions(self):
        """Permisos dinàmics segons el mètode HTTP"""
        if self.request.method == 'GET':
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsSameUser()]
    
    @swagger_auto_schema(...)
    def get(self, request, uid):
        """Lògica completa per obtenir usuari"""
        try:
            controller = UserController()
            success, user, error_message = controller.get_user_by_uid(uid)
            
            if not success:
                return Response({'error': error_message}, status=404)
            
            serializer = UserSerializer(user)
            return Response(serializer.data, status=200)
            
        except Exception as e:
            logger.error(f"Error en get_user: {str(e)}")
            return Response({'error': 'Error intern del servidor'}, status=500)
    
    # patch() i delete() segueixen el mateix patró
```

## Comparativa: Abans vs Després

| Aspecte | Function-Based Views | Class-Based Views (APIView) |
|---------|---------------------|---------------------------|
| **Permisos per mètode** | Comprovació manual amb hacks | `get_permissions()` natiu |
| **Separació de mètodes** | `if request.method` | Mètodes individuals |
| **Encapsulació** | Funcions externes | Tot dins la classe |
| **Línies de codi** | Més verbós | Més concís |
| **Mantenibilitat** | Mitjana | Alta |
| **Idiomàtic DRF** | Menys | Més |
| **Testabilitat** | Bona | Excel·lent |

## Conclusió

La refactorització a APIView millora significativament la qualitat del codi, segueix les millors pràctiques de Django REST Framework, i proporciona una base més sòlida i mantenible per al futur desenvolupament de l'API.

El canvi és **totalment transparent** per als clients de l'API: els endpoints, permisos i comportament funcional romanen idèntics, però amb una implementació més robusta i professional.

