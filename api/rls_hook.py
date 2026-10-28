"""
Hook de RLS per petició (docs/design/postgres-schema.md §7.3).

Després de l'autenticació i **abans** de `check_permissions`, cada vista DRF (`APIView` i `@api_view`)
executa una única sentència `set_config(..., true)` que fixa `app.uid`, `app.is_admin` i `app.is_system`
a la transacció d'`ATOMIC_REQUESTS`. El context mor al `COMMIT`/`ROLLBACK`, de manera que mai es filtra a una
altra petició que reutilitzi la connexió del pooler.

- `app.uid` ve només de l'usuari autenticat pel token verificat (cap capçalera, query ni cos).
- `app.is_admin` és `true` només si els claims verificats tenen exactament `role == 'admin'`.
- `app.is_system` es reinicia sempre a `false` (només `system_context()` el posa a `true`).
"""
import logging
from collections.abc import Mapping

from django.db import connections
from rest_framework.views import APIView

from apps.core.rls import DEFAULT_ALIAS, apply_context

logger = logging.getLogger(__name__)

ADMIN_ROLE = 'admin'


def _verified_identity(request):
    """(uid, claims) de l'usuari autenticat, o (None, None) si la petició és anònima."""
    user = getattr(request, 'user', None)
    uid = getattr(user, 'uid', None) if getattr(user, 'is_authenticated', False) else None
    claims = getattr(user, 'claims', None) if uid else None
    if not isinstance(uid, str) or not uid:
        # Vistes sense autenticació DRF: s'usa el que ha verificat el middleware de Firebase.
        uid = getattr(request, 'user_uid', None)
        claims = getattr(request, 'user_claims', None)
    if not isinstance(uid, str) or not uid:
        return None, None
    return uid, claims


def is_admin_claims(claims):
    return isinstance(claims, Mapping) and claims.get('role') == ADMIN_ROLE


def apply_request_rls_context(request):
    """Fixa el context de RLS de la petició a la transacció en curs."""
    conn = connections[DEFAULT_ALIAS]
    if not conn.in_atomic_block:
        # Sense transacció (`@transaction.non_atomic_requests` o `ATOMIC_REQUESTS` desactivat) un `set_config(..., true)`
        # moriria en la mateixa sentència: la vista queda sense context i la RLS ho denega tot (fail-closed).
        # S'avisa perquè no sigui un error silenciós (la sentència s'executa igualment: és inofensiva).
        logger.warning("Hook de RLS: la petició %s no s'executa dins d'una transacció; el context no persistirà.",
                       getattr(request, 'path', '?'))
    uid, claims = _verified_identity(request)
    apply_context(conn, uid, is_admin_claims(claims))


def install():
    """Embolcalla `APIView.perform_authentication` perquè fixi el context just després d'autenticar."""
    if getattr(APIView, '_rls_hook_installed', False):
        return
    original = APIView.perform_authentication

    def perform_authentication(self, request):
        original(self, request)
        # Una vista que obre la seva pròpia transacció i context (p. ex. `DELETE /users/{uid}/`, D42) ho declara aquí
        # perquè el hook no avisi ni executi un `set_config` inútil fora de transacció.
        if getattr(self, 'skip_rls_hook', None) and self.skip_rls_hook(request):
            return
        apply_request_rls_context(request)

    perform_authentication.__wrapped__ = original
    APIView.perform_authentication = perform_authentication
    APIView._rls_hook_installed = True
