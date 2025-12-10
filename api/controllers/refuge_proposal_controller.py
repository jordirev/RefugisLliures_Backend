"""
Controller per a la gestió de propostes de refugis
"""
import logging
from typing import Dict, Any, List, Optional, Tuple
from ..daos.refuge_proposal_dao import RefugeProposalDAO
from ..models.refuge_proposal import RefugeProposal

logger = logging.getLogger(__name__)


class RefugeProposalController:
    """Controller per a la gestió de propostes de refugis"""
    
    def __init__(self):
        self.proposal_dao = RefugeProposalDAO()
    
    def create_proposal(self, proposal_data: Dict[str, Any], creator_uid: str) -> Tuple[Optional[RefugeProposal], Optional[str]]:
        """
        Crea una nova proposta de refugi
        
        Args:
            proposal_data: Dades de la proposta (refuge_id, action, payload, comment)
            creator_uid: UID de l'usuari creador
            
        Returns:
            (RefugeProposal o None, missatge d'error o None)
        """
        try:
            proposal = self.proposal_dao.create(proposal_data, creator_uid)
            
            if not proposal:
                return None, "Error creating proposal"
            
            return proposal, None
            
        except Exception as e:
            logger.error(f'Error in create_proposal: {str(e)}')
            return None, f"Internal server error: {str(e)}"
    
    def get_proposal_by_id(self, proposal_id: str) -> Tuple[Optional[RefugeProposal], Optional[str]]:
        """
        Obté una proposta per ID
        
        Args:
            proposal_id: ID de la proposta
            
        Returns:
            (RefugeProposal o None, missatge d'error o None)
        """
        try:
            proposal = self.proposal_dao.get_by_id(proposal_id)
            
            if not proposal:
                return None, "Proposal not found"
            
            return proposal, None
            
        except Exception as e:
            logger.error(f'Error in get_proposal_by_id: {str(e)}')
            return None, f"Internal server error: {str(e)}"
    
    def list_proposals(self, status_filter: Optional[str] = None) -> Tuple[Optional[List[RefugeProposal]], Optional[str]]:
        """
        Llista totes les propostes amb filtre opcional per status
        
        Args:
            status_filter: Filtre per status ('pending', 'approved', 'rejected') o None per totes
            
        Returns:
            (Llista de RefugeProposal o None, missatge d'error o None)
        """
        try:
            # Validar el filtre de status
            if status_filter and status_filter not in ['pending', 'approved', 'rejected']:
                return None, f"Invalid status filter: {status_filter}. Must be 'pending', 'approved', or 'rejected'"
            
            proposals = self.proposal_dao.list_all(status_filter)
            
            return proposals, None
            
        except Exception as e:
            logger.error(f'Error in list_proposals: {str(e)}')
            return None, f"Internal server error: {str(e)}"
    
    def approve_proposal(self, proposal_id: str, reviewer_uid: str) -> Tuple[bool, Optional[str]]:
        """
        Aprova una proposta i executa l'acció corresponent
        
        Args:
            proposal_id: ID de la proposta
            reviewer_uid: UID de l'admin que aprova
            
        Returns:
            (èxit, missatge d'error o None)
        """
        try:
            success, error = self.proposal_dao.approve(proposal_id, reviewer_uid)
            
            if not success:
                return False, error
            
            return True, None
            
        except Exception as e:
            logger.error(f'Error in approve_proposal: {str(e)}')
            return False, f"Internal server error: {str(e)}"
    
    def reject_proposal(self, proposal_id: str, reviewer_uid: str, reason: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Rebutja una proposta
        
        Args:
            proposal_id: ID de la proposta
            reviewer_uid: UID de l'admin que rebutja
            reason: Raó del rebuig (opcional)
            
        Returns:
            (èxit, missatge d'error o None)
        """
        try:
            success, error = self.proposal_dao.reject(proposal_id, reviewer_uid, reason)
            
            if not success:
                return False, error
            
            return True, None
            
        except Exception as e:
            logger.error(f'Error in reject_proposal: {str(e)}')
            return False, f"Internal server error: {str(e)}"
