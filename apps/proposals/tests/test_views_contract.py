"""
Contracte HTTP de les propostes de refugi (chunk 8): vistes a `apps/proposals/views.py`, mateixes URL i JSON d'avui.

- `POST /api/refuges-proposals/` (autenticat, no bloquejat, edat confirmada) -> 201 amb la proposta;
  400 `{error: 'Invalid data', details}`; 400 `{error: 'Refuge does not exists'}` (update/delete d'un refugi inexistent).
- `GET /api/refuges-proposals/?status=&refuge-id=` (admin) -> 200 `[Proposta]` per `created_at DESC`;
  400 `{error: "Invalid status filter: x. Must be 'pending', 'approved', or 'rejected'"}`.
- `GET /api/my-refuges-proposals/?status=` -> les pròpies (també per a un admin).
- `POST .../{id}/approve/` -> 200 `{message: 'Proposal approved successfully'}`; 404 `{error: 'Proposal not found'}`;
  409 `{error: 'Proposal is already approved|rejected'}`.
- `POST .../{id}/reject/` `{reason?}` -> 200 `{message: 'Proposal rejected successfully'}`; mateixos 404/409.
- Proposta = `{id, refuge_id, refuge_snapshot, action, payload, comment, status, creator_uid, created_at, reviewer_uid,
  reviewed_at, rejection_reason}`; `creator_uid` `NULL` -> `'unknown'`; dates ISO amb el desplaçament de Madrid.
"""
import re
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from apps.proposals.tests.helpers import (
    DELETED_REASON, MINE, PROPOSAL_KEYS, PROPOSALS, REFUGES, SNAPSHOT_KEYS, UNKNOWN, admin_claims, api_get, api_post,
    approve_url, count_proposals, create_body, delete_body, make_proposal, make_refuge, new_payload, new_refuge_id,
    proposal_ids, proposal_row, refuge_ids, refuge_state, reject_url, sql, update_body, user_claims, uuid7_ok)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration,
              pytest.mark.real_permissions]

INVALID_STATUS = "Invalid status filter: {}. Must be 'pending', 'approved', or 'rejected'"
ISO_MADRID = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?\+0[12]:00$')


@pytest.fixture
def refuge(world):
    return world[0]


@pytest.fixture
def colomers():
    return make_refuge(name='Refugi de Colomers', lat=42.6321, long=0.9984, surname='Colomers', altitude=2135,
                       places=12, type='fermée', description='Un refugi', region='Pirineus', departement='Lleida',
                       modified_at='2024-05-17', condition=1.5, num_contributed_conditions=3,
                       amenities={'eau': True, 'poele': True, 'lits': True},
                       links=['https://a.test/1', 'https://a.test/2'])


# =================================== POST: crear ===================================

def test_post_create_201_forma_exacta(client, world):
    body = create_body()
    r = api_post(client, PROPOSALS, user_claims('u1'), body)
    assert r.status_code == 201, r.content
    data = r.json()
    assert set(data) == PROPOSAL_KEYS
    assert uuid7_ok(data['id']) and data['action'] == 'create' and data['status'] == 'pending'
    assert data['refuge_id'] is None and data['refuge_snapshot'] is None
    assert data['comment'] == body['comment'] and data['creator_uid'] == 'u1'
    assert (data['reviewer_uid'], data['reviewed_at'], data['rejection_reason']) == (None, None, None)
    p = data['payload']
    assert p['name'] == 'Refugi Nou' and p['coord'] == {'long': 1.234, 'lat': 42.567}
    assert (p['altitude'], p['places'], p['type']) == (1800, 15, 'non gardé')
    assert (p['info_comp']['cheminee'], p['info_comp']['eau'], p['info_comp']['lits']) == (1, 1, 1)
    assert ISO_MADRID.match(data['created_at']), data['created_at']
    row = proposal_row(data['id'])
    assert row['creator_uid'] == 'u1' and row['status'] == 'pending' and row['payload'] == p


def test_post_created_at_es_el_de_la_bd_amb_desplacament_de_madrid(client, world):
    data = api_post(client, PROPOSALS, user_claims('u1'), create_body()).json()
    created = datetime.fromisoformat(data['created_at'])
    assert created == proposal_row(data['id'])['created_at']
    assert created.utcoffset() == created.astimezone(ZoneInfo('Europe/Madrid')).utcoffset()


def test_post_update_201_amb_la_foto_igual_que_el_detall_de_l_api(client, colomers, world):
    r = api_post(client, PROPOSALS, user_claims('u1'), update_body(colomers, {'places': 45}))
    assert r.status_code == 201, r.content
    data = r.json()
    assert data['refuge_id'] == str(colomers.pk) and data['payload'] == {'places': 45} and data['action'] == 'update'
    detail = api_get(client, f'{REFUGES}{colomers.pk}/', user_claims('u1')).json()
    for extra in ('visitors', 'images_metadata'):
        detail.pop(extra, None)
    assert set(data['refuge_snapshot']) == SNAPSHOT_KEYS and data['refuge_snapshot'] == detail
    assert 'remarque' not in data['refuge_snapshot'] and 'surname' not in data['refuge_snapshot']


def test_post_update_nomes_desa_els_camps_enviats_i_els_null(client, refuge):
    r = api_post(client, PROPOSALS, user_claims('u1'), update_body(refuge, {'altitude': None, 'places': 3}))
    assert r.status_code == 201 and r.json()['payload'] == {'altitude': None, 'places': 3}


def test_post_delete_201_sense_payload(client, refuge):
    r = api_post(client, PROPOSALS, user_claims('u1'), delete_body(refuge))
    assert r.status_code == 201, r.content
    data = r.json()
    assert data['payload'] is None and data['action'] == 'delete' and data['refuge_id'] == str(refuge.pk)
    assert data['refuge_snapshot']['id'] == str(refuge.pk) and data['comment'] == 'Destruït per una allau'


def test_post_sense_comentari_es_null(client, world):
    body = create_body()
    body.pop('comment')
    assert api_post(client, PROPOSALS, user_claims('u1'), body).json()['comment'] is None


def test_post_el_creador_es_sempre_el_del_token(client, world):
    body = {**create_body(), 'creator_uid': 'u2', 'status': 'approved', 'reviewer_uid': 'adm', 'id': str(uuid.uuid4())}
    data = api_post(client, PROPOSALS, user_claims('u1'), body).json()
    assert (data['creator_uid'], data['status'], data['reviewer_uid']) == ('u1', 'pending', None)
    assert proposal_ids() == {data['id']}


def test_post_un_admin_tambe_crea_propostes_com_a_creador(client, world):
    data = api_post(client, PROPOSALS, admin_claims('adm'), create_body()).json()
    assert data['creator_uid'] == 'adm' and data['status'] == 'pending'


@pytest.mark.parametrize('body,key', [
    ({}, 'action'),
    ({'action': 'merge'}, 'action'),
    ({'action': 'create'}, 'payload'),
    ({'action': 'create', 'payload': {'coord': {'lat': 1, 'long': 1}}}, 'payload'),
    ({'action': 'create', 'payload': {'name': 'x'}}, 'payload'),
    ({'action': 'create', 'refuge_id': 'x', 'payload': {'name': 'x', 'coord': {'lat': 1, 'long': 1}}}, 'refuge_id'),
    ({'action': 'update', 'payload': {'places': 1}}, 'refuge_id'),
    ({'action': 'delete'}, 'refuge_id'),
])
def test_post_dades_invalides_400(client, world, body, key):
    r = api_post(client, PROPOSALS, user_claims('u1'), body)
    assert r.status_code == 400, r.content
    j = r.json()
    assert j['error'] == 'Invalid data' and key in j['details']
    assert count_proposals() == 0


def test_post_camps_no_permesos_400_amb_el_missatge_d_avui(client, world):
    r = api_post(client, PROPOSALS, user_claims('u1'), create_body(remarque='x'))
    assert r.status_code == 400
    assert r.json()['details']['payload'][0].startswith('Camps no permesos al payload: remarque. Camps permesos: ')


def test_post_valors_fora_de_rang_400(client, world):
    for payload in ({'altitude': 9000}, {'places': -1}, {'condition': 4}, {'type': 'inventat'},
                    {'links': ['no-url']}, {'info_comp': {'eau': 2}}, {'name': 'x' * 256}):
        r = api_post(client, PROPOSALS, user_claims('u1'), create_body(**payload))
        assert r.status_code == 400 and 'payload' in r.json()['details'], payload
    assert count_proposals() == 0


def test_post_comment_massa_llarg_400_i_4000_ok(client, world):
    assert api_post(client, PROPOSALS, user_claims('u1'), create_body(comment='x' * 4001)).status_code == 400
    assert api_post(client, PROPOSALS, user_claims('u1'), create_body(comment='x' * 4000)).status_code == 201


@pytest.mark.parametrize('action', ['update', 'delete'])
@pytest.mark.parametrize('rid', [str(uuid.uuid4()), 'no-es-uuid', "1'; DROP TABLE refuges.refuges;--"])
def test_post_refugi_inexistent_400_refuge_does_not_exists(client, world, action, rid):
    body = {'action': action, 'refuge_id': rid, 'comment': 'x'}
    if action == 'update':
        body['payload'] = {'places': 1}
    r = api_post(client, PROPOSALS, user_claims('u1'), body)
    assert r.status_code == 400 and r.json() == {'error': 'Refuge does not exists'}
    assert count_proposals() == 0


def test_post_create_d_un_refugi_proper_amb_el_mateix_nom_es_409_vegeu_test_duplicates(client, refuge):
    r = api_post(client, PROPOSALS, user_claims('u1'), create_body(name='Refugi A', coord={'lat': 42.5, 'long': 1.5}))
    assert r.status_code == 409 and r.json()['error'] == 'possible_duplicates'
    assert count_proposals() == 0


# =================================== GET: llista d'admin ===================================

def test_get_admin_llista_buida(client, world):
    r = api_get(client, PROPOSALS, admin_claims('adm'))
    assert r.status_code == 200 and r.json() == []


def test_get_admin_forma_ordre_i_unknown(client, world):
    r1, _ = world
    old = make_proposal(creator='u1', comment='antiga', minutes=0)
    mid = make_proposal('update', creator='u2', refuge=r1, minutes=10, payload={'places': 3})
    anon = make_proposal('delete', creator=None, refuge=r1, minutes=20)
    done = make_proposal(creator='u3', status='approved', reviewer='adm', minutes=30)
    r = api_get(client, PROPOSALS, admin_claims('adm'))
    assert r.status_code == 200
    body = r.json()
    assert [p['id'] for p in body] == [done, anon, mid, old]                    # created_at DESC
    assert all(set(p) == PROPOSAL_KEYS for p in body)
    by = {p['id']: p for p in body}
    assert by[anon]['creator_uid'] == UNKNOWN and by[old]['creator_uid'] == 'u1'
    assert by[done]['reviewer_uid'] == 'adm' and ISO_MADRID.match(by[done]['reviewed_at'])
    assert by[old]['reviewed_at'] is None and by[old]['comment'] == 'antiga'
    assert by[mid]['refuge_id'] == str(r1.pk) and by[mid]['payload'] == {'places': 3}
    assert by[anon]['payload'] is None and by[anon]['refuge_snapshot']['id'] == str(r1.pk)
    assert by[old]['created_at'] == '2025-01-01T11:00:00+01:00'


def test_get_admin_filtres_status_i_refuge_id(client, world):
    r1, r2 = world
    a = make_proposal(creator='u1', minutes=0)
    b = make_proposal('update', refuge=r1, minutes=1)
    c = make_proposal('delete', refuge=r2, minutes=2, status='rejected', rejection_reason='no')
    d = make_proposal(minutes=3, status='approved')

    def ids(query):
        r = api_get(client, f'{PROPOSALS}{query}', admin_claims('adm'))
        assert r.status_code == 200, r.content
        return [p['id'] for p in r.json()]

    assert ids('?status=pending') == [b, a]
    assert ids('?status=rejected') == [c]
    assert ids('?status=approved') == [d]
    assert ids(f'?refuge-id={r1.pk}') == [b]
    assert ids(f'?refuge-id={r2.pk}&status=rejected') == [c]
    assert ids(f'?refuge-id={r2.pk}&status=pending') == []
    assert ids('?refuge-id=no-es-uuid') == []
    assert ids(f'?refuge-id={uuid.uuid4()}') == []
    assert ids('?status=') == [d, c, b, a]


@pytest.mark.parametrize('bad', ['done', 'PENDING', 'approved;', "x' OR '1'='1"])
def test_get_admin_status_invalid_400(client, world, bad):
    r = api_get(client, f'{PROPOSALS}?status={bad}', admin_claims('adm'))
    assert r.status_code == 400
    assert r.json() == {'error': INVALID_STATUS.format(bad)}


def test_get_admin_la_proposta_aprovada_porta_el_refugi_creat(client, world):
    pid = make_proposal()
    assert api_post(client, approve_url(pid), admin_claims('adm')).status_code == 200
    [p] = api_get(client, f'{PROPOSALS}?status=approved', admin_claims('adm')).json()
    assert p['refuge_id'] == new_refuge_id(pid) and p['reviewer_uid'] == 'adm'


# =================================== GET: les meves ===================================

def test_my_nomes_retorna_les_pròpies_per_created_at_desc(client, world):
    a = make_proposal(creator='u1', minutes=0)
    b = make_proposal(creator='u1', minutes=5, status='rejected', rejection_reason='no')
    make_proposal(creator='u2', minutes=2)
    r = api_get(client, MINE, user_claims('u1'))
    assert r.status_code == 200
    assert [p['id'] for p in r.json()] == [b, a] and all(set(p) == PROPOSAL_KEYS for p in r.json())
    assert r.json()[0]['rejection_reason'] == 'no' and r.json()[0]['creator_uid'] == 'u1'
    assert api_get(client, MINE, user_claims('u3')).json() == []


def test_my_filtre_per_status_i_status_invalid(client, world):
    a = make_proposal(creator='u1', minutes=0)
    b = make_proposal(creator='u1', minutes=1, status='approved')
    assert [p['id'] for p in api_get(client, f'{MINE}?status=pending', user_claims('u1')).json()] == [a]
    assert [p['id'] for p in api_get(client, f'{MINE}?status=approved', user_claims('u1')).json()] == [b]
    r = api_get(client, f'{MINE}?status=nope', user_claims('u1'))
    assert r.status_code == 400 and r.json() == {'error': INVALID_STATUS.format('nope')}


def test_my_un_admin_nomes_veu_les_seves_no_les_de_tothom(client, world):
    mine = make_proposal(creator='adm')
    make_proposal(creator='u1', minutes=1)
    assert [p['id'] for p in api_get(client, MINE, admin_claims('adm')).json()] == [mine]


def test_my_l_historial_sobreviu_a_l_esborrat_del_refugi_amb_refuge_id_null(client, refuge):
    make_proposal('update', creator='u1', refuge=refuge, status='approved')
    sql('DELETE FROM refuges.refuges WHERE id = %s', [refuge.pk])
    [p] = api_get(client, MINE, user_claims('u1')).json()
    assert p['refuge_id'] is None and p['refuge_snapshot']['name'] == 'Refugi A'


# =================================== approve ===================================

def test_approve_create_200_i_el_refugi_apareix_a_l_api(client, world):
    pid = make_proposal(payload=new_payload(name='Cabana Nova', links=['https://a.test/nova']), creator='u1')
    r = api_post(client, approve_url(pid), admin_claims('adm'))
    assert r.status_code == 200 and r.json() == {'message': 'Proposal approved successfully'}
    rid = new_refuge_id(pid)
    detail = api_get(client, f'{REFUGES}{rid}/').json()
    assert detail['name'] == 'Cabana Nova' and uuid7_ok(detail['id']) and detail['links'] == ['https://a.test/nova']
    names = [x['name'] for x in api_get(client, f'{REFUGES}?name=Cabana', user_claims('u1')).json()['results']]
    assert names == ['Cabana Nova']
    assert any(x['id'] == rid for x in api_get(client, REFUGES).json()['results'])        # llista sense filtres


def test_approve_update_200_es_veu_al_detall(client, colomers, world):
    pid = make_proposal('update', refuge=colomers, payload={'places': 45, 'condition': 3})
    assert api_post(client, approve_url(pid), admin_claims('adm')).status_code == 200
    d = api_get(client, f'{REFUGES}{colomers.pk}/').json()
    assert d['places'] == 45 and d['condition'] == 3 and d['modified_at'] == '2025-01-01'
    assert d['name'] == 'Refugi de Colomers'


def test_approve_delete_200_el_refugi_desapareix_de_l_api(client, refuge, world):
    pid = make_proposal('delete', refuge=refuge)
    assert api_post(client, approve_url(pid), admin_claims('adm')).status_code == 200
    assert api_get(client, f'{REFUGES}{refuge.pk}/').status_code == 404
    assert str(refuge.pk) not in {x['id'] for x in api_get(client, REFUGES).json()['results']}


def test_approve_404_i_409(client, world):
    r = api_post(client, approve_url(uuid.uuid4()), admin_claims('adm'))
    assert r.status_code == 404 and r.json() == {'error': 'Proposal not found'}
    for bad in ('no-es-uuid', "1'%20OR%20'1'='1"):
        r = api_post(client, approve_url(bad), admin_claims('adm'))
        assert r.status_code == 404 and r.json() == {'error': 'Proposal not found'}
    for status in ('approved', 'rejected'):
        pid = make_proposal(status=status, minutes=3)
        r = api_post(client, approve_url(pid), admin_claims('adm'))
        assert r.status_code == 409 and r.json() == {'error': f'Proposal is already {status}'}


def test_approve_dues_vegades_200_i_409_sense_duplicar(client, world):
    pid = make_proposal()
    assert api_post(client, approve_url(pid), admin_claims('adm')).status_code == 200
    n = len(refuge_ids())
    r = api_post(client, approve_url(pid), admin_claims('adm2'))
    assert r.status_code == 409 and r.json() == {'error': 'Proposal is already approved'}
    assert len(refuge_ids()) == n and proposal_row(pid)['reviewer_uid'] == 'adm'


def test_approve_un_admin_pot_aprovar_la_seva_pròpia_proposta(client, world):
    pid = make_proposal(creator='adm')
    assert api_post(client, approve_url(pid), admin_claims('adm')).status_code == 200


def test_approve_amb_enllac_d_un_altre_refugi_409_i_la_proposta_es_conserva_pendent(client, world):
    make_refuge(name='Propietari', lat=44, links=['https://a.test/dup'])
    pid = make_proposal(payload=new_payload(links=['https://a.test/dup']))
    n = len(refuge_ids())
    r = api_post(client, approve_url(pid), admin_claims('adm'))
    assert r.status_code == 409 and r.json().get('error'), r.content
    assert proposal_row(pid)['status'] == 'pending' and len(refuge_ids()) == n


def test_approve_no_toca_les_altres_propostes_pendents_d_un_create(client, world):
    a, b = make_proposal(minutes=0), make_proposal(minutes=1)
    api_post(client, approve_url(a), admin_claims('adm'))
    assert proposal_row(b)['status'] == 'pending'


# =================================== reject ===================================

def test_reject_200_amb_i_sense_motiu(client, world):
    a, b = make_proposal(minutes=0), make_proposal(minutes=1)
    r = api_post(client, reject_url(a), admin_claims('adm'), {'reason': 'Cal més evidència'})
    assert r.status_code == 200 and r.json() == {'message': 'Proposal rejected successfully'}
    assert api_post(client, reject_url(b), admin_claims('adm')).status_code == 200
    ra, rb = proposal_row(a), proposal_row(b)
    assert (ra['status'], ra['rejection_reason'], ra['reviewer_uid']) == ('rejected', 'Cal més evidència', 'adm')
    assert (rb['status'], rb['rejection_reason']) == ('rejected', None)
    [mine] = [p for p in api_get(client, MINE, user_claims('u1')).json() if p['id'] == a]
    assert mine['rejection_reason'] == 'Cal més evidència' and mine['reviewer_uid'] == 'adm'


def test_reject_no_aplica_el_payload(client, refuge):
    pid = make_proposal('update', refuge=refuge, payload={'places': 99})
    assert api_post(client, reject_url(pid), admin_claims('adm'), {'reason': 'no'}).status_code == 200
    assert refuge_state(refuge.pk)['places'] == 10


def test_reject_motiu_de_2000_ok_i_2001_400(client, world):
    ok, bad = make_proposal(minutes=0), make_proposal(minutes=1)
    assert api_post(client, reject_url(ok), admin_claims('adm'), {'reason': 'x' * 2000}).status_code == 200
    r = api_post(client, reject_url(bad), admin_claims('adm'), {'reason': 'x' * 2001})
    assert r.status_code == 400 and r.json()['error'] == 'Invalid data' and 'reason' in r.json()['details']
    assert proposal_row(bad)['status'] == 'pending'


def test_reject_motiu_null_400(client, world):
    pid = make_proposal()
    r = api_post(client, reject_url(pid), admin_claims('adm'), {'reason': None})
    assert r.status_code == 400 and 'reason' in r.json()['details']


def test_reject_404_i_409(client, world):
    r = api_post(client, reject_url(uuid.uuid4()), admin_claims('adm'), {})
    assert r.status_code == 404 and r.json() == {'error': 'Proposal not found'}
    assert api_post(client, reject_url('no-es-uuid'), admin_claims('adm'), {}).status_code == 404
    for status in ('approved', 'rejected'):
        pid = make_proposal(status=status, minutes=2)
        r = api_post(client, reject_url(pid), admin_claims('adm'), {'reason': 'tard'})
        assert r.status_code == 409 and r.json() == {'error': f'Proposal is already {status}'}


def test_reject_despres_d_aprovar_409_i_aprovar_despres_de_rebutjar_409(client, world):
    a, b = make_proposal(minutes=0), make_proposal(minutes=1)
    api_post(client, approve_url(a), admin_claims('adm'))
    assert api_post(client, reject_url(a), admin_claims('adm'), {}).status_code == 409
    api_post(client, reject_url(b), admin_claims('adm'), {})
    assert api_post(client, approve_url(b), admin_claims('adm')).status_code == 409
    assert len(refuge_ids()) == 3                                         # 2 del món + el de la proposta `a`


def test_aprovar_un_delete_rebutja_les_altres_pendents_i_ho_mostra_la_llista(client, refuge, world):
    target = make_proposal('delete', refuge=refuge, minutes=0)
    other = make_proposal('update', refuge=refuge, creator='u2', minutes=1)
    assert api_post(client, approve_url(target), admin_claims('adm')).status_code == 200
    [mine] = api_get(client, MINE, user_claims('u2')).json()
    assert mine['id'] == other and mine['status'] == 'rejected' and mine['rejection_reason'] == DELETED_REASON
    assert mine['reviewer_uid'] is None and mine['refuge_id'] is None
    assert api_post(client, approve_url(other), admin_claims('adm')).status_code == 409
