# Guia d'Execució de Tests Automatitzats

## 📋 Configuració Inicial

### 1. Instal·lar dependències de testing

```bash
pip install -r requirements.txt
```

O instal·lar individualment:

```bash
pip install pytest pytest-cov pytest-django pytest-mock coverage
```

## 🧪 Executar Tests

### Tests complets amb coverage

```bash
# Executar tots els tests amb cobertura
pytest --cov=api --cov-report=term-missing --cov-report=html

# Només tests d'usuaris
pytest api/tests/test_user.py --cov=api --cov-report=term-missing

# Només tests de refugis
pytest api/tests/test_refugi_lliure.py --cov=api --cov-report=term-missing
```

### Tests per categories (markers)

```bash
# Només tests de models
pytest -m models

# Només tests de serializers
pytest -m serializers

# Només tests de controllers
pytest -m controllers

# Només tests de DAOs
pytest -m daos

# Només tests de mappers
pytest -m mappers

# Només tests de views
pytest -m views

# Tests d'integració
pytest -m integration
```

### Tests amb més verbositat

```bash
# Executar amb sortida detallada
pytest -v

# Executar amb sortida molt detallada
pytest -vv

# Mostrar print statements
pytest -s
```

### Tests específics

```bash
# Executar una classe de tests específica
pytest api/tests/test_user.py::TestUserModel

# Executar un test específic
pytest api/tests/test_user.py::TestUserModel::test_user_creation_valid

# Executar tests que coincideixin amb un patró
pytest -k "test_create"
```

## 📊 Informes de Coverage

### Generar informe HTML

```bash
pytest --cov=api --cov-report=html
```

L'informe HTML es generarà a `htmlcov/index.html`. Obre'l amb un navegador per veure el coverage detallat.

### Generar informe en terminal

```bash
pytest --cov=api --cov-report=term-missing
```

Això mostrarà les línies que no estan cobertes pels tests.

### Objectiu de Coverage

L'objectiu és aconseguir un **coverage mínim del 85-90%** per a tots els mòduls.

## 🏗️ Estructura de Tests

```
api/tests/
├── conftest.py              # Fixtures compartides
├── test_user.py             # Tests del mòdul user
│   ├── TestUserModel        # Tests de models
│   ├── TestUserSerializers  # Tests de serializers
│   ├── TestUserMapper       # Tests de mappers
│   ├── TestUserDAO          # Tests de DAOs
│   ├── TestUserController   # Tests de controllers
│   ├── TestUserViews        # Tests de views
│   └── TestUserIntegration  # Tests d'integració
└── test_refugi_lliure.py    # Tests del mòdul refugi_lliure
    ├── TestRefugiModels
    ├── TestRefugiSerializers
    ├── TestRefugiMapper
    ├── TestRefugiDAO
    ├── TestRefugiController
    ├── TestRefugiViews
    └── TestRefugiIntegration
```

## 🔍 Markers Disponibles

- `@pytest.mark.unit` - Tests unitaris
- `@pytest.mark.integration` - Tests d'integració
- `@pytest.mark.models` - Tests de models
- `@pytest.mark.serializers` - Tests de serializers
- `@pytest.mark.controllers` - Tests de controllers
- `@pytest.mark.daos` - Tests de DAOs
- `@pytest.mark.mappers` - Tests de mappers
- `@pytest.mark.views` - Tests de views
- `@pytest.mark.slow` - Tests lents (opcional)

## 🐛 Debugging de Tests

### Executar tests amb depuració

```bash
# Aturar en el primer error
pytest -x

# Aturar després de N errors
pytest --maxfail=3

# Mostrar el traceback complet
pytest --tb=long

# Mostrar només la línia de l'error
pytest --tb=line
```

### Utilitzar pdb per depurar

```python
def test_something():
    import pdb; pdb.set_trace()
    # El test s'aturarà aquí
```

O amb pytest:

```bash
pytest --pdb
```

## 📝 Bones Pràctiques

1. **Executar tests abans de cada commit**
   ```bash
   pytest --cov=api --cov-report=term-missing
   ```

2. **Verificar que tots els tests passen**
   ```bash
   pytest -v
   ```

3. **Revisar el coverage regularment**
   ```bash
   pytest --cov=api --cov-report=html
   open htmlcov/index.html
   ```

4. **Tests ràpids durant el desenvolupament**
   ```bash
   # Només executar els tests modificats
   pytest api/tests/test_user.py::TestUserModel::test_user_creation_valid
   ```

## 🚀 Integració amb CI/CD

Per integrar amb GitHub Actions o altres sistemes CI/CD:

```yaml
# .github/workflows/tests.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.11
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
      - name: Run tests with coverage
        run: |
          pytest --cov=api --cov-report=xml --cov-report=term-missing
      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v2
```

## 📈 Objectius de Coverage per Capa

| Capa        | Objectiu | Prioritat |
|-------------|----------|-----------|
| Models      | 100%     | Alta      |
| Serializers | 95%      | Alta      |
| Mappers     | 100%     | Alta      |
| DAOs        | 90%      | Alta      |
| Controllers | 90%      | Alta      |
| Views       | 85%      | Mitjana   |

## 🔧 Troubleshooting

### Error: "No module named 'pytest'"

```bash
pip install pytest pytest-cov pytest-django pytest-mock
```

### Error: "DJANGO_SETTINGS_MODULE is not set"

Assegura't que `pytest.ini` estigui configurat correctament amb:
```ini
[pytest]
DJANGO_SETTINGS_MODULE = refugis_lliures.settings
```

### Tests massa lents

```bash
# Executar tests en paral·lel
pip install pytest-xdist
pytest -n auto
```

## 📚 Recursos Addicionals

- [Documentació de pytest](https://docs.pytest.org/)
- [pytest-cov](https://pytest-cov.readthedocs.io/)
- [pytest-django](https://pytest-django.readthedocs.io/)
- [Best practices for testing](https://docs.pytest.org/en/latest/goodpractices.html)
