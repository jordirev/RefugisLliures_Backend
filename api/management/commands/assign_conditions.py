"""
Management command to assign conditions to all refugis based on their info_comp data.

This command calculates a condition score (0-3) for each refugi based on:
- Available amenities in info_comp
- Whether the refuge has a missing wall (manque_un_mur)

The condition is initialized with num_contributed_conditions = 1.
"""
import os
from django.core.management.base import BaseCommand
from django.conf import settings
import firebase_admin
from firebase_admin import credentials, firestore
from api.services.condition_service import ConditionService


class Command(BaseCommand):
    help = 'Assign conditions to all refugis based on their info_comp data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--collection',
            type=str,
            default='data_refugis_lliures',
            help='Firestore collection name'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without actually updating'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=500,
            help='Number of documents to process in a single batch (max 500)'
        )
        parser.add_argument(
            '--overwrite',
            action='store_true',
            help='Overwrite existing condition values'
        )

    def determine_condition(self, info_comp):
        """
        Determina la condició del refugi basant-se en info_comp.
        
        Args:
            info_comp: Diccionari amb la informació complementària
            
        Returns:
            int: Condició del refugi (0-3) o None si no hi ha info_comp
        """
        if not info_comp:
            return None
        
        # Si falta un mur, la condició és pèssima
        if info_comp.get('manque_un_mur', 0) == 1:
            return 0
        
        # Comptem les comoditats disponibles (tots els camps excepte manque_un_mur)
        amenities_fields = [
            'cheminee',
            'poele',
            'couvertures',
            'latrines',
            'bois',
            'eau',
            'matelas',
            'couchage',
            'bas_flancs',
            'lits',
            'mezzanine_etage'
        ]
        
        amenities_count = sum(
            1 for field in amenities_fields 
            if info_comp.get(field, 0) == 1
        )
        
        # Determinem la condició segons les comoditats
        if amenities_count >= 7:
            return 3  # Excel·lent
        elif amenities_count >= 5:
            return 2  # Bé
        elif amenities_count >= 3:
            return 1  # Correcte
        else:
            return 0  # Pobre

    def handle(self, *args, **options):
        collection_name = options['collection']
        dry_run = options['dry_run']
        batch_size = min(options['batch_size'], 500)  # Firestore limit
        overwrite = options['overwrite']

        # Initialize Firebase Admin SDK
        try:
            firebase_admin.get_app()
            self.stdout.write(self.style.SUCCESS('Firebase already initialized'))
        except ValueError:
            cred_path = os.path.join(settings.BASE_DIR, 'env', 'firebase-service-account.json')
            if not os.path.exists(cred_path):
                self.stdout.write(
                    self.style.ERROR(f'Credentials file not found: {cred_path}')
                )
                return
            
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
            self.stdout.write(self.style.SUCCESS('Firebase initialized successfully'))

        db = firestore.client()
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n=== DRY RUN MODE - No changes will be made ===\n'))
        
        # Fetch all documents
        self.stdout.write(f'Fetching all documents from {collection_name}...')
        docs = db.collection(collection_name).stream()
        
        # Process documents
        updated_count = 0
        skipped_count = 0
        no_info_comp_count = 0
        error_count = 0
        
        batch = db.batch()
        batch_counter = 0
        
        for doc in docs:
            try:
                data = doc.to_dict()
                refugi_id = doc.id
                
                # Skip if already has condition and not overwriting
                if not overwrite and 'condition' in data and data['condition'] is not None:
                    skipped_count += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f'Skipping {refugi_id} - Already has condition: {data["condition"]}'
                        )
                    )
                    continue
                
                # Get info_comp
                info_comp = data.get('info_comp')
                
                # Calculate condition
                calculated_condition = self.determine_condition(info_comp)
                
                if calculated_condition is None:
                    no_info_comp_count += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f'Skipping {refugi_id} - No info_comp available'
                        )
                    )
                    continue
                
                # Use ConditionService to initialize condition
                condition_data = ConditionService.initialize_condition(float(calculated_condition))
                
                if dry_run:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Would update {refugi_id}: condition={condition_data["condition"]}, '
                            f'num_contributed_conditions={condition_data["num_contributed_conditions"]}'
                        )
                    )
                else:
                    # Add to batch
                    doc_ref = db.collection(collection_name).document(refugi_id)
                    batch.update(doc_ref, condition_data)
                    batch_counter += 1
                    
                    # Commit batch if it reaches the batch size
                    if batch_counter >= batch_size:
                        batch.commit()
                        self.stdout.write(
                            self.style.SUCCESS(f'Committed batch of {batch_counter} updates')
                        )
                        batch = db.batch()
                        batch_counter = 0
                    
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Updated {refugi_id}: condition={condition_data["condition"]}, '
                            f'num_contributed_conditions={condition_data["num_contributed_conditions"]}'
                        )
                    )
                
                updated_count += 1
                
            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(f'Error processing {doc.id}: {str(e)}')
                )
        
        # Commit remaining documents in batch
        if not dry_run and batch_counter > 0:
            batch.commit()
            self.stdout.write(
                self.style.SUCCESS(f'Committed final batch of {batch_counter} updates')
            )
        
        # Summary
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('\nSUMMARY:'))
        self.stdout.write(f'Total refugis updated: {updated_count}')
        self.stdout.write(f'Refugis skipped (already have condition): {skipped_count}')
        self.stdout.write(f'Refugis skipped (no info_comp): {no_info_comp_count}')
        self.stdout.write(f'Errors: {error_count}')
        self.stdout.write('=' * 60 + '\n')
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('This was a DRY RUN. Use without --dry-run to apply changes.')
            )
