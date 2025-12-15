# Arquitectura Refugis - Refactoring Completat

## Resum dels Canvis

S'ha refactoritzat completament la gestió de refugis per seguir una arquitectura en capes (layered architecture) seguint el patró:

**View → Controller → DAO → Firestore**

### Estructura Actual

```
api/
├── models/
│   ├── refugi.py              # Models de domini per refugis
│   └── __init__.py            # Exports actualitzats
├── daos/
│   ├── refugi_lliure_dao.py   # Accés a dades Firestore
│   └── __init__.py            # Exports actualitzats
├── mappers/
│   ├── refugi_mapper.py       # Conversió entre models i dades
│   └── __init__.py            # Exports actualitzats
├── controllers/
│   ├── refugi_controller.py   # Lògica de negoci
│   └── __init__.py            # Exports actualitzats
├── serializers/
│   ├── refugi_serializer.py   # Serialització REST API
│   └── __init__.py            # Exports actualitzats
└── views/
    └── refugi_views.py        # Vistes REST refactoritzades
```

## Components Creats

### 1. Models (`api/models/refugi.py`)

**Classes creades:**
- `Coordinates`: Coordenades geogràfiques (lat, long)
- `InfoComplementaria`: Informació sobre equipaments del refugi
- `Refugi`: Model principal del refugi
- `RefugiCoordinates`: Model simplificat per coordenades
- `RefugiSearchFilters`: Model per filtres de cerca

**Caracteristiques:**
- Validació automàtica de dades
- Conversió bidireccional amb diccionaris (`to_dict()`, `from_dict()`)
- Tipus de dades estrictes amb `@dataclass`

### 2. DAO (`api/daos/refugi_lliure_dao.py`)

**Classe:** `RefugiDao`

**Mètodes:**
- `get_by_id(refugi_id)`: Obtenir refugi per ID
- `search_refugis(filters)`: Cercar refugis amb filtres
- `get_all_coordinates(limit)`: Obtenir coordenades dels refugis
- `health_check()`: Comprovar estat de Firestore

**Responsabilitats:**
- Accés directe a Firestore
- Gestió d'errors de base de dades
- Operacions CRUD sobre col·leccions

### 3. Mapper (`api/mappers/refugi_mapper.py`)

**Classe:** `RefugiMapper`

**Mètodes de conversió:**
- `firestore_to_model()`: Firestore dict → Model
- `model_to_firestore()`: Model → Firestore dict
- `firestore_list_to_models()`: Llista conversions
- `coordinates_*()`: Conversions específiques per coordenades

**Mètodes de formatació:**
- `format_search_response()`: Resposta de cerca
- `format_coordinates_response()`: Resposta de coordenades

### 4. Serializers (`api/serializers/refugi_serializer.py`)

**Serializers creats:**
- `CoordinatesSerializer`: Coordenades
- `InfoComplementariaSerializer`: Informació complementària
- `RefugiSerializer`: Refugi complet
- `RefugiCoordinatesSerializer`: Coordenades de refugi
- `RefugiSearchResponseSerializer`: Resposta de cerca
- `RefugiCoordinatesResponseSerializer`: Resposta coordenades
- `HealthCheckResponseSerializer`: Health check
- `RefugiSearchFiltersSerializer`: Filtres entrada cerca
- `RefugiCoordinatesFiltersSerializer`: Filtres entrada coordenades

**Responsabilitats:**
- Validació d'entrada (query parameters)
- Serialització de sortida (responses)
- Transformació de formats per API REST

### 5. Controller (`api/controllers/refugi_controller.py`)

**Classe:** `RefugiController`

**Mètodes:**
- `get_refugi_by_id()`: Obtenir refugi per ID
- `search_refugis()`: Cercar amb filtres
- `get_refugi_coordinates()`: Obtenir coordenades
- `health_check()`: Health check

**Responsabilitats:**
- Lògica de negoci
- Coordinació entre DAO i Mapper
- Gestió d'errors de domini
- Validació de dades d'entrada

### 6. Views (`api/views/refugi_views.py`)

**Funcions refactoritzades:**
- `health_check()`: Utilitza controller + serializers
- `refugi_detail()`: Gestió d'errors millorada
- `search_refugis()`: Validació de paràmetres
- `refugi_coordinates()`: Resposta estructurada

**Millores:**
- Validació automàtica amb serializers
- Gestió d'errors consistent
- Separació completa de lògica de negoci
- Responses tipificades

## Avantatges de la Nova Arquitectura

### ✅ Separació de Responsabilitats
- **View**: Només gestiona HTTP requests/responses
- **Controller**: Lògica de negoci pura
- **DAO**: Només accés a dades
- **Mapper**: Només transformació de formats

### ✅ Testabilitat
- Cada component es pot testar per separat
- Mocking fàcil per a tests unitaris
- Dependency injection simple

### ✅ Mantenibilitat
- Canvis a Firestore només afecten DAO
- Canvis a API només afecten Views/Serializers
- Lògica de negoci centralitzada en Controller

### ✅ Reutilitzabilitat
- DAO es pot reutilitzar en altres contexts
- Models serveixen per a múltiples APIs
- Mappers reutilitzables per diferents formats

### ✅ Escalabilitat
- Fàcil afegir nous endpoints
- Fàcil afegir noves fonts de dades
- Fàcil afegir nova lògica de negoci

## Estructura de Dades del Refugi

El model suporta completament l'estructura original:

```json
{
    "coord": {
      "long": 1.167,
      "lat": 42.71867
    },
    "altitude": 2023,
    "places": 0,
    "remarque": "...",
    "info_comp": {
      "manque_un_mur": 0,
      "cheminee": 0,
      "poele": 0,
      "couvertures": 0,
      "latrines": 1,
      "bois": 1,
      "eau": 1,
      "matelas": 0,
      "couchage": 0,
      "bas_flancs": 0,
      "lits": 0,
      "mezzanine/etage": 0
    },
    "description": "...",
    "links": ["https://..."],
    "type": "Fermée",
    "modified_at": "2024-01-24",
    "name": "Cabane des Clos de Dessus",
    "region": null,
    "departement": null,
    "comarca": null,
    "condition": 2,
    "id": "0"
}
```

## Flux de Dades

### Cerca de Refugis
1. `View` rep request + query params
2. `RefugiSearchFiltersSerializer` valida paràmetres
3. `Controller` processa filtres
4. `DAO` consulta Firestore
5. `Mapper` converteix dades → models
6. `Mapper` formatea resposta
7. `RefugiSearchResponseSerializer` serialitza
8. `View` retorna HTTP response

### Detall de Refugi
1. `View` rep refugi_id
2. `Controller` processa ID
3. `DAO` consulta document específic
4. `Mapper` converteix → model
5. `RefugiSerializer` serialitza
6. `View` retorna refugi o error 404

## Compatibilitat

- ✅ Mantenen tots els endpoints originals
- ✅ Mateix format de resposta
- ✅ Mateixos query parameters
- ✅ Mateixos codis d'error HTTP
- ✅ Compatible amb frontend existent
