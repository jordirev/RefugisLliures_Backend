# Sistema de Mitjana de Conditions

## Descripció

Aquest sistema gestiona l'edició del camp `condition` d'un refugi utilitzant una mitjana ponderada de totes les contribucions dels usuaris.

## Implementació

### 1. ConditionService

**Ubicació**: `api/services/condition_service.py`

Servei reusable que proporciona **només càlculs**, sense fer operacions de Firestore:

- **`calculate_condition_average()`**: Calcula els nous valors de condition i num_contributed_conditions
  - Fórmula: `condition = ((condition_actual × num_contributed_conditions) + contributed_condition) / (num_contributed_conditions + 1)`
  - **Retorna** un diccionari amb els nous valors (NO actualitza Firestore)
  - Paràmetres: `current_condition`, `num_contributed_conditions`, `contributed_condition`

- **`initialize_condition()`**: Retorna els valors inicials de condition per a un refugi nou
  - `condition = float(contributed_condition)`
  - `num_contributed_conditions = 1`

- **`validate_condition_value()`**: Valida que una condition sigui un valor vàlid (0-3)

### 2. Camps a Firestore

Els refugis a Firestore tenen dos camps relacionats amb la condition:

- **`condition`** (float): Mitjana de totes les conditions contribuïdes
- **`num_contributed_conditions`** (int): Nombre total de contribucions de condition

### 3. Flux de Creació (CREATE)

Quan es crea un refugi amb una proposta que inclou `condition` al payload:

1. Es valida que la condition estigui entre 0-3
2. S'inicialitza `condition = float(contributed_condition)`
3. S'inicialitza `num_contributed_conditions = 1`
4. Es guarden els valors a Firestore

**Implementació**: `CreateRefugeStrategy.execute()` a `api/daos/refuge_proposal_dao.py`

### 4. Flux d'Actualització (UPDATE)

Quan s'accepta una proposta d'edició amb `condition` al payload:

1. Es valida que la condition estigui entre 0-3
2. Es llegeix el refugi de Firestore per obtenir `condition` i `num_contributed_conditions` actuals
3. S'utilitza `ConditionService.calculate_condition_average()` per calcular els nous valors
4. S'afegeixen els nous valors a `update_data` juntament amb els altres camps a actualitzar
5. Es fa un **únic** `.update()` a Firestore amb tots els camps

**Implementació**: `UpdateRefugeStrategy.execute()` a `api/daos/refuge_proposal_dao.py`

### 5. Visualització

Quan es mostra la informació d'un refugi (GET):

- La `condition` s'arrodoneix cap a l'enter més proper mitjançant `round()`
- Això es fa al `to_representation()` del serializer
- Els usuaris veuen sempre un valor enter (0, 1, 2 o 3)

**Implementació**: `RefugiSerializer.to_representation()` a `api/serializers/refugi_lliure_serializer.py`

## Avantatges del Disseny

1. **Reusable**: El `ConditionService` es pot utilitzar des de qualsevol endpoint que necessiti calcular la mitjana de condition
2. **Desacoblat**: La lògica de càlcul està separada de la persistència (Firestore)
3. **Mantenible**: Tots els càlculs estan centralitzats en un sol lloc
4. **Extensible**: Fàcil d'adaptar si es volen implementar altres tipus de mitjanes o algorismes
5. **Eficient**: Permet fer un únic `.update()` a Firestore amb tots els camps, en lloc de múltiples operacions
6. **Responsabilitats clares**: El servei calcula, el DAO persisteix

## Exemple d'Ús des d'un Altre Endpoint

```python
from api.services.condition_service import ConditionService
from api.services import firestore_service

# En un DAO o vista
db = firestore_service.get_db()
refuge_ref = db.collection('data_refugis_lliures').document('refugi_123')
refuge_doc = refuge_ref.get()
refuge_data = refuge_doc.to_dict()

# Calcular els nous valors
condition_data = ConditionService.calculate_condition_average(
    current_condition=refuge_data.get('condition'),
    num_contributed_conditions=refuge_data.get('num_contributed_conditions', 0),
    contributed_condition=2.5
)

# Preparar update_data amb tots els camps
update_data = {
    'name': 'Nou nom',
    'places': 20,
    'condition': condition_data['condition'],
    'num_contributed_conditions': condition_data['num_contributed_conditions']
}

# Fer un únic update amb tots els camps
refuge_ref.update(update_data)
```

## Exemples de Càlculs

### Refugi Nou
- Contribució inicial: `2`
- Resultat: `condition = 2.0`, `num_contributed_conditions = 1`

### Primera Actualització
- Estat actual: `condition = 2.0`, `num_contributed_conditions = 1`
- Nova contribució: `3`
- Càlcul: `(2.0 × 1 + 3) / 2 = 2.5`
- Resultat: `condition = 2.5`, `num_contributed_conditions = 2`
- Mostrat a l'usuari: `3` (arrodonit)

### Segona Actualització
- Estat actual: `condition = 2.5`, `num_contributed_conditions = 2`
- Nova contribució: `1`
- Càlcul: `(2.5 × 2 + 1) / 3 = 2.0`
- Resultat: `condition = 2.0`, `num_contributed_conditions = 3`
- Mostrat a l'usuari: `2` (arrodonit)

## Validacions

- La condition contribuïda ha d'estar entre 0 i 3
- Aquesta validació es fa tant al serializer de propostes com al `ConditionService`
- Si la validació falla, la condition no s'actualitza i es registra un warning al log
