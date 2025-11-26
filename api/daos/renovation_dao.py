"""
DAO per a la gestió de renovations amb Firestore
"""
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from ..services.firestore_service import FirestoreService
from ..services.cache_service import cache_service
from ..mappers.renovation_mapper import RenovationMapper
from ..models.renovation import Renovation
from ..utils.timezone_utils import get_madrid_today

logger = logging.getLogger(__name__)

class RenovationDAO:
    """Data Access Object per a renovations"""
    
    COLLECTION_NAME = 'renovations'
    
    def __init__(self):
        """Inicialitza el DAO amb la connexió a Firestore"""
        self.firestore_service = FirestoreService()
        self.mapper = RenovationMapper()
    
    def create_renovation(self, renovation_data: Dict[str, Any]) -> Optional[Renovation]:
        """
        Crea una nova renovation a Firestore
        
        Args:
            renovation_data: Diccionari amb les dades de la renovation
            
        Returns:
            Renovation: Instància del model Renovation creada o None si hi ha error
        """
        try:
            db = self.firestore_service.get_db()
            
            # Crea la renovation
            doc_ref = db.collection(self.COLLECTION_NAME).document()
            renovation_data['id'] = doc_ref.id
            doc_ref.set(renovation_data)
            
            logger.info(f"Renovation creada amb ID: {doc_ref.id}")
            
            # Invalida cache de llistes
            cache_service.delete_pattern('renovation_list:*')
            cache_service.delete_pattern(f"renovation_refuge:{renovation_data['refuge_id']}:*")
            
            # Retornar la instància del model
            return self.mapper.firestore_to_model(renovation_data)
            
        except Exception as e:
            logger.error(f"Error creant renovation: {str(e)}")
            return None
    
    def get_renovation_by_id(self, renovation_id: str) -> Optional[Renovation]:
        """
        Obté una renovation per ID
        
        Args:
            renovation_id: ID de la renovation
            
        Returns:
            Renovation: Instància del model Renovation o None si no existeix
        """
        # Genera clau de cache
        cache_key = cache_service.generate_key('renovation_detail', renovation_id=renovation_id)
        
        # Intenta obtenir de cache
        cached_data = cache_service.get(cache_key)
        if cached_data is not None:
            return self.mapper.firestore_to_model(cached_data)
        
        try:
            db = self.firestore_service.get_db()
            doc_ref = db.collection(self.COLLECTION_NAME).document(renovation_id)
            logger.log(23, f"Firestore READ: collection={self.COLLECTION_NAME} document={renovation_id}")
            doc = doc_ref.get()
            
            if doc.exists:
                renovation_data = doc.to_dict()
                renovation_data['id'] = doc.id
                
                # Guarda a cache
                timeout = cache_service.get_timeout('renovation_detail')
                cache_service.set(cache_key, renovation_data, timeout)
                
                logger.log(23, f"Renovation trobada amb ID: {renovation_id}")
                return self.mapper.firestore_to_model(renovation_data)
            else:
                logger.warning(f"Renovation no trobada amb ID: {renovation_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error obtenint renovation amb ID {renovation_id}: {str(e)}")
            return None
    
    def get_all_renovations(self) -> List[Renovation]:
        """
        Obté totes les renovations actives (ini_date >= data actual en zona horaria Madrid)
        Filtra directament a Firestore per optimitzar la consulta
        
        Returns:
            List d'instàncies del model Renovation
        """
        # Genera clau de cache amb la data actual per evitar servir dades obsoletes
        madrid_today = get_madrid_today()
        cache_key = cache_service.generate_key('renovation_list', list_type='active', date=madrid_today.isoformat())
        
        # Intenta obtenir de cache
        cached_data = cache_service.get(cache_key)
        if cached_data is not None:
            return self.mapper.firestore_list_to_models(cached_data)
        
        try:
            db = self.firestore_service.get_db()
            madrid_today_str = madrid_today.isoformat()
            
            # Filtrar directament a Firestore per obtenir només renovations actives
            logger.log(23, f"Firestore READ: collection={self.COLLECTION_NAME} where ini_date>={madrid_today_str}")
            query = db.collection(self.COLLECTION_NAME).where('ini_date', '>=', madrid_today_str).order_by('ini_date')
            docs = query.stream()
            
            renovations_data = []
            for doc in docs:
                renovation_data = doc.to_dict()
                renovation_data['id'] = doc.id
                renovations_data.append(renovation_data)
            
            # Guarda a cache amb timeout més curt (les dades canvien cada dia)
            timeout = cache_service.get_timeout('renovation_list')
            cache_service.set(cache_key, renovations_data, timeout)
            
            logger.log(23, f"Trobades {len(renovations_data)} renovations actives")
            return self.mapper.firestore_list_to_models(renovations_data)
            
        except Exception as e:
            logger.error(f"Error obtenint renovations actives: {str(e)}")
            return []
    
    def update_renovation(self, renovation_id: str, update_data: Dict[str, Any]) -> bool:
        """
        Actualitza una renovation
        
        Args:
            renovation_id: ID de la renovation
            update_data: Dades a actualitzar
            
        Returns:
            bool: True si s'ha actualitzat correctament, False altrament
        """
        try:
            db = self.firestore_service.get_db()
            doc_ref = db.collection(self.COLLECTION_NAME).document(renovation_id)
            
            # Comprova que existeix i obté les dades actuals
            doc = doc_ref.get()
            if not doc.exists:
                logger.warning(f"Renovation amb ID {renovation_id} no existeix")
                return False
            
            renovation_data = doc.to_dict()
            refuge_id = renovation_data.get('refuge_id')
            
            # Actualitza només els camps proporcionats
            doc_ref.update(update_data)
            
            # Invalida cache
            cache_service.delete(cache_service.generate_key('renovation_detail', renovation_id=renovation_id))
            cache_service.delete_pattern('renovation_list:*')
            if refuge_id:
                cache_service.delete_pattern(f'renovation_refuge:{refuge_id}:*')
            
            logger.info(f"Renovation actualitzada: {renovation_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error actualitzant renovation {renovation_id}: {str(e)}")
            return False
    
    def delete_renovation(self, renovation_id: str) -> bool:
        """
        Elimina una renovation
        
        Args:
            renovation_id: ID de la renovation
            
        Returns:
            bool: True si s'ha eliminat correctament, False altrament
        """
        try:
            db = self.firestore_service.get_db()
            doc_ref = db.collection(self.COLLECTION_NAME).document(renovation_id)
            
            # Comprova que existeix i obté les dades actuals
            doc = doc_ref.get()
            if not doc.exists:
                logger.warning(f"Renovation amb ID {renovation_id} no existeix")
                return False
            
            renovation_data = doc.to_dict()
            refuge_id = renovation_data.get('refuge_id')
            
            doc_ref.delete()
            
            # Invalida cache
            cache_service.delete(cache_service.generate_key('renovation_detail', renovation_id=renovation_id))
            cache_service.delete_pattern('renovation_list:*')
            if refuge_id:
                cache_service.delete_pattern(f'renovation_refuge:{refuge_id}:*')
            
            logger.info(f"Renovation eliminada: {renovation_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error eliminant renovation {renovation_id}: {str(e)}")
            return False
    
    def get_renovations_by_refuge(self, refuge_id: str, active_only: bool = False) -> List[Renovation]:
        """
        Obté les renovations d'un refugi
        
        Args:
            refuge_id: ID del refugi
            active_only: Si True, només retorna renovations actives (ini_date >= avui)
            
        Returns:
            List d'instàncies del model Renovation
        """
        # Genera clau de cache
        active_str = 'active' if active_only else 'all'
        cache_key = cache_service.generate_key('renovation_refuge', refuge_id=refuge_id, active=active_str)
        
        # Intenta obtenir de cache
        cached_data = cache_service.get(cache_key)
        if cached_data is not None:
            return self.mapper.firestore_list_to_models(cached_data)
        
        try:
            db = self.firestore_service.get_db()
            query = db.collection(self.COLLECTION_NAME).where('refuge_id', '==', refuge_id)
            
            if active_only:
                # Obtenir renovations que encara no han començat o estan en curs (zona horaria Madrid)
                madrid_today_str = get_madrid_today().isoformat()
                query = query.where('ini_date', '>=', madrid_today_str).order_by('ini_date')
            
            logger.log(23, f"Firestore READ: collection={self.COLLECTION_NAME} where refuge_id={refuge_id}")
            docs = query.stream()
            
            renovations_data = []
            for doc in docs:
                renovation_data = doc.to_dict()
                renovation_data['id'] = doc.id
                renovations_data.append(renovation_data)
            
            # Guarda a cache
            timeout = cache_service.get_timeout('renovation_list')
            cache_service.set(cache_key, renovations_data, timeout)
            
            logger.log(23, f"Trobades {len(renovations_data)} renovations per refugi {refuge_id}")
            return self.mapper.firestore_list_to_models(renovations_data)
            
        except Exception as e:
            logger.error(f"Error obtenint renovations per refugi {refuge_id}: {str(e)}")
            return []
    
    def get_renovations_by_ids(self, renovation_ids: List[str]) -> List[Renovation]:
        """
        Obté múltiples renovations per IDs
        
        Args:
            renovation_ids: Llista d'IDs de renovations
            
        Returns:
            List d'instàncies del model Renovation
        """
        if not renovation_ids:
            return []
        
        try:
            renovations = []
            
            # Obtenir cada renovation individualment
            for renovation_id in renovation_ids:
                renovation = self.get_renovation_by_id(renovation_id)
                if renovation:
                    renovations.append(renovation)
            
            logger.log(23, f"Trobades {len(renovations)} renovations de {len(renovation_ids)} sol·licitades")
            return renovations
            
        except Exception as e:
            logger.error(f"Error obtenint renovations per IDs: {str(e)}")
            return []
    
    def check_overlapping_renovations(self, refuge_id: str, ini_date: str, fin_date: str, exclude_id: Optional[str] = None) -> Optional[Renovation]:
        """
        Comprova si hi ha renovations actives que es solapen temporalment per un refugi
        
        Args:
            refuge_id: ID del refugi
            ini_date: Data d'inici en format ISO (YYYY-MM-DD)
            fin_date: Data de finalització en format ISO (YYYY-MM-DD)
            exclude_id: ID de renovation a excloure de la comprovació (per edicions)
            
        Returns:
            Optional[Renovation]: Instància de la renovation que se solapa, o None si no hi ha solapament
        """
        try:
            madrid_today_str = get_madrid_today().isoformat()
            
            db = self.firestore_service.get_db()
            
            # Obtenir renovations actives del refugi (utilitza índex compost: refuge_id + ini_date)
            logger.log(23, f"Firestore READ: collection={self.COLLECTION_NAME} where refuge_id={refuge_id} AND ini_date>={madrid_today_str}")
            query = db.collection(self.COLLECTION_NAME)\
                .where('refuge_id', '==', refuge_id)\
                .where('ini_date', '>=', madrid_today_str)\
                .order_by('ini_date')
            docs = query.stream()
            
            for doc in docs:
                # Excloure la renovation que s'està editant
                if exclude_id and doc.id == exclude_id:
                    continue
                
                data = doc.to_dict()
                existing_ini = data.get('ini_date')
                existing_fin = data.get('fin_date')
                
                # Comprovar solapament: les dates es solapen si:
                # - La nova inici està entre l'existent inici i fi
                # - La nova fi està entre l'existent inici i fi
                # - La nova inici és abans de l'existent inici i la nova fi és després de l'existent fi
                if (existing_ini <= ini_date <= existing_fin or
                    existing_ini <= fin_date <= existing_fin or
                    (ini_date <= existing_ini and fin_date >= existing_fin)):
                    logger.warning(f"Solapament detectat amb renovation {doc.id}")
                    data['id'] = doc.id
                    return self.mapper.firestore_to_model(data)
            
            return None
            
        except Exception as e:
            logger.error(f"Error comprovant solapaments: {str(e)}")
            return None
    
    def add_participant(self, renovation_id: str, participant_uid: str) -> bool:
        """
        Afegeix un participant a una renovation
        
        Args:
            renovation_id: ID de la renovation
            participant_uid: UID del participant
            
        Returns:
            bool: True si s'ha afegit correctament, False altrament
        """
        try:
            db = self.firestore_service.get_db()
            doc_ref = db.collection(self.COLLECTION_NAME).document(renovation_id)
            
            # Obtenir la renovation actual
            doc = doc_ref.get()
            if not doc.exists:
                logger.warning(f"Renovation amb ID {renovation_id} no existeix")
                return False
            
            renovation_data = doc.to_dict()
            participants = renovation_data.get('participants_uids', [])
            
            # Comprovar si ja és participant
            if participant_uid in participants:
                logger.warning(f"Participant {participant_uid} ja està a la renovation {renovation_id}")
                return False
            
            # Afegir participant
            participants.append(participant_uid)
            doc_ref.update({'participants_uids': participants})
            
            # Invalida cache
            cache_service.delete(cache_service.generate_key('renovation_detail', renovation_id=renovation_id))
            cache_service.delete_pattern('renovation_list:*')
            
            logger.info(f"Participant {participant_uid} afegit a renovation {renovation_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error afegint participant a renovation {renovation_id}: {str(e)}")
            return False
    
    def remove_participant(self, renovation_id: str, participant_uid: str) -> bool:
        """
        Elimina un participant d'una renovation
        
        Args:
            renovation_id: ID de la renovation
            participant_uid: UID del participant
            
        Returns:
            bool: True si s'ha eliminat correctament, False altrament
        """
        try:
            db = self.firestore_service.get_db()
            doc_ref = db.collection(self.COLLECTION_NAME).document(renovation_id)
            
            # Obtenir la renovation actual
            doc = doc_ref.get()
            if not doc.exists:
                logger.warning(f"Renovation amb ID {renovation_id} no existeix")
                return False
            
            renovation_data = doc.to_dict()
            participants = renovation_data.get('participants_uids', [])
            
            # Comprovar si és participant
            if participant_uid not in participants:
                logger.warning(f"Participant {participant_uid} no està a la renovation {renovation_id}")
                return False
            
            # Eliminar participant
            participants.remove(participant_uid)
            doc_ref.update({'participants_uids': participants})
            
            # Invalida cache
            cache_service.delete(cache_service.generate_key('renovation_detail', renovation_id=renovation_id))
            cache_service.delete_pattern('renovation_list:*')
            
            logger.info(f"Participant {participant_uid} eliminat de renovation {renovation_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error eliminant participant de renovation {renovation_id}: {str(e)}")
            return False
