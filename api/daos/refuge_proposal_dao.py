"""
DAO per a la gestió de propostes de refugis amb Firestore
Implementa el patró Strategy per gestionar les diferents accions (create, update, delete)
"""
from datetime import datetime
import logging
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Tuple
from google.cloud import firestore
from ..services import firestore_service, cache_service
from ..services.condition_service import ConditionService
from ..models.refuge_proposal import RefugeProposal
from ..models.refugi_lliure import Refugi, Coordinates, InfoComplementaria
from ..mappers.refuge_proposal_mapper import RefugeProposalMapper
from ..mappers.refugi_lliure_mapper import RefugiLliureMapper
from ..utils.timezone_utils import get_madrid_now

logger = logging.getLogger(__name__)


# ==================== FUNCIONS AUXILIARS PER COORDS_REFUGIS ====================

def generate_simple_geohash(lat: float, lng: float, precision: int = 5) -> str:
    """Generate a simple geohash for geographical indexing"""
    lat_range = [-90.0, 90.0]
    lng_range = [-180.0, 180.0]
    
    geohash = ""
    bits = 0
    ch = 0
    even = True
    
    base32 = "0123456789bcdefghjkmnpqrstuvwxyz"
    
    while len(geohash) < precision:
        if even:  # longitude
            mid = (lng_range[0] + lng_range[1]) / 2
            if lng >= mid:
                ch |= (1 << (4 - bits))
                lng_range[0] = mid
            else:
                lng_range[1] = mid
        else:  # latitude
            mid = (lat_range[0] + lat_range[1]) / 2
            if lat >= mid:
                ch |= (1 << (4 - bits))
                lat_range[0] = mid
            else:
                lat_range[1] = mid
                
        even = not even
        bits += 1
        
        if bits == 5:
            geohash += base32[ch]
            bits = 0
            ch = 0
            
    return geohash


def add_refuge_to_coords_refugis(db, refuge_id: str, refuge_data: Dict[str, Any]) -> None:
    """Afegeix un nou refugi a la col·lecció coords_refugis"""
    try:
        coords_ref = db.collection('coords_refugis').document('all_refugis_coords')
        logger.log(23, f"Firestore READ: collection=coords_refugis document=all_refugis_coords (for CREATE)")
        coords_doc = coords_ref.get()
        
        # Preparar la nova entrada de coordenades
        coord_data = refuge_data.get('coord', {})
        new_coord_entry = {
            'id': refuge_id,
            'coord': {
                'lat': coord_data.get('lat'),
                'long': coord_data.get('long')
            },
            'geohash': generate_simple_geohash(coord_data.get('lat'), coord_data.get('long')),
            'name': refuge_data.get('name', '')
        }
        
        # Afegir surname si existeix
        if 'surname' in refuge_data and refuge_data['surname']:
            new_coord_entry['surname'] = refuge_data['surname']
        
        if coords_doc.exists:
            # Actualitzar el document existent
            coords_data = coords_doc.to_dict()
            refugis_coordinates = coords_data.get('refugis_coordinates', [])
            refugis_coordinates.append(new_coord_entry)
            
            logger.log(23, f"Firestore UPDATE: collection=coords_refugis document=all_refugis_coords (ADD refuge {refuge_id})")
            coords_ref.update({
                'refugis_coordinates': refugis_coordinates,
                'total_refugis': len(refugis_coordinates),
                'last_updated': firestore.SERVER_TIMESTAMP
            })
        else:
            # Crear el document si no existeix
            logger.log(23, f"Firestore WRITE: collection=coords_refugis document=all_refugis_coords (CREATE with refuge {refuge_id})")
            coords_ref.set({
                'refugis_coordinates': [new_coord_entry],
                'total_refugis': 1,
                'created_at': firestore.SERVER_TIMESTAMP,
                'last_updated': firestore.SERVER_TIMESTAMP
            })
        
        logger.info(f"Coordenades del refugi {refuge_id} afegides a coords_refugis")
    except Exception as e:
        logger.error(f"Error actualitzant coords_refugis per CREATE: {str(e)}")
        raise


def update_refuge_from_coords_refugis(db, refuge_id: str, update_data: Dict[str, Any]) -> None:
    """Actualitza les coordenades d'un refugi a coords_refugis si 'coord' o 'name' estan al payload"""
    try:
        # Només actualitzar si hi ha 'coord' o 'name' al payload
        if 'coord' not in update_data and 'name' not in update_data:
            logger.info(f"No cal actualitzar coords_refugis per refugi {refuge_id} (no hi ha 'coord' ni 'name' al payload)")
            return
        
        coords_ref = db.collection('coords_refugis').document('all_refugis_coords')
        logger.log(23, f"Firestore READ: collection=coords_refugis document=all_refugis_coords (for UPDATE)")
        coords_doc = coords_ref.get()
        
        if not coords_doc.exists:
            logger.warning(f"Document coords_refugis no existeix, no es pot actualitzar refugi {refuge_id}")
            return
        
        coords_data = coords_doc.to_dict()
        refugis_coordinates = coords_data.get('refugis_coordinates', [])
        
        # Trobar i actualitzar el refugi
        updated = False
        for i, coord_entry in enumerate(refugis_coordinates):
            if coord_entry.get('id') == refuge_id:
                # Actualitzar coord si està present
                if 'coord' in update_data:
                    coord_data = update_data['coord']
                    refugis_coordinates[i]['coord'] = {
                        'lat': coord_data.get('lat'),
                        'long': coord_data.get('long')
                    }
                    refugis_coordinates[i]['geohash'] = generate_simple_geohash(
                        coord_data.get('lat'), 
                        coord_data.get('long')
                    )
                
                # Actualitzar name si està present
                if 'name' in update_data:
                    refugis_coordinates[i]['name'] = update_data['name']
                
                # Actualitzar surname si està present
                if 'surname' in update_data:
                    if update_data['surname']:
                        refugis_coordinates[i]['surname'] = update_data['surname']
                    elif 'surname' in refugis_coordinates[i]:
                        # Eliminar surname si és null o buit
                        del refugis_coordinates[i]['surname']
                
                updated = True
                break
        
        if updated:
            logger.log(23, f"Firestore UPDATE: collection=coords_refugis document=all_refugis_coords (UPDATE refuge {refuge_id})")
            coords_ref.update({
                'refugis_coordinates': refugis_coordinates,
                'last_updated': firestore.SERVER_TIMESTAMP
            })
            logger.info(f"Coordenades del refugi {refuge_id} actualitzades a coords_refugis")
        else:
            logger.warning(f"Refugi {refuge_id} no trobat a coords_refugis per actualitzar")
            
    except Exception as e:
        logger.error(f"Error actualitzant coords_refugis per UPDATE: {str(e)}")
        raise


def delete_refuge_from_coords_refugis(db, refuge_id: str) -> None:
    """Elimina un refugi de la col·lecció coords_refugis"""
    try:
        coords_ref = db.collection('coords_refugis').document('all_refugis_coords')
        logger.log(23, f"Firestore READ: collection=coords_refugis document=all_refugis_coords (for DELETE)")
        coords_doc = coords_ref.get()
        
        if not coords_doc.exists:
            logger.warning(f"Document coords_refugis no existeix, no es pot eliminar refugi {refuge_id}")
            return
        
        coords_data = coords_doc.to_dict()
        refugis_coordinates = coords_data.get('refugis_coordinates', [])
        
        # Filtrar per eliminar el refugi
        original_count = len(refugis_coordinates)
        refugis_coordinates = [coord for coord in refugis_coordinates if coord.get('id') != refuge_id]
        
        if len(refugis_coordinates) < original_count:
            logger.log(23, f"Firestore UPDATE: collection=coords_refugis document=all_refugis_coords (DELETE refuge {refuge_id})")
            coords_ref.update({
                'refugis_coordinates': refugis_coordinates,
                'total_refugis': len(refugis_coordinates),
                'last_updated': firestore.SERVER_TIMESTAMP
            })
            logger.info(f"Refugi {refuge_id} eliminat de coords_refugis")
        else:
            logger.warning(f"Refugi {refuge_id} no trobat a coords_refugis per eliminar")
            
    except Exception as e:
        logger.error(f"Error actualitzant coords_refugis per DELETE: {str(e)}")
        raise

# ==================== ESTRATÈGIES PER A APROVACIÓ DE PROPOSTES ====================

class ProposalApprovalStrategy(ABC):
    """Interfície base per a les estratègies d'aprovació de propostes"""
    
    @abstractmethod
    def execute(self, proposal: RefugeProposal, db) -> Tuple[bool, Optional[str]]:
        """
        Executa l'acció segons el tipus de proposta
        
        Args:
            proposal: La proposta a executar
            db: Client de Firestore
            
        Returns:
            (èxit, missatge d'error o None)
        """
        pass


class CreateRefugeStrategy(ProposalApprovalStrategy):
    """Estratègia per crear un nou refugi"""
    
    def execute(self, proposal: RefugeProposal, db) -> Tuple[bool, Optional[str]]:
        """Crea un nou refugi a partir del payload de la proposta"""
        try:
            # Generar un ID per al nou refugi
            refugis_ref = db.collection('data_refugis_lliures')
            new_refugi_ref = refugis_ref.document()
            new_refugi_id = new_refugi_ref.id
            
            # Assignar modified_at com a la data de creació de la proposta (sense hora)
            modified_at = datetime.fromisoformat(proposal.created_at.replace("Z", "")).date().isoformat()
            
            # Crear el model Refugi a partir del payload
            # Assegurar camps obligatoris
            coord_data = proposal.payload.get('coord', {})
            coord = Coordinates(long=coord_data.get('long'), lat=coord_data.get('lat'))
            
            # Assegurar que info_comp sempre té un valor
            info_comp_data = proposal.payload.get('info_comp', {})
            info_comp = InfoComplementaria.from_dict(info_comp_data) if info_comp_data else InfoComplementaria()
            
            # Crear el model Refugi
            refugi = Refugi(
                id=new_refugi_id,
                name=proposal.payload.get('name'),
                coord=coord,
                altitude=proposal.payload.get('altitude'),
                places=proposal.payload.get('places'),
                remarque=proposal.payload.get('remarque'),
                info_comp=info_comp,
                description=proposal.payload.get('description'),
                links=proposal.payload.get('links', []),
                type=proposal.payload.get('type', 'non gardé'),
                modified_at=modified_at,
                region=proposal.payload.get('region'),
                departement=proposal.payload.get('departement'),
                visitors=[],
                images_metadata=[]
            )
            
            # Convertir el model a format Firestore utilitzant el mapper
            refugi_data = RefugiLliureMapper.model_to_firestore(refugi)
            
            # Inicialitzar condition si està present al payload
            if 'condition' in proposal.payload:
                contributed_condition = proposal.payload.get('condition')
                if contributed_condition is not None and ConditionService.validate_condition_value(contributed_condition):
                    condition_data = ConditionService.initialize_condition(float(contributed_condition))
                    refugi_data['condition'] = condition_data['condition']
                    refugi_data['num_contributed_conditions'] = condition_data['num_contributed_conditions']
            
            # Crear el refugi a Firestore
            logger.log(23, f"Firestore WRITE: collection=data_refugis_lliures document={new_refugi_id} (CREATE from proposal)")
            new_refugi_ref.set(refugi_data)
            
            # Afegir a coords_refugis
            add_refuge_to_coords_refugis(db, new_refugi_id, refugi_data)
            
            # Actualitzar el refuge_id a la proposta
            proposal_ref = db.collection('refuges_proposals').document(proposal.id)
            logger.log(23, f"Firestore UPDATE: collection=refuges_proposals document={proposal.id} (set refuge_id)")
            proposal_ref.update({'refuge_id': new_refugi_id})
            
            # Invalidar cache de llistes de refugis
            cache_service.delete_pattern('refugi_search:*')
            cache_service.delete_pattern('refugi_coords:*')
            
            logger.info(f"Refugi creat amb ID {new_refugi_id} des de la proposta {proposal.id}")
            return True, None
            
        except Exception as e:
            logger.error(f"Error creant refugi des de proposta {proposal.id}: {str(e)}")
            return False, f"Error creating refuge: {str(e)}"


class UpdateRefugeStrategy(ProposalApprovalStrategy):
    """Estratègia per actualitzar un refugi existent"""
    
    def execute(self, proposal: RefugeProposal, db) -> Tuple[bool, Optional[str]]:
        """Actualitza un refugi existent amb el payload de la proposta"""
        try:
            if not proposal.refuge_id:
                return False, "refuge_id is required for update action"
            
            # Verificar que el refugi existeix
            refugi_ref = db.collection('data_refugis_lliures').document(proposal.refuge_id)
            logger.log(23, f"Firestore READ: collection=data_refugis_lliures document={proposal.refuge_id} (check exists)")
            refugi_doc = refugi_ref.get()
            
            if not refugi_doc.exists:
                return False, f"Refuge with ID {proposal.refuge_id} not found"
            
            # Obtenir les dades actuals del refugi per calcular la condition
            refugi_data = refugi_doc.to_dict()
            
            # Preparar les dades d'actualització a partir del payload
            update_data = {}
            
            # Assignar modified_at com a la data de creació de la proposta (sense hora)
            modified_at = datetime.fromisoformat(proposal.created_at.replace("Z", "")).date().isoformat()
            update_data['modified_at'] = modified_at
            
            # Copiar només els camps presents al payload
            for key, value in proposal.payload.items():
                if key == 'coord':
                    # Convertir coordenades al format correcte
                    update_data['coord'] = {
                        'long': value.get('long'),
                        'lat': value.get('lat')
                    }
                elif key == 'info_comp':
                    # Convertir info_comp al format correcte
                    info_comp = InfoComplementaria.from_dict(value)
                    update_data['info_comp'] = info_comp.to_dict()
                elif key == 'condition':
                    # Calcular la nova mitjana de condition
                    if value is not None and ConditionService.validate_condition_value(value):
                        current_condition = refugi_data.get('condition')
                        num_contributed = refugi_data.get('num_contributed_conditions', 0)
                        
                        # Calcular els nous valors
                        condition_data = ConditionService.calculate_condition_average(
                            current_condition=current_condition,
                            num_contributed_conditions=num_contributed,
                            contributed_condition=float(value)
                        )
                        
                        # Afegir els nous valors a update_data
                        update_data['condition'] = condition_data['condition']
                        update_data['num_contributed_conditions'] = condition_data['num_contributed_conditions']
                else:
                    update_data[key] = value
            
            # Actualitzar el refugi amb tots els camps (incloent condition si escau)
            logger.log(23, f"Firestore UPDATE: collection=data_refugis_lliures document={proposal.refuge_id} (UPDATE from proposal)")
            refugi_ref.update(update_data)
            
            # Actualitzar coords_refugis si cal (només si 'coord' o 'name' al payload)
            update_refuge_from_coords_refugis(db, proposal.refuge_id, update_data)
            
            # Invalidar cache relacionada amb aquest refugi
            cache_service.delete(cache_service.generate_key('refugi_detail', refugi_id=proposal.refuge_id))
            # NO invalidem refugi_search perquè les IDs no canvien (només update)
            # Només invalidem refugi_coords si 'coord' o 'name' estan al payload
            if 'coord' in update_data or 'name' in update_data:
                cache_service.delete_pattern('refugi_coords:*')
            
            logger.info(f"Refugi {proposal.refuge_id} actualitzat des de la proposta {proposal.id}")
            return True, None
            
        except Exception as e:
            logger.error(f"Error actualitzant refugi des de proposta {proposal.id}: {str(e)}")
            return False, f"Error updating refuge: {str(e)}"


class DeleteRefugeStrategy(ProposalApprovalStrategy):
    """Estratègia per eliminar un refugi"""
    
    def execute(self, proposal: RefugeProposal, db) -> Tuple[bool, Optional[str]]:
        """
        Elimina un refugi existent i totes les seves dades relacionades.
        No s'elimina el refuge_id de la llista de visitats de cada usuari per estalviar escriptures de Firestore. 
        (S'accepta certa inconsistencia en aquest cas)
        """
        try:
            if not proposal.refuge_id:
                return False, "refuge_id is required for delete action"
            
            # Verificar que el refugi existeix
            refugi_ref = db.collection('data_refugis_lliures').document(proposal.refuge_id)
            logger.log(23, f"Firestore READ: collection=data_refugis_lliures document={proposal.refuge_id} (check exists)")
            refugi_doc = refugi_ref.get()
            
            if not refugi_doc.exists:
                return False, f"Refuge with ID {proposal.refuge_id} not found"
            
            refugi_data = refugi_doc.to_dict()
            
            # ==================== PAS 1: REBUTJAR TOTES LES PROPOSALS PENDENTS ====================
            logger.info(f"[DELETE REFUGE] Pas 1: Rebutjant proposals pendents per refugi {proposal.refuge_id}")
            try:
                from ..daos.refuge_proposal_dao import RefugeProposalDAO
                proposal_dao = RefugeProposalDAO()
                
                # Obtenir totes les proposals pendents per aquest refugi
                pending_proposals = proposal_dao.list_all(filters={'status': 'pending', 'refuge_id': proposal.refuge_id})
                
                for pending_proposal in pending_proposals:
                    if pending_proposal.id != proposal.id:  # No rebutjar la proposta actual
                        success, error = proposal_dao.reject(
                            proposal_id=pending_proposal.id,
                            reviewer_uid=None,
                            reason="refuge has been deleted"
                        )
                        if success:
                            logger.info(f"Proposta {pending_proposal.id} rebutjada automàticament")
                        else:
                            logger.warning(f"No s'ha pogut rebutjar la proposta {pending_proposal.id}: {error}")
            except Exception as e:
                logger.error(f"Error rebutjant proposals pendents: {str(e)}")
                # Continuar amb l'eliminació encara que hi hagi errors
            
            # ==================== PAS 2: ELIMINAR TOTS ELS DUBTES ====================
            logger.info(f"[DELETE REFUGE] Pas 2: Eliminant dubtes del refugi {proposal.refuge_id}")
            try:
                from ..controllers.doubt_controller import DoubtController
                doubt_controller = DoubtController()
                
                # Obtenir tots els dubtes d'aquest refugi
                doubts, error = doubt_controller.get_doubts_by_refuge(proposal.refuge_id)
                if error:
                    logger.error(f"Error obtenint dubtes: {error}")
                    return False, f"Error getting doubts: {error}"
                
                if doubts:
                    for doubt in doubts:
                        # Passar el creator_uid del dubte per evitar problemes de permisos
                        success, error = doubt_controller.delete_doubt(doubt_id=doubt.id)
                        if not success:
                            logger.error(f"No s'ha pogut eliminar el dubte {doubt.id}: {error}")
                            return False, f"Error deleting doubt {doubt.id}: {error}"
                        logger.info(f"Dubte {doubt.id} eliminat correctament")
            except Exception as e:
                logger.error(f"Error eliminant dubtes: {str(e)}")
                return False, f"Error deleting doubts: {str(e)}"
            
            # ==================== PAS 3: ELIMINAR TOTES LES EXPERIÈNCIES ====================
            logger.info(f"[DELETE REFUGE] Pas 3: Eliminant experiències del refugi {proposal.refuge_id}")
            try:
                from ..controllers.experience_controller import ExperienceController
                experience_controller = ExperienceController()
                
                # Obtenir totes les experiències d'aquest refugi
                experiences, error = experience_controller.get_experiences_by_refuge(proposal.refuge_id)
                if error:
                    logger.error(f"Error obtenint experiències: {error}")
                    return False, f"Error getting experiences: {error}"
                
                if experiences:
                    for experience in experiences:
                        success, error = experience_controller.delete_experience(experience_id=experience.id)
                        if not success:
                            logger.error(f"No s'ha pogut eliminar l'experiència {experience.id}: {error}")
                            return False, f"Error deleting experience {experience.id}: {error}"
                        logger.info(f"Experiència {experience.id} eliminada correctament")
            except Exception as e:
                logger.error(f"Error eliminant experiències: {str(e)}")
                return False, f"Error deleting experiences: {str(e)}"
            
            # ==================== PAS 4: ELIMINAR TOTES LES FOTOS DEL REFUGI ====================
            logger.info(f"[DELETE REFUGE] Pas 4: Eliminant fotos del refugi {proposal.refuge_id}")
            try:
                # Obtenir les keys de totes les imatges del refugi
                media_metadata = refugi_data.get('media_metadata', {})
                
                if media_metadata:
                    media_keys = list(media_metadata.keys())
                    logger.info(f"Trobades {len(media_keys)} fotos per eliminar")
                    
                    from ..controllers.refugi_lliure_controller import RefugiLliureController
                    refugi_controller = RefugiLliureController()
                    
                    success, error = refugi_controller.delete_multiple_refugi_media(proposal.refuge_id, media_keys)
                    if not success:
                        logger.error(f"Error eliminant fotos del refugi: {error}")
                        return False, f"Error deleting media: {error}"
                    logger.info(f"Totes les fotos del refugi {proposal.refuge_id} eliminades correctament")
                else:
                    logger.info(f"No hi ha fotos per eliminar del refugi {proposal.refuge_id}")
            except Exception as e:
                logger.error(f"Error eliminant fotos del refugi: {str(e)}")
                return False, f"Error deleting media: {str(e)}"
            
            # ==================== PAS 5: ELIMINAR TOTES LES RENOVATIONS ====================
            logger.info(f"[DELETE REFUGE] Pas 5: Eliminant renovations del refugi {proposal.refuge_id}")
            try:
                from ..controllers.renovation_controller import RenovationController
                renovation_controller = RenovationController()
                
                # Obtenir totes les renovations d'aquest refugi
                success_get, renovations, error = renovation_controller.get_renovations_by_refuge(
                    refuge_id=proposal.refuge_id,
                    active_only=False
                )
                if not success_get:
                    logger.error(f"Error obtenint renovations: {error}")
                    return False, f"Error getting renovations: {error}"
                
                if renovations:
                    for renovation in renovations:
                        # Passar el creator_uid de la renovation per evitar problemes de permisos
                        success, error = renovation_controller.delete_renovation(
                            renovation_id=renovation.id,
                            user_uid=renovation.creator_uid
                        )
                        if not success:
                            logger.error(f"No s'ha pogut eliminar la renovation {renovation.id}: {error}")
                            return False, f"Error deleting renovation {renovation.id}: {error}"
                        logger.info(f"Renovation {renovation.id} eliminada correctament")
            except Exception as e:
                logger.error(f"Error eliminant renovations: {str(e)}")
                return False, f"Error deleting renovations: {str(e)}"
            
            # ==================== FINALMENT: ELIMINAR EL REFUGI ====================
            logger.info(f"[DELETE REFUGE] Eliminant el refugi {proposal.refuge_id}")
            
            # Eliminar el refugi
            logger.log(23, f"Firestore DELETE: collection=data_refugis_lliures document={proposal.refuge_id} (DELETE from proposal)")
            refugi_ref.delete()
            
            # Eliminar de coords_refugis
            delete_refuge_from_coords_refugis(db, proposal.refuge_id)
            
            # Invalidar cache relacionada amb aquest refugi
            cache_service.delete(cache_service.generate_key('refugi_detail', refugi_id=proposal.refuge_id))
            cache_service.delete_pattern('refugi_search:*')
            cache_service.delete_pattern('refugi_coords:*')
            
            logger.info(f"Refugi {proposal.refuge_id} i totes les seves dades relacionades eliminats correctament des de la proposta {proposal.id}")
            return True, None
            
        except Exception as e:
            logger.error(f"Error eliminant refugi des de proposta {proposal.id}: {str(e)}")
            return False, f"Error deleting refuge: {str(e)}"


class ProposalStrategySelector:
    """Selector d'estratègies per a l'aprovació de propostes"""
    
    @staticmethod
    def get_strategy(action: str) -> Optional[ProposalApprovalStrategy]:
        """Retorna l'estratègia adequada segons l'acció"""
        strategies = {
            'create': CreateRefugeStrategy(),
            'update': UpdateRefugeStrategy(),
            'delete': DeleteRefugeStrategy()
        }
        return strategies.get(action)


# ==================== DAO PRINCIPAL ====================

class RefugeProposalDAO:
    """DAO per a la gestió de propostes de refugis"""
    
    def __init__(self):
        self.collection_name = 'refuges_proposals'
        self.mapper = RefugeProposalMapper()
    
    def create(self, proposal_data: Dict[str, Any], creator_uid: str) -> Optional[RefugeProposal]:
        """Crea una nova proposta de refugi"""
        try:
            db = firestore_service.get_db()
            
            # Preparar les dades de la proposta
            proposal_dict = {
                'refuge_id': proposal_data.get('refuge_id'),
                'refuge_snapshot': proposal_data.get('refuge_snapshot'),
                'action': proposal_data.get('action'),
                'payload': proposal_data.get('payload'),
                'comment': proposal_data.get('comment'),
                'status': 'pending',
                'creator_uid': creator_uid,
                'created_at': get_madrid_now().isoformat(),
                'reviewer_uid': None,
                'reviewed_at': None,
                'rejection_reason': None
            }
            
            # Crear el document
            doc_ref = db.collection(self.collection_name).document()
            proposal_dict['id'] = doc_ref.id
            
            logger.log(23, f"Firestore WRITE: collection={self.collection_name} document={doc_ref.id} (CREATE proposal)")
            doc_ref.set(proposal_dict)
            
            # Invalidar cache de llistes de propostes
            cache_service.delete_pattern('proposal_list:*')
            
            return self.mapper.firestore_to_model(proposal_dict)
            
        except Exception as e:
            logger.error(f'Error creating proposal: {str(e)}')
            return None
    
    def get_by_id(self, proposal_id: str) -> Optional[RefugeProposal]:
        """Obté una proposta per ID amb cache"""
        cache_key = cache_service.generate_key('proposal_detail', proposal_id=proposal_id)
        
        cached_data = cache_service.get(cache_key)
        if cached_data is not None:
            return self.mapper.firestore_to_model(cached_data)
        
        try:
            db = firestore_service.get_db()
            doc_ref = db.collection(self.collection_name).document(proposal_id)
            logger.log(23, f"Firestore READ: collection={self.collection_name} document={proposal_id}")
            doc = doc_ref.get()
            
            if not doc.exists:
                return None
            
            proposal_data = doc.to_dict()
            
            timeout = cache_service.get_timeout('proposal_detail')
            cache_service.set(cache_key, proposal_data, timeout)
            
            return self.mapper.firestore_to_model(proposal_data)
            
        except Exception as e:
            logger.error(f'Error getting proposal by ID {proposal_id}: {str(e)}')
            return None
    
    def list_all(self, filters: Optional[Dict[str, Any]] = None) -> List[RefugeProposal]:
        """Llista totes les propostes amb filtres opcionals amb cache i ID caching
        
        Args:
            filters: Diccionari amb filtres opcionals:
                - status: Filtre per status
                - refuge_id: Filtre per ID del refugi
                - creator_uid: Filtre per UID del creador
        """
        filters = filters or {}
        
        # Generar clau de cache basada en els filtres
        cache_key = cache_service.generate_key(
            'proposal_list',
            status=filters.get('status', 'all'),
            refuge_id=filters.get('refuge_id', 'all'),
            creator_uid=filters.get('creator_uid', 'all')
        )
        
        try:
            # Funció per obtenir TOTES les dades completes d'una des de Firestore
            def fetch_all():
                db = firestore_service.get_db()
                query = db.collection(self.collection_name)
                
                # Construir la query amb els filtres
                filters_applied = []

                if filters.get('status'):
                    query = query.where('status', '==', filters['status'])
                    filters_applied.append(f"status={filters['status']}")
                
                if filters.get('refuge_id'):
                    query = query.where('refuge_id', '==', filters['refuge_id'])
                    filters_applied.append(f"refuge_id={filters['refuge_id']}")
                
                if filters.get('creator_uid'):
                    query = query.where('creator_uid', '==', filters['creator_uid'])
                    filters_applied.append(f"creator_uid={filters['creator_uid']}")
                
                if not filters_applied:
                    logger.log(23, f"Firestore READ: collection={self.collection_name} (all proposals)")
                else:
                    logger.log(23, f"Firestore READ: collection={self.collection_name} with filters: {', '.join(filters_applied)}")
                
                # Ordenar per data de creació (més recents primer)
                query = query.order_by('created_at', direction=firestore.Query.DESCENDING)
                
                docs = query.stream()
                return [doc.to_dict() for doc in docs]
            
            # Funció per obtenir una proposta individual per ID
            def fetch_single(proposal_id: str):
                db = firestore_service.get_db()
                doc_ref = db.collection(self.collection_name).document(proposal_id)
                logger.log(23, f"Firestore READ: collection={self.collection_name} document={proposal_id}")
                doc = doc_ref.get()
                return doc.to_dict() if doc.exists else None
            
            # Funció per extreure l'ID d'una proposta
            def get_id(proposal_data: Dict[str, Any]) -> str:
                return proposal_data['id']
            
            # Usar estratègia ID caching del cache_service
            proposals_data = cache_service.get_or_fetch_list(
                list_cache_key=cache_key,
                detail_key_prefix='proposal_detail',
                fetch_all_fn=fetch_all,
                fetch_single_fn=fetch_single,
                get_id_fn=get_id,
                list_timeout=cache_service.get_timeout('proposal_list'),
                detail_timeout=cache_service.get_timeout('proposal_detail')
            )
            
            return self.mapper.firestore_list_to_models(proposals_data)
            
        except Exception as e:
            logger.error(f'Error listing proposals: {str(e)}')
            return []
    
    def approve(self, proposal_id: str, reviewer_uid: str) -> Tuple[bool, Optional[str]]:
        """Aprova una proposta i executa l'acció corresponent"""
        try:
            # Obtenir la proposta
            proposal = self.get_by_id(proposal_id)
            if not proposal:
                return False, "Proposal not found"
            
            if proposal.status != 'pending':
                return False, f"Proposal is already {proposal.status}"
            
            db = firestore_service.get_db()
            
            # Obtenir l'estratègia adequada
            strategy = ProposalStrategySelector.get_strategy(proposal.action)
            if not strategy:
                return False, f"Invalid action: {proposal.action}"
            
            # Executar l'estratègia
            success, error = strategy.execute(proposal, db)
            
            if not success:
                return False, error
            
            # Actualitzar l'estat de la proposta
            proposal_ref = db.collection(self.collection_name).document(proposal_id)
            logger.log(23, f"Firestore UPDATE: collection={self.collection_name} document={proposal_id} (APPROVE)")
            proposal_ref.update({
                'status': 'approved',
                'reviewer_uid': reviewer_uid,
                'reviewed_at': get_madrid_now().isoformat()
            })
            
            # Invalidar cache (només detail, la list no canvia en updates)
            cache_service.delete_pattern(f'proposal_detail:proposal_id:{proposal_id}:*')
            
            return True, None
            
        except Exception as e:
            logger.error(f'Error approving proposal {proposal_id}: {str(e)}')
            return False, f"Internal error: {str(e)}"
    
    def reject(self, proposal_id: str, reviewer_uid: Optional[str], reason: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """Rebutja una proposta"""
        try:
            # Obtenir la proposta
            proposal = self.get_by_id(proposal_id)
            if not proposal:
                return False, "Proposal not found"
            
            if proposal.status != 'pending':
                return False, f"Proposal is already {proposal.status}"
            
            db = firestore_service.get_db()
            
            # Actualitzar l'estat de la proposta
            proposal_ref = db.collection(self.collection_name).document(proposal_id)
            update_data = {
                'status': 'rejected',
                'reviewer_uid': reviewer_uid,
                'reviewed_at': get_madrid_now().isoformat()
            }
            
            if reason:
                update_data['rejection_reason'] = reason
            
            logger.log(23, f"Firestore UPDATE: collection={self.collection_name} document={proposal_id} (REJECT)")
            proposal_ref.update(update_data)
            
            # Invalidar cache (només detail, la list no canvia en updates)
            cache_service.delete_pattern(f'proposal_detail:proposal_id:{proposal_id}:*')
            
            return True, None
            
        except Exception as e:
            logger.error(f'Error rejecting proposal {proposal_id}: {str(e)}')
            return False, f"Internal error: {str(e)}"
    
    def anonymize_proposals_by_creator(self, creator_uid: str) -> Tuple[bool, Optional[str]]:
        """
        Anonimitza totes les proposals creades per un usuari posant creator_uid a 'unknown'
        
        Args:
            creator_uid: UID del creador
            
        Returns:
            Tuple (èxit: bool, missatge d'error: Optional[str])
        """
        try:
            db = firestore_service.get_db()
            
            # Obtenir totes les proposals del creador
            logger.log(23, f"Firestore QUERY: collection={self.collection_name} where creator_uid=={creator_uid}")
            proposals_query = db.collection(self.collection_name).where('creator_uid', '==', creator_uid).stream()
            
            anonymized_count = 0
            
            for proposal_doc in proposals_query:
                # Actualitzar creator_uid a 'unknown'
                logger.log(23, f"Firestore UPDATE: collection={self.collection_name} document={proposal_doc.id} (anonymize)")
                proposal_doc.reference.update({'creator_uid': 'unknown'})
                anonymized_count += 1
                
                # Invalida cache de detall
                cache_service.delete_pattern(f'proposal_detail:proposal_id:{proposal_doc.id}:*')
            
            # NO invalidem proposal_list perquè les IDs no canvien (només update)
            
            logger.info(f"{anonymized_count} proposals anonimitzades del creador {creator_uid}")
            return True, None
            
        except Exception as e:
            logger.error(f"Error anonimitzant proposals del creador {creator_uid}: {str(e)}")
            return False, str(e)
