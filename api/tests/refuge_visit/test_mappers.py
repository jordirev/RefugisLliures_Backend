"""
Tests per al mapper de visites a refugi
"""
import pytest
from api.mappers.refuge_visit_mapper import RefugeVisitMapper
from api.models.refuge_visit import RefugeVisit, UserVisit

@pytest.mark.mappers
class TestRefugeVisitMapper:
    """Tests per al mapper RefugeVisitMapper"""
    
    def test_firebase_to_model(self):
        """Test conversió de Firebase a model"""
        firebase_data = {
            'date': '2024-01-01',
            'refuge_id': 'ref_1',
            'visitors': [
                {'uid': 'u1', 'num_visitors': 2},
                {'uid': 'u2', 'num_visitors': 1}
            ],
            'total_visitors': 3
        }
        visit = RefugeVisitMapper.firebase_to_model(firebase_data)
        assert isinstance(visit, RefugeVisit)
        assert visit.date == '2024-01-01'
        assert len(visit.visitors) == 2
        assert visit.visitors[0].uid == 'u1'
        assert visit.total_visitors == 3

    def test_model_to_firebase(self):
        """Test conversió de model a Firebase"""
        visit = RefugeVisit(
            date='2024-01-01',
            refuge_id='ref_1',
            visitors=[UserVisit(uid='u1', num_visitors=2)],
            total_visitors=2
        )
        data = RefugeVisitMapper.model_to_firebase(visit)
        assert data['date'] == '2024-01-01'
        assert len(data['visitors']) == 1
        assert data['visitors'][0]['uid'] == 'u1'
        assert data['total_visitors'] == 2

    def test_validate_firebase_data(self):
        """Test validació de dades de Firebase"""
        valid_data = {'date': '2024-01-01', 'refuge_id': 'ref_1'}
        is_valid, error = RefugeVisitMapper.validate_firebase_data(valid_data)
        assert is_valid is True
        assert error is None
        
        invalid_data = {'date': '2024-01-01'}
        is_valid, error = RefugeVisitMapper.validate_firebase_data(invalid_data)
        assert is_valid is False
        assert "refuge_id" in error
