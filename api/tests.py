from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status


class HealthCheckTestCase(TestCase):
    """Test cases for the health check endpoint"""
    
    def setUp(self):
        """Set up test client"""
        self.client = APIClient()
    
    def test_health_check_endpoint(self):
        """Test that health check endpoint returns 200 OK"""
        response = self.client.get('/api/health/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'ok')
        self.assertIn('message', response.data)

