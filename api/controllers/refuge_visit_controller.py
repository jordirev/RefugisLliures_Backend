"""
Controller per a la gestió de visites a refugis
"""
import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import date
from ..daos.refuge_visit_dao import RefugeVisitDAO
from ..daos.refugi_lliure_dao import RefugiLliureDAO
from ..mappers.refuge_visit_mapper import RefugeVisitMapper
from ..models.refuge_visit import RefugeVisit, UserVisit
from ..utils.timezone_utils import get_madrid_today

logger = logging.getLogger(__name__)


class RefugeVisitController:
    """Controller per gestionar operacions de visites a refugis"""
    
    def __init__(self):
        """Inicialitza el controller"""
        self.visit_dao = RefugeVisitDAO()
        self.refuge_dao = RefugiLliureDAO()
        self.mapper = RefugeVisitMapper()
    
    def get_refuge_visits(self, refuge_id: str) -> tuple[bool, List[RefugeVisit], Optional[str]]:
        """
        Obté totes les visites actuals i futures d'un refugi
        
        Args:
            refuge_id: ID del refugi
            
        Returns:
            tuple: (success, list_of_visits, error_message)
        """
        try:
            # Comprova que el refugi existeix
            refuge = self.refuge_dao.get_refugi_by_id(refuge_id)
            if not refuge:
                return False, [], f"Refugi amb ID {refuge_id} no trobat"
            
            # Obté la data d'avui
            today = get_madrid_today()
            
            # Obté les visites futures
            visits = self.visit_dao.get_visits_by_refuge(refuge_id, today)
            
            logger.info(f"Obtingudes {len(visits)} visites per al refugi {refuge_id}")
            return True, visits, None
            
        except Exception as e:
            logger.error(f"Error en get_refuge_visits: {str(e)}")
            return False, [], f"Error intern: {str(e)}"
    
    def get_user_visits(self, uid: str) -> tuple[bool, List[tuple[str, RefugeVisit]], Optional[str]]:
        """
        Obté totes les visites d'un usuari
        
        Args:
            uid: UID de l'usuari
            
        Returns:
            tuple: (success, list_of_(visit_id, visit), error_message)
        """
        try:
            visits = self.visit_dao.get_visits_by_user(uid)
            
            logger.info(f"Obtingudes {len(visits)} visites per a l'usuari {uid}")
            return True, visits, None
            
        except Exception as e:
            logger.error(f"Error en get_user_visits: {str(e)}")
            return False, [], f"Error intern: {str(e)}"
    
    def create_visit(self, refuge_id: str, visit_date: str, uid: str, num_visitors: int) -> tuple[bool, Optional[RefugeVisit], Optional[str]]:
        """
        Crea o actualitza una visita per un usuari
        
        Args:
            refuge_id: ID del refugi
            visit_date: Data de la visita (format YYYY-MM-DD)
            uid: UID de l'usuari
            num_visitors: Nombre de visitants
            
        Returns:
            tuple: (success, visit_object, error_message)
        """
        try:
            # Comprova que el refugi existeix
            refuge = self.refuge_dao.get_refugi_by_id(refuge_id)
            if not refuge:
                return False, None, f"Refugi amb ID {refuge_id} no trobat"
            
            # Validació de la data (ha de ser futura)
            try:
                visit_date_obj = date.fromisoformat(visit_date)
                today = get_madrid_today()
                if visit_date_obj < today:
                    return False, None, "La data de la visita ha de ser igual o posterior a avui"
            except ValueError:
                return False, None, "Format de data invàlid. Utilitza YYYY-MM-DD"
            
            # Primer comprova si la visita ja existeix
            result = self.visit_dao.get_visit_by_refuge_and_date(refuge_id, visit_date)
            
            if result:
                # La visita ja existeix, afegeix el visitant
                visit_id, existing_visit = result
                
                # Comprova si l'usuari ja està registrat
                if existing_visit.visitors:
                    for visitor in existing_visit.visitors:
                        if visitor.uid == uid:
                            return False, None, "Ja estàs registrat a aquesta visita"
                
                # Afegeix el nou visitant a la llista
                new_visitor = UserVisit(uid=uid, num_visitors=num_visitors)
                if existing_visit.visitors:
                    existing_visit.visitors.append(new_visitor)
                else:
                    existing_visit.visitors = [new_visitor]
                
                # Actualitza el total
                existing_visit.total_visitors += num_visitors
                
                # Mappeja i actualitza
                visit_data = self.mapper.model_to_firebase(existing_visit)
                success = self.visit_dao.add_visitor_to_visit(visit_id, visit_data)
                if not success:
                    return False, None, "Error afegint visitant a la visita"
                
                visit = existing_visit
            else:
                # La visita no existeix, crea el model i mappeja'l
                new_visit = RefugeVisit(
                    date=visit_date,
                    refuge_id=refuge_id,
                    visitors=[UserVisit(uid=uid, num_visitors=num_visitors)],
                    total_visitors=num_visitors
                )
                
                # Mappeja i crea
                visit_data = self.mapper.model_to_firebase(new_visit)
                success, visit_id, error = self.visit_dao.create_visit(visit_data)
                if not success:
                    return False, None, error or "Error creant la visita"
                
                visit = new_visit
            
            logger.info(f"Visita creada/actualitzada correctament: {visit_id}")
            return True, visit, None
            
        except Exception as e:
            logger.error(f"Error en create_visit: {str(e)}")
            return False, None, f"Error intern: {str(e)}"
    
    def update_visit(self, refuge_id: str, visit_date: str, uid: str, num_visitors: int) -> tuple[bool, Optional[RefugeVisit], Optional[str]]:
        """
        Actualitza el nombre de visitants d'un usuari en una visita
        
        Args:
            refuge_id: ID del refugi
            visit_date: Data de la visita (format YYYY-MM-DD)
            uid: UID de l'usuari
            num_visitors: Nou nombre de visitants
            
        Returns:
            tuple: (success, visit_object, error_message)
        """
        try:
            # Obté la visita
            result = self.visit_dao.get_visit_by_refuge_and_date(refuge_id, visit_date)
            if not result:
                return False, None, "Visita no trobada"
            
            visit_id, visit = result
            
            # Busca l'usuari a la llista de visitors i actualitza el seu num_visitors
            user_found = False
            old_num_visitors = 0
            
            if visit.visitors:
                for visitor in visit.visitors:
                    if visitor.uid == uid:
                        user_found = True
                        old_num_visitors = visitor.num_visitors
                        visitor.num_visitors = num_visitors
                        break
            
            if not user_found:
                return False, None, "No estàs registrat a aquesta visita"
            
            # Actualitza el total
            visit.total_visitors = visit.total_visitors - old_num_visitors + num_visitors
            
            # Mappeja i actualitza la visita al DAO
            visit_data = self.mapper.model_to_firebase(visit)
            success = self.visit_dao.update_visitor_in_visit(visit_id, visit_data)
            if not success:
                return False, None, "Error actualitzant la visita"
            
            logger.info(f"Visita actualitzada correctament: {visit_id}")
            return True, visit, None
            
        except Exception as e:
            logger.error(f"Error en update_visit: {str(e)}")
            return False, None, f"Error intern: {str(e)}"
    
    def delete_visit(self, refuge_id: str, visit_date: str, uid: str) -> tuple[bool, Optional[str]]:
        """
        Elimina un usuari d'una visita
        
        Args:
            refuge_id: ID del refugi
            visit_date: Data de la visita (format YYYY-MM-DD)
            uid: UID de l'usuari
            
        Returns:
            tuple: (success, error_message)
        """
        try:
            # Obté la visita
            result = self.visit_dao.get_visit_by_refuge_and_date(refuge_id, visit_date)
            if not result:
                return False, "Visita no trobada"
            
            visit_id = result[0]
            
            # Elimina el visitant
            success = self.visit_dao.remove_visitor_from_visit(visit_id, uid)
            if not success:
                return False, "No estàs registrat a aquesta visita"
            
            logger.info(f"Visitant eliminat de la visita: {visit_id}")
            return True, None
            
        except Exception as e:
            logger.error(f"Error en delete_visit: {str(e)}")
            return False, f"Error intern: {str(e)}"
    
    def process_yesterday_visits(self) -> tuple[bool, Dict[str, Any], Optional[str]]:
        """
        Processa les visites d'ahir:
        - Afegeix els visitants a la llista de visitors del refugi
        - Elimina els documents de visita si estan buits (total_visitors=0 i visitors=[])
        
        Returns:
            tuple: (success, stats_dict, error_message)
        """
        try:
            from datetime import timedelta
            
            # Calcula la data d'ahir
            today = get_madrid_today()
            yesterday = today - timedelta(days=1)
            yesterday_str = yesterday.isoformat()
            
            # Obté totes les visites d'ahir
            visits = self.visit_dao.get_visits_by_date(yesterday_str)
            
            stats = {
                'processed_visits': 0,
                'deleted_visits': 0,
                'updated_refuges': 0,
                'total_visitors_added': 0
            }
            
            for visit_id, visit in visits:
                stats['processed_visits'] += 1
                
                # Si la visita està buida, elimina-la
                if visit.total_visitors == 0 and not visit.visitors:
                    self.visit_dao.delete_visit(visit_id)
                    stats['deleted_visits'] += 1
                    logger.info(f"Visita buida eliminada: {visit_id}")
                    continue
                
                # Afegeix els visitants al refugi
                if visit.visitors:
                    # Obté el refugi
                    refuge = self.refuge_dao.get_refugi_by_id(visit.refuge_id)
                    if not refuge:
                        logger.warning(f"Refugi no trobat: {visit.refuge_id}")
                        continue
                    
                    # Afegeix els UIDs a la llista de visitors del refugi
                    existing_visitors = refuge.visitors if refuge.visitors else []
                    new_visitors = [visitor.uid for visitor in visit.visitors]
                    
                    # Afegeix només els nous UIDs (evita duplicats)
                    updated_visitors = list(set(existing_visitors + new_visitors))
                    
                    # Actualitza el refugi
                    success = self.refuge_dao.update_refugi_visitors(visit.refuge_id, updated_visitors)
                    if success:
                        stats['updated_refuges'] += 1
                        stats['total_visitors_added'] += len(new_visitors)
                        logger.info(f"Refugi {visit.refuge_id} actualitzat amb {len(new_visitors)} visitants")
                    else:
                        logger.warning(f"Error actualitzant refugi: {visit.refuge_id}")
            
            logger.info(f"Visites d'ahir processades: {stats}")
            return True, stats, None
            
        except Exception as e:
            logger.error(f"Error en process_yesterday_visits: {str(e)}")
            return False, {}, f"Error intern: {str(e)}"
