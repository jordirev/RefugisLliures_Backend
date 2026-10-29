from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = 'apps.core'
    label = 'core'
    verbose_name = 'Nucli de la BD (schemas, funcions, RLS)'

    def ready(self):
        """Instal·la el hook de RLS per petició (fixa `app.uid`/`app.is_admin` abans dels permisos)."""
        from . import rls_hook
        rls_hook.install()
