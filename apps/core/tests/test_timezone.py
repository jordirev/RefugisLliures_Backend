"""
Zona horària de negoci (decisió del PO, 26/10): `TIME_ZONE = 'Europe/Madrid'`.

- «Avui», `timezone.localdate()`, `__date`/`Trunc*` i els `datetime` naïfs són hora de Madrid.
- Els instants es desen com a `timestamptz` (UTC) i la sessió de Postgres de Django és UTC (Django la hi força amb
  `USE_TZ`), així que el SQL **no** pot calcular «avui» (`CURRENT_DATE`, `now()::date`...): seria la data UTC, un dia
  abans entre les 00:00 i la 01:00/02:00 de Madrid. Ho vigila `test_cap_sql_calcula_la_data_d_avui`.
"""
import re
from datetime import date, datetime, timezone as dt_timezone
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

import pytest
from django.conf import settings
from django.db import connection
from django.db.models import DateTimeField, Value
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.core import timezone_utils

ROOT = Path(settings.BASE_DIR)
MADRID = ZoneInfo('Europe/Madrid')
# 23:30 UTC del 31/12 = 00:30 de l'1/1 a Madrid (hivern, +01:00); 22:30 UTC del 30/6 = 00:30 de l'1/7 (estiu, +02:00)
WINTER_EDGE = datetime(2025, 12, 31, 23, 30, tzinfo=dt_timezone.utc)
SUMMER_EDGE = datetime(2025, 6, 30, 22, 30, tzinfo=dt_timezone.utc)


def test_zona_de_django_es_madrid_i_use_tz():
    assert settings.TIME_ZONE == 'Europe/Madrid'
    assert settings.USE_TZ is True


@pytest.mark.parametrize('instant, expected', [(WINTER_EDGE, date(2026, 1, 1)), (SUMMER_EDGE, date(2025, 7, 1))])
def test_avui_de_madrid_i_localdate_coincideixen_a_la_frontera_del_dia(instant, expected):
    with mock.patch('django.utils.timezone.now', return_value=instant):
        assert timezone_utils.get_madrid_today() == expected
        assert timezone.localdate() == expected
        assert timezone_utils.get_madrid_now().utcoffset() == instant.astimezone(MADRID).utcoffset()


def test_naif_s_interpreta_com_a_madrid_amb_dst():
    assert timezone_utils.make_madrid_aware(datetime(2025, 1, 15, 10, 0)).isoformat() == '2025-01-15T10:00:00+01:00'
    assert timezone_utils.make_madrid_aware(datetime(2025, 7, 15, 10, 0)).isoformat() == '2025-07-15T10:00:00+02:00'
    aware = datetime(2025, 7, 15, 10, 0, tzinfo=dt_timezone.utc)
    assert timezone_utils.make_madrid_aware(aware) is aware


@pytest.mark.django_db
@pytest.mark.parametrize('instant, expected', [(WINTER_EDGE, date(2026, 1, 1)), (SUMMER_EDGE, date(2025, 7, 1))])
def test_truncdate_de_l_orm_dona_la_data_de_madrid(instant, expected):
    """`__date`/`TruncDate` converteixen amb `AT TIME ZONE 'Europe/Madrid'` encara que la sessió sigui UTC."""
    from apps.accounts.models import Language
    got = (Language.objects.annotate(d=TruncDate(Value(instant, output_field=DateTimeField())))
           .values_list('d', flat=True).first())
    assert got == expected


@pytest.mark.django_db
def test_la_sessio_de_postgres_de_django_continua_en_utc():
    """Si algun dia canvia (p. ex. `DATABASES[...]['TIME_ZONE']`), cal revisar el test de guarda de més avall."""
    with connection.cursor() as cur:
        cur.execute("SELECT current_setting('TimeZone')")
        assert cur.fetchone()[0] in ('UTC', 'Etc/UTC', 'GMT')


# ---------- Guarda: cap codi calcula «avui» fora de get_madrid_today()/localdate() ----------

FORBIDDEN = [
    (re.compile(r'\bCURRENT_DATE\b', re.I), 'CURRENT_DATE (data UTC de la sessió)'),
    (re.compile(r'\bLOCALTIMESTAMP\b|\bLOCALTIME\b', re.I), 'LOCALTIMESTAMP/LOCALTIME (hora UTC de la sessió)'),
    (re.compile(r'now\(\)\s*::\s*date|now\(\)\s*AS\s+date|current_timestamp\s*::\s*date', re.I),
     'now()::date (data UTC de la sessió)'),
    (re.compile(r'\bdate\.today\(\)'), 'date.today() (zona del servidor)'),
    (re.compile(r'\bdatetime\.(now|today)\(\s*\)'), 'datetime.now()/today() naïf (zona del servidor)'),
    (re.compile(r'\bdatetime\.utcnow\(\)'), 'datetime.utcnow() naïf'),
]
SCANNED = ['apps', 'refugis_lliures', 'scripts']


def _sources():
    for top in SCANNED:
        for path in (ROOT / top).rglob('*.py'):
            if 'tests' in path.parts or path.name.startswith('test_') or '__pycache__' in path.parts:
                continue
            yield path


def test_la_guarda_cobreix_el_codi_de_reformes():
    """`apps/renovations` (chunk 5) entra a l'escaneig com la resta d'apps."""
    scanned = {p.relative_to(ROOT).as_posix() for p in _sources()}
    assert {'apps/renovations/services.py', 'apps/renovations/selectors.py'} <= scanned


def test_cap_sql_calcula_la_data_d_avui():
    hits = []
    for path in _sources():
        for n, line in enumerate(path.read_text(encoding='utf-8', errors='ignore').splitlines(), 1):
            code = line.split('#', 1)[0]
            for pattern, why in FORBIDDEN:
                if pattern.search(code):
                    hits.append(f'{path.relative_to(ROOT)}:{n}: {why}')
    assert not hits, "Usa get_madrid_today()/timezone.localdate() i passa la data com a paràmetre:\n" + '\n'.join(hits)
