"""
Conflictes en aprovar amb codi estable (el frontend no ha de dependre del text de l'error):
- un enllaç del payload ja és d'un altre refugi → 409 `link_already_used`;
- el refugi de la proposta ja no existeix (cursa improbable) → 409 `refuge_not_found`, no un 500;
- la proposta ja revisada continua sent 409 sense `code` (contracte d'abans).
"""
from unittest.mock import patch

import pytest

from apps.proposals import services
from apps.proposals.tests.helpers import admin_claims, api_post, approve_url

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration,
              pytest.mark.real_permissions]

ANY_ID = '00000000-0000-7000-8000-000000000001'


def approve_raising(client, exc):
    with patch('apps.proposals.services.approve_proposal', side_effect=exc):
        return api_post(client, approve_url(ANY_ID), admin_claims('adm'), {})


def test_enllac_d_un_altre_refugi_409_amb_codi(client, world):
    resp = approve_raising(client, services.LinkAlreadyUsed())
    assert resp.status_code == 409
    body = resp.json()
    assert body['code'] == 'link_already_used' and body['message']
    assert body['error'] == 'A link of the proposal already belongs to another refuge'


def test_refugi_desaparegut_409_amb_codi_i_no_500(client, world):
    resp = approve_raising(client, services.RefugeNotFound('Refuge does not exists'))
    assert resp.status_code == 409
    assert resp.json()['code'] == 'refuge_not_found' and 'error_id' not in resp.json()


def test_ja_revisada_continua_igual(client, world):
    exc = services.ProposalAlreadyReviewed('approved')
    exc.status = 'approved'
    resp = approve_raising(client, exc)
    assert resp.status_code == 409 and resp.json() == {'error': 'Proposal is already approved'}
