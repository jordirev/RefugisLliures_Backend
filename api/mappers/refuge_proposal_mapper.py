"""
Mapper per a la conversió entre dades de Firestore i models de proposta de refugi
"""
from typing import List, Dict, Any
from ..models.refuge_proposal import RefugeProposal


class RefugeProposalMapper:
    """Mapper per convertir entre dades de Firestore i models de proposta de refugi"""
    
    @staticmethod
    def firestore_to_model(data: Dict[str, Any]) -> RefugeProposal:
        """Converteix dades de Firestore a model RefugeProposal"""
        return RefugeProposal.from_dict(data)
    
    @staticmethod
    def model_to_firestore(proposal: RefugeProposal) -> Dict[str, Any]:
        """Converteix model RefugeProposal a format Firestore"""
        return proposal.to_dict()
    
    @staticmethod
    def firestore_list_to_models(data_list: List[Dict[str, Any]]) -> List[RefugeProposal]:
        """Converteix llista de dades de Firestore a llista de models"""
        return [RefugeProposalMapper.firestore_to_model(data) for data in data_list]
    
    @staticmethod
    def models_to_firestore_list(proposals: List[RefugeProposal]) -> List[Dict[str, Any]]:
        """Converteix llista de models a llista de dades Firestore"""
        return [RefugeProposalMapper.model_to_firestore(proposal) for proposal in proposals]
