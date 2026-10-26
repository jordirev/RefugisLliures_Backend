"""
Contracte HTTP de `apps/visits/views.py` (chunk 4): mateixos JSON i codis que els de Firestore.

    GET    /api/refuges/{refuge_id}/visits/              -> 200 {"result": [visita, ...]}   (visit_date >= avui, ascendent)
    POST   /api/refuges/{refuge_id}/visits/{YYYY-MM-DD}/ -> 201 {"message": "Visita creada correctament", "visit": visita}
    PATCH  idem                                          -> 200 {"message": "Visita actualitzada correctament", "visit": visita}
    DELETE idem                                          -> 200 {"message": "Visitant eliminat correctament"}   (no 204)
    GET    /api/users/{uid}/visits/                      -> 200 {"result": [visita, ...]}   (totes, data descendent)

`visita` = `{date, refuge_id, total_visitors, is_visitor, num_visitors}` (les 5 claus sempre, tambe al llistat del
refugi: el serializer emet `refuge_id` de qualsevol visita). `is_visitor`/`num_visitors` son de l'usuari del token;
els participants d'altres no s'exposen mai. `refuge_id` es el UUID de PostgreSQL com a text.

Errors (cos `{"error": <text>}`; els `error` de validacio del serializer son el dict de DRF):
    400 serializer invalid | «Format de data invàlid. Utilitza YYYY-MM-DD» (POST) | «La data de la visita ha de ser igual
        o posterior a avui» (POST) | «Ja estàs registrat a aquesta visita» (POST) | «No estàs registrat a aquesta visita»
        (PATCH, DELETE)
    404 «Refugi amb ID {id} no trobat» (GET llista i POST; refugi inexistent o id que no es UUID)
        «Visita o refugi no trobat» (PATCH) · «Visita no trobada» (DELETE)
    Ordre de comprovacions del POST (com el controller actual): serializer (400) -> refugi (404) -> format de data
    (400) -> data passada (400) -> ja registrat (400). PATCH/DELETE amb una data no valida: 404 (no troben cap visita).
Les vistes criden `apps.visits.services` (`from . import services` a `views.py`).
"""
import pytest

from apps.visits.tests.helpers import (
    VISIT_KEYS, admin_claims, api_delete, api_get, api_patch, api_post, day, make_refuge, make_user, make_visit,
    participant_rows, refuge_visits_url, total_of, unknown_id, user_claims, user_visits_url, visit_dates,
    visit_id_of, visit_rows, visit_url, visited_ids)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration,
              pytest.mark.real_permissions]

SECRET_UID = 'uid-secret-d-un-altre-usuari'


@pytest.fixture
def scene():
    make_user('u1', username='Anna')
    make_user('u2', username='Bernat')
    make_user(SECRET_UID)
    return make_refuge(name='R1'), make_refuge(name='R2', lat=43)


def body(resp):
    return resp.json()


# =================================== GET /refuges/{id}/visits/ ===================================

def test_get_llista_visites_del_refugi(client, scene):
    r1, r2 = scene
    make_visit(r1, day(-1), {'u1': 1})                                     # passada: no surt
    make_visit(r1, day(5), {'u1': 2, 'u2': 4, SECRET_UID: 1})
    make_visit(r1, day(0), {'u2': 3})
    make_visit(r2, day(1), {'u1': 9})                                      # altre refugi
    resp = api_get(client, refuge_visits_url(r1.pk), user_claims('u1'))
    assert resp.status_code == 200 and set(body(resp)) == {'result'}
    assert body(resp)['result'] == [
        {'date': day(0).isoformat(), 'refuge_id': str(r1.pk), 'total_visitors': 3, 'is_visitor': False,
         'num_visitors': 0},
        {'date': day(5).isoformat(), 'refuge_id': str(r1.pk), 'total_visitors': 7, 'is_visitor': True,
         'num_visitors': 2},
    ]


def test_get_no_exposa_els_participants_d_altres(client, scene):
    r1, _ = scene
    make_visit(r1, day(1), {'u1': 1, 'u2': 2, SECRET_UID: 3})
    resp = api_get(client, refuge_visits_url(r1.pk), user_claims('u1'))
    assert SECRET_UID not in resp.content.decode() and 'u2' not in resp.content.decode()
    assert all(set(v) == VISIT_KEYS for v in body(resp)['result'])
    assert body(resp)['result'][0]['total_visitors'] == 6


def test_get_el_total_inclou_tothom_encara_que_l_usuari_no_hi_participi(client, scene):
    r1, _ = scene
    make_visit(r1, day(1), {'u2': 2, SECRET_UID: 3})
    item = body(api_get(client, refuge_visits_url(r1.pk), user_claims('u1')))['result'][0]
    assert (item['total_visitors'], item['is_visitor'], item['num_visitors']) == (5, False, 0)


def test_get_visita_buida_surt_amb_total_0(client, scene):
    r1, _ = scene
    make_visit(r1, day(1))
    item = body(api_get(client, refuge_visits_url(r1.pk), user_claims('u1')))['result'][0]
    assert (item['total_visitors'], item['is_visitor'], item['num_visitors']) == (0, False, 0)


def test_get_refugi_sense_visites_es_llista_buida(client, scene):
    r1, _ = scene
    resp = api_get(client, refuge_visits_url(r1.pk), user_claims('u1'))
    assert resp.status_code == 200 and body(resp) == {'result': []}


@pytest.mark.parametrize('rid', [unknown_id(), 'id-antic-de-firestore', '123'])
def test_get_refugi_inexistent_o_no_uuid_404(client, scene, rid):
    resp = api_get(client, refuge_visits_url(rid), user_claims('u1'))
    assert resp.status_code == 404 and body(resp) == {'error': f'Refugi amb ID {rid} no trobat'}


def test_get_admin_veu_el_mateix_que_un_usuari(client, scene):
    r1, _ = scene
    make_user('adm')
    make_visit(r1, day(1), {'u1': 2})
    item = body(api_get(client, refuge_visits_url(r1.pk), admin_claims('adm')))['result'][0]
    assert (item['total_visitors'], item['is_visitor'], item['num_visitors']) == (2, False, 0)


# =================================== POST ===================================

def test_post_crea_la_visita_201(client, scene):
    r1, _ = scene
    resp = api_post(client, visit_url(r1.pk, day(3)), user_claims('u1'), {'num_visitors': 4})
    assert resp.status_code == 201
    assert body(resp) == {'message': 'Visita creada correctament',
                          'visit': {'date': day(3).isoformat(), 'refuge_id': str(r1.pk), 'total_visitors': 4,
                                    'is_visitor': True, 'num_visitors': 4}}
    vid = visit_id_of(r1, day(3))
    assert participant_rows(vid) == {'u1': 4} and total_of(vid) == 4


def test_post_afegeix_un_segon_visitant_a_la_visita_existent(client, scene):
    r1, _ = scene
    vid = make_visit(r1, day(3), {'u1': 4})
    resp = api_post(client, visit_url(r1.pk, day(3)), user_claims('u2'), {'num_visitors': 2})
    assert resp.status_code == 201
    assert body(resp)['visit']['total_visitors'] == 6 and body(resp)['visit']['num_visitors'] == 2
    assert participant_rows(vid) == {'u1': 4, 'u2': 2} and len(visit_rows(r1)) == 1


def test_post_data_d_avui_es_valida(client, scene):
    r1, _ = scene
    assert api_post(client, visit_url(r1.pk, day(0)), user_claims('u1'), {'num_visitors': 1}).status_code == 201


def test_post_data_a_12_mesos_vista_es_valida_i_l_endema_400(client, scene):
    """D36: com a molt 12 mesos naturals vista (si no, visites que el job no purga mai)."""
    from datetime import timedelta
    from apps.visits.services import MAX_AHEAD_MONTHS, _months_before
    from api.utils.timezone_utils import get_madrid_today
    r1, _ = scene
    limit = _months_before(get_madrid_today(), -MAX_AHEAD_MONTHS)
    assert api_post(client, visit_url(r1.pk, limit), user_claims('u1'), {'num_visitors': 1}).status_code == 201
    resp = api_post(client, visit_url(r1.pk, limit + timedelta(days=1)), user_claims('u1'), {'num_visitors': 1})
    assert resp.status_code == 400
    assert body(resp) == {'error': 'La data de la visita no pot ser a més de 12 mesos vista'}
    assert api_post(client, visit_url(r1.pk, '9999-12-31'), user_claims('u1'), {'num_visitors': 1}).status_code == 400
    assert len(visit_rows()) == 1


def test_post_data_passada_400(client, scene):
    r1, _ = scene
    resp = api_post(client, visit_url(r1.pk, day(-1)), user_claims('u1'), {'num_visitors': 1})
    assert resp.status_code == 400
    assert body(resp) == {'error': 'La data de la visita ha de ser igual o posterior a avui'}
    assert visit_rows() == []


@pytest.mark.parametrize('bad', ['abc', '2030-13-45', '2030-02-30', '18-07-2030'])
def test_post_format_de_data_invalid_400(client, scene, bad):
    r1, _ = scene
    resp = api_post(client, visit_url(r1.pk, bad), user_claims('u1'), {'num_visitors': 1})
    assert resp.status_code == 400 and body(resp) == {'error': 'Format de data invàlid. Utilitza YYYY-MM-DD'}
    assert visit_rows() == []


def test_post_ja_registrat_400_i_no_canvia_res(client, scene):
    r1, _ = scene
    vid = make_visit(r1, day(3), {'u1': 4})
    resp = api_post(client, visit_url(r1.pk, day(3)), user_claims('u1'), {'num_visitors': 1})
    assert resp.status_code == 400 and body(resp) == {'error': 'Ja estàs registrat a aquesta visita'}
    assert participant_rows(vid) == {'u1': 4}


@pytest.mark.parametrize('rid', [unknown_id(), 'id-antic'])
def test_post_refugi_inexistent_o_no_uuid_404(client, scene, rid):
    resp = api_post(client, visit_url(rid, day(3)), user_claims('u1'), {'num_visitors': 1})
    assert resp.status_code == 404 and body(resp) == {'error': f'Refugi amb ID {rid} no trobat'}
    assert visit_rows() == []


@pytest.mark.parametrize('payload', [{}, {'num_visitors': 0}, {'num_visitors': -2}, {'num_visitors': 'a'},
                                     {'num_visitors': 10 ** 9}, None])
def test_post_cos_invalid_400_amb_errors_del_serializer(client, scene, payload):
    r1, _ = scene
    resp = api_post(client, visit_url(r1.pk, day(3)), user_claims('u1'), payload)
    assert resp.status_code == 400 and 'num_visitors' in body(resp)['error']
    assert visit_rows() == []


def test_post_validacio_del_cos_abans_que_l_existencia_del_refugi(client, scene):
    resp = api_post(client, visit_url(unknown_id(), day(3)), user_claims('u1'), {'num_visitors': 0})
    assert resp.status_code == 400


def test_post_refugi_inexistent_abans_que_el_format_de_data(client, scene):
    resp = api_post(client, visit_url(unknown_id(), 'abc'), user_claims('u1'), {'num_visitors': 1})
    assert resp.status_code == 404


def test_post_ignora_un_uid_al_cos_nomes_compta_el_del_token(client, scene):
    r1, _ = scene
    api_post(client, visit_url(r1.pk, day(3)), user_claims('u1'), {'num_visitors': 2, 'uid': 'u2'})
    assert participant_rows(visit_id_of(r1, day(3))) == {'u1': 2}


def test_post_no_toca_visited_refuges_fins_que_passa_el_dia(client, scene):
    r1, _ = scene
    api_post(client, visit_url(r1.pk, day(0)), user_claims('u1'), {'num_visitors': 2})
    assert visited_ids('u1') == []                                          # ho fa el job diari


# =================================== PATCH ===================================

def test_patch_actualitza_nomes_el_propi_num_visitors_200(client, scene):
    r1, _ = scene
    vid = make_visit(r1, day(3), {'u1': 4, 'u2': 2})
    resp = api_patch(client, visit_url(r1.pk, day(3)), user_claims('u1'), {'num_visitors': 1})
    assert resp.status_code == 200
    assert body(resp) == {'message': 'Visita actualitzada correctament',
                          'visit': {'date': day(3).isoformat(), 'refuge_id': str(r1.pk), 'total_visitors': 3,
                                    'is_visitor': True, 'num_visitors': 1}}
    assert participant_rows(vid) == {'u1': 1, 'u2': 2}


def test_patch_no_comprova_la_data_comportament_actual(client, scene):
    r1, _ = scene
    make_visit(r1, day(-3), {'u1': 4})
    assert api_patch(client, visit_url(r1.pk, day(-3)), user_claims('u1'), {'num_visitors': 2}).status_code == 200


def test_patch_no_registrat_400(client, scene):
    r1, _ = scene
    vid = make_visit(r1, day(3), {'u2': 2})
    resp = api_patch(client, visit_url(r1.pk, day(3)), user_claims('u1'), {'num_visitors': 1})
    assert resp.status_code == 400 and body(resp) == {'error': 'No estàs registrat a aquesta visita'}
    assert participant_rows(vid) == {'u2': 2}


@pytest.mark.parametrize('rid,d', [(unknown_id(), day(3)), ('id-antic', day(3)), ('R1', 'abc'), ('R1', day(9))])
def test_patch_visita_o_refugi_inexistent_404(client, scene, rid, d):
    r1, _ = scene
    make_visit(r1, day(3), {'u1': 1})
    rid = r1.pk if rid == 'R1' else rid
    resp = api_patch(client, visit_url(rid, d), user_claims('u1'), {'num_visitors': 2})
    assert resp.status_code == 404 and body(resp) == {'error': 'Visita o refugi no trobat'}


@pytest.mark.parametrize('payload', [{}, {'num_visitors': 0}, {'num_visitors': 'a'}, {'num_visitors': 10 ** 9}])
def test_patch_cos_invalid_400(client, scene, payload):
    r1, _ = scene
    vid = make_visit(r1, day(3), {'u1': 1})
    resp = api_patch(client, visit_url(r1.pk, day(3)), user_claims('u1'), payload)
    assert resp.status_code == 400 and 'num_visitors' in body(resp)['error']
    assert participant_rows(vid) == {'u1': 1}


# =================================== DELETE ===================================

def test_delete_treu_el_visitant_200_amb_missatge(client, scene):
    r1, _ = scene
    vid = make_visit(r1, day(3), {'u1': 4, 'u2': 2})
    resp = api_delete(client, visit_url(r1.pk, day(3)), user_claims('u1'))
    assert resp.status_code == 200 and body(resp) == {'message': 'Visitant eliminat correctament'}
    assert participant_rows(vid) == {'u2': 2} and total_of(vid) == 2


def test_delete_l_ultim_visitant_deixa_la_visita_amb_total_0(client, scene):
    r1, _ = scene
    vid = make_visit(r1, day(3), {'u1': 4})
    assert api_delete(client, visit_url(r1.pk, day(3)), user_claims('u1')).status_code == 200
    assert visit_dates(r1) == [day(3)] and total_of(vid) == 0
    item = body(api_get(client, refuge_visits_url(r1.pk), user_claims('u1')))['result'][0]
    assert (item['total_visitors'], item['is_visitor']) == (0, False)


def test_delete_no_registrat_400(client, scene):
    r1, _ = scene
    vid = make_visit(r1, day(3), {'u2': 2})
    resp = api_delete(client, visit_url(r1.pk, day(3)), user_claims('u1'))
    assert resp.status_code == 400 and body(resp) == {'error': 'No estàs registrat a aquesta visita'}
    assert participant_rows(vid) == {'u2': 2}


@pytest.mark.parametrize('rid,d', [(unknown_id(), day(3)), ('id-antic', day(3)), ('R1', 'abc'), ('R1', day(9))])
def test_delete_visita_inexistent_404(client, scene, rid, d):
    r1, _ = scene
    make_visit(r1, day(3), {'u1': 1})
    rid = r1.pk if rid == 'R1' else rid
    resp = api_delete(client, visit_url(rid, d), user_claims('u1'))
    assert resp.status_code == 404 and body(resp) == {'error': 'Visita no trobada'}


def test_delete_pot_tornar_a_apuntar_se_despres(client, scene):
    r1, _ = scene
    api_post(client, visit_url(r1.pk, day(3)), user_claims('u1'), {'num_visitors': 2})
    api_delete(client, visit_url(r1.pk, day(3)), user_claims('u1'))
    assert api_post(client, visit_url(r1.pk, day(3)), user_claims('u1'), {'num_visitors': 5}).status_code == 201
    assert len(visit_rows(r1)) == 1


# =================================== GET /users/{uid}/visits/ ===================================

def test_get_visites_de_l_usuari_totes_en_ordre_descendent(client, scene):
    r1, r2 = scene
    make_visit(r1, day(-10), {'u1': 1})
    make_visit(r1, day(5), {'u1': 2, 'u2': 3, SECRET_UID: 1})
    make_visit(r2, day(2), {'u2': 7})                                       # no hi participa
    make_visit(r2, day(-3), {'u1': 4})
    resp = api_get(client, user_visits_url('u1'), user_claims('u1'))
    assert resp.status_code == 200 and set(body(resp)) == {'result'}
    assert body(resp)['result'] == [
        {'date': day(5).isoformat(), 'refuge_id': str(r1.pk), 'total_visitors': 6, 'is_visitor': True,
         'num_visitors': 2},
        {'date': day(-3).isoformat(), 'refuge_id': str(r2.pk), 'total_visitors': 4, 'is_visitor': True,
         'num_visitors': 4},
        {'date': day(-10).isoformat(), 'refuge_id': str(r1.pk), 'total_visitors': 1, 'is_visitor': True,
         'num_visitors': 1},
    ]
    assert SECRET_UID not in resp.content.decode()


def test_get_visites_de_l_usuari_sense_visites(client, scene):
    resp = api_get(client, user_visits_url('u1'), user_claims('u1'))
    assert resp.status_code == 200 and body(resp) == {'result': []}


def test_visites_buides_no_surten_a_les_de_l_usuari(client, scene):
    r1, _ = scene
    make_visit(r1, day(1))
    assert body(api_get(client, user_visits_url('u1'), user_claims('u1'))) == {'result': []}


def test_dates_iguals_a_dos_refugis_surten_totes_dues(client, scene):
    r1, r2 = scene
    make_visit(r1, day(1), {'u1': 1})
    make_visit(r2, day(1), {'u1': 2})
    ids = {v['refuge_id'] for v in body(api_get(client, user_visits_url('u1'), user_claims('u1')))['result']}
    assert ids == {str(r1.pk), str(r2.pk)}


# =================================== Flux complet ===================================

def test_flux_complet_post_patch_get_delete(client, scene):
    r1, _ = scene
    u1, u2 = user_claims('u1'), user_claims('u2')
    assert api_post(client, visit_url(r1.pk, day(4)), u1, {'num_visitors': 3}).status_code == 201
    assert api_post(client, visit_url(r1.pk, day(4)), u2, {'num_visitors': 2}).status_code == 201
    assert api_patch(client, visit_url(r1.pk, day(4)), u1, {'num_visitors': 5}).status_code == 200
    mine = body(api_get(client, refuge_visits_url(r1.pk), u1))['result'][0]
    theirs = body(api_get(client, refuge_visits_url(r1.pk), u2))['result'][0]
    assert (mine['total_visitors'], mine['num_visitors']) == (7, 5)
    assert (theirs['total_visitors'], theirs['num_visitors']) == (7, 2)
    assert api_delete(client, visit_url(r1.pk, day(4)), u2).status_code == 200
    assert body(api_get(client, user_visits_url('u1'), u1))['result'][0]['total_visitors'] == 5
    assert body(api_get(client, user_visits_url('u2'), u2)) == {'result': []}


def test_la_data_d_avui_es_la_de_madrid_i_no_la_d_utc(client, scene):
    """A les 00:30 de Madrid (23:30 UTC del dia abans) el dia «UTC» ja es el passat per al POST."""
    from datetime import datetime, timedelta, timezone as dt_tz
    from unittest import mock
    r1, _ = scene
    instant = datetime(2026, 3, 10, 23, 30, tzinfo=dt_tz.utc)               # 11/03 00:30 a Madrid
    with mock.patch('django.utils.timezone.now', return_value=instant):
        past = api_post(client, visit_url(r1.pk, instant.date()), user_claims('u1'), {'num_visitors': 1})
        ok = api_post(client, visit_url(r1.pk, instant.date() + timedelta(days=1)), user_claims('u1'),
                      {'num_visitors': 1})
    assert (past.status_code, ok.status_code) == (400, 201)
