"""Test d'arquitectura: TOTES les vistes d'`api/views` apliquen el context RLS a `initial()` (§7.3).

No depèn del nom de la classe base: executa `initial()` de cada vista amb el cursor intervingut i exigeix
una sentència `set_config` (app.uid / app.is_admin / app.is_system) **abans** de les comprovacions de permisos.
Cobreix les `APIView` i les vistes de funció (`@api_view`).
"""
import importlib
import inspect
import pkgutil
from unittest.mock import patch

import pytest
from django.test import RequestFactory
from rest_framework.request import Request
from rest_framework.views import APIView

import api.views

pytestmark = [pytest.mark.unit, pytest.mark.rls]


def _all_view_classes():
    classes = {}
    for mod_info in pkgutil.iter_modules(api.views.__path__):
        mod = importlib.import_module(f'api.views.{mod_info.name}')
        for name, obj in vars(mod).items():
            if inspect.isclass(obj) and issubclass(obj, APIView) and obj is not APIView \
                    and obj.__module__ == mod.__name__:
                classes[f'{mod.__name__}.{name}'] = obj
            elif callable(obj) and hasattr(obj, 'cls') and inspect.isclass(obj.cls) and issubclass(obj.cls, APIView):
                classes[f'{mod.__name__}.{name}'] = obj.cls      # @api_view
    return classes


VIEWS = _all_view_classes()


def test_es_troben_les_vistes():
    assert len(VIEWS) >= 40, f"només s'han trobat {len(VIEWS)} vistes"
    assert any(k.endswith('HealthCheckAPIView') for k in VIEWS)
    assert any('cache_views' in k for k in VIEWS), "també les vistes de funció @api_view"


def _recorded_sql(view_cls, authenticated):
    """SQL executat per `initial()` d'una vista, amb el cursor i la BD interceptats."""
    recorded = []

    def fake_execute(self, sql, params=None):
        recorded.append((str(sql), params))
        return None

    factory = RequestFactory()
    django_request = factory.get('/x/')
    if authenticated:
        django_request.firebase_user = {'uid': 'u1', 'role': 'user'}
        django_request.user_uid = 'u1'
        django_request.user_claims = {'uid': 'u1', 'role': 'user'}
    view = view_cls()
    view.args, view.kwargs, view.request = (), {}, None
    drf_request = view.initialize_request(django_request)
    view.request = drf_request
    view.headers = view.default_response_headers
    with patch('django.db.backends.utils.CursorWrapper.execute', fake_execute), \
            patch('django.db.backends.base.base.BaseDatabaseWrapper.ensure_connection', lambda self: None), \
            patch('django.db.backends.utils.CursorWrapper.fetchone', lambda self: (None,) * 3), \
            patch('django.db.backends.utils.CursorWrapper.fetchall', lambda self: []):
        try:
            view.initial(drf_request)
        except Exception:   # permisos/autenticació/BD simulada: ens interessa només el que s'ha executat abans
            pass
    return recorded


@pytest.mark.parametrize('name', sorted(VIEWS))
@pytest.mark.parametrize('authenticated', [False, True], ids=['anonim', 'autenticat'])
def test_totes_les_vistes_apliquen_el_context_rls(name, authenticated):
    recorded = _recorded_sql(VIEWS[name], authenticated)
    cfg = [r for r in recorded if 'set_config' in r[0]]
    assert len(cfg) == 1, f"{name}: initial() ha d'executar exactament un set_config (n'ha fet {len(cfg)})"
    sql, params = cfg[0]
    for setting in ('app.uid', 'app.is_admin', 'app.is_system'):
        assert setting in sql
    assert params is not None and ('u1' in list(params) if authenticated else True), \
        "uid com a paràmetre (cap SQL concatenat)"
    if not authenticated:
        assert 'u1' not in list(params or [])


def test_la_base_no_ha_d_afegir_permisos_que_se_saltin_el_context():
    """El context s'ha de fixar abans que `check_permissions` (HasProfile llegeix `users` amb RLS)."""
    order = []
    original_perm = APIView.check_permissions

    def spy_perm(self, request):
        order.append('permissions')
        return original_perm(self, request)

    def fake_execute(self, sql, params=None):
        if 'set_config' in str(sql):
            order.append('set_config')

    from api.views.health_check_views import HealthCheckAPIView
    view = HealthCheckAPIView()
    req = RequestFactory().get('/api/health/')
    view.args, view.kwargs = (), {}
    drf_request = view.initialize_request(req)
    view.request = drf_request
    view.headers = view.default_response_headers
    with patch.object(APIView, 'check_permissions', spy_perm), \
            patch('django.db.backends.utils.CursorWrapper.execute', fake_execute), \
            patch('django.db.backends.base.base.BaseDatabaseWrapper.ensure_connection', lambda self: None):
        try:
            view.initial(drf_request)
        except Exception:
            pass
    assert order[:2] == ['set_config', 'permissions'], order
