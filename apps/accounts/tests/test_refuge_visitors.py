"""
`visitors` del detall de refugi (§4, §5.2, decisio 5): nomes per a admins, des de `users.user_visited_refuges`.
Substitueix el `[]` provisional del chunk 2 (`apps.refuges.selectors.get_visitor_uids`).
"""
import pytest

from apps.accounts.tests.helpers import (
    FAV, VIS, add_list_row, admin_claims, api_delete, api_get, api_post, make_refuge, make_user, sql, url,
    user_claims)
from apps.core.rls import rls_context

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration,
              pytest.mark.real_permissions]


@pytest.fixture
def world():
    for uid in ('u1', 'u2', 'u3', 'adm'):
        make_user(uid)
    return make_refuge(name='A'), make_refuge(name='B', lat=43)


def detail(r):
    return f'/api/refuges/{r.pk}/'


def test_admin_veu_els_visitants_del_refugi(client, world):
    a, b = world
    add_list_row(VIS, 'u1', a)
    add_list_row(VIS, 'u2', a)
    add_list_row(VIS, 'u3', b)
    data = api_get(client, detail(a), admin_claims('adm')).json()
    assert sorted(data['visitors']) == ['u1', 'u2']
    assert sorted(api_get(client, detail(b), admin_claims('adm')).json()['visitors']) == ['u3']


def test_admin_sense_visitants_veu_llista_buida(client, world):
    a, _ = world
    assert api_get(client, detail(a), admin_claims('adm')).json()['visitors'] == []


@pytest.mark.parametrize('claims', [None, user_claims('u1'), user_claims('u2')])
def test_els_no_admins_no_reben_la_clau_visitors(client, world, claims):
    a, _ = world
    add_list_row(VIS, 'u1', a)
    data = api_get(client, detail(a), claims).json()
    assert 'visitors' not in data


def test_els_preferits_no_compten_com_a_visitants(client, world):
    a, _ = world
    add_list_row(FAV, 'u1', a)
    assert api_get(client, detail(a), admin_claims('adm')).json()['visitors'] == []


def test_visitar_i_deixar_de_visitar_es_reflecteix_al_detall(client, world):
    a, _ = world
    assert api_post(client, url('u1', VIS), user_claims('u1'), {'refuge_id': str(a.pk)}).status_code == 200
    assert api_get(client, detail(a), admin_claims('adm')).json()['visitors'] == ['u1']
    assert api_delete(client, url('u1', VIS, a.pk), user_claims('u1')).status_code == 204
    assert api_get(client, detail(a), admin_claims('adm')).json()['visitors'] == []


def test_esborrar_un_usuari_el_treu_dels_visitants(client, world):
    a, _ = world
    add_list_row(VIS, 'u1', a)
    add_list_row(VIS, 'u2', a)
    sql("DELETE FROM users.users WHERE uid = 'u1'")
    assert api_get(client, detail(a), admin_claims('adm')).json()['visitors'] == ['u2']


def test_selector_get_visitor_uids_amb_context_d_admin_i_normal(world):
    from apps.refuges import selectors
    a, _ = world
    add_list_row(VIS, 'u1', a)
    add_list_row(VIS, 'u2', a)
    with rls_context(uid='adm', is_admin=True):
        assert sorted(selectors.get_visitor_uids(a.pk)) == ['u1', 'u2']
    with rls_context(uid='u3'):
        assert selectors.get_visitor_uids(a.pk) == []                  # la RLS no deixa veure'ls
    with rls_context(uid='u1'):
        assert selectors.get_visitor_uids(a.pk) == ['u1']              # nomes la fila propia


def test_get_visitor_uids_accepta_string(world):
    from apps.refuges import selectors
    a, _ = world
    add_list_row(VIS, 'u1', a)
    with rls_context(uid='adm', is_admin=True):
        assert selectors.get_visitor_uids(str(a.pk)) == ['u1']
