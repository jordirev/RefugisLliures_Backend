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
    def format_search_response(refugis: List[Refugi]) -> Dict[str, Any]:
        """
        Formatea la resposta de cerca
        Args:
            refugis: Llista de refugis
            include_visitors: Si True, inclou la llista de visitants. Si False, l'omet.
            include_media_metadata: Si True, inclou media_metadata i images_metadata. Si False, els omet.
        """
        results = []
        for refugi in refugis:                 
            results.append(refugi.to_dict())
        
        return {
            'count': len(refugis),
            'has_filters': True,
            'results': results
        }
    
    @staticmethod
    def format_search_response_from_raw_data(refugis_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Formatea la resposta de cerca des de dades raw (per coordenades)"""
        return {
            'count': len(refugis_data),
            'has_filters': False,
            'results': refugis_data
        }
    
