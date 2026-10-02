# Recepta — Afegir un endpoint nou

> Segueix el patró **real** del domini renovations. Exemple fil conductor: `GET /api/renovations/{id}/summary/` (fictici, només per il·lustrar; **no existeix**).

## 0. Abans de començar
- Decideix el domini (fitxers `api/*/<domini>_*.py`). Si el domini és nou, primer [add-model.md](add-model.md).
- Mira si la ruta caurà sota `/api/refuges/` (exclosa del middleware → **sense token també arriba a la vista**; la protecció la donen només els `permission_classes`). Vegeu [GOTCHAS #2](../GOTCHAS.md).

## 1. Ruta — `api/urls.py`
Importa la vista al bloc d'imports del domini i afegeix el `path` al bloc corresponent, amb comentari dels mètodes (convenció de `api/urls.py:88-91`):
```python
path('renovations/<str:id>/summary/', RenovationSummaryAPIView.as_view(), name='renovation_summary'),  # GET /renovations/{id}/summary/
```
Convencions: paràmetres `<str:...>`, `name` en snake_case, URL en anglès amb barra final.

## 2. Serializers — `api/serializers/<domini>_serializer.py`
- Entrada: `XCreateSerializer` / `XUpdateSerializer` (`serializers.Serializer`, no `ModelSerializer`). Reutilitza mixins de validació (p. ex. `DateValidationMixin`, `api/serializers/renovation_serializer.py:9-45`).
- Sortida: `XSerializer` que rep `model.to_dict()`.
- **No** posis `default=` en camps opcionals d'un update (bug `api/serializers/user_serializer.py:150`).
- Assegura't que les regles coincideixen amb el `__post_init__` del model (bug `ini_date == fin_date`).

## 3. Controller — `api/controllers/<domini>_controller.py`
```python
def get_renovation_summary(self, renovation_id: str, user_uid: str) -> Tuple[bool, Optional[dict], Optional[str]]:
    try:
        renovation = self.renovation_dao.get_renovation_by_id(renovation_id)
        if not renovation:
            return False, None, f"Renovation amb ID {renovation_id} no trobada"
        # comprovacions de propietat AQUÍ (no a has_object_permission)
        return True, {...}, None
    except Exception as e:
        logger.error(f"Error en get_renovation_summary: {str(e)}")
        return False, None, f"Error intern: {str(e)}"
```
Patró: `api/controllers/renovation_controller.py:63-82` (lectura) i `:100-154` (escriptura amb comprovació de creador).
- Retorn: `(success, data, error)`; per a operacions sense dades, `(success, error)`.
- **Propietat**: compara `creator_uid` amb `user_uid` al controller (`api/controllers/renovation_controller.py:118-120`). `has_object_permission` no s'executa.

## 4. DAO — `api/daos/<domini>_dao.py`
- Lectura amb cache: `generate_key` → `get` → Firestore → `set(timeout=get_timeout(...))` (`api/daos/renovation_dao.py:69-109`).
- Llistes: `cache_service.get_or_fetch_list(...)` amb `fetch_all`, `fetch_single`, `get_id` (`api/daos/renovation_dao.py:111-176`).
- Escriptura: després de `set/update/delete`, **invalida** el detall i les llistes afectades (`api/daos/renovation_dao.py:58-60`). Usa `delete_pattern('<prefix>:')` sense `:*`.
- Logging: `logger.log(23, "Firestore READ: collection=... document=...")`.
- Arrays/comptadors: `firestore.ArrayUnion/ArrayRemove/Increment`, no read-modify-write.

## 5. Vista — `api/views/<domini>_views.py`
```python
class RenovationSummaryAPIView(APIView):
    permission_classes = [IsAuthenticated]   # el default global és AllowAny!

    @swagger_auto_schema(
        operation_description="...",
        responses={200: openapi.Response(description='...', examples={'application/json': EXAMPLE_...}),
                   401: ERROR_401_UNAUTHORIZED, 404: ERROR_404_RENOVATION_NOT_FOUND, 500: ERROR_500_INTERNAL_ERROR}
    )
    def get(self, request, id):
        try:
            controller = RenovationController()
            success, data, error = controller.get_renovation_summary(id, request.user_uid)
            if not success:
                if 'no trobada' in error.lower():
                    return Response({'error': error}, status=status.HTTP_404_NOT_FOUND)
                return Response({'error': error}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            return Response(data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f'Error ...: {str(e)}')
            return Response({'error': 'Error intern del servidor'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
```
- Permisos per mètode: `get_permissions()` com `api/views/renovation_views.py:182-190`.
- Admin: `IsFirebaseAdmin`. Recurs propi per `uid` a la URL: `IsSameUser`.
- Exemples Swagger a `api/utils/swagger_examples.py`; respostes d'error a `api/utils/swagger_error_responses.py`.
- **No** facis `{'error': ERROR_500_INTERNAL_ERROR}` (és un objecte `openapi.Response`, no un text); posa un string.
- El mapatge error→HTTP es fa per subcadena del missatge: si en crees un de nou, documenta'l i fes-lo coincidir amb el controller.

## 6. Tests — `api/tests/<domini>/`
- Vista: mocka el controller **al mòdul de la vista**: `@patch('api.views.renovation_views.RenovationController')`; crea la request amb `APIRequestFactory` i posa `request.user_uid` (`api/tests/renovation/test_views.py:66-89`).
  - ⚠️ Els tests existents fan `view.cls.permission_classes = []` (`api/tests/renovation/test_views.py:101-102`), que **muta la classe** per a la resta del procés de test **[FET]**. Preferible `patch.object(View, 'permission_classes', [])`.
- Controller: mocka els DAOs al mòdul del controller.
- DAO: `@patch('api.daos.<domini>_dao.FirestoreService')` + `@patch('api.daos.<domini>_dao.cache_service')` (`api/tests/renovation/test_daos.py:60-82`).
- Afegeix el marker si cal (`pytest.ini`, `--strict-markers`: només markers declarats).
- Executa: `pytest api/tests/<domini> -q`.

## Checklist
- [ ] Ruta a `api/urls.py` · [ ] `permission_classes` explícits · [ ] Swagger · [ ] Serializer alineat amb model · [ ] Controller retorna tupla i comprova propietat · [ ] DAO invalida cache correctament · [ ] Tests de vista/controller/DAO · [ ] Actualitzar `docs/ARCHITECTURE.md §4` i el flux corresponent.
