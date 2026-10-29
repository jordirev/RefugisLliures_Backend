"""
Visites buides (trigger `AFTER DELETE` de `activity.refuge_visit_participants`; migració `visits.0002`).

Decisio del PO: una visita sense participants s'esborra de la BD en el mateix moment en que se'n va l'ultim (ja no cal el
job). Com que `app` nomes pot esborrar visites com a sistema (§2.10), ho fa un trigger `SECURITY DEFINER` per sentencia
(`activity.fn_visit_drop_if_empty`) que agafa el bloqueig assessor `activity.fn_visit_lock(refugi, data)` abans de
comprovar si queda algu. Cobreix `remove_visitor`, la cascada d'`users.users` i qualsevol altre `DELETE` de participants.
"""
from unittest import mock

import pytest
from django.db import DatabaseError, connection, transaction

from apps.core.rls import rls_context, system_context
from apps.visits.tests.helpers import (
    PARTS, TOTALS, VISITS, api_delete, api_get, api_post, day, make_refuge, make_user, make_visit, participant_rows,
    refuge_visits_url, sql, total_of, user_claims, user_visits_url, visit_id_of, visit_rows, visit_services,
    visit_url)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.integration, pytest.mark.real_permissions]


@pytest.fixture
def scene():
    for u in ('u1', 'u2', 'u3'):
        make_user(u)
    return make_refuge(name='R1'), make_refuge(name='R2', lat=43)


def ids():
    return [r[0] for r in visit_rows()]


# ---------- remove_visitor ----------

def test_treure_l_ultim_participant_esborra_la_visita(scene):
    r1, _ = scene
    vid = make_visit(r1, day(2), {'u1': 3})
    with rls_context(uid='u1'):
        visit_services().remove_visitor('u1', r1.pk, day(2))
    assert visit_rows(r1) == [] and participant_rows(vid) == {}
    assert sql(f'SELECT count(*) FROM {TOTALS} WHERE visit_id = %s', [vid]) == [(0,)]


def test_treure_un_participant_quan_en_queden_d_altres_no_esborra_la_visita(scene):
    r1, _ = scene
    vid = make_visit(r1, day(2), {'u1': 3, 'u2': 2})
    with rls_context(uid='u1'):
        visit_services().remove_visitor('u1', r1.pk, day(2))
    assert [r[0] for r in visit_rows(r1)] == [vid]
    assert participant_rows(vid) == {'u2': 2} and total_of(vid) == 2


def test_nomes_s_esborra_la_visita_que_s_ha_quedat_buida(scene):
    r1, r2 = scene
    make_visit(r1, day(2), {'u1': 1})
    b = make_visit(r1, day(3), {'u1': 1, 'u2': 1})
    c = make_visit(r2, day(2), {'u1': 1})
    with rls_context(uid='u1'):
        visit_services().remove_visitor('u1', r1.pk, day(2))
    assert set(ids()) == {b, c}


def test_es_pot_tornar_a_apuntar_despres_de_que_la_visita_s_esborri(scene):
    r1, _ = scene
    make_visit(r1, day(2), {'u1': 3})
    S = visit_services()
    with rls_context(uid='u1'):
        S.remove_visitor('u1', r1.pk, day(2))
    with rls_context(uid='u2'):
        v = S.create_visit('u2', r1.pk, day(2), 4)
    assert (v.total_visitors, v.is_visitor, v.num_visitors) == (4, True, 4)
    assert len(visit_rows(r1)) == 1


# ---------- esborrat d'usuari (cascada users.users -> participants) ----------

def test_delete_user_que_era_l_unic_participant_esborra_la_visita(scene):
    r1, r2 = scene
    make_visit(r1, day(2), {'u1': 3})
    shared = make_visit(r2, day(2), {'u1': 1, 'u2': 2})
    from apps.accounts import services as accounts
    with mock.patch.object(accounts, '_delete_firebase_account'):
        accounts.delete_user('u1')
    assert ids() == [shared]
    assert participant_rows(shared) == {'u2': 2} and total_of(shared) == 2


def test_delete_usuari_per_http_esborra_les_visites_que_deixa_buides(client, scene):
    r1, _ = scene
    make_visit(r1, day(2), {'u1': 3})
    shared = make_visit(r1, day(3), {'u1': 1, 'u2': 2})
    assert api_delete(client, '/api/users/u1/', user_claims('u1')).status_code == 204
    assert [r[0] for r in visit_rows(r1)] == [shared]
    items = api_get(client, refuge_visits_url(r1.pk), user_claims('u2')).json()['result']
    assert [(i['date'], i['total_visitors']) for i in items] == [(str(day(3)), 2)]


def test_delete_d_un_usuari_amb_moltes_visites_les_buida_totes(scene):
    r1, r2 = scene
    for i in range(1, 6):
        make_visit(r1, day(i), {'u1': 1})
    keep = make_visit(r2, day(1), {'u1': 1, 'u3': 1})
    sql('DELETE FROM users.users WHERE uid = %s', ['u1'])
    assert ids() == [keep]


# ---------- qualsevol altre DELETE de participants ----------

def test_delete_directe_de_participants_com_a_sistema_esborra_la_visita_buida(scene):
    r1, _ = scene
    vid = make_visit(r1, day(2), {'u1': 1, 'u2': 1})
    sql(f'DELETE FROM {PARTS} WHERE visit_id = %s', [vid])
    assert visit_rows(r1) == []


def test_delete_de_diverses_files_deixa_la_visita_si_en_queda_alguna(scene):
    r1, _ = scene
    vid = make_visit(r1, day(2), {'u1': 1, 'u2': 1, 'u3': 1})
    sql(f'DELETE FROM {PARTS} WHERE visit_id = %s AND user_uid <> %s', [vid, 'u3'])
    assert [r[0] for r in visit_rows(r1)] == [vid] and participant_rows(vid) == {'u3': 1}


def test_un_update_de_participants_no_esborra_res(scene):
    r1, _ = scene
    vid = make_visit(r1, day(2), {'u1': 1})
    with rls_context(uid='u1'):
        visit_services().update_visit('u1', r1.pk, day(2), 5)
    assert [r[0] for r in visit_rows(r1)] == [vid] and participant_rows(vid) == {'u1': 5}


def test_delete_que_no_esborra_cap_fila_no_fa_res(scene):
    r1, _ = scene
    vid = make_visit(r1, day(2), {'u1': 1})
    with rls_context(uid='u2'):                                  # la RLS amaga la fila d'u1: 0 files esborrades
        with connection.cursor() as cur:
            cur.execute(f'DELETE FROM {PARTS} WHERE visit_id = %s', [vid])
            assert cur.rowcount == 0
    assert [r[0] for r in visit_rows(r1)] == [vid]


def test_el_trigger_no_toca_les_visites_buides_que_no_han_perdut_cap_participant(scene):
    """Una visita buida inserida a ma (cap DELETE de participants) no la toca el trigger; la purga de 12 mesos la treu."""
    r1, _ = scene
    empty = make_visit(r1, day(2))
    other = make_visit(r1, day(3), {'u1': 1})
    with rls_context(uid='u1'):
        visit_services().remove_visitor('u1', r1.pk, day(3))
    assert ids() == [empty] and other not in ids()


# ---------- RLS i seguretat de la funcio ----------

def test_app_no_pot_esborrar_visites_directament(scene):
    r1, _ = scene
    vid = make_visit(r1, day(2), {'u1': 1})
    for ctx in ({'uid': 'u1'}, {'uid': 'adm', 'is_admin': True}, {}):
        with rls_context(**ctx):
            with connection.cursor() as cur:
                cur.execute(f'DELETE FROM {VISITS} WHERE id = %s', [vid])
                assert cur.rowcount == 0
    assert [r[0] for r in visit_rows(r1)] == [vid]


def test_app_no_pot_cridar_la_funcio_del_trigger(scene):
    with rls_context(uid='u1'):
        with pytest.raises(DatabaseError):
            with transaction.atomic():
                with connection.cursor() as cur:
                    cur.execute('SELECT activity.fn_visit_drop_if_empty()')


# ---------- purga de visites senceres (cascada visita -> participants) ----------

def test_esborrar_visites_senceres_no_falla_ni_fa_res_de_mes(scene):
    r1, r2 = scene
    old = make_visit(r1, day(-400), {'u1': 1, 'u2': 1})
    keep = make_visit(r2, day(2), {'u3': 1})
    assert visit_services().purge_old_visits() == 1
    assert ids() == [keep]
    assert participant_rows(old) == {} and participant_rows(keep) == {'u3': 1}


def test_esborrar_un_refugi_cascadeja_visites_i_participants_sense_error(scene):
    r1, _ = scene
    make_visit(r1, day(2), {'u1': 1})
    sql('DELETE FROM refuges.refuges WHERE id = %s', [r1.pk])
    assert visit_rows() == [] and participant_rows() == {}


# ---------- contracte HTTP ----------

def test_http_apuntar_sortir_i_tornar_a_apuntar(client, scene):
    r1, _ = scene
    url = visit_url(r1.pk, day(2))
    assert api_post(client, url, user_claims('u1'), {'num_visitors': 3}).status_code == 201
    assert api_post(client, url, user_claims('u2'), {'num_visitors': 2}).json()['visit']['total_visitors'] == 5
    assert api_delete(client, url, user_claims('u1')).status_code == 200
    item = api_get(client, refuge_visits_url(r1.pk), user_claims('u1')).json()['result'][0]
    assert (item['total_visitors'], item['is_visitor']) == (2, False)
    resp = api_delete(client, url, user_claims('u2'))
    assert resp.status_code == 200 and resp.json() == {'message': 'Visitant eliminat correctament'}
    assert visit_id_of(r1, day(2)) is None
    assert api_get(client, refuge_visits_url(r1.pk), user_claims('u1')).json() == {'result': []}
    assert api_get(client, user_visits_url('u2'), user_claims('u2')).json() == {'result': []}
    # ja no hi ha visita: DELETE torna a donar 404 i es pot tornar a crear
    assert api_delete(client, url, user_claims('u2')).status_code == 404
    again = api_post(client, url, user_claims('u2'), {'num_visitors': 1})
    assert again.status_code == 201 and again.json()['visit']['total_visitors'] == 1


def test_delete_http_no_deixa_el_total_mal_per_als_qui_queden(client, scene):
    r1, _ = scene
    make_visit(r1, day(2), {'u1': 3, 'u2': 2, 'u3': 4})
    api_delete(client, visit_url(r1.pk, day(2)), user_claims('u1'))
    item = api_get(client, refuge_visits_url(r1.pk), user_claims('u2')).json()['result'][0]
    assert (item['total_visitors'], item['is_visitor'], item['num_visitors']) == (6, True, 2)
