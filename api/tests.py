"""
Tests per a l'API de refugis utilitzant Firestore
"""
from django.test import TestCase, Client
from django.urls import reverse
from unittest.mock import patch, MagicMock
import json

class RefugiAPITestCase(TestCase):
    """Tests per als endpoints de l'API de refugis"""
    
    def setUp(self):
        self.client = Client()
    
    def test_health_check_endpoint(self):
        """Prova l'endpoint de health check"""
        url = reverse('health_check')
        response = self.client.get(url)
        
        # Comprova que la resposta tingui l'estructura correcta
        self.assertIn('status', response.json())
        self.assertIn('message', response.json())
        self.assertIn('firebase', response.json())
    
    @patch('api.services.firestore_service.firestore_service.get_db')
    def test_refugi_list_success(self, mock_get_db):
        """Prova l'endpoint de llista de refugis amb dades mock"""
        # Mock de Firestore
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_query = MagicMock()
        mock_docs = [
            MagicMock(id='test1', to_dict=lambda: {'nom': 'Refugi Test 1', 'altitude': 2000}),
            MagicMock(id='test2', to_dict=lambda: {'nom': 'Refugi Test 2', 'altitude': 1800})
        ]
        
        mock_db.collection.return_value = mock_collection
        mock_collection.limit.return_value = mock_query
        mock_query.stream.return_value = mock_docs
        mock_get_db.return_value = mock_db
        
        url = reverse('refugi_list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('count', data)
        self.assertIn('results', data)
        self.assertEqual(data['count'], 2)
        self.assertEqual(len(data['results']), 2)
    
    @patch('api.services.firestore_service.firestore_service.get_db')
    def test_refugi_detail_success(self, mock_get_db):
        """Prova l'endpoint de detall d'un refugi"""
        # Mock de Firestore
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_doc_ref = MagicMock()
        mock_doc = MagicMock()
        
        mock_db.collection.return_value = mock_collection
        mock_collection.document.return_value = mock_doc_ref
        mock_doc_ref.get.return_value = mock_doc
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {'nom': 'Refugi Test', 'altitude': 2000}
        mock_doc.id = 'test1'
        mock_get_db.return_value = mock_db
        
        url = reverse('refugi_detail', kwargs={'refugi_id': 'test1'})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['nom'], 'Refugi Test')
        self.assertEqual(data['id'], 'test1')
    
    @patch('api.services.firestore_service.firestore_service.get_db')
    def test_refugi_detail_not_found(self, mock_get_db):
        """Prova l'endpoint de detall quan el refugi no existeix"""
        # Mock de Firestore
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_doc_ref = MagicMock()
        mock_doc = MagicMock()
        
        mock_db.collection.return_value = mock_collection
        mock_collection.document.return_value = mock_doc_ref
        mock_doc_ref.get.return_value = mock_doc
        mock_doc.exists = False
        mock_get_db.return_value = mock_db
        
        url = reverse('refugi_detail', kwargs={'refugi_id': 'nonexistent'})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertIn('error', data)
    
    @patch('api.services.firestore_service.firestore_service.get_db')
    def test_search_refugis(self, mock_get_db):
        """Prova l'endpoint de cerca de refugis"""
        # Mock de Firestore
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_query = MagicMock()
        mock_docs = [
            MagicMock(id='test1', to_dict=lambda: {'nom': 'Cabane Test', 'comarca': 'TestComarca'}),
        ]
        
        mock_db.collection.return_value = mock_collection
        mock_collection.limit.return_value = mock_query
        mock_query.stream.return_value = mock_docs
        mock_get_db.return_value = mock_db
        
        url = reverse('search_refugis')
        response = self.client.get(url, {'q': 'test', 'limit': 10})
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('count', data)
        self.assertIn('results', data)
        self.assertIn('filters', data)
    
    @patch('api.services.firestore_service.firestore_service.get_db')
    def test_refugi_coordinates(self, mock_get_db):
        """Prova l'endpoint de coordenades de refugis des d'un sol document"""
        # Mock de Firestore per al document únic
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_doc_ref = MagicMock()
        mock_doc = MagicMock()
        
        # Mock del document únic amb totes les coordenades
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            'refugis_coordinates': [
                {
                    'refugi_id': 'test1',
                    'refugi_name': 'Test Refugi 1',
                    'coordinates': {'latitude': 42.123, 'longitude': 1.456},
                    'geohash': 'sp3dr'
                },
                {
                    'refugi_id': 'test2',
                    'refugi_name': 'Test Refugi 2',
                    'coordinates': {'latitude': 43.123, 'longitude': 2.456},
                    'geohash': 'sp4dr'
                }
            ],
            'total_refugis': 2,
            'created_at': 'test_timestamp'
        }
        
        mock_db.collection.return_value = mock_collection
        mock_collection.document.return_value = mock_doc_ref
        mock_doc_ref.get.return_value = mock_doc
        mock_get_db.return_value = mock_db
        
        url = reverse('refugi_coordinates')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('count', data)
        self.assertIn('coordinates', data)
        self.assertIn('total_available', data)
        self.assertEqual(data['count'], 2)
        self.assertEqual(data['total_available'], 2)
        self.assertEqual(len(data['coordinates']), 2)
        self.assertIn('refugi_id', data['coordinates'][0])
        self.assertIn('coordinates', data['coordinates'][0])
    
    def test_url_patterns(self):
        """Prova que totes les URLs es resolguin correctament"""
        urls_to_test = [
            'health_check',
            'refugi_list',
            'search_refugis',
            'refugi_coordinates',
        ]
        
        for url_name in urls_to_test:
            with self.subTest(url=url_name):
                url = reverse(url_name)
                self.assertIsNotNone(url)
        
        # Prova URL amb paràmetre
        url = reverse('refugi_detail', kwargs={'refugi_id': 'test'})
        self.assertIsNotNone(url)

