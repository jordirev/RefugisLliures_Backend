from django.apps import AppConfig


class FirebaseAuthConfig(AppConfig):
    """Autenticació amb Firebase Auth: permisos, autenticació DRF, middleware i inicialització de Firebase Admin.

    El label és `firebase_auth` perquè `auth` col·lisiona amb `django.contrib.auth`.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.auth'
    label = 'firebase_auth'
    verbose_name = 'Autenticació amb Firebase'

    def ready(self):
        """Inicialitza Firebase Admin SDK (només per a Auth)."""
        from .firebase_config import initialize_firebase
        initialize_firebase()
