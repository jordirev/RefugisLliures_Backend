"""
Contracte HTTP dels endpoints d'usuari movits a PostgreSQL (chunk 3), rol `app` + RLS reals:
`POST /users/`, `GET|PATCH|DELETE /users/{uid}/`, `DELETE /users/{uid}/avatar/`, `PATCH /users/{uid}/age-confirmation/`.

Forma JSON: §5.2 (perfil propi complet; perfil d'un altre = `{uid, username, avatar_metadata}`). Firestore queda bloquejat
pel conftest arrel; els comptadors (D19) es mocken.
"""
from unittest.mock import MagicMock, patch

import pytest

from apps.accounts.tests.helpers import (
    MEDIA_ITEM_KEYS, OWN_KEYS, PUBLIC_KEYS, USERS, add_list_row, admin_claims, api_delete, api_get, api_patch,
    api_post, at, avatar_rows, count_all, list_rows, make_avatar, make_media, make_refuge, make_user, profile_row,
    sql, url, user_claims, user_row, years_ago, FAV, VIS, as_owner)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration,
              pytest.mark.real_permissions]

UNDERAGE = {'error': 'underage', 'code': 'underage',
            'message': "Cal tenir 16 anys o més per utilitzar l'aplicació"}


# =================================== POST /users/ ===================================

def test_post_anonim_401(client):
    assert api_post(client, USERS, None, {'username': 'x'}).status_code == 401
    assert count_all('users.users') == 0


def test_post_crea_usuari_i_perfil_amb_forma_del_contracte(client):
    r = api_post(client, USERS, user_claims('n1'), {'username': 'Anna', 'language': 'es'})
    assert r.status_code == 201, r.content
    data = r.json()
    assert set(data) == OWN_KEYS
    assert data['uid'] == 'n1' and data['username'] == 'Anna' and data['language'] == 'es'
    assert data['favourite_refuges'] == [] and data['visited_refuges'] == [] and data['uploaded_photos_keys'] == []
    assert (data['num_shared_experiences'], data['num_renovated_refuges']) == (0, 0)
    assert data['avatar_metadata'] is None and data['age_confirmed'] is False
    assert data['created_at'] and data['created_at'][-6] in '+-'          # ISO amb offset de Madrid
    assert user_row('n1')['language'] == 'es' and profile_row('n1')['username'] == 'Anna'


def test_post_no_exposa_camps_de_moderacio_ni_d_edat_interns(client):
    resp = api_post(client, USERS, user_claims('n1'), {})
    assert resp.status_code == 201
    body = resp.content.decode()
    for leaked in ('moderation_strikes', 'is_blocked', 'age_threshold', 'age_confirmed_at', 'blocked_'):
        assert leaked not in body


def test_post_idioma_per_defecte_en_i_username_buit(client):
    """§12 #11: sense `language` el valor per defecte passa de 'ca' a 'en'."""
    r = api_post(client, USERS, user_claims('n1'), {})
    assert r.status_code == 201
    assert r.json()['language'] == 'en' and r.json()['username'] == ''
    assert user_row('n1')['language'] == 'en'


def test_post_idioma_es_valida_contra_el_cataleg_de_la_bd(client, AM):
    assert api_post(client, USERS, user_claims('n1'), {'language': 'pt'}).status_code == 400
    with as_owner():
        AM.Language.objects.create(code='pt')
    assert api_post(client, USERS, user_claims('n1'), {'language': 'pt'}).status_code == 201


def test_post_normalitza_idioma_i_username(client):
    r = api_post(client, USERS, user_claims('n1'), {'username': '  Anna ', 'language': 'FR '})
    assert r.status_code == 201
    assert (r.json()['username'], r.json()['language']) == ('Anna', 'fr')


def test_post_usa_l_uid_del_token_i_ignora_camps_perillosos_del_cos(client):
    r = api_post(client, USERS, user_claims('n1'), {
        'uid': 'altre', 'is_blocked': True, 'moderation_strikes': 4, 'age_confirmed_at': '2020-01-01',
        'age_threshold': 18, 'blocked_reason': 'strikes'})
    assert r.status_code == 201
    assert user_row('altre') is None
    row = user_row('n1')
    assert (row['moderation_strikes'], row['is_blocked'], row['age_threshold'], row['blocked_reason']) == \
           (0, False, None, None)


@pytest.mark.parametrize('body,field', [
    ({'username': 'a'}, 'username'), ({'username': 'x' * 256}, 'username'), ({'language': 'xx'}, 'language'),
    ({'birth_date': '2999-01-01'}, 'birth_date'), ({'birth_date': '1800-01-01'}, 'birth_date'),
    ({'birth_date': 'ahir'}, 'birth_date')])
def test_post_dades_invalides_400(client, body, field):
    r = api_post(client, USERS, user_claims('n1'), body)
    assert r.status_code == 400
    assert r.json()['error'] == 'Dades invàlides' and field in r.json()['details']
    assert user_row('n1') is None


def test_post_menor_d_edat_403_i_no_es_desa_res(client):
    r = api_post(client, USERS, user_claims('kid'), {'username': 'kid', 'birth_date': years_ago(16, 1).isoformat()})
    assert r.status_code == 403 and r.json() == UNDERAGE
    assert user_row('kid') is None and profile_row('kid') is None


def test_post_adult_confirma_l_edat_i_no_desa_la_data_de_naixement(client):
    born = years_ago(16)
    r = api_post(client, USERS, user_claims('n1'), {'username': 'adult', 'birth_date': born.isoformat()})
    assert r.status_code == 201 and r.json()['age_confirmed'] is True
    row = user_row('n1')
    assert row['age_threshold'] == 16 and row['age_confirmed_at'] is not None
    assert born.isoformat() not in r.content.decode()
    assert str(born) not in str(row)


def test_post_sense_birth_date_no_confirma_l_edat(client):
    r = api_post(client, USERS, user_claims('n1'), {'username': 'google'})
    assert r.json()['age_confirmed'] is False
    assert user_row('n1')['age_confirmed_at'] is None


def test_post_duplicat_409_i_no_modifica_l_original(client):
    make_user('n1', username='Original', language_id='ca')
    r = api_post(client, USERS, user_claims('n1'), {'username': 'Altre', 'language': 'fr'})
    assert r.status_code == 409 and 'ja existeix' in r.json()['error']
    assert profile_row('n1')['username'] == 'Original' and user_row('n1')['language'] == 'ca'


def test_post_es_atomic_si_el_perfil_no_es_pot_crear(client):
    """Un perfil orfe preexistent fa fallar el segon INSERT: no ha de quedar la fila de `users` (una transaccio)."""
    sql('INSERT INTO users.user_public_profiles (uid, username) VALUES (%s, %s)', ['ghost', 'orfe'])
    try:
        r = api_post(client, USERS, user_claims('ghost'), {'username': 'Nou'})
        assert r.status_code in (409, 500)
        assert user_row('ghost') is None
        if r.status_code == 500:
            assert set(r.json()) == {'error', 'error_id'}
    finally:
        with as_owner():
            from django.db import connection
            with connection.cursor() as cur:
                cur.execute("DELETE FROM users.user_public_profiles WHERE uid = 'ghost'")


# =================================== GET /users/{uid}/ ===================================

def test_get_anonim_401(client):
    make_user('u1')
    assert api_get(client, url('u1')).status_code == 401


def test_get_propi_forma_completa_i_valors(client, RM, legacy_counts):
    legacy_counts.return_value = {'num_shared_experiences': 3, 'num_renovated_refuges': 2}
    from datetime import datetime, timezone
    make_user('u1', username='Anna', language_id='ca', created_at=datetime(2025, 1, 15, 10, 0, tzinfo=timezone.utc),
              age_confirmed_at=at(0), age_threshold=16)
    r1, r2, r3 = make_refuge(name='A'), make_refuge(name='B', lat=43), make_refuge(name='C', lat=44)
    add_list_row(FAV, 'u1', r2, 2)
    add_list_row(FAV, 'u1', r1, 1)
    add_list_row(VIS, 'u1', r3, 5)
    add_list_row(VIS, 'u1', r1, 4)
    make_media(r1, 'u1', key='k/b.webp', minutes=2)
    make_media(r2, 'u1', key='k/a.webp', minutes=2, status='removed')           # tots els estats compten (§4)
    make_media(r1, 'u1', key='k/c.webp', minutes=1)
    make_media(r1, 'u2', key='k/other.webp', minutes=0)                         # d'un altre: no surt
    make_user('u2')
    data = api_get(client, url('u1'), user_claims('u1')).json()
    assert set(data) == OWN_KEYS
    assert (data['uid'], data['username'], data['language']) == ('u1', 'Anna', 'ca')
    assert data['favourite_refuges'] == [str(r2.pk), str(r1.pk)]                 # més recent primer (created_at DESC)
    assert data['visited_refuges'] == [str(r3.pk), str(r1.pk)]
    assert data['uploaded_photos_keys'] == ['k/b.webp', 'k/a.webp', 'k/c.webp']        # (uploaded_at DESC, key DESC)
    assert (data['num_shared_experiences'], data['num_renovated_refuges']) == (3, 2)
    assert data['age_confirmed'] is True
    assert data['created_at'] == '2025-01-15T11:00:00+01:00'                      # Europe/Madrid
    assert data['avatar_metadata'] is None


def test_get_propi_photo_keys_ordenades_per_uploaded_at_i_key(client):
    make_user('u1')
    r = make_refuge()
    make_media(r, 'u1', key='k/z.webp', minutes=1)
    make_media(r, 'u1', key='k/b.webp', minutes=2)
    make_media(r, 'u1', key='k/a.webp', minutes=2)
    data = api_get(client, url('u1'), user_claims('u1')).json()
    assert data['uploaded_photos_keys'] == ['k/z.webp', 'k/a.webp', 'k/b.webp']


def test_get_propi_amb_avatar_en_forma_media_item(client):
    make_user('u1')
    make_avatar('u1', key='users-avatars/u1/a.webp', thumb_key='users-avatars/u1/a_t.webp', width=64, height=32,
                blurhash='LEHV', size_bytes=100)
    av = api_get(client, url('u1'), user_claims('u1')).json()['avatar_metadata']
    assert set(av) == MEDIA_ITEM_KEYS
    assert av['key'] == 'users-avatars/u1/a.webp' and av['creator_uid'] == 'u1'
    assert av['url'] == 'https://r2.test/users-avatars/u1/a.webp?sig=1'
    assert av['thumb_url'] == 'https://r2.test/users-avatars/u1/a_t.webp?sig=1'
    assert (av['width'], av['height'], av['blurhash'], av['media_type']) == (64, 32, 'LEHV', 'image')
    assert av['uploaded_at'] and av['taken_at'] is None and av['experience_id'] is None


def test_get_avatar_sense_miniatura_usa_la_url_principal(client):
    make_user('u1')
    make_avatar('u1', key='users-avatars/u1/a.webp')
    av = api_get(client, url('u1'), user_claims('u1')).json()['avatar_metadata']
    assert av['thumb_url'] == av['url']


def test_get_altre_usuari_nomes_uid_username_i_avatar(client):
    make_user('u1')
    make_user('u2', username='Bernat', language_id='fr')
    r = make_refuge()
    add_list_row(FAV, 'u2', r)
    add_list_row(VIS, 'u2', r)
    make_media(r, 'u2', key='k/x.webp')
    make_avatar('u2', key='users-avatars/u2/a.webp')
    r_ = api_get(client, url('u2'), user_claims('u1'))
    assert r_.status_code == 200
    data = r_.json()
    assert set(data) == PUBLIC_KEYS
    assert (data['uid'], data['username']) == ('u2', 'Bernat')
    assert set(data['avatar_metadata']) == MEDIA_ITEM_KEYS
    body = r_.content.decode()
    # (`uploaded_at` és de l'avatar, un MediaItem: el que no ha de sortir és `uploaded_photos_keys`)
    for leaked in ('language', 'favourite', 'visited', 'uploaded_photos', 'created_at', 'age_confirmed', 'num_'):
        assert leaked not in body


def test_get_altre_usuari_sense_avatar(client):
    make_user('u1')
    make_user('u2', username='Bo')
    assert api_get(client, url('u2'), user_claims('u1')).json() == {'uid': 'u2', 'username': 'Bo',
                                                                    'avatar_metadata': None}


def test_get_altre_usuari_com_a_admin_tambe_es_reduit(client):
    make_user('adm')
    make_user('u2', username='Bo')
    assert set(api_get(client, url('u2'), admin_claims('adm')).json()) == PUBLIC_KEYS


def test_get_usuari_inexistent_404(client):
    make_user('u1')
    r = api_get(client, url('fantasma'), user_claims('u1'))
    assert r.status_code == 404 and 'no trobat' in r.json()['error']


def test_get_no_consulta_firestore_per_a_un_perfil_aliè(client, legacy_counts):
    make_user('u1')
    make_user('u2')
    assert api_get(client, url('u2'), user_claims('u1')).status_code == 200
    legacy_counts.assert_not_called()


# =================================== PATCH /users/{uid}/ ===================================

def test_patch_username_no_reseteja_l_idioma(client):
    """TECH_DEBT M1: el PATCH d'usuari resetejava `language` a 'ca'."""
    make_user('u1', username='Vell', language_id='fr')
    r = api_patch(client, url('u1'), user_claims('u1'), {'username': 'Nou'})
    assert r.status_code == 200
    assert (r.json()['username'], r.json()['language']) == ('Nou', 'fr')
    assert user_row('u1')['language'] == 'fr' and profile_row('u1')['username'] == 'Nou'


def test_patch_idioma_no_toca_el_username(client):
    make_user('u1', username='Anna', language_id='fr')
    r = api_patch(client, url('u1'), user_claims('u1'), {'language': 'ES'})
    assert r.status_code == 200 and r.json()['language'] == 'es' and r.json()['username'] == 'Anna'


def test_patch_resposta_te_la_forma_del_perfil_propi(client):
    make_user('u1')
    assert set(api_patch(client, url('u1'), user_claims('u1'), {'username': 'Anna'}).json()) == OWN_KEYS


def test_patch_username_buit_es_permes(client):
    make_user('u1', username='Anna')
    r = api_patch(client, url('u1'), user_claims('u1'), {'username': ''})
    assert r.status_code == 200 and r.json()['username'] == ''


def test_patch_sense_cap_camp_400(client):
    """M1: el «almenys un camp» mai fallava."""
    make_user('u1')
    for body in ({}, {'is_blocked': True}, {'unknown': 1}):
        r = api_patch(client, url('u1'), user_claims('u1'), body)
        assert r.status_code == 400 and r.json()['error'] == 'Dades invàlides', body


@pytest.mark.parametrize('body,field', [({'username': 'a'}, 'username'), ({'language': 'xx'}, 'language'),
                                        ({'username': 'x' * 256}, 'username')])
def test_patch_invalid_400(client, body, field):
    make_user('u1', username='Anna', language_id='ca')
    r = api_patch(client, url('u1'), user_claims('u1'), body)
    assert r.status_code == 400 and field in r.json()['details']
    assert profile_row('u1')['username'] == 'Anna' and user_row('u1')['language'] == 'ca'


def test_patch_no_permet_canviar_moderacio_ni_edat_ni_uid(client):
    make_user('u1')
    r = api_patch(client, url('u1'), user_claims('u1'), {
        'username': 'ok', 'is_blocked': True, 'moderation_strikes': 5, 'age_confirmed': True, 'uid': 'x',
        'age_threshold': 18, 'blocked_reason': 'strikes'})
    assert r.status_code == 200
    row = user_row('u1')
    assert (row['is_blocked'], row['moderation_strikes'], row['age_threshold'], row['blocked_reason']) == \
           (False, 0, None, None)
    assert user_row('x') is None


def test_patch_actualitza_updated_at_del_perfil(client):
    make_user('u1')
    sql("UPDATE users.user_public_profiles SET updated_at = %s WHERE uid = 'u1'", [at(0)])
    api_patch(client, url('u1'), user_claims('u1'), {'username': 'Nou'})
    assert profile_row('u1')['updated_at'] > at(0)


def test_patch_trim_del_username(client):
    make_user('u1')
    assert api_patch(client, url('u1'), user_claims('u1'), {'username': '  Anna '}).json()['username'] == 'Anna'


@pytest.mark.parametrize('claims', [user_claims('u2'), admin_claims('adm')])
def test_patch_d_un_altre_403_tambe_per_a_admin(client, claims):
    make_user('u1', username='Anna')
    make_user(claims['uid'])
    r = api_patch(client, url('u1'), claims, {'username': 'Hack'})
    assert r.status_code == 403
    assert profile_row('u1')['username'] == 'Anna'


def test_patch_anonim_401(client):
    make_user('u1')
    assert api_patch(client, url('u1'), None, {'username': 'x'}).status_code == 401


# =================================== DELETE /users/{uid}/ ===================================
# Els tests de l'esborrat d'usuari (D42) són a `test_user_deletion_procedure.py`. Aquí només queden els de `POST /users/`
# relacionats amb el compte de Firebase esborrat (U7).

def test_post_amb_token_d_un_compte_de_firebase_esborrat_401_i_no_crea_res(client, firebase_accounts):
    """U7: amb el token encara vigent (fins a 1 h) no es pot recrear el mateix UID sense el bloqueig."""
    from firebase_admin import auth
    firebase_accounts.get_user.side_effect = auth.UserNotFoundError('esborrat')
    resp = api_post(client, USERS, user_claims('n1'), {'username': 'Anna'})
    assert resp.status_code == 401
    assert resp.json()['code'] == 'account_not_found'
    assert count_all('users.users') == 0 and count_all('users.user_public_profiles') == 0


def test_post_si_firebase_falla_en_comprovar_el_compte_500_sense_detalls(client, firebase_accounts):
    firebase_accounts.get_user.side_effect = RuntimeError('timeout amb host intern')
    resp = api_post(client, USERS, user_claims('n1'), {})
    assert resp.status_code == 500 and 'timeout' not in resp.content.decode()
    assert count_all('users.users') == 0


# =================================== DELETE /users/{uid}/avatar/ ===================================

def test_delete_avatar_204_esborra_la_fila_i_els_dos_fitxers_de_r2(client, r2):
    make_user('u1')
    make_avatar('u1', key='users-avatars/u1/a.webp', thumb_key='users-avatars/u1/a_t.webp')
    resp = api_delete(client, url('u1', 'avatar'), user_claims('u1'))
    assert resp.status_code == 204
    assert avatar_rows('u1') == []
    deleted = {c.args[0] for c in r2.delete_file.call_args_list}
    assert deleted == {'users-avatars/u1/a.webp', 'users-avatars/u1/a_t.webp'}
    assert api_get(client, url('u1'), user_claims('u1')).json()['avatar_metadata'] is None


def test_delete_avatar_sense_avatar_404(client, r2):
    make_user('u1')
    r = api_delete(client, url('u1', 'avatar'), user_claims('u1'))
    assert r.status_code == 404 and 'no té cap avatar' in r.json()['error']
    r2.delete_file.assert_not_called()


def test_delete_avatar_si_r2_falla_500_i_es_conserva_la_fila(client, r2):
    make_user('u1')
    make_avatar('u1', key='users-avatars/u1/a.webp')
    r2.delete_file.return_value = False
    r = api_delete(client, url('u1', 'avatar'), user_claims('u1'))
    assert r.status_code == 500 and set(r.json()) == {'error', 'error_id'}
    assert [k for k, _ in avatar_rows('u1')] == ['users-avatars/u1/a.webp']


def test_delete_avatar_si_r2_llanca_excepcio_500_sense_filtrar_detalls(client, r2):
    make_user('u1')
    make_avatar('u1', key='users-avatars/u1/a.webp')
    r2.delete_file.side_effect = RuntimeError('bucket secret-bucket host r2.internal')
    r = api_delete(client, url('u1', 'avatar'), user_claims('u1'))
    assert r.status_code == 500 and 'secret-bucket' not in r.content.decode()
    assert len(avatar_rows('u1')) == 1


def test_delete_avatar_miniatura_orfa_nomes_avisa(client, r2):
    make_user('u1')
    make_avatar('u1', key='users-avatars/u1/a.webp', thumb_key='users-avatars/u1/a_t.webp')
    r2.delete_file.side_effect = lambda key: not key.endswith('_t.webp')
    assert api_delete(client, url('u1', 'avatar'), user_claims('u1')).status_code == 204
    assert avatar_rows('u1') == []


@pytest.mark.parametrize('claims', [user_claims('u2'), admin_claims('adm')])
def test_delete_avatar_d_un_altre_403(client, claims, r2):
    make_user('u1')
    make_user(claims['uid'])
    make_avatar('u1')
    assert api_delete(client, url('u1', 'avatar'), claims).status_code == 403
    assert len(avatar_rows('u1')) == 1
    r2.delete_file.assert_not_called()


def test_delete_avatar_anonim_401(client):
    make_user('u1')
    assert api_delete(client, url('u1', 'avatar')).status_code == 401


# =================================== PATCH /users/{uid}/age-confirmation/ ===================================

def test_age_confirmation_adult_200_i_perfil_propi(client, _mock_audit_log):
    make_user('u1')
    r = api_patch(client, url('u1', 'age-confirmation'), user_claims('u1'), {'birth_date': years_ago(30).isoformat()})
    assert r.status_code == 200
    assert set(r.json()) == OWN_KEYS and r.json()['age_confirmed'] is True
    row = user_row('u1')
    assert row['age_threshold'] == 16 and row['age_confirmed_at'] is not None
    assert years_ago(30).isoformat() not in r.content.decode() and str(years_ago(30)) not in str(row)
    args = _mock_audit_log.call_args.args
    assert args[0] == 'u1' and args[2:4] == ('user', 'u1') and args[4] == {'age_threshold': 16}


def test_age_confirmation_menor_403_underage_i_no_canvia_res(client):
    make_user('u1')
    r = api_patch(client, url('u1', 'age-confirmation'), user_claims('u1'),
                  {'birth_date': years_ago(15).isoformat()})
    assert r.status_code == 403 and r.json() == UNDERAGE
    assert user_row('u1')['age_confirmed_at'] is None


def test_age_confirmation_limit_de_16_anys_exactes(client):
    make_user('u1')
    assert api_patch(client, url('u1', 'age-confirmation'), user_claims('u1'),
                     {'birth_date': years_ago(16).isoformat()}).status_code == 200
    make_user('u2')
    assert api_patch(client, url('u2', 'age-confirmation'), user_claims('u2'),
                     {'birth_date': years_ago(16, 1).isoformat()}).status_code == 403


@pytest.mark.parametrize('body', [{}, {'birth_date': '2999-01-01'}, {'birth_date': '1800-01-01'},
                                  {'birth_date': '01/01/1990'}, {'birth_date': ''}])
def test_age_confirmation_dades_invalides_400(client, body):
    make_user('u1')
    r = api_patch(client, url('u1', 'age-confirmation'), user_claims('u1'), body)
    assert r.status_code == 400 and 'birth_date' in r.json()['details']


def test_age_confirmation_repetida_es_idempotent(client):
    make_user('u1', age_confirmed_at=at(0), age_threshold=16)
    r = api_patch(client, url('u1', 'age-confirmation'), user_claims('u1'), {'birth_date': years_ago(40).isoformat()})
    assert r.status_code == 200 and user_row('u1')['age_confirmed_at'] > at(0)


@pytest.mark.parametrize('claims', [user_claims('u2'), admin_claims('adm')])
def test_age_confirmation_d_un_altre_403(client, claims):
    make_user('u1')
    make_user(claims['uid'])
    r = api_patch(client, url('u1', 'age-confirmation'), claims, {'birth_date': years_ago(30).isoformat()})
    assert r.status_code == 403 and user_row('u1')['age_confirmed_at'] is None


def test_age_confirmation_anonim_401(client):
    make_user('u1')
    assert api_patch(client, url('u1', 'age-confirmation'), None,
                     {'birth_date': years_ago(30).isoformat()}).status_code == 401
