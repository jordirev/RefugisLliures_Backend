import os
import sys

from django.apps import AppConfig

# Comandes de `manage.py` que mai verifiquen tokens ni usen Firebase: no hi carreguem el service account. Així
# `PRODUCTION=true python manage.py migrate` / `load_refuges` es poden executar contra la BD de producció des d'un entorn
# que només té les URL de la BD (`decouple` llegeix `env/.env.production` però no l'exporta a `os.environ`, GOTCHAS #6).
# El servidor (gunicorn, `runserver`) i qualsevol altra comanda continuen inicialitzant Firebase i fallen fort sense credencial.
COMMANDS_WITHOUT_FIREBASE = frozenset({
    'migrate', 'makemigrations', 'showmigrations', 'sqlmigrate', 'collectstatic',
    'check_neon', 'load_refuges', 'load_hash_blocklist',
    'purge_audit_logs', 'purge_moderation', 'purge_upload_intents', 'process_yesterday_visits',
})


def _runs_command_without_firebase(argv=None) -> bool:
    argv = sys.argv if argv is None else argv
    return len(argv) > 1 and os.path.basename(argv[0]) == 'manage.py' and argv[1] in COMMANDS_WITHOUT_FIREBASE


class FirebaseAuthConfig(AppConfig):
    """Autenticació amb Firebase Auth: permisos, autenticació DRF, middleware i inicialització de Firebase Admin.

    El label és `firebase_auth` perquè `auth` col·lisiona amb `django.contrib.auth`.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.auth'
    label = 'firebase_auth'
    verbose_name = 'Autenticació amb Firebase'

    def ready(self):
        """Inicialitza Firebase Admin SDK (només per a Auth), tret de les comandes de gestió que no el necessiten."""
        if _runs_command_without_firebase():
            return
        from .firebase_config import initialize_firebase
        initialize_firebase()
