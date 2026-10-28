"""
`GET /api/users/{uid}/moderation-notices/` (chunk 9; DSA art. 17): avisos de moderació d'un usuari.

Contracte (com avui): 200 `{notices: [...]}`, cada avís amb `NOTICE_KEYS` (`uid` = l'usuari afectat, `redress` = text
constant, no es desa); ordre `created_at DESC, id DESC`. Permisos: `IsAuthenticated, HasProfile, IsSameUser`: només
l'afectat; **un altre usuari és 403 i un admin també** (la vista d'avui, `IsSameUser`; la RLS sí que deixa llegir-los a
l'admin, però l'endpoint no ho exposa — vegeu la pregunta oberta a l'informe). Màxim 2 consultes (perfil + avisos).
"""
import re

import pytest

from apps.moderation.tests.helpers import (
    NOTICE_KEYS, NOTICE_TYPES, REDRESS, QueryCounter, admin_claims, api_get, at, make_notice, make_report, notices_url,
    user_claims)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration,
              pytest.mark.real_permissions]


def get(client, uid='u1', as_uid=None):
    return api_get(client, notices_url(uid), user_claims(as_uid or uid))


def test_anonim_es_401(client, world):
    assert client.get(notices_url('u1')).status_code == 401


def test_sense_perfil_es_403_profile_required(client, world):
    resp = api_get(client, notices_url('fantasma'), user_claims('fantasma'))
    assert resp.status_code == 403 and resp.json()['error'] == 'profile_required'


def test_un_altre_usuari_es_403_i_no_veu_res(client, world):
    make_notice('u1')
    resp = get(client, 'u1', as_uid='u2')
    assert resp.status_code == 403 and 'notices' not in resp.json()


def test_un_admin_no_llegeix_els_avisos_d_un_altre_per_aquest_endpoint(client, world):
    make_notice('u1')
    resp = api_get(client, notices_url('u1'), admin_claims('adm'))
    assert resp.status_code == 403


def test_sense_avisos(client, world):
    resp = get(client)
    assert resp.status_code == 200 and resp.json() == {'notices': []}


def test_forma_d_un_avis_complet(client, world):
    r = world[0]
    rid = make_report(r, 'k', 'u2', creator='u1')
    nid = make_notice('u1', 'strike', statement='Has infringit les normes', refuge=r, media_key='k',
                      reason='hate_speech', action='remove_and_strike', report_id=rid, strikes=2, minutes=5)
    [n] = get(client).json()['notices']
    assert set(n) == NOTICE_KEYS
    assert n['id'] == nid and n['uid'] == 'u1' and n['type'] == 'strike' and n['statement'] == 'Has infringit les normes'
    assert (n['refuge_id'], n['media_key'], n['reason'], n['action'], n['report_id']) == (
        str(r.pk), 'k', 'hate_speech', 'remove_and_strike', rid)
    assert (n['automated'], n['strikes']) == (False, 2)
    assert n['redress'] == REDRESS
    assert re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}.*\+0[12]:00$', n['created_at'])


def test_camps_opcionals_buits_surten_com_a_null(client, world):
    make_notice('u1', 'content_hidden', automated=True)
    [n] = get(client).json()['notices']
    assert (n['refuge_id'], n['media_key'], n['reason'], n['action'], n['report_id'], n['strikes']) == (None,) * 6
    assert n['automated'] is True and n['redress'] == REDRESS


@pytest.mark.parametrize('type_', NOTICE_TYPES)
def test_tots_els_tipus(client, world, type_):
    make_notice('u1', type_)
    assert get(client).json()['notices'][0]['type'] == type_


def test_ordre_mes_recents_primer_i_desempat_per_id_descendent(client, world):
    old = make_notice('u1', minutes=0)
    new = make_notice('u1', minutes=30)
    tie_a = make_notice('u1', minutes=10, notice_id='00000000-0000-7000-8000-00000000000a')
    tie_b = make_notice('u1', minutes=10, notice_id='00000000-0000-7000-8000-00000000000b')
    assert [n['id'] for n in get(client).json()['notices']] == [new, tie_b, tie_a, old]


def test_nomes_els_avisos_de_l_usuari(client, world):
    mine = make_notice('u1')
    make_notice('u2', 'strike')
    assert [n['id'] for n in get(client).json()['notices']] == [mine]
    assert [n['uid'] for n in get(client, 'u2').json()['notices']] == ['u2']


def test_avis_amb_refugi_esborrat_es_consulta_amb_refuge_id_null(client, world):
    from apps.moderation.tests.helpers import as_owner, sql
    make_notice('u1', refuge=world[1], media_key='k')
    with as_owner():
        sql('DELETE FROM refuges.refuges WHERE id = %s', [world[1].pk])
    [n] = get(client).json()['notices']
    assert n['refuge_id'] is None and n['media_key'] == 'k'


def test_pressupost_de_consultes_constant(client, world):
    make_notice('u1', minutes=0)
    with QueryCounter() as q1:
        assert get(client).status_code == 200
    for i in range(1, 25):
        make_notice('u1', minutes=i)
    with QueryCounter() as q2:
        resp = get(client)
    assert len(resp.json()['notices']) == 25
    assert q1.count == q2.count <= 2, (q1.queries, q2.queries)
