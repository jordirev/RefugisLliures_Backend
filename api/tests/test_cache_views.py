"""
Tests unitaris per a les views de cache
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate
from django.contrib.auth.models import User
from api.views.cache_views import cache_stats, cache_clear, cache_invalidate


# ============= FIXTURES =============

@pytest.fixture
def api_factory():
    """Factory per crear requests d'API"""
    return APIRequestFactory()


@pytest.fixture
def admin_user(db):
    """Usuari administrador per als tests"""
    user = User.objects.create_user(
        username='admin',
        email='admin@test.com',
        password='testpass123',
        is_staff=True,
        is_superuser=True
    )
    return user


@pytest.fixture
def mock_admin_claims():
    """Mock dels custom claims d'administrador per Firebase"""
    return {'role': 'admin', 'uid': 'test-admin-uid'}


@pytest.fixture
def regular_user(db):
    """Usuari regular (no admin) per als tests"""
    user = User.objects.create_user(
        username='user',
        email='user@test.com',
        password='testpass123',
        is_staff=False,
        is_superuser=False
    )
    return user


@pytest.fixture
def mock_cache_service():
    """Mock del servei de cache"""
    with patch('api.views.cache_views.cache_service') as mock_service:
        yield mock_service


# ============= TESTS CACHE_STATS =============

class TestCacheStatsView:
    """Tests per a la view cache_stats"""
    
    def test_cache_stats_success(self, api_factory, admin_user, mock_admin_claims, mock_cache_service):
        """Test: Obtenció exitosa d'estadístiques de cache"""
        # Arrange
        mock_stats = {
            'connected': True,
            'keys': 150,
            'memory_used': '2.5MB',
            'hits': 1000,
            'misses': 50
        }
        mock_cache_service.get_stats.return_value = mock_stats
        
        request = api_factory.get('/api/cache/stats/')
        force_authenticate(request, user=admin_user)
        request.user_uid = mock_admin_claims['uid']
        request.user_claims = mock_admin_claims  # Mock Firebase custom claims
        
        # Act
        response = cache_stats(request)
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data == mock_stats
        assert response.data['connected'] is True
        assert response.data['keys'] == 150
        mock_cache_service.get_stats.assert_called_once()
    
    def test_cache_stats_not_authenticated(self, api_factory):
        """Test: Accés sense autenticació"""
        # Arrange
        request = api_factory.get('/api/cache/stats/')
        # No force_authenticate - user is AnonymousUser
        
        # Act
        response = cache_stats(request)
        
        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_cache_stats_not_admin(self, api_factory, regular_user, mock_cache_service):
        """Test: Accés d'usuari no administrador"""
        # Arrange
        request = api_factory.get('/api/cache/stats/')
        force_authenticate(request, user=regular_user)
        
        # Act
        response = cache_stats(request)
        
        # Assert
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert not mock_cache_service.get_stats.called
    
    def test_cache_stats_service_exception(self, api_factory, admin_user, mock_admin_claims,
                                          mock_cache_service):
        """Test: Gestió d'excepcions del servei"""
        # Arrange
        mock_cache_service.get_stats.side_effect = Exception("Redis connection error")
        
        request = api_factory.get('/api/cache/stats/')
        force_authenticate(request, user=admin_user)
        request.user_uid = mock_admin_claims['uid']
        request.user_claims = mock_admin_claims  # Mock Firebase custom claims
        
        # Act
        response = cache_stats(request)
        
        # Assert
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert 'error' in response.data
        assert 'Error obtenint estadístiques de cache' in response.data['error']
        assert 'detail' in response.data
    
    def test_cache_stats_disconnected(self, api_factory, admin_user, mock_admin_claims,
                                     mock_cache_service):
        """Test: Estadístiques quan cache està desconnectat"""
        # Arrange
        mock_stats = {
            'connected': False,
            'error': 'Connection refused'
        }
        mock_cache_service.get_stats.return_value = mock_stats
        
        request = api_factory.get('/api/cache/stats/')
        force_authenticate(request, user=admin_user)
        request.user_uid = mock_admin_claims['uid']
        request.user_claims = mock_admin_claims  # Mock Firebase custom claims
        
        # Act
        response = cache_stats(request)
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data['connected'] is False
        assert 'error' in response.data
    
    def test_cache_stats_zero_keys(self, api_factory, admin_user, mock_admin_claims, mock_cache_service):
        """Test: Estadístiques amb cache buida"""
        # Arrange
        mock_stats = {
            'connected': True,
            'keys': 0,
            'memory_used': '0B',
            'hits': 0,
            'misses': 0
        }
        mock_cache_service.get_stats.return_value = mock_stats
        
        request = api_factory.get('/api/cache/stats/')
        force_authenticate(request, user=admin_user)
        request.user_uid = mock_admin_claims['uid']
        request.user_claims = mock_admin_claims  # Mock Firebase custom claims
        
        # Act
        response = cache_stats(request)
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data['keys'] == 0
        assert response.data['hits'] == 0
    
    def test_cache_stats_high_values(self, api_factory, admin_user, mock_admin_claims,
                                    mock_cache_service):
        """Test: Estadístiques amb valors alts (escenari límit)"""
        # Arrange
        mock_stats = {
            'connected': True,
            'keys': 999999,
            'memory_used': '500MB',
            'hits': 10000000,
            'misses': 1000000
        }
        mock_cache_service.get_stats.return_value = mock_stats
        
        request = api_factory.get('/api/cache/stats/')
        force_authenticate(request, user=admin_user)
        request.user_uid = mock_admin_claims['uid']
        request.user_claims = mock_admin_claims  # Mock Firebase custom claims
        
        # Act
        response = cache_stats(request)
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data['keys'] == 999999
        assert response.data['hits'] == 10000000


# ============= TESTS CACHE_CLEAR =============

class TestCacheClearView:
    """Tests per a la view cache_clear"""
    
    def test_cache_clear_success(self, api_factory, admin_user, mock_admin_claims, mock_cache_service):
        """Test: Neteja exitosa de la cache"""
        # Arrange
        mock_cache_service.clear_all.return_value = True
        
        request = api_factory.delete('/api/cache/clear/')
        force_authenticate(request, user=admin_user)
        request.user_uid = mock_admin_claims['uid']
        request.user_claims = mock_admin_claims  # Mock Firebase custom claims
        
        # Act
        response = cache_clear(request)
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert 'message' in response.data
        assert 'Cache netejada correctament' in response.data['message']
        mock_cache_service.clear_all.assert_called_once()
    
    def test_cache_clear_failure(self, api_factory, admin_user, mock_admin_claims, mock_cache_service):
        """Test: Error en netejar la cache"""
        # Arrange
        mock_cache_service.clear_all.return_value = False
        
        request = api_factory.delete('/api/cache/clear/')
        force_authenticate(request, user=admin_user)
        request.user_uid = mock_admin_claims['uid']
        request.user_claims = mock_admin_claims  # Mock Firebase custom claims
        
        # Act
        response = cache_clear(request)
        
        # Assert
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert 'error' in response.data
        assert 'Error netejant la cache' in response.data['error']
    
    def test_cache_clear_not_authenticated(self, api_factory):
        """Test: Accés sense autenticació"""
        # Arrange
        request = api_factory.delete('/api/cache/clear/')
        
        # Act
        response = cache_clear(request)
        
        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_cache_clear_not_admin(self, api_factory, regular_user, 
                                  mock_cache_service):
        """Test: Accés d'usuari no administrador"""
        # Arrange
        request = api_factory.delete('/api/cache/clear/')
        force_authenticate(request, user=regular_user)
        
        # Act
        response = cache_clear(request)
        
        # Assert
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert not mock_cache_service.clear_all.called
    
    def test_cache_clear_exception(self, api_factory, admin_user, mock_admin_claims,
                                   mock_cache_service):
        """Test: Gestió d'excepcions durant la neteja"""
        # Arrange
        mock_cache_service.clear_all.side_effect = Exception("Redis error")
        
        request = api_factory.delete('/api/cache/clear/')
        force_authenticate(request, user=admin_user)
        request.user_uid = mock_admin_claims['uid']
        request.user_claims = mock_admin_claims  # Mock Firebase custom claims
        
        # Act
        response = cache_clear(request)
        
        # Assert
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert 'error' in response.data
        assert 'detail' in response.data
    
    def test_cache_clear_wrong_method(self, api_factory, admin_user, mock_admin_claims):
        """Test: Ús de mètode HTTP incorrecte"""
        # Arrange
        request = api_factory.get('/api/cache/clear/')  # GET instead of DELETE
        force_authenticate(request, user=admin_user)
        request.user_uid = mock_admin_claims['uid']
        request.user_claims = mock_admin_claims  # Mock Firebase custom claims
        
        # Act
        response = cache_clear(request)
        
        # Assert
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    
    def test_cache_clear_post_method(self, api_factory, admin_user, mock_admin_claims):
        """Test: Ús de POST (també hauria de fallar)"""
        # Arrange
        request = api_factory.post('/api/cache/clear/')
        force_authenticate(request, user=admin_user)
        request.user_uid = mock_admin_claims['uid']
        request.user_claims = mock_admin_claims  # Mock Firebase custom claims
        
        # Act
        response = cache_clear(request)
        
        # Assert
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


# ============= TESTS CACHE_INVALIDATE =============

class TestCacheInvalidateView:
    """Tests per a la view cache_invalidate"""
    
    def test_cache_invalidate_success(self, api_factory, admin_user, mock_admin_claims,
                                     mock_cache_service):
        """Test: Invalidació exitosa de claus amb patró"""
        # Arrange
        mock_cache_service.delete_pattern.return_value = True
        
        request = api_factory.delete('/api/cache/invalidate/?pattern=refugi_*')
        force_authenticate(request, user=admin_user)
        request.user_uid = mock_admin_claims['uid']
        request.user_claims = mock_admin_claims  # Mock Firebase custom claims
        
        # Act
        response = cache_invalidate(request)
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert 'message' in response.data
        assert 'refugi_*' in response.data['message']
        mock_cache_service.delete_pattern.assert_called_once_with('refugi_*')
    
    def test_cache_invalidate_no_pattern(self, api_factory, admin_user, mock_admin_claims,
                                        mock_cache_service):
        """Test: Error quan no es proporciona el patró"""
        # Arrange
        request = api_factory.delete('/api/cache/invalidate/')  # No pattern param
        force_authenticate(request, user=admin_user)
        request.user_uid = mock_admin_claims['uid']
        request.user_claims = mock_admin_claims  # Mock Firebase custom claims
        
        # Act
        response = cache_invalidate(request)
        
        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data
        assert 'Patró no proporcionat' in response.data['error']
        assert not mock_cache_service.delete_pattern.called
    
    def test_cache_invalidate_empty_pattern(self, api_factory, admin_user, mock_admin_claims,
                                           mock_cache_service):
        """Test: Patró buit"""
        # Arrange
        request = api_factory.delete('/api/cache/invalidate/?pattern=')
        force_authenticate(request, user=admin_user)
        request.user_uid = mock_admin_claims['uid']
        request.user_claims = mock_admin_claims  # Mock Firebase custom claims
        
        # Act
        response = cache_invalidate(request)
        
        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'Patró no proporcionat' in response.data['error']
    
    def test_cache_invalidate_failure(self, api_factory, admin_user, mock_admin_claims,
                                     mock_cache_service):
        """Test: Error en invalidar claus"""
        # Arrange
        mock_cache_service.delete_pattern.return_value = False
        
        request = api_factory.delete('/api/cache/invalidate/?pattern=test_*')
        force_authenticate(request, user=admin_user)
        request.user_uid = mock_admin_claims['uid']
        request.user_claims = mock_admin_claims  # Mock Firebase custom claims
        
        # Act
        response = cache_invalidate(request)
        
        # Assert
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert 'error' in response.data
        assert 'Error eliminant claus' in response.data['error']
    
    def test_cache_invalidate_not_authenticated(self, api_factory):
        """Test: Accés sense autenticació"""
        # Arrange
        request = api_factory.delete('/api/cache/invalidate/?pattern=test_*')
        
        # Act
        response = cache_invalidate(request)
        
        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_cache_invalidate_not_admin(self, api_factory, regular_user, 
                                       mock_cache_service):
        """Test: Accés d'usuari no administrador"""
        # Arrange
        request = api_factory.delete('/api/cache/invalidate/?pattern=test_*')
        force_authenticate(request, user=regular_user)
        
        # Act
        response = cache_invalidate(request)
        
        # Assert
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert not mock_cache_service.delete_pattern.called
    
    def test_cache_invalidate_exception(self, api_factory, admin_user, mock_admin_claims,
                                       mock_cache_service):
        """Test: Gestió d'excepcions durant la invalidació"""
        # Arrange
        mock_cache_service.delete_pattern.side_effect = Exception("Redis error")
        
        request = api_factory.delete('/api/cache/invalidate/?pattern=test_*')
        force_authenticate(request, user=admin_user)
        request.user_uid = mock_admin_claims['uid']
        request.user_claims = mock_admin_claims  # Mock Firebase custom claims
        
        # Act
        response = cache_invalidate(request)
        
        # Assert
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert 'error' in response.data
        assert 'detail' in response.data
    
    def test_cache_invalidate_complex_pattern(self, api_factory, admin_user, mock_admin_claims,
                                             mock_cache_service):
        """Test: Patró complex amb wildcards"""
        # Arrange
        mock_cache_service.delete_pattern.return_value = True
        complex_pattern = 'refugi_list:*:page_*'
        
        request = api_factory.delete(f'/api/cache/invalidate/?pattern={complex_pattern}')
        force_authenticate(request, user=admin_user)
        request.user_uid = mock_admin_claims['uid']
        request.user_claims = mock_admin_claims  # Mock Firebase custom claims
        
        # Act
        response = cache_invalidate(request)
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert complex_pattern in response.data['message']
        mock_cache_service.delete_pattern.assert_called_once_with(complex_pattern)
    
    def test_cache_invalidate_special_characters(self, api_factory, admin_user, mock_admin_claims,
                                                 mock_cache_service):
        """Test: Patró amb caràcters especials"""
        # Arrange
        mock_cache_service.delete_pattern.return_value = True
        pattern = 'user:42:data_*'
        
        request = api_factory.delete(f'/api/cache/invalidate/?pattern={pattern}')
        force_authenticate(request, user=admin_user)
        request.user_uid = mock_admin_claims['uid']
        request.user_claims = mock_admin_claims  # Mock Firebase custom claims
        
        # Act
        response = cache_invalidate(request)
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        mock_cache_service.delete_pattern.assert_called_once_with(pattern)
    
    def test_cache_invalidate_single_key_pattern(self, api_factory, admin_user, mock_admin_claims,
                                                mock_cache_service):
        """Test: Patró per a una sola clau específica"""
        # Arrange
        mock_cache_service.delete_pattern.return_value = True
        pattern = 'refugi_detail:123'
        
        request = api_factory.delete(f'/api/cache/invalidate/?pattern={pattern}')
        force_authenticate(request, user=admin_user)
        request.user_uid = mock_admin_claims['uid']
        request.user_claims = mock_admin_claims  # Mock Firebase custom claims
        
        # Act
        response = cache_invalidate(request)
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        mock_cache_service.delete_pattern.assert_called_once_with(pattern)
    
    def test_cache_invalidate_wildcard_only(self, api_factory, admin_user, mock_admin_claims,
                                           mock_cache_service):
        """Test: Patró amb només wildcard (cas límit)"""
        # Arrange
        mock_cache_service.delete_pattern.return_value = True
        pattern = '*'
        
        request = api_factory.delete(f'/api/cache/invalidate/?pattern={pattern}')
        force_authenticate(request, user=admin_user)
        request.user_uid = mock_admin_claims['uid']
        request.user_claims = mock_admin_claims  # Mock Firebase custom claims
        
        # Act
        response = cache_invalidate(request)
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        mock_cache_service.delete_pattern.assert_called_once_with(pattern)
    
    def test_cache_invalidate_wrong_method(self, api_factory, admin_user, mock_admin_claims):
        """Test: Ús de mètode HTTP incorrecte"""
        # Arrange
        request = api_factory.get('/api/cache/invalidate/?pattern=test_*')
        force_authenticate(request, user=admin_user)
        request.user_uid = mock_admin_claims['uid']
        request.user_claims = mock_admin_claims  # Mock Firebase custom claims
        
        # Act
        response = cache_invalidate(request)
        
        # Assert
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    
    def test_cache_invalidate_multiple_patterns_in_query(self, api_factory, admin_user,
                                                        mock_admin_claims, mock_cache_service):
        """Test: Múltiples valors de pattern (només s'agafa el primer)"""
        # Arrange
        mock_cache_service.delete_pattern.return_value = True
        
        # Django takes the first value when multiple params with same name
        request = api_factory.delete('/api/cache/invalidate/?pattern=first_*&pattern=second_*')
        force_authenticate(request, user=admin_user)
        request.user_uid = mock_admin_claims['uid']
        request.user_claims = mock_admin_claims  # Mock Firebase custom claims
        
        # Act
        response = cache_invalidate(request)
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        # Should use the first pattern
        mock_cache_service.delete_pattern.assert_called_once()


# ============= TESTS D'INTEGRACIÓ ENTRE VIEWS =============

class TestCacheViewsIntegration:
    """Tests d'integració entre diferents views de cache"""
    
    def test_stats_after_clear(self, api_factory, admin_user, mock_admin_claims, mock_cache_service):
        """Test: Obtenir estadístiques després de netejar la cache"""
        # Arrange - Clear
        mock_cache_service.clear_all.return_value = True
        request_clear = api_factory.delete('/api/cache/clear/')
        force_authenticate(request_clear, user=admin_user)
        request_clear.user_uid = mock_admin_claims  # Mock Firebase admin UID
        
        # Act - Clear
        response_clear = cache_clear(request_clear)
        
        # Assert - Clear
        assert response_clear.status_code == status.HTTP_200_OK
        
        # Arrange - Stats after clear
        mock_cache_service.get_stats.return_value = {
            'connected': True,
            'keys': 0,
            'memory_used': '0B',
            'hits': 0,
            'misses': 0
        }
        request_stats = api_factory.get('/api/cache/stats/')
        force_authenticate(request_stats, user=admin_user)
        request_stats.user_uid = mock_admin_claims  # Mock Firebase admin UID
        
        # Act - Stats
        response_stats = cache_stats(request_stats)
        
        # Assert - Stats
        assert response_stats.status_code == status.HTTP_200_OK
        assert response_stats.data['keys'] == 0
    
    def test_invalidate_then_stats(self, api_factory, admin_user, mock_admin_claims, mock_cache_service):
        """Test: Invalidar claus i després verificar amb stats"""
        # Arrange - Invalidate
        mock_cache_service.delete_pattern.return_value = True
        request_invalidate = api_factory.delete('/api/cache/invalidate/?pattern=test_*')
        force_authenticate(request_invalidate, user=admin_user)
        request_invalidate.user_uid = mock_admin_claims  # Mock Firebase admin UID
        
        # Act - Invalidate
        response_invalidate = cache_invalidate(request_invalidate)
        
        # Assert - Invalidate
        assert response_invalidate.status_code == status.HTTP_200_OK
        
        # Arrange - Stats
        mock_cache_service.get_stats.return_value = {
            'connected': True,
            'keys': 50,  # Reduced from before
            'memory_used': '1MB',
            'hits': 1000,
            'misses': 100
        }
        request_stats = api_factory.get('/api/cache/stats/')
        force_authenticate(request_stats, user=admin_user)
        request_stats.user_uid = mock_admin_claims  # Mock Firebase admin UID
        
        # Act - Stats
        response_stats = cache_stats(request_stats)
        
        # Assert - Stats
        assert response_stats.status_code == status.HTTP_200_OK
        assert response_stats.data['keys'] == 50
