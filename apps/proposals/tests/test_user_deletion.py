"""
Esborrat d'usuari i propostes (§8.2, §8.5; chunk 8): les propostes es **conserven** (historial de refugis, interès
legítim) amb `creator_uid`/`reviewer_uid` a `NULL` per la FK `SET NULL` (l'API emet `'unknown'`); l'esborrat no toca Firestore (D42).

Decisió del PO (27/10, canvi respecte de §8): el `comment` (text lliure, pot dur dades personals) passa a `NULL` per a
les propostes de l'usuari esborrat; la resta de la proposta (payload, foto, estat) es conserva.
"""
import pytest

from apps.proposals.tests.helpers import (
    PROPOSALS, UNKNOWN, admin_claims, api_delete, api_get, api_post, approve_url, count_proposals,
    make_proposal, proposal_row, refuge_ids, user_claims)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration,
              pytest.mark.real_permissions]


def test_delete_user_no_toca_firestore_ni_el_controller_de_propostes(client, world):
    """Sense cap mock: el conftest arrel prohibeix Firestore real, de manera que cap pas ha de quedar-hi."""
    assert api_delete(client, '/api/users/u1/', user_claims('u1')).status_code == 204


def test_delete_user_conserva_les_propostes_anonimitzades(client, world):
    r1, _ = world
    pending = make_proposal(creator='u1', comment='la meva')
    update = make_proposal('update', creator='u1', refuge=r1, minutes=1)
    approved = make_proposal(creator='u1', status='approved', reviewer='adm', minutes=2)
    rejected = make_proposal(creator='u1', status='rejected', reviewer='adm', rejection_reason='no', minutes=3)
    other = make_proposal(creator='u2', comment="de l'altre", minutes=4)
    assert api_delete(client, '/api/users/u1/', user_claims('u1')).status_code == 204
    assert count_proposals() == 5
    for pid in (pending, update, approved, rejected):
        row = proposal_row(pid)
        assert row['creator_uid'] is None, pid
    assert proposal_row(pending)['payload'] is not None
    for pid in (pending, update, approved, rejected):
        assert proposal_row(pid)['comment'] is None, pid                       # RGPD: el comentari s'esborra
    assert proposal_row(other)['comment'] == "de l'altre"
    assert proposal_row(update)['refuge_id'] == str(r1.pk)
    assert proposal_row(rejected)['rejection_reason'] == 'no' and proposal_row(approved)['reviewer_uid'] == 'adm'
    assert proposal_row(other)['creator_uid'] == 'u2'


def test_l_api_emet_unknown_per_al_creador_esborrat(client, world):
    pid = make_proposal(creator='u1')
    api_delete(client, '/api/users/u1/', user_claims('u1'))
    [p] = api_get(client, PROPOSALS, admin_claims('adm')).json()
    assert p['id'] == pid and p['creator_uid'] == UNKNOWN and p['reviewer_uid'] is None


def test_l_admin_esborrat_deixa_reviewer_uid_a_null_i_l_api_el_dona_com_a_null(client, world):
    pid = make_proposal(creator='u1', status='approved', reviewer='adm2')
    assert api_delete(client, '/api/users/adm2/', user_claims('adm2')).status_code == 204
    row = proposal_row(pid)
    assert row['reviewer_uid'] is None and row['reviewed_at'] is not None
    [p] = api_get(client, f'{PROPOSALS}?status=approved', admin_claims('adm')).json()
    assert p['reviewer_uid'] is None and p['creator_uid'] == 'u1'


def test_una_proposta_pendent_d_un_usuari_esborrat_es_pot_aprovar_i_rebutjar(client, world):
    a, b = make_proposal(creator='u1', minutes=0), make_proposal(creator='u1', minutes=1)
    api_delete(client, '/api/users/u1/', user_claims('u1'))
    n = len(refuge_ids())
    assert api_post(client, approve_url(a), admin_claims('adm')).status_code == 200
    assert api_post(client, f'{PROPOSALS}{b}/reject/', admin_claims('adm'), {'reason': 'x'}).status_code == 200
    assert len(refuge_ids()) == n + 1 and proposal_row(a)['creator_uid'] is None


def test_si_firebase_falla_500_i_les_propostes_ja_estan_anonimitzades(client, world, firebase_accounts):
    """D42: Firebase després del commit; l'anonimització ja és ferma."""
    pid = make_proposal(creator='u1')
    firebase_accounts.delete_user.side_effect = RuntimeError('firebase caigut')
    assert api_delete(client, '/api/users/u1/', user_claims('u1')).status_code == 500
    assert proposal_row(pid)['creator_uid'] is None


def test_delete_user_esborra_el_comentari_de_totes_les_seves_propostes_i_l_api_el_dona_com_a_null(client, world):
    pid = make_proposal(creator='u1', comment='el meu telèfon és 600000000')
    api_delete(client, '/api/users/u1/', user_claims('u1'))
    [p] = api_get(client, PROPOSALS, admin_claims('adm')).json()
    assert p['id'] == pid and p['comment'] is None and p['creator_uid'] == UNKNOWN


def test_delete_user_no_toca_el_comentari_de_les_propostes_que_ha_revisat(client, world):
    pid = make_proposal(creator='u1', comment='del creador', status='approved', reviewer='adm2')
    api_delete(client, '/api/users/adm2/', user_claims('adm2'))
    assert proposal_row(pid)['comment'] == 'del creador'


def test_si_firebase_falla_el_comentari_ja_s_ha_esborrat(client, world, firebase_accounts):
    pid = make_proposal(creator='u1', comment='hola')
    firebase_accounts.delete_user.side_effect = RuntimeError('firebase caigut')
    assert api_delete(client, '/api/users/u1/', user_claims('u1')).status_code == 500
    assert proposal_row(pid)['comment'] is None
