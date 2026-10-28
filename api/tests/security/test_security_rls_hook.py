"""Forats del hook de RLS: sense transacció, escalada de context i identitat (§7.3, §7.4)."""
from unittest.mock import patch

import pytest
from django.db import transaction
from django.test import RequestFactory

from api.tests.conftest import fetch_one
from apps.core.rls import rls_context, system_context

pytestmark = [pytest.mark.db_infra, pytest.mark.rls]

CTX = 'SELECT core.uid(), core.is_admin(), core.is_system()'


def _request(uid=None, role='user'):
    req = RequestFactory().get('/api/x/')
    if uid:
        req.user_uid = uid
        req.user_claims = {'uid': uid, 'role': role}
    return req


def test_hook_fora_de_transaccio_deixa_el_context_buit_i_avisa(app_db):
    """`non_atomic_requests`: set_config local mor a la mateixa sentència -> fail-closed (uid NULL), amb avís."""
    from api.rls_hook import apply_request_rls_context
    assert not app_db.in_atomic_block
    with patch('api.rls_hook.logger') as log:
        apply_request_rls_context(_request('u-admin', 'admin'))
    text = ' '.join(str(c) for c in log.warning.call_args_list)
    assert fetch_one(app_db, CTX) == (None, False, False), "el context no pot sobreviure fora d'una transacció"
    assert 'transacció' in text
    assert 'u-admin' not in text, "l'avís no ha de contenir l'UID"


def test_l_avis_fora_de_transaccio_no_porta_el_cami_amb_l_uid(app_db):
    """L'avís registra el nom de la ruta, no el camí (que pot portar l'UID, p. ex. `/api/users/<uid>/`)."""
    from types import SimpleNamespace
    from api.rls_hook import apply_request_rls_context
    req = _request('u-secret')
    req.path = '/api/users/u-secret/'
    req.method = 'PATCH'
    req.resolver_match = SimpleNamespace(view_name='user_detail')
    with patch('api.rls_hook.logger') as log:
        apply_request_rls_context(req)
    text = ' '.join(str(c) for c in log.warning.call_args_list)
    assert 'user_detail' in text and 'u-secret' not in text


def test_hook_dins_de_transaccio_no_avisa(app_db):
    from api.rls_hook import apply_request_rls_context
    with patch('api.rls_hook.logger') as log, transaction.atomic():
        apply_request_rls_context(_request('u1'))
        assert fetch_one(app_db, CTX) == ('u1', False, False)
    log.warning.assert_not_called()


def test_el_context_d_una_peticio_no_sobreviu_a_la_transaccio(app_db):
    from api.rls_hook import apply_request_rls_context
    with transaction.atomic():
        apply_request_rls_context(_request('u-adm', 'admin'))
    assert fetch_one(app_db, CTX) == (None, False, False)


def test_un_context_intern_admin_o_system_no_escala_l_extern_ni_amb_excepcio(app_db):
    from api.rls_hook import apply_request_rls_context
    with transaction.atomic():
        apply_request_rls_context(_request('u1'))
        with pytest.raises(RuntimeError):
            with rls_context(uid='u1', is_admin=True, system=True):
                with system_context():
                    raise RuntimeError('x')
        assert fetch_one(app_db, CTX) == ('u1', False, False)


def test_apply_context_reinicia_is_system_encara_que_l_extern_el_tingui(app_db):
    from api.rls_hook import apply_request_rls_context
    with system_context():
        apply_request_rls_context(_request('u1'))
        assert fetch_one(app_db, CTX) == ('u1', False, False)


def test_uid_no_string_es_tracta_com_anonim():
    from api.rls_hook import _verified_identity

    class U:
        is_authenticated = True
        uid = 123
        claims = {'role': 'admin'}

    class R:
        user = U()

    assert _verified_identity(R()) == (None, None)


@pytest.mark.parametrize('role', [['admin'], {'admin': True}, True, 'Admin', 'ADMIN', ' admin', None])
def test_claim_role_no_exacte_no_dona_admin(role):
    from api.rls_hook import is_admin_claims
    assert is_admin_claims({'role': role}) is False
    assert is_admin_claims(None) is False
    assert is_admin_claims('admin') is False
