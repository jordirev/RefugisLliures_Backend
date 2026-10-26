"""
Revisió SQL del chunk 6: carreres amb les FK diferides. Un pare (refugi, dubte o resposta) esborrat entre la lectura del
service i l'`INSERT` no pot acabar en un 500 al `COMMIT`: el service ho converteix en 404 a l'acte (`_insert_checked`).
Es simula amb un pare «vell» (lectura feta abans de l'esborrat), sense necessitat de dos fils.
"""
from unittest.mock import patch

import pytest

from apps.core.rls import rls_context
from apps.doubts.tests.helpers import as_owner, answer_ids, doubt_ids, make_answer, make_doubt, sql

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.integration, pytest.mark.real_permissions]


def test_resposta_a_un_pare_esborrat_alhora_es_404_i_no_deixa_fila(services, selectors, world):
    d = make_doubt(world[0], 'u1')
    parent = make_answer(d, 'u2')
    stale = selectors.get_answer(d, parent)                       # lectura del service...
    sql('DELETE FROM activity.answers WHERE id = %s', [parent])   # ...i l'esborrat concurrent
    with patch.object(selectors, 'get_answer', return_value=stale):
        with rls_context('u3'), pytest.raises(services.AnswerNotFound):
            services.create_answer(doubt_id=d, creator_uid='u3', message='x', parent_answer_id=parent)
    assert answer_ids(d) == []


def test_resposta_a_un_dubte_esborrat_alhora_es_404(services, selectors, world):
    d = make_doubt(world[0], 'u1')
    stale = selectors.get_doubt(d)
    sql('DELETE FROM activity.doubts WHERE id = %s', [d])
    with patch.object(selectors, 'get_doubt', return_value=stale):
        with rls_context('u3'), pytest.raises(services.DoubtNotFound):
            services.create_answer(doubt_id=d, creator_uid='u3', message='x')
    assert answer_ids() == []


def test_dubte_en_un_refugi_esborrat_alhora_es_404(services, world):
    refuge = world[0]
    with patch('apps.doubts.services.refuge_selectors.refuge_exists', return_value=True):
        with as_owner():
            sql('DELETE FROM refuges.refuges WHERE id = %s', [refuge.pk])
        with rls_context('u1'), pytest.raises(services.RefugeNotFound):
            services.create_doubt(refuge_id=refuge.pk, creator_uid='u1', message='x')
    assert doubt_ids() == []


def test_altres_violacions_d_fk_no_es_tradueixen(services, world):
    """L'usuari creador inexistent no és un «no trobat»: l'error es propaga (500 amb `error_id` a la vista)."""
    from django.db import IntegrityError
    with rls_context('fantasma'), pytest.raises(IntegrityError):
        services.create_doubt(refuge_id=world[0].pk, creator_uid='fantasma', message='x')
