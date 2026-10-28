"""
Models `MediaReport`, `ModerationNotice` i `HashBlocklistEntry` (chunk 9, §2.20–§2.22) i les seves restriccions amb el
rol `app` (SQL pla: no depenen del nom dels camps).

Contracte de models (`apps/moderation/models.py`): `MediaReport` (`db_table = 'moderation"."media_reports'`),
`ModerationNotice` (`'moderation"."moderation_notices'`), `HashBlocklistEntry`
(`'moderation"."moderation_hash_blocklist'`); PK `uuid` amb `db_default=uuidv7()`; FK `DO_NOTHING` + `db_constraint=False`
(les `ON DELETE` són del DDL, §6.3); `TextChoices` `ReportReason`, `ReportStatus`, `ReportPriority`, `ReportAction`,
`ReportSource`, `NoticeType`, `NoticeAction`, `HashCategory` i les constants de mòdul `AUTO_HIDE_REASONS` (frozenset) i
`AUTO_HIDE_DISTINCT_REPORTERS = 3`.
"""
import uuid
from datetime import timedelta

import pytest
from django.db import DatabaseError, IntegrityError, models, transaction

from apps.core.rls import system_context
from apps.moderation.tests.helpers import (
    AUTO_HIDE, HIDDEN, NOTICE_TYPES, REASONS, T0, at, count_reports, make_hash, make_media, make_notice, make_report,
    notice_rows, report_row, report_rows, sql)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.models, pytest.mark.integration,
              pytest.mark.real_permissions]

KEY = 'refugis-lliures/x/m1.webp'


def _fails(fn, exc=IntegrityError):
    with pytest.raises(exc):
        with transaction.atomic():
            fn()


# ---------- metadades ----------

def test_db_table_pk_i_fk(MM):
    for model, table in ((MM.MediaReport, 'moderation"."media_reports'),
                         (MM.ModerationNotice, 'moderation"."moderation_notices'),
                         (MM.HashBlocklistEntry, 'moderation"."moderation_hash_blocklist')):
        assert model._meta.db_table == table
        pk = model._meta.pk
        assert isinstance(pk, models.UUIDField) and pk.db_default is not models.NOT_PROVIDED
    for name, column in (('refuge', 'refuge_id'), ('reporter', 'reporter_uid'),
                         ('media_creator', 'media_creator_uid'), ('resolved_by', 'resolved_by')):
        f = MM.MediaReport._meta.get_field(name)
        assert f.remote_field.on_delete is models.DO_NOTHING and f.db_constraint is False and f.column == column, name
        assert f.null, name
    for name, column in (('user', 'user_uid'), ('refuge', 'refuge_id'), ('report', 'report_id')):
        f = MM.ModerationNotice._meta.get_field(name)
        assert f.remote_field.on_delete is models.DO_NOTHING and f.db_constraint is False and f.column == column, name


def test_textchoices_i_constants_amb_els_valors_del_disseny(MM):
    assert set(MM.ReportReason.values) == set(REASONS)
    assert set(MM.ReportStatus.values) == {'pending', 'resolved'}
    assert set(MM.ReportPriority.values) == {'high', 'normal'}
    assert set(MM.ReportAction.values) == {'dismiss', 'remove', 'remove_and_strike'}
    assert set(MM.ReportSource.values) == {'user', 'automatic'}
    assert set(MM.NoticeType.values) == set(NOTICE_TYPES)
    assert set(MM.NoticeAction.values) == {'dismiss', 'remove', 'remove_and_strike', 'auto_hide', 'upload_blocked'}
    assert set(MM.HashCategory.values) == {'csam', 'other'}
    assert set(MM.AUTO_HIDE_REASONS) == set(AUTO_HIDE) and MM.AUTO_HIDE_DISTINCT_REPORTERS == 3


def test_models_defaults_de_la_bd(MM, world):
    with system_context():
        r = MM.MediaReport.objects.create(refuge_id=world[0].pk, media_key=KEY, reporter_id='u2', reason='hate_speech')
        n = MM.ModerationNotice.objects.create(user_id='u1', type='content_removed', statement='x')
    assert isinstance(r.pk, uuid.UUID) and r.pk.version == 7 and isinstance(n.pk, uuid.UUID)
    row = report_row(str(r.pk))
    assert (row['status'], row['priority'], row['source'], row['legal_hold']) == ('pending', 'normal', 'user', False)
    assert row['created_at'] is not None and row['anonymized_at'] is None
    assert notice_rows('u1')[0]['automated'] is False


# ---------- CHECK de media_reports ----------

@pytest.mark.parametrize('reason', REASONS)
def test_tots_els_motius_s_accepten(world, reason):
    make_report(world[0], KEY, 'u2', reason)
    assert count_reports() == 1


def test_un_motiu_desconegut_es_rebutja(world):
    _fails(lambda: make_report(world[0], KEY, 'u2', 'spam'))


def test_other_exigeix_details_no_buits(world):
    _fails(lambda: sql("INSERT INTO moderation.media_reports (refuge_id, media_key, reporter_uid, reason) "
                       "VALUES (%s, %s, 'u2', 'other')", [world[0].pk, KEY]))
    _fails(lambda: make_report(world[0], KEY, 'u2', 'other', details='   '))
    make_report(world[0], KEY, 'u3', 'other', details='motiu')


def test_details_maxim_1000(world):
    make_report(world[0], KEY, 'u2', 'hate_speech', details='x' * 1000)
    _fails(lambda: make_report(world[0], KEY, 'u3', 'hate_speech', details='x' * 1001))


@pytest.mark.parametrize('column,value', [('status', 'closed'), ('priority', 'urgent'), ('source', 'bot')])
def test_enumeracions_amb_valor_invalid(world, column, value):
    _fails(lambda: sql(f"INSERT INTO moderation.media_reports (refuge_id, media_key, reporter_uid, reason, {column}) "
                       "VALUES (%s, %s, 'u2', 'hate_speech', %s)", [world[0].pk, KEY, value]))


def test_action_invalida(world):
    rid = make_report(world[0], KEY, 'u2')
    _fails(lambda: sql("UPDATE moderation.media_reports SET status = 'resolved', resolved_at = now(), "
                       "action = 'ban', statement = 'x' WHERE id = %s", [rid]))


def test_resolucio_coherent(world):
    rid = make_report(world[0], KEY, 'u2')
    # resolved sense action/statement/resolved_at
    _fails(lambda: sql("UPDATE moderation.media_reports SET status = 'resolved' WHERE id = %s", [rid]))
    _fails(lambda: sql("UPDATE moderation.media_reports SET status = 'resolved', resolved_at = now(), "
                       "action = 'remove' WHERE id = %s", [rid]))
    # pending amb camps de resolució
    _fails(lambda: sql("UPDATE moderation.media_reports SET action = 'remove' WHERE id = %s", [rid]))
    _fails(lambda: sql("UPDATE moderation.media_reports SET resolved_at = now() WHERE id = %s", [rid]))
    sql("UPDATE moderation.media_reports SET status = 'resolved', resolved_at = now(), resolved_by = 'adm', "
        "action = 'remove', statement = 'x' WHERE id = %s", [rid])
    assert report_row(rid)['status'] == 'resolved'


def test_no_es_pot_denunciar_el_propi_mitjà(world):
    _fails(lambda: make_report(world[0], KEY, 'u1', creator='u1'))
    make_report(world[0], KEY, 'u2', creator='u1')


def test_source_user_exigeix_denunciant_o_anonimitzacio(world):
    _fails(lambda: sql("INSERT INTO moderation.media_reports (refuge_id, media_key, reporter_uid, reason, source) "
                       "VALUES (%s, %s, NULL, 'hate_speech', 'user')", [world[0].pk, KEY]))
    make_report(world[0], KEY, None, 'child_sexual_abuse', anonymized_at=T0, legal_hold=True)       # anonimitzada


def test_source_automatic_no_pot_tenir_denunciant(world):
    _fails(lambda: sql("INSERT INTO moderation.media_reports (refuge_id, media_key, reporter_uid, reason, source) "
                       "VALUES (%s, %s, 'u2', 'hate_speech', 'automatic')", [world[0].pk, KEY]))
    make_report(world[0], 'moderation-hold/u/x', None, 'child_sexual_abuse', source='automatic')


def test_anonymized_at_nomes_amb_legal_hold(world):
    _fails(lambda: make_report(world[0], KEY, None, 'hate_speech', anonymized_at=T0, legal_hold=False))


# ---------- UNIQUE ----------

def test_una_denuncia_per_refugi_mitja_i_denunciant(world):
    make_report(world[0], KEY, 'u2', 'hate_speech')
    _fails(lambda: make_report(world[0], KEY, 'u2', 'animal_cruelty'))
    make_report(world[0], KEY, 'u3', 'hate_speech')                                  # un altre denunciant
    make_report(world[0], 'refugis-lliures/x/m2.webp', 'u2', 'hate_speech')          # un altre mitjà
    make_report(world[1], KEY, 'u2', 'hate_speech')                                  # un altre refugi


def test_el_conflicte_es_un_integrity_error_amb_el_nom_de_la_restriccio(world):
    make_report(world[0], KEY, 'u2')
    with pytest.raises(IntegrityError) as err:
        with transaction.atomic():
            make_report(world[0], KEY, 'u2')
    assert getattr(err.value.__cause__.diag, 'constraint_name', None) == 'media_reports_unique_reporter_uq'


def test_una_denuncia_automatica_per_mitja(world):
    make_report(world[0], 'moderation-hold/a', None, 'child_sexual_abuse', source='automatic')
    _fails(lambda: make_report(world[0], 'moderation-hold/a', None, 'child_sexual_abuse', source='automatic'))
    make_report(world[0], 'moderation-hold/b', None, 'child_sexual_abuse', source='automatic')


def test_una_automatica_amb_refuge_null_tambe_es_unica(world):
    """`NULLS NOT DISTINCT`: l'avatar (sense refugi) només té una automàtica per mitjà."""
    sql("INSERT INTO moderation.media_reports (refuge_id, media_key, reason, source, legal_hold) "
        "VALUES (NULL, 'moderation-hold/av', 'child_sexual_abuse', 'automatic', true)")
    _fails(lambda: sql("INSERT INTO moderation.media_reports (refuge_id, media_key, reason, source, legal_hold) "
                       "VALUES (NULL, 'moderation-hold/av', 'child_sexual_abuse', 'automatic', true)"))


def test_dues_denuncies_anonimitzades_del_mateix_mitja_conviuen(world):
    """Les desvinculades (`reporter_uid IS NULL`, `source='user'`) queden fora de les dues restriccions."""
    make_report(world[0], KEY, None, 'child_sexual_abuse', anonymized_at=T0, legal_hold=True)
    make_report(world[0], KEY, None, 'child_sexual_abuse', anonymized_at=T0, legal_hold=True)
    assert count_reports() == 2


# ---------- ON DELETE de la BD (rol app amb el seu context) ----------

def test_esborrar_el_refugi_cascadeja_les_denuncies_no_legal_hold(world):
    r = world[0]
    make_report(r, KEY, 'u2', 'hate_speech')
    make_report(r, 'k2', 'u3', 'child_sexual_abuse')
    make_report(world[1], KEY, 'u2', 'hate_speech')
    from apps.moderation.tests.helpers import as_owner
    with as_owner():
        sql('DELETE FROM refuges.refuges WHERE id = %s', [r.pk])
    rows = report_rows()
    assert len(rows) == 2
    legal = [x for x in rows if x['legal_hold']]
    assert len(legal) == 1 and legal[0]['refuge_id'] is None and legal[0]['media_key'] == 'k2'
    assert [x['refuge_id'] for x in rows if not x['legal_hold']] == [str(world[1].pk)]


def test_el_refugi_esborrat_deixa_els_avisos_amb_refuge_id_null(world):
    n = make_notice('u1', refuge=world[0], media_key=KEY)
    from apps.moderation.tests.helpers import as_owner
    with as_owner():
        sql('DELETE FROM refuges.refuges WHERE id = %s', [world[0].pk])
    [row] = notice_rows('u1')
    assert row['id'] == n and row['refuge_id'] is None and row['media_key'] == KEY


def test_esborrar_la_denuncia_deixa_l_avis_amb_report_id_null(world):
    rid = make_report(world[0], KEY, 'u2')
    make_notice('u1', report_id=rid)
    sql('DELETE FROM moderation.media_reports WHERE id = %s', [rid])
    assert notice_rows('u1')[0]['report_id'] is None


def test_esborrar_l_admin_que_va_resoldre_deixa_resolved_by_null(world):
    rid = make_report(world[0], KEY, 'u2', status='resolved', resolved_by='adm')
    sql('DELETE FROM users.users WHERE uid = %s', ['adm'])
    row = report_row(rid)
    assert row['status'] == 'resolved' and row['resolved_by'] is None and row['statement'] == 'motiu'


# ---------- avisos ----------

@pytest.mark.parametrize('type_', NOTICE_TYPES)
def test_tots_els_tipus_d_avis(world, type_):
    make_notice('u1', type_)
    assert len(notice_rows('u1')) == 1


def test_avis_amb_tipus_o_accio_invalids(world):
    _fails(lambda: make_notice('u1', 'bogus'))
    _fails(lambda: make_notice('u1', 'strike', action='ban'))
    for action in ('dismiss', 'remove', 'remove_and_strike', 'auto_hide', 'upload_blocked'):
        make_notice('u1', 'strike', action=action)


def test_avis_amb_strikes_negatius(world):
    _fails(lambda: make_notice('u1', 'strike', strikes=-1))
    make_notice('u1', 'strike', strikes=0)


# ---------- llista de hashes ----------

def test_hash_valid_i_invalids(world):
    make_hash(sha256='a' * 64)
    make_hash(phash=-1)
    make_hash(sha256='b' * 64, phash=5, category='other')
    from apps.moderation.tests.helpers import as_owner
    with as_owner():
        _fails(lambda: sql("INSERT INTO moderation.moderation_hash_blocklist (sha256, source) VALUES (%s, 'x')",
                           ['A' * 64]))                                            # en majúscules: el CHECK és minúscula
        _fails(lambda: sql("INSERT INTO moderation.moderation_hash_blocklist (sha256, source) VALUES (%s, 'x')",
                           ['a' * 63]))
        _fails(lambda: sql("INSERT INTO moderation.moderation_hash_blocklist (source) VALUES ('x')"))   # cap hash
        _fails(lambda: sql("INSERT INTO moderation.moderation_hash_blocklist (sha256, category, source) "
                           "VALUES (%s, 'terror', 'x')", ['c' * 64]))
        _fails(lambda: sql("INSERT INTO moderation.moderation_hash_blocklist (sha256, source) VALUES (%s, 'x')",
                           ['a' * 64]))                                            # sha256 repetit


def test_dues_entrades_nomes_amb_phash_poden_coincidir(world):
    make_hash(phash=7)
    make_hash(phash=7)                                                              # sense UNIQUE sobre phash (§2.22)


def test_app_no_pot_llegir_ni_escriure_la_llista_de_hashes(world):
    make_hash(sha256='d' * 64)
    for statement in ('SELECT * FROM moderation.moderation_hash_blocklist',
                      "INSERT INTO moderation.moderation_hash_blocklist (sha256, source) VALUES ('%s', 'x')" % ('e' * 64),
                      'DELETE FROM moderation.moderation_hash_blocklist'):
        with pytest.raises(DatabaseError) as err:
            with transaction.atomic():
                sql(statement)
        assert getattr(err.value.__cause__, 'sqlstate', None) == '42501', statement
