"""
Estratègies de cerca per a refugis utilitzant el patró Strategy.
Cada estratègia optimitza les queries de Firestore segons els índexs composats disponibles.

Índexs disponibles a Firestore:
- type + condition + places
- type + condition + altitude
- type + places
- type + altitude  
- condition + places
- condition + altitude
"""
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from google.cloud import firestore

if TYPE_CHECKING:
    from ..models.refugi_lliure import RefugiSearchFilters

logger = logging.getLogger(__name__)


class RefugiSearchStrategy(ABC):
    """Interfície base per a les estratègies de cerca de refugis"""
    
    @abstractmethod
    def execute_query(self, db: firestore.Client, collection_name: str, filters: 'RefugiSearchFilters') -> List[Dict[str, Any]]:
        """
        Executa la query optimitzada segons l'estratègia
        
        Args:
            db: Client de Firestore
            collection_name: Nom de la col·lecció
            filters: Filtres de cerca
            
        Returns:
            Llista de documents de refugis
        """
        pass
    
    @abstractmethod
    def get_strategy_name(self) -> str:
        """Retorna el nom de l'estratègia per a logging"""
        pass


# ==================== ESTRATÈGIES AMB ÍNDEXS COMPOSATS DE 3 CAMPS ====================

class TypeConditionPlacesStrategy(RefugiSearchStrategy):
    """Estratègia per a filtres: type + condition + places (utilitza índex: type, condition, places)"""
    
    def execute_query(self, db: firestore.Client, collection_name: str, filters: 'RefugiSearchFilters') -> List[Dict[str, Any]]:
        query = db.collection(collection_name)
        
        # Ordre segons índex: type, condition, places
        query = query.where(filter=firestore.FieldFilter('type', 'in', filters.type))
        query = query.where(filter=firestore.FieldFilter('condition', 'in', filters.condition))
        
        if filters.places_min is not None:
            query = query.where(filter=firestore.FieldFilter('places', '>=', filters.places_min))
        if filters.places_max is not None:
            query = query.where(filter=firestore.FieldFilter('places', '<=', filters.places_max))
        
        logger.log(23, f"Firestore QUERY: collection={collection_name} filters=type+condition+places")
        docs = query.stream()
        return [doc.to_dict() for doc in docs]
    
    def get_strategy_name(self) -> str:
        return "TypeConditionPlacesStrategy"


class TypeConditionAltitudeStrategy(RefugiSearchStrategy):
    """Estratègia per a filtres: type + condition + altitude (utilitza índex: type, condition, altitude)"""
    
    def execute_query(self, db: firestore.Client, collection_name: str, filters: 'RefugiSearchFilters') -> List[Dict[str, Any]]:
        query = db.collection(collection_name)
        
        # Ordre segons índex: type, condition, altitude
        query = query.where(filter=firestore.FieldFilter('type', 'in', filters.type))
        query = query.where(filter=firestore.FieldFilter('condition', 'in', filters.condition))
        
        if filters.altitude_min is not None:
            query = query.where(filter=firestore.FieldFilter('altitude', '>=', filters.altitude_min))
        if filters.altitude_max is not None:
            query = query.where(filter=firestore.FieldFilter('altitude', '<=', filters.altitude_max))
        
        logger.log(23, f"Firestore QUERY: collection={collection_name} filters=type+condition+altitude")
        docs = query.stream()
        return [doc.to_dict() for doc in docs]
    
    def get_strategy_name(self) -> str:
        return "TypeConditionAltitudeStrategy"


class TypeConditionPlacesAltitudeStrategy(RefugiSearchStrategy):
    """
    Estratègia per a filtres: type + condition + places + altitude
    Utilitza índex type+condition+places i filtra altitude manualment
    """
    
    def execute_query(self, db: firestore.Client, collection_name: str, filters: 'RefugiSearchFilters') -> List[Dict[str, Any]]:
        query = db.collection(collection_name)
        
        # Utilitza índex: type, condition, places
        query = query.where(filter=firestore.FieldFilter('type', 'in', filters.type))
        query = query.where(filter=firestore.FieldFilter('condition', 'in', filters.condition))
        
        if filters.places_min is not None:
            query = query.where(filter=firestore.FieldFilter('places', '>=', filters.places_min))
        if filters.places_max is not None:
            query = query.where(filter=firestore.FieldFilter('places', '<=', filters.places_max))
        
        logger.log(23, f"Firestore QUERY: collection={collection_name} filters=type+condition+places (manual altitude)")
        docs = query.stream()
        results = [doc.to_dict() for doc in docs]
        
        # Filtre manual per altitude
        if filters.altitude_min is not None or filters.altitude_max is not None:
            filtered_results = []
            for refugi in results:
                altitude = refugi.get('altitude', 0)
                if filters.altitude_min is not None and altitude < filters.altitude_min:
                    continue
                if filters.altitude_max is not None and altitude > filters.altitude_max:
                    continue
                filtered_results.append(refugi)
            return filtered_results
        
        return results
    
    def get_strategy_name(self) -> str:
        return "TypeConditionPlacesAltitudeStrategy"


# ==================== ESTRATÈGIES AMB ÍNDEXS COMPOSATS DE 2 CAMPS ====================

class TypePlacesStrategy(RefugiSearchStrategy):
    """Estratègia per a filtres: type + places (utilitza índex: type, places)"""
    
    def execute_query(self, db: firestore.Client, collection_name: str, filters: 'RefugiSearchFilters') -> List[Dict[str, Any]]:
        query = db.collection(collection_name)
        
        # Ordre segons índex: type, places
        query = query.where(filter=firestore.FieldFilter('type', 'in', filters.type))
        
        if filters.places_min is not None:
            query = query.where(filter=firestore.FieldFilter('places', '>=', filters.places_min))
        if filters.places_max is not None:
            query = query.where(filter=firestore.FieldFilter('places', '<=', filters.places_max))
        
        logger.log(23, f"Firestore QUERY: collection={collection_name} filters=type+places")
        docs = query.stream()
        return [doc.to_dict() for doc in docs]
    
    def get_strategy_name(self) -> str:
        return "TypePlacesStrategy"


class TypeAltitudeStrategy(RefugiSearchStrategy):
    """Estratègia per a filtres: type + altitude (utilitza índex: type, altitude)"""
    
    def execute_query(self, db: firestore.Client, collection_name: str, filters: 'RefugiSearchFilters') -> List[Dict[str, Any]]:
        query = db.collection(collection_name)
        
        # Ordre segons índex: type, altitude
        query = query.where(filter=firestore.FieldFilter('type', 'in', filters.type))
        
        if filters.altitude_min is not None:
            query = query.where(filter=firestore.FieldFilter('altitude', '>=', filters.altitude_min))
        if filters.altitude_max is not None:
            query = query.where(filter=firestore.FieldFilter('altitude', '<=', filters.altitude_max))
        
        logger.log(23, f"Firestore QUERY: collection={collection_name} filters=type+altitude")
        docs = query.stream()
        return [doc.to_dict() for doc in docs]
    
    def get_strategy_name(self) -> str:
        return "TypeAltitudeStrategy"


class ConditionPlacesStrategy(RefugiSearchStrategy):
    """Estratègia per a filtres: condition + places (utilitza índex: condition, places)"""
    
    def execute_query(self, db: firestore.Client, collection_name: str, filters: 'RefugiSearchFilters') -> List[Dict[str, Any]]:
        query = db.collection(collection_name)
        
        # Ordre segons índex: condition, places
        query = query.where(filter=firestore.FieldFilter('condition', 'in', filters.condition))
        
        if filters.places_min is not None:
            query = query.where(filter=firestore.FieldFilter('places', '>=', filters.places_min))
        if filters.places_max is not None:
            query = query.where(filter=firestore.FieldFilter('places', '<=', filters.places_max))
        
        logger.log(23, f"Firestore QUERY: collection={collection_name} filters=condition+places")
        docs = query.stream()
        return [doc.to_dict() for doc in docs]
    
    def get_strategy_name(self) -> str:
        return "ConditionPlacesStrategy"


class ConditionAltitudeStrategy(RefugiSearchStrategy):
    """Estratègia per a filtres: condition + altitude (utilitza índex: condition, altitude)"""
    
    def execute_query(self, db: firestore.Client, collection_name: str, filters: 'RefugiSearchFilters') -> List[Dict[str, Any]]:
        query = db.collection(collection_name)
        
        # Ordre segons índex: condition, altitude
        query = query.where(filter=firestore.FieldFilter('condition', 'in', filters.condition))
        
        if filters.altitude_min is not None:
            query = query.where(filter=firestore.FieldFilter('altitude', '>=', filters.altitude_min))
        if filters.altitude_max is not None:
            query = query.where(filter=firestore.FieldFilter('altitude', '<=', filters.altitude_max))
        
        logger.log(23, f"Firestore QUERY: collection={collection_name} filters=condition+altitude")
        docs = query.stream()
        return [doc.to_dict() for doc in docs]
    
    def get_strategy_name(self) -> str:
        return "ConditionAltitudeStrategy"


class TypePlacesAltitudeStrategy(RefugiSearchStrategy):
    """
    Estratègia per a filtres: type + places + altitude
    Utilitza índex type+places i filtra altitude manualment
    """
    
    def execute_query(self, db: firestore.Client, collection_name: str, filters: 'RefugiSearchFilters') -> List[Dict[str, Any]]:
        query = db.collection(collection_name)
        
        # Utilitza índex: type, places
        query = query.where(filter=firestore.FieldFilter('type', 'in', filters.type))
        
        if filters.places_min is not None:
            query = query.where(filter=firestore.FieldFilter('places', '>=', filters.places_min))
        if filters.places_max is not None:
            query = query.where(filter=firestore.FieldFilter('places', '<=', filters.places_max))
        
        logger.log(23, f"Firestore QUERY: collection={collection_name} filters=type+places (manual altitude)")
        docs = query.stream()
        results = [doc.to_dict() for doc in docs]
        
        # Filtre manual per altitude
        if filters.altitude_min is not None or filters.altitude_max is not None:
            filtered_results = []
            for refugi in results:
                altitude = refugi.get('altitude', 0)
                if filters.altitude_min is not None and altitude < filters.altitude_min:
                    continue
                if filters.altitude_max is not None and altitude > filters.altitude_max:
                    continue
                filtered_results.append(refugi)
            return filtered_results
        
        return results
    
    def get_strategy_name(self) -> str:
        return "TypePlacesAltitudeStrategy"


class ConditionPlacesAltitudeStrategy(RefugiSearchStrategy):
    """
    Estratègia per a filtres: condition + places + altitude
    Utilitza índex condition+places i filtra altitude manualment
    """
    
    def execute_query(self, db: firestore.Client, collection_name: str, filters: 'RefugiSearchFilters') -> List[Dict[str, Any]]:
        query = db.collection(collection_name)
        
        # Utilitza índex: condition, places
        query = query.where(filter=firestore.FieldFilter('condition', 'in', filters.condition))
        
        if filters.places_min is not None:
            query = query.where(filter=firestore.FieldFilter('places', '>=', filters.places_min))
        if filters.places_max is not None:
            query = query.where(filter=firestore.FieldFilter('places', '<=', filters.places_max))
        
        logger.log(23, f"Firestore QUERY: collection={collection_name} filters=condition+places (manual altitude)")
        docs = query.stream()
        results = [doc.to_dict() for doc in docs]
        
        # Filtre manual per altitude
        if filters.altitude_min is not None or filters.altitude_max is not None:
            filtered_results = []
            for refugi in results:
                altitude = refugi.get('altitude', 0)
                if filters.altitude_min is not None and altitude < filters.altitude_min:
                    continue
                if filters.altitude_max is not None and altitude > filters.altitude_max:
                    continue
                filtered_results.append(refugi)
            return filtered_results
        
        return results
    
    def get_strategy_name(self) -> str:
        return "ConditionPlacesAltitudeStrategy"


class PlacesAltitudeStrategy(RefugiSearchStrategy):
    """
    Estratègia per a filtres: places + altitude (sense type ni condition)
    Utilitza el filtre de places i filtra altitude manualment
    """
    
    def execute_query(self, db: firestore.Client, collection_name: str, filters: 'RefugiSearchFilters') -> List[Dict[str, Any]]:
        query = db.collection(collection_name)
        
        # Utilitza filtre de places (no hi ha índex compost sense type o condition)
        if filters.places_min is not None:
            query = query.where(filter=firestore.FieldFilter('places', '>=', filters.places_min))
        if filters.places_max is not None:
            query = query.where(filter=firestore.FieldFilter('places', '<=', filters.places_max))
        
        logger.log(23, f"Firestore QUERY: collection={collection_name} filters=places (manual altitude)")
        docs = query.stream()
        results = [doc.to_dict() for doc in docs]
        
        # Filtre manual per altitude
        if filters.altitude_min is not None or filters.altitude_max is not None:
            filtered_results = []
            for refugi in results:
                altitude = refugi.get('altitude', 0)
                if filters.altitude_min is not None and altitude < filters.altitude_min:
                    continue
                if filters.altitude_max is not None and altitude > filters.altitude_max:
                    continue
                filtered_results.append(refugi)
            return filtered_results
        
        return results
    
    def get_strategy_name(self) -> str:
        return "PlacesAltitudeStrategy"


# ==================== ESTRATÈGIES AMB UN SOL CAMP ====================

class TypeOnlyStrategy(RefugiSearchStrategy):
    """Estratègia per a filtres: només type"""
    
    def execute_query(self, db: firestore.Client, collection_name: str, filters: 'RefugiSearchFilters') -> List[Dict[str, Any]]:
        query = db.collection(collection_name)
        query = query.where(filter=firestore.FieldFilter('type', 'in', filters.type))
        
        logger.log(23, f"Firestore QUERY: collection={collection_name} filters=type")
        docs = query.stream()
        return [doc.to_dict() for doc in docs]
    
    def get_strategy_name(self) -> str:
        return "TypeOnlyStrategy"


class ConditionOnlyStrategy(RefugiSearchStrategy):
    """Estratègia per a filtres: només condition"""
    
    def execute_query(self, db: firestore.Client, collection_name: str, filters: 'RefugiSearchFilters') -> List[Dict[str, Any]]:
        query = db.collection(collection_name)
        query = query.where(filter=firestore.FieldFilter('condition', 'in', filters.condition))
        
        logger.log(23, f"Firestore QUERY: collection={collection_name} filters=condition")
        docs = query.stream()
        return [doc.to_dict() for doc in docs]
    
    def get_strategy_name(self) -> str:
        return "ConditionOnlyStrategy"


class PlacesOnlyStrategy(RefugiSearchStrategy):
    """Estratègia per a filtres: només places"""
    
    def execute_query(self, db: firestore.Client, collection_name: str, filters: 'RefugiSearchFilters') -> List[Dict[str, Any]]:
        query = db.collection(collection_name)
        
        if filters.places_min is not None:
            query = query.where(filter=firestore.FieldFilter('places', '>=', filters.places_min))
        if filters.places_max is not None:
            query = query.where(filter=firestore.FieldFilter('places', '<=', filters.places_max))
        
        logger.log(23, f"Firestore QUERY: collection={collection_name} filters=places")
        docs = query.stream()
        return [doc.to_dict() for doc in docs]
    
    def get_strategy_name(self) -> str:
        return "PlacesOnlyStrategy"


class AltitudeOnlyStrategy(RefugiSearchStrategy):
    """Estratègia per a filtres: només altitude"""
    
    def execute_query(self, db: firestore.Client, collection_name: str, filters: 'RefugiSearchFilters') -> List[Dict[str, Any]]:
        query = db.collection(collection_name)
        
        if filters.altitude_min is not None:
            query = query.where(filter=firestore.FieldFilter('altitude', '>=', filters.altitude_min))
        if filters.altitude_max is not None:
            query = query.where(filter=firestore.FieldFilter('altitude', '<=', filters.altitude_max))
        
        logger.log(23, f"Firestore QUERY: collection={collection_name} filters=altitude")
        docs = query.stream()
        return [doc.to_dict() for doc in docs]
    
    def get_strategy_name(self) -> str:
        return "AltitudeOnlyStrategy"


# ==================== SELECTOR D'ESTRATÈGIA ====================

class SearchStrategySelector:
    """Selector d'estratègia segons els filtres actius"""
    
    @staticmethod
    def select_strategy(filters: 'RefugiSearchFilters') -> RefugiSearchStrategy:
        """
        Selecciona l'estratègia òptima segons els filtres actius
        
        Args:
            filters: Filtres de cerca
            
        Returns:
            Estratègia de cerca adequada
        """
        has_type = bool(filters.type and len(filters.type) > 0)
        has_condition = bool(filters.condition and len(filters.condition) > 0)
        has_places = filters.places_min is not None or filters.places_max is not None
        has_altitude = filters.altitude_min is not None or filters.altitude_max is not None
        
        # Combinacions amb type + condition (prioritat màxima)
        if has_type and has_condition and has_places and has_altitude:
            # type + condition + places + altitude: usa índex type+condition+places, filtra altitude
            return TypeConditionPlacesAltitudeStrategy()
        
        if has_type and has_condition and has_places:
            # type + condition + places: índex directe
            return TypeConditionPlacesStrategy()
        
        if has_type and has_condition and has_altitude:
            # type + condition + altitude: índex directe
            return TypeConditionAltitudeStrategy()
        
        # Combinacions amb type (sense condition)
        if has_type and has_places and has_altitude:
            # type + places + altitude: usa índex type+places, filtra altitude
            return TypePlacesAltitudeStrategy()
        
        if has_type and has_places:
            # type + places: índex directe
            return TypePlacesStrategy()
        
        if has_type and has_altitude:
            # type + altitude: índex directe
            return TypeAltitudeStrategy()
        
        if has_type:
            # només type
            return TypeOnlyStrategy()
        
        # Combinacions amb condition (sense type)
        if has_condition and has_places and has_altitude:
            # condition + places + altitude: usa índex condition+places, filtra altitude
            return ConditionPlacesAltitudeStrategy()
        
        if has_condition and has_places:
            # condition + places: índex directe
            return ConditionPlacesStrategy()
        
        if has_condition and has_altitude:
            # condition + altitude: índex directe
            return ConditionAltitudeStrategy()
        
        if has_condition:
            # només condition
            return ConditionOnlyStrategy()
        
        # Combinacions sense type ni condition
        if has_places and has_altitude:
            # places + altitude: usa places, filtra altitude manualment
            return PlacesAltitudeStrategy()
        
        if has_places:
            # només places
            return PlacesOnlyStrategy()
        
        if has_altitude:
            # només altitude
            return AltitudeOnlyStrategy()
        
        # No hauria d'arribar aquí si _has_active_filters funciona correctament
        raise ValueError("No s'ha pogut determinar cap estratègia per als filtres proporcionats")
