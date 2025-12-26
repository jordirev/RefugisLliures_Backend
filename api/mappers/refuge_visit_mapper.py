"""
Mapper per a la transformació de dades de visites a refugis entre Firebase i Django
"""
from typing import Dict, Any, Optional
from ..models.refuge_visit import RefugeVisit, UserVisit


class RefugeVisitMapper:
    """Mapper per transformar dades entre Firebase i models Django"""
    
    @staticmethod
    def firebase_to_model(firebase_data: Dict[str, Any]) -> RefugeVisit:
        """
        Converteix dades de Firebase a model Django RefugeVisit
        
        Args:
            firebase_data: Diccionari amb dades de Firebase
            
        Returns:
            RefugeVisit: Instància del model RefugeVisit
        """
        # Converteix la llista de visitors de dict a UserVisit
        visitors = []
        if 'visitors' in firebase_data and firebase_data['visitors']:
            for visitor_data in firebase_data['visitors']:
                visitors.append(UserVisit(
                    uid=visitor_data.get('uid', ''),
                    num_visitors=visitor_data.get('num_visitors', 0)
                ))
        
        return RefugeVisit(
            date=firebase_data.get('date', ''),
            refuge_id=firebase_data.get('refuge_id', ''),
            visitors=visitors,
            total_visitors=firebase_data.get('total_visitors', 0)
        )
    
    @staticmethod
    def model_to_firebase(visit: RefugeVisit) -> Dict[str, Any]:
        """
        Converteix model Django RefugeVisit a diccionari per Firebase
        
        Args:
            visit: Instància del model RefugeVisit
            
        Returns:
            Dict: Diccionari amb dades per Firebase
        """
        # Converteix la llista de UserVisit a dict
        visitors_list = []
        if visit.visitors:
            for visitor in visit.visitors:
                visitors_list.append({
                    'uid': visitor.uid,
                    'num_visitors': visitor.num_visitors
                })
        
        return {
            'date': visit.date,
            'refuge_id': visit.refuge_id,
            'visitors': visitors_list,
            'total_visitors': visit.total_visitors
        }
    
    @staticmethod
    def validate_firebase_data(firebase_data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Valida les dades rebudes de Firebase
        
        Args:
            firebase_data: Diccionari amb dades de Firebase
            
        Returns:
            tuple: (és_vàlid, missatge_error)
        """
        required_fields = ['date', 'refuge_id']
        
        for field in required_fields:
            if field not in firebase_data:
                return False, f"Camp requerit '{field}' no trobat"
        
        return True, None
