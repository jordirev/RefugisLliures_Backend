"""
Model `Experience` (chunk 7, §2.15) i les seves restriccions, amb el rol `app`.

Contracte de models (`apps/experiences/models.py`):
- `Experience`: `id` (UUID, `db_default=uuidv7()`), `refuge` (FK a `refuges.Refuge`, `db_column='refuge_id'`), `creator` (FK
  a `accounts.UserAccount`, `db_column='creator_uid'`), `comment`, `created_at`, `modified_at`, `condition`
  (smallint 0-3), `condition_counted_at`; `db_table = 'activity"."experiences'`.
- Les FK son `DO_NOTHING` + `db_constraint=False` (§6.3): les cascades son del DDL.
- `RefugeMedia.experience` (FK nullable a `Experience`, `db_column='experience_id'`, `DO_NOTHING`, `db_constraint=False`).
- `condition_counted_at` el posa el trigger (no l'aplicacio): el model no el pot inventar.
"""
import uuid

import pytest
from django.db import IntegrityError, models, transaction

from apps.core.rls import rls_context, system_context
from apps.experiences.tests.helpers import (
    exp_ids, exp_row, make_exp_media, make_experience, make_refuge, make_user, sql, utc)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.models, pytest.mark.integration,
              pytest.mark.real_permissions]


@pytest.fixture
def base():
    make_user('u1')
    make_user('u2')
    return make_refuge()


def _fails(fn):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            fn()


def _create(EM, refuge, **fields):
    fields.setdefault('creator_id', 'u1')
    fields.setdefault('comment', 'Bon refugi')
    fields.setdefault('condition', 2)
    with system_context():
        return EM.Experience.objects.create(refuge_id=refuge.pk, **fields)


# ---------- metadades ----------

def test_db_table_i_pk_uuid_amb_default_de_la_bd(EM):
    assert EM.Experience._meta.db_table == 'activity"."experiences'
    pk = EM.Experience._meta.pk
    assert isinstance(pk, models.UUIDField) and pk.name == 'id' and pk.db_default is not models.NOT_PROVIDED


def test_les_fk_son_do_nothing_sense_constraint_de_django(EM, RM):
    for name, column in (('refuge', 'refuge_id'), ('creator', 'creator_uid')):
        f = EM.Experience._meta.get_field(name)
        assert f.remote_field.on_delete is models.DO_NOTHING and f.db_constraint is False, name
        assert f.column == column
    media_fk = RM.RefugeMedia._meta.get_field('experience')
    assert media_fk.remote_field.model is EM.Experience and media_fk.column == 'experience_id'
    assert media_fk.null is True
    assert media_fk.remote_field.on_delete is models.DO_NOTHING and media_fk.db_constraint is False


def test_el_model_no_desa_media_keys(EM):
    names = {f.name for f in EM.Experience._meta.get_fields()}
    assert 'media_keys' not in names and 'images_metadata' not in names      # els mitjans son refuge_media.experience_id


# ---------- defaults de la BD ----------

def test_crear_usa_uuidv7_i_els_instants_de_la_bd(EM, base):
    e = _create(EM, base)
    assert isinstance(e.pk, uuid.UUID) and e.pk.version == 7
    row = exp_row(str(e.pk))
    assert row['created_at'] is not None and row['modified_at'] is not None
    assert row['condition_counted_at'] is not None
    assert row['modified_at'] == row['created_at']              # mateix now() de la transaccio


def test_el_trigger_posa_condition_counted_at_a_now_en_inserir(EM, base):
    """El valor que enviï l'aplicació es descarta: el posa el trigger (`NEW.condition_counted_at := now()`)."""
    e = _create(EM, base, condition_counted_at=utc(2000, 1, 1))
    row = exp_row(str(e.pk))
    assert row['condition_counted_at'].year >= 2025 and row['condition_counted_at'] == row['created_at']


# ---------- CHECK de la condicio ----------

@pytest.mark.parametrize('value', [0, 1, 2, 3])
def test_condicio_valida(EM, base, value):
    assert exp_row(str(_create(EM, base, condition=value).pk))['condition'] == value


@pytest.mark.parametrize('value', [-1, 4, 100])
def test_condicio_fora_de_rang_rebutjada(EM, base, value):
    _fails(lambda: _create(EM, base, condition=value))
    assert exp_ids() == []


def test_condicio_obligatoria(base):
    def go():
        with system_context():
            sql("INSERT INTO activity.experiences (refuge_id, creator_uid, comment) VALUES (%s, 'u1', 'x')", [base.pk])
    _fails(go)


# ---------- CHECK del comentari ----------

@pytest.mark.parametrize('comment', ['', ' ', '   ', '\n', '\t\n ', 'x' * 2001])
def test_comentari_buit_o_massa_llarg_rebutjat(EM, base, comment):
    _fails(lambda: _create(EM, base, comment=comment))
    assert exp_ids() == []


@pytest.mark.parametrize('comment', ['x', 'x' * 2000, ' hola ', 'ñandú ç à\nlinia 2'])
def test_comentari_valid(EM, base, comment):
    e = _create(EM, base, comment=comment)
    assert exp_row(str(e.pk))['comment'] == comment


def test_comentari_de_2000_caracters_multibyte_es_valid(EM, base):
    """`char_length`, no `length(bytea)`: 2000 caracters de 3 bytes passen."""
    comment = '€' * 2000
    assert exp_row(str(_create(EM, base, comment=comment).pk))['comment'] == comment


# ---------- FK reals ----------

def test_creador_inexistent_rebutjat_al_commit_o_amb_constraints_immediate(EM, base):
    def go():
        with system_context():
            EM.Experience.objects.create(refuge_id=base.pk, creator_id='fantasma', comment='x', condition=1)
            from django.db import connection
            with connection.cursor() as cur:
                cur.execute('SET CONSTRAINTS ALL IMMEDIATE')
    _fails(go)


def test_refugi_inexistent_rebutjat(EM, base):
    def go():
        with system_context():
            EM.Experience.objects.create(refuge_id=uuid.uuid4(), creator_id='u1', comment='x', condition=1)
            from django.db import connection
            with connection.cursor() as cur:
                cur.execute('SET CONSTRAINTS ALL IMMEDIATE')
    _fails(go)


# ---------- cascades (del DDL) ----------

def test_esborrar_el_refugi_cascadeja_experiencies_i_mitjans(base):
    from apps.experiences.tests.helpers import as_owner, media_keys_of
    e = make_experience(base, 'u1')
    make_exp_media(base, 'u1', e, key='k/a.webp')
    with as_owner():
        sql('DELETE FROM refuges.refuges WHERE id = %s', [base.pk])
    assert exp_ids() == [] and sql('SELECT count(*) FROM refuges.refuge_media') == [(0,)]


def test_esborrar_l_experiencia_cascadeja_nomes_els_seus_mitjans(base):
    from apps.experiences.tests.helpers import all_media_keys, media_keys_of
    e1, e2 = make_experience(base, 'u1'), make_experience(base, 'u2')
    make_exp_media(base, 'u1', e1, key='k/e1.webp', thumb_key='k/e1_thumb.webp')
    make_exp_media(base, 'u2', e2, key='k/e2.webp')
    from apps.experiences.tests.helpers import make_media
    make_media(base, 'u1', key='k/refuge-photo.webp')                       # foto del refugi, sense experiencia
    sql('DELETE FROM activity.experiences WHERE id = %s', [e1])
    assert all_media_keys() == ['k/e2.webp', 'k/refuge-photo.webp']
    assert media_keys_of(e2) == ['k/e2.webp']


def test_esborrar_l_usuari_cascadeja_les_seves_experiencies_i_mitjans(base):
    from apps.experiences.tests.helpers import all_media_keys
    e1, e2 = make_experience(base, 'u1'), make_experience(base, 'u2')
    make_exp_media(base, 'u1', e1, key='k/e1.webp')
    make_exp_media(base, 'u2', e2, key='k/e2.webp')
    sql("DELETE FROM users.users WHERE uid = 'u1'")
    assert exp_ids() == [e2] and all_media_keys() == ['k/e2.webp']


def test_un_mitja_no_pot_apuntar_a_una_experiencia_inexistent(base):
    from apps.experiences.tests.helpers import make_media
    def go():
        make_media(base, 'u1', key='k/orfe.webp', experience_id=uuid.uuid4())
        from django.db import connection
        with connection.cursor() as cur:
            cur.execute('SET CONSTRAINTS ALL IMMEDIATE')
    _fails(go)


def test_no_hi_ha_unicitat_per_usuari_i_refugi(EM, base):
    """Un usuari pot deixar diverses experiències al mateix refugi (com ara)."""
    _create(EM, base)
    _create(EM, base)
    assert len(exp_ids(base, 'u1')) == 2
