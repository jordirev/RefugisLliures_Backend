"""
Mapper per a la conversió entre dades de Firestore i models de refugi
"""
from typing import List, Dict, Any, Optional
from ..models.refugi_lliure import Refugi, RefugiCoordinates, Coordinates

class RefugiLliureMapper:
    """Mapper per convertir entre dades de Firestore i models de refugi"""
    
    @staticmethod
    def firestore_to_model(data: Dict[str, Any]) -> Refugi:
        """Converteix dades de Firestore a model Refugi"""
        return Refugi.from_dict(data)
    
    @staticmethod
    def model_to_firestore(refugi: Refugi) -> Dict[str, Any]:
        """Converteix model Refugi a format Firestore"""
        return refugi.to_dict()
    
    @staticmethod
    def firestore_list_to_models(data_list: List[Dict[str, Any]]) -> List[Refugi]:
        """Converteix llista de dades de Firestore a llista de models"""
        return [RefugiLliureMapper.firestore_to_model(data) for data in data_list]
    
    @staticmethod
    def models_to_firestore_list(refugis: List[Refugi]) -> List[Dict[str, Any]]:
        """Converteix llista de models a llista de dades Firestore"""
        return [RefugiLliureMapper.model_to_firestore(refugi) for refugi in refugis]
    
    @staticmethod
    def coordinates_firestore_to_model(data: Dict[str, Any]) -> RefugiCoordinates:
        """Converteix dades de coordenades de Firestore a model"""
        return RefugiCoordinates.from_dict(data)
    
    @staticmethod
    def coordinates_model_to_firestore(coords: RefugiCoordinates) -> Dict[str, Any]:
        """Converteix model de coordenades a format Firestore"""
        return coords.to_dict()
    
    @staticmethod
    def coordinates_list_to_models(data_list: List[Dict[str, Any]]) -> List[RefugiCoordinates]:
        """Converteix llista de coordenades de Firestore a models"""
        return [RefugiLliureMapper.coordinates_firestore_to_model(data) for data in data_list]
    
    @staticmethod
    def format_search_response(refugis: List[Refugi], filters: Dict[str, Any]) -> Dict[str, Any]:
        """Formatea la resposta de cerca"""
        return {
            'count': len(refugis),
            'results': [refugi.to_dict() for refugi in refugis],
            'filters': filters
        }
    
    @staticmethod
    def format_coordinates_response(
        coordinates: List[RefugiCoordinates], 
        total_available: int
    ) -> Dict[str, Any]:
        """Formatea la resposta de coordenades"""
        response = {
            'count': len(coordinates),
            'total_available': total_available,
            'coordinates': [coord.to_dict() for coord in coordinates]
        }
        
        return response