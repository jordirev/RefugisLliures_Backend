"""
`GET /api/admin/media-reports/?status=pending|resolved` (chunk 9; §2.20): llista per a moderadors.

Contracte: `{count, reports: [...]}`; cada denúncia porta les claus de `REPORT_KEYS` més `media` (el `MediaItem` de
l'API amb `status`, o `null` si el mitjà ja no existeix o és evidència a `moderation-hold/`). Ordre: `priority` (`high`
primer), `created_at`, `id`. **Una sola consulta** amb `LEFT JOIN refuges.refuge_media` (cap N+1 per refugi).
Permisos: `IsAuthenticated, HasProfile, IsFirebaseAdmin`. `status` invàlid → 400. Defecte: `pending`.
`reporter_uid` d'una denúncia automàtica és `'system'` (com avui) i el d'una anonimitzada `'unknown'` (com propostes).
"""
import re

import pytest

from apps.moderation.tests.helpers import (
    ADMIN_REPORTS, HIDDEN, MEDIA_ITEM_KEYS, REPORT_KEYS, QueryCounter, admin_claims, api_get, at, make_exp_media,
    make_experience, make_media, make_report, media_key_for, user_claims)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration,
              pytest.mark.real_permissions]


def listing(client, status=None, claims=None):
    path = ADMIN_REPORTS + (f'?status={status}' if status else '')
    return api_get(client, path, claims or admin_claims('adm'))


def ids(resp):
    return [r['id'] for r in resp.json()['reports']]


# =================================== permisos ===================================

def test_anonim_es_401(client, world):
    assert client.get(ADMIN_REPORTS).status_code == 401


def test_un_usuari_normal_es_403_i_no_veu_res(client, world):
    make_report(world[0], 'k', 'u2')
    resp = listing(client, claims=user_claims('u2'))
    assert resp.status_code == 403 and 'reports' not in resp.json()


def test_un_admin_sense_perfil_es_403_profile_required(client, world):
    resp = api_get(client, ADMIN_REPORTS, admin_claims('adm_nou'))
    assert resp.status_code == 403 and resp.json()['error'] == 'profile_required'


def test_status_invalid_es_400(client, world):
    resp = listing(client, 'closed')
    assert resp.status_code == 400 and resp.json()['error'] == 'Dades invàlides'


# =================================== contingut ===================================

def test_buit(client, world):
    resp = listing(client)
    assert resp.status_code == 200 and resp.json() == {'count': 0, 'reports': []}


def test_forma_d_una_denuncia_amb_la_previsualitzacio_del_mitja(client, world):
    r = world[0]
    key = media_key_for(r)
    make_media(r, 'u1', key=key, thumb_key=key.replace('.webp', '_thumb.webp'), status=HIDDEN, width=800, height=600,
               blurhash='LEHV6nWB2yk8pyo0adR*.7kCMdnj')
    rid = make_report(r, key, 'u2', 'my_image', creator='u1', details='sóc jo')
    resp = listing(client)
    assert resp.status_code == 200
    data = resp.json()
    assert data['count'] == 1
    [rep] = data['reports']
    assert set(rep) == REPORT_KEYS | {'media'}
    assert rep['id'] == rid and rep['refuge_id'] == str(r.pk) and rep['media_key'] == key
    assert (rep['reporter_uid'], rep['reason'], rep['details'], rep['media_creator_uid']) == (
        'u2', 'my_image', 'sóc jo', 'u1')
    assert (rep['status'], rep['priority'], rep['source']) == ('pending', 'high', 'user')
    assert (rep['resolved_at'], rep['resolved_by'], rep['action'], rep['statement']) == (None, None, None, None)
    assert re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}.*\+0[12]:00$', rep['created_at'])
    media = rep['media']
    assert set(media) == MEDIA_ITEM_KEYS | {'status'}
    assert media['key'] == key and media['status'] == HIDDEN and media['creator_uid'] == 'u1'
    assert media['url'].startswith('https://r2.test/') and 'thumb' in media['thumb_url']
    assert (media['width'], media['height'], media['media_type']) == (800, 600, 'image')
    assert media['experience_id'] is None


def test_la_previsualitzacio_de_mitjans_d_experiencia_porta_experience_id(client, world):
    r = world[0]
    e = make_experience(r, 'u1')
    key = media_key_for(r, 'exp')
    make_exp_media(r, 'u1', e, key=key)
    make_report(r, key, 'u2', creator='u1')
    [rep] = listing(client).json()['reports']
    assert rep['media']['experience_id'] == e and rep['media']['key'] == key


def test_estat_per_defecte_pending_i_filtre_resolved(client, world):
    r = world[0]
    p = make_report(r, 'k1', 'u2')
    d = make_report(r, 'k2', 'u2', status='resolved')
    assert ids(listing(client)) == [p] == ids(listing(client, 'pending'))
    resp = listing(client, 'resolved')
    assert ids(resp) == [d] and resp.json()['count'] == 1
    rep = resp.json()['reports'][0]
    assert (rep['status'], rep['resolved_by'], rep['action'], rep['statement']) == ('resolved', 'adm', 'remove', 'motiu')
    assert rep['resolved_at'] is not None


def test_ordre_prioritat_alta_primer_despres_created_at_i_id(client, world):
    r = world[0]
    n_old = make_report(r, 'k1', 'u2', 'hate_speech', minutes=0)
    h_new = make_report(r, 'k2', 'u2', 'my_image', minutes=50)
    n_mid = make_report(r, 'k3', 'u2', 'hate_speech', minutes=10)
    h_old = make_report(r, 'k4', 'u2', 'child_endangerment', minutes=5)
    # empat exacte de created_at: desempata l'id
    a = make_report(r, 'k5', 'u2', 'hate_speech', minutes=20, report_id='00000000-0000-7000-8000-00000000000b')
    b = make_report(r, 'k6', 'u2', 'hate_speech', minutes=20, report_id='00000000-0000-7000-8000-00000000000a')
    assert ids(listing(client)) == [h_old, h_new, n_old, n_mid, b, a]


def test_no_hi_ha_previsualitzacio_per_a_evidencia_retinguda_ni_mitjans_esborrats(client, world):
    r = world[0]
    make_report(r, 'moderation-hold/refugis-lliures/x/y.webp', None, 'child_sexual_abuse', source='automatic',
                minutes=0)
    make_report(r, media_key_for(r, 'esborrat'), 'u2', minutes=1)
    resp = listing(client)
    assert [x['media'] for x in resp.json()['reports']] == [None, None]


def test_un_mitja_retirat_encara_es_previsualitza_amb_status_removed(client, world):
    r = world[0]
    key = media_key_for(r, 'rem')
    make_media(r, 'u1', key=key, status='removed')
    make_report(r, key, 'u2', creator='u1', status='resolved')
    [rep] = listing(client, 'resolved').json()['reports']
    assert rep['media']['status'] == 'removed' and rep['media']['key'] == key


def test_la_previsualitzacio_nomes_si_el_mitja_es_del_refugi_de_la_denuncia(client, world):
    a, b = world
    key = 'refugis-lliures/comu/m.webp'
    make_media(a, 'u1', key=key)
    make_report(a, key, 'u2', creator='u1', minutes=0)
    make_report(b, key, 'u2', minutes=1)          # el mitjà és de A: la denúncia de B no en té previsualització
    reps = listing(client).json()['reports']
    assert reps[0]['media'] is not None and reps[1]['media'] is None


def test_automatica_i_anonimitzada(client, world):
    r = world[0]
    make_report(r, 'moderation-hold/a', None, 'child_sexual_abuse', source='automatic', creator='u1', minutes=0,
                details='Coincidència automàtica (hash_blocklist/sha256, categoria csam)')
    make_report(r, 'k2', None, 'child_sexual_abuse', anonymized_at=at(), minutes=1, details='detall conservat')
    auto, anon = listing(client).json()['reports']
    assert auto['source'] == 'automatic' and auto['reporter_uid'] == 'system'
    assert anon['source'] == 'user' and anon['reporter_uid'] == 'unknown' and anon['details'] == 'detall conservat'


def test_el_creador_esborrat_surt_com_a_null(client, world):
    r = world[0]
    make_report(r, 'k', 'u2', creator=None)
    assert listing(client).json()['reports'][0]['media_creator_uid'] is None


# =================================== consultes ===================================

def test_una_sola_consulta_de_llista_sense_n_mes_1(client, world):
    r, r2 = world
    for i in range(3):
        key = media_key_for(r, f'a{i}')
        make_media(r, 'u1', key=key, minutes=i)
        make_report(r, key, 'u2', creator='u1', minutes=i)
    with QueryCounter() as q1:
        resp = listing(client)
    assert resp.status_code == 200 and len(resp.json()['reports']) == 3
    for i in range(12):
        rr = r if i % 2 else r2
        key = media_key_for(rr, f'b{i}')
        make_media(rr, 'u1', key=key, minutes=100 + i)
        make_report(rr, key, 'u3', creator='u1', minutes=100 + i)
    with QueryCounter() as q2:
        resp = listing(client)
    assert len(resp.json()['reports']) == 15
    assert q1.count == q2.count <= 3, (q1.queries, q2.queries)
    joins = [s for s in q2.queries if 'media_reports' in s]
    assert len(joins) == 1 and 'refuge_media' in joins[0], joins


def test_cap_consulta_pel_mitja_de_cada_refugi(client, world):
    r = world[0]
    for i in range(5):
        key = media_key_for(r, f'c{i}')
        make_media(r, 'u1', key=key, minutes=i)
        make_report(r, key, 'u2', creator='u1', minutes=i)
    with QueryCounter() as q:
        listing(client)
    assert sum('refuge_media' in s for s in q.queries) == 1
    assert not any('refuges"."refuges' in s or 'refuges.refuges' in s for s in q.queries)


# =================================== auditoria ===================================

@pytest.mark.real_audit_log
def test_el_llistat_queda_registrat(client, world):
    from apps.moderation.tests.helpers import audit_rows
    make_report(world[0], 'k', 'u2')
    make_report(world[0], 'k2', 'u2', minutes=1)
    listing(client)
    [row] = audit_rows('moderation.reports_list')
    assert row['actor_uid'] == 'adm' and (row['target_type'], row['target_id']) == ('media_reports', 'pending')
    assert row['metadata'] == {'count': 2}
