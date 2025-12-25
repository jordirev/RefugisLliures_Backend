"""
DAO per a la gestió de visites a refugis amb Firestore
"""
import logging
from typing import List, Optional, Dict, Any
from datetime import date
from firebase_admin import firestore
from ..services.firestore_service import FirestoreService
from ..services.cache_service import cache_service
from ..mappers.refuge_visit_mapper import RefugeVisitMapper
from ..models.refuge_visit import RefugeVisit, UserVisit

logger = logging.getLogger(__name__)


class RefugeVisitDAO:
    """Data Access Object per a visites a refugis"""
    
    COLLECTION_NAME = 'refuge_visits'
    
    def __init__(self):
        """Inicialitza el DAO amb la connexió a Firestore"""
        self.firestore_service = FirestoreService()
        self.mapper = RefugeVisitMapper()
    
    def create_visit(self, data: Dict[str, Any]) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Crea una nova visita amb les dades ja transformades
        
        Args:
            data: Diccionari amb les dades de la visita (ja transformat amb mapper.model_to_firebase)
            
        Returns:
            tuple: (success, visit_id, error_message)
        """
        try:
            db = self.firestore_service.get_db()
            
            logger.log(23, f"Firestore CREATE: collection={self.COLLECTION_NAME}")
            doc_ref = db.collection(self.COLLECTION_NAME).document()
            doc_ref.set(data)
            
            # Invalida cache de llista
            refuge_id = data.get('refuge_id')
            if refuge_id:
                self._invalidate_list_cache(refuge_id)
            
            logger.info(f"Visita creada amb ID: {doc_ref.id}")
            return True, doc_ref.id, None
            
        except Exception as e:
            logger.error(f"Error creant visita: {str(e)}")
            return False, None, f"Error creant visita: {str(e)}"
    
    def get_visit_by_id(self, visit_id: str) -> Optional[RefugeVisit]:
        """
        Obté una visita per ID amb cache
        
        Args:
            visit_id: ID de la visita
            
        Returns:
            RefugeVisit: Instància del model RefugeVisit o None si no existeix
        """
        cache_key = cache_service.generate_key('refuge_visit_detail', visit_id=visit_id)
        
        # Intenta obtenir de cache
        cached_data = cache_service.get(cache_key)
        if cached_data is not None:
            return self.mapper.firebase_to_model(cached_data)
        
        try:
            db = self.firestore_service.get_db()
            doc_ref = db.collection(self.COLLECTION_NAME).document(visit_id)
            logger.log(23, f"Firestore READ: collection={self.COLLECTION_NAME} document={visit_id}")
            doc = doc_ref.get()
            
            if doc.exists:
                visit_data = doc.to_dict()
                
                # Guarda a cache
                timeout = cache_service.get_timeout('refuge_visit_detail')
                cache_service.set(cache_key, visit_data, timeout)
                
                logger.info(f"Visita trobada amb ID: {visit_id}")
                return self.mapper.firebase_to_model(visit_data)
            else:
                logger.warning(f"Visita no trobada amb ID: {visit_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error obtenint visita amb ID {visit_id}: {str(e)}")
            return None
    
    def get_visit_by_refuge_and_date(self, refuge_id: str, visit_date: str) -> Optional[tuple[str, RefugeVisit]]:
        """
        Obté una visita per refuge_id i date
        
        Args:
            refuge_id: ID del refugi
            visit_date: Data de la visita (format YYYY-MM-DD)
            
        Returns:
            tuple: (visit_id, RefugeVisit) o None si no existeix
        """
        try:
            db = self.firestore_service.get_db()
            logger.log(23, f"Firestore QUERY: collection={self.COLLECTION_NAME} filter=refuge_id=={refuge_id} AND date=={visit_date}")
            query = db.collection(self.COLLECTION_NAME).where(
                filter=firestore.FieldFilter('refuge_id', '==', refuge_id)
            ).where(
                filter=firestore.FieldFilter('date', '==', visit_date)
            ).limit(1)
            
            docs = query.get()
            
            if docs:
                doc = docs[0]
                visit_data = doc.to_dict()
                visit = self.mapper.firebase_to_model(visit_data)
                
                # Guarda a cache
                cache_key = cache_service.generate_key('refuge_visit_detail', visit_id=doc.id)
                timeout = cache_service.get_timeout('refuge_visit_detail')
                cache_service.set(cache_key, visit_data, timeout)
                
                logger.info(f"Visita trobada: {doc.id}")
                return (doc.id, visit)
            
            logger.warning(f"Visita no trobada per refuge_id={refuge_id} i date={visit_date}")
            return None
            
        except Exception as e:
            logger.error(f"Error obtenint visita: {str(e)}")
            return None
    
    def get_visits_by_refuge(self, refuge_id: str, from_date: date) -> List[RefugeVisit]:
        """
        Obté totes les visites futures d'un refugi (ordenades per data ascendent) amb cache
        
        Args:
            refuge_id: ID del refugi
            from_date: Data mínima (inclusiva)
            
        Returns:
            List[RefugeVisit]: Llista de visites
        """
        cache_key = cache_service.generate_key('refuge_visits_list', refuge_id=refuge_id, from_date=from_date.isoformat())
        
        # Intenta obtenir de cache
        cached_data = cache_service.get(cache_key)
        if cached_data is not None:
            return [self.mapper.firebase_to_model(visit_data) for visit_data in cached_data]
        
        try:
            db = self.firestore_service.get_db()
            logger.log(23, f"Firestore QUERY: collection={self.COLLECTION_NAME} filter=refuge_id=={refuge_id} AND date>={from_date.isoformat()} order_by=date ASC")
            query = db.collection(self.COLLECTION_NAME).where(
                filter=firestore.FieldFilter('refuge_id', '==', refuge_id)
            ).where(
                filter=firestore.FieldFilter('date', '>=', from_date.isoformat())
            ).order_by('date')
            
            docs = query.get()
            visits = []
            visits_data = []
            
            for doc in docs:
                visit_data = doc.to_dict()
                visits.append(self.mapper.firebase_to_model(visit_data))
                visits_data.append(visit_data)
            
            # Guarda a cache
            timeout = cache_service.get_timeout('refuge_visits_list')
            cache_service.set(cache_key, visits_data, timeout)
            
            logger.info(f"Obtingudes {len(visits)} visites per al refugi {refuge_id}")
            return visits
            
        except Exception as e:
            logger.error(f"Error obtenint visites del refugi {refuge_id}: {str(e)}")
            return []
    
    def get_visits_by_user(self, uid: str) -> List[tuple[str, RefugeVisit]]:
        """
        Obté totes les visites d'un usuari (ordenades per data descendent)
        
        Args:
            uid: UID de l'usuari
            
        Returns:
            List[tuple[str, RefugeVisit]]: Llista de tuples (visit_id, RefugeVisit)
        """
        try:
            db = self.firestore_service.get_db()
            logger.log(23, f"Firestore QUERY: collection={self.COLLECTION_NAME} filter=visitors array_contains uid={uid} order_by=date DESC")
            
            # Firestore no pot fer array-contains amb objectes, així que necessitem fer un filtre més manual
            # Obtenim totes les visites i filtrem en memòria
            query = db.collection(self.COLLECTION_NAME).order_by('date', direction=firestore.Query.DESCENDING)
            
            docs = query.get()
            visits = []
            
            for doc in docs:
                visit_data = doc.to_dict()
                visitors = visit_data.get('visitors', [])
                
                # Comprova si l'usuari està a la llista de visitors
                user_found = False
                for visitor in visitors:
                    if visitor.get('uid') == uid:
                        user_found = True
                        break
                
                if user_found:
                    visit = self.mapper.firebase_to_model(visit_data)
                    visits.append((doc.id, visit))
            
            logger.info(f"Obtingudes {len(visits)} visites per a l'usuari {uid}")
            return visits
            
        except Exception as e:
            logger.error(f"Error obtenint visites de l'usuari {uid}: {str(e)}")
            return []
    
    def add_visitor_to_visit(self, visit_id: str, data: Dict[str, Any]) -> bool:
        """
        Afegeix un visitant a una visita amb les dades ja transformades
        
        Args:
            visit_id: ID de la visita
            data: Diccionari amb les dades de la visita actualitzada (ja transformat amb mapper.model_to_firebase)
            
        Returns:
            bool: True si l'operació ha tingut èxit, False altrament
        """
        try:
            db = self.firestore_service.get_db()
            doc_ref = db.collection(self.COLLECTION_NAME).document(visit_id)
            
            logger.log(23, f"Firestore READ: collection={self.COLLECTION_NAME} document={visit_id}")
            doc = doc_ref.get()
            
            if not doc.exists:
                logger.error(f"Visita no trobada amb ID: {visit_id}")
                return False
            
            # Actualitza el document amb les dades rebudes
            logger.log(23, f"Firestore UPDATE: collection={self.COLLECTION_NAME} document={visit_id}")
            doc_ref.update({
                'visitors': data.get('visitors', []),
                'total_visitors': data.get('total_visitors', 0)
            })
            
            # Invalida cache
            refuge_id = data.get('refuge_id')
            self._invalidate_visit_cache(visit_id, refuge_id)
            
            logger.info(f"Visitant afegit a la visita {visit_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error afegint visitant a la visita {visit_id}: {str(e)}")
            return False
    
    def update_visitor_in_visit(self, visit_id: str, data: Dict[str, Any]) -> bool:
        """
        Actualitza una visita amb les dades ja transformades
        
        Args:
            visit_id: ID de la visita
            data: Diccionari amb les dades de la visita actualitzada (ja transformat amb mapper.model_to_firebase)
            
        Returns:
            bool: True si l'operació ha tingut èxit, False altrament
        """
        try:
            db = self.firestore_service.get_db()
            doc_ref = db.collection(self.COLLECTION_NAME).document(visit_id)
            
            logger.log(23, f"Firestore READ: collection={self.COLLECTION_NAME} document={visit_id}")
            doc = doc_ref.get()
            
            if not doc.exists:
                logger.error(f"Visita no trobada amb ID: {visit_id}")
                return False
            
            # Actualitza el document amb les dades rebudes
            logger.log(23, f"Firestore UPDATE: collection={self.COLLECTION_NAME} document={visit_id}")
            doc_ref.update({
                'visitors': data.get('visitors', []),
                'total_visitors': data.get('total_visitors', 0)
            })
            
            # Invalida cache
            refuge_id = data.get('refuge_id')
            self._invalidate_visit_cache(visit_id, refuge_id)
            
            logger.info(f"Visita actualitzada: {visit_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error actualitzant visita {visit_id}: {str(e)}")
            return False
    
    def remove_visitor_from_visit(self, visit_id: str, uid: str) -> bool:
        """
        Elimina un visitant d'una visita i actualitza el total
        
        Args:
            visit_id: ID de la visita
            uid: UID de l'usuari
            
        Returns:
            bool: True si l'operació ha tingut èxit, False altrament
        """
        try:
            db = self.firestore_service.get_db()
            doc_ref = db.collection(self.COLLECTION_NAME).document(visit_id)
            
            logger.log(23, f"Firestore READ: collection={self.COLLECTION_NAME} document={visit_id}")
            doc = doc_ref.get()
            
            if not doc.exists:
                logger.error(f"Visita no trobada amb ID: {visit_id}")
                return False
            
            visit_data = doc.to_dict()
            visitors = visit_data.get('visitors', [])
            
            # Busca i elimina l'usuari de la llista
            user_found = False
            removed_num_visitors = 0
            new_visitors = []
            for visitor in visitors:
                if visitor.get('uid') == uid:
                    user_found = True
                    removed_num_visitors = visitor.get('num_visitors', 0)
                else:
                    new_visitors.append(visitor)
            
            if not user_found:
                logger.error(f"L'usuari {uid} no està registrat a la visita {visit_id}")
                return False
            
            # Actualitza el total
            total_visitors = visit_data.get('total_visitors', 0) - removed_num_visitors
            
            logger.log(23, f"Firestore UPDATE: collection={self.COLLECTION_NAME} document={visit_id}")
            doc_ref.update({
                'visitors': new_visitors,
                'total_visitors': total_visitors
            })
            
            # Invalida cache
            self._invalidate_visit_cache(visit_id, visit_data.get('refuge_id'))
            
            logger.info(f"Visitant eliminat de la visita {visit_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error eliminant visitant de la visita {visit_id}: {str(e)}")
            return False
    
    def get_visits_by_date(self, target_date: str) -> List[tuple[str, RefugeVisit]]:
        """
        Obté totes les visites per una data específica
        
        Args:
            target_date: Data de la visita (format YYYY-MM-DD)
            
        Returns:
            List[tuple[str, RefugeVisit]]: Llista de tuples (visit_id, RefugeVisit)
        """
        try:
            db = self.firestore_service.get_db()
            logger.log(23, f"Firestore QUERY: collection={self.COLLECTION_NAME} filter=date=={target_date}")
            query = db.collection(self.COLLECTION_NAME).where(
                filter=firestore.FieldFilter('date', '==', target_date)
            )
            
            docs = query.get()
            visits = []
            
            for doc in docs:
                visit_data = doc.to_dict()
                visit = self.mapper.firebase_to_model(visit_data)
                visits.append((doc.id, visit))
            
            logger.info(f"Obtingudes {len(visits)} visites per a la data {target_date}")
            return visits
            
        except Exception as e:
            logger.error(f"Error obtenint visites per la data {target_date}: {str(e)}")
            return []
    
    def delete_visit(self, visit_id: str) -> bool:
        """
        Elimina una visita
        
        Args:
            visit_id: ID de la visita
            
        Returns:
            bool: True si l'operació ha tingut èxit, False altrament
        """
        try:
            db = self.firestore_service.get_db()
            
            # Obté la visita abans d'eliminar per invalidar cache
            doc_ref = db.collection(self.COLLECTION_NAME).document(visit_id)
            logger.log(23, f"Firestore READ: collection={self.COLLECTION_NAME} document={visit_id}")
            doc = doc_ref.get()
            
            if not doc.exists:
                logger.error(f"Visita no trobada amb ID: {visit_id}")
                return False
            
            visit_data = doc.to_dict()
            refuge_id = visit_data.get('refuge_id')
            
            logger.log(23, f"Firestore DELETE: collection={self.COLLECTION_NAME} document={visit_id}")
            doc_ref.delete()
            
            # Invalida cache
            self._invalidate_visit_cache(visit_id, refuge_id)
            
            logger.info(f"Visita eliminada amb ID: {visit_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error eliminant visita {visit_id}: {str(e)}")
            return False
    
    def _invalidate_visit_cache(self, visit_id: str, refuge_id: Optional[str] = None):
        """
        Invalida la cache d'una visita
        
        Args:
            visit_id: ID de la visita
            refuge_id: ID del refugi (opcional, per invalidar cache de llista)
        """
        # Invalida cache del detall
        cache_key = cache_service.generate_key('refuge_visit_detail', visit_id=visit_id)
        cache_service.delete(cache_key)
        
        # Invalida cache de llista si tenim el refuge_id
        if refuge_id:
            self._invalidate_list_cache(refuge_id)
    
    def _invalidate_list_cache(self, refuge_id: str):
        """
        Invalida la cache de llista de visites d'un refugi
        
        Args:
            refuge_id: ID del refugi
        """
        # Invalida totes les claus de llista que continguin aquest refuge_id
        cache_service.delete_pattern(f'refuge_visits_list:refuge_id={refuge_id}:*')
    
    def remove_user_from_all_visits(self, uid: str, user_visits: List[tuple[str, RefugeVisit]]) -> tuple[bool, Optional[str]]:
        """
        Elimina un usuari de visitors i decrementa total_visitors de totes les refuge_visits
        
        Args:
            uid: UID de l'usuari
            user_visits: Llista de tuples (visit_id, RefugeVisit) de l'usuari
            
        Returns:
            Tuple (èxit: bool, missatge d'error: Optional[str])
        """
        try:
            if not user_visits:
                logger.info(f"Usuari {uid} no té visites registrades")
                return True, None
            
            db = self.firestore_service.get_db()
            updated_count = 0
            
            for visit_id, visit in user_visits:
                try:
                    doc_ref = db.collection(self.COLLECTION_NAME).document(visit_id)
                    logger.log(23, f"Firestore READ: collection={self.COLLECTION_NAME} document={visit_id}")
                    doc = doc_ref.get()
                    
                    if doc.exists:
                        visit_data = doc.to_dict()
                        visitors = visit_data.get('visitors', [])
                        
                        # Buscar i eliminar l'usuari de la llista de visitors
                        new_visitors = []
                        found = False
                        for visitor in visitors:
                            if isinstance(visitor, dict) and visitor.get('uid') == uid:
                                found = True
                                continue
                            new_visitors.append(visitor)
                        
                        if found:
                            # Actualitzar visitors i decrementar total_visitors
                            new_total = visit_data.get('total_visitors', 0) - 1
                            if new_total < 0:
                                new_total = 0
                            
                            logger.log(23, f"Firestore UPDATE: collection={self.COLLECTION_NAME} document={visit_id} (remove visitor)")
                            doc_ref.update({
                                'visitors': new_visitors,
                                'total_visitors': new_total
                            })
                            updated_count += 1
                            
                            # Invalida cache
                            refuge_id = visit_data.get('refuge_id')
                            self._invalidate_visit_cache(visit_id, refuge_id)
                    else:
                        logger.warning(f"Visita {visit_id} no trobada al eliminar usuari {uid}")
                except Exception as e:
                    logger.error(f"Error eliminant usuari {uid} de la visita {visit_id}: {str(e)}")
                    # Continua amb les altres visites
            
            logger.info(f"Usuari {uid} eliminat de {updated_count} visites")
            return True, None
            
        except Exception as e:
            logger.error(f"Error eliminant usuari {uid} de visites: {str(e)}")
            return False, str(e)
