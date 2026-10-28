"""
Una proposta aprovada amb `condition` **reinicia** la mitjana del refugi (§2.9, decisió del PO): `c = valor`, `n = 1`,
`condition_reset_at = now()`; ja no és «un vot més» com feia `ConditionService.calculate_condition_average`. La interacció
amb el *trigger* d'experiències (regla del «vot antic», D2): una experiència comptada abans del reinici
(`condition_counted_at < condition_reset_at`) que després canvia el valor compta com a vot nou.

Nota: dins un test tot passa a la mateixa transacció (`now()` constant), així que els instants antics es fixen a mà
(`set_counted_at`), com a `apps/experiences/tests/test_condition_trigger.py`.
"""
import pytest

from apps.core.rls import rls_context
from apps.experiences import services as exp_services
from apps.experiences.tests.helpers import make_experience, refuge_state, set_counted_at, utc
from apps.proposals.tests.helpers import make_proposal, make_refuge

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.integration, pytest.mark.real_permissions]


def approve(services, pid):
    with rls_context(uid='adm', is_admin=True):
        return services.approve_proposal(proposal_id=pid, reviewer_uid='adm')


def vote_update(uid, experience, value):
    with rls_context(uid=uid):
        exp_services.update_experience(experience_id=experience, actor_uid=uid, condition=value)


def vote_new(uid, refuge, value):
    with rls_context(uid=uid):
        return exp_services.create_experience(refuge_id=refuge.pk, creator_uid=uid, comment='x', condition=value)


@pytest.fixture
def voted(world):
    """Refugi amb dues experiències antigues (valors 3 i 1 -> mitjana 2, n = 2)."""
    r = world[0]
    e1, e2 = make_experience(r, 'u1', condition=3), make_experience(r, 'u2', condition=1)
    assert refuge_state(r)[:2] == (2.0, 2)
    for e in (e1, e2):
        set_counted_at(e, utc(2025, 1, 1))
    return r, e1, e2


def test_la_proposta_no_es_un_vot_mes_reinicia(services, voted):
    r, *_ = voted
    approve(services, make_proposal('update', refuge=r, payload={'condition': 0}))
    c, n, reset_at = refuge_state(r)
    assert (c, n) == (0.0, 1) and reset_at is not None


def test_les_experiencies_antigues_compten_com_a_vot_nou_en_canviar_de_valor_despres_del_reinici(services, voted):
    r, e1, e2 = voted
    approve(services, make_proposal('update', refuge=r, payload={'condition': 2}))
    assert refuge_state(r)[:2] == (2.0, 1)
    # Nota: un PATCH que no canvia el valor no fa res (§2.9); `e1` valia 3, per això passa a 2.
    vote_update('u1', e1, 2)                                  # vot nou: (2·1 + 2) / 2
    assert refuge_state(r)[:2] == (2.0, 2)
    vote_update('u2', e2, 0)                                  # vot nou: (2·2 + 0) / 3
    assert refuge_state(r)[0] == pytest.approx(4 / 3) and refuge_state(r)[1] == 3
    vote_update('u1', e1, 1)                                  # ja recomptada: només ajusta (2 -> 1) / 3
    assert refuge_state(r)[0] == pytest.approx(4 / 3 - 1 / 3) and refuge_state(r)[1] == 3


def test_una_experiencia_nova_despres_del_reinici_fa_la_mitjana_amb_el_valor_de_la_proposta(services, voted):
    r, *_ = voted
    approve(services, make_proposal('update', refuge=r, payload={'condition': 3}))
    vote_new('u3', r, 0)
    assert refuge_state(r)[:2] == (1.5, 2)


def test_create_amb_condition_i_despres_experiencies(services, world):
    pid = make_proposal(payload={'name': 'Nou', 'coord': {'lat': 42.1, 'long': 2.1}, 'condition': 2})
    approve(services, pid)
    from apps.proposals.tests.helpers import new_refuge_id
    rid = new_refuge_id(pid)
    new = type('R', (), {'pk': rid})
    vote_new('u1', new, 0)
    assert refuge_state(rid)[:2] == (1.0, 2)


def test_un_update_sense_condition_no_reinicia_i_les_experiencies_continuen_igual(services, voted):
    r, e1, _ = voted
    approve(services, make_proposal('update', refuge=r, payload={'places': 7}))
    assert refuge_state(r) == (2.0, 2, None)
    vote_update('u1', e1, 2)                                  # ajust (3 -> 2) / 2
    assert refuge_state(r)[:2] == (1.5, 2)


def test_esborrar_la_proposta_o_l_usuari_no_toca_la_mitjana(services, voted, client):
    r, e1, _ = voted
    approve(services, make_proposal('update', refuge=r, payload={'condition': 3}, creator='u3'))
    from apps.proposals.tests.helpers import sql
    sql("DELETE FROM users.users WHERE uid = 'u3'")
    assert refuge_state(r)[:2] == (3.0, 1)
