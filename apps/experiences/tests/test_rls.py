"""
RLS d'`activity.experiences` i de la política `media_insert` reescrita de `refuges.refuge_media` amb el rol `app`
(§2.8, §2.15, §7.5): anònim, propi, aliè, admin i sistema.

- `SELECT` d'experiències: públic (`USING (true)`), també sense context.
- `INSERT`: `creator_uid = {U}` o sistema (l'admin NO pot crear en nom d'un altre).
- `UPDATE`: el creador, l'admin o el sistema (el creador no pot passar l'experiència a un altre usuari).
- `DELETE`: el creador, l'admin o el sistema.
- `refuge_media.media_insert`: `creator_uid = {U} AND status = 'visible' AND (experience_id IS NULL OR l'experiència és
  meva)`, o admin, o sistema. Les cascades (FK `ON DELETE CASCADE`) no passen per la RLS.
Un `INSERT` denegat per la RLS llança error; un `SELECT`/`UPDATE`/`DELETE` denegat afecta 0 files.
"""
import pytest
from django.db import DatabaseError, connection, transaction

from apps.core.rls import rls_context
from apps.experiences.tests.helpers import (
    T0, all_media_keys, exp_ids, exp_row, make_exp_media, make_experience, make_refuge, make_user)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.rls, pytest.mark.integration,
              pytest.mark.real_permissions]

ANON = {}
OWN = {'uid': 'u1'}
OTHER = {'uid': 'u2'}
ADMIN = {'uid': 'adm', 'is_admin': True}
SYSTEM = {'system': True}
ALL_CTX = {'anon': ANON, 'own': OWN, 'other': OTHER, 'admin': ADMIN, 'system': SYSTEM}
# Qui pot modificar/esborrar les experiències d'`u1`
CAN_WRITE = {'anon': False, 'own': True, 'other': False, 'admin': True, 'system': True}
# Qui pot inserir experiències amb creator_uid = 'u1'
CAN_INSERT_AS_U1 = {'anon': False, 'own': True, 'other': False, 'admin': False, 'system': True}


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


# =================================== experiences: SELECT ===================================

@pytest.mark.parametrize('ctx', ALL_CTX)
def test_select_public_per_a_tothom_inclos_anonim(world, ctx):
    make_experience(world, 'u1')
    assert _run(ctx, 'SELECT count(*) FROM activity.experiences')[0][0] == 1


def test_select_sense_cap_context_tambe_funciona(world):
    make_experience(world, 'u1')
    with connection.cursor() as cur:
        cur.execute('SELECT count(*) FROM activity.experiences')
        assert cur.fetchone() == (1,)


# =================================== experiences: INSERT ===================================

@pytest.mark.parametrize('ctx', ALL_CTX)
def test_insert_amb_creator_u1(world, ctx):
    def go():
        _run(ctx, 'INSERT INTO activity.experiences (refuge_id, creator_uid, comment, condition) '
                  "VALUES (%s, 'u1', 'hola', 2)", [world.pk])
    if CAN_INSERT_AS_U1[ctx]:
        go()
        assert len(exp_ids()) == 1
    else:
        _denied(go)
        assert exp_ids() == []


def test_l_admin_si_pot_inserir_en_nom_propi(world):
    _run('admin', "INSERT INTO activity.experiences (refuge_id, creator_uid, comment, condition) "
                  "VALUES (%s, 'adm', 'consulta', 1)", [world.pk])
    assert len(exp_ids(creator_uid='adm')) == 1


def test_insert_amb_returning_i_defaults_de_la_bd(world):
    rows = _run('own', "INSERT INTO activity.experiences (refuge_id, creator_uid, comment, condition) "
                       "VALUES (%s, 'u1', 'x', 0) RETURNING id, created_at, modified_at, condition_counted_at",
                [world.pk])
    assert len(rows) == 1 and all(v is not None for v in rows[0])


def test_insert_sense_context_es_denegat_fail_closed(world):
    make_experience(world, 'u1')
    _denied(lambda: _exec("INSERT INTO activity.experiences (refuge_id, creator_uid, comment, condition) "
                          "VALUES (%s, 'u1', 'x', 1)", [world.pk]))


def _exec(statement, params=None):
    with connection.cursor() as cur:
        cur.execute(statement, params)


# =================================== experiences: UPDATE / DELETE ===================================

@pytest.mark.parametrize('ctx', ALL_CTX)
def test_update_del_comentari_d_una_experiencia_d_u1(world, ctx):
    e = make_experience(world, 'u1')
    n = _run(ctx, "UPDATE activity.experiences SET comment = 'editat' WHERE id = %s", [e])
    assert n == (1 if CAN_WRITE[ctx] else 0)
    assert exp_row(e)['comment'] == ('editat' if CAN_WRITE[ctx] else 'Refugi net')


@pytest.mark.parametrize('ctx', ALL_CTX)
def test_delete_d_una_experiencia_d_u1(world, ctx):
    e = make_experience(world, 'u1')
    n = _run(ctx, 'DELETE FROM activity.experiences WHERE id = %s', [e])
    assert n == (1 if CAN_WRITE[ctx] else 0)
    assert exp_ids() == ([] if CAN_WRITE[ctx] else [e])


def test_el_creador_no_pot_passar_l_experiencia_a_un_altre_usuari(world):
    e = make_experience(world, 'u1')
    _denied(lambda: _run('own', "UPDATE activity.experiences SET creator_uid = 'u2' WHERE id = %s", [e]))
    assert exp_row(e)['creator_uid'] == 'u1'


def test_l_admin_pot_editar_el_comentari_d_un_altre_i_l_autoria_es_conserva(world):
    """`USING/WITH CHECK (creator_uid = {U} OR {ADM} OR {SYS})` (§2.15): l'admin edita sense canviar l'autor."""
    e = make_experience(world, 'u1')
    assert _run('admin', "UPDATE activity.experiences SET comment = 'moderat' WHERE id = %s", [e]) == 1
    assert exp_row(e)['creator_uid'] == 'u1'


def test_delete_en_massa_nomes_afecta_les_files_permeses(world):
    make_experience(world, 'u1', minutes=0)
    make_experience(world, 'u2', minutes=1)
    make_experience(world, 'u1', minutes=2)
    assert _run('own', 'DELETE FROM activity.experiences') == 2
    assert len(exp_ids()) == 1
    assert _run('admin', 'DELETE FROM activity.experiences') == 1


@pytest.mark.parametrize('ctx', ALL_CTX)
def test_no_hi_ha_truncate(world, ctx):
    make_experience(world, 'u1')
    _denied(lambda: _run(ctx, 'TRUNCATE activity.experiences'))


# =================================== cascades amb el rol app ===================================

def test_esborrar_l_usuari_amb_el_rol_app_cascadeja_experiencies_i_mitjans(world):
    e1, e2 = make_experience(world, 'u1'), make_experience(world, 'u2')
    make_exp_media(world, 'u1', e1, key='k/e1.webp')
    make_exp_media(world, 'u2', e2, key='k/e2.webp')
    assert _run('own', 'DELETE FROM users.users WHERE uid = %s', ['u1']) == 1
    assert exp_ids() == [e2] and all_media_keys() == ['k/e2.webp']


def test_esborrar_l_experiencia_cascadeja_els_mitjans_encara_que_no_siguin_visibles_ni_propis(world):
    """El mitjà el pot haver pujat l'admin o estar amagat: la cascada no passa per la RLS de `refuge_media`."""
    e = make_experience(world, 'u1')
    make_exp_media(world, 'u1', e, key='k/own.webp')
    make_exp_media(world, 'adm', e, key='k/adm.webp', minutes=1)
    make_exp_media(world, 'u1', e, key='k/hid.webp', status='hidden_pending_review', minutes=2)
    assert _run('own', 'DELETE FROM activity.experiences WHERE id = %s', [e]) == 1
    assert all_media_keys() == []


# =================================== refuge_media.media_insert amb experience_id ===================================

def _insert_media(ctx, world, key, creator, experience_id, status='visible'):
    _run(ctx, 'INSERT INTO refuges.refuge_media (key, refuge_id, creator_uid, experience_id, media_type, content_type, '
              'status, rights_confirmed_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)',
         [key, world.pk, creator, experience_id, 'image', 'image/webp', status, T0])


@pytest.mark.parametrize('ctx,expected', [('anon', False), ('own', True), ('other', False), ('admin', True),
                                          ('system', True)])
def test_insert_de_media_a_una_experiencia_d_u1_creador_u1(world, ctx, expected):
    e = make_experience(world, 'u1')
    go = lambda: _insert_media(ctx, world, f'k/{ctx}.webp', 'u1', e)          # noqa: E731
    if expected:
        go()
        assert all_media_keys() == [f'k/{ctx}.webp']
    else:
        _denied(go)
        assert all_media_keys() == []


def test_un_usuari_no_pot_penjar_mitjans_a_l_experiencia_d_un_altre_ni_amb_el_seu_creator(world):
    e = make_experience(world, 'u2')
    _denied(lambda: _insert_media('own', world, 'k/intrus.webp', 'u1', e))
    assert all_media_keys() == []


def test_un_usuari_no_pot_inserir_a_una_experiencia_inexistent(world):
    import uuid
    e = make_experience(world, 'u1')
    _insert_media('own', world, 'k/ok.webp', 'u1', e)                           # la columna i la taula han d'existir
    def go():
        _insert_media('own', world, 'k/fantasma.webp', 'u1', str(uuid.uuid4()))
    _denied(go)
    assert all_media_keys() == ['k/ok.webp']


def test_l_admin_pot_penjar_a_l_experiencia_d_un_altre_amb_el_seu_creator(world):
    e = make_experience(world, 'u1')
    _insert_media('admin', world, 'k/adm.webp', 'adm', e)
    assert all_media_keys() == ['k/adm.webp']


def test_sense_experience_id_la_politica_es_la_d_abans(world):
    _insert_media('own', world, 'k/foto.webp', 'u1', None)
    _denied(lambda: _insert_media('own', world, 'k/altre.webp', 'u2', None))          # en nom d'un altre
    _denied(lambda: _insert_media('own', world, 'k/hid.webp', 'u1', None, 'hidden_pending_review'))
    assert all_media_keys() == ['k/foto.webp']


def test_un_mitja_d_experiencia_no_visible_no_es_pot_inserir_com_a_usuari(world):
    e = make_experience(world, 'u1')
    _denied(lambda: _insert_media('own', world, 'k/h.webp', 'u1', e, 'hidden_pending_review'))


@pytest.mark.parametrize('ctx,sees', [('anon', False), ('own', True), ('other', False), ('admin', True),
                                      ('system', True)])
def test_select_dels_mitjans_d_experiencia_segueix_la_regla_d_estat(world, ctx, sees):
    e = make_experience(world, 'u1')
    make_exp_media(world, 'u1', e, key='k/h.webp', status='hidden_pending_review')
    make_exp_media(world, 'u1', e, key='k/v.webp', minutes=1)
    got = [r[0] for r in _run(ctx, 'SELECT key FROM refuges.refuge_media ORDER BY key')]
    assert got == (['k/h.webp', 'k/v.webp'] if sees else ['k/v.webp'])
