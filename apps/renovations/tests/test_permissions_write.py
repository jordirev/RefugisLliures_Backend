"""
Escriptura de contingut de reformes (decisió del PO, 26/10; gotcha 15): `POST /renovations/`, `PATCH /renovations/{id}/`
i unir-se (`POST /renovations/{id}/participants/`) exigeixen `IsNotBlocked` i `IsAgeConfirmed`, en aquest ordre i
després d'`IsAuthenticated, HasProfile`. Els `GET` i els `DELETE` (esborrar la reforma pròpia, sortir-ne o expulsar
algú) no: un usuari bloquejat o sense l'edat confirmada pot llegir i esborrar el que és seu.
"""
import pytest

from apps.renovations.tests.helpers import (
    api_delete, api_get, api_patch, api_post, count_renovations, day, expelled_of, make_renovation, make_user,
    new_body, participants_of, reno_url, refuge_reno_url, renovation_row, sql, user_claims, RENOVATIONS)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration,
              pytest.mark.real_permissions]

BLOCKED = 'user_blocked'
AGE = 'age_not_confirmed'


@pytest.fixture
def scene(world):
    """`u1` crea una reforma amb el participant `u2`; `blk` està bloquejat i `kid` no ha confirmat l'edat."""
    make_user('blk')
    sql("UPDATE users.users SET is_blocked = true, blocked_reason = 'strikes', blocked_at = now() WHERE uid = 'blk'")
    make_user('kid', age_confirmed_at=None, age_threshold=None)
    world.rid = make_renovation(world.refuge, 'u1', participants=['u2'])
    return world


def _writes(client, w, uid):
    """Les tres escriptures de contingut, com a `uid` (el PATCH sobre una reforma pròpia de `uid`)."""
    mine = make_renovation(w.refuge2, uid, ini=day(30), fin=day(31))
    return [
        api_post(client, RENOVATIONS, user_claims(uid), new_body(w.refuge, ini_date=day(40).isoformat(),
                                                                  fin_date=day(41).isoformat())),
        api_patch(client, reno_url(mine), user_claims(uid), {'description': 'x'}),
        api_post(client, reno_url(w.rid, 'participants'), user_claims(uid), None),
    ]


@pytest.mark.parametrize('uid,code', [('blk', BLOCKED), ('kid', AGE)])
def test_escriptura_de_contingut_denegada_a_bloquejats_i_menors_sense_confirmar(client, scene, uid, code):
    before = count_renovations()
    for resp in _writes(client, scene, uid):
        assert resp.status_code == 403 and resp.json()['error'] == code, resp.content
    assert count_renovations() == before + 1                 # només la reforma pròpia creada pel helper
    assert participants_of(scene.rid) == ['u2']


def test_bloquejat_te_prioritat_sobre_edat_no_confirmada(client, scene):
    make_user('both', age_confirmed_at=None, age_threshold=None)
    sql("UPDATE users.users SET is_blocked = true, blocked_reason = 'strikes', blocked_at = now() WHERE uid = 'both'")
    resp = api_post(client, reno_url(scene.rid, 'participants'), user_claims('both'), None)
    assert resp.status_code == 403 and resp.json()['error'] == BLOCKED


@pytest.mark.parametrize('uid', ['blk', 'kid'])
def test_lectures_permeses(client, scene, uid):
    for path in (RENOVATIONS, reno_url(scene.rid), refuge_reno_url(scene.refuge.pk)):
        assert api_get(client, path, user_claims(uid)).status_code == 200


def test_bloquejat_pot_esborrar_la_seva_reforma(client, scene):
    mine = make_renovation(scene.refuge2, 'blk', ini=day(30), fin=day(31))
    assert api_delete(client, reno_url(mine), user_claims('blk')).status_code == 204
    assert renovation_row(mine) is None


def test_bloquejat_pot_sortir_d_una_reforma(client, scene):
    sql("INSERT INTO activity.renovation_participants (renovation_id, user_uid) VALUES (%s, 'blk')", [scene.rid])
    resp = api_delete(client, reno_url(scene.rid, 'participants', 'blk'), user_claims('blk'))
    assert resp.status_code == 200 and 'blk' not in resp.json()['participants_uids']


def test_bloquejat_creador_pot_expulsar(client, world):
    make_user('blk')
    sql("UPDATE users.users SET is_blocked = true, blocked_reason = 'strikes', blocked_at = now() WHERE uid = 'blk'")
    rid = make_renovation(world.refuge, 'blk', participants=['u2'])
    resp = api_delete(client, reno_url(rid, 'participants', 'u2'), user_claims('blk'))
    assert resp.status_code == 200 and expelled_of(rid) == ['u2']


def test_menor_sense_edat_pot_esborrar_la_seva_reforma(client, scene):
    mine = make_renovation(scene.refuge2, 'kid', ini=day(30), fin=day(31))
    assert api_delete(client, reno_url(mine), user_claims('kid')).status_code == 204


def test_get_permissions_per_metode():
    from types import SimpleNamespace
    from django.urls import resolve
    from rest_framework.permissions import IsAuthenticated
    from apps.auth.permissions import HasProfile, IsAgeConfirmed, IsNotBlocked
    write = [IsAuthenticated, HasProfile, IsNotBlocked, IsAgeConfirmed]
    read = [IsAuthenticated, HasProfile]
    cases = [('/api/renovations/', 'GET', read), ('/api/renovations/', 'POST', write),
             ('/api/renovations/x/', 'GET', read), ('/api/renovations/x/', 'PATCH', write),
             ('/api/renovations/x/', 'DELETE', read), ('/api/renovations/x/participants/', 'POST', write),
             ('/api/renovations/x/participants/u/', 'DELETE', read)]
    for path, method, expected in cases:
        view = resolve(path).func.view_class()
        view.request = SimpleNamespace(method=method)
        assert [type(p) for p in view.get_permissions()] == expected, (path, method)
