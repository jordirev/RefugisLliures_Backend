"""
DAO per a la gestió d'experiències amb Firestore
"""
import logging
from typing import List, Optional, Dict, Any, Tuple
from ..services.firestore_service import FirestoreService
from ..services.cache_service import cache_service
from ..mappers.experience_mapper import ExperienceMapper
from ..models.experience import Experience
from google.cloud.firestore import ArrayUnion

logger = logging.getLogger(__name__)


class ExperienceDAO:
    """Data Access Object per a experiències"""
    
    COLLECTION_NAME = 'experiences'
    
    def __init__(self):
        """Inicialitza el DAO amb la connexió a Firestore"""
        self.firestore_service = FirestoreService()
        self.mapper = ExperienceMapper()
    
    def create_experience(self, experience_data: Dict[str, Any]) -> Optional[Experience]:
        """
        Crea una nova experiència a Firestore
        
        Args:
            experience_data: Diccionari amb les dades de l'experiència
            
        Returns:
            Experience: Instància del model Experience creada o None si hi ha error
        """
        try:
            db = self.firestore_service.get_db()
            
            # Crea l'experiència
            doc_ref = db.collection(self.COLLECTION_NAME).document()
            experience_data['id'] = doc_ref.id
            logger.log(23, f"Firestore WRITE: collection={self.COLLECTION_NAME} document={doc_ref.id}")
            doc_ref.set(experience_data)
            
            logger.info(f"Experiència creada amb ID: {doc_ref.id}")
            
            # Invalida cache de llistes d'experiències d'aquest refugi
            cache_service.delete_pattern(f"experience_list:refuge_id:{experience_data['refuge_id']}:*")
            
            # Retornar la instància del model
            return self.mapper.firestore_to_model(experience_data)
            
        except Exception as e:
            logger.error(f"Error creant experiència: {str(e)}")
            return None
    
    def get_experience_by_id(self, experience_id: str) -> Optional[Experience]:
        """
        Obté una experiència per ID
        
        Args:
            experience_id: ID de l'experiència
            
        Returns:
            Experience: Instància del model Experience o None si no existeix
        """
        # Genera clau de cache
        cache_key = cache_service.generate_key('experience_detail', experience_id=experience_id)
        
        # Intenta obtenir de cache
        cached_data = cache_service.get(cache_key)
        if cached_data is not None:
            return self.mapper.firestore_to_model(cached_data)
        
        try:
            db = self.firestore_service.get_db()
            doc_ref = db.collection(self.COLLECTION_NAME).document(experience_id)
            logger.log(23, f"Firestore READ: collection={self.COLLECTION_NAME} document={experience_id}")
            doc = doc_ref.get()
            
            if doc.exists:
                experience_data = doc.to_dict()
                experience_data['id'] = doc.id
                
                # Guarda a cache
                timeout = cache_service.get_timeout('experience_detail')
                cache_service.set(cache_key, experience_data, timeout)
                
                logger.log(23, f"Experiència trobada amb ID: {experience_id}")
                return self.mapper.firestore_to_model(experience_data)
            else:
                logger.warning(f"Experiència no trobada amb ID: {experience_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error obtenint experiència amb ID {experience_id}: {str(e)}")
            return None
    
    def get_experiences_by_refuge_id(self, refuge_id: str) -> List[Experience]:
        """
        Obté totes les experiències d'un refugi ordenades per modified_at descendent amb ID caching
        
        Args:
            refuge_id: ID del refugi
            
        Returns:
            List d'instàncies del model Experience
        """
        # Genera clau de cache
        cache_key = cache_service.generate_key('experience_list', refuge_id=refuge_id)
        
        try:
            # Funció per obtenir TOTES les dades completes d'una des de Firestore
            def fetch_all():
                db = self.firestore_service.get_db()
                logger.log(23, f"Firestore READ: collection={self.COLLECTION_NAME} where refuge_id={refuge_id} order_by modified_at desc")
                query = db.collection(self.COLLECTION_NAME)\
                            .where('refuge_id', '==', refuge_id)\
                            .order_by('modified_at', direction='DESCENDING')
                docs = query.stream()
                
                experiences_data = []
                for doc in docs:
                    experience_data = doc.to_dict()
                    experience_data['id'] = doc.id
                    experiences_data.append(experience_data)
                return experiences_data
            
            # Funció per obtenir una experiència individual per ID
            def fetch_single(experience_id: str):
                db = self.firestore_service.get_db()
                doc_ref = db.collection(self.COLLECTION_NAME).document(experience_id)
                logger.log(23, f"Firestore READ: collection={self.COLLECTION_NAME} document={experience_id}")
                doc = doc_ref.get()
                if doc.exists:
                    experience_data = doc.to_dict()
                    experience_data['id'] = doc.id
                    return experience_data
                return None
            
            # Funció per extreure l'ID d'una experiència
            def get_id(experience_data: Dict[str, Any]) -> str:
                return experience_data['id']
            
            # Usar estratègia ID caching del cache_service
            experiences_data = cache_service.get_or_fetch_list(
                list_cache_key=cache_key,
                detail_key_prefix='experience_detail',
                fetch_all_fn=fetch_all,
                fetch_single_fn=fetch_single,
                get_id_fn=get_id,
                list_timeout=cache_service.get_timeout('experience_list'),
                detail_timeout=cache_service.get_timeout('experience_detail')
            )
            
            logger.log(23, f"Trobades {len(experiences_data)} experiències per al refugi {refuge_id}")
            return self.mapper.firestore_list_to_models(experiences_data)
            
        except Exception as e:
            logger.error(f"Error obtenint experiències del refugi {refuge_id}: {str(e)}")
            return []
    
    def update_experience(self, experience_id: str, update_data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Actualitza una experiència a Firestore
        
        Args:
            experience_id: ID de l'experiència
            update_data: Diccionari amb les dades a actualitzar
            
        Returns:
            Tuple (èxit: bool, missatge d'error: Optional[str])
        """
        try:
            db = self.firestore_service.get_db()
            doc_ref = db.collection(self.COLLECTION_NAME).document(experience_id)
            
            # Comprova que l'experiència existeix
            logger.log(23, f"Firestore READ: collection={self.COLLECTION_NAME} document={experience_id}")
            doc = doc_ref.get()
            if not doc.exists:
                return False, "Experience not found" 
            
            # Actualitza l'experiència
            logger.log(23, f"Firestore UPDATE: collection={self.COLLECTION_NAME} document={experience_id}")
            if 'media_keys' in update_data:
                # Actualitza media_keys amb ArrayUnion per evitar sobrescriure
                media_keys = update_data.pop('media_keys')
                doc_ref.update({
                    **update_data,
                    'media_keys': ArrayUnion(media_keys)
                })
            else:
                doc_ref.update(update_data)

            logger.info(f"Experiència {experience_id} actualitzada correctament")
            
            # Invalida cache (només detail, la list no canvia en updates)
            cache_service.delete(cache_service.generate_key('experience_detail', experience_id=experience_id))

            return True, None
            
        except Exception as e:
            logger.error(f"Error actualitzant experiència {experience_id}: {str(e)}")
            return False, str(e)
    
    def delete_experience(self, experience_id: str) -> Tuple[bool, Optional[str]]:
        """
        Elimina una experiència de Firestore
        
        Args:
            experience_id: ID de l'experiència
            
        Returns:
            Tuple (èxit: bool, missatge d'error: Optional[str])
        """
        try:
            db = self.firestore_service.get_db()
            doc_ref = db.collection(self.COLLECTION_NAME).document(experience_id)
            
            # Comprova que l'experiència existeix i obté les dades abans d'eliminar
            logger.log(23, f"Firestore READ: collection={self.COLLECTION_NAME} document={experience_id}")
            doc = doc_ref.get()
            if not doc.exists:
                return False, "Experience not found"
            
            experience_data = doc.to_dict()
            
            # Elimina l'experiència
            logger.log(23, f"Firestore DELETE: collection={self.COLLECTION_NAME} document={experience_id}")
            doc_ref.delete()
            
            logger.info(f"Experiència {experience_id} eliminada correctament")
            
            # Invalida cache
            cache_service.delete(cache_service.generate_key('experience_detail', experience_id=experience_id))
            if experience_data and 'refuge_id' in experience_data:
                cache_service.delete_pattern(f"experience_list:refuge_id:{experience_data['refuge_id']}:*")
            
            return True, None
            
        except Exception as e:
            logger.error(f"Error eliminant experiència {experience_id}: {str(e)}")
            return False, str(e)
    
    def add_media_keys_to_experience(self, experience_id: str, media_keys: List[str]) -> Tuple[bool, Optional[str]]:
        """
        Afegeix claus de media a la llista media_keys d'una experiència
        
        Args:
            experience_id: ID de l'experiència
            media_keys: Llista de claus de media a afegir
            
        Returns:
            Tuple (èxit: bool, missatge d'error: Optional[str])
        """
        try:
            db = self.firestore_service.get_db()
            doc_ref = db.collection(self.COLLECTION_NAME).document(experience_id)
            
            # Comprova que l'experiència existeix
            logger.log(23, f"Firestore READ: collection={self.COLLECTION_NAME} document={experience_id}")
            doc = doc_ref.get()
            if not doc.exists:
                return False, "Experience not found"
            
            # Afegeix la clau de media
            logger.log(23, f"Firestore UPDATE: collection={self.COLLECTION_NAME} document={experience_id} (add media_key)")
            doc_ref.update({
                'media_keys': ArrayUnion(media_keys)
            })
            
            logger.info(f"Media keys afegides a l'experiència {experience_id}")
            
            # Invalida cache (només detail, la list no canvia en updates)
            cache_service.delete(cache_service.generate_key('experience_detail', experience_id=experience_id))
            
            return True, None
            
        except Exception as e:
            logger.error(f"Error afegint media key a l'experiència {experience_id}: {str(e)}")
            return False, str(e)
    
    def remove_media_key(self, experience_id: str, media_key: str) -> Tuple[bool, Optional[str]]:
        """
        Elimina una clau de media de la llista media_keys d'una experiència
        
        Args:
            experience_id: ID de l'experiència
            media_key: Clau del media a eliminar
            
        Returns:
            Tuple (èxit: bool, missatge d'error: Optional[str])
        """
        try:
            db = self.firestore_service.get_db()
            doc_ref = db.collection(self.COLLECTION_NAME).document(experience_id)
            
            # Comprova que l'experiència existeix
            logger.log(23, f"Firestore READ: collection={self.COLLECTION_NAME} document={experience_id}")
            doc = doc_ref.get()
            if not doc.exists:
                return False, "Experience not found"
            
            # Elimina la clau de media
            from google.cloud.firestore import ArrayRemove
            logger.log(23, f"Firestore UPDATE: collection={self.COLLECTION_NAME} document={experience_id} (remove media_key)")
            doc_ref.update({
                'media_keys': ArrayRemove([media_key])
            })
            
            logger.info(f"Media key {media_key} eliminada de l'experiència {experience_id}")
            
            # Invalida cache (només detail, la list no canvia en updates)
            cache_service.delete(cache_service.generate_key('experience_detail', experience_id=experience_id))
            
            return True, None
            
        except Exception as e:
            logger.error(f"Error eliminant media key de l'experiència {experience_id}: {str(e)}")
            return False, str(e)
    
    def delete_experiences_by_creator(self, creator_uid: str) -> Tuple[bool, Optional[str]]:
        """
        Elimina totes les experiències creades per un usuari
        
        Args:
            creator_uid: UID del creador
            
        Returns:
            Tuple (èxit: bool, missatge d'error: Optional[str])
        """
        try:
            db = self.firestore_service.get_db()
            
            # Obtenir totes les experiències del creador
            logger.log(23, f"Firestore QUERY: collection={self.COLLECTION_NAME} where creator_uid=={creator_uid}")
            experiences_query = db.collection(self.COLLECTION_NAME).where('creator_uid', '==', creator_uid).stream()
            
            deleted_count = 0
            refuge_ids = set()
            
            for exp_doc in experiences_query:
                experience_data = exp_doc.to_dict()
                refuge_id = experience_data.get('refuge_id')
                if refuge_id:
                    refuge_ids.add(refuge_id)
                
                # Eliminar document
                logger.log(23, f"Firestore DELETE: collection={self.COLLECTION_NAME} document={exp_doc.id}")
                exp_doc.reference.delete()
                deleted_count += 1
                
                # Invalida cache de detall
                cache_service.delete(cache_service.generate_key('experience_detail', experience_id=exp_doc.id))
            
            # Invalida cache de llistes per cada refugi afectat
            for refuge_id in refuge_ids:
                cache_service.delete_pattern(f"experience_list:refuge_id:{refuge_id}:*")
            
            logger.info(f"{deleted_count} experiències eliminades del creador {creator_uid}")
            return True, None
            
        except Exception as e:
            logger.error(f"Error eliminant experiències del creador {creator_uid}: {str(e)}")
            return False, str(e)
