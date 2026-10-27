"""
Revisió de seguretat del chunk 7 (pujades): forats que els altres tests no cobrien.

- Guarda estàtica contra injecció SQL a `apps/uploads` (cap `.raw()`, `.extra()`, `RawSQL` ni `execute()` amb SQL no literal).
- La comanda de purga no rep cap entrada de l'usuari.
- IDOR: confirmar l'intent d'un altre és indistinguible d'un intent inexistent; una `experience_id` o `refuge_id`
  falsificada no permet penjar mitjans a l'experiència d'un altre ni a un altre refugi.
- Identificadors estranys (claus, NUL, claus UUID escrites de maneres diferents): mai 500, mai un mitjà duplicat.
- Dues confirmacions concurrents del mateix intent es serialitzen (`SELECT ... FOR UPDATE`).
- La resposta i el log no porten UIDs d'altres usuaris.
"""
import ast
import logging
import pathlib
import uuid

import pytest
from django.db import DatabaseError, connection, transaction
from django.test.utils import CaptureQueriesContext

from apps.core.rls import rls_context
from apps.experiences.tests.helpers import make_experience
from apps.uploads import services
from apps.uploads.tests.helpers import (
    CONFIRM, INTENTS, admin_claims, api_post, file_spec, intent_body, intent_row, make_intent, make_jpeg_with_gps,
    refuge_media_rows, sql, user_claims)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration,
              pytest.mark.real_permissions]

APP_DIR = pathlib.Path(services.__file__).parent


def _sources():
    for path in APP_DIR.rglob('*.py'):
        if 'tests' in path.parts or 'migrations' in path.parts:
            continue
        yield path


def _literal(node):
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def test_cap_raw_extra_rawsql_ni_execute_amb_sql_no_literal():
    offenders = []
    for path in _sources():
        tree = ast.parse(path.read_text(encoding='utf-8'))
        constants = {t.id for n in ast.walk(tree) if isinstance(n, ast.Assign) and _literal(n.value)
                     for t in n.targets if isinstance(t, ast.Name)}
        for node in ast.walk(tree):
            if isinstance(node, (ast.Name, ast.Attribute)) and getattr(node, 'id', getattr(node, 'attr', '')) == 'RawSQL':
                offenders.append(f'{path.name}:{node.lineno} RawSQL')
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in ('raw', 'extra'):
                    offenders.append(f'{path.name}:{node.lineno} .{node.func.attr}()')
                if node.func.attr in ('execute', 'executemany') and node.args:
                    arg = node.args[0]
                    # literal, o una constant de mòdul que és un literal (p. ex. PURGE_SQL)
                    if not (_literal(arg) or (isinstance(arg, ast.Name) and arg.id in constants)):
                        offenders.append(f'{path.name}:{node.lineno} execute() amb SQL no literal')
    assert not offenders, offenders


def test_la_comanda_de_purga_no_rep_arguments():
    from apps.uploads.management.commands.purge_upload_intents import Command
    parser = Command().create_parser('manage.py', 'purge_upload_intents')
    custom = [a.dest for a in parser._actions if a.dest not in {
        'help', 'version', 'verbosity', 'settings', 'pythonpath', 'traceback', 'no_color', 'force_color',
        'skip_checks'}]
    assert custom == []


@pytest.fixture
def scene(world):
    return world


def _confirm(client, ids, claims=None):
    return api_post(client, CONFIRM, claims or user_claims('u1'), {'upload_ids': ids})


# ---------- IDOR ----------

def test_confirmar_l_intent_d_un_altre_es_missing_object_i_no_toca_res(client, scene, r2store):
    r = scene[0]
    iid = make_intent('u2', 'refuge', r)
    r2store.put_quarantine(iid, make_jpeg_with_gps((800, 600), orientation=1))
    before = intent_row(iid)
    resp = _confirm(client, [iid, str(uuid.uuid4())])
    assert resp.status_code == 200
    assert [f['reason'] for f in resp.json()['failed']] == ['missing_object', 'missing_object']
    assert resp.json()['uploaded'] == []
    assert intent_row(iid) == before and refuge_media_rows(r) == []
    assert f'quarantine/{iid}' in r2store.store                      # no s'esborra la quarantena d'un altre
    assert 'u2' not in resp.content.decode()


def test_admin_tampoc_confirma_l_intent_d_un_altre(client, scene, r2store):
    iid = make_intent('u2', 'refuge', scene[0])
    r2store.put_quarantine(iid, make_jpeg_with_gps((800, 600), orientation=1))
    resp = _confirm(client, [iid], admin_claims('adm'))
    assert resp.json()['failed'] == [{'upload_id': iid, 'reason': 'missing_object'}]
    assert refuge_media_rows(scene[0]) == [] and intent_row(iid)['status'] == 'pending'


def test_experience_id_falsificada_no_crea_intents_ni_mitjans(client, scene):
    r1, r2_ = scene
    exp = make_experience(r1, 'u2')
    resp = api_post(client, INTENTS, user_claims('u1'), intent_body('experience', experience_id=exp))
    assert resp.status_code == 403 and resp.json()['code'] == 'not_owner'
    assert sql('SELECT count(*) FROM moderation.upload_intents')[0][0] == 0
    # refuge_id que no és el de l'experiència pròpia: 400
    own = make_experience(r1, 'u1')
    resp = api_post(client, INTENTS, user_claims('u1'), intent_body('experience', refuge=r2_, experience_id=own))
    assert resp.status_code == 400
    assert sql('SELECT count(*) FROM moderation.upload_intents')[0][0] == 0


def test_intent_d_avatar_ignora_refuge_i_experience_del_cos(client, scene):
    exp = make_experience(scene[0], 'u2')
    body = intent_body('avatar', refuge=scene[0], experience_id=exp)
    resp = api_post(client, INTENTS, user_claims('u1'), body)
    assert resp.status_code == 201
    row = intent_row(resp.json()['uploads'][0]['upload_id'])
    assert row['user_uid'] == 'u1' and row['refuge_id'] is None and row['experience_id'] is None


def test_la_url_put_no_porta_uids_i_la_quarantena_no_la_tria_el_client(client, scene):
    body = intent_body('refuge', refuge=scene[0], files=[file_spec(), file_spec('image/png', 99)])
    resp = api_post(client, INTENTS, user_claims('u1'), body)
    assert resp.status_code == 201
    for up in resp.json()['uploads']:
        assert f"quarantine/{up['upload_id']}?" in up['put_url']
        assert 'u1' not in up['put_url'].split('?')[0]
        assert intent_row(up['upload_id'])['quarantine_key'] == f"quarantine/{up['upload_id']}"


# ---------- Identificadors estranys ----------

@pytest.mark.parametrize('bad', [
    'a\x00b', '../../etc/passwd', 'quarantine/x', '%00', '١٢٣', '‮', 'x' * 128, ' ',
    "'; DROP TABLE x;--", '00000000-0000-0000-0000-00000000000g',
])
def test_upload_id_estrany_es_missing_object_mai_500(client, scene, bad):
    resp = _confirm(client, [bad])
    assert resp.status_code in (200, 400), resp.content
    if resp.status_code == 200:
        assert resp.json()['failed'][0]['reason'] == 'missing_object'


@pytest.mark.parametrize('bad', ['a\x00b', '../x', "1' OR '1'='1", '١' * 36, 'x' * 5000])
def test_experience_i_refuge_id_estranys_a_les_pujades_mai_500(client, scene, bad):
    for body in (intent_body('experience', experience_id=bad), intent_body('refuge', refuge=bad)):
        resp = api_post(client, INTENTS, user_claims('u1'), body)
        assert resp.status_code in (400, 404), resp.content


def test_el_mateix_upload_id_escrit_de_maneres_diferents_es_processa_una_sola_vegada(client, scene, r2store):
    r = scene[0]
    iid = make_intent('u1', 'refuge', r)
    r2store.put_quarantine(iid, make_jpeg_with_gps((800, 600), orientation=1))
    variants = [iid, iid.upper(), iid.replace('-', ''), '{' + iid + '}', 'urn:uuid:' + iid]
    resp = _confirm(client, variants)
    assert resp.status_code == 200, resp.content
    assert len(resp.json()['uploaded']) == 1 and resp.json()['failed'] == []
    assert len(refuge_media_rows(r)) == 1


# ---------- Concurrència ----------

def test_la_confirmacio_bloqueja_la_fila_de_l_intent(client, scene, r2store):
    """`SELECT ... FOR UPDATE`: dues confirmacions simultànies del mateix intent no publiquen dos mitjans."""
    iid = make_intent('u1', 'refuge', scene[0])
    r2store.put_quarantine(iid, make_jpeg_with_gps((800, 600), orientation=1))
    with CaptureQueriesContext(connection) as ctx:
        assert _confirm(client, [iid]).status_code == 200
    selects = [q['sql'] for q in ctx.captured_queries if 'FROM "moderation"."upload_intents"' in q['sql']
               and q['sql'].lstrip().upper().startswith('SELECT')]
    assert selects and 'FOR UPDATE' in selects[0]


# ---------- RLS (rol app): mitjans a experiències alienes ----------

class _Rollback(Exception):
    pass


@pytest.mark.parametrize('ctx, allowed', [
    ({'uid': 'u1'}, False), ({'uid': 'adm', 'is_admin': True}, True), ({}, False), ({'system': True}, True)])
def test_rls_mitjans_a_l_experiencia_d_un_altre(scene, ctx, allowed):
    exp = make_experience(scene[0], 'u2')
    stmt = ("INSERT INTO refuges.refuge_media (key, refuge_id, creator_uid, experience_id, media_type, content_type, "
            "width, height, size_bytes, rights_confirmed_at) VALUES ('k/forged.webp', %s, 'u1', %s, 'image', "
            "'image/webp', 1, 1, 1, now())")
    try:
        with transaction.atomic():
            with rls_context(**ctx), connection.cursor() as cur:
                cur.execute(stmt, [scene[0].pk, exp])
            raise _Rollback
    except _Rollback:
        ok = True
    except DatabaseError:
        ok = False
    assert ok is allowed


# ---------- Logs ----------

def test_cap_uid_d_un_altre_als_logs_en_confirmar(client, scene, r2store, caplog):
    iid = make_intent('u2', 'refuge', scene[0])
    r2store.put_quarantine(iid, make_jpeg_with_gps((800, 600), orientation=1))
    with caplog.at_level(logging.DEBUG):
        _confirm(client, [iid])
    assert 'u2' not in caplog.text
