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

            # Normalitzar dates a format YYYY-MM-DD per garantir ordenació correcta a Firestore
            from datetime import date, datetime as _dt
            if 'ini_date' in renovation_data:
                if isinstance(renovation_data['ini_date'], _dt):
                    renovation_data['ini_date'] = renovation_data['ini_date'].date().isoformat()
                elif isinstance(renovation_data['ini_date'], date):
                    renovation_data['ini_date'] = renovation_data['ini_date'].isoformat()
            if 'fin_date' in renovation_data:
                if isinstance(renovation_data['fin_date'], _dt):
                    renovation_data['fin_date'] = renovation_data['fin_date'].date().isoformat()
                elif isinstance(renovation_data['fin_date'], date):
                    renovation_data['fin_date'] = renovation_data['fin_date'].isoformat()

            # Crea la renovation
            doc_ref = db.collection(self.COLLECTION_NAME).document()
            renovation_data['id'] = doc_ref.id
            doc_ref.set(renovation_data)

            logger.info(f"Renovation creada amb ID: {doc_ref.id}")

            # Invalida cache de llistes
            cache_service.delete_pattern('renovation_list:*')
            cache_service.delete_pattern(f"renovation_refuge:{renovation_data['refuge_id']}:*")

            # Retornar la instància del model (usar les dades normalitzades)
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
        Obté totes les renovations actives (fin_date >= data actual en zona horaria Madrid)
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
            logger.log(23, f"Firestore READ: collection={self.COLLECTION_NAME} where fin_date>={madrid_today_str}")
            query = db.collection(self.COLLECTION_NAME)\
                        .where('fin_date', '>=', madrid_today_str)\
                        .order_by('ini_date')
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
            
            # Normalitzar dates a format YYYY-MM-DD per garantir ordenació correcta a Firestore
            from datetime import date, datetime as _dt
            if 'ini_date' in update_data:
                if isinstance(update_data['ini_date'], _dt):
                    update_data['ini_date'] = update_data['ini_date'].date().isoformat()
                elif isinstance(update_data['ini_date'], date):
                    update_data['ini_date'] = update_data['ini_date'].isoformat()
            if 'fin_date' in update_data:
                if isinstance(update_data['fin_date'], _dt):
                    update_data['fin_date'] = update_data['fin_date'].date().isoformat()
                elif isinstance(update_data['fin_date'], date):
                    update_data['fin_date'] = update_data['fin_date'].isoformat()
            
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
            query = db.collection(self.COLLECTION_NAME)
            
            if active_only:
                # Obtenir renovations que encara no han començat o estan en curs (zona horaria Madrid)
                madrid_today_str = get_madrid_today().isoformat()
                query = query\
                    .where('refuge_id', '==', refuge_id)\
                    .where('fin_date', '>=', madrid_today_str)\
                    .order_by('ini_date')
            else:
                query = query\
                    .where('refuge_id', '==', refuge_id)\
                    .order_by('ini_date')

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
    
    def check_overlapping_renovations(self, refuge_id: str, ini_date: str, fin_date: str, exclude_id: Optional[str] = None) -> Optional[Renovation]:
        """
        Comprova si hi ha renovations actives que es solapen temporalment per un refugi
        
        Args:
            refuge_id: ID del refugi
            ini_date: Data d'inici en format ISO (YYYY-MM-DD) o objecte date
            fin_date: Data de finalització en format ISO (YYYY-MM-DD) o objecte date
            exclude_id: ID de renovation a excloure de la comprovació (per edicions)
            
        Returns:
            Optional[Renovation]: Instància de la renovation que se solapa, o None si no hi ha solapament
        """
        try:
            # Normalitzar dates a format ISO string per comparació
            from datetime import date, datetime as _dt
            if isinstance(ini_date, (_dt, date)):
                ini_date = ini_date.isoformat() if isinstance(ini_date, date) else ini_date.date().isoformat()
            if isinstance(fin_date, (_dt, date)):
                fin_date = fin_date.isoformat() if isinstance(fin_date, date) else fin_date.date().isoformat()
            
            madrid_today_str = get_madrid_today().isoformat()
            
            db = self.firestore_service.get_db()
            
            # Obtenir renovations actives del refugi (utilitza índex compost: refuge_id + ini_date)
            logger.log(23, f"Firestore READ: collection={self.COLLECTION_NAME} where refuge_id={refuge_id} AND ini_date>={madrid_today_str}")
            query = db.collection(self.COLLECTION_NAME)\
                .where('refuge_id', '==', refuge_id)\
                .where('fin_date', '>=', madrid_today_str)\
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
    
    def add_participant(self, renovation_id: str, participant_uid: str) -> tuple[bool, Optional[str]]:
        """
        Afegeix un participant a una renovation
        
        Args:
            renovation_id: ID de la renovation
            participant_uid: UID del participant
            
        Returns:
            tuple: (success, error_code) on error_code pot ser 'not_found', 'expelled', 'already_participant', o None si èxit
        """
        try:
            db = self.firestore_service.get_db()
            doc_ref = db.collection(self.COLLECTION_NAME).document(renovation_id)
            
            # Obtenir la renovation actual
            doc = doc_ref.get()
            if not doc.exists:
                logger.warning(f"Renovation amb ID {renovation_id} no existeix")
                return False, 'not_found'
            
            renovation_data = doc.to_dict()
            participants = renovation_data.get('participants_uids', [])
            expelled = renovation_data.get('expelled_uids', [])
            refuge_id = renovation_data.get('refuge_id')
            
            # Comprovar si l'usuari està expulsat
            if participant_uid in expelled:
                logger.warning(f"Participant {participant_uid} està expulsat de la renovation {renovation_id}")
                return False, 'expelled'
            
            # Comprovar si ja és participant
            if participant_uid in participants:
                logger.warning(f"Participant {participant_uid} ja està a la renovation {renovation_id}")
                return False, 'already_participant'
            
            # Afegir participant
            participants.append(participant_uid)
            doc_ref.update({'participants_uids': participants})
            
            # Incrementar el comptador de refugis renovats de l'usuari
            from ..daos.user_dao import UserDAO
            user_dao = UserDAO()
            user_dao.increment_renovated_refuges(participant_uid)
            
            # Invalida cache de la renovation
            cache_service.delete(cache_service.generate_key('renovation_detail', renovation_id=renovation_id))
            cache_service.delete_pattern('renovation_list:*')
            if refuge_id:
                cache_service.delete_pattern(f'renovation_refuge:{refuge_id}:*')
            
            logger.info(f"Participant {participant_uid} afegit a renovation {renovation_id}")
            return True, None
            
        except Exception as e:
            logger.error(f"Error afegint participant a renovation {renovation_id}: {str(e)}")
            return False, None
    
    def remove_participant(self, renovation_id: str, participant_uid: str, is_expulsion: bool = False) -> bool:
        """
        Elimina un participant d'una renovation
        
        Args:
            renovation_id: ID de la renovation
            participant_uid: UID del participant
            is_expulsion: True si és una expulsió pel creador (l'usuari s'afegeix a expelled_uids)
            
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
            refuge_id = renovation_data.get('refuge_id')
            
            # Comprovar si és participant
            if participant_uid not in participants:
                logger.warning(f"Participant {participant_uid} no està a la renovation {renovation_id}")
                return False
            
            # Eliminar participant
            participants.remove(participant_uid)
            update_data = {'participants_uids': participants}
            
            # Si és una expulsió, afegir l'usuari a expelled_uids
            if is_expulsion:
                expelled = renovation_data.get('expelled_uids', [])
                if participant_uid not in expelled:
                    expelled.append(participant_uid)
                    update_data['expelled_uids'] = expelled
                    logger.info(f"Participant {participant_uid} afegit a expelled_uids de renovation {renovation_id}")
            
            doc_ref.update(update_data)
            
            # Decrementar el comptador de refugis renovats de l'usuari
            from ..daos.user_dao import UserDAO
            user_dao = UserDAO()
            user_dao.decrement_renovated_refuges(participant_uid)
            
            # Invalida cache de la renovation
            cache_service.delete(cache_service.generate_key('renovation_detail', renovation_id=renovation_id))
            cache_service.delete_pattern('renovation_list:*')
            if refuge_id:
                cache_service.delete_pattern(f'renovation_refuge:{refuge_id}:*')
            
            logger.info(f"Participant {participant_uid} eliminat de renovation {renovation_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error eliminant participant de renovation {renovation_id}: {str(e)}")
            return False
