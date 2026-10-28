"""
Selectors i services de `apps.proposals` (chunk 8). Contracte proposat pels tests (l'implementador pot renomenar-lo
justificant-ho). Les vistes hi accedeixen com a `selectors.x(...)` / `services.x(...)` (mòdul) perquè els tests de 500
puguin fer `patch('apps.proposals.services.x')`.

selectors (lectures; sense cache; la RLS filtra: propi o admin)
- `list_proposals(*, status=None, refuge_id=None, creator_uid=None) -> list[RefugeProposal]`
      1 consulta, `(created_at DESC, id DESC)`; `refuge_id` no UUID -> `[]`
- `get_proposal(proposal_id) -> RefugeProposal | None`        1 consulta; id no UUID -> `None`

services (escriptures; excepcions de domini, cap tupla; s'executen dins `rls_context` de l'actor)
- excepcions: `RefugeNotFound` (update/delete d'un refugi inexistent), `ProposalNotFound`, `ProposalAlreadyReviewed`
  (amb `.status`), `LinkAlreadyUsed` (un enllaç del payload ja és d'un altre refugi: PK de `refuge_links`, R12)
- `create_proposal(*, creator_uid, action, refuge_id=None, payload=None, comment=None) -> RefugeProposal`
- `approve_proposal(*, proposal_id, reviewer_uid) -> RefugeProposal`      una sola `transaction.atomic()`
- `reject_proposal(*, proposal_id, reviewer_uid, reason=None) -> RefugeProposal`

Semàntica (idèntica a l'actual, §2.18): `modified_at` = data (Madrid) de **creació** de la proposta; `info_comp` d'un
`update` substitueix els 12 indicadors; `links` es substitueixen sencers; `coord` -> Point(long, lat); `condition`
**reinicia** la mitjana (`c = valor`, `n = 1`, `condition_reset_at = now()`; ja no és una mitjana nova com avui).
"""
import uuid
from datetime import datetime, timedelta, timezone as dt_timezone

import pytest
from django.utils import timezone

from apps.core.rls import rls_context
from apps.proposals.tests.helpers import (
    DELETED_REASON, INFO_COMP_FIELDS, SNAPSHOT_KEYS, at, make_proposal, make_refuge, new_payload, new_refuge_id,
    proposal_ids, proposal_row, refuge_ids, refuge_state, snapshot_of, sql, uuid7_ok)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.integration, pytest.mark.real_permissions]

BAD_IDS = ['no-es-uuid', '', '0' * 40, 'a\x00b', "1'; DROP TABLE proposals.refuge_proposals;--"]


def admin(uid='adm'):
    return rls_context(uid=uid, is_admin=True)


def user(uid='u1'):
    return rls_context(uid=uid)


def approve(services, pid, uid='adm'):
    with admin(uid):
        return services.approve_proposal(proposal_id=pid, reviewer_uid=uid)


def reject(services, pid, reason=None, uid='adm'):
    with admin(uid):
        return services.reject_proposal(proposal_id=pid, reviewer_uid=uid, reason=reason)


@pytest.fixture
def refuge(world):
    return world[0]


@pytest.fixture
def full_refuge():
    """Refugi amb totes les dades, mitjana de condició (1,5 de 3 vots) i enllaços."""
    return make_refuge(name='Refugi de Colomers', lat=42.6321, long=0.9984, surname='Colomers', altitude=2135,
                       places=12, type='fermée', description='Un refugi', region='Pirineus', departement='Lleida',
                       modified_at='2024-05-17', condition=1.5, num_contributed_conditions=3,
                       amenities={'eau': True, 'poele': True, 'lits': True},
                       links=['https://a.test/1', 'https://a.test/2'])


# =================================== selectors ===================================

def test_list_ordre_i_filtres(selectors, world):
    r1, r2 = world
    a = make_proposal(creator='u1', minutes=0)
    b = make_proposal('update', creator='u2', refuge=r1, minutes=10)
    c = make_proposal('delete', creator='u1', refuge=r2, minutes=20, status='rejected')
    d = make_proposal(creator='u1', minutes=30, status='approved')
    with admin():
        ids = lambda **kw: [str(p.pk) for p in selectors.list_proposals(**kw)]          # noqa: E731
        assert ids() == [d, c, b, a]                                                    # created_at DESC
        assert ids(status='pending') == [b, a]
        assert ids(status='rejected') == [c]
        assert ids(refuge_id=str(r1.pk)) == [b]
        assert ids(refuge_id=str(r2.pk), status='rejected') == [c]
        assert ids(creator_uid='u1') == [d, c, a]
        assert ids(creator_uid='u1', status='pending') == [a]


def test_list_desempata_per_id_quan_created_at_coincideix(selectors, world):
    ids = [make_proposal(creator='u1', minutes=0) for _ in range(3)]
    with admin():
        got = [str(p.pk) for p in selectors.list_proposals()]
    assert got == sorted(ids, reverse=True)


def test_list_respecta_la_rls_un_usuari_nomes_veu_les_seves(selectors, world):
    mine = make_proposal(creator='u1')
    make_proposal(creator='u2', minutes=1)
    with user('u1'):
        assert [str(p.pk) for p in selectors.list_proposals()] == [mine]
    with user('u3'):
        assert selectors.list_proposals() == []


@pytest.mark.parametrize('bad', BAD_IDS)
def test_list_amb_refuge_id_invalid_es_buit(selectors, world, bad):
    make_proposal()
    with admin():
        assert selectors.list_proposals(refuge_id=bad) == []


def test_list_1_consulta(selectors, world):
    from apps.proposals.tests.helpers import QueryCounter
    for i in range(5):
        make_proposal(minutes=i)
    with admin():
        with QueryCounter() as q:
            assert len(selectors.list_proposals()) == 5
    assert q.count == 1, q.queries


def test_get_proposal(selectors, world):
    pid = make_proposal(creator='u1', comment='hola')
    with user('u1'):
        p = selectors.get_proposal(pid)
        assert str(p.pk) == pid and p.comment == 'hola' and p.creator_id == 'u1'
        assert selectors.get_proposal(str(uuid.uuid4())) is None
    with user('u2'):
        assert selectors.get_proposal(pid) is None                                       # RLS


@pytest.mark.parametrize('bad', BAD_IDS)
def test_get_proposal_amb_id_invalid_es_none(selectors, world, bad):
    with admin():
        assert selectors.get_proposal(bad) is None


# =================================== create_proposal ===================================

def test_create_guarda_payload_sense_foto_ni_refugi(services, world):
    payload = new_payload()
    with user('u1'):
        p = services.create_proposal(creator_uid='u1', action='create', payload=payload, comment='nou')
    assert uuid7_ok(str(p.pk))
    row = proposal_row(str(p.pk))
    assert (row['action'], row['status'], row['creator_uid'], row['comment']) == ('create', 'pending', 'u1', 'nou')
    assert row['payload'] == payload and row['refuge_snapshot'] is None and row['refuge_id'] is None
    assert row['reviewer_uid'] is None and row['reviewed_at'] is None and row['rejection_reason'] is None
    assert row['created_at'] is not None


def test_create_update_desa_la_foto_del_refugi_en_forma_d_api(services, full_refuge):
    from apps.proposals.tests.helpers import make_user
    make_user('u1')
    with user('u1'):
        p = services.create_proposal(creator_uid='u1', action='update', refuge_id=str(full_refuge.pk),
                                     payload={'places': 45})
    row = proposal_row(str(p.pk))
    snap = row['refuge_snapshot']
    assert set(snap) == SNAPSHOT_KEYS                                  # sense visitors, images_metadata, surname ni remarque
    assert row['refuge_id'] == str(full_refuge.pk) and row['payload'] == {'places': 45}
    assert snap['id'] == str(full_refuge.pk) and snap['name'] == 'Refugi de Colomers'
    assert snap['coord'] == pytest.approx({'lat': 42.6321, 'long': 0.9984})
    assert (snap['altitude'], snap['places'], snap['type'], snap['description']) == (2135, 12, 'fermée', 'Un refugi')
    assert (snap['region'], snap['departement'], snap['modified_at']) == ('Pirineus', 'Lleida', '2024-05-17')
    assert snap['links'] == ['https://a.test/1', 'https://a.test/2']
    assert snap['condition'] == 2                                       # round(1,5) half-to-even, com l'API
    assert set(snap['info_comp']) == set(INFO_COMP_FIELDS)
    assert all(type(v) is int for v in snap['info_comp'].values())
    assert (snap['info_comp']['eau'], snap['info_comp']['poele'], snap['info_comp']['lits'],
            snap['info_comp']['cheminee']) == (1, 1, 1, 0)


def test_create_delete_sense_payload_i_amb_foto(services, refuge):
    with user('u1'):
        p = services.create_proposal(creator_uid='u1', action='delete', refuge_id=str(refuge.pk), comment='allau')
    row = proposal_row(str(p.pk))
    assert row['payload'] is None and row['refuge_snapshot']['id'] == str(refuge.pk) and row['action'] == 'delete'


def test_la_foto_es_immutable_encara_que_el_refugi_canviï(services, refuge):
    with user('u1'):
        p = services.create_proposal(creator_uid='u1', action='delete', refuge_id=str(refuge.pk))
    before = proposal_row(str(p.pk))['refuge_snapshot']
    sql("UPDATE refuges.refuges SET name = 'Canviat', places = 99 WHERE id = %s", [refuge.pk])
    assert proposal_row(str(p.pk))['refuge_snapshot'] == before and before['name'] == 'Refugi A'


@pytest.mark.parametrize('action', ['update', 'delete'])
@pytest.mark.parametrize('rid', [str(uuid.uuid4())] + BAD_IDS)
def test_create_d_un_refugi_inexistent_o_id_invalid(services, world, action, rid):
    with pytest.raises(services.RefugeNotFound):
        with user('u1'):
            services.create_proposal(creator_uid='u1', action=action, refuge_id=rid,
                                     payload={'places': 1} if action == 'update' else None)
    assert proposal_ids() == set()


def test_create_d_un_refugi_proper_i_amb_nom_semblant_llanca_possible_duplicates(services, refuge):
    """Decisió del PO (27/10): <= 500 m i nom semblant -> `PossibleDuplicates` (409 a l'API); no es crea res."""
    with pytest.raises(services.PossibleDuplicates) as info:
        with user('u1'):
            services.create_proposal(creator_uid='u1', action='create',
                                     payload=new_payload(name='Refugi A', coord={'lat': 42.5, 'long': 1.5}))
    assert [d['id'] for d in info.value.duplicates] == [str(refuge.pk)]
    assert proposal_ids() == set()


def test_create_com_a_un_altre_usuari_es_rebutjat_per_la_rls(services, world):
    with pytest.raises(Exception):
        with user('u2'):
            services.create_proposal(creator_uid='u1', action='create', payload=new_payload())
    assert proposal_ids() == set()


# =================================== approve: create ===================================

def test_approve_create_crea_refugi_amenities_i_enllacos(services, world):
    pid = make_proposal(payload=new_payload(description='Al costat del llac', region='Pirineus', departement='Lleida',
                                            links=['https://a.test/x', 'https://a.test/y']),
                        creator='u1', created_at=datetime(2025, 3, 4, 12, 0, tzinfo=dt_timezone.utc))
    p = approve(services, pid)
    rid = new_refuge_id(pid)
    assert uuid7_ok(rid) and str(p.refuge_id) == rid
    s = refuge_state(rid)
    assert (s['name'], s['type'], s['altitude'], s['places']) == ('Refugi Nou', 'non gardé', 1800, 15)
    assert (s['long'], s['lat']) == pytest.approx((1.234, 42.567))               # Point(long, lat)
    assert (s['description'], s['region'], s['departement']) == ('Al costat del llac', 'Pirineus', 'Lleida')
    assert s['modified_at'].isoformat() == '2025-03-04'
    assert s['surname'] is None and s['condition'] is None and s['n'] == 0 and s['condition_reset_at'] is None
    assert s['amenities'] == {f: f in ('cheminee', 'eau', 'lits') for f in INFO_COMP_FIELDS}
    assert s['links'] == ['https://a.test/x', 'https://a.test/y'] and s['link_positions'] == [0, 1]
    row = proposal_row(pid)
    assert (row['status'], row['reviewer_uid'], row['refuge_id']) == ('approved', 'adm', rid)
    assert row['rejection_reason'] is None and abs(timezone.now() - row['reviewed_at']) < timedelta(minutes=1)
    assert row['payload'] == new_payload(description='Al costat del llac', region='Pirineus', departement='Lleida',
                                         links=['https://a.test/x', 'https://a.test/y'])      # el payload no es toca


def test_approve_create_minim_usa_els_valors_per_defecte(services, world):
    pid = make_proposal(payload={'name': 'Mínim', 'coord': {'lat': 42.0, 'long': 2.0}})
    approve(services, pid)
    s = refuge_state(new_refuge_id(pid))
    assert (s['type'], s['description'], s['altitude'], s['places'], s['region']) == ('non gardé', '', None, None, None)
    assert s['amenities'] == {f: False for f in INFO_COMP_FIELDS} and s['links'] == []   # la fila d'amenities hi és sempre


def test_approve_create_modified_at_es_la_data_de_madrid_de_la_creacio_no_la_d_aprovacio(services, world):
    late = make_proposal(created_at=datetime(2025, 3, 4, 23, 30, tzinfo=dt_timezone.utc))        # 00:30 del 5 a Madrid
    early = make_proposal(created_at=datetime(2025, 3, 4, 22, 30, tzinfo=dt_timezone.utc), minutes=1)   # 23:30 del 4
    approve(services, late)
    approve(services, early)
    assert refuge_state(new_refuge_id(late))['modified_at'].isoformat() == '2025-03-05'
    assert refuge_state(new_refuge_id(early))['modified_at'].isoformat() == '2025-03-04'


@pytest.mark.parametrize('value', [0, 1, 2, 3])
def test_approve_create_amb_condition_inicialitza_la_mitjana(services, world, value):
    pid = make_proposal(payload=new_payload(condition=value))
    approve(services, pid)
    s = refuge_state(new_refuge_id(pid))
    assert s['condition'] == float(value) and s['n'] == 1
    assert abs(timezone.now() - s['condition_reset_at']) < timedelta(minutes=1)


def test_approve_create_amb_condition_nul_no_inicialitza_res(services, world):
    pid = make_proposal(payload=new_payload(condition=None))
    approve(services, pid)
    s = refuge_state(new_refuge_id(pid))
    assert (s['condition'], s['n'], s['condition_reset_at']) == (None, 0, None)


def test_approve_create_el_nou_refugi_es_veu_a_l_api_i_te_uuid_v7(services, world, client):
    from apps.proposals.tests.helpers import api_get, user_claims
    pid = make_proposal(payload=new_payload(name='Cabana del Mirador', links=['https://a.test/mirador']))
    approve(services, pid)
    rid = new_refuge_id(pid)
    assert uuid7_ok(rid)
    detail = api_get(client, f'/api/refuges/{rid}/').json()
    assert detail['name'] == 'Cabana del Mirador' and detail['id'] == rid and detail['links'] == ['https://a.test/mirador']
    assert detail['coord'] == pytest.approx({'lat': 42.567, 'long': 1.234})
    assert detail['info_comp']['cheminee'] == 1 and detail['info_comp']['poele'] == 0
    assert detail['modified_at'] == '2025-01-01'                                       # data de creació de la proposta
    found = api_get(client, '/api/refuges/?name=Mirador', user_claims('u1')).json()
    assert [r['id'] for r in found['results']] == [rid]


def test_approve_create_amb_enllac_ja_usat_per_un_altre_refugi_es_desfa_tot(services, world):
    make_refuge(name='Propietari', lat=44, links=['https://a.test/dup'])
    pid = make_proposal(payload=new_payload(name='Duplicat', links=['https://a.test/ok', 'https://a.test/dup']))
    n = len(refuge_ids())
    with pytest.raises(services.LinkAlreadyUsed):
        approve(services, pid)
    row = proposal_row(pid)
    assert row['status'] == 'pending' and row['refuge_id'] is None and len(refuge_ids()) == n
    assert sql("SELECT count(*) FROM refuges.refuge_links WHERE url = 'https://a.test/ok'") == [(0,)]


# =================================== approve: update ===================================

def test_approve_update_nomes_toca_els_camps_enviats(services, full_refuge):
    pid = make_proposal('update', refuge=full_refuge, payload={'places': 45},
                        created_at=datetime(2025, 6, 1, 8, 0, tzinfo=dt_timezone.utc))
    approve(services, pid)
    s = refuge_state(full_refuge.pk)
    assert s['places'] == 45 and s['modified_at'].isoformat() == '2025-06-01'
    assert (s['name'], s['surname'], s['type'], s['altitude'], s['description']) == (
        'Refugi de Colomers', 'Colomers', 'fermée', 2135, 'Un refugi')
    assert (s['region'], s['departement']) == ('Pirineus', 'Lleida')
    assert s['links'] == ['https://a.test/1', 'https://a.test/2']
    assert (s['amenities']['eau'], s['amenities']['poele'], s['amenities']['lits']) == (True, True, True)
    assert (s['condition'], s['n'], s['condition_reset_at']) == (1.5, 3, None)
    row = proposal_row(pid)
    assert (row['status'], row['reviewer_uid'], row['refuge_id']) == ('approved', 'adm', str(full_refuge.pk))


def test_approve_update_de_tots_els_camps(services, full_refuge):
    pid = make_proposal('update', refuge=full_refuge, payload={
        'name': 'Nou nom', 'coord': {'lat': 43.1, 'long': 2.2}, 'altitude': 1500, 'places': 8, 'type': 'orri',
        'description': 'Nova descripció', 'region': 'Aran', 'departement': 'Vall'})
    approve(services, pid)
    s = refuge_state(full_refuge.pk)
    assert (s['name'], s['altitude'], s['places'], s['type']) == ('Nou nom', 1500, 8, 'orri')
    assert (s['long'], s['lat']) == pytest.approx((2.2, 43.1))
    assert (s['description'], s['region'], s['departement'], s['surname']) == ('Nova descripció', 'Aran', 'Vall', 'Colomers')


def test_approve_update_amb_null_buida_el_camp(services, full_refuge):
    pid = make_proposal('update', refuge=full_refuge, payload={'altitude': None, 'places': None, 'region': None,
                                                                'departement': None, 'description': None})
    approve(services, pid)
    s = refuge_state(full_refuge.pk)
    assert (s['altitude'], s['places'], s['region'], s['departement']) == (None, None, None, None)
    assert s['description'] == ''                                       # NOT NULL a la BD: mai `null` (§2.5)


def test_approve_update_amb_regio_buida_la_desa_com_a_null(services, full_refuge):
    pid = make_proposal('update', refuge=full_refuge, payload={'region': '', 'departement': ''})
    approve(services, pid)
    s = refuge_state(full_refuge.pk)
    assert (s['region'], s['departement']) == (None, None)               # decisió 15 del disseny


def test_approve_update_info_comp_substitueix_els_12_indicadors(services, full_refuge):
    pid = make_proposal('update', refuge=full_refuge, payload={'info_comp': {'cheminee': 1, 'latrines': 1}})
    approve(services, pid)
    assert refuge_state(full_refuge.pk)['amenities'] == {f: f in ('cheminee', 'latrines') for f in INFO_COMP_FIELDS}


def test_approve_update_amb_info_comp_buit_ho_posa_tot_a_fals(services, full_refuge):
    pid = make_proposal('update', refuge=full_refuge, payload={'info_comp': {}})
    approve(services, pid)
    assert refuge_state(full_refuge.pk)['amenities'] == {f: False for f in INFO_COMP_FIELDS}


def test_approve_update_sense_info_comp_no_toca_els_serveis(services, full_refuge):
    pid = make_proposal('update', refuge=full_refuge, payload={'name': 'Altre'})
    approve(services, pid)
    assert refuge_state(full_refuge.pk)['amenities']['eau'] is True


def test_approve_update_links_se_substitueixen_sencers(services, full_refuge):
    pid = make_proposal('update', refuge=full_refuge, payload={'links': ['https://a.test/n1', 'https://a.test/n2',
                                                                        'https://a.test/n3']})
    approve(services, pid)
    s = refuge_state(full_refuge.pk)
    assert s['links'] == ['https://a.test/n1', 'https://a.test/n2', 'https://a.test/n3']
    assert s['link_positions'] == [0, 1, 2]


def test_approve_update_pot_reordenar_i_reenviar_els_propis_enllacos(services, full_refuge):
    pid = make_proposal('update', refuge=full_refuge, payload={'links': ['https://a.test/2', 'https://a.test/1']})
    approve(services, pid)
    s = refuge_state(full_refuge.pk)
    assert s['links'] == ['https://a.test/2', 'https://a.test/1'] and s['link_positions'] == [0, 1]


def test_approve_update_links_buits_esborra_els_enllacos(services, full_refuge):
    approve(services, make_proposal('update', refuge=full_refuge, payload={'links': []}))
    assert refuge_state(full_refuge.pk)['links'] == []


def test_approve_update_amb_enllac_d_un_altre_refugi_es_desfa_tot(services, full_refuge):
    make_refuge(name='Altre', lat=44, links=['https://a.test/dup'])
    pid = make_proposal('update', refuge=full_refuge, payload={'name': 'No ha de quedar', 'places': 99,
                                                               'links': ['https://a.test/dup']})
    with pytest.raises(services.LinkAlreadyUsed):
        approve(services, pid)
    s = refuge_state(full_refuge.pk)
    assert (s['name'], s['places'], s['links']) == ('Refugi de Colomers', 12, ['https://a.test/1', 'https://a.test/2'])
    assert proposal_row(pid)['status'] == 'pending'


@pytest.mark.parametrize('value', [0, 1, 3])
def test_approve_update_amb_condition_reinicia_la_mitjana(services, full_refuge, value):
    pid = make_proposal('update', refuge=full_refuge, payload={'condition': value})
    approve(services, pid)
    s = refuge_state(full_refuge.pk)
    assert s['condition'] == float(value) and s['n'] == 1                 # no (1,5*3 + v)/4 com abans
    assert abs(timezone.now() - s['condition_reset_at']) < timedelta(minutes=1)


@pytest.mark.parametrize('payload', [{'condition': None, 'places': 5}, {'places': 5}])
def test_approve_update_sense_condition_valida_no_reinicia(services, full_refuge, payload):
    approve(services, make_proposal('update', refuge=full_refuge, payload=payload))
    s = refuge_state(full_refuge.pk)
    assert (s['condition'], s['n'], s['condition_reset_at']) == (1.5, 3, None)


def test_approve_update_amb_condition_sobre_un_refugi_sense_mitjana(services, refuge):
    approve(services, make_proposal('update', refuge=refuge, payload={'condition': 2}))
    s = refuge_state(refuge.pk)
    assert (s['condition'], s['n']) == (2.0, 1)


def test_approve_update_no_canvia_l_id_ni_la_data_de_creacio_del_refugi(services, refuge):
    before = sql('SELECT id, created_at FROM refuges.refuges WHERE id = %s', [refuge.pk])
    approve(services, make_proposal('update', refuge=refuge, payload={'name': 'x'}))
    assert sql('SELECT id, created_at FROM refuges.refuges WHERE id = %s', [refuge.pk]) == before


# =================================== approve: delete ===================================

def test_approve_delete_esborra_refugi_serveis_i_enllacos(services, full_refuge):
    pid = make_proposal('delete', refuge=full_refuge)
    approve(services, pid)
    assert refuge_state(full_refuge.pk) is None
    assert sql('SELECT count(*) FROM refuges.refuge_amenities WHERE refuge_id = %s', [full_refuge.pk]) == [(0,)]
    assert sql('SELECT count(*) FROM refuges.refuge_links WHERE refuge_id = %s', [full_refuge.pk]) == [(0,)]
    row = proposal_row(pid)
    assert (row['status'], row['reviewer_uid']) == ('approved', 'adm')
    assert row['refuge_id'] is None and row['refuge_snapshot']['name'] == 'Refugi A' and row['action'] == 'delete'


def test_approve_delete_rebutja_primer_les_altres_pendents_del_refugi(services, world):
    r1, r2 = world
    target = make_proposal('delete', refuge=r1, minutes=0)
    other_update = make_proposal('update', refuge=r1, creator='u2', minutes=1)
    other_delete = make_proposal('delete', refuge=r1, creator='u3', minutes=2)
    elsewhere = make_proposal('update', refuge=r2, minutes=3)
    creation = make_proposal('create', minutes=4)
    done_approved = make_proposal('update', refuge=r1, status='approved', minutes=5)
    done_rejected = make_proposal('update', refuge=r1, status='rejected', rejection_reason='no', minutes=6)
    approve(services, target)
    for pid in (other_update, other_delete):
        row = proposal_row(pid)
        assert row['status'] == 'rejected' and row['rejection_reason'] == DELETED_REASON, pid
        assert row['reviewer_uid'] is None and row['reviewed_at'] is not None and row['refuge_id'] is None
    assert proposal_row(target)['status'] == 'approved'
    # no toca ni les d'altres refugis, ni les creacions, ni les ja resoltes (que només perden el refuge_id)
    assert proposal_row(elsewhere)['status'] == 'pending' and proposal_row(elsewhere)['refuge_id'] == str(r2.pk)
    assert proposal_row(creation)['status'] == 'pending'
    assert proposal_row(done_approved)['status'] == 'approved' and proposal_row(done_approved)['refuge_id'] is None
    r = proposal_row(done_rejected)
    assert (r['status'], r['rejection_reason'], r['reviewer_uid'], r['refuge_id']) == ('rejected', 'no', 'adm', None)


def test_una_pendent_rebutjada_per_l_esborrat_ja_no_es_pot_aprovar(services, world):
    r1, _ = world
    target = make_proposal('delete', refuge=r1)
    other = make_proposal('update', refuge=r1, minutes=1)
    approve(services, target)
    with pytest.raises(services.ProposalAlreadyReviewed) as info:
        approve(services, other)
    assert info.value.status == 'rejected'


def test_approve_delete_no_toca_la_mitjana_ni_els_altres_refugis(services, world):
    r1, r2 = world
    approve(services, make_proposal('delete', refuge=r1))
    assert refuge_state(r2.pk) is not None and refuge_ids() == {str(r2.pk)}


# =================================== approve: errors i estat ===================================

@pytest.mark.parametrize('status,expected', [('approved', 'approved'), ('rejected', 'rejected')])
def test_approve_d_una_proposta_ja_resolta_no_fa_res(services, world, status, expected):
    pid = make_proposal(status=status)
    n = len(refuge_ids())
    with pytest.raises(services.ProposalAlreadyReviewed) as info:
        approve(services, pid)
    assert info.value.status == expected and len(refuge_ids()) == n
    assert proposal_row(pid)['reviewer_uid'] == 'adm'


def test_approve_dues_vegades_la_segona_falla_i_no_duplica_el_refugi(services, world):
    pid = make_proposal()
    approve(services, pid)
    n = len(refuge_ids())
    with pytest.raises(services.ProposalAlreadyReviewed):
        approve(services, pid, uid='adm2')
    assert len(refuge_ids()) == n and proposal_row(pid)['reviewer_uid'] == 'adm'


@pytest.mark.parametrize('bad', [str(uuid.uuid4())] + BAD_IDS)
def test_approve_inexistent_o_id_invalid(services, world, bad):
    with pytest.raises(services.ProposalNotFound):
        approve(services, bad)


def test_approve_per_part_d_un_usuari_normal_no_canvia_res(services, world):
    pid = make_proposal(creator='u1')
    n = len(refuge_ids())
    with pytest.raises(Exception):
        with user('u1'):
            services.approve_proposal(proposal_id=pid, reviewer_uid='u1')
    assert proposal_row(pid)['status'] == 'pending' and len(refuge_ids()) == n


# =================================== reject ===================================

def test_reject_amb_motiu(services, refuge):
    pid = make_proposal('update', refuge=refuge)
    reject(services, pid, 'Cal més evidència')
    row = proposal_row(pid)
    assert (row['status'], row['reviewer_uid'], row['rejection_reason']) == ('rejected', 'adm', 'Cal més evidència')
    assert abs(timezone.now() - row['reviewed_at']) < timedelta(minutes=1)
    assert refuge_state(refuge.pk)['places'] == 10                          # no s'aplica res


@pytest.mark.parametrize('reason', [None, ''])
def test_reject_sense_motiu_deixa_null(services, world, reason):
    pid = make_proposal()
    reject(services, pid, reason)
    row = proposal_row(pid)
    assert row['status'] == 'rejected' and row['rejection_reason'] is None and row['reviewer_uid'] == 'adm'


def test_reject_no_crea_cap_refugi(services, world):
    n = len(refuge_ids())
    reject(services, make_proposal(), 'no')
    assert len(refuge_ids()) == n


@pytest.mark.parametrize('status', ['approved', 'rejected'])
def test_reject_d_una_proposta_ja_resolta(services, world, status):
    pid = make_proposal(status=status)
    with pytest.raises(services.ProposalAlreadyReviewed) as info:
        reject(services, pid, 'tard')
    assert info.value.status == status
    assert proposal_row(pid)['rejection_reason'] is None


@pytest.mark.parametrize('bad', [str(uuid.uuid4())] + BAD_IDS)
def test_reject_inexistent_o_id_invalid(services, world, bad):
    with pytest.raises(services.ProposalNotFound):
        reject(services, bad)


def test_reject_per_part_d_un_usuari_normal_no_canvia_res(services, world):
    pid = make_proposal(creator='u1')
    with pytest.raises(Exception):
        with user('u1'):
            services.reject_proposal(proposal_id=pid, reviewer_uid='u1', reason='x')
    assert proposal_row(pid)['status'] == 'pending'
