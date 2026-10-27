"""
Quota d'intents de pujada pendents (decisió del PO, 27/10): com a molt `MAX_PENDING_INTENTS` (40) intents `pending` sense
caducar per usuari, comptant els que es demanen (un per fitxer). Si se supera: 429 `too_many_pending_uploads` i no es
crea res ni se signa cap URL. Els `confirmed`, els `failed`, els caducats i els d'altres usuaris no compten.
"""
from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.uploads import services
from apps.uploads.tests.helpers import (
    INTENTS, api_post, file_spec, intent_body, intent_ids, make_intent, user_claims)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration,
              pytest.mark.real_permissions]

LIMIT = services.MAX_PENDING_INTENTS


def post(client, refuge, n, uid='u1'):
    return api_post(client, INTENTS, user_claims(uid), intent_body('refuge', refuge, files=[file_spec()] * n))


def pending(uid, refuge, n, **kwargs):
    for _ in range(n):
        make_intent(uid, refuge=refuge, **kwargs)


def test_el_limit_es_40():
    assert LIMIT == 40


def test_fins_al_limit_201(client, world, r2store):
    pending('u1', world[0], LIMIT - 1)
    assert post(client, world[0], 1).status_code == 201
    assert len(intent_ids('u1')) == LIMIT


def test_superar_el_limit_429_amb_codi_i_res_creat(client, world, r2store):
    pending('u1', world[0], LIMIT)
    before = sorted(intent_ids('u1'))
    resp = post(client, world[0], 1)
    assert resp.status_code == 429
    assert resp.json()['code'] == 'too_many_pending_uploads' and resp.json()['message']
    assert sorted(intent_ids('u1')) == before
    r2store.client.generate_presigned_url.assert_not_called()


def test_compta_els_fitxers_de_la_peticio(client, world, r2store):
    pending('u1', world[0], LIMIT - 5)
    assert post(client, world[0], 10).status_code == 429
    assert post(client, world[0], 5).status_code == 201


def test_confirmats_fallits_caducats_i_d_altres_no_compten(client, world, r2store):
    r = world[0]
    pending('u1', r, LIMIT, status='confirmed', result_key='refugis-lliures/x.jpg')
    pending('u1', r, LIMIT, status='failed', failure_reason='missing_object')
    pending('u1', r, LIMIT, created_ago=timedelta(days=2), expires_in=timedelta(days=-1))
    pending('u2', r, LIMIT)
    assert post(client, r, 10).status_code == 201


def test_la_quota_es_comprova_amb_un_bloqueig_per_usuari(client, world, r2store):
    """Dues peticions simultànies del mateix usuari no poden comptar abans d'inserir: bloqueig assessor per uid."""
    with CaptureQueriesContext(connection) as ctx:
        assert post(client, world[0], 1).status_code == 201
    assert any('pg_advisory_xact_lock' in q['sql'] for q in ctx.captured_queries)
