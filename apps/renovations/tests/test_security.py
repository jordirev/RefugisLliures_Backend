"""
Revisió de seguretat del chunk 5 (Reformes): forats trobats i comprovacions addicionals sobre les vistes reals
(rol `app` + RLS). Complementa `test_views_contract.py` i `test_rls.py`.

- Cap entrada mal formada (NUL, UID enorme, injecció SQL) pot donar 500.
- `group_link` només accepta http/https (sense espais ni caràcters de control) i mai es filtra a tercers, tampoc a les
  respostes 409 de solapament.
- Els camps de propietat i d'estat (`creator_uid`, `refuge_id`, `participants_uids`, `expelled_uids`) no es poden injectar
  pel cos.
"""
import pytest
from django.db import connection

from apps.renovations.tests.helpers import (
    BASE_KEYS, RENOVATIONS, admin_claims, api_delete, api_get, api_patch, api_post, count_renovations, day,
    expelled_of, link_of, make_renovation, new_body, participants_of, reno_url, renovation_row, user_claims)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration,
              pytest.mark.real_permissions]


def claims(uid):
    return admin_claims(uid) if uid == 'adm' else user_claims(uid)


def GET(client, path, uid):
    return api_get(client, path, claims(uid))


def POST(client, path, uid, body=None):
    return api_post(client, path, claims(uid), body)


def PATCH(client, path, uid, body=None):
    return api_patch(client, path, claims(uid), body)


def DELETE(client, path, uid):
    return api_delete(client, path, claims(uid))


@pytest.fixture
def crew(world):
    """Reforma d'`u1` amb participants `u2` i `u3` i expulsat `u4`."""
    world.rid = make_renovation(world.refuge, 'u1', participants=['u2', 'u3'], expelled=['u4'],
                                link='https://t.me/privat')
    return world


# ------------------------------------------------ entrades mal formades: mai 500 ------------------------------------

@pytest.mark.parametrize('uid', ['%00', 'a%00b', 'x' * 5000, "'; DROP TABLE activity.renovations;--",
                                 "' OR '1'='1", '..', '%E2%80%AE'])
@pytest.mark.parametrize('requester', ['u1', 'u3'])
def test_delete_participant_amb_uid_estrany_no_es_500(client, crew, uid, requester):
    r = DELETE(client, reno_url(crew.rid, 'participants', uid), requester)
    assert r.status_code in (403, 404), r.content
    assert participants_of(crew.rid) == ['u2', 'u3'] and expelled_of(crew.rid) == ['u4']
    assert count_renovations() == 1


@pytest.mark.parametrize('rid', ['%00', "' OR 1=1--", '00000000-0000-0000-0000-00000000000%00', 'x' * 5000,
                                 '0190aaaa-bbbb-cccc-dddd-eeeeeeeeeeee;DROP'])
def test_id_de_reforma_estrany_404_a_tots_els_metodes(client, crew, rid):
    for call in (lambda: GET(client, reno_url(rid), 'u1'), lambda: PATCH(client, reno_url(rid), 'u1', {}),
                 lambda: DELETE(client, reno_url(rid), 'u1'), lambda: POST(client, reno_url(rid, 'participants'), 'u2'),
                 lambda: DELETE(client, reno_url(rid, 'participants', 'u2'), 'u1')):
        assert call().status_code == 404
    assert count_renovations() == 1


@pytest.mark.parametrize('field', ['description', 'materials_needed', 'refuge_id', 'group_link'])
def test_nul_al_cos_400_i_no_500(client, crew, field):
    value = 'https://t.me/a\x00b' if field == 'group_link' else 'a\x00b'
    assert POST(client, RENOVATIONS, 'u2', new_body(crew.refuge2, **{field: value})).status_code in (400, 404)
    if field != 'refuge_id':
        assert PATCH(client, reno_url(crew.rid), 'u1', {field: value}).status_code == 400
    assert count_renovations() == 1 and link_of(crew.rid) == 'https://t.me/privat'


def test_query_active_only_estranya_no_es_500(client, crew):
    for value in ('%00', "x' OR 1=1", 'a' * 5000):
        assert GET(client, f'/api/refuges/{crew.refuge.pk}/renovations/?active_only={value}', 'u1').status_code == 200


# ------------------------------------------------ group_link: esquema, caràcters i longitud --------------------------

BAD_LINKS = [
    'javascript:alert(1)', 'JAVASCRIPT:alert(1)', 'data:text/html;base64,PHNjcmlwdD4=', 'vbscript:x',
    'file:///etc/passwd', 'ftp://x/y', '//evil.example/x', 'http:/x', 'http//x', 'https:evil',
    ' javascript:alert(1)', 'https://', 'https://a b.example/x', 'https://a.example/x\nSet-Cookie: a=b',
    'https://a.example/\r\nX: y', 'https://a.example/\tx', 'x' * 10, '', '   ',
    'https://' + 'a' * 2050 + '.org', 'https://a.example/' + 'p' * 2048,
]


@pytest.mark.parametrize('link', BAD_LINKS)
def test_group_link_dolent_400_a_post_i_patch_i_no_es_desa(client, crew, link):
    assert POST(client, RENOVATIONS, 'u2', new_body(crew.refuge2, group_link=link)).status_code == 400
    assert PATCH(client, reno_url(crew.rid), 'u1', {'group_link': link}).status_code == 400
    assert count_renovations() == 1 and link_of(crew.rid) == 'https://t.me/privat'


@pytest.mark.parametrize('link', ['https://chat.whatsapp.com/abc', 'http://t.me/x', 'HTTPS://T.ME/X',
                                  'https://t.me/joinchat/AAAA?x=1&y=2#f', 'https://a.example/' + 'p' * 2000])
def test_group_link_bo_es_desa_i_nomes_el_veu_qui_hi_te_dret(client, crew, link):
    r = PATCH(client, reno_url(crew.rid), 'u1', {'group_link': link})
    assert r.status_code == 200 and r.json()['group_link'] == link and link_of(crew.rid) == link
    assert 'group_link' not in GET(client, reno_url(crew.rid), 'u4').json()


def test_group_link_amb_espais_al_voltant_es_retalla(client, crew):
    r = PATCH(client, reno_url(crew.rid), 'u1', {'group_link': '  https://t.me/x  '})
    assert r.status_code == 200 and link_of(crew.rid) == 'https://t.me/x'


# ------------------------------------------------ filtracions de group_link ------------------------------------------

def test_cap_resposta_409_filtra_group_link_a_un_tercer(client, world):
    make_renovation(world.refuge, 'u2', ini=day(5), fin=day(9), link='https://t.me/secret', participants=['u3'])
    # POST d'un aliè que se solapa
    r = POST(client, RENOVATIONS, 'u1', new_body(world.refuge, ini_date=day(6).isoformat()))
    assert r.status_code == 409 and 'secret' not in r.content.decode()
    assert set(r.json()['overlapping_renovation']) == BASE_KEYS
    # PATCH d'un aliè que se solapa amb la d'`u2`
    mine = make_renovation(world.refuge, 'u1', ini=day(20), fin=day(22), link='https://t.me/meu')
    r = PATCH(client, reno_url(mine), 'u1', {'ini_date': day(8).isoformat(), 'fin_date': day(21).isoformat()})
    assert r.status_code == 409 and 'secret' not in r.content.decode()
    assert set(r.json()['overlapping_renovation']) == BASE_KEYS
    # un participant de l'altra, sí que el veu
    r = POST(client, RENOVATIONS, 'u3', new_body(world.refuge, ini_date=day(6).isoformat()))
    assert r.status_code == 409 and r.json()['overlapping_renovation']['group_link'] == 'https://t.me/secret'


def test_un_expulsat_no_veu_l_enllac_ni_sap_que_ho_es_a_cap_lectura(client, crew):
    bodies = [GET(client, RENOVATIONS, 'u4').content, GET(client, reno_url(crew.rid), 'u4').content,
              GET(client, f'/api/refuges/{crew.refuge.pk}/renovations/', 'u4').content]
    for body in bodies:
        assert b'expelled' not in body and b'privat' not in body and b'group_link' not in body
    assert b'u4' not in bodies[1]            # ni apareix a la llista de participants


def test_unir_se_no_revela_res_a_un_expulsat_mes_enlla_del_403(client, crew):
    r = POST(client, reno_url(crew.rid, 'participants'), 'u4')
    assert r.status_code == 403 and 'privat' not in r.content.decode() and 'group_link' not in r.json()
    assert participants_of(crew.rid) == ['u2', 'u3']


# ------------------------------------------------ propietat: injecció pel cos i IDOR ---------------------------------

INJECT = {'creator_uid': 'u3', 'participants_uids': ['u3', 'u4'], 'expelled_uids': ['u2'],
          'id': '0190aaaa-bbbb-7ccc-8ddd-eeeeeeeeeeee', 'created_at': '2000-01-01T00:00:00Z', 'is_admin': True,
          'user_uid': 'u3', 'renovation_id': 'x'}


def test_patch_no_pot_injectar_camps_de_propietat_ni_d_estat(client, crew):
    before = renovation_row(crew.rid)
    body = dict(INJECT, refuge_id=str(crew.refuge2.pk), description='nova')
    r = PATCH(client, reno_url(crew.rid), 'u1', body)
    assert r.status_code == 200 and r.json()['participants_uids'] == ['u2', 'u3']
    assert renovation_row(crew.rid) == dict(before, description='nova')
    assert participants_of(crew.rid) == ['u2', 'u3'] and expelled_of(crew.rid) == ['u4']


@pytest.mark.parametrize('uid', ['u2', 'u3', 'u4', 'adm'])
def test_patch_i_delete_d_un_tercer_no_toquen_res_ni_amb_cos_malici(client, crew, uid):
    before = renovation_row(crew.rid)
    body = dict(INJECT, refuge_id=str(crew.refuge2.pk), description='robat', group_link='https://evil.example/')
    assert PATCH(client, reno_url(crew.rid), uid, body).status_code == 403
    assert DELETE(client, reno_url(crew.rid), uid).status_code == 403
    assert renovation_row(crew.rid) == before and link_of(crew.rid) == 'https://t.me/privat'
    assert participants_of(crew.rid) == ['u2', 'u3'] and expelled_of(crew.rid) == ['u4']


def test_post_no_pot_injectar_creador_participants_ni_expulsats(client, world):
    body = new_body(world.refuge, **INJECT)
    r = POST(client, RENOVATIONS, 'u2', body)
    assert r.status_code == 201
    data = r.json()
    assert data['creator_uid'] == 'u2' and data['participants_uids'] == [] and data['id'] != INJECT['id']
    assert expelled_of(data['id']) == [] and renovation_row(data['id'])['created_at'].year != 2000


def test_un_participant_nomes_pot_treure_se_a_si_mateix(client, crew):
    assert DELETE(client, reno_url(crew.rid, 'participants', 'u3'), 'u2').status_code == 403
    assert DELETE(client, reno_url(crew.rid, 'participants', 'u1'), 'u2').status_code == 403
    assert participants_of(crew.rid) == ['u2', 'u3'] and expelled_of(crew.rid) == ['u4']
    assert DELETE(client, reno_url(crew.rid, 'participants', 'u2'), 'u2').status_code == 200
    assert participants_of(crew.rid) == ['u3'] and expelled_of(crew.rid) == ['u4']


def test_unir_se_usa_sempre_el_uid_del_token_i_no_el_del_cos_ni_la_query(client, crew):
    r = api_post(client, reno_url(crew.rid, 'participants') + '?uid=u2&user_uid=u2', claims('adm'),
                 {'uid': 'u2', 'user_uid': 'u2'})
    assert r.status_code == 200
    assert participants_of(crew.rid) == ['u2', 'u3', 'adm']


# ------------------------------------------------ BD: grants, SECURITY DEFINER i escalada -----------------------------

def test_app_no_pot_crear_objectes_als_schemas():
    with connection.cursor() as cur:
        cur.execute("SELECT has_schema_privilege('app', 'activity', 'CREATE'), "
                    "has_schema_privilege('app', 'public', 'CREATE')")
        assert cur.fetchone() == (False, False)


@pytest.mark.parametrize('fn', ['fn_renovation_anonymize', 'fn_renovation_requires_link',
                                'fn_renovation_member_guard'])
def test_les_funcions_security_definer_son_de_trigger_amb_search_path_fix(fn):
    with connection.cursor() as cur:
        cur.execute("SELECT p.prosecdef, p.proconfig, t.typname FROM pg_proc p "
                    "JOIN pg_namespace n ON n.oid = p.pronamespace JOIN pg_type t ON t.oid = p.prorettype "
                    "WHERE n.nspname = 'activity' AND p.proname = %s", [fn])
        secdef, config, ret = cur.fetchone()
    assert secdef and ret == 'trigger'                   # no es poden cridar directament amb `SELECT fn()`
    assert config and any(c.startswith('search_path=pg_catalog') for c in config)
    assert not any('public' in c or '$user' in c for c in config)


def test_app_no_es_superusuari_ni_bypassrls_i_les_taules_tenen_rls():
    with connection.cursor() as cur:
        cur.execute("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = 'app'")
        assert cur.fetchone() == (False, False)
        cur.execute("SELECT count(*) FROM pg_tables WHERE schemaname = 'activity' AND tablename LIKE 'renovation%%' "
                    "AND tableowner = 'app'")
        assert cur.fetchone()[0] == 0
        cur.execute("SELECT relname, relrowsecurity FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE n.nspname = 'activity' AND relname LIKE 'renovation%%' AND relkind = 'r'")
        rows = cur.fetchall()
    assert len(rows) == 4 and all(rls for _, rls in rows)
