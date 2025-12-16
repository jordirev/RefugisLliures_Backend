"""
Management command to verify assigned conditions
"""
from django.core.management.base import BaseCommand
from api.services import firestore_service


class Command(BaseCommand):
    help = 'Verify that conditions have been assigned correctly'

    def handle(self, *args, **options):
        db = firestore_service.get_db()
        
        # Verificar refugis amb diferents conditions
        refugis_to_check = [
            ('CT7MFN327xWDqufTr4vA', 3),  # Hauria de tenir condition 3
            ('ycirEQe9eLwfCJtdipsP', 3),  # Hauria de tenir condition 3
            ('4Ry7yUfjuppenw5OAsr7', 2),  # Hauria de tenir condition 2
            ('20v5nqEWdq6VhZ14coou', 1),  # Hauria de tenir condition 1
            ('0Cj5r1VXW29W4ExqDwGf', 0),  # Hauria de tenir condition 0
        ]
        
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.SUCCESS('Verificant conditions assignades:'))
        self.stdout.write('=' * 80 + '\n')
        
        success_count = 0
        fail_count = 0
        
        for refugi_id, expected_condition in refugis_to_check:
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
                
                # Verificar si coincideix amb l'esperat
                if condition == float(expected_condition) and num_contributed == 1:
                    status = self.style.SUCCESS('✓ OK')
                    success_count += 1
                else:
                    status = self.style.ERROR('✗ FAIL')
                    fail_count += 1
                
                self.stdout.write(f'\n{status} Refugi: {name[:50]}')
                self.stdout.write(f'    ID: {refugi_id}')
                self.stdout.write(f'    Condition: {condition} (tipus: {type(condition).__name__}, esperat: {expected_condition})')
                self.stdout.write(f'    Num contributed: {num_contributed}')
                self.stdout.write(f'    Amenities: {len(amenities)} comoditats')
                self.stdout.write(f'    Manque un mur: {manque_mur}')
            else:
                self.stdout.write(self.style.ERROR(f'\n✗ Refugi {refugi_id} no trobat'))
                fail_count += 1
        
        # Comptar estadístiques generals
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.SUCCESS('\nESTADÍSTIQUES GENERALS:'))
        
        all_docs = db.collection('data_refugis_lliures').stream()
        conditions_count = {0: 0, 1: 0, 2: 0, 3: 0, None: 0}
        
        for doc in all_docs:
            data = doc.to_dict()
            condition = data.get('condition')
            if condition is not None:
                conditions_count[int(condition)] += 1
            else:
                conditions_count[None] += 1
        
        self.stdout.write(f'\nTotal refugis per condition:')
        self.stdout.write(f'  Condition 0 (Pobre): {conditions_count[0]}')
        self.stdout.write(f'  Condition 1 (Correcte): {conditions_count[1]}')
        self.stdout.write(f'  Condition 2 (Bé): {conditions_count[2]}')
        self.stdout.write(f'  Condition 3 (Excel·lent): {conditions_count[3]}')
        self.stdout.write(f'  Sense condition: {conditions_count[None]}')
        
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.SUCCESS(f'\nVerificació completada: {success_count} OK, {fail_count} FAIL\n'))
