# Implementació del Patró Strategy per a la Cerca de Refugis

## Resum

S'ha implementat el patró de disseny Strategy per optimitzar les cerques de refugis a Firestore aprofitant els índexs composats disponibles.

## Índexs Disponibles a Firestore

Els següents índexs composats estan configurats:

1. `type` + `places`
2. `type` + `altitude`
3. `type` + `condition` + `places` (no implementat, camp condition no present al model)
4. `type` + `condition` + `altitude` (no implementat, camp condition no present al model)
5. `condition` + `places` (no implementat, camp condition no present al model)
6. `condition` + `altitude` (no implementat, camp condition no present al model)

## Arquitectura

### 1. Interfície Base: `RefugiSearchStrategy`

Classe abstracta que defineix el contracte per a totes les estratègies:

```python
class RefugiSearchStrategy(ABC):
    @abstractmethod
    def execute_query(self, db: firestore.Client, collection_name: str, filters: 'RefugiSearchFilters') -> List[Dict[str, Any]]:
        pass
    
    @abstractmethod
    def get_strategy_name(self) -> str:
        pass
```

### 2. Estratègies Implementades

#### Estratègies amb Índexs Directes

- **TypePlacesStrategy**: Filtres `type` + `places` (índex directe)
- **TypeAltitudeStrategy**: Filtres `type` + `altitude` (índex directe)
- **TypeOnlyStrategy**: Només filtre `type`
- **PlacesOnlyStrategy**: Només filtre `places`
- **AltitudeOnlyStrategy**: Només filtre `altitude`

#### Estratègies amb Filtre Manual

Quan no hi ha índex compost disponible per a la combinació de filtres, s'utilitza l'índex que millor s'ajusti i es fa el filtre restant manualment:

- **TypePlacesAltitudeStrategy**: Utilitza índex `type+places`, filtra `altitude` manualment
- **PlacesAltitudeStrategy**: Filtra per `places`, després `altitude` manualment

### 3. Selector d'Estratègia: `SearchStrategySelector`

Classe que selecciona l'estratègia òptima segons els filtres actius:

```python
strategy = SearchStrategySelector.select_strategy(filters)
results = strategy.execute_query(db, collection_name, filters)
```

#### Lògica de Selecció

1. **Cerca per name**: Si hi ha filtre `name`, retorna directament el refugi (name és únic)
2. **Type + Places + Altitude**: Usa `TypePlacesAltitudeStrategy` (índex type+places, filtra altitude)
3. **Type + Places**: Usa `TypePlacesStrategy` (índex directe)
4. **Type + Altitude**: Usa `TypeAltitudeStrategy` (índex directe)
5. **Type**: Usa `TypeOnlyStrategy`
6. **Places + Altitude**: Usa `PlacesAltitudeStrategy` (filtra places, després altitude)
7. **Places**: Usa `PlacesOnlyStrategy`
8. **Altitude**: Usa `AltitudeOnlyStrategy`

## Integració al DAO

El `RefugiLliureDAO` utilitza les estratègies a través dels següents mètodes:

### `_has_active_filters(filters: RefugiSearchFilters) -> bool`

Comprova si hi ha filtres actius (exclou limit). Retorna `True` si hi ha algun filtre actiu.

### `_build_optimized_query(db, filters: RefugiSearchFilters) -> List[Dict[str, Any]]`

Construeix i executa una query optimitzada:

1. Si hi ha filtre `name`, crida `_search_by_name()`
2. Altrament, selecciona l'estratègia òptima i executa la query
3. Retorna els resultats en format raw (Dict)

### `_search_by_name(db, name: str) -> List[Dict[str, Any]]`

Cerca un refugi pel seu nom exacte. Només retorna un refugi (màxim) ja que el name és únic.

## Flux de Cerca

```
search_refugis(filters)
    ↓
_has_active_filters(filters)
    ↓ (si true)
_build_optimized_query(db, filters)
    ↓
    ├─ Si name → _search_by_name()
    └─ Altrament → SearchStrategySelector.select_strategy()
                        ↓
                    strategy.execute_query()
```

## Beneficis

1. **Optimització de queries**: Aprofita els índexs composats de Firestore
2. **Mantenibilitat**: Cada estratègia és independent i fàcil de modificar
3. **Extensibilitat**: Afegir nous filtres o índexs només requereix crear noves estratègies
4. **Separació de responsabilitats**: Lògica de cerca separada del DAO
5. **Testabilitat**: Cada estratègia es pot testejar independentment
6. **Cache integrat**: Manté la cache existent per a resultats de cerques

## Exemples d'Ús

### Cerca per Name

```python
filters = RefugiSearchFilters()
filters.name = "Cabane de Bastan"
results = dao.search_refugis(filters)
# Retorna màxim 1 refugi
```

### Cerca per Type i Places

```python
filters = RefugiSearchFilters()
filters.type = "Cabane"
filters.places_min = 5
filters.places_max = 20
results = dao.search_refugis(filters)
# Usa TypePlacesStrategy amb índex directe
```

### Cerca per Type, Places i Altitude

```python
filters = RefugiSearchFilters()
filters.type = "Cabane"
filters.places_min = 5
filters.altitude_min = 2000
filters.altitude_max = 3000
results = dao.search_refugis(filters)
# Usa TypePlacesAltitudeStrategy: índex type+places, filtra altitude manualment
```

## Arxius Modificats/Creats

- **Creat**: `api/daos/search_strategies.py` - Estratègies de cerca
- **Modificat**: `api/daos/refugi_lliure_dao.py` - Integració del patró Strategy

## Notes Tècniques

- Utilitza `TYPE_CHECKING` per evitar imports circulars
- Logging detallat per monitoritzar les queries executades
- Compatible amb el sistema de cache existent
- Gestió d'errors per cada estratègia
