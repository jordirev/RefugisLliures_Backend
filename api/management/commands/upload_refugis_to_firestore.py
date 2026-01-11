import json
import os
from django.core.management.base import BaseCommand
from django.conf import settings
import firebase_admin
from firebase_admin import credentials, firestore
from pathlib import Path


"""
IMPORTANT: Aquesta comanda està dissenyada per a ser executada una sola vegada per migrar les dades dels refugis existents a una nova col·lecció
anomenada 'data_refugis_lliures'. Aquesta col·lecció contindrà un document per a cada refugi amb tota la informació rellevant.

Si ja s'ha executat aquesta comanda i la col·lecció 'data_refugis_lliures' ja existeix, NO s'ha d'executar de nou per evitar duplicats, inconsistències o perdua d'informació.

"""

class Command(BaseCommand):
    help = 'Upload refugis data from JSON to Firestore'

    def add_arguments(self, parser):
        parser.add_argument(
            '--json-file',
            type=str,
            default='api/utils/final_data_refuges.json',
            help='Path to the JSON file with refugis data'
        )
        parser.add_argument(
            '--collection',
            type=str,
            default='data_refugis_lliures',
            help='Firestore collection name'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be uploaded without actually uploading'
        )
        parser.add_argument(
            '--clear-collection',
            action='store_true',
            help='Clear the collection before uploading new data'
        )

    def _clear_collection(self, db, collection_name):
        """Clear all documents from a collection"""
        docs = db.collection(collection_name).stream()
        batch = db.batch()
        
        count = 0
        for doc in docs:
            batch.delete(doc.reference)
            count += 1
            
            # Commit in batches of 500 (Firestore limit)
            if count % 500 == 0:
                batch.commit()
                batch = db.batch()
        
        # Commit remaining
        if count % 500 != 0:
            batch.commit()
            
        self.stdout.write(self.style.SUCCESS(f'Cleared {count} documents from {collection_name}'))
        return count

    def handle(self, *args, **options):
        json_file = options['json_file']
        collection_name = options['collection']
        dry_run = options['dry_run']
        clear_collection = options['clear_collection']

        # Initialize Firebase Admin SDK
        try:
            # Check if Firebase is already initialized
            firebase_admin.get_app()
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

        # Initialize Firestore client
        db = firestore.client()

        # Clear collection if requested
        if clear_collection:
            if dry_run:
                self.stdout.write(
                    self.style.WARNING(f'[DRY RUN] Would clear collection: {collection_name}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Clearing collection: {collection_name}...')
                )
                self._clear_collection(db, collection_name)

        # Load JSON data
        json_path = os.path.join(settings.BASE_DIR, json_file)
        if not os.path.exists(json_path):
            self.stdout.write(
                self.style.ERROR(f'JSON file not found at {json_path}')
            )
            return

        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                refugis_data = json.load(f)
        except json.JSONDecodeError as e:
            self.stdout.write(
                self.style.ERROR(f'Error parsing JSON file: {e}')
            )
            return

        if not isinstance(refugis_data, list):
            self.stdout.write(
                self.style.ERROR('JSON file must contain an array of refugis')
            )
            return

        self.stdout.write(
            self.style.SUCCESS(f'Found {len(refugis_data)} refugis in JSON file')
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN - No data will be uploaded')
            )
            for i, refugi in enumerate(refugis_data):
                self.stdout.write(f'Would upload refugi {i}: {refugi.get("name", "Unknown")}')
            return

        # Upload data to Firestore
        collection_ref = db.collection(collection_name)
        uploaded_count = 0
        errors = 0

        for i, refugi_data in enumerate(refugis_data):
            try:
                # Create document with auto-generated ID
                doc_ref = collection_ref.document()
                
                # Add the Firebase auto-generated ID to the document data
                refugi_data['id'] = doc_ref.id
                
                # Upload the document
                doc_ref.set(refugi_data)
                
                uploaded_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Uploaded refugi {i}: {refugi_data.get("name", "Unknown")} with ID: {doc_ref.id}')
                )
                
            except Exception as e:
                errors += 1
                self.stdout.write(
                    self.style.ERROR(f'✗ Error uploading refugi {i}: {e}')
                )

        # Summary
        self.stdout.write(
            self.style.SUCCESS(f'\n--- Upload Summary ---')
        )
        self.stdout.write(
            self.style.SUCCESS(f'Successfully uploaded: {uploaded_count} documents')
        )
        if errors > 0:
            self.stdout.write(
                self.style.ERROR(f'Errors: {errors} documents failed')
            )
        self.stdout.write(
            self.style.SUCCESS(f'Collection: {collection_name}')
        )