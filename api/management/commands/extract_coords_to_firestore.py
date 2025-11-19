import os
from django.core.management.base import BaseCommand
from django.conf import settings
import firebase_admin
from firebase_admin import credentials, firestore
from pathlib import Path


class Command(BaseCommand):
    help = 'Extract coordinates from existing refugis in Firestore and create a coords_refugis collection'

    def add_arguments(self, parser):
        parser.add_argument(
            '--source-collection',
            type=str,
            default='data_refugis_lliures',
            help='Source Firestore collection name'
        )
        parser.add_argument(
            '--target-collection',
            type=str,
            default='coords_refugis',
            help='Target Firestore collection name for coordinates'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without actually creating documents'
        )
        parser.add_argument(
            '--clear-target',
            action='store_true',
            help='Clear target collection before adding new documents'
        )

    def handle(self, *args, **options):
        source_collection = options['source_collection']
        target_collection = options['target_collection']
        dry_run = options['dry_run']
        clear_target = options['clear_target']

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

        db = firestore.client()

        try:
            # Clear target collection if requested
            if clear_target and not dry_run:
                self.stdout.write(f'Clearing target collection: {target_collection}')
                self._clear_collection(db, target_collection)

            # Get all documents from source collection
            self.stdout.write(f'Reading refugis from collection: {source_collection}')
            refugis_ref = db.collection(source_collection)
            docs = refugis_ref.stream()

            processed_count = 0
            skipped_count = 0
            coords_data = []

            for doc in docs:
                doc_data = doc.to_dict()
                refuge_id = doc.id

                # Extract coordinates
                coord_info = doc_data.get('coord', {})
                
                if not coord_info or 'lat' not in coord_info or 'long' not in coord_info:
                    self.stdout.write(
                        self.style.WARNING(f'Skipping refugi {refuge_id}: missing coordinates')
                    )
                    skipped_count += 1
                    continue

                # Prepare coordinate document
                coord_doc = {
                    'refuge_id': refuge_id,
                    'coordinates': {
                        'latitude': coord_info['lat'],
                        'longitude': coord_info['long']
                    },
                    # Add geohash for efficient geo queries (optional)
                    'geohash': self._generate_simple_geohash(coord_info['lat'], coord_info['long'])
                }

                # Add refugi name if available for easier identification
                if 'name' in doc_data:
                    coord_doc['refugi_name'] = doc_data['name']

                coords_data.append({
                    'id': refuge_id,
                    'data': coord_doc
                })

                processed_count += 1

                if dry_run:
                    self.stdout.write(
                        f'[DRY RUN] Would create coordinate document for refugi: {refuge_id} '
                        f'(lat: {coord_info["lat"]}, long: {coord_info["long"]})'
                    )

            if not dry_run:
                # Create a single document with all coordinates
                self.stdout.write(f'Writing all {len(coords_data)} coordinates to a single document in {target_collection}')
                
                # Prepare the single document with all coordinates
                all_coords_doc = {
                    'refugis_coordinates': [coord_item['data'] for coord_item in coords_data],
                    'total_refugis': len(coords_data),
                    'created_at': firestore.SERVER_TIMESTAMP,
                    'last_updated': firestore.SERVER_TIMESTAMP
                }
                
                target_ref = db.collection(target_collection)
                doc_ref = target_ref.document('all_refugis_coords')  # Single document ID
                doc_ref.set(all_coords_doc)
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Successfully created single document with {processed_count} refugi coordinates in collection: {target_collection}'
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'[DRY RUN] Would create a single document with {processed_count} refugi coordinates'
                    )
                )

            if skipped_count > 0:
                self.stdout.write(
                    self.style.WARNING(f'Skipped {skipped_count} refugis due to missing coordinates')
                )

            # Show collection stats
            if not dry_run:
                self._show_collection_stats(db, target_collection)

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error processing refugis: {str(e)}')
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
            
        self.stdout.write(f'Cleared {count} documents from {collection_name}')

    def _show_collection_stats(self, db, collection_name):
        """Show statistics about the collection"""
        try:
            doc_ref = db.collection(collection_name).document('all_refugis_coords')
            doc = doc_ref.get()
            if doc.exists:
                data = doc.to_dict()
                refugis_count = data.get('total_refugis', 0)
                self.stdout.write(f'Collection {collection_name} contains 1 document with {refugis_count} refugi coordinates')
            else:
                self.stdout.write(f'Collection {collection_name} is empty')
        except Exception as e:
            self.stdout.write(f'Could not get collection stats: {str(e)}')

    def _generate_simple_geohash(self, lat, lng, precision=5):
        """Generate a simple geohash for geographical indexing"""
        # Simple implementation for demonstration
        # In production, consider using a proper geohash library
        lat_range = [-90.0, 90.0]
        lng_range = [-180.0, 180.0]
        
        geohash = ""
        bits = 0
        ch = 0
        even = True
        
        base32 = "0123456789bcdefghjkmnpqrstuvwxyz"
        
        while len(geohash) < precision:
            if even:  # longitude
                mid = (lng_range[0] + lng_range[1]) / 2
                if lng >= mid:
                    ch |= (1 << (4 - bits))
                    lng_range[0] = mid
                else:
                    lng_range[1] = mid
            else:  # latitude
                mid = (lat_range[0] + lat_range[1]) / 2
                if lat >= mid:
                    ch |= (1 << (4 - bits))
                    lat_range[0] = mid
                else:
                    lat_range[1] = mid
                    
            even = not even
            bits += 1
            
            if bits == 5:
                geohash += base32[ch]
                bits = 0
                ch = 0
                
        return geohash