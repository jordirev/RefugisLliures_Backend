"""
Mapper per a la conversió entre dades de Firestore i models de dubtes i respostes
"""
from typing import Dict, Any, List
from ..models.doubt import Doubt, Answer


class AnswerMapper:
    """Mapper per convertir entre dades de Firestore i models d'Answer"""
    
    @staticmethod
    def firestore_to_model(data: Dict[str, Any]) -> Answer:
        """Converteix dades de Firestore a model Answer"""
        return Answer.from_dict(data)
    
    @staticmethod
    def model_to_firestore(answer: Answer) -> Dict[str, Any]:
        """Converteix model Answer a format Firestore"""
        return answer.to_dict()
    
    @staticmethod
    def firestore_list_to_models(data_list: List[Dict[str, Any]]) -> List[Answer]:
        """Converteix llista de dades de Firestore a llista de models Answer"""
        return [AnswerMapper.firestore_to_model(data) for data in data_list]
    
    @staticmethod
    def models_to_firestore_list(answers: List[Answer]) -> List[Dict[str, Any]]:
        """Converteix llista de models Answer a llista de dades Firestore"""
        return [AnswerMapper.model_to_firestore(answer) for answer in answers]


class DoubtMapper:
    """Mapper per convertir entre dades de Firestore i models de Doubt"""
    
    @staticmethod
    def firestore_to_model(data: Dict[str, Any], answers: List[Answer] = None) -> Doubt:
        """Converteix dades de Firestore a model Doubt"""
        return Doubt.from_dict(data, answers)
    
    @staticmethod
    def model_to_firestore(doubt: Doubt) -> Dict[str, Any]:
        """
        Converteix model Doubt a format Firestore.
        Elimina el camp 'answers' ja que no es guarda a Firestore (es guarda a subcollection).
        """
        doubt_dict = doubt.to_dict()
        # Eliminar answers ja que no es guarda al document principal
        if 'answers' in doubt_dict:
            doubt_dict.pop('answers')
        return doubt_dict
    
    @staticmethod
    def firestore_list_to_models(data_list: List[Dict[str, Any]]) -> List[Doubt]:
        """Converteix llista de dades de Firestore a llista de models Doubt"""
        return [DoubtMapper.firestore_to_model(data) for data in data_list]
    
    @staticmethod
    def models_to_firestore_list(doubts: List[Doubt]) -> List[Dict[str, Any]]:
        """Converteix llista de models Doubt a llista de dades Firestore"""
        return [DoubtMapper.model_to_firestore(doubt) for doubt in doubts]
