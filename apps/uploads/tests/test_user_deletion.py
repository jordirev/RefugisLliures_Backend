"""
Esborrat d'usuari / experiència / refugi i intents de pujada (chunk 7; §8.4, §8.5): les FK `ON DELETE CASCADE` de
`upload_intents` (`user_uid`, `refuge_id`, `experience_id`) esborren els intents; el fitxer a `quarantine/` el tanca el
lifecycle d'R2 d'1 dia (no es toca des d'aquí). Els mitjans ja publicats segueixen el seu propi camí (D22).
"""
from unittest.mock import patch

import pytest

from apps.experiences.tests.helpers import make_experience
from apps.uploads.tests.helpers import (
    api_delete, intent_ids, make_intent, refuge_media_rows, user_claims)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration,
              pytest.mark.real_permissions]


@pytest.fixture(autouse=True)
def no_firestore_steps():
    with patch('apps.accounts.services._firestore_steps', return_value=[]):
        yield


def test_delete_user_cascadeja_els_seus_intents_de_qualsevol_estat(client, world, r2store):
    r = world[0]
    e = make_experience(r, 'u1')
    mine = [make_intent('u1', 'avatar'), make_intent('u1', 'refuge', refuge=r),
            make_intent('u1', 'experience', refuge=r, experience_id=e),
            make_intent('u1', 'avatar', status='confirmed', result_key='k/a.webp'),
            make_intent('u1', 'avatar', status='failed', failure_reason='too_large')]
    keep = make_intent('u2', 'refuge', refuge=r)
    r2store.store[f'quarantine/{mine[0]}'] = b'x'
    resp = api_delete(client, '/api/users/u1/', user_claims('u1'))
    assert resp.status_code == 204, resp.content
    assert intent_ids() == [keep]
    assert f'quarantine/{mine[0]}' in r2store.store                      # el lifecycle de R2 l'esborrarà (1 dia)


def test_delete_user_desfet_si_firebase_falla_conserva_els_intents(client, world, firebase_accounts):
    i = make_intent('u1', 'avatar')
    firebase_accounts.delete_user.side_effect = RuntimeError('firebase caigut')
    assert api_delete(client, '/api/users/u1/', user_claims('u1')).status_code == 500
    assert intent_ids() == [i]


def test_delete_experiencia_cascadeja_nomes_els_intents_d_aquella_experiencia(client, world, r2store):
    r = world[0]
    e1, e2 = make_experience(r, 'u1'), make_experience(r, 'u1', minutes=1)
    make_intent('u1', 'experience', refuge=r, experience_id=e1)
    keep = [make_intent('u1', 'experience', refuge=r, experience_id=e2), make_intent('u1', 'refuge', refuge=r),
            make_intent('u1', 'avatar')]
    assert api_delete(client, f'/api/experiences/{e1}/', user_claims('u1')).status_code == 200
    assert sorted(intent_ids()) == sorted(keep)


def test_un_intent_pendent_no_publica_res_al_esborrar_l_usuari(client, world):
    make_intent('u1', 'avatar')
    api_delete(client, '/api/users/u1/', user_claims('u1'))
    assert refuge_media_rows() == []
