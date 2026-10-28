"""
Restriccions de `proposals.refuge_proposals` (§2.18): cada `CHECK` (forma per acció, `refuge_id`, estat de revisió,
claus del payload, `coord`, mida, longituds, enumeracions), les FK `SET NULL` i l'**ordre obligatori** en esborrar un
refugi. Les files s'insereixen amb SQL pla (rol `app` + `system_context()`: els `CHECK` s'apliquen igualment).
"""
import secrets

import pytest
from django.db import IntegrityError

from apps.core.rls import system_context
from apps.proposals.tests.helpers import (
    as_owner, make_proposal, make_refuge, make_user, new_payload, proposal_row, snapshot_of, sql, uuid7_ok)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.models, pytest.mark.integration,
              pytest.mark.real_permissions]


@pytest.fixture
def refuge(world):
    return world[0]


def violates(constraint, **kwargs):
    """Falla si la inserció no viola exactament la restricció `constraint`."""
    with pytest.raises(IntegrityError) as info:
        make_proposal(**kwargs)
    assert getattr(info.value.__cause__.diag, 'constraint_name', None) == constraint, info.value


# =================================== forma per acció ===================================

@pytest.mark.parametrize('kwargs', [
    dict(action='create', snapshot={'a': 1}),                                  # create no porta foto
    dict(action='create', payload=None),
    dict(action='create', payload=[1]),
    dict(action='create', payload={'coord': {'lat': 1, 'long': 1}}),           # sense name
    dict(action='create', payload={'name': 'x'}),                              # sense coord
    dict(action='create', payload={'name': 5, 'coord': {'lat': 1, 'long': 1}}),
    dict(action='create', payload={'name': '   ', 'coord': {'lat': 1, 'long': 1}}),
])
def test_shape_create(world, kwargs):
    violates('refuge_proposals_shape_ck', **kwargs)


def test_shape_update(refuge):
    violates('refuge_proposals_shape_ck', action='update', refuge=refuge, snapshot=None)
    violates('refuge_proposals_shape_ck', action='update', refuge=refuge, payload=None)
    violates('refuge_proposals_shape_ck', action='update', refuge=refuge, payload={})
    violates('refuge_proposals_shape_ck', action='update', refuge=refuge, payload=[{'places': 1}])


def test_shape_delete_no_porta_payload_i_exigeix_foto(refuge):
    violates('refuge_proposals_shape_ck', action='delete', refuge=refuge, payload={'places': 1})
    violates('refuge_proposals_shape_ck', action='delete', refuge=refuge, snapshot=None)


def test_formes_valides(refuge):
    assert make_proposal('create')
    assert make_proposal('update', refuge=refuge, payload={'altitude': None})      # null = «buida'l»
    assert make_proposal('update', refuge=refuge, payload={'info_comp': {}})
    assert make_proposal('delete', refuge=refuge)


# =================================== refuge_id ===================================

def test_refuge_ref_create_pendent_sense_refugi(refuge):
    violates('refuge_proposals_refuge_ref_ck', action='create', refuge=refuge)


@pytest.mark.parametrize('action', ['update', 'delete'])
def test_refuge_ref_update_i_delete_pendents_exigeixen_refugi(refuge, action):
    violates('refuge_proposals_refuge_ref_ck', action=action, refuge=None, snapshot=snapshot_of(refuge))


def test_refuge_ref_valid_quan_ja_no_es_pendent(refuge):
    assert make_proposal('update', refuge=None, snapshot=snapshot_of(refuge), status='rejected')
    assert make_proposal('delete', refuge=None, snapshot=snapshot_of(refuge), status='approved')
    assert make_proposal('create', refuge=refuge, status='approved')


# =================================== revisió ===================================

def test_review_pendent_no_pot_portar_dades_de_revisio(world):
    from apps.proposals.tests.helpers import at
    violates('refuge_proposals_review_ck', reviewer='adm')
    violates('refuge_proposals_review_ck', reviewed_at=at(1))
    violates('refuge_proposals_review_ck', rejection_reason='no')


def test_review_aprovada_exigeix_data_i_no_te_motiu(world):
    with pytest.raises(IntegrityError) as info:
        sql("INSERT INTO proposals.refuge_proposals (action, status, payload, creator_uid) "
            "VALUES ('create', 'approved', %s::jsonb, 'u1')", ['{"name": "x", "coord": {"lat": 1, "long": 1}}'])
    assert info.value.__cause__.diag.constraint_name == 'refuge_proposals_review_ck'
    violates('refuge_proposals_review_ck', status='approved', rejection_reason='no')


def test_review_rebutjada_exigeix_data_i_el_motiu_es_opcional(world):
    with pytest.raises(IntegrityError) as info:
        sql("INSERT INTO proposals.refuge_proposals (action, status, payload, creator_uid) "
            "VALUES ('create', 'rejected', %s::jsonb, 'u1')", ['{"name": "x", "coord": {"lat": 1, "long": 1}}'])
    assert info.value.__cause__.diag.constraint_name == 'refuge_proposals_review_ck'
    assert make_proposal(status='rejected')                                    # sense motiu
    assert make_proposal(status='rejected', rejection_reason='no')


def test_review_resolta_amb_revisor_nul_es_valida(world):
    """Rebuig automàtic per esborrat del refugi i revisor eliminat (`SET NULL`)."""
    assert make_proposal(status='rejected', reviewer=None, rejection_reason='refuge has been deleted') is not None
    pid = make_proposal(status='approved')
    sql("UPDATE proposals.refuge_proposals SET reviewer_uid = NULL WHERE id = %s", [pid])


# =================================== claus i valors del payload ===================================

@pytest.mark.parametrize('extra', ['remarque', 'images_metadata', 'visitors', 'id', 'modified_at', 'foo'])
def test_payload_nomes_admet_la_llista_blanca(world, extra):
    violates('refuge_proposals_payload_keys_ck', payload=new_payload(**{extra: 'x'}))


def test_payload_amb_totes_les_claus_permeses(world):
    full = new_payload(description='d', links=['https://a.org'], region='r', departement='d', condition=2)
    assert make_proposal(payload=full)


@pytest.mark.parametrize('coord', ['text', [1, 2], {'lat': 1}, {'long': 1}, {}, None])
def test_coord_ha_de_ser_objecte_amb_lat_i_long(refuge, coord):
    violates('refuge_proposals_payload_coord_ck', action='update', refuge=refuge, payload={'coord': coord})


# =================================== mida i longituds ===================================

def test_mida_maxima_del_payload_i_de_la_foto(refuge):
    big = secrets.token_urlsafe(120_000)                                       # incompressible: > 64 KiB desat
    violates('refuge_proposals_size_ck', payload=new_payload(description=big))
    violates('refuge_proposals_size_ck', action='update', refuge=refuge, payload={'description': 'x'},
             snapshot=snapshot_of(refuge, description=big))


def test_comment_fins_a_4000(world):
    assert make_proposal(comment='x' * 4000)
    with pytest.raises(IntegrityError):
        make_proposal(comment='x' * 4001)


def test_rejection_reason_fins_a_2000(world):
    assert make_proposal(status='rejected', rejection_reason='x' * 2000)
    with pytest.raises(IntegrityError):
        make_proposal(status='rejected', rejection_reason='x' * 2001)


@pytest.mark.parametrize('field,value', [('action', 'merge'), ('status', 'done')])
def test_enumeracions(world, field, value):
    with pytest.raises(IntegrityError) as info:
        sql(f"INSERT INTO proposals.refuge_proposals (action, status, payload, creator_uid) "
            f"VALUES (%s, %s, %s::jsonb, 'u1')",
            [value if field == 'action' else 'create', value if field == 'status' else 'pending',
             '{"name": "x", "coord": {"lat": 1, "long": 1}}'])
    # PostgreSQL avalua els `CHECK` per ordre alfabètic: amb un `status` desconegut, `review_ck` salta abans que `status_ck`.
    assert info.value.__cause__.diag.constraint_name in (f'refuge_proposals_{field}_ck', 'refuge_proposals_review_ck')


# =================================== FK i ordre d'esborrat ===================================

def test_id_uuid_v7_de_la_bd(world):
    assert uuid7_ok(make_proposal())


def test_creador_inexistent_es_rebutjat(world):
    with pytest.raises(IntegrityError):
        make_proposal(creator='ghost')
        sql('SET CONSTRAINTS ALL IMMEDIATE')


def test_esborrar_un_usuari_deixa_la_proposta_anonima(world):
    pid = make_proposal(creator='u2')
    done = make_proposal(creator='u2', status='approved', reviewer='u3')
    sql("DELETE FROM users.users WHERE uid IN ('u2', 'u3')")
    assert proposal_row(pid)['creator_uid'] is None
    row = proposal_row(done)
    assert row['creator_uid'] is None and row['reviewer_uid'] is None and row['status'] == 'approved'


def test_esborrar_un_refugi_amb_propostes_historiques_les_deixa_sense_refugi(refuge):
    approved = make_proposal('update', refuge=refuge, status='approved')
    rejected = make_proposal('delete', refuge=refuge, status='rejected')
    with as_owner():
        type(refuge).objects.filter(pk=refuge.pk).delete()
    assert proposal_row(approved)['refuge_id'] is None and proposal_row(rejected)['refuge_id'] is None
    assert proposal_row(approved)['refuge_snapshot'] is not None


def test_no_es_pot_esborrar_un_refugi_amb_una_proposta_pendent_ordre_obligatori(refuge):
    """§2.18: el `SET NULL` violaria `refuge_ref_ck`; primer cal rebutjar les pendents."""
    make_proposal('update', refuge=refuge)
    with pytest.raises(IntegrityError):
        with as_owner():
            type(refuge).objects.filter(pk=refuge.pk).delete()


def test_rebutjant_primer_les_pendents_es_pot_esborrar_el_refugi(refuge):
    pid = make_proposal('update', refuge=refuge)
    sql("UPDATE proposals.refuge_proposals SET status = 'rejected', reviewed_at = now(), "
        "rejection_reason = 'refuge has been deleted', reviewer_uid = NULL WHERE refuge_id = %s AND status = 'pending'",
        [refuge.pk])
    with as_owner():
        type(refuge).objects.filter(pk=refuge.pk).delete()
    row = proposal_row(pid)
    assert row['refuge_id'] is None and row['status'] == 'rejected' and row['reviewer_uid'] is None


# =================================== model Django ===================================

def test_model_taula_i_camps(PM):
    m = PM.RefugeProposal
    assert m._meta.db_table == 'proposals"."refuge_proposals'
    names = {f.attname for f in m._meta.concrete_fields}
    assert {'id', 'refuge_id', 'action', 'status', 'payload', 'refuge_snapshot', 'comment', 'creator_id',
            'created_at', 'reviewer_id', 'reviewed_at', 'rejection_reason'} <= names


def test_model_crea_amb_defaults_de_la_bd(PM, world):
    with system_context():
        p = PM.RefugeProposal.objects.create(action='create', creator_id='u1',
                                             payload={'name': 'x', 'coord': {'lat': 1, 'long': 1}})
        p.refresh_from_db()                                      # dins el context: fora, la RLS no deixaria veure-la
    assert uuid7_ok(str(p.pk)) and p.status == 'pending' and p.created_at is not None
