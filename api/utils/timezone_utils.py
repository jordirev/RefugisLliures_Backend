"""
Utilitats per a gestió de zones horàries
"""
from datetime import datetime, date
from zoneinfo import ZoneInfo


def get_madrid_timezone():
    """
    Retorna la zona horària de Madrid
    
    Returns:
        ZoneInfo: Zona horària de Madrid
    """
    return ZoneInfo('Europe/Madrid')


def get_madrid_now():
    """
    Retorna el datetime actual en zona horària de Madrid
    
    Returns:
        datetime: Datetime actual en zona horària de Madrid
    """
    return datetime.now(get_madrid_timezone())


def get_madrid_today():
    """
    Retorna la data actual (només data, sense hora) en zona horària de Madrid
    
    Returns:
        date: Data actual en zona horària de Madrid
    """
    return get_madrid_now().date()
