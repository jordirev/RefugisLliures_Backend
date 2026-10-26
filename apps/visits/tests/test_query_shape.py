"""Forma del SQL de les lectures de `visits` (revisió SQL del chunk 4): el total mai s'enllaça amb un JOIN a la vista."""
import uuid

from apps.visits import selectors


def test_totals_are_correlated_subqueries_not_joins():
    """
    Un `LEFT JOIN` amb `refuge_visit_totals` (GROUP BY) obliga Postgres a agregar tots els participants (5 s amb 1 M de
    files); la subconsulta correlacionada hi empeny `visit_id` i usa la PK. Els dos camins han d'usar-la.
    """
    refuge_query = str(selectors._annotated_visits('u1').filter(refuge_id=uuid.uuid4()).values_list(
        *selectors._FIELDS).query)
    assert 'JOIN "activity"."refuge_visit_totals"' not in refuge_query
    assert 'FROM "activity"."refuge_visit_totals"' in refuge_query
