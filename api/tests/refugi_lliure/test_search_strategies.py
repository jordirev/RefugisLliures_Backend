"""
Tests complerts per les estratègies de cerca de refugis i el DAO
"""

import pytest
from unittest.mock import MagicMock, patch, Mock
from api.models.refugi_lliure import RefugiSearchFilters
from api.daos.search_strategies import (
    SearchStrategySelector,
    TypeConditionStrategy,
    TypeConditionPlacesStrategy,
    TypeConditionAltitudeStrategy,
    TypeConditionPlacesAltitudeStrategy,
    TypePlacesStrategy,
    TypeAltitudeStrategy,
    ConditionPlacesStrategy,
    ConditionAltitudeStrategy,
    TypePlacesAltitudeStrategy,
    ConditionPlacesAltitudeStrategy,
    PlacesAltitudeStrategy,
    TypeOnlyStrategy,
    ConditionOnlyStrategy,
    PlacesOnlyStrategy,
    AltitudeOnlyStrategy
)
from api.daos.refugi_lliure_dao import RefugiLliureDAO


# ==================== TESTS PER SearchStrategySelector ====================

class TestSearchStrategySelector:
    """Tests per al selector d'estratègies"""
    
    def test_select_type_condition_places_altitude(self):
        """Test selecció: type + condition + places + altitude"""
        filters = RefugiSearchFilters()
        filters.type = ["Cabane"]
        filters.condition = ["Bon estat"]
        filters.places_min = 5
        filters.altitude_min = 2000
        
        strategy = SearchStrategySelector.select_strategy(filters)
        assert isinstance(strategy, TypeConditionPlacesAltitudeStrategy)
        assert strategy.get_strategy_name() == "TypeConditionPlacesAltitudeStrategy"
    
    def test_select_type_condition_places(self):
        """Test selecció: type + condition + places"""
        filters = RefugiSearchFilters()
        filters.type = ["Cabane"]
        filters.condition = ["Bon estat"]
        filters.places_min = 5
        
        strategy = SearchStrategySelector.select_strategy(filters)
        assert isinstance(strategy, TypeConditionPlacesStrategy)
        assert strategy.get_strategy_name() == "TypeConditionPlacesStrategy"
    
    def test_select_type_condition_altitude(self):
        """Test selecció: type + condition + altitude"""
        filters = RefugiSearchFilters()
        filters.type = ["Cabane"]
        filters.condition = ["Bon estat"]
        filters.altitude_min = 2000
        
        strategy = SearchStrategySelector.select_strategy(filters)
        assert isinstance(strategy, TypeConditionAltitudeStrategy)
        assert strategy.get_strategy_name() == "TypeConditionAltitudeStrategy"
    
    def test_select_type_places_altitude(self):
        """Test selecció: type + places + altitude"""
        filters = RefugiSearchFilters()
        filters.type = ["Cabane"]
        filters.places_min = 5
        filters.altitude_min = 2000
        
        strategy = SearchStrategySelector.select_strategy(filters)
        assert isinstance(strategy, TypePlacesAltitudeStrategy)
        assert strategy.get_strategy_name() == "TypePlacesAltitudeStrategy"
    
    def test_select_type_places(self):
        """Test selecció: type + places"""
        filters = RefugiSearchFilters()
        filters.type = ["Cabane"]
        filters.places_min = 5
        
        strategy = SearchStrategySelector.select_strategy(filters)
        assert isinstance(strategy, TypePlacesStrategy)
        assert strategy.get_strategy_name() == "TypePlacesStrategy"
    
    def test_select_type_altitude(self):
        """Test selecció: type + altitude"""
        filters = RefugiSearchFilters()
        filters.type = ["Cabane"]
        filters.altitude_min = 2000
        
        strategy = SearchStrategySelector.select_strategy(filters)
        assert isinstance(strategy, TypeAltitudeStrategy)
        assert strategy.get_strategy_name() == "TypeAltitudeStrategy"
    
    def test_select_type_only(self):
        """Test selecció: només type"""
        filters = RefugiSearchFilters()
        filters.type = ["Cabane"]
        
        strategy = SearchStrategySelector.select_strategy(filters)
        assert isinstance(strategy, TypeOnlyStrategy)
        assert strategy.get_strategy_name() == "TypeOnlyStrategy"
    
    def test_select_condition_places_altitude(self):
        """Test selecció: condition + places + altitude"""
        filters = RefugiSearchFilters()
        filters.condition = ["Bon estat"]
        filters.places_min = 5
        filters.altitude_min = 2000
        
        strategy = SearchStrategySelector.select_strategy(filters)
        assert isinstance(strategy, ConditionPlacesAltitudeStrategy)
        assert strategy.get_strategy_name() == "ConditionPlacesAltitudeStrategy"
    
    def test_select_condition_places(self):
        """Test selecció: condition + places"""
        filters = RefugiSearchFilters()
        filters.condition = ["Bon estat"]
        filters.places_min = 5
        
        strategy = SearchStrategySelector.select_strategy(filters)
        assert isinstance(strategy, ConditionPlacesStrategy)
        assert strategy.get_strategy_name() == "ConditionPlacesStrategy"
    
    def test_select_condition_altitude(self):
        """Test selecció: condition + altitude"""
        filters = RefugiSearchFilters()
        filters.condition = ["Bon estat"]
        filters.altitude_min = 2000
        
        strategy = SearchStrategySelector.select_strategy(filters)
        assert isinstance(strategy, ConditionAltitudeStrategy)
        assert strategy.get_strategy_name() == "ConditionAltitudeStrategy"
    
    def test_select_condition_only(self):
        """Test selecció: només condition"""
        filters = RefugiSearchFilters()
        filters.condition = ["Bon estat"]
        
        strategy = SearchStrategySelector.select_strategy(filters)
        assert isinstance(strategy, ConditionOnlyStrategy)
        assert strategy.get_strategy_name() == "ConditionOnlyStrategy"
    
    def test_select_places_altitude(self):
        """Test selecció: places + altitude"""
        filters = RefugiSearchFilters()
        filters.places_min = 5
        filters.altitude_min = 2000
        
        strategy = SearchStrategySelector.select_strategy(filters)
        assert isinstance(strategy, PlacesAltitudeStrategy)
        assert strategy.get_strategy_name() == "PlacesAltitudeStrategy"
    
    def test_select_places_only(self):
        """Test selecció: només places"""
        filters = RefugiSearchFilters()
        filters.places_min = 5
        
        strategy = SearchStrategySelector.select_strategy(filters)
        assert isinstance(strategy, PlacesOnlyStrategy)
        assert strategy.get_strategy_name() == "PlacesOnlyStrategy"
    
    def test_select_altitude_only(self):
        """Test selecció: només altitude"""
        filters = RefugiSearchFilters()
        filters.altitude_min = 2000
        
        strategy = SearchStrategySelector.select_strategy(filters)
        assert isinstance(strategy, AltitudeOnlyStrategy)
        assert strategy.get_strategy_name() == "AltitudeOnlyStrategy"
    
    def test_select_no_filters_raises_error(self):
        """Test selecció sense filtres actius llança error"""
        filters = RefugiSearchFilters()
        
        with pytest.raises(ValueError, match="No s'ha pogut determinar cap estratègia"):
            SearchStrategySelector.select_strategy(filters)


# ==================== TESTS PER ESTRATÈGIES INDIVIDUALS ====================

class TestIndividualStrategies:
    """Tests per a l'execució de cada estratègia"""
    
    def setup_mock_db(self, return_data):
        """Helper per configurar mock de Firestore"""
        mock_db = MagicMock()
        mock_doc = MagicMock()
        mock_doc.to_dict.return_value = return_data
        # Set doc.id to match the id in return_data
        mock_doc.id = return_data.get('id', '001')
        
        mock_query = MagicMock()
        mock_query.stream.return_value = [mock_doc]
        mock_query.where.return_value = mock_query
        
        mock_collection = MagicMock()
        mock_collection.where.return_value = mock_query
        mock_db.collection.return_value = mock_collection
        
        return mock_db
    
    def test_type_condition_places_strategy(self):
        """Test TypeConditionPlacesStrategy"""
        refugi_data = {'id': '001', 'name': 'Test', 'type': 'Cabane', 'condition': 'Bon estat', 'places': 10}
        mock_db = self.setup_mock_db(refugi_data)
        
        filters = RefugiSearchFilters()
        filters.type = ["Cabane"]
        filters.condition = ["Bon estat"]
        filters.places_min = 5
        filters.places_max = 15
        
        strategy = TypeConditionPlacesStrategy()
        results = strategy.execute_query(mock_db, 'test_collection', filters)
        
        assert len(results) == 1
        assert results[0]['id'] == '001'
    
    def test_type_condition_altitude_strategy(self):
        """Test TypeConditionAltitudeStrategy"""
        refugi_data = {'id': '001', 'altitude': 2500, 'type': 'Cabane', 'condition': 'Bon estat'}
        mock_db = self.setup_mock_db(refugi_data)
        
        filters = RefugiSearchFilters()
        filters.type = ["Cabane"]
        filters.condition = ["Bon estat"]
        filters.altitude_min = 2000
        filters.altitude_max = 3000
        
        strategy = TypeConditionAltitudeStrategy()
        results = strategy.execute_query(mock_db, 'test_collection', filters)
        
        assert len(results) == 1
        assert results[0]['altitude'] == 2500
    
    def test_type_condition_places_altitude_strategy(self):
        """Test TypeConditionPlacesAltitudeStrategy amb filtre manual"""
        refugi_data_1 = {'id': '001', 'altitude': 1500, 'type': 'Cabane', 'condition': 'Bon estat', 'places': 10}
        refugi_data_2 = {'id': '002', 'altitude': 2500, 'type': 'Cabane', 'condition': 'Bon estat', 'places': 10}
        
        mock_db = MagicMock()
        mock_doc1 = MagicMock()
        mock_doc1.to_dict.return_value = refugi_data_1
        mock_doc1.id = '001'
        mock_doc2 = MagicMock()
        mock_doc2.to_dict.return_value = refugi_data_2
        mock_doc2.id = '002'
        
        mock_query = MagicMock()
        mock_query.stream.return_value = [mock_doc1, mock_doc2]
        mock_query.where.return_value = mock_query
        
        mock_collection = MagicMock()
        mock_collection.where.return_value = mock_query
        mock_db.collection.return_value = mock_collection
        
        filters = RefugiSearchFilters()
        filters.type = ["Cabane"]
        filters.condition = ["Bon estat"]
        filters.places_min = 5
        filters.altitude_min = 2000
        
        strategy = TypeConditionPlacesAltitudeStrategy()
        results = strategy.execute_query(mock_db, 'test_collection', filters)
        
        # Només el segon refugi passa el filtre d'altitude
        assert len(results) == 1
        assert results[0]['id'] == '002'
    
    def test_type_altitude_strategy(self):
        """Test TypeAltitudeStrategy"""
        refugi_data = {'id': '001', 'altitude': 2200, 'type': 'Cabane'}
        mock_db = self.setup_mock_db(refugi_data)
        
        filters = RefugiSearchFilters()
        filters.type = ["Cabane"]
        filters.altitude_min = 2000
        
        strategy = TypeAltitudeStrategy()
        results = strategy.execute_query(mock_db, 'test_collection', filters)
        
        assert len(results) == 1
        assert results[0]['altitude'] == 2200
    
    def test_condition_places_strategy(self):
        """Test ConditionPlacesStrategy"""
        refugi_data = {'id': '001', 'condition': 'Bon estat', 'places': 10}
        mock_db = self.setup_mock_db(refugi_data)
        
        filters = RefugiSearchFilters()
        filters.condition = ["Bon estat"]
        filters.places_min = 5
        
        strategy = ConditionPlacesStrategy()
        results = strategy.execute_query(mock_db, 'test_collection', filters)
        
        assert len(results) == 1
        assert results[0]['places'] == 10
    
    def test_condition_altitude_strategy(self):
        """Test ConditionAltitudeStrategy"""
        refugi_data = {'id': '001', 'condition': 'Bon estat', 'altitude': 2500}
        mock_db = self.setup_mock_db(refugi_data)
        
        filters = RefugiSearchFilters()
        filters.condition = ["Bon estat"]
        filters.altitude_min = 2000
        
        strategy = ConditionAltitudeStrategy()
        results = strategy.execute_query(mock_db, 'test_collection', filters)
        
        assert len(results) == 1
        assert results[0]['altitude'] == 2500
    
    def test_condition_places_altitude_strategy(self):
        """Test ConditionPlacesAltitudeStrategy amb filtre manual"""
        refugi_data_1 = {'id': '001', 'altitude': 1500, 'condition': 'Bon estat', 'places': 10}
        refugi_data_2 = {'id': '002', 'altitude': 2500, 'condition': 'Bon estat', 'places': 10}
        
        mock_db = MagicMock()
        mock_doc1 = MagicMock()
        mock_doc1.to_dict.return_value = refugi_data_1
        mock_doc1.id = '001'
        mock_doc2 = MagicMock()
        mock_doc2.to_dict.return_value = refugi_data_2
        mock_doc2.id = '002'
        
        mock_query = MagicMock()
        mock_query.stream.return_value = [mock_doc1, mock_doc2]
        mock_query.where.return_value = mock_query
        
        mock_collection = MagicMock()
        mock_collection.where.return_value = mock_query
        mock_db.collection.return_value = mock_collection
        
        filters = RefugiSearchFilters()
        filters.condition = ["Bon estat"]
        filters.places_min = 5
        filters.altitude_min = 2000
        
        strategy = ConditionPlacesAltitudeStrategy()
        results = strategy.execute_query(mock_db, 'test_collection', filters)
        
        # Només el segon refugi passa el filtre d'altitude
        assert len(results) == 1
        assert results[0]['id'] == '002'
    
    def test_type_only_strategy(self):
        """Test TypeOnlyStrategy"""
        refugi_data = {'id': '001', 'type': 'Cabane'}
        mock_db = self.setup_mock_db(refugi_data)
        
        filters = RefugiSearchFilters()
        filters.type = ["Cabane"]
        
        strategy = TypeOnlyStrategy()
        results = strategy.execute_query(mock_db, 'test_collection', filters)
        
        assert len(results) == 1
        assert results[0]['type'] == 'Cabane'
    
    def test_condition_only_strategy(self):
        """Test ConditionOnlyStrategy"""
        refugi_data = {'id': '001', 'condition': 'Bon estat'}
        mock_db = self.setup_mock_db(refugi_data)
        
        filters = RefugiSearchFilters()
        filters.condition = ["Bon estat"]
        
        strategy = ConditionOnlyStrategy()
        results = strategy.execute_query(mock_db, 'test_collection', filters)
        
        assert len(results) == 1
        assert results[0]['condition'] == 'Bon estat'
    
    def test_places_only_strategy(self):
        """Test PlacesOnlyStrategy"""
        refugi_data = {'id': '001', 'places': 10}
        mock_db = self.setup_mock_db(refugi_data)
        
        filters = RefugiSearchFilters()
        filters.places_min = 5
        filters.places_max = 15
        
        strategy = PlacesOnlyStrategy()
        results = strategy.execute_query(mock_db, 'test_collection', filters)
        
        assert len(results) == 1
        assert results[0]['places'] == 10
    
    def test_altitude_only_strategy(self):
        """Test AltitudeOnlyStrategy"""
        refugi_data = {'id': '001', 'altitude': 2500}
        mock_db = self.setup_mock_db(refugi_data)
        
        filters = RefugiSearchFilters()
        filters.altitude_min = 2000
        filters.altitude_max = 3000
        
        strategy = AltitudeOnlyStrategy()
        results = strategy.execute_query(mock_db, 'test_collection', filters)
        
        assert len(results) == 1
        assert results[0]['altitude'] == 2500
    
    def test_type_places_altitude_strategy_with_manual_filter(self):
        """Test TypePlacesAltitudeStrategy amb filtre manual d'altitude"""
        refugi_data_1 = {'id': '001', 'altitude': 1500, 'type': 'Cabane', 'places': 10}
        refugi_data_2 = {'id': '002', 'altitude': 2500, 'type': 'Cabane', 'places': 10}
        
        mock_db = MagicMock()
        mock_doc1 = MagicMock()
        mock_doc1.to_dict.return_value = refugi_data_1
        mock_doc1.id = '001'
        mock_doc2 = MagicMock()
        mock_doc2.to_dict.return_value = refugi_data_2
        mock_doc2.id = '002'
        
        mock_query = MagicMock()
        mock_query.stream.return_value = [mock_doc1, mock_doc2]
        mock_query.where.return_value = mock_query
        
        mock_collection = MagicMock()
        mock_collection.where.return_value = mock_query
        mock_db.collection.return_value = mock_collection
        
        filters = RefugiSearchFilters()
        filters.type = ["Cabane"]
        filters.places_min = 5
        filters.altitude_min = 2000
        
        strategy = TypePlacesAltitudeStrategy()
        results = strategy.execute_query(mock_db, 'test_collection', filters)
        
        # Només el segon refugi ha de passar el filtre d'altitude
        assert len(results) == 1
        assert results[0]['id'] == '002'
        assert results[0]['altitude'] == 2500
    
    def test_type_places_altitude_strategy_no_altitude_filter(self):
        """Test TypePlacesAltitudeStrategy sense filtre d'altitude"""
        refugi_data = {'id': '001', 'altitude': 1500, 'type': 'Cabane', 'places': 10}
        mock_db = self.setup_mock_db(refugi_data)
        
        filters = RefugiSearchFilters()
        filters.type = ["Cabane"]
        filters.places_min = 5
        # Sense altitude_min ni altitude_max
        
        strategy = TypePlacesAltitudeStrategy()
        results = strategy.execute_query(mock_db, 'test_collection', filters)
        
        # Ha de retornar sense filtrar per altitude
        assert len(results) == 1
        assert results[0]['id'] == '001'
    
    def test_places_altitude_strategy_filters_both(self):
        """Test PlacesAltitudeStrategy filtra altitude manualment"""
        refugi_data_1 = {'id': '001', 'altitude': 1500, 'places': 10}
        refugi_data_2 = {'id': '002', 'altitude': 2500, 'places': 10}
        refugi_data_3 = {'id': '003', 'altitude': 2200, 'places': 10}
        
        mock_db = MagicMock()
        mock_docs = []
        for data in [refugi_data_1, refugi_data_2, refugi_data_3]:
            mock_doc = MagicMock()
            mock_doc.to_dict.return_value = data
            mock_doc.id = data['id']
            mock_docs.append(mock_doc)
        
        mock_query = MagicMock()
        mock_query.stream.return_value = mock_docs
        mock_query.where.return_value = mock_query
        
        mock_collection = MagicMock()
        mock_collection.where.return_value = mock_query
        mock_db.collection.return_value = mock_collection
        
        filters = RefugiSearchFilters()
        filters.places_min = 5
        filters.altitude_min = 2000
        filters.altitude_max = 2400
        
        strategy = PlacesAltitudeStrategy()
        results = strategy.execute_query(mock_db, 'test_collection', filters)
        
        # Només el tercer refugi passa els filtres
        assert len(results) == 1
        assert results[0]['id'] == '003'


# ==================== TESTS PER RefugiLliureDAO ====================

class TestRefugiLliureDAOWithStrategies:
    """Tests per al DAO amb les noves estratègies"""
    
    @patch('api.daos.refugi_lliure_dao.firestore_service')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    def test_search_by_name(self, mock_cache, mock_firestore):
        """Test cerca per nom"""
        refugi_data = {
            'id': '001',
            'name': 'Cabane de Bastan',
            'type': 'Cabane',
            'altitude': 2000,
            'places': 10,
            'coord': {'long': 1.5, 'lat': 42.5},
            'info_comp': {}
        }
        
        mock_cache.get_or_fetch_list.return_value = [refugi_data]
        mock_cache.generate_key.return_value = 'test_cache_key'
        mock_cache.get_timeout.return_value = 300
        
        dao = RefugiLliureDAO()
        filters = RefugiSearchFilters()
        filters.name = "Cabane de Bastan"
        
        results = dao.search_refugis(filters)
        
        assert results['has_filters'] == True
        assert len(results['results']) == 1
        assert results['results'][0].name == "Cabane de Bastan"
    
    @patch('api.daos.refugi_lliure_dao.firestore_service')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    def test_search_with_type_and_places(self, mock_cache, mock_firestore):
        """Test cerca amb type i places"""
        refugi_data = {
            'id': '001',
            'name': 'Test Refugi',
            'type': 'Cabane',
            'altitude': 2000,
            'places': 10,
            'coord': {'long': 1.5, 'lat': 42.5},
            'info_comp': {}
        }
        
        mock_cache.get_or_fetch_list.return_value = [refugi_data]
        mock_cache.generate_key.return_value = 'test_cache_key'
        mock_cache.get_timeout.return_value = 300
        
        dao = RefugiLliureDAO()
        filters = RefugiSearchFilters()
        filters.type = ["Cabane"]
        filters.places_min = 5
        
        results = dao.search_refugis(filters)
        
        assert results['has_filters'] == True
        assert len(results['results']) == 1
    
    def test_has_active_filters_with_name(self):
        """Test _has_active_filters amb name"""
        dao = RefugiLliureDAO()
        filters = RefugiSearchFilters()
        filters.name = "Test"
        
        assert dao._has_active_filters(filters) == True
    
    def test_has_active_filters_with_type(self):
        """Test _has_active_filters amb type"""
        dao = RefugiLliureDAO()
        filters = RefugiSearchFilters()
        filters.type = ["Cabane"]
        
        assert dao._has_active_filters(filters) == True
    
    def test_has_active_filters_with_condition(self):
        """Test _has_active_filters amb condition"""
        dao = RefugiLliureDAO()
        filters = RefugiSearchFilters()
        filters.condition = ["Bon estat"]
        
        assert dao._has_active_filters(filters) == True
    
    def test_has_active_filters_with_places(self):
        """Test _has_active_filters amb places"""
        dao = RefugiLliureDAO()
        filters = RefugiSearchFilters()
        filters.places_min = 5
        
        assert dao._has_active_filters(filters) == True
    
    def test_has_active_filters_with_altitude(self):
        """Test _has_active_filters amb altitude"""
        dao = RefugiLliureDAO()
        filters = RefugiSearchFilters()
        filters.altitude_min = 2000
        
        assert dao._has_active_filters(filters) == True
    
    def test_has_active_filters_no_filters(self):
        """Test _has_active_filters sense filtres"""
        dao = RefugiLliureDAO()
        filters = RefugiSearchFilters()
        
        assert dao._has_active_filters(filters) == False
    
    @patch('api.daos.refugi_lliure_dao.firestore_service')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    def test_search_refugis_no_filters_returns_coordinates(self, mock_cache, mock_firestore):
        """Test cerca sense filtres retorna coordenades"""
        mock_cache.get.return_value = None
        
        coords_data = {
            'refugis_coordinates': [
                {
                    'id': 'ref_001',
                    'name': 'Refugi A',
                    'coord': {'long': 1.5, 'lat': 42.5},
                    'geohash': 'abc'
                }
            ]
        }
        
        mock_db = MagicMock()
        mock_firestore.get_db.return_value = mock_db
        
        mock_doc_snapshot = MagicMock()
        mock_doc_snapshot.exists = True
        mock_doc_snapshot.to_dict.return_value = coords_data
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc_snapshot
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = RefugiLliureDAO()
        filters = RefugiSearchFilters()
        results = dao.search_refugis(filters)
        
        assert results['has_filters'] == False
        assert isinstance(results['results'], list)
    
    @patch('api.daos.refugi_lliure_dao.firestore_service')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    def test_search_from_cache(self, mock_cache, mock_firestore):
        """Test cerca des de cache"""
        cached_data = {
            'has_filters': True,
            'results': [{'id': '001', 'name': 'Test', 'coord': {'long': 1.5, 'lat': 42.5}, 'info_comp': {}}]
        }
        mock_cache.get.return_value = cached_data
        
        dao = RefugiLliureDAO()
        filters = RefugiSearchFilters()
        filters.type = ["Cabane"]
        
        results = dao.search_refugis(filters)
        
        assert results['has_filters'] == True
        # No hauria de cridar Firestore
        mock_firestore.get_db.assert_not_called()
    
    @patch('api.daos.refugi_lliure_dao.firestore_service')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    def test_search_by_name_error_handling(self, mock_cache, mock_firestore):
        """Test gestió d'errors en cerca per nom"""
        mock_cache.get.return_value = None
        
        mock_db = MagicMock()
        mock_firestore.get_db.return_value = mock_db
        
        mock_query = MagicMock()
        mock_query.stream.side_effect = Exception("Database error")
        
        mock_collection = MagicMock()
        mock_collection.where.return_value = mock_query
        mock_db.collection.return_value = mock_collection
        
        dao = RefugiLliureDAO()
        
        # _search_by_name gestiona errors internament i retorna llista buida
        results = dao._search_by_name(mock_db, "Test")
        assert results == []
    
    @patch('api.daos.refugi_lliure_dao.firestore_service')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    def test_build_optimized_query_uses_strategy(self, mock_cache, mock_firestore):
        """Test que _build_optimized_query usa l'estratègia correcta"""
        mock_db = MagicMock()
        
        refugi_data = {'id': '001', 'name': 'Test', 'type': 'Cabane', 'places': 10}
        mock_doc = MagicMock()
        mock_doc.to_dict.return_value = refugi_data
        mock_doc.id = '001'
        
        mock_query = MagicMock()
        mock_query.stream.return_value = [mock_doc]
        mock_query.where.return_value = mock_query
        
        mock_collection = MagicMock()
        mock_collection.where.return_value = mock_query
        mock_db.collection.return_value = mock_collection
        
        dao = RefugiLliureDAO()
        filters = RefugiSearchFilters()
        filters.type = ["Cabane"]
        filters.places_min = 5
        
        results = dao._build_optimized_query(mock_db, filters)
        
        assert len(results) == 1
        assert results[0]['id'] == '001'


# ==================== TESTS DE CASOS LÍMIT I EXCEPCIONS ====================

class TestEdgeCasesAndExceptions:
    """Tests per casos límit i excepcions"""
    
    def test_filters_with_empty_strings(self):
        """Test filtres amb strings buits"""
        filters = RefugiSearchFilters()
        filters.type = ["  "]  # Llista amb string amb espais
        filters.condition = []  # Llista buida
        
        dao = RefugiLliureDAO()
        assert dao._has_active_filters(filters) == False
    
    def test_filters_with_none_values(self):
        """Test filtres inicialitzats amb valors per defecte"""
        filters = RefugiSearchFilters()
        
        # __post_init__ hauria de normalitzar els valors per defecte
        assert filters.type == []
        assert filters.condition == []
        assert filters.name == ""
        assert filters.places_min is None
        assert filters.altitude_min is None
    
    def test_altitude_filter_with_min_greater_than_max(self):
        """Test filtre d'altitude amb min > max (configuració invàlida)"""
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_query.stream.return_value = []
        mock_query.where.return_value = mock_query
        
        mock_collection = MagicMock()
        mock_collection.where.return_value = mock_query
        mock_db.collection.return_value = mock_collection
        
        filters = RefugiSearchFilters()
        filters.altitude_min = 3000
        filters.altitude_max = 2000  # Configuració invàlida
        
        strategy = AltitudeOnlyStrategy()
        results = strategy.execute_query(mock_db, 'test_collection', filters)
        
        # Firestore retornarà resultats buits per aquesta query invàlida
        assert len(results) == 0
    
    def test_places_filter_only_max(self):
        """Test filtre de places només amb max (sense min)"""
        refugi_data = {'id': '001', 'places': 8}
        
        mock_db = MagicMock()
        mock_doc = MagicMock()
        mock_doc.to_dict.return_value = refugi_data
        
        mock_query = MagicMock()
        mock_query.stream.return_value = [mock_doc]
        mock_query.where.return_value = mock_query
        
        mock_collection = MagicMock()
        mock_collection.where.return_value = mock_query
        mock_db.collection.return_value = mock_collection
        
        filters = RefugiSearchFilters()
        filters.places_max = 10  # Només max, sense min
        
        strategy = PlacesOnlyStrategy()
        results = strategy.execute_query(mock_db, 'test_collection', filters)
        
        assert len(results) == 1
        assert results[0]['places'] == 8
    
    def test_altitude_filter_only_max(self):
        """Test filtre d'altitude només amb max (sense min)"""
        refugi_data = {'id': '001', 'altitude': 1800}
        
        mock_db = MagicMock()
        mock_doc = MagicMock()
        mock_doc.to_dict.return_value = refugi_data
        
        mock_query = MagicMock()
        mock_query.stream.return_value = [mock_doc]
        mock_query.where.return_value = mock_query
        
        mock_collection = MagicMock()
        mock_collection.where.return_value = mock_query
        mock_db.collection.return_value = mock_collection
        
        filters = RefugiSearchFilters()
        filters.altitude_max = 2000  # Només max, sense min
        
        strategy = AltitudeOnlyStrategy()
        results = strategy.execute_query(mock_db, 'test_collection', filters)
        
        assert len(results) == 1
        assert results[0]['altitude'] == 1800
    
    def test_type_condition_places_strategy_only_max(self):
        """Test TypeConditionPlacesStrategy només amb places_max"""
        refugi_data = {'id': '001', 'type': 'Cabane', 'condition': 'Bon estat', 'places': 8}
        
        mock_db = MagicMock()
        mock_doc = MagicMock()
        mock_doc.to_dict.return_value = refugi_data
        
        mock_query = MagicMock()
        mock_query.stream.return_value = [mock_doc]
        mock_query.where.return_value = mock_query
        
        mock_collection = MagicMock()
        mock_collection.where.return_value = mock_query
        mock_db.collection.return_value = mock_collection
        
        filters = RefugiSearchFilters()
        filters.type = ["Cabane"]
        filters.condition = ["Bon estat"]
        filters.places_max = 10  # Només max
        
        strategy = TypeConditionPlacesStrategy()
        results = strategy.execute_query(mock_db, 'test_collection', filters)
        
        assert len(results) == 1
    
    def test_type_condition_altitude_strategy_only_max(self):
        """Test TypeConditionAltitudeStrategy només amb altitude_max"""
        refugi_data = {'id': '001', 'type': 'Cabane', 'condition': 'Bon estat', 'altitude': 1800}
        
        mock_db = MagicMock()
        mock_doc = MagicMock()
        mock_doc.to_dict.return_value = refugi_data
        
        mock_query = MagicMock()
        mock_query.stream.return_value = [mock_doc]
        mock_query.where.return_value = mock_query
        
        mock_collection = MagicMock()
        mock_collection.where.return_value = mock_query
        mock_db.collection.return_value = mock_collection
        
        filters = RefugiSearchFilters()
        filters.type = ["Cabane"]
        filters.condition = ["Bon estat"]
        filters.altitude_max = 2000  # Només max
        
        strategy = TypeConditionAltitudeStrategy()
        results = strategy.execute_query(mock_db, 'test_collection', filters)
        
        assert len(results) == 1
    
    def test_type_places_altitude_strategy_max_only_in_manual_filter(self):
        """Test TypePlacesAltitudeStrategy amb altitude_max en filtre manual"""
        refugi_data_1 = {'id': '001', 'altitude': 1500, 'type': 'Cabane', 'places': 10}
        refugi_data_2 = {'id': '002', 'altitude': 2500, 'type': 'Cabane', 'places': 10}
        
        mock_db = MagicMock()
        mock_docs = []
        for data in [refugi_data_1, refugi_data_2]:
            mock_doc = MagicMock()
            mock_doc.to_dict.return_value = data
            mock_doc.id = data['id']
            mock_docs.append(mock_doc)
        
        mock_query = MagicMock()
        mock_query.stream.return_value = mock_docs
        mock_query.where.return_value = mock_query
        
        mock_collection = MagicMock()
        mock_collection.where.return_value = mock_query
        mock_db.collection.return_value = mock_collection
        
        filters = RefugiSearchFilters()
        filters.type = ["Cabane"]
        filters.places_min = 5
        filters.altitude_max = 2000  # Només max per al filtre manual
        
        strategy = TypePlacesAltitudeStrategy()
        results = strategy.execute_query(mock_db, 'test_collection', filters)
        
        # Només el primer refugi passa el filtre (altitude <= 2000)
        assert len(results) == 1
        assert results[0]['id'] == '001'
    
    def test_condition_places_altitude_strategy_both_altitude_filters(self):
        """Test ConditionPlacesAltitudeStrategy amb min i max d'altitude"""
        refugi_data_1 = {'id': '001', 'altitude': 1500, 'condition': 'Bon estat', 'places': 10}
        refugi_data_2 = {'id': '002', 'altitude': 2200, 'condition': 'Bon estat', 'places': 10}
        refugi_data_3 = {'id': '003', 'altitude': 2800, 'condition': 'Bon estat', 'places': 10}
        
        mock_db = MagicMock()
        mock_docs = []
        for data in [refugi_data_1, refugi_data_2, refugi_data_3]:
            mock_doc = MagicMock()
            mock_doc.to_dict.return_value = data
            mock_doc.id = data['id']
            mock_docs.append(mock_doc)
        
        mock_query = MagicMock()
        mock_query.stream.return_value = mock_docs
        mock_query.where.return_value = mock_query
        
        mock_collection = MagicMock()
        mock_collection.where.return_value = mock_query
        mock_db.collection.return_value = mock_collection
        
        filters = RefugiSearchFilters()
        filters.condition = ["Bon estat"]
        filters.places_min = 5
        filters.altitude_min = 2000
        filters.altitude_max = 2500
        
        strategy = ConditionPlacesAltitudeStrategy()
        results = strategy.execute_query(mock_db, 'test_collection', filters)
        
        # Només el segon refugi passa els filtres (2000 <= 2200 <= 2500)
        assert len(results) == 1
        assert results[0]['id'] == '002'
    
    def test_manual_altitude_filter_all_filtered_out(self):
        """Test filtre manual d'altitude que elimina tots els resultats"""
        refugi_data_1 = {'id': '001', 'altitude': 1500, 'places': 10}
        refugi_data_2 = {'id': '002', 'altitude': 1800, 'places': 10}
        
        mock_db = MagicMock()
        mock_docs = []
        for data in [refugi_data_1, refugi_data_2]:
            mock_doc = MagicMock()
            mock_doc.to_dict.return_value = data
            mock_doc.id = data['id']
            mock_docs.append(mock_doc)
        
        mock_query = MagicMock()
        mock_query.stream.return_value = mock_docs
        mock_query.where.return_value = mock_query
        
        mock_collection = MagicMock()
        mock_collection.where.return_value = mock_query
        mock_db.collection.return_value = mock_collection
        
        filters = RefugiSearchFilters()
        filters.places_min = 5
        filters.altitude_min = 2000  # Tots els refugis estan per sota
        
        strategy = PlacesAltitudeStrategy()
        results = strategy.execute_query(mock_db, 'test_collection', filters)
        
        assert len(results) == 0
    
    def test_refugi_without_altitude_field(self):
        """Test refugi sense camp altitude (usa default 0)"""
        refugi_data = {'id': '001', 'places': 10}  # Sense altitude
        
        mock_db = MagicMock()
        mock_doc = MagicMock()
        mock_doc.to_dict.return_value = refugi_data
        
        mock_query = MagicMock()
        mock_query.stream.return_value = [mock_doc]
        mock_query.where.return_value = mock_query
        
        mock_collection = MagicMock()
        mock_collection.where.return_value = mock_query
        mock_db.collection.return_value = mock_collection
        
        filters = RefugiSearchFilters()
        filters.places_min = 5
        filters.altitude_min = 2000
        
        strategy = PlacesAltitudeStrategy()
        results = strategy.execute_query(mock_db, 'test_collection', filters)
        
        # El refugi s'ha de filtrar perquè altitude=0 < 2000
        assert len(results) == 0
    
    @patch('api.daos.refugi_lliure_dao.firestore_service')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    def test_search_exception_propagates(self, mock_cache, mock_firestore):
        """Test que les excepcions es propaguen correctament"""
        mock_cache.get.return_value = None
        # Mock get_or_fetch_list to raise the exception
        mock_cache.get_or_fetch_list.side_effect = Exception("Firestore connection failed")
        
        dao = RefugiLliureDAO()
        filters = RefugiSearchFilters()
        filters.type = ["Cabane"]
        
        with pytest.raises(Exception, match="Firestore connection failed"):
            dao.search_refugis(filters)

