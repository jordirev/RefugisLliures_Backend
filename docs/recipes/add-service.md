# Recepta — Afegir un servei nou (`api/services/`)

> ## `services.py` per feature
> A les apps `apps/<feature>/` el **service** de la feature (`services.py`) és el lloc de la lògica d'escriptura: funcions amb arguments *keyword-only* i `transaction.atomic()`, que llancen excepcions de domini; les lectures van a `selectors.py`. Exemple: `apps/refuges/services.py: delete_media` (fila + R2; si `R2MediaService.delete_file` retorna `False`, es desfà l'esborrat amb el `savepoint`). Aquesta recepta és per als serveis **transversals** (R2, imatge, moderació, health) que viuen a `api/services/`; no hi posis cache de dades (no n'hi ha, D43).

## Patrons existents [FET]
| Tipus | Exemple | Quan usar-lo |
|---|---|---|
| Classe amb Strategy injectada | `R2MediaService(strategy)` + factories (`api/services/r2_media_service.py`) | mateix servei amb variants de comportament |
| Funcions pures | `database_health.check_database`, `image_processing_service` | càlculs o comprovacions sense estat |
| Singleton amb `__new__` | cap des del chunk 11 (`FirestoreService` i `CacheService` han desaparegut) | recurs compartit car de crear |

## Passos
1. **Fitxer** `api/services/<nom>_service.py`, docstring de mòdul en català, `logger = logging.getLogger(__name__)`.
2. **Configuració**:
   - Settings de Django: afegeix-la a `refugis_lliures/settings.py` amb `config('NOM', default=...)` (decouple) i llegeix-la amb `django.conf.settings`.
   - Si l'has de llegir amb `os.getenv` (com R2), recorda que `decouple.RepositoryEnv` **no** omple `os.environ` (vegeu [GOTCHAS #25](../GOTCHAS.md)).
   - Llegeix les variables **dins de la funció/constructor**, no a nivell de mòdul, perquè els tests les puguin fixar abans (`api/r2_config.py:9-11`).
   - Documenta el **nom** de la variable a `docs/integrations/` i a `render.yaml` (comentari). Mai valors.
3. **Estat compartit**: evita singletons; si en cal un, que `__init__` no es re-executi (no hi posis inicialitzacions cares).
4. **Errors**: decideix i documenta si el servei **llança** o **retorna False/None**. El codi actual barreja (`upload_file` llança, `delete_file` retorna False) i això ha trencat rollbacks ([TECH_DEBT A4](../TECH_DEBT.md)). Recomanació: llançar excepcions pròpies i que la vista les tradueixi.
5. **Export** a `api/services/__init__.py` (afegir a l'import i a `__all__`).
6. **Logging**: nivells estàndard; el logger `api` només mostra `WARNING`+ (`LOGGING['loggers']` a `refugis_lliures/settings.py`).
7. **Creació mandrosa**: no construeixis clients externs (R2) en constructors si poden fallar per configuració; crea'ls sota demanda.
8. **Tests**: `.coveragerc` i Sonar **exclouen `services/`** del coverage; igualment escriu tests i mocka les dependències externes (`patch('api.services.<nom>_service.<client>')`). Si el servei llegeix variables d'entorn a l'import, fixa-les a `conftest.py` (arrel) com es fa amb `R2_*`.
9. **Docs**: nou fitxer a `docs/integrations/` si és extern; actualitza `docs/ARCHITECTURE.md §1/§7`.
