"""
Utilitats per a gestió de zones horàries.

La zona de negoci és `Europe/Madrid` i és la `TIME_ZONE` de Django (decisió del PO, 26/10): aquestes funcions són
embolcalls de `django.utils.timezone` que es mantenen pel codi existent.
"""
from datetime import datetime, date
from zoneinfo import ZoneInfo

from django.utils import timezone

MADRID_TZ = 'Europe/Madrid'


def get_madrid_timezone():
    """
    Retorna la zona horària de Madrid

    Returns:
        ZoneInfo: Zona horària de Madrid
    """
    return ZoneInfo(MADRID_TZ)


def get_madrid_now():
    """
    Retorna el datetime actual en zona horària de Madrid

    Returns:
        datetime: Datetime actual en zona horària de Madrid
    """
    return timezone.now().astimezone(get_madrid_timezone())


def get_madrid_today():
    """
    Retorna la data actual (només data, sense hora) en zona horària de Madrid

    Returns:
        date: Data actual en zona horària de Madrid
    """
    return get_madrid_now().date()


def madrid_after(start: datetime, delta) -> datetime:
    """
    `start + delta` com a **durada real** (en UTC), expressat en hora de Madrid.

    Sumar un `timedelta` a un `datetime` amb `ZoneInfo` és aritmètica de rellotge de paret: si es travessa un canvi
    d'hora, «+1 dia» són 23 o 25 h reals i «+365 dies» pot quedar 1 h curt (TTL d'auditoria, caducitat d'intents).
    """
    return (start.astimezone(ZoneInfo('UTC')) + delta).astimezone(get_madrid_timezone())


def make_madrid_aware(value: datetime) -> datetime:
    """Un `datetime` naïf s'interpreta com a hora de Madrid (DST inclòs); un de conscient es retorna igual."""
    if timezone.is_naive(value):
        return value.replace(tzinfo=get_madrid_timezone())
    return value
