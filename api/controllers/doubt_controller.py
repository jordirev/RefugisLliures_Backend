"""
Controller per a la gestió de dubtes i respostes
"""
import logging
from typing import Dict, Any, List, Optional, Tuple

from ..daos.doubt_dao import DoubtDAO
from ..daos.refugi_lliure_dao import RefugiLliureDAO
from ..models.doubt import Doubt, Answer
from ..utils.timezone_utils import get_madrid_now

logger = logging.getLogger(__name__)


class DoubtController:
    """Controller per a la gestió de dubtes i respostes"""
    
    def __init__(self):
        self.doubt_dao = DoubtDAO()
        self.refugi_dao = RefugiLliureDAO()
    
    def get_doubts_by_refuge(self, refuge_id: str) -> Tuple[Optional[List[Doubt]], Optional[str]]:
        """
        Obté tots els dubtes d'un refugi amb totes les seves respostes
        
        Args:
            refuge_id: ID del refugi
            
        Returns:
            (Llista de dubtes amb respostes o None, missatge d'error o None)
        """
        try:
            # Verificar que el refugi existeix
            if not self.refugi_dao.refugi_exists(refuge_id):
                return None, "Refuge not found"
            
            # Obtenir dubtes del DAO
            doubts = self.doubt_dao.get_doubts_by_refuge_id(refuge_id)
            
            return doubts, None
            
        except Exception as e:
            logger.error(f"Error obtenint dubtes del refugi {refuge_id}: {str(e)}")
            return None, f"Internal server error: {str(e)}"
    
    def create_doubt(
        self,
        refuge_id: str,
        creator_uid: str,
        message: str
    ) -> Tuple[Optional[Doubt], Optional[str]]:
        """
        Crea un nou dubte per a un refugi
        
        Args:
            refuge_id: ID del refugi
            creator_uid: UID de l'usuari creador
            message: Missatge del dubte
            
        Returns:
            (Model del dubte o None, missatge d'error o None)
        """
        try:
            # Verificar que el refugi existeix
            if not self.refugi_dao.refugi_exists(refuge_id):
                return None, "Refuge not found"
            
            created_at = get_madrid_now().isoformat()
            
            # Crear dades del dubte
            doubt_data = {
                'refuge_id': refuge_id,
                'creator_uid': creator_uid,
                'message': message,
                'created_at': created_at,
                'answers_count': 0
            }
            
            # Crear el dubte a Firestore
            doubt = self.doubt_dao.create_doubt(doubt_data)
            if not doubt:
                return None, "Error creating doubt"
            
            logger.info(f"Dubte creat amb ID: {doubt.id}")
            return doubt, None
            
        except Exception as e:
            logger.error(f"Error creant dubte: {str(e)}")
            return None, f"Internal server error: {str(e)}"
    
    def create_answer(
        self,
        doubt_id: str,
        creator_uid: str,
        message: str,
        parent_answer_id: Optional[str] = None
    ) -> Tuple[Optional[Answer], Optional[str]]:
        """
        Crea una nova resposta per a un dubte
        
        Args:
            doubt_id: ID del dubte
            creator_uid: UID de l'usuari creador
            message: Missatge de la resposta
            parent_answer_id: ID de l'answer pare si és una resposta a una resposta (opcional)
            
        Returns:
            (Model de la resposta o None, missatge d'error o None)
        """
        try:
            # Verificar que el dubte existeix
            doubt = self.doubt_dao.get_doubt_by_id(doubt_id)
            if not doubt:
                return None, "Doubt not found"
            
            # Si hi ha parent_answer_id, verificar que existeix
            if parent_answer_id:
                parent_answer = self.doubt_dao.get_answer_by_id(doubt_id, parent_answer_id)
                if not parent_answer:
                    return None, "Parent answer not found"
            
            created_at = get_madrid_now().isoformat()
            
            # Crear dades de la resposta
            answer_data = {
                'creator_uid': creator_uid,
                'message': message,
                'created_at': created_at,
                'parent_answer_id': parent_answer_id
            }
            
            # Crear la resposta a Firestore
            answer = self.doubt_dao.create_answer(doubt_id, answer_data)
            if not answer:
                return None, "Error creating answer"
            
            logger.info(f"Resposta creada amb ID: {answer.id} per al dubte {doubt_id}")
            return answer, None
            
        except Exception as e:
            logger.error(f"Error creant resposta: {str(e)}")
            return None, f"Internal server error: {str(e)}"
    
    def delete_doubt(self, doubt_id: str) -> Tuple[bool, Optional[str]]:
        """
        Elimina un dubte i totes les seves respostes
        
        Args:
            doubt_id: ID del dubte
            
        Returns:
            (True si s'ha eliminat correctament, missatge d'error o None)
        """
        try:
            # Verificar que el dubte existeix
            doubt = self.doubt_dao.get_doubt_by_id(doubt_id)
            if not doubt:
                return False, "Doubt not found"
            
            # Eliminar el dubte i les seves respostes
            success = self.doubt_dao.delete_doubt(doubt_id)
            if not success:
                return False, "Error deleting doubt"
            
            logger.info(f"Dubte eliminat amb ID: {doubt_id}")
            return True, None
            
        except Exception as e:
            logger.error(f"Error eliminant dubte: {str(e)}")
            return False, f"Internal server error: {str(e)}"
    
    def delete_answer(
        self,
        doubt_id: str,
        answer_id: str,
    ) -> Tuple[bool, Optional[str]]:
        """
        Elimina una resposta
        
        Args:
            doubt_id: ID del dubte
            answer_id: ID de la resposta
            
        Returns:
            (True si s'ha eliminat correctament, missatge d'error o None)
        """
        try:
            # Verificar que el dubte existeix
            doubt = self.doubt_dao.get_doubt_by_id(doubt_id)
            if not doubt:
                return False, "Doubt not found"
            
            # Verificar que la resposta existeix
            answer = self.doubt_dao.get_answer_by_id(doubt_id, answer_id)
            if not answer:
                return False, "Answer not found"
            
            # Eliminar la resposta
            success = self.doubt_dao.delete_answer(doubt_id, answer_id)
            if not success:
                return False, "Error deleting answer"
            
            logger.info(f"Resposta eliminada amb ID: {answer_id}")
            return True, None
            
        except Exception as e:
            logger.error(f"Error eliminant resposta: {str(e)}")
            return False, f"Internal server error: {str(e)}"
    
    def delete_doubts_by_creator(self, creator_uid: str) -> Tuple[bool, Optional[str]]:
        """
        Elimina tots els dubtes creats per un usuari
        
        Args:
            creator_uid: UID del creador
            
        Returns:
            Tuple (èxit: bool, missatge d'error: Optional[str])
        """
        try:
            success, error = self.doubt_dao.delete_doubts_by_creator(creator_uid)
            if not success:
                return False, error
            
            logger.info(f"Dubtes eliminats correctament per al creador {creator_uid}")
            return True, None
            
        except Exception as e:
            logger.error(f"Error eliminant dubtes del creador {creator_uid}: {str(e)}")
            return False, f"Internal server error: {str(e)}"
    
    def delete_answers_by_creator(self, creator_uid: str) -> Tuple[bool, Optional[str]]:
        """
        Elimina totes les respostes creades per un usuari
        
        Args:
            creator_uid: UID del creador
            
        Returns:
            Tuple (èxit: bool, missatge d'error: Optional[str])
        """
        try:
            success, error = self.doubt_dao.delete_answers_by_creator(creator_uid)
            if not success:
                return False, error
            
            logger.info(f"Respostes eliminades correctament per al creador {creator_uid}")
            return True, None
            
        except Exception as e:
            logger.error(f"Error eliminant respostes del creador {creator_uid}: {str(e)}")
            return False, f"Internal server error: {str(e)}"
