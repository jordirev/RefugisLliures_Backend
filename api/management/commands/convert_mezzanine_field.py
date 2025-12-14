"""
Management command to convert 'mezzanine/etage' field to 'mezzanine_etage'
in all documents of the data_refugis_lliures collection.

This command updates the field name in the info_comp nested object from
'mezzanine/etage' to 'mezzanine_etage' to maintain consistency with Python
naming conventions and avoid issues with the '/' character in field names.
"""
import os
from django.core.management.base import BaseCommand
from django.conf import settings
import firebase_admin
from firebase_admin import credentials, firestore


class Command(BaseCommand):
    help = 'Convert mezzanine/etage field to mezzanine_etage in all refugis'

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

    def handle(self, *args, **options):
        collection_name = options['collection']
        dry_run = options['dry_run']
        batch_size = min(options['batch_size'], 500)  # Firestore limit

        # Initialize Firebase Admin SDK
        try:
            # Check if Firebase is already initialized
            firebase_admin.get_app()
            self.stdout.write(self.style.SUCCESS('Firebase already initialized'))
        except ValueError:
            # Initialize Firebase
            cred_path = os.path.join(settings.BASE_DIR, 'env', 'firebase-service-account.json')
            if not os.path.exists(cred_path):
                self.stdout.write(
                    self.style.ERROR(f'Firebase credentials file not found at {cred_path}')
                )
                return

            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
            self.stdout.write(self.style.SUCCESS('Firebase initialized'))

        # Initialize Firestore client
        db = firestore.client()
        collection_ref = db.collection(collection_name)

        self.stdout.write(
            self.style.SUCCESS(f'\nProcessing collection: {collection_name}')
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No data will be modified\n')
            )

        # Get all documents
        docs = collection_ref.stream()
        
        total_docs = 0
        updated_docs = 0
        skipped_docs = 0
        error_docs = 0

        batch = db.batch()
        batch_count = 0

        for doc in docs:
            total_docs += 1
            doc_data = doc.to_dict()
            doc_id = doc.id

            # Check if the document has info_comp field
            if 'info_comp' not in doc_data or not doc_data['info_comp']:
                self.stdout.write(
                    self.style.WARNING(f'  Skipped {doc_id}: No info_comp field')
                )
                skipped_docs += 1
                continue

            info_comp = doc_data['info_comp']
            
            # Check if the old field exists
            if 'mezzanine/etage' not in info_comp:
                self.stdout.write(
                    self.style.WARNING(f'  Skipped {doc_id}: No mezzanine/etage field')
                )
                skipped_docs += 1
                continue

            # Get the value and prepare the update
            old_value = info_comp['mezzanine/etage']
            
            if dry_run:
                self.stdout.write(
                    f'  Would update {doc_id}: mezzanine/etage={old_value} -> mezzanine_etage={old_value}'
                )
                updated_docs += 1
            else:
                try:
                    # Create a new info_comp dict with the updated field
                    new_info_comp = info_comp.copy()
                    new_info_comp['mezzanine_etage'] = old_value
                    del new_info_comp['mezzanine/etage']
                    
                    # Update the entire info_comp object
                    doc_ref = collection_ref.document(doc_id)
                    batch.update(doc_ref, {
                        'info_comp': new_info_comp
                    })
                    batch_count += 1
                    updated_docs += 1
                    
                    self.stdout.write(
                        self.style.SUCCESS(f'  Queued {doc_id}: mezzanine/etage={old_value} -> mezzanine_etage={old_value}')
                    )

                    # Commit batch when it reaches the batch size
                    if batch_count >= batch_size:
                        batch.commit()
                        self.stdout.write(
                            self.style.SUCCESS(f'\n  Committed batch of {batch_count} updates\n')
                        )
                        batch = db.batch()
                        batch_count = 0

                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'  Error updating {doc_id}: {str(e)}')
                    )
                    error_docs += 1

        # Commit any remaining updates in the batch
        if batch_count > 0 and not dry_run:
            try:
                batch.commit()
                self.stdout.write(
                    self.style.SUCCESS(f'\n  Committed final batch of {batch_count} updates\n')
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'\n  Error committing final batch: {str(e)}\n')
                )

        # Print summary
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('SUMMARY'))
        self.stdout.write('='*60)
        self.stdout.write(f'Total documents processed: {total_docs}')
        self.stdout.write(self.style.SUCCESS(f'Documents updated: {updated_docs}'))
        self.stdout.write(self.style.WARNING(f'Documents skipped: {skipped_docs}'))
        if error_docs > 0:
            self.stdout.write(self.style.ERROR(f'Documents with errors: {error_docs}'))
        self.stdout.write('='*60 + '\n')

        if dry_run:
            self.stdout.write(
                self.style.WARNING('\nThis was a dry run. Run without --dry-run to apply changes.')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('\nField conversion completed successfully!')
            )
