"""
DAO per a la gestió de dubtes i respostes amb Firestore
"""
import logging
from typing import List, Optional, Dict, Any, Tuple
from ..services.firestore_service import FirestoreService
from ..services.cache_service import cache_service
from ..mappers.doubt_mapper import DoubtMapper, AnswerMapper
from ..models.doubt import Doubt, Answer
from google.cloud.firestore import Increment

logger = logging.getLogger(__name__)


class DoubtDAO:
    """Data Access Object per a dubtes i respostes"""
    
    COLLECTION_NAME = 'doubts'
    ANSWERS_SUBCOLLECTION = 'answers'
    
    def __init__(self):
        """Inicialitza el DAO amb la connexió a Firestore"""
        self.firestore_service = FirestoreService()
        self.doubt_mapper = DoubtMapper()
        self.answer_mapper = AnswerMapper()
    
    def create_doubt(self, doubt_data: Dict[str, Any]) -> Optional[Doubt]:
        """
        Crea un nou dubte a Firestore
        
        Args:
            doubt_data: Diccionari amb les dades del dubte
            
        Returns:
            Doubt: Instància del model Doubt creada o None si hi ha error
        """
        try:
            db = self.firestore_service.get_db()
            
            # Crea el dubte
            doc_ref = db.collection(self.COLLECTION_NAME).document()
            doubt_data['id'] = doc_ref.id
            logger.log(23, f"Firestore WRITE: collection={self.COLLECTION_NAME} document={doc_ref.id}")
            doc_ref.set(doubt_data)
            
            logger.info(f"Dubte creat amb ID: {doc_ref.id}")
            
            # Invalida cache de llistes de dubtes d'aquest refugi
            cache_service.delete_pattern(f"doubt_list:refuge_id:{doubt_data['refuge_id']}")
            
            # Retornar la instància del model
            return self.doubt_mapper.firestore_to_model(doubt_data)
            
        except Exception as e:
            logger.error(f"Error creant dubte: {str(e)}")
            return None
    
    def get_doubt_by_id(self, doubt_id: str) -> Optional[Doubt]:
        """
        Obté un dubte per ID sense les seves respostes
        
        Args:
            doubt_id: ID del dubte
            
        Returns:
            Doubt: Instància del model Doubt o None si no existeix
        """
        # Genera clau de cache
        cache_key = cache_service.generate_key('doubt_detail', doubt_id=doubt_id)
        
        # Intenta obtenir de cache
        cached_data = cache_service.get(cache_key)
        if cached_data is not None:
            return self.doubt_mapper.firestore_to_model(cached_data)
        
        try:
            db = self.firestore_service.get_db()
            doc_ref = db.collection(self.COLLECTION_NAME).document(doubt_id)
            logger.log(23, f"Firestore READ: collection={self.COLLECTION_NAME} document={doubt_id}")
            doc = doc_ref.get()
            
            if doc.exists:
                doubt_data = doc.to_dict()
                doubt_data['id'] = doc.id
                
                # Guarda a cache
                timeout = cache_service.get_timeout('doubt_detail')
                cache_service.set(cache_key, doubt_data, timeout)
                
                logger.log(23, f"Dubte trobat amb ID: {doubt_id}")
                return self.doubt_mapper.firestore_to_model(doubt_data)
            else:
                logger.warning(f"Dubte no trobat amb ID: {doubt_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error obtenint dubte amb ID {doubt_id}: {str(e)}")
            return None
    
    def get_doubts_by_refuge_id(self, refuge_id: str) -> List[Doubt]:
        """
        Obté tots els dubtes d'un refugi amb totes les seves respostes amb ID caching
        
        Args:
            refuge_id: ID del refugi
            
        Returns:
            List[Doubt]: Llista de dubtes amb les seves respostes
        """
        # Genera clau de cache
        cache_key = cache_service.generate_key('doubt_list', refuge_id=refuge_id)
        
        try:
            # Funció per obtenir TOTES les dades completes (amb respostes) d'una des de Firestore
            def fetch_all():
                db = self.firestore_service.get_db()
                
                # Obtenir tots els dubtes del refugi ordenats per created_at descendent
                doubts_ref = db.collection(self.COLLECTION_NAME).where('refuge_id', '==', refuge_id).order_by('created_at', direction='DESCENDING')
                logger.log(23, f"Firestore READ: collection={self.COLLECTION_NAME} where refuge_id=={refuge_id}")
                doubts_docs = doubts_ref.stream()
                
                doubts_data = []
                for doubt_doc in doubts_docs:
                    doubt_data = doubt_doc.to_dict()
                    doubt_data['id'] = doubt_doc.id
                    
                    # Obtenir totes les respostes del dubte ordenades per created_at ascendent
                    answers = self._get_answers_by_doubt_id(doubt_doc.id)
                    
                    # Preparar dades amb respostes
                    doubt_data['answers'] = [answer.to_dict() for answer in answers]
                    doubts_data.append(doubt_data)
                
                return doubts_data
            
            # Funció per obtenir un dubte individual (amb respostes) per ID
            def fetch_single(doubt_id: str):
                db = self.firestore_service.get_db()
                doc_ref = db.collection(self.COLLECTION_NAME).document(doubt_id)
                logger.log(23, f"Firestore READ: collection={self.COLLECTION_NAME} document={doubt_id}")
                doc = doc_ref.get()
                
                if not doc.exists:
                    return None
                
                doubt_data = doc.to_dict()
                doubt_data['id'] = doc.id
                
                # Obtenir totes les respostes del dubte
                answers = self._get_answers_by_doubt_id(doubt_id)
                doubt_data['answers'] = [answer.to_dict() for answer in answers]
                return doubt_data
            
            # Funció per extreure l'ID d'un dubte
            def get_id(doubt_data: Dict[str, Any]) -> str:
                return doubt_data['id']
            
            # Usar estratègia ID caching del cache_service
            doubts_data = cache_service.get_or_fetch_list(
                list_cache_key=cache_key,
                detail_key_prefix='doubt_detail',
                fetch_all_fn=fetch_all,
                fetch_single_fn=fetch_single,
                get_id_fn=get_id,
                list_timeout=cache_service.get_timeout('doubt_list'),
                detail_timeout=cache_service.get_timeout('doubt_detail'),
                id_param_name='doubt_id'
            )
            
            # Convertir dades de cache a models
            doubts = []
            for doubt_data in doubts_data:
                answers_data = doubt_data.pop('answers', [])
                answers = self.answer_mapper.firestore_list_to_models(answers_data)
                doubt = self.doubt_mapper.firestore_to_model(doubt_data, answers)
                doubts.append(doubt)
            
            logger.info(f"Obtinguts {len(doubts)} dubtes per al refugi {refuge_id}")
            return doubts
            
        except Exception as e:
            logger.error(f"Error obtenint dubtes del refugi {refuge_id}: {str(e)}")
            return []
    
    def _get_answers_by_doubt_id(self, doubt_id: str) -> List[Answer]:
        """
        Obté totes les respostes d'un dubte ordenades per created_at ascendent
        
        Args:
            doubt_id: ID del dubte
            
        Returns:
            List[Answer]: Llista de respostes
        """
        try:
            db = self.firestore_service.get_db()
            
            # Obtenir totes les respostes del dubte ordenades per created_at ascendent
            answers_ref = db.collection(self.COLLECTION_NAME).document(doubt_id).collection(self.ANSWERS_SUBCOLLECTION).order_by('created_at', direction='ASCENDING')
            logger.log(23, f"Firestore READ: collection={self.COLLECTION_NAME}/{doubt_id}/{self.ANSWERS_SUBCOLLECTION}")
            answers_docs = answers_ref.stream()
            
            answers = []
            for answer_doc in answers_docs:
                answer_data = answer_doc.to_dict()
                answer_data['id'] = answer_doc.id
                answer = self.answer_mapper.firestore_to_model(answer_data)
                answers.append(answer)
            
            logger.log(23, f"Obtingudes {len(answers)} respostes per al dubte {doubt_id}")
            return answers
            
        except Exception as e:
            logger.error(f"Error obtenint respostes del dubte {doubt_id}: {str(e)}")
            return []
    
    def create_answer(self, doubt_id: str, answer_data: Dict[str, Any]) -> Optional[Answer]:
        """
        Crea una nova resposta per a un dubte
        
        Args:
            doubt_id: ID del dubte
            answer_data: Diccionari amb les dades de la resposta
            
        Returns:
            Answer: Instància del model Answer creada o None si hi ha error
        """
        try:
            db = self.firestore_service.get_db()
            
            # Crea la resposta a la subcollection del dubte
            answers_ref = db.collection(self.COLLECTION_NAME).document(doubt_id).collection(self.ANSWERS_SUBCOLLECTION)
            doc_ref = answers_ref.document()
            answer_data['id'] = doc_ref.id
            logger.log(23, f"Firestore WRITE: collection={self.COLLECTION_NAME}/{doubt_id}/{self.ANSWERS_SUBCOLLECTION} document={doc_ref.id}")
            doc_ref.set(answer_data)
            
            # Incrementar el comptador d'answers_count del dubte
            doubt_ref = db.collection(self.COLLECTION_NAME).document(doubt_id)
            logger.log(23, f"Firestore UPDATE: collection={self.COLLECTION_NAME} document={doubt_id} increment answers_count")
            doubt_ref.update({'answers_count': Increment(1)})
            
            logger.info(f"Resposta creada amb ID: {doc_ref.id} per al dubte {doubt_id}")
            
            # Invalida cache (només detail, la list no canvia en updates)
            self._invalidate_doubt_detail_cache(doubt_id)
            
            # Retornar la instància del model
            return self.answer_mapper.firestore_to_model(answer_data)
            
        except Exception as e:
            logger.error(f"Error creant resposta per al dubte {doubt_id}: {str(e)}")
            return None
    
    def get_answer_by_id(self, doubt_id: str, answer_id: str) -> Optional[Answer]:
        """
        Obté una resposta per ID
        
        Args:
            doubt_id: ID del dubte
            answer_id: ID de la resposta
            
        Returns:
            Answer: Instància del model Answer o None si no existeix
        """
        try:
            db = self.firestore_service.get_db()
            doc_ref = db.collection(self.COLLECTION_NAME).document(doubt_id).collection(self.ANSWERS_SUBCOLLECTION).document(answer_id)
            logger.log(23, f"Firestore READ: collection={self.COLLECTION_NAME}/{doubt_id}/{self.ANSWERS_SUBCOLLECTION} document={answer_id}")
            doc = doc_ref.get()
            
            if doc.exists:
                answer_data = doc.to_dict()
                answer_data['id'] = doc.id
                logger.log(23, f"Resposta trobada amb ID: {answer_id}")
                return self.answer_mapper.firestore_to_model(answer_data)
            else:
                logger.warning(f"Resposta no trobada amb ID: {answer_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error obtenint resposta amb ID {answer_id}: {str(e)}")
            return None
    
    def delete_answer(self, doubt_id: str, answer_id: str) -> bool:
        """
        Elimina una resposta i decrementa el comptador d'answers_count del dubte
        
        Args:
            doubt_id: ID del dubte
            answer_id: ID de la resposta
            
        Returns:
            bool: True si s'ha eliminat correctament, False en cas contrari
        """
        try:
            db = self.firestore_service.get_db()
            
            # Eliminar la resposta
            answer_ref = db.collection(self.COLLECTION_NAME).document(doubt_id).collection(self.ANSWERS_SUBCOLLECTION).document(answer_id)
            logger.log(23, f"Firestore DELETE: collection={self.COLLECTION_NAME}/{doubt_id}/{self.ANSWERS_SUBCOLLECTION} document={answer_id}")
            answer_ref.delete()
            
            # Decrementar el comptador d'answers_count del dubte
            doubt_ref = db.collection(self.COLLECTION_NAME).document(doubt_id)
            logger.log(23, f"Firestore UPDATE: collection={self.COLLECTION_NAME} document={doubt_id} decrement answers_count")
            doubt_ref.update({'answers_count': Increment(-1)})
            
            logger.info(f"Resposta eliminada amb ID: {answer_id}")
            
            # Invalida cache (només detail, la list no canvia en updates)
            self._invalidate_doubt_detail_cache(doubt_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Error eliminant resposta amb ID {answer_id}: {str(e)}")
            return False
    
    def delete_doubt(self, doubt_id: str) -> bool:
        """
        Elimina un dubte i totes les seves respostes
        
        Args:
            doubt_id: ID del dubte
            
        Returns:
            bool: True si s'ha eliminat correctament, False en cas contrari
        """
        try:
            db = self.firestore_service.get_db()
            
            # Primer, eliminar totes les respostes del dubte
            answers_ref = db.collection(self.COLLECTION_NAME).document(doubt_id).collection(self.ANSWERS_SUBCOLLECTION)
            logger.log(23, f"Firestore READ: collection={self.COLLECTION_NAME}/{doubt_id}/{self.ANSWERS_SUBCOLLECTION}")
            answers_docs = answers_ref.stream()
            
            for answer_doc in answers_docs:
                logger.log(23, f"Firestore DELETE: collection={self.COLLECTION_NAME}/{doubt_id}/{self.ANSWERS_SUBCOLLECTION} document={answer_doc.id}")
                answer_doc.reference.delete()
            
            # Després, eliminar el dubte
            doubt_ref = db.collection(self.COLLECTION_NAME).document(doubt_id)
            logger.log(23, f"Firestore DELETE: collection={self.COLLECTION_NAME} document={doubt_id}")
            doubt_ref.delete()
            
            logger.info(f"Dubte eliminat amb ID: {doubt_id}")
            
            # Invalida cache
            self._invalidate_doubt_cache(doubt_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Error eliminant dubte amb ID {doubt_id}: {str(e)}")
            return False
    
    def _invalidate_doubt_detail_cache(self, doubt_id: str):
        """
        Invalida només la cache de detall d'un dubte específic
        
        Args:
            doubt_id: ID del dubte
        """
        cache_service.delete_pattern(f"doubt_detail:doubt_id:{doubt_id}")
    
    def _invalidate_doubt_cache(self, doubt_id: str):
        """
        Invalida la cache relacionada amb un dubte (detail + list)
        
        Args:
            doubt_id: ID del dubte
        """
        try:
            # Invalida cache del dubte específic
            self._invalidate_doubt_detail_cache(doubt_id)
            
            # Obtenir el dubte per saber el refuge_id
            doubt = self.get_doubt_by_id(doubt_id)
            if doubt:
                # Invalida cache de la llista de dubtes del refugi
                cache_service.delete_pattern(f"doubt_list:refuge_id:{doubt.refuge_id}")
            
        except Exception as e:
            logger.error(f"Error invalidant cache per al dubte {doubt_id}: {str(e)}")
    
    def delete_doubts_by_creator(self, creator_uid: str) -> Tuple[bool, Optional[str]]:
        """
        Elimina tots els dubtes creats per un usuari
        
        Args:
            creator_uid: UID del creador
            
        Returns:
            Tuple (èxit: bool, missatge d'error: Optional[str])
        """
        try:
            db = self.firestore_service.get_db()
            
            # Obtenir tots els dubtes del creador
            logger.log(23, f"Firestore QUERY: collection={self.COLLECTION_NAME} where creator_uid=={creator_uid}")
            doubts_query = db.collection(self.COLLECTION_NAME).where('creator_uid', '==', creator_uid).stream()
            
            deleted_count = 0
            refuge_ids = set()
            
            for doubt_doc in doubts_query:
                doubt_data = doubt_doc.to_dict()
                refuge_id = doubt_data.get('refuge_id')
                if refuge_id:
                    refuge_ids.add(refuge_id)
                
                # Eliminar totes les respostes del dubte
                answers_ref = doubt_doc.reference.collection(self.ANSWERS_SUBCOLLECTION)
                logger.log(23, f"Firestore READ: collection={self.COLLECTION_NAME}/{doubt_doc.id}/{self.ANSWERS_SUBCOLLECTION}")
                answers_docs = answers_ref.stream()
                
                for answer_doc in answers_docs:
                    logger.log(23, f"Firestore DELETE: collection={self.COLLECTION_NAME}/{doubt_doc.id}/{self.ANSWERS_SUBCOLLECTION} document={answer_doc.id}")
                    answer_doc.reference.delete()
                
                # Eliminar el dubte
                logger.log(23, f"Firestore DELETE: collection={self.COLLECTION_NAME} document={doubt_doc.id}")
                doubt_doc.reference.delete()
                deleted_count += 1
                
                # Invalida cache de detall
                cache_service.delete_pattern(f"doubt_detail:doubt_id:{doubt_doc.id}")
            
            # Invalida cache de llistes per cada refugi afectat
            for refuge_id in refuge_ids:
                cache_service.delete_pattern(f"doubt_list:refuge_id:{refuge_id}")
            
            logger.info(f"{deleted_count} dubtes eliminats del creador {creator_uid}")
            return True, None
            
        except Exception as e:
            logger.error(f"Error eliminant dubtes del creador {creator_uid}: {str(e)}")
            return False, str(e)
    
    def delete_answers_by_creator(self, creator_uid: str) -> Tuple[bool, Optional[str]]:
        """
        Elimina totes les respostes creades per un usuari utilitzant collection_group
        
        Args:
            creator_uid: UID del creador
            
        Returns:
            Tuple (èxit: bool, missatge d'error: Optional[str])
        """
        try:
            db = self.firestore_service.get_db()
            
            # Utilitzar collection_group per obtenir totes les respostes de totes les subcollections
            logger.log(23, f"Firestore COLLECTION_GROUP_QUERY: {self.ANSWERS_SUBCOLLECTION} where creator_uid=={creator_uid}")
            answers_query = db.collection_group(self.ANSWERS_SUBCOLLECTION).where('creator_uid', '==', creator_uid).stream()
            
            deleted_count = 0
            doubt_ids = set()
            
            for answer_doc in answers_query:
                # Obtenir el doubt_id del path del document
                # Path format: doubts/{doubt_id}/answers/{answer_id}
                doubt_id = answer_doc.reference.parent.parent.id
                doubt_ids.add(doubt_id)
                
                # Eliminar la resposta
                logger.log(23, f"Firestore DELETE: answers document={answer_doc.id} from doubt={doubt_id}")
                answer_doc.reference.delete()
                deleted_count += 1
            
            # Actualitzar el comptador answers_count per cada dubte afectat
            for doubt_id in doubt_ids:
                doubt_ref = db.collection(self.COLLECTION_NAME).document(doubt_id)
                logger.log(23, f"Firestore READ: collection={self.COLLECTION_NAME} document={doubt_id}")
                doubt_doc = doubt_ref.get()
                
                if doubt_doc.exists:
                    # Comptar respostes restants
                    answers_ref = doubt_ref.collection(self.ANSWERS_SUBCOLLECTION)
                    logger.log(23, f"Firestore READ: collection={self.COLLECTION_NAME}/{doubt_id}/{self.ANSWERS_SUBCOLLECTION}")
                    remaining_answers = len(list(answers_ref.stream()))
                    
                    # Actualitzar comptador
                    logger.log(23, f"Firestore UPDATE: collection={self.COLLECTION_NAME} document={doubt_id} (answers_count)")
                    doubt_ref.update({'answers_count': remaining_answers})
                    
                    # Invalida cache (només detail, la list no canvia en updates)
                    self._invalidate_doubt_detail_cache(doubt_id)
            
            logger.info(f"{deleted_count} respostes eliminades del creador {creator_uid}")
            return True, None
            
        except Exception as e:
            logger.error(f"Error eliminant respostes del creador {creator_uid}: {str(e)}")
            return False, str(e)
