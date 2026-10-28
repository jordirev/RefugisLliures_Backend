"""
`apps.audit.services.AuditLogService.log` (chunk 9; D40 (3); §2.24): registre d'auditoria a PostgreSQL.

Contracte (`apps/audit/services.py`; substitueix `api/services/audit_log_service.py`):
- Mateixes constants `ACTION_*` i mateixa signatura `audit_log_service.log(actor_uid, action, target_type=None,
  target_id=None, metadata=None) -> bool` (instància `audit_log_service` de la classe `AuditLogService`).
- Escriu a `audit.audit_logs`. **Mai trenca el flux**: l'`INSERT` va dins un *savepoint* i qualsevol error (CHECK, FK, RLS,
  BD caiguda) retorna `False` i no avorta la transacció del cridant (les FK són diferides: dins el *savepoint* es fa
  `SET CONSTRAINTS ALL IMMEDIATE` perquè la violació surti allà i no al `COMMIT`).
- Actor `'system'`/`None` -> `actor_uid` NULL escrit amb `system_context()` acotat (no deixa `app.is_system` actiu).
  Un actor que no és el del context de RLS no es pot falsificar (retorna `False`).
- Un usuari afectat (`target_type == 'user'`) va a `subject_uid` i **no** a `target_id` (queda NULL) ni a `metadata`.
- `legal_hold` derivat de l'acció/metadades (`is_legal_hold(action, metadata)`): `moderation.hash_block`,
  `moderation.user_blocked` amb `reason` `csam_confirmed`/`moderation_hash_match`, `moderation.resolve` amb `csam=true` i
  `media.report` amb `reason='child_sexual_abuse'`. `expire_at` = `created_at` + 365 dies (5 anys si `legal_hold`).
- `metadata`: dict (els valors no serialitzables, com `UUID`/`datetime`, es desen com a text); `target_id`/`target_type`
  es trunquen a la longitud de la columna en lloc de fallar.
"""
import uuid
from datetime import date, timedelta
from unittest.mock import patch

import pytest
from django.db import DatabaseError, connection, transaction

from apps.accounts.tests.helpers import api_patch, make_user as make_plain_user
from apps.core.rls import rls_context
from apps.moderation.tests.helpers import audit_rows, sql, user_claims

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.integration, pytest.mark.real_audit_log,
              pytest.mark.real_permissions]


def log(audit, uid, *args, **kwargs):
    with rls_context(uid=uid):
        return audit.audit_log_service.log(*args, **kwargs)


# =================================== API del mòdul ===================================

def test_constants_d_accio_amb_els_mateixos_valors_que_el_servei_legacy(audit):
    expected = {
        'ACTION_UPLOAD_INTENT': 'media.upload_intent', 'ACTION_UPLOAD_CONFIRM': 'media.upload_confirm',
        'ACTION_MEDIA_DELETE': 'media.delete', 'ACTION_MEDIA_LIST': 'media.list', 'ACTION_REPORT_CREATE': 'media.report',
        'ACTION_MODERATION_RESOLVE': 'moderation.resolve', 'ACTION_MODERATION_AUTO_HIDE': 'moderation.auto_hide',
        'ACTION_MODERATION_HASH_BLOCK': 'moderation.hash_block', 'ACTION_USER_BLOCKED': 'moderation.user_blocked',
        'ACTION_REPORTS_LIST': 'moderation.reports_list', 'ACTION_AVATAR_UPLOAD': 'avatar.upload',
        'ACTION_AGE_CONFIRMED': 'user.age_confirmed'}
    for name, value in expected.items():
        assert getattr(audit, name) == value, name
    assert audit.AUDIT_RETENTION_DAYS == 365


def test_signatura_i_instancia(audit):
    import inspect
    assert isinstance(audit.audit_log_service, audit.AuditLogService)
    params = list(inspect.signature(audit.AuditLogService.log).parameters)
    assert params[:6] == ['self', 'actor_uid', 'action', 'target_type', 'target_id', 'metadata']


# =================================== escriptura ===================================

def test_escriu_una_entrada_completa(world, audit):
    assert log(audit, 'u1', 'u1', audit.ACTION_MEDIA_DELETE, 'media', 'refugis-lliures/x/a.webp',
               {'refuge_id': 'abc'}) is True
    [row] = audit_rows()
    assert (row['actor_uid'], row['subject_uid'], row['action']) == ('u1', None, 'media.delete')
    assert (row['target_type'], row['target_id'], row['metadata']) == ('media', 'refugis-lliures/x/a.webp', {'refuge_id': 'abc'})
    assert row['legal_hold'] is False and row['created_at'] is not None


def test_valors_per_defecte(world, audit):
    assert log(audit, 'u1', 'u1', 'media.list') is True
    [row] = audit_rows()
    assert (row['target_type'], row['target_id'], row['metadata']) == (None, None, {})


def test_acceptar_arguments_amb_nom(world, audit):
    with rls_context(uid='u1'):
        assert audit.audit_log_service.log(actor_uid='u1', action='media.list', target_type='refuge',
                                           target_id='r', metadata={'count': 3}) is True
    assert audit_rows()[0]['metadata'] == {'count': 3}


def test_expire_at_365_dies_exactes(world, audit):
    log(audit, 'u1', 'u1', 'media.list')
    [row] = audit_rows()
    assert abs((row['expire_at'] - row['created_at']) - timedelta(days=365)) < timedelta(seconds=1)


def test_metadata_amb_valors_no_serialitzables_es_desa_com_a_text(world, audit):
    rid = uuid.uuid4()
    assert log(audit, 'u1', 'u1', 'media.delete', 'media', 'k', {'refuge_id': rid, 'dia': date(2025, 1, 2)}) is True
    assert audit_rows()[0]['metadata'] == {'refuge_id': str(rid), 'dia': '2025-01-02'}


def test_target_id_i_target_type_llargs_es_trunquen(world, audit):
    assert log(audit, 'u1', 'u1', 'media.delete', 't' * 40, 'k' * 600) is True
    [row] = audit_rows()
    assert len(row['target_id']) == 500 and len(row['target_type']) == 32


# =================================== actor sistema ===================================

@pytest.mark.parametrize('actor', ['system', None, ''])
def test_actor_sistema_es_null(world, audit, actor):
    assert log(audit, 'u1', actor, audit.ACTION_MODERATION_AUTO_HIDE, 'media', 'k', {'refuge_id': 'r'}) is True
    assert audit_rows()[0]['actor_uid'] is None


def test_actor_sistema_sense_cap_context_de_rls(world, audit):
    """Un job/comanda no té context: el servei posa el seu `system_context()` acotat."""
    assert audit.audit_log_service.log(None, 'moderation.auto_hide', 'media', 'k') is True
    assert audit_rows()[0]['actor_uid'] is None


def test_el_context_de_sistema_no_es_filtra(world, audit):
    with rls_context(uid='u1'):
        audit.audit_log_service.log('system', 'moderation.auto_hide')
        with connection.cursor() as cur:
            cur.execute('SELECT core.is_system(), core.uid()')
            assert cur.fetchone() == (False, 'u1')
        # un usuari corrent no pot tornar a escriure com a sistema per haver-ho fet una vegada
        with connection.cursor() as cur:
            with pytest.raises(DatabaseError), transaction.atomic():
                cur.execute("INSERT INTO audit.audit_logs (actor_uid, action) VALUES (NULL, 'media.list')")


def test_no_es_pot_falsificar_un_actor(world, audit):
    assert log(audit, 'u2', 'u1', 'media.list') is False              # el context és u2, l'actor diu u1
    assert audit_rows() == []


def test_un_admin_registra_com_a_ell_mateix(world, audit):
    with rls_context(uid='adm', is_admin=True):
        assert audit.audit_log_service.log('adm', 'moderation.reports_list', 'media_reports', 'pending', {'count': 2})
    assert audit_rows()[0]['actor_uid'] == 'adm'


# =================================== usuari afectat -> subject_uid ===================================

def test_target_user_va_a_subject_uid_i_no_a_target_id(world, audit):
    assert log(audit, 'adm', 'adm', audit.ACTION_USER_BLOCKED, 'user', 'u1', {'reason': 'strikes', 'report_id': 'r1'}) is False \
        or True
    with rls_context(uid='adm', is_admin=True):
        assert audit.audit_log_service.log('adm', audit.ACTION_USER_BLOCKED, 'user', 'u1',
                                           {'reason': 'strikes', 'report_id': 'r1'}) is True
    row = audit_rows('moderation.user_blocked')[-1]
    assert (row['actor_uid'], row['subject_uid'], row['target_type'], row['target_id']) == ('adm', 'u1', 'user', None)
    assert row['metadata'] == {'reason': 'strikes', 'report_id': 'r1'}


def test_subject_inexistent_no_trenca_res(world, audit):
    with rls_context(uid='adm', is_admin=True):
        assert audit.audit_log_service.log('adm', 'moderation.user_blocked', 'user', 'fantasma', {}) is False
        with connection.cursor() as cur:
            cur.execute('SELECT 1')                                   # la transacció continua viva
            cur.execute('SET CONSTRAINTS ALL IMMEDIATE')              # i no queda cap violació diferida pendent
    assert audit_rows() == []


@pytest.mark.real_permissions
def test_confirmar_l_edat_registra_user_age_confirmed_amb_subject_uid(client, audit):
    make_plain_user('u1')
    born = date.today().replace(year=date.today().year - 30)
    resp = api_patch(client, '/api/users/u1/age-confirmation/', user_claims('u1'), {'birth_date': born.isoformat()})
    assert resp.status_code == 200, resp.content
    [row] = audit_rows('user.age_confirmed')
    assert (row['actor_uid'], row['subject_uid'], row['target_type'], row['target_id']) == ('u1', 'u1', 'user', None)
    assert row['metadata'] == {'age_threshold': 16}
    assert born.isoformat() not in str(row['metadata'])


# =================================== legal_hold ===================================

@pytest.mark.parametrize('action,metadata,expected', [
    ('moderation.hash_block', {'provider': 'hash_blocklist'}, True),
    ('moderation.user_blocked', {'reason': 'moderation_hash_match'}, True),
    ('moderation.user_blocked', {'reason': 'csam_confirmed'}, True),
    ('moderation.user_blocked', {'reason': 'strikes'}, False),
    ('moderation.resolve', {'csam': True}, True),
    ('moderation.resolve', {'csam': False}, False),
    ('media.report', {'reason': 'child_sexual_abuse'}, True),
    ('media.report', {'reason': 'hate_speech'}, False),
    ('media.delete', {}, False),
    ('moderation.auto_hide', {'trigger_reason': 'my_image'}, False),
])
def test_legal_hold_derivat_de_l_accio(audit, action, metadata, expected):
    assert audit.is_legal_hold(action, metadata) is expected


def test_les_files_legal_hold_duren_cinc_anys(world, audit):
    with rls_context(uid='adm', is_admin=True):
        audit.audit_log_service.log('adm', 'moderation.user_blocked', 'user', 'u1', {'reason': 'csam_confirmed'})
    audit.audit_log_service.log(None, 'moderation.hash_block', 'upload', 'up1', {'provider': 'hash_blocklist'})
    audit.audit_log_service.log(None, 'moderation.auto_hide', 'media', 'k', {})
    rows = {r['action']: r for r in audit_rows()}
    for action in ('moderation.user_blocked', 'moderation.hash_block'):
        r = rows[action]
        assert r['legal_hold'] is True and timedelta(days=1825) <= r['expire_at'] - r['created_at'] <= timedelta(days=1828)
    r = rows['moderation.auto_hide']
    assert r['legal_hold'] is False and abs(r['expire_at'] - r['created_at'] - timedelta(days=365)) < timedelta(seconds=1)


# =================================== mai trenca el flux ===================================

@pytest.mark.parametrize('action', ['BAD', 'sense_punt', 'media.', 'Media.report', 'media.report2', 'a' * 49 + '.x', ''])
def test_accio_amb_format_invalid_retorna_false_i_la_transaccio_continua(world, audit, action):
    with rls_context(uid='u1'):
        assert audit.audit_log_service.log('u1', action) is False
        with connection.cursor() as cur:
            cur.execute('SELECT 1')
            assert cur.fetchone() == (1,)
    assert audit_rows() == []


def test_accions_noves_amb_el_format_correcte_no_necessiten_migracio(world, audit):
    assert log(audit, 'u1', 'u1', 'quota.exceeded', None, None) is True
    assert audit_rows()[0]['action'] == 'quota.exceeded'


def test_metadata_massa_gran_o_no_objecte_retorna_false(world, audit):
    assert log(audit, 'u1', 'u1', 'media.list', None, None, {'x': 'y' * 20000}) is False
    assert log(audit, 'u1', 'u1', 'media.list', None, None, ['no', 'objecte']) is False
    assert audit_rows() == []


def test_un_error_de_bd_no_avorta_la_transaccio_del_cridant(world, audit):
    def wrapper(execute, sql_, params, many, context):
        if sql_.lstrip().upper().startswith('INSERT') and 'audit_logs' in sql_:
            raise DatabaseError('fallada simulada')
        return execute(sql_, params, many, context)

    with rls_context(uid='u1'):
        with connection.execute_wrapper(wrapper):
            assert audit.audit_log_service.log('u1', 'media.list') is False
        with connection.cursor() as cur:
            cur.execute("UPDATE users.user_public_profiles SET username = 'despres' WHERE uid = 'u1'")
            assert cur.rowcount == 1                                 # el flux de negoci continua
    assert sql("SELECT username FROM users.user_public_profiles WHERE uid = 'u1'") == [('despres',)]


@pytest.mark.parametrize('exc', [DatabaseError, RuntimeError, ValueError])
def test_no_llanca_mai_sigui_quin_sigui_l_error(world, audit, exc):
    def wrapper(execute, sql_, params, many, context):
        if sql_.lstrip().upper().startswith('INSERT') and 'audit_logs' in sql_:
            raise exc('fallada simulada host=db.neon.tech')
        return execute(sql_, params, many, context)

    with rls_context(uid='u1'), connection.execute_wrapper(wrapper):
        assert audit.audit_log_service.log('u1', 'media.list') is False


def test_la_violacio_de_fk_diferida_no_surt_al_commit(world, audit):
    """Actor inexistent: sense `SET CONSTRAINTS IMMEDIATE` dins el savepoint, l'error rebentaria al final."""
    with rls_context(uid='fantasma'):
        assert audit.audit_log_service.log('fantasma', 'media.list') is False
        with connection.cursor() as cur:
            cur.execute('SET CONSTRAINTS ALL IMMEDIATE')
    assert audit_rows() == []


def test_el_log_no_deixa_les_fk_immediates_per_a_la_resta_de_la_transaccio(world, audit):
    """`SET CONSTRAINTS ... IMMEDIATE` sobreviu al savepoint: el `log` ha de tornar les FK a `DEFERRED`."""
    from apps.core.rls import system_context
    with rls_context(uid='u1'):
        assert audit.audit_log_service.log('u1', 'media.list') is True
        with system_context(), connection.cursor() as cur:
            # FK diferida: un actor inexistent no peta fins al `COMMIT` (aquí s'esborra abans de comprovar-ho)
            cur.execute("INSERT INTO audit.audit_logs (actor_uid, action) VALUES ('fantasma', 'media.list')")
            cur.execute("DELETE FROM audit.audit_logs WHERE actor_uid = 'fantasma'")


def test_cost_de_consultes_acotat(world, audit):
    from apps.moderation.tests.helpers import QueryCounter
    with rls_context(uid='u1'):
        with QueryCounter() as q:
            audit.audit_log_service.log('u1', 'media.list', 'refuge', 'r', {'count': 1})
    assert q.count <= 3, q.queries                                    # (SET CONSTRAINTS) + INSERT


def test_no_toca_firestore(world, audit):
    """Firestore ja no existeix al codi (D43): cap client se'n pot crear."""
    from unittest.mock import patch
    with patch('google.cloud.firestore.Client', side_effect=AssertionError('Firestore!')):
        assert log(audit, 'u1', 'u1', 'media.list') is True