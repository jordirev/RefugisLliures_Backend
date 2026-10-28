"""
Tests d'utilitats d'edat (els avisos de moderació són a `apps/moderation/tests/`).

La resta (creació, edat, moderació, avatar, llistes) és a PostgreSQL: `apps/accounts/tests/` (chunk 3).
"""
from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from api.utils.age_utils import compute_age, is_old_enough


@pytest.mark.unit
class TestAgeUtils:
    def test_compute_age(self):
        assert compute_age('2000-05-17', today=date(2016, 5, 16)) == 15
        assert compute_age('2000-05-17', today=date(2016, 5, 17)) == 16
        assert is_old_enough(date(2000, 1, 1), 16, today=date(2016, 1, 1))
        assert not is_old_enough(date(2000, 1, 2), 16, today=date(2016, 1, 1))


def authed(request, uid='u1'):
    force_authenticate(request, user=MagicMock(is_authenticated=True, uid=uid, claims={}))
    request.user_uid = uid
    return request


