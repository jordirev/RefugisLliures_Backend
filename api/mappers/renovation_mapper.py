"""
Mapper per a la conversió entre dades de Firestore i models de renovation
"""
from typing import List, Dict, Any, Optional
from ..models.renovation import Renovation

class RenovationMapper:
    """Mapper per convertir entre dades de Firestore i models de renovation"""
    
    @staticmethod
    def firestore_to_model(data: Dict[str, Any]) -> Renovation:
        """Converteix dades de Firestore a model Renovation"""
        return Renovation.from_dict(data)
    
    @staticmethod
    def model_to_firestore(renovation: Renovation) -> Dict[str, Any]:
        """Converteix model Renovation a format Firestore"""
        return renovation.to_dict()
    
    @staticmethod
    def firestore_list_to_models(data_list: List[Dict[str, Any]]) -> List[Renovation]:
        """Converteix llista de dades de Firestore a llista de models"""
        return [RenovationMapper.firestore_to_model(data) for data in data_list]
    
    @staticmethod
    def models_to_firestore_list(renovations: List[Renovation]) -> List[Dict[str, Any]]:
        """Converteix llista de models a llista de dades Firestore"""
        return [RenovationMapper.model_to_firestore(renovation) for renovation in renovations]