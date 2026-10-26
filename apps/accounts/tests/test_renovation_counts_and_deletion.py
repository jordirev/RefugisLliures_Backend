"""
Reformes dins `accounts` (chunk 5): comptador `num_renovated_refuges` del perfil propi (U1, D19, §4) i esborrat d'usuari
(`DELETE /users/{uid}/`, §8.4, D21). Rol `app` + RLS reals.

Contracte:
- `apps.accounts.selectors.get_legacy_counts(uid)` continua retornant
  `{'num_shared_experiences': int, 'num_renovated_refuges': int}`, però **`num_renovated_refuges` surt de PostgreSQL**:
  reformes creades + reformes on l'usuari és participant (passades i vigents; els expulsats no compten). Ja no es fa cap
  `count()` de Firestore sobre `renovations`. Les experiències continuen a Firestore fins al chunk 7: el selector
  segueix usant `apps.accounts.selectors._firestore_count(collection, field, op, value)` només per a elles. Els tests
  d'aquest fitxer porten el marker `real_legacy_counts`, que només mocka aquesta funció (i falla si algú li demana
  `renovations`).
- `apps.accounts.services._firestore_steps(uid)` ja no té els 4 passos de reformes ('reformes actuals', 'reformes
  anonimitzades', 'participacions en reformes', 'expulsions de reformes').
- `delete_user(uid)` fa, dins el mateix *savepoint* que `DELETE users.users` (i el compte de Firebase): esborra les
  reformes vigents del creador (`fin_date >= avui de Madrid`; cascada a participants, expulsats i enllaç); les passades
  queden anònimes per la FK `SET NULL` i el *trigger* esborra l'enllaç; les seves participacions i expulsions
  s'esborren per cascada. Si Firebase falla, es desfà tot (reformes incloses).
"""
from unittest.mock import patch

import pytest

from apps.accounts.tests.helpers import (
    admin_claims, api_delete, api_get, api_patch, count_all, make_refuge, sql, url, user_claims, user_row,
    QueryCounter)
from apps.renovations.tests.helpers import (
    LINK, make_user, day, expelled_of, link_of, make_renovation, participants_of, reno_url, renovation_row)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration,
              pytest.mark.real_permissions, pytest.mark.real_legacy_counts]


@pytest.fixture
def world():
    for uid in ('u1', 'u2', 'u3', 'u4'):
        make_user(uid, username=uid)
    from types import SimpleNamespace
    return SimpleNamespace(r1=make_refuge(name='R1'), r2=make_refuge(name='R2', lat=43), r3=make_refuge(name='R3', lat=44),
                           r4=make_refuge(name='R4', lat=45))


def own_profile(client, uid):
    resp = api_get(client, url(uid), user_claims(uid))
    assert resp.status_code == 200, resp.content
    return resp.json()


# =============================================== num_renovated_refuges ===============================================

def test_zero_sense_reformes(client, world):
    assert own_profile(client, 'u1')['num_renovated_refuges'] == 0


def test_compta_creades_mes_unides_incloses_les_passades(client, world):
    make_renovation(world.r1, 'u1', ini=day(2), fin=day(4))                                  # creada vigent
    make_renovation(world.r2, 'u1', ini=day(-20), fin=day(-10))                             # creada passada
    make_renovation(world.r3, 'u2', ini=day(2), fin=day(4), participants=['u1'])            # unida
    make_renovation(world.r4, 'u2', ini=day(-9), fin=day(-5), participants=['u1'])          # unida passada
    assert own_profile(client, 'u1')['num_renovated_refuges'] == 4
    assert own_profile(client, 'u2')['num_renovated_refuges'] == 2


def test_un_expulsat_no_compta(client, world):
    make_renovation(world.r1, 'u2', participants=['u3'], expelled=['u4'])
    assert own_profile(client, 'u4')['num_renovated_refuges'] == 0
    assert own_profile(client, 'u3')['num_renovated_refuges'] == 1


def test_compta_reformes_diferents_no_usuaris_diferents(client, world):
    make_renovation(world.r1, 'u1', ini=day(2), fin=day(3), participants=['u2', 'u3'])
    assert [own_profile(client, u)['num_renovated_refuges'] for u in ('u1', 'u2', 'u3', 'u4')] == [1, 1, 1, 0]


def test_el_flux_http_actualitza_el_comptador(client, world):
    from apps.renovations.tests.helpers import RENOVATIONS, api_post, new_body
    from apps.accounts.tests.helpers import api_delete as delete
    body = new_body(world.r1)
    created = api_post(client, RENOVATIONS, user_claims('u1'), body)
    assert created.status_code == 201
    rid = created.json()['id']
    assert own_profile(client, 'u1')['num_renovated_refuges'] == 1
    assert api_post(client, reno_url(rid, 'participants'), user_claims('u2'), None).status_code == 200
    assert own_profile(client, 'u2')['num_renovated_refuges'] == 1
    assert delete(client, reno_url(rid, 'participants', 'u2'), user_claims('u2')).status_code == 200      # surt
    assert own_profile(client, 'u2')['num_renovated_refuges'] == 0
    assert api_post(client, reno_url(rid, 'participants'), user_claims('u3'), None).status_code == 200
    assert delete(client, reno_url(rid, 'participants', 'u3'), user_claims('u1')).status_code == 200      # expulsat
    assert own_profile(client, 'u3')['num_renovated_refuges'] == 0
    assert delete(client, reno_url(rid), user_claims('u1')).status_code == 204                            # esborrada
    assert own_profile(client, 'u1')['num_renovated_refuges'] == 0


def test_patch_del_perfil_tambe_retorna_el_comptador(client, world):
    make_renovation(world.r1, 'u1')
    resp = api_patch(client, url('u1'), user_claims('u1'), {'username': 'Nou'})
    assert resp.status_code == 200 and resp.json()['num_renovated_refuges'] == 1


def test_no_es_demana_res_de_reformes_a_firestore(client, world, legacy_counts):
    make_renovation(world.r1, 'u1')
    own_profile(client, 'u1')
    assert all(call.args[0] == 'experiences' for call in legacy_counts.call_args_list), legacy_counts.call_args_list


def test_les_experiencies_segueixen_venint_de_firestore(client, world, legacy_counts):
    legacy_counts.side_effect = lambda collection, *a: 7 if collection == 'experiences' else 99
    make_renovation(world.r1, 'u1')
    profile = own_profile(client, 'u1')
    assert profile['num_shared_experiences'] == 7 and profile['num_renovated_refuges'] == 1


def test_el_perfil_propi_no_depen_de_firestore_per_a_les_reformes(client, world, legacy_counts):
    """U1: si Firestore falla només pot afectar les experiències, mai el recompte de reformes."""
    legacy_counts.side_effect = lambda collection, *a: 0
    make_renovation(world.r1, 'u1')
    assert own_profile(client, 'u1')['num_renovated_refuges'] == 1


def test_perfil_aliè_no_te_comptadors_ni_consulta_reformes(client, world):
    make_renovation(world.r1, 'u2')
    resp = api_get(client, url('u2'), user_claims('u1'))
    assert resp.status_code == 200 and set(resp.json()) == {'uid', 'username', 'avatar_metadata'}


def test_selector_get_legacy_counts_directe(world):
    from apps.accounts import selectors
    from apps.core.rls import rls_context
    make_renovation(world.r1, 'u1')
    make_renovation(world.r2, 'u2', participants=['u1'])
    with rls_context(uid='u1'):
        counts = selectors.get_legacy_counts('u1')
    assert counts == {'num_shared_experiences': 0, 'num_renovated_refuges': 2}


def test_comptador_amb_pressupost_de_consultes_constant(client, world):
    """Cap N+1 ni consulta extra per reforma: el recompte de consultes no depèn de quantes en té l'usuari."""
    results = []
    for n in (1, 12):
        for i in range(n):
            make_renovation(world.r1, 'u1', ini=day(i * 4 + 1), fin=day(i * 4 + 2), participants=['u2'])
        with QueryCounter() as q:
            resp = api_get(client, url('u1'), user_claims('u1'))
        assert resp.status_code == 200 and resp.json()['num_renovated_refuges'] == n
        results.append(q.count)
        sql('DELETE FROM activity.renovations')
    assert results[0] == results[1] and results[0] <= 3, results


# =============================================== esborrat d'usuari ===============================================

STEPS = [
    'api.controllers.experience_controller.ExperienceController.delete_experiences_by_creator',
    'api.controllers.doubt_controller.DoubtController.delete_doubts_by_creator',
    'api.controllers.doubt_controller.DoubtController.delete_answers_by_creator',
    'api.controllers.refuge_proposal_controller.RefugeProposalController.anonymize_proposals_by_creator',
    'api.controllers.refuge_visit_controller.RefugeVisitController.remove_user_from_all_visits',
]
RENOVATION_STEP_NAMES = {'reformes actuals', 'reformes anonimitzades', 'participacions en reformes',
                         'expulsions de reformes'}


@pytest.fixture
def firestore_steps():
    """Passos que continuen a Firestore (dominis encara no migrats): es mocken i retornen èxit. Els que ja no
    existeixen (p. ex. quan es fusioni el chunk de visites) s'ometen."""
    started = []
    for target in STEPS:
        try:
            p = patch(target, return_value=(True, None))
            started.append((p, p.start()))
        except (AttributeError, ImportError, ModuleNotFoundError):
            continue
    yield [m for _, m in started]
    for p, _ in started:
        p.stop()


@pytest.fixture
def scene(world):
    """`u1` crea una vigent (amb participant i expulsat), una que acaba avui, i una de passada (amb participant i
    expulsat); participa a una vigent d'`u2` i està expulsat d'una altra d'`u2`. `u3` participa a la passada d'`u1`."""
    s = world
    s.current = make_renovation(s.r1, 'u1', ini=day(2), fin=day(6), participants=['u2'], expelled=['u4'])
    s.ends_today = make_renovation(s.r2, 'u1', ini=day(-3), fin=day(0), participants=['u3'])
    s.past = make_renovation(s.r3, 'u1', ini=day(-30), fin=day(-10), participants=['u3'], expelled=['u4'],
                             link='https://t.me/passada')
    s.other = make_renovation(s.r4, 'u2', ini=day(2), fin=day(6), participants=['u1', 'u3'], expelled=[])
    s.other2 = make_renovation(s.r1, 'u2', ini=day(20), fin=day(25), participants=['u3'], expelled=['u1'])
    return s


def test_delete_pas_de_reformes_ja_no_son_a_firestore(world):
    from apps.accounts import services
    names = {name for name, _ in services._firestore_steps('u1')}
    assert not names & RENOVATION_STEP_NAMES, names


def test_delete_no_crida_cap_controller_de_reformes(client, scene, firestore_steps):
    try:
        from api.controllers.renovation_controller import RenovationController
    except ImportError:                                                  # el chunk 11 l'eliminarà del tot
        assert api_delete(client, url('u1'), user_claims('u1')).status_code == 204
        return
    with patch.object(RenovationController, '__init__', side_effect=AssertionError('les reformes ja no van a Firestore')) as ctor:
        assert api_delete(client, url('u1'), user_claims('u1')).status_code == 204
    ctor.assert_not_called()


def test_delete_esborra_les_vigents_i_anonimitza_les_passades(client, scene, firestore_steps):
    resp = api_delete(client, url('u1'), user_claims('u1'))
    assert resp.status_code == 204 and resp.content == b''
    # Vigents (inclosa la que acaba avui): fora, amb tot el que penja (participants, expulsats, enllaç).
    for rid in (scene.current, scene.ends_today):
        assert renovation_row(rid) is None, rid
        assert (participants_of(rid), expelled_of(rid), link_of(rid)) == ([], [], None)
    # Passada: anònima, sense enllaç, i es conserven els altres participants i expulsats.
    row = renovation_row(scene.past)
    assert row is not None and row['creator_uid'] is None
    assert link_of(scene.past) is None
    assert participants_of(scene.past) == ['u3'] and expelled_of(scene.past) == ['u4']
    assert user_row('u1') is None


def test_delete_treu_les_participacions_i_expulsions_de_l_usuari_a_reformes_alienes(client, scene, firestore_steps):
    api_delete(client, url('u1'), user_claims('u1'))
    assert participants_of(scene.other) == ['u3']                      # u1 fora; u3 es queda
    assert expelled_of(scene.other2) == [] and participants_of(scene.other2) == ['u3']
    assert renovation_row(scene.other)['creator_uid'] == 'u2' and renovation_row(scene.other2)['creator_uid'] == 'u2'
    assert link_of(scene.other) == LINK and link_of(scene.other2) == LINK


def test_delete_la_reforma_passada_anonima_surt_a_l_api_com_unknown_sense_enllac(client, scene, firestore_steps):
    api_delete(client, url('u1'), user_claims('u1'))
    data = api_get(client, reno_url(scene.past), user_claims('u3')).json()
    assert data['creator_uid'] == 'unknown' and 'group_link' not in data and data['participants_uids'] == ['u3']
    assert api_get(client, reno_url(scene.current), user_claims('u3')).status_code == 404


def test_delete_el_comptador_dels_altres_es_actualitza(client, scene, firestore_steps):
    assert api_get(client, url('u3'), user_claims('u3')).json()['num_renovated_refuges'] == 4
    api_delete(client, url('u1'), user_claims('u1'))
    # u3 conserva: la passada (ara anònima), l'`other` i l'`other2`; ha perdut la que acabava avui (esborrada).
    assert api_get(client, url('u3'), user_claims('u3')).json()['num_renovated_refuges'] == 3


def test_delete_no_toca_les_reformes_d_altres_usuaris(client, scene, firestore_steps):
    before = renovation_row(scene.other)
    api_delete(client, url('u1'), user_claims('u1'))
    after = renovation_row(scene.other)
    assert after == before


def test_delete_d_un_usuari_sense_reformes_204(client, world, firestore_steps):
    assert api_delete(client, url('u4'), user_claims('u4')).status_code == 204


def test_delete_les_reformes_es_desfan_si_firebase_falla(client, scene, firestore_steps, firebase_accounts):
    """Mateixa transacció que el `DELETE users.users`: si el compte de Firebase no s'esborra, tot es desfà."""
    firebase_accounts.delete_user.side_effect = RuntimeError('firebase caigut')
    resp = api_delete(client, url('u1'), user_claims('u1'))
    assert resp.status_code == 500 and set(resp.json()) == {'error', 'error_id'}
    assert user_row('u1') is not None
    for rid in (scene.current, scene.ends_today, scene.past):
        assert renovation_row(rid)['creator_uid'] == 'u1', rid
        assert link_of(rid) is not None
    assert participants_of(scene.current) == ['u2'] and expelled_of(scene.current) == ['u4']
    assert participants_of(scene.other) == ['u1', 'u3'] and expelled_of(scene.other2) == ['u1']


def test_delete_les_reformes_es_desfan_si_falla_el_delete_dels_passos_de_postgres(client, scene, firestore_steps):
    """Si falla qualsevol sentència de reformes, 500 i res no es perd (un sol savepoint)."""
    from django.db import DatabaseError, connection

    def boom(execute, sql_, params, many, context):
        if sql_.lstrip().upper().startswith('DELETE') and 'users"."users' in sql_:
            raise DatabaseError('fallada simulada')
        return execute(sql_, params, many, context)

    with connection.execute_wrapper(boom):
        resp = api_delete(client, url('u1'), user_claims('u1'))
    assert resp.status_code == 500
    assert renovation_row(scene.current) is not None and user_row('u1') is not None


@pytest.mark.parametrize('claims', [user_claims('u2'), admin_claims('adm')])
def test_delete_d_un_altre_403_i_no_toca_les_reformes(client, scene, firestore_steps, claims):
    if user_row(claims['uid']) is None:                               # `u2` ja existeix al fixture `world`
        make_user(claims['uid'])
    assert api_delete(client, url('u1'), claims).status_code == 403
    assert renovation_row(scene.current) is not None and participants_of(scene.current) == ['u2']


def test_delete_idempotent_les_reformes_no_deixen_files_orfes(client, scene, firestore_steps):
    api_delete(client, url('u1'), user_claims('u1'))
    assert sql("SELECT count(*) FROM activity.renovation_group_links l "
               "WHERE NOT EXISTS (SELECT 1 FROM activity.renovations r WHERE r.id = l.renovation_id)")[0][0] == 0
    assert sql("SELECT count(*) FROM activity.renovations WHERE creator_uid = 'u1'")[0][0] == 0
    assert sql("SELECT count(*) FROM activity.renovation_participants WHERE user_uid = 'u1'")[0][0] == 0
    assert sql("SELECT count(*) FROM activity.renovation_expelled WHERE user_uid = 'u1'")[0][0] == 0
    # Cap enllaç de reformes anònimes (privacitat): les anònimes no en tenen.
    assert sql("SELECT count(*) FROM activity.renovation_group_links l JOIN activity.renovations r "
               "ON r.id = l.renovation_id WHERE r.creator_uid IS NULL")[0][0] == 0
    # Queden la passada (anònima) i les dues d'`u2` (`other`, `other2`); les dues vigents d'`u1` s'han esborrat.
    assert count_all('activity.renovations') == 3


def test_delete_les_vigents_s_esborren_amb_el_dia_de_madrid(client, world, firestore_steps):
    """La vigència és `fin_date >= avui de Madrid` (`get_madrid_today`), mai `CURRENT_DATE` (sessió en UTC)."""
    today_ends = make_renovation(world.r1, 'u1', ini=day(-2), fin=day(0))
    yesterday_ends = make_renovation(world.r2, 'u1', ini=day(-5), fin=day(-1))
    api_delete(client, url('u1'), user_claims('u1'))
    assert renovation_row(today_ends) is None
    assert renovation_row(yesterday_ends)['creator_uid'] is None
