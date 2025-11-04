from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'

    def ready(self):
        """
        S'executa quan l'aplicació està llesta.
        Inicialitza Firebase Admin SDK.
        """
        from .firebase_config import initialize_firebase
        initialize_firebase()
