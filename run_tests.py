#!/usr/bin/env python
"""
Script per executar tests amb diferents configuracions
"""
import subprocess
import sys
import os


def run_command(command, description):
    """Executa una comanda i mostra el resultat"""
    print(f"\n{'='*60}")
    print(f"🔍 {description}")
    print(f"{'='*60}\n")
    
    result = subprocess.run(command, shell=True)
    
    if result.returncode != 0:
        print(f"\n❌ Error executant: {description}")
        return False
    else:
        print(f"\n✅ {description} - Completat")
        return True


def main():
    """Funció principal"""
    
    # Comprovar que estem al directori correcte
    if not os.path.exists('api'):
        print("❌ Error: Aquest script s'ha d'executar des del directori arrel del projecte")
        sys.exit(1)
    
    print("""
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║          🧪 TEST RUNNER - RefugisLliures Backend         ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
    """)
    
    opcions = {
        '1': ('Executar TOTS els tests amb coverage', 
              'pytest --cov=api --cov-report=term-missing --cov-report=html --cov-report=xml -v'),
        '2': ('Tests de USUARIS amb coverage',
              'pytest apps/accounts --cov=apps.accounts --cov-report=term-missing --cov-report=xml -v'),
        '3': ('Tests de REFUGIS amb coverage',
              'pytest api/tests/test_refugi_lliure.py --cov=api.models.refugi_lliure --cov=api.serializers.refugi_lliure_serializer --cov=api.controllers.refugi_lliure_controller --cov=api.daos.refugi_lliure_dao --cov=api.mappers.refugi_lliure_mapper --cov=api.views.refugi_lliure_views --cov-report=term-missing --cov-report=xml -v'),
        '4': ('Tests de MODELS només',
              'pytest -m models -v'),
        '5': ('Tests de SERIALIZERS només',
              'pytest -m serializers -v'),
        '6': ('Tests de CONTROLLERS només',
              'pytest -m controllers -v'),
        '7': ('Tests de DAOs només',
              'pytest -m daos -v'),
        '8': ('Tests de VIEWS només',
              'pytest -m views -v'),
        '9': ('Tests d\'INTEGRACIÓ només',
              'pytest -m integration -v'),
        '10': ('Generar informe HTML de coverage',
               'pytest --cov=api --cov-report=html && echo "Informe generat a htmlcov/index.html"'),
        '11': ('Tests ràpids (sense coverage)',
               'pytest -v'),
        '12': ('Tests amb depuració (primer error)',
               'pytest -x -v'),
    }
    
    print("Opcions disponibles:\n")
    for key, (description, _) in sorted(opcions.items()):
        print(f"  [{key}] {description}")
    print(f"  [0] Sortir\n")
    
    while True:
        choice = input("Selecciona una opció: ").strip()
        
        if choice == '0':
            print("\n👋 Adéu!")
            sys.exit(0)
        
        if choice in opcions:
            description, command = opcions[choice]
            success = run_command(command, description)
            
            if not success:
                continuar = input("\n❓ Vols continuar amb altres tests? (s/n): ").strip().lower()
                if continuar != 's':
                    sys.exit(1)
            
            altra = input("\n❓ Vols executar una altra opció? (s/n): ").strip().lower()
            if altra != 's':
                print("\n✅ Tests completats!")
                sys.exit(0)
            
            # Mostrar opcions de nou
            print("\nOpcions disponibles:\n")
            for key, (description, _) in sorted(opcions.items()):
                print(f"  [{key}] {description}")
            print(f"  [0] Sortir\n")
        else:
            print("❌ Opció invàlida. Tria un número del menú.")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Tests interromputs per l'usuari")
        sys.exit(0)
