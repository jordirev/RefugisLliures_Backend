"""
Revisió SQL del chunk 5: carreres amb l'esborrat del pare (FK diferides → 404 i no un 500 al `COMMIT` d'`ATOMIC_REQUESTS`)
i bloqueigs de membres (unir-se / expulsar).

Les carreres es simulen de manera determinista: s'intercepta una lectura del servei i, just després, un «altre client»
esborra el pare (SQL pla com a sistema). Sense `SET CONSTRAINTS ... IMMEDIATE` l'`IntegrityError` no sortiria del servei.
"""
import uuid
from unittest.mock import patch

import pytest
from django.db import connection

from apps.core.rls import rls_context
from apps.renovations import selectors, services
from apps.renovations.tests.helpers import (
    LINK, as_owner, count_renovations, day, expelled_of, make_renovation, participants_of, sql)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.integration, pytest.mark.real_permissions]


def _after(real, action):
    """Embolcall que executa `real` i després `action()` (l'«altre client» actua entre la lectura i l'escriptura)."""
    def wrapper(*args, **kwargs):
        result = real(*args, **kwargs)
        action()
        return result
    return wrapper


def _advisory_locks():
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' AND pid = pg_backend_pid()")
        return cur.fetchone()[0]


def test_unir_se_a_una_reforma_esborrada_entremig_es_404_no_500(world):
    rid = make_renovation(world.refuge, 'u1')
    real = services._creator_of
    with patch.object(services, '_creator_of',
                      _after(real, lambda: sql('DELETE FROM activity.renovations WHERE id = %s', [rid]))):
        with rls_context(uid='u2'):
            with pytest.raises(services.RenovationNotFound):
                services.add_participant(rid, 'u2')
    assert participants_of(rid) == []


def test_crear_en_un_refugi_esborrat_entremig_es_404_no_500(world):
    def drop_refuge():
        with as_owner():
            with connection.cursor() as cur:
                cur.execute('DELETE FROM refuges.refuges WHERE id = %s', [world.refuge.pk])
    real = selectors.find_overlapping
    with patch.object(selectors, 'find_overlapping', _after(real, drop_refuge)):
        with rls_context(uid='u1'):
            with pytest.raises(services.RefugeNotFound):
                services.create_renovation('u1', refuge_id=world.refuge.pk, ini_date=day(5), fin_date=day(6),
                                           description='x', group_link=LINK)
    assert count_renovations() == 0


def test_expulsar_d_una_reforma_esborrada_entremig_es_404(world):
    rid = make_renovation(world.refuge, 'u1', participants=['u2'])
    real = services._creator_of
    with patch.object(services, '_creator_of',
                      _after(real, lambda: sql('DELETE FROM activity.renovations WHERE id = %s', [rid]))):
        with rls_context(uid='u1'):
            with pytest.raises(services.RenovationNotFound):
                services.remove_participant(rid, 'u2', 'u1')
    assert expelled_of(rid) == []


def test_unir_se_i_expulsar_agafen_el_bloqueig_per_reforma_i_usuari(world):
    """Serialitza «unir-se» i «expulsar» el mateix usuari (si no, podria quedar alhora a participants i expulsats)."""
    rid = make_renovation(world.refuge, 'u1', participants=['u3'])
    assert _advisory_locks() == 0
    with rls_context(uid='u2'):
        services.add_participant(rid, 'u2')
    assert _advisory_locks() == 1
    with rls_context(uid='u1'):
        services.remove_participant(rid, 'u3', 'u1')
    assert _advisory_locks() == 2                          # un altre (reforma, usuari)
    assert participants_of(rid) == ['u2'] and expelled_of(rid) == ['u3']


def test_sortir_un_mateix_no_agafa_bloqueig(world):
    rid = make_renovation(world.refuge, 'u1', participants=['u2'])
    with rls_context(uid='u2'):
        services.remove_participant(rid, 'u2', 'u2')
    assert _advisory_locks() == 0


def test_una_fk_diferida_no_queda_immediata_per_al_constraint_trigger(world):
    """`SET CONSTRAINTS` només toca la FK nomenada: el *constraint trigger* de l'enllaç continua diferit."""
    with rls_context(uid='u1'):
        r = services.create_renovation('u1', refuge_id=world.refuge.pk, ini_date=day(5), fin_date=day(6),
                                       description='x', group_link=LINK)
        with connection.cursor() as cur:
            cur.execute("SELECT tgdeferrable, tginitdeferred FROM pg_trigger WHERE tgname = 'renovations_requires_link'")
            assert cur.fetchone() == (True, True)          # definició intacta
    assert uuid.UUID(str(r.pk))
