"""
Controller per a la gestió de renovations
"""
import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from ..daos.renovation_dao import RenovationDAO
from ..daos.user_dao import UserDAO
from ..models.renovation import Renovation

logger = logging.getLogger(__name__)

class RenovationController:
    """Controller per gestionar operacions de renovations"""
    
    def __init__(self):
        """Inicialitza el controller"""
        self.renovation_dao = RenovationDAO()
        self.user_dao = UserDAO()
    
    def create_renovation(self, renovation_data: Dict[str, Any], creator_uid: str) -> Tuple[bool, Optional[Renovation], Optional[str]]:
        """
        Crea una nova renovation
        
        Args:
            renovation_data: Diccionari amb les dades de la renovation
            creator_uid: UID del creador
            
        Returns:
            tuple: (success, renovation_object, error_message)
        """
        try:
            # Afegir creator_uid
            renovation_data['creator_uid'] = creator_uid
            renovation_data['participants_uids'] = []
            
            # Comprovar solapaments temporals
            overlapping_renovation = self.renovation_dao.check_overlapping_renovations(
                renovation_data['refuge_id'],
                renovation_data['ini_date'],
                renovation_data['fin_date']
            )
            
            if overlapping_renovation:
                return False, overlapping_renovation, "Hi ha una altra renovation que es solapa temporalment amb aquest refugi"
            
            # Crear la renovation (retorna instància del model)
            renovation = self.renovation_dao.create_renovation(renovation_data)
            if not renovation:
                return False, None, "Error creant renovation a la base de dades"
            
            # Afegir l'ID de la renovation a l'usuari creador
            user_data = self.user_dao.get_user_by_uid(creator_uid)
            if user_data:
                created_renovations = user_data.get('created_renovations', [])
                created_renovations.append(renovation.id)
                self.user_dao.update_user(creator_uid, {'created_renovations': created_renovations})
            
            logger.info(f"Renovation creada correctament amb ID: {renovation.id}")
            return True, renovation, None
            
        except Exception as e:
            logger.error(f"Error en create_renovation: {str(e)}")
            return False, None, f"Error intern: {str(e)}"
    
    def get_renovation_by_id(self, renovation_id: str) -> Tuple[bool, Optional[Renovation], Optional[str]]:
        """
        Obté una renovation per ID
        
        Args:
            renovation_id: ID de la renovation
            
        Returns:
            tuple: (success, renovation_object, error_message)
        """
        try:
            renovation = self.renovation_dao.get_renovation_by_id(renovation_id)
            if not renovation:
                return False, None, f"Renovation amb ID {renovation_id} no trobada"
            
            return True, renovation, None
            
        except Exception as e:
            logger.error(f"Error en get_renovation_by_id: {str(e)}")
            return False, None, f"Error intern: {str(e)}"
    
    def get_all_renovations(self) -> Tuple[bool, List[Renovation], Optional[str]]:
        """
        Obté totes les renovations actives (ini_date >= data actual en zona horaria Madrid)
        El filtratge es fa directament al DAO per optimitzar la consulta a Firestore
        
        Returns:
            tuple: (success, list_of_renovations, error_message)
        """
        try:
            renovations = self.renovation_dao.get_all_renovations()
            return True, renovations, None
            
        except Exception as e:
            logger.error(f"Error en get_all_renovations: {str(e)}")
            return False, [], f"Error intern: {str(e)}"
    
    def update_renovation(self, renovation_id: str, update_data: Dict[str, Any], user_uid: str) -> Tuple[bool, Optional[Renovation], Optional[str]]:
        """
        Actualitza una renovation
        
        Args:
            renovation_id: ID de la renovation
            update_data: Dades a actualitzar
            user_uid: UID de l'usuari que fa l'actualització
            
        Returns:
            tuple: (success, renovation_object, error_message)
        """
        try:
            # Obtenir la renovation actual
            renovation = self.renovation_dao.get_renovation_by_id(renovation_id)
            if not renovation:
                return False, None, f"Renovation amb ID {renovation_id} no trobada"
            
            # Comprovar que l'usuari és el creador
            if renovation.creator_uid != user_uid:
                return False, None, "Només el creador pot editar la renovation"
            
            # Si s'actualitzen les dates, comprovar solapaments
            if 'ini_date' in update_data or 'fin_date' in update_data:
                ini_date = update_data.get('ini_date', renovation.ini_date)
                fin_date = update_data.get('fin_date', renovation.fin_date)
                
                # Validar que ini_date < fin_date
                if ini_date >= fin_date:
                    return False, None, "La data d'inici ha de ser anterior a la data de finalització"
                
                overlapping_renovation = self.renovation_dao.check_overlapping_renovations(
                    renovation.refuge_id,
                    ini_date,
                    fin_date,
                    exclude_id=renovation_id
                )
                
                if overlapping_renovation:
                    return False, overlapping_renovation, "Hi ha una altra renovation que es solapa temporalment amb aquest refugi"
            
            # Actualitzar
            success = self.renovation_dao.update_renovation(renovation_id, update_data)
            if not success:
                return False, None, "Error actualitzant renovation a la base de dades"
            
            # Obtenir la renovation actualitzada
            renovation = self.renovation_dao.get_renovation_by_id(renovation_id)
            
            logger.info(f"Renovation actualitzada correctament: {renovation_id}")
            return True, renovation, None
            
        except Exception as e:
            logger.error(f"Error en update_renovation: {str(e)}")
            return False, None, f"Error intern: {str(e)}"
    
    def delete_renovation(self, renovation_id: str, user_uid: str) -> Tuple[bool, Optional[str]]:
        """
        Elimina una renovation
        
        Args:
            renovation_id: ID de la renovation
            user_uid: UID de l'usuari que fa l'eliminació
            
        Returns:
            tuple: (success, error_message)
        """
        try:
            # Obtenir la renovation actual
            renovation = self.renovation_dao.get_renovation_by_id(renovation_id)
            if not renovation:
                return False, f"Renovation amb ID {renovation_id} no trobada"
            
            # Comprovar que l'usuari és el creador
            if renovation.creator_uid != user_uid:
                return False, "Només el creador pot eliminar la renovation"
            
            # Eliminar l'ID de la llista created_renovations del creador
            user_data = self.user_dao.get_user_by_uid(user_uid)
            if user_data:
                created_renovations = user_data.get('created_renovations', [])
                if renovation_id in created_renovations:
                    created_renovations.remove(renovation_id)
                    self.user_dao.update_user(user_uid, {'created_renovations': created_renovations})
            
            # Eliminar l'ID de la llista joined_renovations de tots els participants
            for participant_uid in renovation.participants_uids:
                participant_data = self.user_dao.get_user_by_uid(participant_uid)
                if participant_data:
                    joined_renovations = participant_data.get('joined_renovations', [])
                    if renovation_id in joined_renovations:
                        joined_renovations.remove(renovation_id)
                        self.user_dao.update_user(participant_uid, {'joined_renovations': joined_renovations})
            
            # Eliminar la renovation
            success = self.renovation_dao.delete_renovation(renovation_id)
            if not success:
                return False, "Error eliminant renovation de la base de dades"
            
            logger.info(f"Renovation eliminada correctament: {renovation_id}")
            return True, None
            
        except Exception as e:
            logger.error(f"Error en delete_renovation: {str(e)}")
            return False, f"Error intern: {str(e)}"
    
    def add_participant(self, renovation_id: str, participant_uid: str) -> Tuple[bool, Optional[Renovation], Optional[str]]:
        """
        Afegeix un participant a una renovation
        
        Args:
            renovation_id: ID de la renovation
            participant_uid: UID del participant
            
        Returns:
            tuple: (success, renovation_object, error_message)
        """
        try:
            # Obtenir la renovation
            renovation = self.renovation_dao.get_renovation_by_id(renovation_id)
            if not renovation:
                return False, None, f"Renovation amb ID {renovation_id} no trobada"
            
            # Comprovar que no és el creador
            if renovation.creator_uid == participant_uid:
                return False, None, "El creador no pot unir-se a la seva pròpia renovation"
            
            # Afegir participant
            success = self.renovation_dao.add_participant(renovation_id, participant_uid)
            if not success:
                return False, None, "Error afegint participant o ja és participant"
            
            # Afegir l'ID de la renovation a joined_renovations de l'usuari
            user_data = self.user_dao.get_user_by_uid(participant_uid)
            if user_data:
                joined_renovations = user_data.get('joined_renovations', [])
                if renovation_id not in joined_renovations:
                    joined_renovations.append(renovation_id)
                    self.user_dao.update_user(participant_uid, {'joined_renovations': joined_renovations})
            
            # Obtenir la renovation actualitzada
            renovation = self.renovation_dao.get_renovation_by_id(renovation_id)
            
            logger.info(f"Participant {participant_uid} afegit a renovation {renovation_id}")
            return True, renovation, None
            
        except Exception as e:
            logger.error(f"Error en add_participant: {str(e)}")
            return False, None, f"Error intern: {str(e)}"
    
    def remove_participant(self, renovation_id: str, participant_uid: str, requester_uid: str) -> Tuple[bool, Optional[Renovation], Optional[str]]:
        """
        Elimina un participant d'una renovation
        
        Args:
            renovation_id: ID de la renovation
            participant_uid: UID del participant a eliminar
            requester_uid: UID de l'usuari que fa la sol·licitud
            
        Returns:
            tuple: (success, renovation_object, error_message)
        """
        try:
            # Obtenir la renovation
            renovation = self.renovation_dao.get_renovation_by_id(renovation_id)
            if not renovation:
                return False, None, f"Renovation amb ID {renovation_id} no trobada"
            
            # Només el propi participant o el creador poden eliminar un participant
            if requester_uid != participant_uid and requester_uid != renovation.creator_uid:
                return False, None, "No tens permís per eliminar aquest participant"
            
            # Eliminar participant
            success = self.renovation_dao.remove_participant(renovation_id, participant_uid)
            if not success:
                return False, None, "Error eliminant participant o no és participant"
            
            # Eliminar l'ID de la renovation de joined_renovations de l'usuari
            user_data = self.user_dao.get_user_by_uid(participant_uid)
            if user_data:
                joined_renovations = user_data.get('joined_renovations', [])
                if renovation_id in joined_renovations:
                    joined_renovations.remove(renovation_id)
                    self.user_dao.update_user(participant_uid, {'joined_renovations': joined_renovations})
            
            # Obtenir la renovation actualitzada
            renovation = self.renovation_dao.get_renovation_by_id(renovation_id)
            
            logger.info(f"Participant {participant_uid} eliminat de renovation {renovation_id}")
            return True, renovation, None
            
        except Exception as e:
            logger.error(f"Error en remove_participant: {str(e)}")
            return False, None, f"Error intern: {str(e)}"
    
    def get_renovations_by_refuge(self, refuge_id: str, active_only: bool = False) -> Tuple[bool, List[Renovation], Optional[str]]:
        """
        Obté les renovations d'un refugi
        
        Args:
            refuge_id: ID del refugi
            active_only: Si True, només retorna renovations actives
            
        Returns:
            tuple: (success, list_of_renovations, error_message)
        """
        try:
            renovations = self.renovation_dao.get_renovations_by_refuge(refuge_id, active_only)
            return True, renovations, None
            
        except Exception as e:
            logger.error(f"Error en get_renovations_by_refuge: {str(e)}")
            return False, [], f"Error intern: {str(e)}"
    
    def get_user_renovations(self, user_uid: str) -> Tuple[bool, Dict[str, List[Renovation]], Optional[str]]:
        """
        Obté totes les renovations d'un usuari (creades i unides)
        
        Args:
            user_uid: UID de l'usuari
            
        Returns:
            tuple: (success, dict_with_created_and_joined, error_message)
        """
        try:
            # Obtenir l'usuari
            user_data = self.user_dao.get_user_by_uid(user_uid)
            if not user_data:
                return False, {}, f"Usuari amb UID {user_uid} no trobat"
            
            # Obtenir renovations creades
            created_ids = user_data.get('created_renovations', [])
            created_renovations = self.renovation_dao.get_renovations_by_ids(created_ids)
            
            # Obtenir renovations unides
            joined_ids = user_data.get('joined_renovations', [])
            joined_renovations = self.renovation_dao.get_renovations_by_ids(joined_ids)
            
            result = {
                'created': created_renovations,
                'joined': joined_renovations
            }
            
            return True, result, None
            
        except Exception as e:
            logger.error(f"Error en get_user_renovations: {str(e)}")
            return False, {}, f"Error intern: {str(e)}"
