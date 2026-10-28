"""
Aprovar una proposta `delete` (A5, R15, R17, §8.5): en **una** transacció (1) es rebutgen les altres propostes pendents
del refugi, (2) es llegeixen les claus d'R2 dels seus mitjans (tots: ocults, d'altres usuaris, d'experiències, amb
miniatura) amb `system_context()` i s'esborren els fitxers, (3) s'esborra el refugi i la BD cascadeja amb els privilegis
del propietari: serveis, enllaços, mitjans, visites (+ participants), reformes (+ participants, expulsats, enllaç),
experiències, dubtes (+ respostes), preferits, visitats i intents de pujada. Si R2 falla, 500 i es desfà tot (com
`delete_media` i l'esborrat d'experiència, D38). `media_deletion_queue` és del chunk 9.
"""
import logging

import pytest

from apps.accounts.tests.helpers import FAV, VIS, add_list_row
from apps.experiences.tests.helpers import make_exp_media, make_experience
from apps.proposals.tests.helpers import (
    DELETED_REASON, admin_claims, api_get, api_post, approve_url, make_media, make_proposal, make_refuge,
    make_user, proposal_row, refuge_ids, sql)
from apps.renovations.tests.helpers import day, make_renovation
from apps.uploads.tests.helpers import make_intent
from apps.visits.tests.helpers import make_visit
from apps.doubts.tests.helpers import make_answer, make_doubt

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration,
              pytest.mark.real_permissions]

CHILD_COUNTS = {
    'amenities': 'SELECT count(*) FROM refuges.refuge_amenities WHERE refuge_id = %s',
    'links': 'SELECT count(*) FROM refuges.refuge_links WHERE refuge_id = %s',
    'media': 'SELECT count(*) FROM refuges.refuge_media WHERE refuge_id = %s',
    'visits': 'SELECT count(*) FROM activity.refuge_visits WHERE refuge_id = %s',
    'visit_participants': 'SELECT count(*) FROM activity.refuge_visit_participants p JOIN activity.refuge_visits v '
                          'ON v.id = p.visit_id WHERE v.refuge_id = %s',
    'renovations': 'SELECT count(*) FROM activity.renovations WHERE refuge_id = %s',
    'renovation_participants': 'SELECT count(*) FROM activity.renovation_participants p JOIN activity.renovations r '
                               'ON r.id = p.renovation_id WHERE r.refuge_id = %s',
    'renovation_expelled': 'SELECT count(*) FROM activity.renovation_expelled p JOIN activity.renovations r '
                           'ON r.id = p.renovation_id WHERE r.refuge_id = %s',
    'renovation_links': 'SELECT count(*) FROM activity.renovation_group_links p JOIN activity.renovations r '
                        'ON r.id = p.renovation_id WHERE r.refuge_id = %s',
    'experiences': 'SELECT count(*) FROM activity.experiences WHERE refuge_id = %s',
    'doubts': 'SELECT count(*) FROM activity.doubts WHERE refuge_id = %s',
    'answers': 'SELECT count(*) FROM activity.answers a JOIN activity.doubts d ON d.id = a.doubt_id '
               'WHERE d.refuge_id = %s',
    'favourites': 'SELECT count(*) FROM users.user_favourite_refuges WHERE refuge_id = %s',
    'visited': 'SELECT count(*) FROM users.user_visited_refuges WHERE refuge_id = %s',
    'intents': 'SELECT count(*) FROM moderation.upload_intents WHERE refuge_id = %s',
}


def counts(refuge):
    return {name: sql(q, [refuge.pk])[0][0] for name, q in CHILD_COUNTS.items()}


def populate(refuge, tag):
    """Dades de totes les apps migrades penjant del refugi; retorna les claus d'R2 (clau i miniatura)."""
    keys = set()

    def media(creator, n, status='visible', experience=None, thumb=True):
        key, thumb_key = f'refugis-lliures/{refuge.pk}/{tag}-{n}.webp', f'refugis-lliures/{refuge.pk}/{tag}-{n}-t.webp'
        extra = {'thumb_key': thumb_key} if thumb else {}
        if experience:
            make_exp_media(refuge, creator, experience, key=key, status=status, **extra)
        else:
            make_media(refuge, creator, key=key, status=status, minutes=n, **extra)
        keys.update({key, thumb_key} if thumb else {key})

    media('u1', 1)
    media('u2', 2, status='hidden_pending_review')
    media('u3', 3, status='removed', thumb=False)
    exp = make_experience(refuge, 'u2', condition=2)
    media('u1', 4, experience=exp)
    make_experience(refuge, 'u3', condition=1, minutes=1)
    d = make_doubt(refuge, 'u1')
    make_answer(d, 'u2', parent=make_answer(d, 'u3'))
    make_visit(refuge, day(-3), {'u1': 2, 'u2': 1})
    make_renovation(refuge, 'u1', participants=['u2'], expelled=['u3'])
    add_list_row(FAV, 'u1', refuge)
    add_list_row(VIS, 'u2', refuge)
    make_intent('u1', refuge=refuge)
    return keys


@pytest.fixture
def scene(world):
    """Refugi `r` (amb de tot, també enllaços) i un altre `keep` idèntic que ha de sobreviure."""
    r = make_refuge(name='A esborrar', lat=44.0, links=['https://a.test/r1', 'https://a.test/r2'])
    keep = world[1]
    return r, keep, populate(r, 'r'), populate(keep, 'k')


def delete_via_api(client, refuge, **kw):
    pid = make_proposal('delete', refuge=refuge, **kw)
    return pid, api_post(client, approve_url(pid), admin_claims('adm'))


def test_la_cascada_esborra_tot_el_del_refugi_i_res_mes(client, scene):
    r, keep, r_keys, k_keys = scene
    before_keep = counts(keep)
    assert all(v > 0 for k, v in counts(r).items() if k != 'links'), counts(r)
    pid, resp = delete_via_api(client, r)
    assert resp.status_code == 200, resp.content
    assert all(v == 0 for v in counts(r).values()), counts(r)
    assert counts(keep) == before_keep                                        # l'altre refugi, intacte
    assert str(r.pk) not in refuge_ids() and str(keep.pk) in refuge_ids()
    assert sql('SELECT count(*) FROM users.users') == [(5,)]                  # els usuaris no es toquen


def test_esborra_a_r2_totes_les_claus_i_miniatures_del_refugi_i_cap_d_un_altre(client, scene, r2):
    r, keep, r_keys, k_keys = scene
    _, resp = delete_via_api(client, r)
    assert resp.status_code == 200
    assert r2.deleted_keys() == r_keys                                        # ocults, d'altres usuaris i d'experiències inclosos
    assert not r2.deleted_keys() & k_keys


def test_a5_totes_les_fotos_son_d_experiencies_no_falla_a_mitges(client, world, r2):
    """Abans (TECH_DEBT A5) l'aprovació fallava amb 500 després d'haver esborrat dubtes i experiències."""
    r = make_refuge(name='Només experiències', lat=44.0)
    exp = make_experience(r, 'u1', condition=3)
    make_exp_media(r, 'u1', exp, key=f'refugis-lliures/{r.pk}/e.webp', thumb_key=f'refugis-lliures/{r.pk}/e-t.webp')
    make_doubt(r, 'u2')
    _, resp = delete_via_api(client, r)
    assert resp.status_code == 200
    assert r2.deleted_keys() == {f'refugis-lliures/{r.pk}/e.webp', f'refugis-lliures/{r.pk}/e-t.webp'}
    assert all(v == 0 for v in counts(r).values())


def test_sense_mitjans_no_es_crida_r2(client, world, r2):
    _, resp = delete_via_api(client, world[0])
    assert resp.status_code == 200 and r2.deleted_keys() == set()


def test_aprovar_un_update_o_un_create_no_toca_r2(client, world, r2):
    make_media(world[0], 'u1', key='k/a.webp')
    pid = make_proposal('update', refuge=world[0])
    assert api_post(client, approve_url(pid), admin_claims('adm')).status_code == 200
    assert api_post(client, approve_url(make_proposal(minutes=1)), admin_claims('adm')).status_code == 200
    assert r2.deleted_keys() == set()


@pytest.mark.parametrize('how', ['fails', 'raises'])
def test_si_r2_falla_500_i_es_desfa_tot(client, scene, r2, caplog, how):
    r, keep, r_keys, _ = scene
    other = make_proposal('update', refuge=r, creator='u3', minutes=5)
    before = counts(r)
    if how == 'fails':
        r2.fail()
    else:
        r2.delete_file.side_effect = RuntimeError('R2 caigut host=r2.cloudflare bucket=prod')
        r2.delete_files.side_effect = RuntimeError('R2 caigut host=r2.cloudflare bucket=prod')
    pid = make_proposal('delete', refuge=r, minutes=6)
    with caplog.at_level(logging.ERROR):
        resp = api_post(client, approve_url(pid), admin_claims('adm'))
    assert resp.status_code == 500, resp.content
    body = resp.json()
    assert set(body) == {'error', 'error_id'} and 'bucket=prod' not in resp.content.decode()
    assert any(body['error_id'] in rec.getMessage() and rec.exc_info for rec in caplog.records)
    assert counts(r) == before and str(r.pk) in refuge_ids()                  # res no s'ha esborrat a la BD
    assert proposal_row(pid)['status'] == 'pending'
    assert proposal_row(other)['status'] == 'pending'                         # el rebuig automàtic també es desfà
    assert proposal_row(other)['rejection_reason'] is None


def test_es_pot_reintentar_l_aprovacio_quan_r2_torna(client, scene, r2):
    r, *_ = scene
    pid = make_proposal('delete', refuge=r)
    r2.fail()
    assert api_post(client, approve_url(pid), admin_claims('adm')).status_code == 500
    r2.delete_file.return_value = True
    r2.delete_files.side_effect = lambda keys: {'deleted': list(keys), 'failed': []}
    assert api_post(client, approve_url(pid), admin_claims('adm')).status_code == 200
    assert str(r.pk) not in refuge_ids()


# =================================== propostes ===================================

def test_l_historial_de_propostes_sobreviu_amb_refuge_id_null_i_la_foto(client, world):
    r1, r2_ = world
    approved = make_proposal('update', refuge=r1, status='approved', minutes=0)
    rejected = make_proposal('delete', refuge=r1, status='rejected', rejection_reason='no', minutes=1)
    pending_here = make_proposal('update', refuge=r1, creator='u2', minutes=2)
    pending_there = make_proposal('update', refuge=r2_, creator='u2', minutes=3)
    pid, resp = delete_via_api(client, r1, minutes=4)
    assert resp.status_code == 200
    for p in (approved, rejected, pending_here, pid):
        row = proposal_row(p)
        assert row is not None and row['refuge_id'] is None and row['refuge_snapshot']['name'] == 'Refugi A', p
    assert proposal_row(approved)['status'] == 'approved' and proposal_row(rejected)['rejection_reason'] == 'no'
    h = proposal_row(pending_here)
    assert (h['status'], h['rejection_reason'], h['reviewer_uid']) == ('rejected', DELETED_REASON, None)
    assert h['reviewed_at'] is not None
    t = proposal_row(pid)
    assert (t['status'], t['reviewer_uid'], t['rejection_reason']) == ('approved', 'adm', None)
    assert proposal_row(pending_there)['status'] == 'pending' and proposal_row(pending_there)['refuge_id'] == str(r2_.pk)


def test_el_creador_veu_el_rebuig_automatic_a_les_seves_propostes(client, world):
    r1, _ = world
    mine = make_proposal('update', refuge=r1, creator='u2')
    delete_via_api(client, r1, minutes=1)
    [p] = api_get(client, '/api/my-refuges-proposals/', {'uid': 'u2', 'role': 'user'}).json()
    assert p['id'] == mine and p['status'] == 'rejected' and p['rejection_reason'] == DELETED_REASON
    assert p['reviewer_uid'] is None and p['refuge_id'] is None


def test_les_propostes_resoltes_no_es_modifiquen_pel_rebuig_automatic(client, world):
    r1, _ = world
    done = make_proposal('update', refuge=r1, status='approved', reviewer='adm2', minutes=0)
    before = proposal_row(done)
    delete_via_api(client, r1, minutes=1)
    after = proposal_row(done)
    assert {k: v for k, v in after.items() if k != 'refuge_id'} == {k: v for k, v in before.items() if k != 'refuge_id'}


def test_una_proposta_create_aprovada_apunta_al_refugi_i_torna_a_null_si_s_esborra(client, world):
    created = make_proposal(minutes=0)
    assert api_post(client, approve_url(created), admin_claims('adm')).status_code == 200
    new_id = proposal_row(created)['refuge_id']
    assert new_id is not None
    pid = make_proposal('delete', refuge=new_id, snapshot={'id': new_id, 'name': 'Refugi Nou'}, minutes=1)
    assert api_post(client, approve_url(pid), admin_claims('adm')).status_code == 200
    assert proposal_row(created)['refuge_id'] is None and proposal_row(created)['status'] == 'approved'
    assert new_id not in refuge_ids()


def test_el_refugi_esborrat_no_surt_a_cap_lectura_de_l_api(client, scene):
    r, keep, *_ = scene
    delete_via_api(client, r)
    assert api_get(client, f'/api/refuges/{r.pk}/').status_code == 404
    assert api_get(client, f'/api/refuges/{keep.pk}/').status_code == 200
    assert api_get(client, f'/api/refuges/{r.pk}/media/', {'uid': 'u1', 'role': 'user'}).status_code in (200, 404)
    assert api_get(client, f'/api/doubts/?refuge_id={r.pk}', {'uid': 'u1', 'role': 'user'}).status_code == 404
