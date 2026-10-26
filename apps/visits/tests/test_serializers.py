"""
Serializers de `apps/visits/serializers.py` (chunk 4, §2.11, §5.2).

Contracte:
- `CreateRefugeVisitSerializer` i `UpdateRefugeVisitSerializer` (mateixos noms que els de Firestore): un sol camp
  `num_visitors`, enter obligatori, `min_value=1` i **`max_value`** (§2.11: «afegir `max_value` al serializer per
  evitar valors absurds»; el valor exacte es la pregunta 1 de l'informe: s'accepta fins a 50 i es rebutja 100000).
- `RefugeVisitListSerializer` (sortida): rep un objecte amb els atributs `date` (`datetime.date`), `refuge_id`
  (`UUID`), `total_visitors`, `is_visitor`, `num_visitors` (els del `VisitSummary` que retornen selectors/services) i
  emet exactament `{date: 'YYYY-MM-DD', refuge_id: '<uuid>', total_visitors, is_visitor, num_visitors}`. **No** calcula
  res del context i **mai** exposa participants (cap camp `visitors` ni `uid`).
"""
import uuid
from datetime import date
from types import SimpleNamespace

import pytest

from apps.visits.tests.helpers import VISIT_KEYS

pytestmark = [pytest.mark.serializers, pytest.mark.unit]


def _ser():
    import apps.visits.serializers as s
    return s


@pytest.mark.parametrize('name', ['CreateRefugeVisitSerializer', 'UpdateRefugeVisitSerializer'])
class TestInput:
    def test_valid(self, name):
        s = getattr(_ser(), name)(data={'num_visitors': 2})
        assert s.is_valid(), s.errors
        assert s.validated_data == {'num_visitors': 2}

    @pytest.mark.parametrize('value', [1, 50])
    def test_limits_acceptats(self, name, value):
        assert getattr(_ser(), name)(data={'num_visitors': value}).is_valid()

    @pytest.mark.parametrize('data', [{}, {'num_visitors': None}, {'num_visitors': 0}, {'num_visitors': -3},
                                      {'num_visitors': 'molts'}, {'num_visitors': 1.5}, {'num_visitors': ''}])
    def test_invalid(self, name, data):
        s = getattr(_ser(), name)(data=data)
        assert not s.is_valid() and 'num_visitors' in s.errors

    @pytest.mark.parametrize('value', [100000, 2 ** 31 - 1, 2 ** 31])
    def test_te_max_value_contra_valors_absurds(self, name, value):
        s = getattr(_ser(), name)(data={'num_visitors': value})
        assert not s.is_valid() and 'num_visitors' in s.errors

    def test_camps_desconeguts_s_ignoren(self, name):
        s = getattr(_ser(), name)(data={'num_visitors': 2, 'uid': 'altre', 'total_visitors': 99})
        assert s.is_valid() and s.validated_data == {'num_visitors': 2}


def _obj(**kw):
    base = dict(date=date(2030, 7, 18), refuge_id=uuid.UUID('0190aaaa-0000-7000-8000-000000000001'),
                total_visitors=12, is_visitor=True, num_visitors=2)
    base.update(kw)
    return SimpleNamespace(**base)


class TestOutput:
    def test_claus_i_tipus(self):
        data = _ser().RefugeVisitListSerializer(_obj()).data
        assert set(data) == VISIT_KEYS
        assert data['date'] == '2030-07-18' and data['refuge_id'] == '0190aaaa-0000-7000-8000-000000000001'
        assert data['total_visitors'] == 12 and data['is_visitor'] is True and data['num_visitors'] == 2

    def test_no_visitant(self):
        data = _ser().RefugeVisitListSerializer(_obj(is_visitor=False, num_visitors=0, total_visitors=0)).data
        assert data['is_visitor'] is False and data['num_visitors'] == 0 and data['total_visitors'] == 0

    def test_many(self):
        data = _ser().RefugeVisitListSerializer([_obj(), _obj(date=date(2030, 7, 19))], many=True).data
        assert [d['date'] for d in data] == ['2030-07-18', '2030-07-19']

    def test_no_exposa_participants(self):
        obj = _obj()
        obj.visitors = [SimpleNamespace(uid='secret-uid', num_visitors=9)]
        data = _ser().RefugeVisitListSerializer(obj).data
        assert 'visitors' not in data and 'secret-uid' not in str(data)

    def test_no_depen_del_context_d_usuari(self):
        """`is_visitor`/`num_visitors` ja venen calculats de la consulta (respecte a l'usuari del token)."""
        data = _ser().RefugeVisitListSerializer(_obj(is_visitor=True, num_visitors=4),
                                                context={'user_uid': 'un-altre'}).data
        assert data['is_visitor'] is True and data['num_visitors'] == 4
