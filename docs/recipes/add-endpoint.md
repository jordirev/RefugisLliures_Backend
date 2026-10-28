# Recepta — Afegir un endpoint nou

> ## Features migrades a PostgreSQL (`apps/<feature>/`) — patró nou
> Referència: `apps/refuges` (chunk 2). Per a una feature nova o existent, el flux és:
> 1. **Ruta** — `apps/<feature>/urls.py` amb `path(...)`/`name=` (mateixos paths i noms que tenia); `api/urls.py` només l'inclou: `path('<prefix>/', include('apps.<feature>.urls'))`. Les rutes niades d'altres features (p. ex. `refuges/<id>/renovations/`) es queden a `api/urls.py` fins que aquestes es migrin. Id de refugi: `<str:id>` i `selectors.parse_refuge_id` (un id que no sigui UUID → 404, no 500).
> 2. **Serializers** — `apps/<feature>/serializers.py`: entrada (`XSearchFiltersSerializer`, `XCreateSerializer`) i sortida (forma exacta del contracte JSON); sense `ModelSerializer`.
> 3. **Selectors** — `apps/<feature>/selectors.py` (lectures: ORM amb `select_related`/`Prefetch`/`ArraySubquery`/`annotate`, **una consulta per cas d'ús**; filtres al `WHERE`; sense cache de dades). Afegeix un test de recompte de consultes (`QueryCounter`).
> 4. **Services** — `apps/<feature>/services.py` (escriptures: `transaction.atomic`, `select_for_update` si hi ha carreres, R2 comprovant el booleà de `delete_file`); llança excepcions de domini (`MediaForbidden`, `MediaNotFound`…).
> 5. **Vista** — `apps/<feature>/views.py`: `APIView` fina amb `permission_classes` explícit (el default és `AllowAny`), crida selectors/services i mapa excepcions → HTTP; el context de RLS el posa el hook. Els errors inesperats es capturen **per punt** i es retornen amb `apps.core.errors.server_error("<missatge específic>", exc, logger=logger)` → `500 {error, error_id}` (l'`error_id` és al log amb la traça); **mai** `str(e)` ni text d'excepció a la resposta. Cal un test per a cada missatge (vegeu `apps/refuges/tests/test_server_errors.py`).
> 6. **Tests** — `apps/<feature>/tests/`: contracte HTTP contra Postgres real (rol `app`), anònim/propi/aliè/admin, errors 400/401/403/404, `QueryCounter`. `pytest.ini` ja inclou `apps` a `testpaths`.
> 7. **Docs** — `docs/ARCHITECTURE.md §4`, el flux a `docs/flows/` i `docs/recipes/`.

> Exemple de referència: `apps/renovations/` (views fines, `selectors`, `services` amb excepcions de domini, `constraint_name`, `get_permissions()` per mètode) o `apps/refuges/`. Després de la neteja (chunk 11, D43) no queda cap domini amb el patró Controller/DAO/Firestore: el que descriuen els passos de dalt és l'únic patró.

## 0. Abans de començar
- Decideix la feature (`apps/<feature>/`). Si és nova, primer [add-model.md](add-model.md).
- Mira si la ruta caurà sota `/api/refuges/` (exclosa del middleware → **sense token també arriba a la vista**; la protecció la donen només els `permission_classes`). Vegeu [GOTCHAS #2](../GOTCHAS.md).
- Convencions de ruta: paràmetres `<str:...>`, `name` en snake_case, URL en anglès amb barra final.

## Detalls de la vista
- Permisos per mètode: `get_permissions()` (vegeu `apps/renovations/views.py`). Admin: `IsFirebaseAdmin`. Recurs propi per `uid` a la URL: `IsSameUser`.
- Exemples Swagger a `api/utils/swagger_examples.py`; respostes d'error a `api/utils/swagger_error_responses.py`.
- **Propietat**: comprova-la al service (`has_object_permission` no s'executa).
- El mapatge error→HTTP el fan les excepcions de domini (i `constraint_name`), mai el text del missatge.

### Errors amb codi i permisos de moderació
Si el client ha de distingir l'error, retorna `coded_error('<codi>', '<missatge>')` (`api/permissions.py`) → `{"error", "code", "message"}`. **Tot endpoint autenticat** ha de dur `HasProfile` just després d'`IsAuthenticated` (`[IsAuthenticated, HasProfile, …]`; 403 `profile_required` si no hi ha fila a `users.users`); l'única excepció és `POST /users/` (el crea). Per a endpoints que publiquen o denuncien contingut afegeix `IsNotBlocked` (i `IsAgeConfirmed` si és contingut nou) **després** de `HasProfile`: l'ordre fa que un usuari sense perfil rebi `profile_required` i no `age_not_confirmed`.

## Tests — `apps/<feature>/tests/`
- Vistes: contracte HTTP contra Postgres real (rol `app`); per canviar permisos usa `patch.object(View, 'permission_classes', [...])` (el `conftest.py` arrel restaura les polítiques després de cada test).
- Firebase Auth es mocka amb la fixture `firebase_accounts`; Firebase Admin real està bloquejat (`_block_real_firebase`).
- Afegeix el marker si cal (`pytest.ini`, `--strict-markers`).
- Executa: `pytest apps/<feature> -q`.

## Checklist
- [ ] Ruta a `apps/<feature>/urls.py` (i inclosa des d'`api/urls.py`) · [ ] `permission_classes` explícits (`IsAuthenticated, HasProfile, …`) · [ ] Swagger · [ ] Serializer alineat amb el `CHECK` de la BD · [ ] Service comprova propietat i llança excepcions de domini · [ ] `server_error` als 500 · [ ] Tests (contracte, permisos, recomptes de consultes) · [ ] Actualitzar `docs/ARCHITECTURE.md §4` i el flux corresponent.
