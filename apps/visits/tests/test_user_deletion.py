"""
Esborrat d'usuari i visites (chunk 4; §8.4/§8.5; M3).

- El pas «visites» de `apps.accounts.services._firestore_steps` desapareix: ho fa la cascada de la FK
  `refuge_visit_participants.user_uid -> users.users ON DELETE CASCADE`. Despres d'aquest chunk
  `RefugeVisitController.remove_user_from_all_visits` ja no existeix.
- `DELETE /users/{uid}/` deixa els totals correctes: es resta el `num_visitors` de l'usuari (M3: avui es resta 1).
- Els altres passos de Firestore encara no migrats (D21) es mocken aqui.
"""
from unittest.mock import patch

import pytest

from apps.visits.tests.helpers import (
    api_delete, api_get, day, make_refuge, make_user, make_visit, participant_rows, refuge_visits_url, sql, total_of,
    user_claims, visit_rows)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration,
              pytest.mark.real_permissions]

OTHER_STEPS = [
    'api.controllers.experience_controller.ExperienceController.delete_experiences_by_creator',
    'api.controllers.doubt_controller.DoubtController.delete_doubts_by_creator',
    'api.controllers.doubt_controller.DoubtController.delete_answers_by_creator',
    'api.controllers.refuge_proposal_controller.RefugeProposalController.anonymize_proposals_by_creator',
    'api.controllers.renovation_controller.RenovationController.delete_current_renovations_by_creator',
    'api.controllers.renovation_controller.RenovationController.anonymize_renovations_by_creator',
    'api.controllers.renovation_controller.RenovationController.remove_user_from_participations',
    'api.controllers.renovation_controller.RenovationController.remove_user_from_expelled',
]


@pytest.fixture(autouse=True)
def other_firestore_steps():
    patches = []
    for target in OTHER_STEPS:
        try:
            p = patch(target, return_value=(True, None))
            p.start()
        except (AttributeError, ImportError):                  # chunk 7: el controller d'experiències ja no existeix
            continue
        patches.append(p)
    yield patches
    for p in patches:
        p.stop()


def test_el_pas_visites_ja_no_es_a_l_esborrat_provisional():
    from apps.accounts import services
    assert 'visites' not in [name for name, _ in services._firestore_steps('u1')]


def test_el_controller_de_firestore_de_visites_ja_no_existeix():
    with pytest.raises(ImportError):
        from api.controllers import refuge_visit_controller  # noqa: F401


def test_delete_usuari_cascadeja_els_participants_i_deixa_els_totals_correctes(client):
    make_user('u1')
    make_user('u2')
    r = make_refuge()
    v = make_visit(r, day(2), {'u1': 3, 'u2': 2})
    other = make_visit(make_refuge(name='R2', lat=43), day(3), {'u1': 4})
    resp = api_delete(client, '/api/users/u1/', user_claims('u1'))
    assert resp.status_code == 204
    assert participant_rows(v) == {'u2': 2} and participant_rows(other) == {}
    assert total_of(v) == 2                                              # M3: -3 (num_visitors), no -1
    assert total_of(other) == 0
    assert len(visit_rows()) == 2                                        # les visites es conserven


def test_el_total_visible_a_l_api_despres_d_esborrar_un_usuari(client):
    make_user('u1')
    make_user('u2')
    r = make_refuge()
    make_visit(r, day(2), {'u1': 3, 'u2': 2})
    api_delete(client, '/api/users/u1/', user_claims('u1'))
    item = api_get(client, refuge_visits_url(r.pk), user_claims('u2')).json()['result'][0]
    assert (item['total_visitors'], item['is_visitor'], item['num_visitors']) == (2, True, 2)


def test_si_falla_firebase_es_desfa_tambe_la_cascada_de_visites(client, firebase_accounts):
    make_user('u1')
    r = make_refuge()
    v = make_visit(r, day(2), {'u1': 3})
    firebase_accounts.delete_user.side_effect = RuntimeError('firebase caigut')
    assert api_delete(client, '/api/users/u1/', user_claims('u1')).status_code == 500
    assert participant_rows(v) == {'u1': 3}


def test_delete_usuari_no_toca_user_visited_refuges_d_altres(client):
    make_user('u1')
    make_user('u2')
    r = make_refuge()
    make_visit(r, day(2), {'u1': 1, 'u2': 1})
    sql('INSERT INTO users.user_visited_refuges (user_uid, refuge_id) VALUES (%s, %s)', ['u2', r.pk])
    api_delete(client, '/api/users/u1/', user_claims('u1'))
    assert sql('SELECT user_uid FROM users.user_visited_refuges') == [('u2',)]
