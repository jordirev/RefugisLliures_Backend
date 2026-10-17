"""
Utilitats d'edat. La data de naixement només s'usa en memòria per calcular l'edat:
MAI es desa ni es registra als logs (minimització, art. 5.1.c RGPD).
"""
from datetime import date, datetime
from typing import Optional, Union

from .timezone_utils import get_madrid_today


def _to_date(value: Union[date, datetime, str]) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value), '%Y-%m-%d').date()


def compute_age(birth_date: Union[date, datetime, str], today: Optional[date] = None) -> int:
    """Edat en anys complerts a data d'avui (zona Europe/Madrid)"""
    born = _to_date(birth_date)
    today = today or get_madrid_today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def is_old_enough(birth_date: Union[date, datetime, str], threshold: int, today: Optional[date] = None) -> bool:
    return compute_age(birth_date, today) >= threshold
