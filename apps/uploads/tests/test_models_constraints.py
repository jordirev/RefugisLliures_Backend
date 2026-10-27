"""
Model `UploadIntent` (chunk 7, §2.19) i les seves restriccions, amb el rol `app`.

Contracte de models (`apps/uploads/models.py`): `UploadIntent` amb `id` (UUID `db_default=uuidv7()`), `user` (FK a
`accounts.UserAccount`, `db_column='user_uid'`), `target`, `content_type`, `size`, `quarantine_key`, `refuge` (FK nullable
a `refuges.Refuge`), `experience` (FK nullable a `experiences.Experience`), `status` (`pending`), `rights_confirmed_at`,
`created_at`, `expire_at` (`created_at + 1 dia`), `result_key`, `failure_reason`; `db_table = 'moderation"."upload_intents'`;
FK `DO_NOTHING` + `db_constraint=False`. Les enumeracions són `TextChoices` (`UploadTarget`, `UploadStatus`,
`UploadFailureReason`). Les restriccions es proven amb SQL pla (sense dependre del nom dels camps).
"""
import uuid
from datetime import timedelta

import pytest
from django.db import IntegrityError, models, transaction

from apps.core.rls import system_context
from apps.experiences.tests.helpers import make_experience
from apps.uploads.tests.helpers import intent_ids, intent_row, is_uuid, make_intent, sql

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.models, pytest.mark.integration,
              pytest.mark.real_permissions]


def _fails(fn):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            fn()


# ---------- metadades ----------

def test_db_table_pk_i_fk(UM):
    M = UM.UploadIntent
    assert M._meta.db_table == 'moderation"."upload_intents'
    pk = M._meta.pk
    assert isinstance(pk, models.UUIDField) and pk.db_default is not models.NOT_PROVIDED
    for name, column in (('user', 'user_uid'), ('refuge', 'refuge_id'), ('experience', 'experience_id')):
        f = M._meta.get_field(name)
        assert f.remote_field.on_delete is models.DO_NOTHING and f.db_constraint is False and f.column == column, name
    assert M._meta.get_field('refuge').null and M._meta.get_field('experience').null


def test_textchoices_amb_els_valors_del_disseny(UM):
    assert set(UM.UploadTarget.values) == {'refuge', 'experience', 'avatar'}
    assert set(UM.UploadStatus.values) == {'pending', 'confirmed', 'failed'}
    assert set(UM.UploadFailureReason.values) == {'missing_object', 'too_large', 'invalid_type', 'processing_error',
                                                  'moderation_blocked'}


# ---------- defaults de la BD ----------

def test_crear_usa_uuidv7_pending_i_expiracio_a_un_dia(UM, world):
    with system_context():
        i = UM.UploadIntent.objects.create(
            user_id='u1', target='refuge', refuge_id=world[0].pk, content_type='image/jpeg', size=10,
            quarantine_key='quarantine/x1', rights_confirmed_at=sql('SELECT now()')[0][0])
    assert isinstance(i.pk, uuid.UUID) and i.pk.version == 7
    row = intent_row(str(i.pk))
    assert row['status'] == 'pending' and row['result_key'] is None and row['failure_reason'] is None
    assert row['expire_at'] - row['created_at'] == timedelta(days=1)


# ---------- CHECK de forma (target) ----------

def test_forma_valida_per_a_cada_target(world):
    e = make_experience(world[0], 'u1')
    make_intent('u1', 'avatar')
    make_intent('u1', 'refuge', refuge=world[0])
    make_intent('u1', 'experience', refuge=world[0], experience_id=e)
    assert len(intent_ids('u1')) == 3


@pytest.mark.parametrize('target,with_refuge,with_experience', [
    ('avatar', True, False), ('avatar', False, True), ('avatar', True, True),
    ('refuge', False, False), ('refuge', True, True), ('refuge', False, True),
    ('experience', False, False), ('experience', True, False), ('experience', False, True),
])
def test_forma_invalida_rebutjada(world, target, with_refuge, with_experience):
    e = make_experience(world[0], 'u1')
    _fails(lambda: make_intent('u1', target, refuge=world[0] if with_refuge else None,
                               experience_id=e if with_experience else None))
    assert intent_ids() == []


def test_target_desconegut_rebutjat(world):
    _fails(lambda: make_intent('u1', 'banner'))


# ---------- CHECK d'estat ----------

@pytest.mark.parametrize('kwargs', [
    dict(status='confirmed'),                                           # confirmat sense result_key
    dict(status='pending', result_key='refugis-lliures/x/y.webp'),      # result_key sense estar confirmat
    dict(status='failed'),                                              # fallat sense motiu
    dict(status='pending', failure_reason='too_large'),                 # motiu sense estar fallat
    dict(status='confirmed', result_key='k', failure_reason='too_large'),
    dict(status='failed', failure_reason='too_large', result_key='k'),
    dict(status='failed', failure_reason='no_existeix'),                # motiu fora del catàleg
    dict(status='caducat'),                                             # estat fora del catàleg
])
def test_estat_incoherent_rebutjat(world, kwargs):
    _fails(lambda: make_intent('u1', 'avatar', **kwargs))
    assert intent_ids() == []


@pytest.mark.parametrize('kwargs', [
    dict(status='pending'),
    dict(status='confirmed', result_key='refugis-lliures/x/y.webp'),
    dict(status='failed', failure_reason='missing_object'),
    dict(status='failed', failure_reason='too_large'),
    dict(status='failed', failure_reason='invalid_type'),
    dict(status='failed', failure_reason='processing_error'),
    dict(status='failed', failure_reason='moderation_blocked'),
])
def test_estats_coherents_acceptats(world, kwargs):
    i = make_intent('u1', 'avatar', **kwargs)
    assert intent_row(i)['status'] == kwargs['status']


def test_pas_de_pending_a_confirmed_i_a_failed_amb_update(world):
    a, b = make_intent('u1', 'avatar'), make_intent('u1', 'avatar')
    sql("UPDATE moderation.upload_intents SET status = 'confirmed', result_key = 'k/a.webp' WHERE id = %s", [a])
    sql("UPDATE moderation.upload_intents SET status = 'failed', failure_reason = 'too_large' WHERE id = %s", [b])
    assert (intent_row(a)['status'], intent_row(b)['failure_reason']) == ('confirmed', 'too_large')
    c = make_intent('u1', 'avatar')
    _fails(lambda: sql("UPDATE moderation.upload_intents SET status = 'confirmed' WHERE id = %s", [c]))   # sense result_key


# ---------- mida, caducitat, unicitat ----------

@pytest.mark.parametrize('size', [0, -1])
def test_mida_ha_de_ser_positiva(world, size):
    _fails(lambda: make_intent('u1', 'avatar', size=size))


def test_expire_at_ha_de_ser_posterior_a_created_at(world):
    _fails(lambda: make_intent('u1', 'avatar', created_ago=timedelta(0), expires_in=timedelta(0)))
    _fails(lambda: make_intent('u1', 'avatar', created_ago=timedelta(0), expires_in=-timedelta(seconds=1)))


def test_quarantine_key_unica(world):
    i = make_intent('u1', 'avatar')
    def go():
        sql("INSERT INTO moderation.upload_intents (user_uid, target, content_type, size, quarantine_key, "
            "rights_confirmed_at) VALUES ('u1', 'avatar', 'image/png', 5, %s, now())", [f'quarantine/{i}'])
    _fails(go)


def test_usuari_inexistent_rebutjat_amb_constraints_immediate(world):
    def go():
        make_intent('fantasma', 'avatar')
        sql('SET CONSTRAINTS ALL IMMEDIATE')
    _fails(go)


# ---------- cascades ----------

def test_esborrar_l_usuari_cascadeja_els_seus_intents(world):
    a, b = make_intent('u1', 'avatar'), make_intent('u2', 'avatar')
    sql("DELETE FROM users.users WHERE uid = 'u1'")
    assert intent_ids() == [b]


def test_esborrar_el_refugi_cascadeja_els_intents_de_refugi_i_experiencia(world):
    from apps.experiences.tests.helpers import as_owner
    r1, r2 = world
    e1, e2 = make_experience(r1, 'u1'), make_experience(r2, 'u1')
    keep = make_intent('u1', 'refuge', refuge=r2)
    make_intent('u1', 'refuge', refuge=r1)
    make_intent('u1', 'experience', refuge=r1, experience_id=e1)
    avatar = make_intent('u1', 'avatar')
    with as_owner():
        sql('DELETE FROM refuges.refuges WHERE id = %s', [r1.pk])
    assert sorted(intent_ids()) == sorted([keep, avatar])


def test_esborrar_l_experiencia_cascadeja_els_intents_d_aquella_experiencia(world):
    r = world[0]
    e1, e2 = make_experience(r, 'u1'), make_experience(r, 'u1')
    gone = make_intent('u1', 'experience', refuge=r, experience_id=e1)
    kept = make_intent('u1', 'experience', refuge=r, experience_id=e2)
    sql('DELETE FROM activity.experiences WHERE id = %s', [e1])
    assert intent_ids() == [kept] and intent_row(gone) is None
