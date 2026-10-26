"""
Selectors i services de `apps.accounts` (chunk 3). Contracte proposat pels tests (l'implementador pot renomenar-lo
justificant-ho):

selectors
- `get_user(uid) -> UserAccount | None`  (1 consulta; la RLS nomes deixa veure la fila propia, o totes a admin/sistema)

services (excepcions de domini, cap tupla; escriuen amb el context RLS de la peticio, llevat de moderacio/avatar -> D20)
- `create_user(*, uid, username='', language=None, birth_date=None) -> UserAccount`
      `UserAlreadyExists`, `UserUnderage`; crea `users` + `user_public_profiles` en una transaccio; mai desa la data.
- `confirm_age(uid, birth_date)`                -> `UserUnderage`
- `add_favourite(uid, refuge_id)` / `add_visited(uid, refuge_id)`      idempotents; `RefugeNotFound` (inclos id mal format)
- `remove_favourite(uid, refuge_id)` / `remove_visited(uid, refuge_id)`  idempotents; `RefugeNotFound`
- `increment_moderation_strikes(uid) -> int | None`   (dins `system_context()`: D20)
- `set_blocked(uid, blocked=True, reason=None, blocked_at=None) -> bool`   (dins `system_context()`: D20)
- `update_avatar_metadata(uid, metadata: dict) -> bool`   DELETE + INSERT a `user_avatars` (D20); claus de `metadata`:
      `key, uploaded_at (ISO), width, height, blurhash, size, content_type[, thumb_key]` (forma que ja produeix
      `MediaUploadController._publish_avatar`)
"""
import uuid
from datetime import datetime, timezone

import pytest

from apps.accounts.tests.helpers import (
    FAV, VIS, add_list_row, avatar_rows, list_refuge_ids, make_avatar, make_refuge, make_user, profile_row, sql,
    user_row, years_ago)
from apps.core.rls import rls_context, system_context

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.integration, pytest.mark.real_permissions]


@pytest.fixture
def services():
    from apps.accounts import services
    return services


@pytest.fixture
def selectors():
    from apps.accounts import selectors
    return selectors


# ---------- selectors.get_user ----------

def test_get_user_propi_i_inexistent(selectors):
    make_user('u1')
    with rls_context(uid='u1'):
        assert selectors.get_user('u1').uid == 'u1'
        assert selectors.get_user('fantasma') is None


def test_get_user_no_veu_la_fila_d_un_altre(selectors):
    make_user('u1')
    make_user('u2')
    with rls_context(uid='u1'):
        assert selectors.get_user('u2') is None
    with rls_context(uid='adm', is_admin=True):
        assert selectors.get_user('u2').uid == 'u2'


def test_get_user_1_consulta(selectors):
    from apps.accounts.tests.helpers import QueryCounter
    make_user('u1')
    with rls_context(uid='u1'):
        with QueryCounter() as q:
            selectors.get_user('u1')
    assert q.count == 1


# ---------- services.create_user ----------

def test_create_user_desa_usuari_i_perfil_a_la_mateixa_transaccio(services):
    with rls_context(uid='n1'):
        user = services.create_user(uid='n1', username='Nou')
    assert user.uid == 'n1'
    assert user_row('n1')['language'] == 'en'
    assert profile_row('n1')['username'] == 'Nou'


def test_create_user_amb_edat_adulta_desa_nomes_confirmacio_i_llindar(services):
    with rls_context(uid='n1'):
        services.create_user(uid='n1', birth_date=years_ago(30))
    row = user_row('n1')
    assert row['age_threshold'] == 16 and row['age_confirmed_at'] is not None
    assert str(years_ago(30)) not in str(row)               # la data de naixement no es desa mai


def test_create_user_menor_no_desa_res(services):
    with pytest.raises(services.UserUnderage):
        with rls_context(uid='n1'):
            services.create_user(uid='n1', birth_date=years_ago(16, days_offset=1))
    assert user_row('n1') is None and profile_row('n1') is None


def test_create_user_limit_exacte_de_16_anys_es_adult(services):
    with rls_context(uid='n1'):
        services.create_user(uid='n1', birth_date=years_ago(16))
    assert user_row('n1')['age_threshold'] == 16


def test_create_user_duplicat(services):
    make_user('n1', username='Original')
    with pytest.raises(services.UserAlreadyExists):
        with rls_context(uid='n1'):
            services.create_user(uid='n1', username='Altre')
    assert profile_row('n1')['username'] == 'Original'


def test_create_user_idioma_explicit(services):
    with rls_context(uid='n1'):
        services.create_user(uid='n1', language='fr')
    assert user_row('n1')['language'] == 'fr'


# ---------- services.confirm_age ----------

def test_confirm_age(services):
    make_user('u1')
    with rls_context(uid='u1'):
        services.confirm_age('u1', years_ago(40))
    row = user_row('u1')
    assert row['age_threshold'] == 16 and row['age_confirmed_at'] is not None


def test_confirm_age_menor_no_canvia_res(services):
    make_user('u1')
    with pytest.raises(services.UserUnderage):
        with rls_context(uid='u1'):
            services.confirm_age('u1', years_ago(15))
    assert user_row('u1')['age_confirmed_at'] is None


# ---------- preferits / visitats ----------

@pytest.mark.parametrize('kind,add,remove', [(FAV, 'add_favourite', 'remove_favourite'),
                                             (VIS, 'add_visited', 'remove_visited')])
def test_afegir_es_idempotent_i_conserva_la_data_original(services, kind, add, remove):
    make_user('u1')
    r = make_refuge()
    with rls_context(uid='u1'):
        getattr(services, add)('u1', r.pk)
    first = sql('SELECT created_at FROM ' + ('users.user_favourite_refuges' if kind == FAV
                                              else 'users.user_visited_refuges'))
    with rls_context(uid='u1'):
        getattr(services, add)('u1', str(r.pk))             # accepta UUID o string
    assert list_refuge_ids(kind, 'u1') == [r.pk]
    assert sql('SELECT created_at FROM ' + ('users.user_favourite_refuges' if kind == FAV
                                             else 'users.user_visited_refuges')) == first


@pytest.mark.parametrize('add,remove', [('add_favourite', 'remove_favourite'), ('add_visited', 'remove_visited')])
@pytest.mark.parametrize('bad', [uuid.uuid4(), str(uuid.uuid4()), 'garbage', '', '1'])
def test_refugi_inexistent_o_mal_format(services, add, remove, bad):
    make_user('u1')
    with rls_context(uid='u1'):
        with pytest.raises(services.RefugeNotFound):
            getattr(services, add)('u1', bad)
        with pytest.raises(services.RefugeNotFound):
            getattr(services, remove)('u1', bad)


@pytest.mark.parametrize('kind,add,remove', [(FAV, 'add_favourite', 'remove_favourite'),
                                             (VIS, 'add_visited', 'remove_visited')])
def test_treure_es_idempotent_i_nomes_toca_el_propi(services, kind, add, remove):
    make_user('u1')
    make_user('u2')
    r = make_refuge()
    add_list_row(kind, 'u1', r)
    add_list_row(kind, 'u2', r)
    with rls_context(uid='u1'):
        getattr(services, remove)('u1', r.pk)
        getattr(services, remove)('u1', r.pk)               # ja no hi es: sense error
    assert list_refuge_ids(kind, 'u1') == [] and list_refuge_ids(kind, 'u2') == [r.pk]


# ---------- moderacio (D20): escriu a PostgreSQL dins system_context ----------

def test_increment_strikes_des_de_la_peticio_d_un_altre_usuari(services):
    """L'admin/usuari que denuncia no es el creador: el `fn_users_guard` nomes ho permet dins `system_context()`."""
    make_user('creator')
    make_user('adm')
    with rls_context(uid='adm', is_admin=True):
        assert services.increment_moderation_strikes('creator') == 1
        assert services.increment_moderation_strikes('creator') == 2
    assert user_row('creator')['moderation_strikes'] == 2


def test_increment_strikes_usuari_inexistent_retorna_none(services):
    with rls_context(uid='adm', is_admin=True):
        assert services.increment_moderation_strikes('fantasma') is None


def test_set_blocked_i_desbloquejar(services):
    make_user('u1')
    with rls_context(uid='u1'):                                  # fins i tot dins la peticio del propi usuari (hash match)
        assert services.set_blocked('u1', True, reason='moderation_hash_match') is True
    row = user_row('u1')
    assert (row['is_blocked'], row['blocked_reason']) == (True, 'moderation_hash_match')
    # `blocked_at` el posa el rellotge de la BD (decisió del PO, 26/10), no l'aplicació
    db_now = sql('SELECT statement_timestamp()')[0][0]
    assert row['blocked_at'] is not None and abs((db_now - row['blocked_at']).total_seconds()) < 60
    with rls_context(uid='adm', is_admin=True):
        assert services.set_blocked('u1', False) is True
    row = user_row('u1')
    assert (row['is_blocked'], row['blocked_reason'], row['blocked_at']) == (False, None, None)


def test_set_blocked_motiu_invalid_o_usuari_inexistent(services):
    make_user('u1')
    with rls_context(uid='adm', is_admin=True):
        assert services.set_blocked('fantasma', True, reason='strikes') is False
    with pytest.raises(Exception):
        with rls_context(uid='adm', is_admin=True):
            services.set_blocked('u1', True, reason='altre')
    assert user_row('u1')['is_blocked'] is False


def test_les_escriptures_de_moderacio_no_deixen_privilegis_de_sistema(services):
    make_user('u1')
    make_user('u2')
    with rls_context(uid='u2'):
        services.increment_moderation_strikes('u1')
        with system_context():
            pass
        from django.db import DatabaseError, connection, transaction
        with pytest.raises(DatabaseError):
            with transaction.atomic():
                with connection.cursor() as cur:
                    cur.execute('UPDATE users.users SET moderation_strikes = 7 WHERE uid = %s', ['u2'])


# ---------- avatar (D20): DELETE + INSERT ----------

def _meta(**kw):
    base = {'key': 'users-avatars/u1/new.webp', 'width': 256,
            'height': 128, 'blurhash': 'LEHV6nWB2yk8', 'size': 4096, 'content_type': 'image/webp'}
    base.update(kw)
    return base


def test_update_avatar_metadata_insereix_i_mapeja_size(services):
    make_user('u1')
    meta = _meta(thumb_key='users-avatars/u1/new_t.webp', uploaded_at='2001-01-01T00:00:00+00:00')
    with rls_context(uid='u1'):
        assert services.update_avatar_metadata('u1', meta) is True
    rows = sql('SELECT key, thumb_key, content_type, width, height, size_bytes, blurhash, uploaded_at '
               'FROM users.user_avatars WHERE user_uid = %s', ['u1'])
    assert rows[0][:7] == ('users-avatars/u1/new.webp', 'users-avatars/u1/new_t.webp', 'image/webp', 256, 128, 4096,
                           'LEHV6nWB2yk8')
    # `uploaded_at` = rellotge de la BD (el valor de l'aplicació s'ignora) i torna a `metadata` en hora de Madrid
    db_now = sql('SELECT statement_timestamp()')[0][0]
    assert abs((db_now - rows[0][7]).total_seconds()) < 60
    assert datetime.fromisoformat(meta['uploaded_at']) == rows[0][7]
    assert meta['uploaded_at'].endswith(('+01:00', '+02:00'))


def test_update_avatar_metadata_reemplaca_l_antic(services):
    make_user('u1')
    make_avatar('u1', key='users-avatars/u1/old.webp')
    with rls_context(uid='u1'):
        assert services.update_avatar_metadata('u1', _meta()) is True
    assert [r[0] for r in avatar_rows('u1')] == ['users-avatars/u1/new.webp']


def test_update_avatar_metadata_usuari_inexistent(services):
    with rls_context(uid='u1'):
        assert services.update_avatar_metadata('fantasma', _meta()) is False


def test_update_avatar_metadata_bloqueja_la_fila_d_usuari(services):
    """Revisor SQL: `FOR UPDATE` serialitza dues substitucions concurrents de l'avatar."""
    from django.db import connection
    from django.test.utils import CaptureQueriesContext
    make_user('u1')
    with rls_context(uid='u1'), CaptureQueriesContext(connection) as ctx:
        assert services.update_avatar_metadata('u1', _meta()) is True
    assert any('FOR UPDATE' in q['sql'] and 'users"."users' in q['sql'] for q in ctx.captured_queries)
