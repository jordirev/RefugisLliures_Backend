"""
Servei per gestionar l'actualització de la condition d'un refugi amb mitjana de contribucions
"""
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class ConditionService:
    """Servei per gestionar la condition d'un refugi amb mitjana de contribucions"""
    
    @staticmethod
    def calculate_condition_average(
        current_condition: Optional[float],
        num_contributed_conditions: int,
        contributed_condition: float
    ) -> Dict[str, Any]:
        """
        Calcula els nous valors de condition i num_contributed_conditions basant-se en la mitjana.
        
        Fórmula: condition = ((condition_actual * num_contributed_conditions) + contributed_condition) / (num_contributed_conditions + 1)
        
        Args:
            current_condition: Condition actual del refugi (None si és la primera contribució)
            num_contributed_conditions: Nombre de contribucions actuals
            contributed_condition: Nova condition contribuïda (0-3)
            
        Returns:
            dict: Diccionari amb 'condition' i 'num_contributed_conditions' actualitzats
        """
        # Si no hi ha condition actual, inicialitzar
        if current_condition is None:
            new_condition = float(contributed_condition)
            new_num_contributed = 1
        else:
            # Calcular la nova mitjana
            current_condition = float(current_condition)
            new_condition = ((current_condition * num_contributed_conditions) + contributed_condition) / (num_contributed_conditions + 1)
            new_num_contributed = num_contributed_conditions + 1
        
        logger.info(
            f"Condition calculada: "
            f"{current_condition if current_condition is not None else 'None'} -> {new_condition:.2f} "
            f"(contribucions: {new_num_contributed})"
        )
        
        return {
            'condition': new_condition,
            'num_contributed_conditions': new_num_contributed
        }
    
    @staticmethod
    def initialize_condition(
        contributed_condition: float
    ) -> Dict[str, Any]:
        """
        Inicialitza els valors de condition per a un refugi nou.
        
        Args:
            contributed_condition: Condition inicial (0-3)
            
        Returns:
            dict: Diccionari amb 'condition' i 'num_contributed_conditions'
        """
        return {
            'condition': float(contributed_condition),
            'num_contributed_conditions': 1
        }
    
    @staticmethod
    def validate_condition_value(condition: Any) -> bool:
        """
        Valida que una condition sigui un valor vàlid (0-3).
        
        Args:
            condition: Valor a validar
            
        Returns:
            bool: True si és vàlid, False altrament
        """
        try:
            condition_float = float(condition)
            return 0 <= condition_float <= 3
        except (TypeError, ValueError):
            return False
