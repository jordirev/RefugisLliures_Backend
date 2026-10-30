#!/usr/bin/env python3
"""
Script per gestionar administradors del sistema mitjançant Custom Claims de Firebase
"""
import sys
import os
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'refugis_lliures.settings')
django.setup()

from firebase_admin import auth

# `django.setup()` ja ha inicialitzat Firebase Admin (`FirebaseAuthConfig.ready()`) amb FIREBASE_SERVICE_ACCOUNT_KEY:
# `PRODUCTION=true python scripts/manage_admins.py ...` usa el service account de `env/.env.production`.


def add_admin(uid):
    """Afegeix permisos d'administrador a un usuari"""
    try:
        user = auth.get_user(uid)
    except auth.UserNotFoundError:
        print(f"✗ Error: Usuari {uid} no trobat")
        return False
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        return False

    # Tot endpoint autenticat exigeix perfil (403 `profile_required`): primer es crea la fila de `users` + perfil
    # públic (idempotent; no trepitja un perfil existent) i només després el claim, perquè cap admin quedi sense perfil.
    try:
        from apps.accounts import services
        from apps.core.rls import system_context
        with system_context():
            services.ensure_user(uid)
        print(f"✓ Perfil de {uid} assegurat a PostgreSQL")
    except Exception as e:
        print(f"✗ Error creant el perfil a PostgreSQL ({type(e).__name__}); torna a executar 'add'")
        return False

    try:
        current_claims = user.custom_claims or {}
        current_claims['role'] = 'admin'
        auth.set_custom_user_claims(uid, current_claims)
        print(f"✓ Usuari {uid} ({user.email}) ara és administrador")
        print("⚠️  L'usuari ha de renovar el seu token (logout/login)")
        return True
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        return False


def remove_admin(uid):
    """Elimina permisos d'administrador d'un usuari"""
    try:
        user = auth.get_user(uid)
        current_claims = user.custom_claims or {}
        
        # Eliminar rol admin (assignar role 'user' o eliminar el claim)
        if 'role' in current_claims:
            del current_claims['role']
        auth.set_custom_user_claims(uid, current_claims)
        
        print(f"✓ Permisos d'admin eliminats per {uid} ({user.email})")
        print("⚠️  L'usuari ha de renovar el seu token (logout/login)")
        return True
    except auth.UserNotFoundError:
        print(f"✗ Error: Usuari {uid} no trobat")
        return False
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        return False


def check_admin(uid):
    """Comprova si un usuari és administrador"""
    try:
        user = auth.get_user(uid)
        claims = user.custom_claims or {}
        is_admin = claims.get('role') == 'admin'
        
        print(f"Usuari: {user.email}")
        print(f"UID: {uid}")
        print(f"Admin: {'✓ Sí' if is_admin else '✗ No'}")
        print(f"Custom Claims: {claims}")
        return is_admin
    except auth.UserNotFoundError:
        print(f"✗ Error: Usuari {uid} no trobat")
        return False
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        return False


def list_users():
    """Llista tots els usuaris amb els seus rols"""
    try:
        page = auth.list_users()
        users_info = []
        
        while page:
            for user in page.users:
                claims = user.custom_claims or {}
                is_admin = claims.get('role') == 'admin'
                users_info.append({
                    'uid': user.uid,
                    'email': user.email,
                    'admin': is_admin
                })
            page = page.get_next_page()
        
        # Imprimir taula
        print(f"\n{'UID':<30} {'Email':<35} {'Admin':<10}")
        print("-" * 80)
        for user_info in users_info:
            admin_status = '✓ Sí' if user_info['admin'] else '✗ No'
            print(f"{user_info['uid']:<30} {user_info['email']:<35} {admin_status:<10}")
        
        # Resum
        total = len(users_info)
        admins = sum(1 for u in users_info if u['admin'])
        print(f"\nTotal usuaris: {total}")
        print(f"Administradors: {admins}")
        
        return users_info
    except Exception as e:
        print(f"✗ Error llistant usuaris: {str(e)}")
        return []


def main():
    """Funció principal"""
    if len(sys.argv) < 2:
        print("Gestió d'Administradors - Refugis Lliures")
        print("\nÚs:")
        print("  python manage_admins.py add <uid>       - Afegir admin")
        print("  python manage_admins.py remove <uid>    - Eliminar admin")
        print("  python manage_admins.py check <uid>     - Comprovar admin")
        print("  python manage_admins.py list            - Llistar tots els usuaris")
        print("\nExemples:")
        print("  python manage_admins.py add abc123def456")
        print("  python manage_admins.py check abc123def456")
        print("  python manage_admins.py list")
        sys.exit(1)
    
    action = sys.argv[1].lower()
    
    if action == "add":
        if len(sys.argv) != 3:
            print("✗ Error: Especifica el UID de l'usuari")
            sys.exit(1)
        uid = sys.argv[2]
        add_admin(uid)
    
    elif action == "remove":
        if len(sys.argv) != 3:
            print("✗ Error: Especifica el UID de l'usuari")
            sys.exit(1)
        uid = sys.argv[2]
        remove_admin(uid)
    
    elif action == "check":
        if len(sys.argv) != 3:
            print("✗ Error: Especifica el UID de l'usuari")
            sys.exit(1)
        uid = sys.argv[2]
        check_admin(uid)
    
    elif action == "list":
        list_users()
    
    else:
        print(f"✗ Error: Acció '{action}' no reconeguda")
        print("Accions vàlides: add, remove, check, list")
        sys.exit(1)


if __name__ == "__main__":
    main()
