# Recepta — Afegir un model nou (entitat persistida a Firestore)

> Els "models" **no** són models de Django: són `@dataclass` persistits a Firestore via DAO. No hi ha migracions.

## 1. Model — `api/models/<entitat>.py`
Patró: `api/models/renovation.py`.
```python
@dataclass
class Foo:
    id: str
    creator_uid: str
    refuge_id: str
    created_at: str               # ISO string (get_madrid_now().isoformat())
    tags: Optional[list] = None

    def __post_init__(self):
        if not self.id:
            raise ValueError("ID és requerit")
        ...

    def to_dict(self) -> dict: ...
    @classmethod
    def from_dict(cls, data: dict) -> 'Foo': ...
```
Regles:
- Validació a `__post_init__` amb `ValueError` i missatges en català.
- **Les mateixes regles** han d'existir al serializer d'entrada; si el model és més estricte, el DAO pot desar un document que després no es pot llegir (cas `ini_date == fin_date`, `api/models/renovation.py:32-33`).
- Dates: desa strings ISO (`YYYY-MM-DD` o datetime ISO) i usa `api/utils/timezone_utils.py` (Madrid). Si `from_dict` converteix a `datetime`, vigila comparacions amb `date` (bug `api/controllers/renovation_controller.py:124-128`).
- Media: desa **claus** R2, no URLs; genera URLs presignades a `from_dict` si cal (com `Experience`, `User`, `Refugi`).
- Si l'usuari es pot esborrar, preveu l'anonimització (`creator_uid='unknown'`), com `Renovation` (`api/models/renovation.py:36-38`).
- Importa el logger amb `logging.getLogger(__name__)`; **no** copiïs `from venv import logger` / `from asyncio.log import logger`.

## 2. Mapper — `api/mappers/<entitat>_mapper.py`
Còpia de `api/mappers/renovation_mapper.py`: `firestore_to_model`, `model_to_firestore`, `firestore_list_to_models`, `models_to_firestore_list` (tots `@staticmethod`). Posa-hi lògica només si cal transformar formats (exemple amb lògica: `api/mappers/refugi_lliure_mapper.py`).

## 3. DAO — `api/daos/<entitat>_dao.py`
- `COLLECTION_NAME = '<col·lecció>'` (snake_case, plural en anglès, com `renovations`, `experiences`).
- `__init__`: `self.firestore_service = FirestoreService()`, `self.mapper = FooMapper()`.
- Crear: `doc_ref = db.collection(...).document()`, `data['id'] = doc_ref.id`, `doc_ref.set(data)` (`api/daos/renovation_dao.py:52-54`).
- Considera validar construint el model **abans** del `set()` per no persistir dades invàlides.
- Cache: afegeix `'foo_detail'` i `'foo_list'` a `CacheService.CACHE_TIMEOUTS` (`api/services/cache_service.py:20-48`) i fes servir `generate_key('foo_detail', foo_id=...)`.
- Invalidació en totes les escriptures (detall + llistes).
- Arrays i comptadors amb `ArrayUnion`/`ArrayRemove`/`Increment`; diverses escriptures relacionades → `db.transaction()` o `db.batch()` (avui no s'usa enlloc de `api/`, però és el camí correcte).
- Si hi ha queries amb `where` + `order_by`, preveu índex compost a Firestore (no hi ha `firestore.indexes.json` al repo).

## 4. Serializers — `api/serializers/<entitat>_serializer.py`
`FooSerializer` (sortida), `FooCreateSerializer`, `FooUpdateSerializer` (entrada). Convenció de nom amb **sufix** (`RenovationCreateSerializer`), no prefix.

## 5. Controller, vista i rutes
Segueix [add-endpoint.md](add-endpoint.md).

## 6. Cascades
Si l'entitat té `creator_uid`, afegeix el pas corresponent a `UserController.delete_user` (`api/controllers/user_controller.py:125-276`): esborrar o anonimitzar. Si depèn d'un refugi, afegeix-la a `DeleteRefugeStrategy` (`api/daos/refuge_proposal_dao.py:388-556`).

## 7. Tests — `api/tests/<entitat>/`
Crea `__init__.py`, `test_models.py`, `test_mappers.py`, `test_daos.py`, `test_serializers.py`, `test_controllers.py`, `test_views.py`. Fixtures de dades a nivell de fitxer (com `api/tests/renovation/test_daos.py:10-55`) o a `api/tests/conftest.py` si són compartides. Mocks de DAO: `@patch('api.daos.foo_dao.FirestoreService')` + `@patch('api.daos.foo_dao.cache_service')`.

## 8. Docs
Afegeix la col·lecció a `docs/integrations/firestore.md`, el flux a `docs/flows/` i la ruta a `docs/ARCHITECTURE.md §4`.
