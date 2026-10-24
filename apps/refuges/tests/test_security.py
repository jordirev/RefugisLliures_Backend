"""
Revisió de seguretat del chunk 2 (refugis): permisos de les vistes, IDOR de claus R2, injecció, grants/RLS provats amb
el rol `app`, filtracions a respostes i logs i context de RLS local a la transacció.
"""
import logging
import re
from unittest.mock import patch

import pytest
from django.db import DatabaseError, connection, transaction

from apps.core.rls import rls_context
from apps.refuges import views
from apps.refuges.tests.helpers import (
    VERIFY, admin_claims, api_delete, api_get, make_media, make_refuge, make_user, user_claims)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.integration]

URL = '/api/refuges/'


def _one(sql, params=None, conn=None):
    with (conn or connection).cursor() as cur:
        cur.execute(sql, params or [])
        return cur.fetchone()[0]


def _denied(stmt):
    with pytest.raises(DatabaseError):
        with transaction.atomic():
            with connection.cursor() as cur:
                cur.execute(stmt)


# ---------- permission_classes explícits (el default global és AllowAny) ----------

@pytest.mark.views
@pytest.mark.parametrize('view,perm', [
    (views.RefugeCollectionAPIView, 'AllowAny'),
    (views.RefugeDetailAPIView, 'AllowAny'),
    (views.RefugeMediaListAPIView, 'IsAuthenticated'),
    (views.RefugeMediaDetailAPIView, 'IsAuthenticated'),
])
def test_permission_classes_de_cada_vista(view, perm):
    assert [p.__name__ for p in view.permission_classes] == [perm]
    assert 'permission_classes' in vars(view), 'declarada a la vista, no heretada del default global'


@pytest.mark.views
@pytest.mark.parametrize('method', ['post', 'put', 'patch', 'delete'])
@pytest.mark.parametrize('claims', [None, 'user', 'admin'])
def test_no_hi_ha_escriptura_sobre_el_cataleg_per_http(client, method, claims):
    """Cap endpoint no escriu refugis: POST/PUT/PATCH/DELETE sobre col·lecció i detall no són 2xx ni canvien res."""
    r = make_refuge('Intacte')
    tok = {'user': user_claims('u1'), 'admin': admin_claims()}.get(claims)
    for path in (URL, f'{URL}{r.pk}/'):
        kw = {'HTTP_AUTHORIZATION': 'Bearer t'} if tok else {}
        with patch(VERIFY, return_value=tok):
            resp = getattr(client, method)(path, data='{"name":"X"}', content_type='application/json', **kw)
        assert resp.status_code in (401, 403, 405), (method, path, resp.status_code)
    assert api_get(client, f'{URL}{r.pk}/').json()['name'] == 'Intacte'


# ---------- IDOR / claus R2 ----------

@pytest.fixture
def two_refuges(RM):
    make_user('u1')
    make_user('u2')
    return make_refuge('A', lat=42.1), make_refuge('B', lat=42.2)


def _exists(RM, key):
    with rls_context(system=True):
        return RM.RefugeMedia.objects.filter(pk=key).exists()


@pytest.mark.views
@pytest.mark.parametrize('who', ['u1', 'u2', 'adm'])
def test_no_es_pot_esborrar_un_mitja_amb_l_id_d_un_altre_refugi(client, RM, two_refuges, who):
    a, b = two_refuges
    key = f'refugis-lliures/{a.pk}/x.webp'
    make_media(a, 'u1', key=key)
    claims = admin_claims() if who == 'adm' else user_claims(who)
    r = api_delete(client, f'{URL}{b.pk}/media/{key}/', claims)
    assert r.status_code in (403, 404)
    assert _exists(RM, key)


@pytest.mark.views
@pytest.mark.parametrize('attack', [
    '../{a}/x.webp', '..%2F{a}%2Fx.webp', '%2e%2e/{a}/x.webp', 'refugis-lliures/{a}/../{a}/x.webp',
    'refugis-lliures/{a}/x.webp%00', 'refugis-lliures/{a}/x.webp/..', '/refugis-lliures/{a}/x.webp',
    'refugis-lliures/{a}/*', "refugis-lliures/{a}/x.webp' OR '1'='1"])
def test_claus_amb_traversal_o_codificades_no_esborren_res(client, RM, two_refuges, attack):
    a, _ = two_refuges
    key = f'refugis-lliures/{a.pk}/x.webp'
    make_media(a, 'u1', key=key)
    r = api_delete(client, f'{URL}{a.pk}/media/{attack.format(a=a.pk)}/', admin_claims())
    assert r.status_code in (400, 404), r.status_code
    assert _exists(RM, key)


@pytest.mark.views
def test_la_clau_es_decodifica_una_sola_vegada(client, RM, two_refuges):
    """Doble decodificació (`unquote` sobre un path que Django ja ha decodificat): `%2561` no ha de ser un àlies de `a`."""
    a, _ = two_refuges
    key = f'refugis-lliures/{a.pk}/a.webp'
    make_media(a, 'u1', key=key)
    r = api_delete(client, f'{URL}{a.pk}/media/refugis-lliures/{a.pk}/%2561.webp/', admin_claims())
    assert r.status_code == 404
    assert _exists(RM, key)


@pytest.mark.views
def test_la_clau_de_la_miniatura_no_serveix_per_esborrar_el_mitja(client, RM, two_refuges):
    a, _ = two_refuges
    key = f'refugis-lliures/{a.pk}/m.webp'
    make_media(a, 'u1', key=key, thumb_key=f'refugis-lliures/{a.pk}/m_thumb.webp')
    r = api_delete(client, f'{URL}{a.pk}/media/refugis-lliures/{a.pk}/m_thumb.webp/', user_claims('u1'))
    assert r.status_code == 403
    assert _exists(RM, key)


@pytest.mark.views
def test_mitja_ocult_d_un_tercer_es_indistingible_d_un_inexistent(client, RM, two_refuges):
    a, _ = two_refuges
    hidden = f'refugis-lliures/{a.pk}/h.webp'
    make_media(a, 'u1', key=hidden, status='hidden_pending_review')
    r1 = api_delete(client, f'{URL}{a.pk}/media/{hidden}/', user_claims('u2'))
    r2 = api_delete(client, f'{URL}{a.pk}/media/refugis-lliures/{a.pk}/no-existeix.webp/', user_claims('u2'))
    assert (r1.status_code, r1.json()) == (r2.status_code, r2.json())
    assert _exists(RM, hidden)


@pytest.mark.views
def test_el_403_d_un_mitja_alie_no_porta_l_uid_de_l_autor(client, RM, two_refuges):
    a, _ = two_refuges
    key = f'refugis-lliures/{a.pk}/v.webp'
    make_media(a, 'u1', key=key)
    r = api_delete(client, f'{URL}{a.pk}/media/{key}/', user_claims('u2'))
    assert r.status_code == 403 and 'u1' not in r.content.decode()
    assert _exists(RM, key)


# ---------- Injecció SQL i paràmetres ----------

@pytest.mark.views
@pytest.mark.parametrize('qs', [
    "name=%27%29%3B%20DROP%20TABLE%20refuges.refuges%3B--", 'name=%5C%27', 'name=%25%5F', 'name=a%00b',
    "type=non gardé' OR '1'='1", 'condition=1;SELECT 1', 'condition=1%20OR%201=1', 'places_min=1;DROP',
    'altitude_max=1%20OR%201=1'])
def test_parametres_de_cerca_no_s_injecten(client, RM, qs):
    make_refuge('Normal')
    r = api_get(client, f'{URL}?{qs}')
    assert r.status_code in (200, 400), r.content[:200]
    if r.status_code == 200:
        assert r.json()['count'] == 0
    assert api_get(client, URL).json()['count'] == 1


@pytest.mark.views
def test_la_cerca_no_formata_cadenes_dins_del_sql(client, RM):
    """El valor de `name` viatja com a paràmetre: no apareix dins del text SQL."""
    make_refuge('Normal')
    seen = []

    def spy(execute, sql, params, many, context):
        seen.append((sql, params))
        return execute(sql, params, many, context)

    with connection.execute_wrapper(spy):
        api_get(client, URL + '?name=ZZsentinella99&type=orri&condition=1&places_min=3')
    assert seen and all('ZZsentinella99' not in str(sql) for sql, _ in seen)
    assert any('ZZsentinella99' in str(params) for _, params in seen)


@pytest.mark.views
@pytest.mark.parametrize('qs', ['places_min=99999999999', 'places_max=99999999999', 'altitude_min=99999999999'])
def test_enters_enormes_no_provoquen_un_500(client, RM, qs):
    """`places_*` no té `max_value`: un enter > int32 arriba a Postgres («integer out of range») i fa 500."""
    make_refuge('Normal')
    assert api_get(client, f'{URL}?{qs}').status_code in (200, 400)


@pytest.mark.views
def test_ids_de_ruta_mal_formats_no_arriben_al_sql(client, RM):
    for bad in ("1' OR '1'='1", '%00', '..', 'a' * 5000):
        assert api_get(client, f'{URL}{bad}/').status_code == 404
        assert api_get(client, f'{URL}{bad}/media/', user_claims('u1')).status_code == 404


# ---------- Dades personals a respostes ----------

@pytest.mark.views
def test_visitors_i_surname_mai_a_les_respostes_dels_no_admins(client, RM):
    r = make_refuge('R', surname='Alies')
    make_user('u1')
    make_media(r, 'u1')
    for claims in (None, user_claims('u1'), user_claims('u2')):
        body = api_get(client, f'{URL}{r.pk}/?visitors=1', claims).content.decode()
        assert '"visitors"' not in body and 'Alies' not in body
        lst = api_get(client, f'{URL}?name=Alies&visitors=1', claims).content.decode()
        assert '"visitors"' not in lst and 'surname' not in lst


@pytest.mark.views
def test_anonim_no_rep_cap_mitja_ni_url_prefirmada(client, RM):
    r = make_refuge('R')
    make_user('u1')
    make_media(r, 'u1')
    for path in (f'{URL}{r.pk}/', f'{URL}?name=R'):
        body = api_get(client, path).content.decode()
        assert 'sig=' not in body and 'creator_uid' not in body and 'images_metadata' not in body


@pytest.mark.views
def test_un_rol_amb_majuscules_o_espais_no_es_admin(client, RM):
    r = make_refuge('R')
    for role in ('Admin', 'ADMIN', 'admin ', ['admin'], True):
        body = api_get(client, f'{URL}{r.pk}/', {'uid': 'x', 'role': role}).json()
        assert 'visitors' not in body


# ---------- Errors i logs ----------

@pytest.mark.views
def test_errors_de_r2_i_presign_no_filtren_secrets_ni_a_la_resposta_ni_al_missatge_del_log(client, RM, caplog):
    from api.services.r2_media_service import R2MediaService
    r = make_refuge('R')
    make_user('u1')
    key = f'refugis-lliures/{r.pk}/s.webp'
    make_media(r, 'u1', key=key)
    boom = RuntimeError('bucket=secret-bucket host=r2.cloudflarestorage.com AKIA123 password=hunter2')
    with caplog.at_level(logging.ERROR), \
            patch.object(R2MediaService, 'generate_presigned_url', side_effect=boom), \
            patch.object(R2MediaService, 'delete_file', side_effect=boom):
        for resp in (api_get(client, f'{URL}{r.pk}/media/', user_claims('u1')),
                     api_get(client, f'{URL}{r.pk}/', user_claims('u1')),
                     api_delete(client, f'{URL}{r.pk}/media/{key}/', user_claims('u1'))):
            assert resp.status_code == 500
            text = resp.content.decode()
            assert 'error_id' in text
            for secret in ('secret-bucket', 'cloudflare', 'AKIA', 'hunter2', 'RuntimeError', 'Traceback'):
                assert secret not in text
    assert 'hunter2' not in ' '.join(rec.getMessage() for rec in caplog.records)


@pytest.mark.views
def test_el_log_no_porta_urls_prefirmades(client, RM, caplog):
    r = make_refuge('R')
    make_user('u1')
    key = f'refugis-lliures/{r.pk}/s.webp'
    make_media(r, 'u1', key=key, thumb_key=f'refugis-lliures/{r.pk}/s_t.webp')
    with caplog.at_level(logging.DEBUG):
        api_get(client, f'{URL}{r.pk}/media/', user_claims('u1'))
        api_delete(client, f'{URL}{r.pk}/media/{key}/', user_claims('u1'))
    assert not re.search(r'sig=|X-Amz-Signature', caplog.text)


# ---------- Grants i rol `app` ----------

@pytest.mark.parametrize('attr', ['rolsuper', 'rolbypassrls', 'rolcreatedb', 'rolcreaterole', 'rolreplication'])
def test_app_no_te_atributs_privilegiats(attr):
    assert _one('SELECT current_user') == 'app'
    assert _one(f"SELECT {attr} FROM pg_roles WHERE rolname = current_user") is False


@pytest.mark.parametrize('schema', ['public', 'core', 'refuges', 'users'])
def test_app_no_pot_crear_objectes_als_schemas(schema):
    assert _one("SELECT has_schema_privilege('app', %s, 'CREATE')", [schema]) is False


def test_app_no_pot_assumir_el_rol_migrator_i_no_es_propietari_de_res():
    _denied('SET LOCAL ROLE migrator')
    owners = {_one("SELECT tableowner FROM pg_tables WHERE schemaname||'.'||tablename = %s", [t])
              for t in ('refuges.refuges', 'refuges.refuge_media', 'users.users', 'users.user_public_profiles')}
    assert owners == {'migrator'}


@pytest.mark.parametrize('stmt', [
    'TRUNCATE refuges.refuges', 'DROP TABLE refuges.refuges',
    'ALTER TABLE refuges.refuges DISABLE ROW LEVEL SECURITY', 'CREATE TABLE public.hack (a int)',
    'DROP POLICY refuges_select ON refuges.refuges',
    'CREATE OR REPLACE FUNCTION core.is_admin() RETURNS boolean LANGUAGE sql AS $$ SELECT true $$',
    "UPDATE refuges.refuge_map SET name = 'x'", 'DELETE FROM refuges.refuge_map'])
def test_app_no_pot_fer_ddl_ni_truncate_ni_escriure_a_la_vista(stmt):
    _denied(stmt)


def test_public_no_te_privilegis_sobre_taules_ni_funcions_de_domini():
    assert _one("""SELECT count(*) FROM information_schema.role_table_grants
                   WHERE grantee = 'PUBLIC' AND table_schema IN ('core', 'refuges', 'users')""") == 0
    assert _one("""SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
                   CROSS JOIN LATERAL aclexplode(COALESCE(p.proacl, acldefault('f', p.proowner))) a
                   WHERE n.nspname IN ('core', 'users', 'refuges') AND a.grantee = 0
                     AND a.privilege_type = 'EXECUTE'""") == 0


def test_cap_funcio_de_domini_es_security_definer():
    """Una SECURITY DEFINER executaria amb els privilegis del propietari (salt de RLS)."""
    assert _one("""SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
                   WHERE n.nspname IN ('core', 'users', 'refuges') AND p.prosecdef""") == 0


def test_un_uid_amb_valors_especials_no_dona_privilegis(RM):
    for uid in ('system', 'true', "x', 'true", ''):
        with rls_context(uid=uid):
            assert _one('SELECT core.is_system()') is False
            assert _one('SELECT core.is_admin()') is False


def test_un_uid_amb_sql_no_veu_usuaris_aliens(RM):
    from apps.accounts.models import UserAccount
    make_user('u1')
    make_user('u2')
    with rls_context(uid="u1' OR '1'='1"):
        assert UserAccount.objects.count() == 0
