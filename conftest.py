"""
Conftest arrel del projecte per configurar l'entorn de tests.
Les variables d'entorn s'han de configurar AQUÍ perquè
pytest carrega aquest fitxer ABANS que qualsevol altre conftest
i abans que els fitxers de test s'importin.
"""
import os

# Configurar variables d'entorn TESTING i R2 abans de qualsevol import
os.environ['TESTING'] = 'true'
os.environ['R2_ACCESS_KEY_ID'] = 'test_access_key'
os.environ['R2_SECRET_ACCESS_KEY'] = 'test_secret_key'
os.environ['R2_ENDPOINT'] = 'https://test.r2.cloudflarestorage.com'
os.environ['R2_BUCKET_NAME'] = 'test-bucket'


def pytest_configure(config):
    """
    Hook que s'executa molt aviat durant la configuració de pytest.
    Assegura que les variables d'entorn estiguin configurades.
    """
    os.environ.setdefault('TESTING', 'true')
    os.environ.setdefault('R2_ACCESS_KEY_ID', 'test_access_key')
    os.environ.setdefault('R2_SECRET_ACCESS_KEY', 'test_secret_key')
    os.environ.setdefault('R2_ENDPOINT', 'https://test.r2.cloudflarestorage.com')
    os.environ.setdefault('R2_BUCKET_NAME', 'test-bucket')

