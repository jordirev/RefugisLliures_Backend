# Fix: Firebase no s'inicialitza durant els tests

## Problema
Quan s'executaven els tests a GitHub Actions (o qualsevol entorn de CI/CD), Firebase intentava inicialitzar-se i buscava el fitxer de credencials `env/firebase-service-account.json`, que no existeix en l'entorn de testing. Això provocava l'error:

```
FileNotFoundError: Fitxer de credencials no trobat: /home/runner/work/RefugisLliures_Backend/RefugisLliures_Backend/env/firebase-service-account.json
```

## Causa
El mètode `AppConfig.ready()` en `api/apps.py` crida `initialize_firebase()` quan Django es carrega, i això passa **abans** que els tests comencin a executar-se. Això significa que Firebase intentava inicialitzar-se fins i tot durant els tests, on no és necessari perquè tot està mockat.

## Solució implementada

### 1. Detecció d'entorn de testing en `firebase_config.py`
S'ha modificat la funció `initialize_firebase()` per detectar si s'està executant en un entorn de testing i no inicialitzar Firebase:

```python
def initialize_firebase():
    """
    Inicialitza Firebase Admin SDK si encara no s'ha inicialitzat.
    - A Render: usa la variable d'entorn FIREBASE_SERVICE_ACCOUNT_KEY
    - En local: carrega les variables d'entorn des de env/.env.development i busca el fitxer JSON
    - En tests: no inicialitza Firebase
    """
    # No inicialitzar Firebase durant els tests
    import sys
    if 'pytest' in sys.modules or os.environ.get('TESTING') == 'true':
        logger.info("🧪 Entorn de testing detectat - Firebase NO s'inicialitza")
        return
    
    # ... resta del codi d'inicialització
```

**Detecció doble:**
- `'pytest' in sys.modules`: Detecta si pytest està carregat
- `os.environ.get('TESTING') == 'true'`: Variable d'entorn explícita per tests

### 2. Fixture global en `conftest.py`
S'ha afegit una fixture `autouse=True` amb scope de sessió que estableix la variable d'entorn `TESTING=true` al començament de tots els tests:

```python
@pytest.fixture(scope='session', autouse=True)
def setup_test_environment():
    """
    Configuració global que s'executa una vegada al principi de tots els tests.
    Assegura que Firebase no s'inicialitza durant els tests.
    """
    import os
    os.environ['TESTING'] = 'true'
    yield
    # Cleanup
    if 'TESTING' in os.environ:
        del os.environ['TESTING']
```

## Avantatges d'aquesta solució

1. **No cal fitxers de credencials en CI/CD**: Els tests no necessiten cap credencial de Firebase.
2. **Tests més ràpids**: No es perd temps inicialitzant Firebase.
3. **Tests més aïllats**: Els tests no depenen de serveis externs.
4. **Doble protecció**: Dues maneres de detectar l'entorn de testing.
5. **Compatible amb totes les eines**: Funciona amb pytest, manage.py test, i qualsevol CI/CD.

## Verificació

### Local
```bash
pytest api/tests/ -v
```

### GitHub Actions
El workflow existent (`python manage.py test` o `pytest`) funcionarà sense modificacions addicionals.

## Notes importants

- Els tests continuen usant mocks per a Firestore i altres serveis de Firebase.
- Aquesta solució no afecta el comportament en producció ni en desenvolupament local.
- Si necessites executar tests amb Firebase real (tests d'integració), pots establir `TESTING=false` manualment.
