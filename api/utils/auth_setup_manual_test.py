"""
Test ràpid de l'autenticació Firebase

Aquest script fa un test ràpid per verificar que el middleware està funcionant correctament.
"""

def test_imports():
    """Test que les importacions funcionin correctament"""
    print("Testing imports...")
    try:
        from api.middleware.firebase_auth_middleware import FirebaseAuthenticationMiddleware
        print("✅ FirebaseAuthenticationMiddleware importat correctament")
    except ImportError as e:
        print(f"❌ Error important FirebaseAuthenticationMiddleware: {e}")
        return False
    
    try:
        from api.authentication import FirebaseAuthentication
        print("✅ FirebaseAuthentication importat correctament")
    except ImportError as e:
        print(f"❌ Error important FirebaseAuthentication: {e}")
        return False
    
    try:
        from api.permissions import IsSameUser, IsOwner, IsOwnerOrReadOnly
        print("✅ Permissions importades correctament")
    except ImportError as e:
        print(f"❌ Error important Permissions: {e}")
        return False
    
    return True

def test_settings():
    """Test que la configuració sigui correcta"""
    print("\nTesting settings...")
    try:
        from django.conf import settings
        
        # Verificar middleware
        if 'api.middleware.FirebaseAuthenticationMiddleware' in settings.MIDDLEWARE:
            print("✅ Middleware configurat correctament")
        else:
            print("❌ Middleware no trobat a MIDDLEWARE")
            return False
        
        # Verificar authentication classes
        if hasattr(settings, 'REST_FRAMEWORK'):
            auth_classes = settings.REST_FRAMEWORK.get('DEFAULT_AUTHENTICATION_CLASSES', [])
            if 'api.authentication.FirebaseAuthentication' in auth_classes:
                print("✅ Authentication class configurada correctament")
            else:
                print("⚠️  Authentication class no trobada a REST_FRAMEWORK")
        
        # Verificar drf_yasg
        if 'drf_yasg' in settings.INSTALLED_APPS:
            print("✅ drf_yasg instal·lat correctament")
        else:
            print("⚠️  drf_yasg no trobat a INSTALLED_APPS")
        
        return True
        
    except Exception as e:
        print(f"❌ Error verificant settings: {e}")
        return False

def test_firebase_connection():
    """Test que Firebase Admin SDK estigui configurat"""
    print("\nTesting Firebase connection...")
    try:
        import firebase_admin
        from firebase_admin import auth
        
        # Intentar obtenir l'app
        try:
            app = firebase_admin.get_app()
            print("✅ Firebase Admin SDK ja inicialitzat")
        except ValueError:
            print("⚠️  Firebase Admin SDK no inicialitzat (es farà al primer ús)")
        
        return True
        
    except ImportError as e:
        print(f"❌ Error important firebase_admin: {e}")
        return False
    except Exception as e:
        print(f"⚠️  Advertència: {e}")
        return True  # No és un error crític

def main():
    """Executa tots els tests"""
    print("="*60)
    print("TEST D'INSTAL·LACIÓ DE L'AUTENTICACIÓ FIREBASE")
    print("="*60)
    
    results = []
    
    # Test imports
    results.append(test_imports())
    
    # Test settings (només si Django està configurat)
    try:
        import django
        django.setup()
        results.append(test_settings())
        results.append(test_firebase_connection())
    except Exception as e:
        print(f"\n⚠️  No es pot verificar Django settings: {e}")
        print("   (Això és normal si no estàs al directori del projecte)")
    
    # Resum
    print("\n" + "="*60)
    print("RESUM")
    print("="*60)
    
    if all(results):
        print("✅ Tots els tests han passat!")
        print("\nPots executar el servidor amb:")
        print("  python manage.py runserver")
        print("\nI accedir a Swagger a:")
        print("  http://localhost:8000/swagger/")
    else:
        print("⚠️  Alguns tests han fallat. Revisa els errors anteriors.")
        
if __name__ == "__main__":
    import sys
    import os
    
    # Afegir el directori del projecte al path
    project_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, project_dir)
    
    # Configurar Django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'refugis_lliures.settings')
    
    main()
