"""
Revisió de seguretat del chunk 4 (visites): forats que els altres tests no cobrien.

- Dates mal formades a la URL (salt de línia final, dígits no ASCII, formats laxos): mai 500 i mai s'escriu res.
- Cos amb valors extrems (NaN, Infinity, enters gegants, tipus equivocats): 400, mai 500.
- Guarda estàtica contra injecció SQL: cap `.raw()`, `.extra()`, `RawSQL` ni `execute()` amb SQL formatat a `apps/visits`.
- Cap UID d'un altre participant surt a les respostes ni als logs (nivell DEBUG).
- Un bloquejat o sense edat no arriba mai al servei: no es crea ni la fila de `refuge_visits`.
- El job no deixa el context de sistema obert encara que falli.
"""
import ast
import json
import logging
import pathlib
from unittest.mock import patch

import pytest
from django.db import connection

from apps.core.rls import rls_context
from apps.visits import services
from apps.visits.tests.helpers import (
    api_delete, api_get, api_patch, api_post, day, make_refuge, make_user, make_visit, participant_rows,
    refuge_visits_url, user_claims, user_visits_url, visit_rows, visit_url)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration,
              pytest.mark.real_permissions]

APP_DIR = pathlib.Path(services.__file__).parent


@pytest.fixture
def scene():
    make_user('u1')
    make_user('uid-secret-u2')
    return make_refuge()


# ---------- Dates mal formades a la URL ----------

BAD_DATES = [
    '2030-01-01%0A',                                    # `$` de la regex accepta un salt de línia final
    '%0A2030-01-01',
    '%202030-01-01',
    '2030-01-01%20',
    '%D9%A2%D9%A0%D9%A3%D9%A0-%D9%A0%D9%A1-%D9%A0%D9%A1',   # dígits aràbics: `\d` de Python els accepta
    '2030-1-1',
    '2030-01-01T00:00:00',
    '20300101',
    '2030-13-01',
    '2030-02-30',
    '0000-01-01',
    '%EF%BC%92%EF%BC%90%EF%BC%93%EF%BC%90-01-01',       # dígits d'amplada completa
    '2030-01-01%00',
]


@pytest.mark.parametrize('bad', BAD_DATES)
def test_data_mal_formada_post_400_patch_delete_404_i_no_s_escriu_res(client, scene, bad):
    r = scene
    vid = make_visit(r, day(3), {'u1': 2})
    path = f'/api/refuges/{r.pk}/visits/{bad}/'
    u = user_claims('u1')
    assert api_post(client, path, u, {'num_visitors': 1}).status_code in (400, 404)
    assert api_patch(client, path, u, {'num_visitors': 9}).status_code == 404
    assert api_delete(client, path, u).status_code == 404
    assert participant_rows(vid) == {'u1': 2} and len(visit_rows(r)) == 1


def test_data_limit_superior_es_rebutja_sense_500(client, scene):
    """9999-12-31 és una data real però és a més de 12 mesos vista (D36): 400 i no es desa res."""
    resp = api_post(client, visit_url(scene.pk, '9999-12-31'), user_claims('u1'), {'num_visitors': 1})
    assert resp.status_code == 400
    assert len(visit_rows(scene)) == 0


# ---------- Cos amb valors extrems ----------

def _raw_post(client, path, body, claims, method='post'):
    fn = {'post': api_post, 'patch': api_patch}[method]
    return fn(client, path, claims, body)


@pytest.mark.parametrize('method', ['post', 'patch'])
@pytest.mark.parametrize('body', [
    {'num_visitors': 10 ** 30}, {'num_visitors': '9' * 5000}, {'num_visitors': -1}, {'num_visitors': 0},
    {'num_visitors': None}, {'num_visitors': True}, {'num_visitors': [1]}, {'num_visitors': {'a': 1}},
    {'num_visitors': 1.5}, {'num_visitors': 'cinc'}, {'num_visitors': 101}, {}, [], 'text', 7,
])
def test_cos_extrem_400_i_cap_escriptura(client, scene, method, body):
    r = scene
    vid = make_visit(r, day(3), {'u1': 2})
    path = visit_url(r.pk, day(3) if method == 'patch' else day(4))
    resp = _raw_post(client, path, body, user_claims('u1'), method)
    assert resp.status_code == 400, resp.content
    assert participant_rows(vid) == {'u1': 2} and len(visit_rows(r)) == 1


@pytest.mark.parametrize('literal', ['NaN', 'Infinity', '-Infinity', '1e999'])
def test_json_amb_constants_no_estandard_no_dona_500(client, scene, literal):
    from apps.accounts.tests.helpers import VERIFY
    payload = '{"num_visitors": %s}' % literal
    with patch(VERIFY, return_value=user_claims('u1')):
        resp = client.post(visit_url(scene.pk, day(4)), data=payload, content_type='application/json',
                           HTTP_AUTHORIZATION='Bearer t')
    assert resp.status_code == 400


# ---------- Injecció SQL: guarda estàtica ----------

def _production_sources():
    for path in APP_DIR.rglob('*.py'):
        if 'tests' in path.parts or 'migrations' in path.parts:
            continue
        yield path


def _literal_sql(node) -> bool:
    """Un literal de text (les cadenes adjacents ja són una sola `Constant`); cap f-string, `%`, `+` ni `.format`."""
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def test_cap_raw_extra_rawsql_ni_execute_amb_sql_formatat():
    offenders = []
    for path in _production_sources():
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id == 'RawSQL':
                offenders.append(f'{path.name}:{node.lineno} RawSQL')
            if isinstance(node, ast.Attribute) and node.attr == 'RawSQL':
                offenders.append(f'{path.name}:{node.lineno} RawSQL')
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in ('raw', 'extra'):
                    offenders.append(f'{path.name}:{node.lineno} .{node.func.attr}()')
                if node.func.attr in ('execute', 'executemany') and node.args and not _literal_sql(node.args[0]):
                    offenders.append(f'{path.name}:{node.lineno} execute() amb SQL no literal')
    assert not offenders, offenders


def test_la_comanda_del_job_no_rep_entrada_de_l_usuari():
    """El job no declara arguments: res de fora pot arribar al SQL."""
    from apps.visits.management.commands.process_yesterday_visits import Command
    parser = Command().create_parser('manage.py', 'process_yesterday_visits')
    custom = [a.dest for a in parser._actions if a.dest not in {
        'help', 'version', 'verbosity', 'settings', 'pythonpath', 'traceback', 'no_color', 'force_color',
        'skip_checks'}]
    assert custom == []


# ---------- Dades personals ----------

def test_cap_uid_d_un_altre_participant_a_respostes_ni_logs(client, scene, caplog):
    r = scene
    make_visit(r, day(3), {'uid-secret-u2': 4})
    u = user_claims('u1')
    with caplog.at_level(logging.DEBUG):
        responses = [
            api_get(client, refuge_visits_url(r.pk), u),
            api_post(client, visit_url(r.pk, day(3)), u, {'num_visitors': 1}),
            api_patch(client, visit_url(r.pk, day(3)), u, {'num_visitors': 2}),
            api_get(client, user_visits_url('u1'), u),
            api_get(client, user_visits_url('un-altre'), u),                            # IDOR: 403
            api_delete(client, visit_url(r.pk, day(3)), u),
            api_delete(client, visit_url(r.pk, day(3)), u),                         # ja no hi és: 400
        ]
    assert [x.status_code for x in responses] == [200, 201, 200, 200, 403, 200, 400]
    for resp in responses:
        assert 'uid-secret-u2' not in resp.content.decode()
    assert 'uid-secret-u2' not in caplog.text
    # el total sí que inclou l'altre participant (agregat), però només com a nombre
    assert responses[0].json()['result'][0]['total_visitors'] == 4 and responses[0].json()['result'][0]['num_visitors'] == 0


def test_error_500_no_porta_uid_ni_sql_a_la_resposta(client, scene):
    from django.db import DatabaseError
    boom = DatabaseError('INSERT ... uid-secret-u2 duplicate key')
    with patch('apps.visits.views.services.create_visit', side_effect=boom):
        resp = api_post(client, visit_url(scene.pk, day(3)), user_claims('u1'), {'num_visitors': 1})
    assert resp.status_code == 500 and set(resp.json()) == {'error', 'error_id'}
    assert 'uid-secret-u2' not in resp.content.decode() and 'INSERT' not in resp.content.decode()


# ---------- Bloquejats / sense edat: el servei no s'executa ----------

@pytest.mark.parametrize('kwargs', [{'is_blocked': True}, {'age_confirmed_at': None, 'age_threshold': None}])
@pytest.mark.parametrize('method', ['post', 'patch'])
def test_bloquejat_o_sense_edat_no_crea_ni_la_visita(client, method, kwargs):
    from apps.visits.tests.helpers import make_user as mk
    mk('b1', **kwargs)
    r = make_refuge()
    fn = {'post': api_post, 'patch': api_patch}[method]
    with patch('apps.visits.views.services') as svc:
        resp = fn(client, visit_url(r.pk, day(3)), user_claims('b1'), {'num_visitors': 1})
    assert resp.status_code == 403
    assert not svc.create_visit.called and not svc.update_visit.called
    assert visit_rows(r) == []


# ---------- Context de RLS del job ----------

def _is_system():
    with connection.cursor() as cur:
        cur.execute("SELECT coalesce(current_setting('app.is_system', true), '')")
        return cur.fetchone()[0]


@pytest.mark.parametrize('func', ['process_yesterday_visits', 'purge_old_visits'])
def test_el_job_no_deixa_el_context_de_sistema_obert_si_falla(func):
    with rls_context(uid='u1'):
        assert _is_system() == 'false'
        with patch.object(services.RefugeVisit, 'objects') as objects:
            objects.filter.side_effect = RuntimeError('boom')
            with pytest.raises(RuntimeError):
                getattr(services, func)()
        assert _is_system() == 'false'
