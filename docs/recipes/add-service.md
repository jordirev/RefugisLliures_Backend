# Recepta — Afegir un servei nou (`api/services/`)

> Un "servei" aquí és una peça transversal o una integració externa (Firestore, cache, R2, càlcul de condició). La lògica de negoci d'un domini va al **controller**, no a un servei.

## Patrons existents [FET]
| Tipus | Exemple | Quan usar-lo |
|---|---|---|
| Singleton amb `__new__` + instància global | `FirestoreService` (`api/services/firestore_service.py:13-22,78`), `CacheService` (`api/services/cache_service.py:14-57,317`) | recurs compartit car de crear (client, connexió) |
| Classe amb Strategy injectada | `R2MediaService(strategy)` + factories (`api/services/r2_media_service.py:146-164,462-469`) | mateix servei amb variants de comportament |
| Classe amb mètodes estàtics/purs | `ConditionService` (`api/services/condition_service.py`) | càlculs sense estat |

## Passos
1. **Fitxer** `api/services/<nom>_service.py`, docstring de mòdul en català, `logger = logging.getLogger(__name__)`.
2. **Configuració**:
   - Settings de Django: afegeix-la a `refugis_lliures/settings.py` amb `config('NOM', default=...)` (decouple) i llegeix-la amb `django.conf.settings`.
   - Si l'has de llegir amb `os.getenv` (com R2), recorda que `decouple.RepositoryEnv` **no** omple `os.environ` (vegeu [GOTCHAS #25](../GOTCHAS.md)).
   - Llegeix les variables **dins de la funció/constructor**, no a nivell de mòdul, perquè els tests les puguin fixar abans (`api/r2_config.py:9-11`).
   - Documenta el **nom** de la variable a `docs/integrations/` i a `render.yaml` (comentari). Mai valors.
3. **Singleton** (si cal):
   ```python
   class FooService:
       _instance = None
       def __new__(cls):
           if cls._instance is None:
               cls._instance = super().__new__(cls)
           return cls._instance
   foo_service = FooService()
   ```
   ⚠️ `CacheService.__init__` es re-executa a cada `CacheService()` (L55-57); no hi posis inicialitzacions cares.
4. **Errors**: decideix i documenta si el servei **llança** o **retorna False/None**. El codi actual barreja (`upload_file` llança, `delete_file` retorna False) i això ha trencat rollbacks ([TECH_DEBT A4](../TECH_DEBT.md)). Recomanació: llançar excepcions pròpies i que el controller les tradueixi.
5. **Export** a `api/services/__init__.py` (afegir a l'import i a `__all__`).
6. **Logging**: si vols un nivell propi, afegeix-lo a `LOGGING['loggers']` de `refugis_lliures/settings.py:234-256`; recorda que el logger `api` només mostra `WARNING`+.
7. **No el construeixis en constructors de controllers** si pot fallar per configuració: `RefugiLliureController()` crea R2 i trenca el health check (`api/controllers/refugi_lliure_controller.py:22`). Millor creació mandrosa.
8. **Tests**: `.coveragerc` i Sonar **exclouen `services/`** del coverage; igualment escriu tests i mocka les dependències externes (`patch('api.services.<nom>_service.<client>')`). Si el servei llegeix variables d'entorn a l'import, fixa-les a `conftest.py` (arrel) com es fa amb `R2_*`.
9. **Docs**: nou fitxer a `docs/integrations/` si és extern; actualitza `docs/ARCHITECTURE.md §1/§7`.
