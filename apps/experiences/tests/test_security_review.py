"""
Revisió de seguretat del chunk 7 (experiències): forats que els altres tests no cobrien.

- Guarda estàtica contra injecció SQL a `apps/experiences` (cap `.raw()`, `.extra()`, `RawSQL` ni `execute()` no literal).
- Permisos de cada mètode (POST/PATCH amb bloqueig i edat; GET i DELETE només perfil) i propietat (`not_owner`).
- Identificadors estranys a la URL i al cos (NUL, `../`, Unicode, SQL): 400/404, mai 500.
- Assignació massiva: el cos no pot canviar `creator_uid`, `refuge_id`, `id` ni `modified_at`.
- Dades personals: mitjans amagats d'altres (clau, URL prefirmada) no surten a la llista ni als logs; el context de
  sistema de l'esborrat es tanca sempre, també si R2 falla.
"""
import ast
import logging
import pathlib

import pytest
from django.db import connection

from apps.core.rls import rls_context

from apps.experiences import services
from apps.experiences.tests.helpers import (
    NOT_OWNER, ZERO_UUID, admin_claims, api_delete, api_get, api_patch, api_post, exp_ids, exp_row, exp_url, fail_r2,
    list_url, make_exp_media, make_experience, make_user, media_keys_of, new_body, sql, user_claims)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration,
              pytest.mark.real_permissions]

APP_DIR = pathlib.Path(services.__file__).parent


def _literal(node):
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def test_cap_raw_extra_rawsql_ni_execute_amb_sql_no_literal():
    offenders = []
    for path in APP_DIR.rglob('*.py'):
        if 'tests' in path.parts or 'migrations' in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Name, ast.Attribute)) and getattr(node, 'id', getattr(node, 'attr', '')) == 'RawSQL':
                offenders.append(f'{path.name}:{node.lineno} RawSQL')
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in ('raw', 'extra'):
                    offenders.append(f'{path.name}:{node.lineno} .{node.func.attr}()')
                if node.func.attr in ('execute', 'executemany') and node.args and not _literal(node.args[0]):
                    offenders.append(f'{path.name}:{node.lineno} execute() amb SQL no literal')
    assert not offenders, offenders


def test_permisos_declarats_a_cada_metode():
    from rest_framework.permissions import IsAuthenticated
    from api.permissions import HasProfile, IsAgeConfirmed, IsNotBlocked
    from apps.experiences import views
    from rest_framework.test import APIRequestFactory
    from rest_framework.request import Request
    factory = APIRequestFactory()
    for view_cls in (views.ExperienceListAPIView, views.ExperienceDetailAPIView):
        for method, expected in (('post', [IsAuthenticated, HasProfile, IsNotBlocked, IsAgeConfirmed]),
                                 ('patch', [IsAuthenticated, HasProfile, IsNotBlocked, IsAgeConfirmed]),
                                 ('get', [IsAuthenticated, HasProfile]),
                                 ('delete', [IsAuthenticated, HasProfile])):
            view = view_cls()
            view.request = Request(getattr(factory, method)('/'))
            assert [type(p) for p in view.get_permissions()] == expected, (view_cls, method)


@pytest.fixture
def scene(world):
    return world


# ---------- Autenticació i bloqueig ----------

def test_anonim_no_pot_res(client, scene):
    exp = make_experience(scene[0], 'u1')
    for resp in (client.get(list_url(scene[0].pk)), client.post('/api/experiences/', {}),
                 client.patch(exp_url(exp), {}, content_type='application/json'), client.delete(exp_url(exp))):
        assert resp.status_code in (401, 403)
    assert exp_ids() == [exp]


def test_bloquejat_pot_esborrar_la_seva_pero_no_crear_ni_editar(client, scene):
    r = scene[0]
    make_user('b1', is_blocked=True)
    mine = make_experience(r, 'b1', comment='meva')
    b = user_claims('b1')
    assert api_post(client, '/api/experiences/', b, new_body(r)).status_code == 403
    assert api_patch(client, exp_url(mine), b, {'comment': 'nou'}).status_code == 403
    assert exp_row(mine)['comment'] == 'meva'
    assert api_delete(client, exp_url(mine), b).status_code == 200


# ---------- Propietat ----------

def test_editar_o_esborrar_l_experiencia_d_un_altre_es_403_not_owner_i_no_canvia_res(client, scene):
    exp = make_experience(scene[0], 'u2', comment='original')
    for fn, args in ((api_patch, ({'comment': 'hackejat', 'condition': 0},)), (api_delete, ())):
        resp = fn(client, exp_url(exp), user_claims('u1'), *args)
        assert resp.status_code == 403 and resp.json()['code'] == NOT_OWNER
    assert exp_row(exp)['comment'] == 'original' and exp_ids() == [exp]


def test_l_admin_si_pot_editar_i_esborrar(client, scene):
    exp = make_experience(scene[0], 'u2')
    assert api_patch(client, exp_url(exp), admin_claims('adm'), {'comment': 'moderat'}).status_code == 200
    assert exp_row(exp)['comment'] == 'moderat'
    assert api_delete(client, exp_url(exp), admin_claims('adm')).status_code == 200


def test_cos_no_pot_canviar_creador_refugi_id_ni_data(client, scene):
    r1, r2_ = scene
    exp = make_experience(r1, 'u1')
    before = exp_row(exp)
    resp = api_patch(client, exp_url(exp), user_claims('u1'), {
        'comment': 'ok', 'creator_uid': 'u2', 'refuge_id': str(r2_.pk), 'id': ZERO_UUID,
        'modified_at': '2000-01-01T00:00:00Z', 'created_at': '2000-01-01T00:00:00Z'})
    assert resp.status_code == 200
    after = exp_row(exp)
    for col in ('id', 'refuge_id', 'creator_uid', 'created_at'):
        assert after[col] == before[col]
    assert after['modified_at'] > before['modified_at'] or after['modified_at'].year > 2000
    created = api_post(client, '/api/experiences/', user_claims('u1'), {**new_body(r1), 'creator_uid': 'u2'})
    assert created.status_code == 201 and created.json()['experience']['creator_uid'] == 'u1'


# ---------- Identificadors estranys ----------

WEIRD = ['a%00b', '..%2F..%2Fetc%2Fpasswd', "1'%20OR%20'1'='1", '%D9%A1%D9%A2%D9%A3', '%E2%80%AE', 'x' * 300,
         '%20', '{' + ZERO_UUID + '}', 'null']


@pytest.mark.parametrize('bad', WEIRD)
def test_id_estrany_a_la_url_es_404_mai_500(client, scene, bad):
    make_experience(scene[0], 'u1')
    path = f'/api/experiences/{bad}/'
    u = user_claims('u1')
    assert api_patch(client, path, u, {'comment': 'x'}).status_code in (404, 400)
    assert api_delete(client, path, u).status_code in (404, 400)
    assert len(exp_ids()) == 1


@pytest.mark.parametrize('bad', ['a\x00b', '../x', "1' OR '1'='1", '١' * 36, 'x' * 5000, 0, None, [], {}])
def test_refuge_id_estrany_al_cos_i_a_la_consulta_mai_500(client, scene, bad):
    body = {'refuge_id': bad, 'comment': 'x', 'condition': 1}
    assert api_post(client, '/api/experiences/', user_claims('u1'), body).status_code in (400, 404)
    if isinstance(bad, str):
        resp = client.get('/api/experiences/', {'refuge_id': bad}, HTTP_AUTHORIZATION='Bearer t')
        assert resp.status_code in (400, 401, 404)
        from unittest.mock import patch
        from apps.experiences.tests.helpers import VERIFY
        with patch(VERIFY, return_value=user_claims('u1')):
            resp = client.get('/api/experiences/', {'refuge_id': bad}, HTTP_AUTHORIZATION='Bearer t')
        assert resp.status_code in (400, 404)
    assert exp_ids() == []


@pytest.mark.parametrize('body', [
    {'comment': 'a\x00b', 'condition': 1}, {'comment': 'x' * 100000, 'condition': 1}, {'comment': '   ', 'condition': 1},
    {'comment': 'x', 'condition': 10 ** 30}, {'comment': 'x', 'condition': True}, {'comment': 'x', 'condition': 1.5},
    {'comment': ['x'], 'condition': 1}, {'comment': 'x', 'condition': '1; DROP TABLE x'}, [], 'text',
])
def test_cos_extrem_es_400_i_no_crea_res(client, scene, body):
    body = body if not isinstance(body, dict) else {'refuge_id': str(scene[0].pk), **body}
    assert api_post(client, '/api/experiences/', user_claims('u1'), body).status_code == 400
    assert exp_ids() == []


def test_comentari_amb_html_i_sql_es_desa_literal(client, scene):
    text = "<script>alert(1)</script>'); DROP TABLE activity.experiences;--"
    resp = api_post(client, '/api/experiences/', user_claims('u1'), new_body(scene[0], comment=text))
    assert resp.status_code == 201 and resp.json()['experience']['comment'] == text
    assert exp_row(resp.json()['experience']['id'])['comment'] == text


# ---------- Dades personals / mitjans amagats ----------

def test_mitjans_amagats_d_un_altre_no_surten_a_la_llista_ni_es_prefirmen(client, scene, r2):
    r = scene[0]
    exp = make_experience(r, 'u2')
    make_exp_media(r, 'u2', exp, key='k/visible.webp', status='visible', minutes=1)
    make_exp_media(r, 'u2', exp, key='k/secret-hidden.webp', status='hidden_pending_review', minutes=2)
    resp = api_get(client, list_url(r.pk), user_claims('u1'))
    assert resp.status_code == 200
    body = resp.content.decode()
    assert 'secret-hidden' not in body
    assert [m['key'] for m in resp.json()['experiences'][0]['images_metadata']] == ['k/visible.webp']
    # l'admin sí que el veu; l'autor també
    assert 'secret-hidden' in api_get(client, list_url(r.pk), admin_claims('adm')).content.decode()
    assert 'secret-hidden' in api_get(client, list_url(r.pk), user_claims('u2')).content.decode()


def test_patch_d_un_altre_no_filtra_res_i_la_resposta_403_no_porta_dades(client, scene):
    exp = make_experience(scene[0], 'uid-secret-u2', comment='privat?')
    make_user('uid-secret-u2')
    resp = api_patch(client, exp_url(exp), user_claims('u1'), {'comment': 'x'})
    assert resp.status_code == 403 and 'uid-secret-u2' not in resp.content.decode()
    assert 'privat' not in resp.content.decode()


def test_els_logs_d_un_error_no_porten_claus_ni_uids_d_altres(client, scene, r2, caplog):
    r = scene[0]
    exp = make_experience(r, 'u1')
    make_user('uid-secret-u2')
    make_exp_media(r, 'uid-secret-u2', exp, key='k/uid-secret-key.webp', status='hidden_pending_review')
    fail_r2(r2)
    with caplog.at_level(logging.DEBUG):
        resp = api_delete(client, exp_url(exp), user_claims('u1'))
    assert resp.status_code == 500 and set(resp.json()) == {'error', 'error_id'}
    assert 'uid-secret-key' not in resp.content.decode()
    assert exp_ids() == [exp] and media_keys_of(exp) == ['k/uid-secret-key.webp']


# ---------- Context de RLS ----------

def _is_system():
    with connection.cursor() as cur:
        cur.execute('SELECT core.is_system()')
        return cur.fetchone()[0]


@pytest.mark.parametrize('fails', [False, True])
def test_l_esborrat_tanca_el_context_de_sistema_encara_que_r2_falli(scene, r2, fails):
    exp = make_experience(scene[0], 'u1')
    make_exp_media(scene[0], 'u1', exp, key='k/a.webp')
    if fails:
        fail_r2(r2)
    assert not _is_system()
    try:
        with rls_context(uid='u1'):
            services.delete_experience(experience_id=exp, actor_uid='u1', is_admin=False)
    except services.MediaStorageError:
        assert fails
    assert not _is_system()


def test_l_esborrat_bloqueja_l_experiencia_abans_de_llegir_les_claus(scene, r2):
    """Un mitjà confirmat concurrentment no pot quedar orfe a R2: `SELECT ... FOR UPDATE` de l'experiència."""
    from django.test.utils import CaptureQueriesContext
    exp = make_experience(scene[0], 'u1')
    with CaptureQueriesContext(connection) as ctx, rls_context(uid='u1'):
        services.delete_experience(experience_id=exp, actor_uid='u1')
    sqls = [q['sql'] for q in ctx.captured_queries]
    lock = next(i for i, s in enumerate(sqls) if 'FOR UPDATE' in s and 'activity"."experiences' in s)
    media = next(i for i, s in enumerate(sqls) if 'refuge_media' in s and s.lstrip().upper().startswith('SELECT'))
    assert lock < media
