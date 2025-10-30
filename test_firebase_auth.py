"""
Compatibility shim: tests moved to `api/tests`.

This file remains at the repository root for backwards compatibility.
It delegates execution to `api.tests.test_firebase_auth`.
"""

from api.tests import test_firebase_auth as _mod


def main():
    # Delegate to the moved test module
    return _mod.main()


if __name__ == '__main__':
    main()


def test_unauthorized_access(base_url, uid):
    """
    Testa l'accés sense token (hauria de fallar)
    """
    print("\n" + "="*60)
    print("TEST: Endpoint sense autenticació - GET /api/users/{uid}/")
    print("="*60)
    
    url = f"{base_url}/api/users/{uid}/"
    
    print(f"\nURL: {url}")
    print("Headers: Sense Authorization header")
    
    try:
        response = requests.get(url)
        print(f"\nStatus Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 401:
            print("\n✅ Test PASSAT - Correctament denegat sense token")
            return True
        else:
            print(f"\n❌ Test FALLAT - S'esperava 401 però s'ha obtingut {response.status_code}")
            return False
            
    except Exception as e:
        print(f"\n❌ Error en la petició: {str(e)}")
        return False


def test_public_endpoint(base_url):
    """
    Testa un endpoint públic (no requereix autenticació)
    """
    print("\n" + "="*60)
    print("TEST: Endpoint públic - GET /api/health/")
    print("="*60)
    
    url = f"{base_url}/api/health/"
    
    print(f"\nURL: {url}")
    
    try:
        response = requests.get(url)
        print(f"\nStatus Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            print("\n✅ Test PASSAT - Endpoint públic accessible")
            return True
        else:
            print(f"\n❌ Test FALLAT - S'esperava 200 però s'ha obtingut {response.status_code}")
            return False
            
    except Exception as e:
        print(f"\n❌ Error en la petició: {str(e)}")
        return False


def test_update_user(base_url, uid, token):
    """
    Testa l'actualització d'un usuari autenticat
    """
    print("\n" + "="*60)
    print("TEST: Actualitzar usuari - PUT /api/users/{uid}/")
    print("="*60)
    
    url = f"{base_url}/api/users/{uid}/"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = {
        "nom": "Nom de Test",
        "bio": "Biografia de test actualitzada"
    }
    
    print(f"\nURL: {url}")
    print(f"Headers: {json.dumps(headers, indent=2)}")
    print(f"Data: {json.dumps(data, indent=2)}")
    
    try:
        response = requests.put(url, headers=headers, json=data)
        print(f"\nStatus Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            print("\n✅ Test PASSAT - Usuari actualitzat correctament")
            return True
        elif response.status_code == 401:
            print("\n❌ Test FALLAT - Token no autoritzat")
            return False
        elif response.status_code == 403:
            print("\n❌ Test FALLAT - Permís denegat")
            return False
        else:
            print(f"\n⚠️  Test amb status code inesperat: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"\n❌ Error en la petició: {str(e)}")
        return False


def main():
    """
    Funció principal per executar els tests
    """
    print("="*60)
    print("TESTS D'AUTENTICACIÓ FIREBASE JWT")
    print("="*60)
    
    # Configuració
    base_url = "http://localhost:8000"
    
    print("\n⚠️  ATENCIÓ:")
    print("Per executar aquests tests necessites:")
    print("1. Tenir el servidor Django executant-se")
    print("2. Un token JWT vàlid de Firebase")
    print("3. Un UID d'usuari vàlid")
    print("\nPer obtenir un token JWT:")
    print("  - Autentica't a l'aplicació frontend amb Firebase")
    print("  - Copia el token que et proporciona Firebase")
    
    # Test públic (sempre hauria de funcionar)
    test_public_endpoint(base_url)
    
    # Per als altres tests, necessites un token i UID
    print("\n" + "-"*60)
    print("Tests amb autenticació (opcional)")
    print("-"*60)
    print("\nVols executar els tests amb autenticació? (s/n): ", end="")
    
    try:
        resposta = input().strip().lower()
        
        if resposta == 's':
            print("\nIntrodueix el UID de l'usuari: ", end="")
            uid = input().strip()
            
            print("Introdueix el token JWT de Firebase: ", end="")
            token = input().strip()
            
            if uid and token:
                # Executa els tests
                results = []
                results.append(test_unauthorized_access(base_url, uid))
                results.append(test_authenticated_endpoint(base_url, uid, token))
                results.append(test_update_user(base_url, uid, token))
                
                # Resum
                print("\n" + "="*60)
                print("RESUM DELS TESTS")
                print("="*60)
                print(f"Tests passats: {sum(results)}/{len(results) + 1}")
                
                if all(results):
                    print("\n✅ Tots els tests han passat correctament!")
                else:
                    print("\n⚠️  Alguns tests han fallat. Revisa els logs anteriors.")
            else:
                print("\n⚠️  UID o token no proporcionats. Tests omesos.")
        else:
            print("\nTests amb autenticació omesos.")
            
    except KeyboardInterrupt:
        print("\n\nTests interromputs per l'usuari.")
        sys.exit(0)


if __name__ == "__main__":
    main()
