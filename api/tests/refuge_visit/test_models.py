"""
Tests per al model de visita a refugi
"""
import pytest
from api.models.refuge_visit import RefugeVisit, UserVisit

@pytest.mark.models
class TestRefugeVisitModels:
    """Tests per al model RefugeVisit"""
    
    def test_user_visit_creation(self):
        """Test creació d'UserVisit"""
        user_visit = UserVisit(uid="user_1", num_visitors=3)
        assert user_visit.uid == "user_1"
        assert user_visit.num_visitors == 3

    def test_refuge_visit_creation(self):
        """Test creació de RefugeVisit"""
        visit = RefugeVisit(
            date="2024-01-01",
            refuge_id="ref_1",
            visitors=[UserVisit(uid="u1", num_visitors=2)],
            total_visitors=2
        )
        assert visit.date == "2024-01-01"
        assert len(visit.visitors) == 1
        assert visit.total_visitors == 2

    def test_refuge_visit_validation(self):
        """Test validacions de RefugeVisit"""
        with pytest.raises(ValueError, match="Refuge ID és requerit"):
            RefugeVisit(date="2024-01-01", refuge_id="")
        
        with pytest.raises(ValueError, match="Data d'inici és requerida"):
            RefugeVisit(date="", refuge_id="ref_1")

    def test_refuge_visit_to_dict(self):
        """Test to_dict de RefugeVisit"""
        visitors = [UserVisit(uid="u1", num_visitors=2)]
        visit = RefugeVisit(date="2024-01-01", refuge_id="ref_1", visitors=visitors, total_visitors=2)
        data = visit.to_dict()
        assert data['date'] == "2024-01-01"
        assert data['visitors'] == visitors

    def test_refuge_visit_from_dict(self):
        """Test from_dict de RefugeVisit"""
        data = {
            'date': '2024-01-01',
            'refuge_id': 'ref_1',
            'visitors': [],
            'total_visitors': 0
        }
        visit = RefugeVisit.from_dict(data)
        assert visit.date == '2024-01-01'
        assert visit.refuge_id == 'ref_1'
