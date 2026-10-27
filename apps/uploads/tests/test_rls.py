"""
RLS de `moderation.upload_intents` amb el rol `app` (§2.19, §7.5): anònim, propi, aliè, admin i sistema.

- `SELECT`: només el propietari o el sistema (l'admin NO veu els intents dels altres: són privats).
- `INSERT`: `user_uid = {U}` i `status = 'pending'` (i, si hi ha `experience_id`, l'experiència és meva o sóc admin), o
  sistema. Ningú pot inserir en nom d'un altre.
- `UPDATE` (marcar confirmat/fallat): el propietari o el sistema; no es pot traspassar a un altre usuari.
- `DELETE`: només el sistema (job de purga).
Un `INSERT` denegat per la RLS llança error; un `SELECT`/`UPDATE`/`DELETE` denegat afecta 0 files.
"""
import pytest
from django.db import DatabaseError, connection, transaction

from apps.core.rls import rls_context
from apps.experiences.tests.helpers import make_experience
from apps.uploads.tests.helpers import intent_ids, intent_row, make_intent, make_refuge, make_user, sql

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.rls, pytest.mark.integration,
              pytest.mark.real_permissions]

ANON = {}
OWN = {'uid': 'u1'}
OTHER = {'uid': 'u2'}
ADMIN = {'uid': 'adm', 'is_admin': True}
SYSTEM = {'system': True}
ALL_CTX = {'anon': ANON, 'own': OWN, 'other': OTHER, 'admin': ADMIN, 'system': SYSTEM}
SEES_U1 = {'anon': False, 'own': True, 'other': False, 'admin': False, 'system': True}
INSERT_AS_U1 = {'anon': False, 'own': True, 'other': False, 'admin': False, 'system': True}
UPDATE_U1 = {'anon': False, 'own': True, 'other': False, 'admin': False, 'system': True}
DELETE_U1 = {'anon': False, 'own': False, 'other': False, 'admin': False, 'system': True}

INSERT = ("INSERT INTO moderation.upload_intents (user_uid, target, content_type, size, quarantine_key, {extra}"
          "rights_confirmed_at) VALUES (%s, %s, 'image/png', 5, %s, {marks}now())")


@pytest.fixture
def world():
    for uid in ('u1', 'u2', 'adm'):
        make_user(uid)
    return make_refuge()


def _run(ctx, statement, params=None):
    with rls_context(**ALL_CTX[ctx]):
        with connection.cursor() as cur:
            cur.execute(statement, params)
            return cur.fetchall() if cur.description else cur.rowcount


def _denied(fn):
    with pytest.raises(DatabaseError):
        with transaction.atomic():
            fn()


def _insert_avatar(ctx, uid, key):
    _run(ctx, INSERT.format(extra='', marks=''), [uid, 'avatar', key])


# =================================== SELECT ===================================

@pytest.mark.parametrize('ctx', ALL_CTX)
def test_select_dels_intents_d_u1(world, ctx):
    make_intent('u1', 'avatar')
    n = _run(ctx, 'SELECT count(*) FROM moderation.upload_intents')[0][0]
    assert n == (1 if SEES_U1[ctx] else 0)


def test_cadascu_nomes_veu_els_seus(world):
    a, b = make_intent('u1', 'avatar'), make_intent('u2', 'avatar')
    assert [str(r[0]) for r in _run('own', 'SELECT id FROM moderation.upload_intents')] == [a]
    assert [str(r[0]) for r in _run('other', 'SELECT id FROM moderation.upload_intents')] == [b]
    assert sorted(str(r[0]) for r in _run('system', 'SELECT id FROM moderation.upload_intents')) == sorted([a, b])
    assert _run('admin', 'SELECT id FROM moderation.upload_intents') == []


def test_select_sense_cap_context_no_veu_res(world):
    make_intent('u1', 'avatar')
    with connection.cursor() as cur:
        cur.execute('SELECT count(*) FROM moderation.upload_intents')
        assert cur.fetchone() == (0,)


# =================================== INSERT ===================================

@pytest.mark.parametrize('ctx', ALL_CTX)
def test_insert_amb_user_uid_u1(world, ctx):
    go = lambda: _insert_avatar(ctx, 'u1', f'quarantine/{ctx}')                 # noqa: E731
    if INSERT_AS_U1[ctx]:
        go()
        assert len(intent_ids('u1')) == 1
    else:
        _denied(go)
        assert intent_ids() == []


def test_l_admin_si_pot_inserir_en_nom_propi(world):
    _insert_avatar('admin', 'adm', 'quarantine/adm')
    assert len(intent_ids('adm')) == 1


def test_insert_nomes_com_a_pending_per_a_un_usuari(world):
    def go():
        _run('own', "INSERT INTO moderation.upload_intents (user_uid, target, content_type, size, quarantine_key, "
                    "status, result_key, rights_confirmed_at) VALUES ('u1', 'avatar', 'image/png', 5, 'quarantine/c', "
                    "'confirmed', 'k', now())")
    _denied(go)
    assert intent_ids() == []


def test_el_sistema_pot_inserir_en_qualsevol_estat(world):
    make_intent('u1', 'avatar', status='confirmed', result_key='k/a.webp')
    assert len(intent_ids('u1')) == 1


def test_insert_amb_experiencia_propia_si_aliena_no(world):
    r = world
    mine, theirs = make_experience(r, 'u1'), make_experience(r, 'u2')
    q = INSERT.format(extra='refuge_id, experience_id, ', marks='%s, %s, ')
    _run('own', q, ['u1', 'experience', 'quarantine/mine', r.pk, mine])
    _denied(lambda: _run('own', q, ['u1', 'experience', 'quarantine/theirs', r.pk, theirs]))
    assert len(intent_ids('u1')) == 1


def test_l_admin_pot_crear_un_intent_propi_sobre_l_experiencia_d_un_altre(world):
    r = world
    theirs = make_experience(r, 'u1')
    q = INSERT.format(extra='refuge_id, experience_id, ', marks='%s, %s, ')
    _run('admin', q, ['adm', 'experience', 'quarantine/adm-exp', r.pk, theirs])
    assert len(intent_ids('adm')) == 1


def test_insert_sobre_una_experiencia_inexistent_es_denegat(world):
    import uuid
    q = INSERT.format(extra='refuge_id, experience_id, ', marks='%s, %s, ')
    make_intent('u1', 'avatar')                                                 # la taula ha d'existir
    _denied(lambda: _run('own', q, ['u1', 'experience', 'quarantine/x', world.pk, str(uuid.uuid4())]))
    assert len(intent_ids()) == 1


def test_insert_sense_context_es_denegat_fail_closed(world):
    make_intent('u1', 'avatar')
    def go():
        with connection.cursor() as cur:
            cur.execute(INSERT.format(extra='', marks=''), ['u1', 'avatar', 'quarantine/x'])
    _denied(go)


# =================================== UPDATE ===================================

@pytest.mark.parametrize('ctx', ALL_CTX)
def test_update_per_marcar_confirmat(world, ctx):
    i = make_intent('u1', 'avatar')
    n = _run(ctx, "UPDATE moderation.upload_intents SET status = 'confirmed', result_key = 'k/a.webp' WHERE id = %s", [i])
    assert n == (1 if UPDATE_U1[ctx] else 0)
    assert intent_row(i)['status'] == ('confirmed' if UPDATE_U1[ctx] else 'pending')


@pytest.mark.parametrize('ctx', ALL_CTX)
def test_update_per_marcar_fallat(world, ctx):
    i = make_intent('u1', 'avatar')
    n = _run(ctx, "UPDATE moderation.upload_intents SET status = 'failed', failure_reason = 'too_large' WHERE id = %s", [i])
    assert n == (1 if UPDATE_U1[ctx] else 0)


def test_no_es_pot_traspassar_un_intent_a_un_altre_usuari(world):
    i = make_intent('u1', 'avatar')
    _denied(lambda: _run('own', "UPDATE moderation.upload_intents SET user_uid = 'u2' WHERE id = %s", [i]))
    assert intent_row(i)['user_uid'] == 'u1'


# =================================== DELETE ===================================

@pytest.mark.parametrize('ctx', ALL_CTX)
def test_delete_nomes_el_sistema(world, ctx):
    i = make_intent('u1', 'avatar')
    n = _run(ctx, 'DELETE FROM moderation.upload_intents WHERE id = %s', [i])
    assert n == (1 if DELETE_U1[ctx] else 0)
    assert intent_ids() == ([] if DELETE_U1[ctx] else [i])


@pytest.mark.parametrize('ctx', ALL_CTX)
def test_no_hi_ha_truncate(world, ctx):
    make_intent('u1', 'avatar')
    _denied(lambda: _run(ctx, 'TRUNCATE moderation.upload_intents'))


# =================================== cascades amb el rol app ===================================

def test_esborrar_l_usuari_amb_el_rol_app_cascadeja_els_seus_intents_sense_que_la_rls_ho_talli(world):
    make_intent('u1', 'avatar')
    keep = make_intent('u2', 'avatar')
    assert _run('own', 'DELETE FROM users.users WHERE uid = %s', ['u1']) == 1
    assert intent_ids() == [keep]
