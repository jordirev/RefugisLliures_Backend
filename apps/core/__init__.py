"""
App `core`: schemas, funcions SQL, grants base i helpers de RLS (docs/design/postgres-schema.md §2.0, §7).

No té models: només migracions (`RunSQL`) i el context de RLS per transacció.
"""
from .rls import rls_context, system_context

__all__ = ['rls_context', 'system_context']
