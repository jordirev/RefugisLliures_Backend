# Recepta — Afegir un model nou (PostgreSQL)

> ## `apps/<feature>/models.py` — únic patró (Firestore eliminat al chunk 11, D43)
> Referència: `apps/refuges/models.py`, `apps/accounts/models.py` i les seves migracions `0001_initial.py`. Un model de Postgres:
> - És un `django.db.models.Model` a `apps/<feature>/models.py` (nova app: `apps.py` amb `name='apps.<feature>'`, `label='<feature>'`, i afegir-la a `INSTALLED_APPS`).
> - `db_table = 'schema"."taula'` (el schema ve de `docs/design/postgres-schema.md`), PK `UUIDField(primary_key=True, db_default=Func(function='uuidv7', output_field=UUIDField()))` (UUID v7 generat per la BD amb `uuidv7()` de Postgres 18; l'helper `api/utils/ids.py` s'ha eliminat; disseny §1.4), `CompositePrimaryKey` (Django 5.2) a les taules d'unió sense FK entrant, `db_default=` per als valors per defecte (`Now()`, `False`, `''`), `TextChoices` + `CheckConstraint` per als estats interns (els catàlegs oberts, com idiomes i tipus de refugi, són taula + FK), noms explícits de constraints/índexs (`<taula>_<cols>_ck|uq|idx|gist|gin`).
> - **FK**: `ForeignKey(..., on_delete=models.DO_NOTHING, db_constraint=False, db_index=False, db_column='x_uid')`; la restricció real (`ON DELETE CASCADE/SET NULL`, `DEFERRABLE INITIALLY DEFERRED`) es crea a la migració amb `RunSQL` (§6.3), i l'índex de la FK a `Meta.indexes`.
> - **Migració**: `makemigrations` genera el DDL; hi afegeixes, a la **mateixa** migració i amb `reverse_sql`, un `PostgresRunSQL` (`apps.core.migration_utils`) amb les FK reals, `ENABLE ROW LEVEL SECURITY` + polítiques (`create_policy_sql` amb les macros `{U}`, `{ADM}`, `{SYS}`), els `GRANT` mínims per a `app`, triggers i vistes (models `managed = False`). S'aplica sempre amb `migrate --database=migrator`. Si hi ha una PK o un camp únic de text, afegeix `DropDjangoLikeIndexes([...])` amb els índexs `*_like` que hagi generat Django (noms a `pg_indexes`). Comprova `makemigrations --check` net i forward/reverse/forward.
> - Escriptures de dades de prova i de comandes: amb `system_context()`/`rls_context()` (o l'àlies `migrator`).


## Passos
1. **Model i migració** segons la nota de dalt. Model de referència amb constraints (`CHECK`, `EXCLUDE`), triggers i RLS: `apps/renovations/models.py` + `migrations/0001_initial.py`.
2. **Regles**: les mateixes han d'existir al serializer d'entrada i al `CHECK` de la BD (cas `ini_date == fin_date`: un dia és vàlid).
3. **Dates**: instants `timestamptz` amb el rellotge de la BD; dates de negoci amb `get_madrid_today()` (`api/utils/timezone_utils.py`).
4. **Media**: desa **claus** R2, no URLs; `media_to_dict` presigna a la resposta.
5. **Esborrat d'usuari**: decideix la FK `ON DELETE CASCADE`/`SET NULL` al DDL (migració `RunSQL`; vegeu `accounts.0002`) — [deep-dive](../deep-dives/user-deletion.md). Si depèn d'un refugi, la FK cap a `refuges.refuges` l'esborra amb el refugi (`apps/proposals/services.py: _apply_delete`); si guarda fitxers a R2, afegeix-ne la lectura de claus a `_apply_delete`.
6. **Serializers, selectors, services i vista**: vegeu [add-endpoint.md](add-endpoint.md).
7. **Tests**: `apps/<feature>/tests/` (esquema, constraints, RLS, models).
8. **Docs**: el flux a `docs/flows/` i la ruta a `docs/ARCHITECTURE.md §4`.
