"""
Mapper per a la conversió entre dades de Firestore i models d'experiència
"""
from typing import Dict, Any, List
from ..models.experience import Experience


class ExperienceMapper:
    """Mapper per convertir entre dades de Firestore i models d'experiència"""
    
    @staticmethod
    def firestore_to_model(data: Dict[str, Any]) -> Experience:
        """Converteix dades de Firestore a model Experience"""
        return Experience.from_dict(data)
    
    @staticmethod
    def model_to_firestore(experience: Experience) -> Dict[str, Any]:
        """
        Converteix model Experience a format Firestore.
        Elimina images_metadata ja que no es guarda a Firestore.
        """
        experience_dict = experience.to_dict()
        # Eliminar images_metadata ja que no es guarda a Firestore
        if 'images_metadata' in experience_dict:
            experience_dict.pop('images_metadata')
        return experience_dict
    
    @staticmethod
    def firestore_list_to_models(data_list: List[Dict[str, Any]]) -> List[Experience]:
        """Converteix llista de dades de Firestore a llista de models"""
        return [ExperienceMapper.firestore_to_model(data) for data in data_list]
    
    @staticmethod
    def models_to_firestore_list(experiences: List[Experience]) -> List[Dict[str, Any]]:
        """Converteix llista de models a llista de dades Firestore"""
        return [ExperienceMapper.model_to_firestore(experience) for experience in experiences]
