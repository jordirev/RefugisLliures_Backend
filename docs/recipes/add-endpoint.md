# Recepta — Afegir un endpoint nou

> ## Features migrades a PostgreSQL (`apps/<feature>/`) — patró nou
> Referència: `apps/refuges` (chunk 2). Aquesta recepta descriu a sota el patró **legacy** (Firestore); per a una feature ja migrada, o quan en migris una, el flux és:
> 1. **Ruta** — `apps/<feature>/urls.py` amb `path(...)`/`name=` (mateixos paths i noms que tenia); `api/urls.py` només l'inclou: `path('<prefix>/', include('apps.<feature>.urls'))`. Les rutes niades d'altres features (p. ex. `refuges/<id>/renovations/`) es queden a `api/urls.py` fins que aquestes es migrin. Id de refugi: `<str:id>` i `selectors.parse_refuge_id` (un id que no sigui UUID → 404, no 500).
> 2. **Serializers** — `apps/<feature>/serializers.py`: entrada (`XSearchFiltersSerializer`, `XCreateSerializer`) i sortida (forma exacta del contracte JSON); sense `ModelSerializer`.
> 3. **Selectors** — `apps/<feature>/selectors.py` (lectures: ORM amb `select_related`/`Prefetch`/`ArraySubquery`/`annotate`, **una consulta per cas d'ús**; filtres al `WHERE`; sense cache de dades). Afegeix un test de recompte de consultes (`QueryCounter`).
> 4. **Services** — `apps/<feature>/services.py` (escriptures: `transaction.atomic`, `select_for_update` si hi ha carreres, R2 comprovant el booleà de `delete_file`); llança excepcions de domini (`MediaForbidden`, `MediaNotFound`…).
> 5. **Vista** — `apps/<feature>/views.py`: `APIView` fina amb `permission_classes` explícit (el default és `AllowAny`), crida selectors/services i mapa excepcions → HTTP; el context de RLS el posa el hook. Els errors inesperats es capturen **per punt** i es retornen amb `apps.core.errors.server_error("<missatge específic>", exc, logger=logger)` → `500 {error, error_id}` (l'`error_id` és al log amb la traça); **mai** `str(e)` ni text d'excepció a la resposta. Cal un test per a cada missatge (vegeu `apps/refuges/tests/test_server_errors.py`).
> 6. **Tests** — `apps/<feature>/tests/`: contracte HTTP contra Postgres real (rol `app`), anònim/propi/aliè/admin, errors 400/401/403/404, `QueryCounter`. `pytest.ini` ja inclou `apps` a `testpaths`.
> 7. **Docs** — `docs/ARCHITECTURE.md §4`, el flux a `docs/flows/` i `docs/recipes/`.

> **Patró legacy (Firestore).** Per a una feature nova a PostgreSQL segueix la secció d'`apps/<feature>/` d'aquest document i `apps/renovations/` (views fines, `selectors`, `services` amb excepcions de domini, `constraint_name`, `get_permissions()` per mètode) o `apps/refuges/`. El que segueix descriu el patró dels dominis que encara són a Firestore, exemplificat amb els fitxers legacy de reformes (fins al chunk 8).
>
> Segueix el patró **real** del domini renovations (legacy). Exemple fil conductor: `GET /api/renovations/{id}/summary/` (fictici, només per il·lustrar; **no existeix**).

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
- **No** posis `default=` en camps opcionals d'un update (bug que tenia `UserUpdateSerializer`, corregit al chunk 3 a `apps/accounts/serializers.py`).
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
    permission_classes = [IsAuthenticated, HasProfile]   # el default global és AllowAny!

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

### Errors amb codi i permisos de moderació
Si el client ha de distingir l'error, retorna `coded_error('<codi>', '<missatge>')` (`api/permissions.py`) → `{"error", "code", "message"}`. **Tot endpoint autenticat** ha de dur `HasProfile` just després d'`IsAuthenticated` (`[IsAuthenticated, HasProfile, …]`; 403 `profile_required` si no hi ha fila a `users.users`); l'única excepció és `POST /users/` (el crea) i `/api/cache/*`. Per a endpoints que publiquen o denuncien contingut afegeix `IsNotBlocked` (i `IsAgeConfirmed` si és contingut nou) **després** de `HasProfile`: l'ordre fa que un usuari sense perfil rebi `profile_required` i no `age_not_confirmed`.

## 6. Tests — `api/tests/<domini>/`
- Vista: mocka el controller **al mòdul de la vista**: `@patch('api.views.renovation_views.RenovationController')`; crea la request amb `APIRequestFactory` i posa `request.user_uid` (`api/tests/renovation/test_views.py:66-89`).
  - ⚠️ Els tests existents fan `view.cls.permission_classes = []` (`api/tests/renovation/test_views.py:101-102`), que **muta la classe**; des del chunk 3 el `conftest.py` arrel la restaura després de cada test (`_restore_view_policies`), però és preferible `patch.object(View, 'permission_classes', [])` **[FET]**.
- Controller: mocka els DAOs al mòdul del controller.
- DAO: `@patch('api.daos.<domini>_dao.FirestoreService')` + `@patch('api.daos.<domini>_dao.cache_service')` (`api/tests/renovation/test_daos.py:60-82`).
- Afegeix el marker si cal (`pytest.ini`, `--strict-markers`: només markers declarats).
- Executa: `pytest api/tests/<domini> -q`.

## Checklist
- [ ] Ruta a `api/urls.py` · [ ] `permission_classes` explícits · [ ] Swagger · [ ] Serializer alineat amb model · [ ] Controller retorna tupla i comprova propietat · [ ] DAO invalida cache correctament · [ ] Tests de vista/controller/DAO · [ ] Actualitzar `docs/ARCHITECTURE.md §4` i el flux corresponent.
