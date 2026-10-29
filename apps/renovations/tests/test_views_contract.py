"""
Contracte HTTP dels endpoints de reformes a PostgreSQL (chunk 5), rol `app` + RLS reals. Mateixos codis i mateixa forma
JSON que els endpoints de Firestore d'avui (`api/views/renovation_views.py`), amb les decisions del PO (PLAN.md):

- `GET /renovations/` (actives: `fin_date >= avui de Madrid`), `POST /renovations/`;
- `GET|PATCH|DELETE /renovations/{id}/`;
- `POST /renovations/{id}/participants/`, `DELETE /renovations/{id}/participants/{uid}/`;
- `GET /refuges/{id}/renovations/[?active_only=true]` (B1: la query es llegeix; per defecte, totes com avui).

Forma d'una reforma: `{id, creator_uid ('unknown' si anònima), refuge_id, ini_date, fin_date ('YYYY-MM-DD'),
description, materials_needed, participants_uids[, group_link]}`. **`group_link`** només hi és per al creador, els
participants i els admins (clau omesa per a la resta); **`expelled_uids` no surt mai**.

Codis: 400 validació `{error, details}` o creador que s'uneix; 401 anònim; 403 `profile_required`, no creador, expulsat,
sense permís per treure; 404 reforma/refugi inexistent o id no UUID; 409 solapament (`error` conté «solapa» +
`overlapping_renovation`) o ja participant; 500 `{error, error_id}` (vegeu `test_server_errors.py`).
"""
import uuid

import pytest

from apps.renovations.tests.helpers import (
    BASE_KEYS, FULL_KEYS, LINK, PROFILE_REQUIRED, RENOVATIONS, admin_claims, api_delete, api_get, api_patch, api_post,
    count_renovations, day, expelled_of, link_of, make_renovation, make_user, missing_uuid, new_body, participants_of,
    reno_url, refuge_reno_url, renovation_row, sql, user_claims)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration,
              pytest.mark.real_permissions]


def claims(uid):
    return admin_claims(uid) if uid == 'adm' else user_claims(uid)


def GET(client, path, uid=None):
    return api_get(client, path, claims(uid) if uid else None)


def POST(client, path, uid=None, body=None):
    return api_post(client, path, claims(uid) if uid else None, body)


def PATCH(client, path, uid=None, body=None):
    return api_patch(client, path, claims(uid) if uid else None, body)


def DELETE(client, path, uid=None):
    return api_delete(client, path, claims(uid) if uid else None)


BAD_IDS = ['abc', '12345', 'a' * 40, '%00']


# =============================================== autenticació i perfil ===============================================

@pytest.fixture
def one(world):
    world.rid = make_renovation(world.refuge, 'u1', participants=['u2'])
    return world


def _endpoints(w):
    rid = w.rid
    return [
        ('get', RENOVATIONS), ('post', RENOVATIONS), ('get', reno_url(rid)), ('patch', reno_url(rid)),
        ('delete', reno_url(rid)), ('post', reno_url(rid, 'participants')),
        ('delete', reno_url(rid, 'participants', 'u2')), ('get', f'/api/refuges/{w.refuge.pk}/renovations/')]


def _call(client, method, path, uid=None, body=None):
    fn = {'get': lambda: GET(client, path, uid), 'post': lambda: POST(client, path, uid, body),
          'patch': lambda: PATCH(client, path, uid, body), 'delete': lambda: DELETE(client, path, uid)}[method]
    return fn()


@pytest.mark.parametrize('idx', range(8))
def test_anonim_401(client, one, idx):
    method, path = _endpoints(one)[idx]
    assert _call(client, method, path, None, {}).status_code == 401


@pytest.mark.parametrize('idx', range(8))
def test_sense_perfil_403_profile_required(client, one, idx):
    """Gotcha 15: `HasProfile` darrere `IsAuthenticated`; un token vàlid sense fila a `users` rep `profile_required`."""
    method, path = _endpoints(one)[idx]
    resp = _call(client, method, path, 'sense-perfil', {})
    assert resp.status_code == 403 and resp.json()['error'] == PROFILE_REQUIRED
    assert count_renovations() == 1 and participants_of(one.rid) == ['u2']


def test_les_vistes_porten_is_authenticated_i_has_profile_en_aquest_ordre():
    from django.urls import resolve
    from types import SimpleNamespace
    from apps.auth.permissions import HasProfile
    from rest_framework.permissions import IsAuthenticated
    paths = {
        'list': ('/api/renovations/', ['GET', 'POST']),
        'detail': (f'/api/renovations/{uuid.uuid4()}/', ['GET', 'PATCH', 'DELETE']),
        'join': (f'/api/renovations/{uuid.uuid4()}/participants/', ['POST']),
        'leave': (f'/api/renovations/{uuid.uuid4()}/participants/u2/', ['DELETE']),
        'refuge': (f'/api/refuges/{uuid.uuid4()}/renovations/', ['GET']),
    }
    for name, (path, methods) in paths.items():
        cls = resolve(path).func.view_class
        for m in methods:
            view = cls()
            view.request = SimpleNamespace(method=m)
            classes = [type(p) for p in view.get_permissions()]
            assert classes[:2] == [IsAuthenticated, HasProfile], f'{name} {m}: {classes}'


def test_un_usuari_bloquejat_pot_llegir_les_reformes_com_ara(client, one):
    """Els permisos d'aquest domini són només `IsAuthenticated + HasProfile` (sense `IsNotBlocked`/`IsAgeConfirmed`)."""
    sql("UPDATE users.users SET is_blocked = true, blocked_reason = 'strikes', blocked_at = now() WHERE uid = 'u3'")
    assert GET(client, RENOVATIONS, 'u3').status_code == 200


# =============================================== GET /renovations/ ===============================================

def test_llista_buida(client, world):
    r = GET(client, RENOVATIONS, 'u3')
    assert r.status_code == 200 and r.json() == []


def test_llista_forma_per_a_un_alie_sense_enllac_ni_expulsats(client, world):
    rid = make_renovation(world.refuge, 'u1', ini=day(5), fin=day(9), participants=['u2', 'u3'], expelled=['u4'],
                          materials='Fusta')
    data = GET(client, RENOVATIONS, 'u4').json()
    assert isinstance(data, list) and len(data) == 1
    item = data[0]
    assert set(item) == BASE_KEYS                                     # cap `group_link` ni `expelled_uids`
    assert item == {'id': str(rid), 'creator_uid': 'u1', 'refuge_id': str(world.refuge.pk),
                    'ini_date': day(5).isoformat(), 'fin_date': day(9).isoformat(),
                    'description': 'Pintar la cabana', 'materials_needed': 'Fusta',
                    'participants_uids': ['u2', 'u3']}


def test_llista_nomes_actives_inclou_la_que_acaba_avui_i_ordena_per_inici(client, world):
    late = make_renovation(world.refuge, 'u1', ini=day(20), fin=day(22))
    ends_today = make_renovation(world.refuge2, 'u1', ini=day(-4), fin=day(0))
    make_renovation(world.refuge, 'u1', ini=day(-20), fin=day(-1))                 # acabada ahir: fora
    soon = make_renovation(world.refuge, 'u1', ini=day(3), fin=day(4))
    ids = [r['id'] for r in GET(client, RENOVATIONS, 'u3').json()]
    assert ids == [str(ends_today), str(soon), str(late)]


def test_llista_reforma_d_un_dia_apareix_a_les_actives(client, world):
    """A1: abans una reforma d'un dia deixava la llista buida per a tothom."""
    make_renovation(world.refuge, 'u1', ini=day(3), fin=day(3))
    assert len(GET(client, RENOVATIONS, 'u3').json()) == 1


@pytest.mark.parametrize('uid,sees', [('u1', True), ('u2', True), ('adm', True), ('u3', False), ('u4', False)])
def test_llista_group_link_nomes_per_creador_participants_i_admin(client, world, uid, sees):
    make_renovation(world.refuge, 'u1', participants=['u2'], expelled=['u4'])
    item = GET(client, RENOVATIONS, uid).json()[0]
    assert ('group_link' in item) == sees
    if sees:
        assert item['group_link'] == LINK and set(item) == FULL_KEYS


@pytest.mark.parametrize('uid', ['u1', 'u2', 'u3', 'u4', 'adm'])
def test_expelled_uids_no_surt_mai_a_cap_endpoint(client, world, uid):
    rid = make_renovation(world.refuge, 'u1', participants=['u2'], expelled=['u4'])
    for path in (RENOVATIONS, refuge_reno_url(world.refuge.pk), reno_url(rid)):
        body = GET(client, path, uid).content.decode()
        assert 'expelled' not in body


def test_llista_barreja_enllacos_nomes_de_les_reformes_on_s_es_participant(client, world):
    a = make_renovation(world.refuge, 'u1', ini=day(1), fin=day(2), participants=['u3'], link='https://t.me/A')
    b = make_renovation(world.refuge2, 'u2', ini=day(1), fin=day(2), link='https://t.me/B')
    items = {i['id']: i for i in GET(client, RENOVATIONS, 'u3').json()}
    assert items[str(a)]['group_link'] == 'https://t.me/A' and 'group_link' not in items[str(b)]


def test_llista_unknown_per_a_reforma_anonima(client, world):
    make_renovation(world.refuge, None, ini=day(-1), fin=day(2))                    # en curs i sense creador
    item = GET(client, RENOVATIONS, 'u1').json()[0]
    assert item['creator_uid'] == 'unknown' and 'group_link' not in item


def test_llista_sense_paginacio(client, world):
    for i in range(12):
        make_renovation(world.refuge, 'u1', ini=day(i * 3 + 1), fin=day(i * 3 + 2))
    assert len(GET(client, RENOVATIONS, 'u3').json()) == 12


# =============================================== GET /refuges/{id}/renovations/ ===============================================

def test_refugi_per_defecte_retorna_totes_les_del_refugi_ordenades(client, world):
    """B1 / comportament actual: sense `active_only` també surten les acabades."""
    past = make_renovation(world.refuge, 'u1', ini=day(-20), fin=day(-10))
    cur = make_renovation(world.refuge, 'u1', ini=day(2), fin=day(3))
    make_renovation(world.refuge2, 'u1', ini=day(2), fin=day(3))
    ids = [r['id'] for r in GET(client, refuge_reno_url(world.refuge.pk), 'u3').json()]
    assert ids == [str(past), str(cur)]


@pytest.mark.parametrize('flag', ['true', 'True', '1'])
def test_refugi_active_only_es_llegeix_de_la_query(client, world, flag):
    make_renovation(world.refuge, 'u1', ini=day(-20), fin=day(-10))
    cur = make_renovation(world.refuge, 'u1', ini=day(2), fin=day(3))
    ends_today = make_renovation(world.refuge, 'u1', ini=day(-5), fin=day(0))
    ids = [r['id'] for r in GET(client, refuge_reno_url(world.refuge.pk) + f'?active_only={flag}', 'u3').json()]
    assert ids == [str(ends_today), str(cur)]


@pytest.mark.parametrize('flag', ['false', 'False', '0'])
def test_refugi_active_only_fals_retorna_totes(client, world, flag):
    make_renovation(world.refuge, 'u1', ini=day(-20), fin=day(-10))
    make_renovation(world.refuge, 'u1', ini=day(2), fin=day(3))
    assert len(GET(client, refuge_reno_url(world.refuge.pk) + f'?active_only={flag}', 'u3').json()) == 2


def test_refugi_sense_reformes_llista_buida(client, world):
    r = GET(client, refuge_reno_url(world.refuge.pk), 'u3')
    assert r.status_code == 200 and r.json() == []


@pytest.mark.parametrize('refuge_id', [missing_uuid(), 'abc', '12345', '%00'])
def test_refugi_inexistent_o_no_uuid_404(client, world, refuge_id):
    r = GET(client, refuge_reno_url(refuge_id), 'u3')
    assert r.status_code == 404 and 'error' in r.json()


def test_refugi_group_link_segons_l_usuari(client, world):
    make_renovation(world.refuge, 'u1', participants=['u2'])
    assert 'group_link' in GET(client, refuge_reno_url(world.refuge.pk), 'u2').json()[0]
    assert 'group_link' not in GET(client, refuge_reno_url(world.refuge.pk), 'u3').json()[0]


# =============================================== GET /renovations/{id}/ ===============================================

def test_detall_forma_i_valors(client, world):
    rid = make_renovation(world.refuge, 'u1', ini=day(5), fin=day(9), participants=['u3', 'u2'])
    r = GET(client, reno_url(rid), 'u2')
    assert r.status_code == 200
    assert r.json() == {'id': str(rid), 'creator_uid': 'u1', 'refuge_id': str(world.refuge.pk),
                        'ini_date': day(5).isoformat(), 'fin_date': day(9).isoformat(),
                        'description': 'Pintar la cabana', 'materials_needed': None,
                        'participants_uids': ['u3', 'u2'], 'group_link': LINK}


def test_detall_d_una_reforma_acabada_tambe_es_veu(client, world):
    rid = make_renovation(world.refuge, 'u1', ini=day(-20), fin=day(-10))
    assert GET(client, reno_url(rid), 'u3').status_code == 200


@pytest.mark.parametrize('uid,sees', [('u1', True), ('u2', True), ('adm', True), ('u3', False), ('u4', False)])
def test_detall_group_link_segons_l_usuari(client, world, uid, sees):
    rid = make_renovation(world.refuge, 'u1', participants=['u2'], expelled=['u4'])
    data = GET(client, reno_url(rid), uid).json()
    assert ('group_link' in data) == sees


def test_detall_d_una_reforma_anonima(client, world):
    rid = make_renovation(world.refuge, None, ini=day(-20), fin=day(-10), participants=['u2'])
    data = GET(client, reno_url(rid), 'u2').json()
    assert data['creator_uid'] == 'unknown' and 'group_link' not in data and data['participants_uids'] == ['u2']


@pytest.mark.parametrize('rid', [missing_uuid()] + BAD_IDS)
def test_detall_inexistent_o_no_uuid_404(client, world, rid):
    r = GET(client, reno_url(rid), 'u1')
    assert r.status_code == 404 and 'error' in r.json()


# =============================================== POST /renovations/ ===============================================

def test_post_crea_reforma_201_amb_forma_i_bd(client, world):
    r = POST(client, RENOVATIONS, 'u1', new_body(world.refuge, materials_needed='Taulons'))
    assert r.status_code == 201, r.content
    data = r.json()
    assert set(data) == FULL_KEYS
    assert data['creator_uid'] == 'u1' and data['participants_uids'] == [] and data['group_link'] == LINK
    assert data['refuge_id'] == str(world.refuge.pk) and data['materials_needed'] == 'Taulons'
    assert (data['ini_date'], data['fin_date']) == (day(5).isoformat(), day(10).isoformat())
    rid = uuid.UUID(data['id'])
    assert rid.version == 7
    assert renovation_row(rid)['creator_uid'] == 'u1' and link_of(rid) == LINK


def test_post_sense_materials_retorna_null(client, world):
    data = POST(client, RENOVATIONS, 'u1', new_body(world.refuge)).json()
    assert data['materials_needed'] is None


def test_post_el_creador_es_el_del_token_i_s_ignoren_camps_alienes(client, world):
    body = new_body(world.refuge, creator_uid='u2', participants_uids=['u3'], expelled_uids=['u4'], id=missing_uuid())
    data = POST(client, RENOVATIONS, 'u1', body).json()
    assert data['creator_uid'] == 'u1' and data['participants_uids'] == []
    assert participants_of(uuid.UUID(data['id'])) == [] and expelled_of(uuid.UUID(data['id'])) == []


def test_post_reforma_d_un_dia_201_i_surt_a_la_llista(client, world):
    """Decisió del PO #1 (A1): `ini_date == fin_date` és vàlid."""
    body = new_body(world.refuge, ini_date=day(4).isoformat(), fin_date=day(4).isoformat())
    assert POST(client, RENOVATIONS, 'u1', body).status_code == 201
    assert len(GET(client, RENOVATIONS, 'u3').json()) == 1


def test_post_avui_es_valid(client, world):
    body = new_body(world.refuge, ini_date=day(0).isoformat(), fin_date=day(1).isoformat())
    assert POST(client, RENOVATIONS, 'u1', body).status_code == 201


@pytest.mark.parametrize('over,field', [
    ({'ini_date': day(-1).isoformat()}, 'ini_date'),
    ({'ini_date': day(9).isoformat(), 'fin_date': day(8).isoformat()}, 'fin_date'),
    ({'description': ''}, 'description'),
    ({'description': '   '}, 'description'),
    ({'group_link': 'no-es-una-url'}, 'group_link'),
    ({'group_link': 'ftp://servidor/grup'}, 'group_link'),
    ({'group_link': 'https://' + 'a' * 2050 + '.org'}, 'group_link'),
    ({'ini_date': 'ahir'}, 'ini_date'),
])
def test_post_dades_invalides_400_amb_details_i_res_creat(client, world, over, field):
    r = POST(client, RENOVATIONS, 'u1', new_body(world.refuge, **over))
    assert r.status_code == 400
    body = r.json()
    assert 'error' in body and field in body['details']
    assert count_renovations() == 0


@pytest.mark.parametrize('field', ['refuge_id', 'ini_date', 'fin_date', 'description', 'group_link'])
def test_post_camp_obligatori_absent_400(client, world, field):
    body = new_body(world.refuge)
    del body[field]
    r = POST(client, RENOVATIONS, 'u1', body)
    assert r.status_code == 400 and field in r.json()['details']


def test_post_cos_buit_400(client, world):
    assert POST(client, RENOVATIONS, 'u1', {}).status_code == 400


@pytest.mark.parametrize('refuge_id', [missing_uuid(), 'abc', '12345', 'a' * 40])
def test_post_refugi_inexistent_o_no_uuid_404(client, world, refuge_id):
    r = POST(client, RENOVATIONS, 'u1', new_body(world.refuge, refuge_id=refuge_id))
    assert r.status_code == 404 and 'error' in r.json()
    assert count_renovations() == 0


@pytest.mark.parametrize('ini,fin', [(5, 10), (7, 8), (3, 6), (9, 12), (1, 20), (4, 5)])
def test_post_solapament_409_amb_la_reforma_en_conflicte(client, world, ini, fin):
    other = make_renovation(world.refuge, 'u2', ini=day(5), fin=day(9), participants=['u3'], expelled=['u4'])
    body = new_body(world.refuge, ini_date=day(ini).isoformat(), fin_date=day(fin).isoformat())
    r = POST(client, RENOVATIONS, 'u1', body)
    assert r.status_code == 409
    data = r.json()
    assert 'solapa' in data['error'].lower() and data['overlapping_renovation']['id'] == str(other)
    # La reforma en conflicte és d'una altra persona: ni l'enllaç ni els expulsats es filtren.
    assert set(data['overlapping_renovation']) == BASE_KEYS
    assert count_renovations() == 1


def test_post_solapament_amb_una_reforma_propia_mostra_l_enllac(client, world):
    make_renovation(world.refuge, 'u1', ini=day(5), fin=day(9))
    r = POST(client, RENOVATIONS, 'u1', new_body(world.refuge, ini_date=day(6).isoformat()))
    assert r.status_code == 409 and r.json()['overlapping_renovation']['group_link'] == LINK


@pytest.mark.parametrize('ini,fin', [(10, 12), (1, 4), (2, 3)])
def test_post_dates_contigües_o_a_un_altre_refugi_no_se_solapen(client, world, ini, fin):
    make_renovation(world.refuge, 'u2', ini=day(5), fin=day(9))
    body = new_body(world.refuge, ini_date=day(ini).isoformat(), fin_date=day(fin).isoformat())
    assert POST(client, RENOVATIONS, 'u1', body).status_code == 201


def test_post_mateixes_dates_a_un_altre_refugi_201(client, world):
    make_renovation(world.refuge, 'u2', ini=day(5), fin=day(9))
    body = new_body(world.refuge2, ini_date=day(5).isoformat(), fin_date=day(9).isoformat())
    assert POST(client, RENOVATIONS, 'u1', body).status_code == 201


def test_post_solapament_que_la_comprovacio_previa_no_veu_tambe_es_409(client, world):
    """Carrera entre dues creacions: l'`EXCLUDE` de la BD s'ha de traduir a 409 (no a 500)."""
    from unittest.mock import patch
    make_renovation(world.refuge, 'u2', ini=day(5), fin=day(9))
    with patch('apps.renovations.services.selectors.find_overlapping', return_value=None):
        r = POST(client, RENOVATIONS, 'u1', new_body(world.refuge))
    assert r.status_code == 409 and 'solapa' in r.json()['error'].lower()
    assert count_renovations() == 1


# =============================================== PATCH /renovations/{id}/ ===============================================

@pytest.fixture
def mine(world):
    world.rid = make_renovation(world.refuge, 'u1', ini=day(5), fin=day(10), participants=['u2'], expelled=['u4'],
                                materials='abans')
    return world


def test_patch_canvia_nomes_els_camps_enviats_i_retorna_la_reforma(client, mine):
    r = PATCH(client, reno_url(mine.rid), 'u1', {'description': 'Nova descripció'})
    assert r.status_code == 200
    data = r.json()
    assert set(data) == FULL_KEYS and data['description'] == 'Nova descripció'
    assert data['materials_needed'] == 'abans' and data['participants_uids'] == ['u2'] and data['group_link'] == LINK
    assert (data['ini_date'], data['fin_date']) == (day(5).isoformat(), day(10).isoformat())
    assert renovation_row(mine.rid)['description'] == 'Nova descripció'


def test_patch_canvia_tots_els_camps(client, mine):
    body = {'ini_date': day(6).isoformat(), 'fin_date': day(8).isoformat(), 'description': 'D',
            'materials_needed': 'M', 'group_link': 'https://t.me/nou'}
    data = PATCH(client, reno_url(mine.rid), 'u1', body).json()
    for k, v in body.items():
        assert data[k] == v
    assert link_of(mine.rid) == 'https://t.me/nou'


def test_patch_buit_200_sense_canvis(client, mine):
    r = PATCH(client, reno_url(mine.rid), 'u1', {})
    assert r.status_code == 200 and r.json()['description'] == 'Pintar la cabana'


def test_patch_materials_a_null(client, mine):
    assert PATCH(client, reno_url(mine.rid), 'u1', {'materials_needed': None}).json()['materials_needed'] is None


def test_patch_m2_nomes_ini_date_no_dona_500(client, mine):
    r = PATCH(client, reno_url(mine.rid), 'u1', {'ini_date': day(7).isoformat()})
    assert r.status_code == 200 and r.json()['ini_date'] == day(7).isoformat()
    assert r.json()['fin_date'] == day(10).isoformat()


def test_patch_m2_nomes_fin_date_no_dona_500(client, mine):
    r = PATCH(client, reno_url(mine.rid), 'u1', {'fin_date': day(12).isoformat()})
    assert r.status_code == 200 and r.json()['fin_date'] == day(12).isoformat()


def test_patch_nomes_fin_date_igual_a_la_ini_desada_es_reforma_d_un_dia(client, mine):
    r = PATCH(client, reno_url(mine.rid), 'u1', {'fin_date': day(5).isoformat()})
    assert r.status_code == 200 and r.json()['ini_date'] == r.json()['fin_date']


@pytest.mark.parametrize('body', [{'ini_date': day(12).isoformat()}, {'fin_date': day(4).isoformat()},
                                  {'ini_date': day(9).isoformat(), 'fin_date': day(8).isoformat()}])
def test_patch_dates_incoherents_amb_les_desades_400_no_500(client, mine, body):
    r = PATCH(client, reno_url(mine.rid), 'u1', body)
    assert r.status_code == 400 and 'error' in r.json()
    row = renovation_row(mine.rid)
    assert (row['ini_date'], row['fin_date']) == (day(5), day(10))


def test_patch_ini_date_en_el_passat_400(client, mine):
    assert PATCH(client, reno_url(mine.rid), 'u1', {'ini_date': day(-2).isoformat()}).status_code == 400


@pytest.mark.parametrize('body,field', [({'description': ''}, 'description'), ({'group_link': 'x'}, 'group_link'),
                                        ({'group_link': 'ftp://x/y'}, 'group_link'),
                                        ({'group_link': None}, 'group_link'), ({'ini_date': 'ahir'}, 'ini_date')])
def test_patch_cos_invalid_400_amb_details(client, mine, body, field):
    r = PATCH(client, reno_url(mine.rid), 'u1', body)
    assert r.status_code == 400 and field in r.json()['details']
    assert link_of(mine.rid) == LINK


def test_patch_ignora_camps_que_no_es_poden_editar(client, mine):
    body = {'refuge_id': str(mine.refuge2.pk), 'creator_uid': 'u3', 'participants_uids': ['u3'],
            'expelled_uids': [], 'id': missing_uuid(), 'description': 'ok'}
    data = PATCH(client, reno_url(mine.rid), 'u1', body).json()
    row = renovation_row(mine.rid)
    assert row['refuge_id'] == mine.refuge.pk and row['creator_uid'] == 'u1'
    assert data['participants_uids'] == ['u2'] and expelled_of(mine.rid) == ['u4']
    assert data['id'] == str(mine.rid)


def test_patch_solapament_409_amb_la_reforma_en_conflicte(client, mine):
    other = make_renovation(mine.refuge, 'u3', ini=day(20), fin=day(25))
    r = PATCH(client, reno_url(mine.rid), 'u1', {'fin_date': day(21).isoformat()})
    assert r.status_code == 409
    assert 'solapa' in r.json()['error'].lower() and r.json()['overlapping_renovation']['id'] == str(other)
    assert renovation_row(mine.rid)['fin_date'] == day(10)


def test_patch_les_mateixes_dates_o_un_rang_mes_petit_no_se_solapa_amb_ella_mateixa(client, mine):
    assert PATCH(client, reno_url(mine.rid), 'u1', {'ini_date': day(5).isoformat(),
                                                    'fin_date': day(10).isoformat()}).status_code == 200
    assert PATCH(client, reno_url(mine.rid), 'u1', {'ini_date': day(6).isoformat(),
                                                    'fin_date': day(9).isoformat()}).status_code == 200


@pytest.mark.parametrize('uid', ['u2', 'u3', 'u4', 'adm'])
def test_patch_nomes_el_creador_403_tambe_per_a_participants_i_admin(client, mine, uid):
    r = PATCH(client, reno_url(mine.rid), uid, {'description': 'Hack'})
    assert r.status_code == 403 and 'error' in r.json()
    assert renovation_row(mine.rid)['description'] == 'Pintar la cabana'


def test_patch_d_una_reforma_anonima_403(client, world):
    rid = make_renovation(world.refuge, None, ini=day(-20), fin=day(-10))
    assert PATCH(client, reno_url(rid), 'u1', {'description': 'x'}).status_code == 403


@pytest.mark.parametrize('rid', [missing_uuid()] + BAD_IDS)
def test_patch_inexistent_o_no_uuid_404(client, world, rid):
    assert PATCH(client, reno_url(rid), 'u1', {'description': 'x'}).status_code == 404


# =============================================== DELETE /renovations/{id}/ ===============================================

def test_delete_204_buit_i_cascada(client, mine):
    r = DELETE(client, reno_url(mine.rid), 'u1')
    assert r.status_code == 204 and r.content == b''
    assert renovation_row(mine.rid) is None
    assert (link_of(mine.rid), participants_of(mine.rid), expelled_of(mine.rid)) == (None, [], [])
    assert GET(client, reno_url(mine.rid), 'u1').status_code == 404


def test_delete_no_toca_les_altres_reformes(client, mine):
    keep = make_renovation(mine.refuge2, 'u1', participants=['u2'])
    assert DELETE(client, reno_url(mine.rid), 'u1').status_code == 204
    assert participants_of(keep) == ['u2'] and link_of(keep) == LINK


@pytest.mark.parametrize('uid', ['u2', 'u3', 'u4', 'adm'])
def test_delete_nomes_el_creador_403_tambe_per_a_participants_i_admin(client, mine, uid):
    r = DELETE(client, reno_url(mine.rid), uid)
    assert r.status_code == 403
    assert renovation_row(mine.rid) is not None and participants_of(mine.rid) == ['u2']


def test_delete_d_una_reforma_anonima_403(client, world):
    rid = make_renovation(world.refuge, None, ini=day(-20), fin=day(-10))
    assert DELETE(client, reno_url(rid), 'u1').status_code == 403
    assert renovation_row(rid) is not None


@pytest.mark.parametrize('rid', [missing_uuid()] + BAD_IDS)
def test_delete_inexistent_o_no_uuid_404(client, world, rid):
    assert DELETE(client, reno_url(rid), 'u1').status_code == 404


def test_delete_dues_vegades_la_segona_es_404(client, mine):
    assert DELETE(client, reno_url(mine.rid), 'u1').status_code == 204
    assert DELETE(client, reno_url(mine.rid), 'u1').status_code == 404


# =============================================== POST /renovations/{id}/participants/ ===============================================

@pytest.fixture
def open_reno(world):
    world.rid = make_renovation(world.refuge, 'u1', participants=['u2'], expelled=['u4'])
    return world


def test_unir_se_200_retorna_la_reforma_amb_l_enllac(client, open_reno):
    r = POST(client, reno_url(open_reno.rid, 'participants'), 'u3')
    assert r.status_code == 200, r.content
    data = r.json()
    assert set(data) == FULL_KEYS and data['participants_uids'] == ['u2', 'u3'] and data['group_link'] == LINK
    assert participants_of(open_reno.rid) == ['u2', 'u3']


def test_unir_se_fa_visible_l_enllac_al_nou_participant(client, open_reno):
    assert 'group_link' not in GET(client, reno_url(open_reno.rid), 'u3').json()
    POST(client, reno_url(open_reno.rid, 'participants'), 'u3')
    assert GET(client, reno_url(open_reno.rid), 'u3').json()['group_link'] == LINK


def test_unir_se_l_admin_hi_participa_com_qualsevol(client, open_reno):
    assert POST(client, reno_url(open_reno.rid, 'participants'), 'adm').status_code == 200
    assert participants_of(open_reno.rid) == ['u2', 'adm']


def test_unir_se_el_creador_400(client, open_reno):
    r = POST(client, reno_url(open_reno.rid, 'participants'), 'u1')
    assert r.status_code == 400 and 'creador' in r.json()['error'].lower()
    assert participants_of(open_reno.rid) == ['u2']


def test_unir_se_expulsat_403_sense_revelar_res(client, open_reno):
    r = POST(client, reno_url(open_reno.rid, 'participants'), 'u4')
    assert r.status_code == 403
    body = r.json()
    assert set(body) == {'error'} and 'expulsat' in body['error'].lower()
    assert 'u4' not in r.content.decode() and 'expelled' not in r.content.decode()
    assert participants_of(open_reno.rid) == ['u2']


def test_unir_se_ja_participant_409(client, open_reno):
    r = POST(client, reno_url(open_reno.rid, 'participants'), 'u2')
    assert r.status_code == 409 and 'participant' in r.json()['error'].lower()
    assert participants_of(open_reno.rid) == ['u2']


def test_unir_se_dues_vegades_deixa_una_sola_fila_a3(client, open_reno):
    assert POST(client, reno_url(open_reno.rid, 'participants'), 'u3').status_code == 200
    assert POST(client, reno_url(open_reno.rid, 'participants'), 'u3').status_code == 409
    assert participants_of(open_reno.rid).count('u3') == 1


@pytest.mark.parametrize('rid', [missing_uuid()] + BAD_IDS)
def test_unir_se_inexistent_o_no_uuid_404(client, world, rid):
    assert POST(client, reno_url(rid, 'participants'), 'u3').status_code == 404


# =============================================== DELETE /renovations/{id}/participants/{uid}/ ===============================================

@pytest.fixture
def crew(world):
    world.rid = make_renovation(world.refuge, 'u1', participants=['u2', 'u3'])
    return world


def test_sortir_un_mateix_200_i_pot_tornar(client, crew):
    r = DELETE(client, reno_url(crew.rid, 'participants', 'u2'), 'u2')
    assert r.status_code == 200
    data = r.json()
    assert data['participants_uids'] == ['u3'] and 'group_link' not in data           # ja no hi participa
    assert participants_of(crew.rid) == ['u3'] and expelled_of(crew.rid) == []
    assert POST(client, reno_url(crew.rid, 'participants'), 'u2').status_code == 200


def test_el_creador_expulsa_200_i_l_expulsat_no_pot_tornar(client, crew):
    r = DELETE(client, reno_url(crew.rid, 'participants', 'u2'), 'u1')
    assert r.status_code == 200
    data = r.json()
    assert data['participants_uids'] == ['u3'] and data['group_link'] == LINK
    assert 'expelled_uids' not in data
    assert participants_of(crew.rid) == ['u3'] and expelled_of(crew.rid) == ['u2']
    again = POST(client, reno_url(crew.rid, 'participants'), 'u2')
    assert again.status_code == 403 and 'expulsat' in again.json()['error'].lower()
    assert participants_of(crew.rid) == ['u3']


@pytest.mark.parametrize('requester', ['u3', 'u4', 'adm'])
def test_un_tercer_no_pot_treure_ningu_403(client, crew, requester):
    r = DELETE(client, reno_url(crew.rid, 'participants', 'u2'), requester)
    assert r.status_code == 403 and 'permís' in r.json()['error'].lower()
    assert participants_of(crew.rid) == ['u2', 'u3'] and expelled_of(crew.rid) == []


def test_treure_qui_no_es_participant_403_i_no_l_expulsa(client, crew):
    r = DELETE(client, reno_url(crew.rid, 'participants', 'u4'), 'u1')
    assert r.status_code == 403
    assert expelled_of(crew.rid) == []
    assert DELETE(client, reno_url(crew.rid, 'participants', 'u4'), 'u4').status_code == 403


def test_el_creador_no_pot_treure_se_a_si_mateix_403(client, crew):
    assert DELETE(client, reno_url(crew.rid, 'participants', 'u1'), 'u1').status_code == 403
    assert expelled_of(crew.rid) == []


@pytest.mark.parametrize('rid', [missing_uuid()] + BAD_IDS)
def test_treure_participant_reforma_inexistent_o_no_uuid_404(client, world, rid):
    assert DELETE(client, reno_url(rid, 'participants', 'u2'), 'u2').status_code == 404


def test_expulsio_atomica_si_falla_la_inserció_a_expulsats_no_es_perd_el_participant(client, crew):
    from django.db import connection

    def boom(execute, sql_, params, many, context):
        if sql_.lstrip().upper().startswith('INSERT') and 'renovation_expelled' in sql_:
            raise RuntimeError('fallada simulada')
        return execute(sql_, params, many, context)

    with connection.execute_wrapper(boom):
        r = DELETE(client, reno_url(crew.rid, 'participants', 'u2'), 'u1')
    assert r.status_code == 500 and set(r.json()) == {'error', 'error_id'}
    assert participants_of(crew.rid) == ['u2', 'u3'] and expelled_of(crew.rid) == []


# =============================================== flux complet ===============================================

def test_flux_crear_unir_expulsar_esborrar(client, world):
    created = POST(client, RENOVATIONS, 'u1', new_body(world.refuge))
    assert created.status_code == 201
    rid = created.json()['id']
    assert POST(client, reno_url(rid, 'participants'), 'u2').status_code == 200
    assert POST(client, reno_url(rid, 'participants'), 'u3').status_code == 200
    assert DELETE(client, reno_url(rid, 'participants', 'u2'), 'u1').json()['participants_uids'] == ['u3']
    assert POST(client, reno_url(rid, 'participants'), 'u2').status_code == 403
    assert PATCH(client, reno_url(rid), 'u1', {'description': 'Final'}).json()['participants_uids'] == ['u3']
    assert DELETE(client, reno_url(rid), 'u1').status_code == 204
    assert GET(client, RENOVATIONS, 'u3').json() == []
