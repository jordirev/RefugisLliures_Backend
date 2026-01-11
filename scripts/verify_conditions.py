"""Script temporal per verificar les conditions assignades"""
from api.services import firestore_service

db = firestore_service.get_db()

# Verificar refugis amb diferents conditions
refugis_to_check = [
    'CT7MFN327xWDqufTr4vA',  # Hauria de tenir condition 3
    'ycirEQe9eLwfCJtdipsP',  # Hauria de tenir condition 3
    '4Ry7yUfjuppenw5OAsr7',  # Hauria de tenir condition 2
    '20v5nqEWdq6VhZ14coou',  # Hauria de tenir condition 1
    '0Cj5r1VXW29W4ExqDwGf',  # Hauria de tenir condition 0
]

print("Verificant conditions assignades:\n")
print("=" * 80)

for refugi_id in refugis_to_check:
    doc = db.collection('data_refugis_lliures').document(refugi_id).get()
    if doc.exists:
        data = doc.to_dict()
        name = data.get('name', 'Sense nom')
        condition = data.get('condition')
        num_contributed = data.get('num_contributed_conditions')
        info_comp = data.get('info_comp', {})
        
        # Comptar amenities
        amenities = [k for k, v in info_comp.items() if k != 'manque_un_mur' and v == 1]
        manque_mur = info_comp.get('manque_un_mur', 0)
        
        print(f"\nRefugi: {name} (ID: {refugi_id})")
        print(f"  Condition: {condition} (tipus: {type(condition).__name__})")
        print(f"  Num contributed: {num_contributed}")
        print(f"  Amenities: {len(amenities)} - {amenities[:3]}..." if len(amenities) > 3 else f"  Amenities: {len(amenities)} - {amenities}")
        print(f"  Manque un mur: {manque_mur}")
    else:
        print(f"\nRefugi {refugi_id} no trobat")

print("\n" + "=" * 80)
print("\nVerificació completada!")
