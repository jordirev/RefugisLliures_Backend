"""
Pressupost de consultes del chunk 9 (§5.3): cap N+1. El recompte exclou `set_config`/punts de desat (QueryCounter) i
inclou la lectura de `users` de `HasProfile` (una per petició). L'auditoria va mockada (conftest arrel).

Pressupost: `POST /media/reports/` <= 8 (independent de les denúncies que ja hi ha); llista d'admin <= 3 (perfil + una
consulta amb `LEFT JOIN refuge_media`), constant amb N; avisos <= 2 (perfil + avisos); resoldre: constant amb el nombre de
denúncies relacionades.
"""
import pytest

from apps.moderation.tests.helpers import (
    ADMIN_REPORTS, REPORTS, QueryCounter, admin_claims, api_get, api_patch, api_post, make_media, make_report,
    media_key_for, resolve_url, user_claims)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration,
              pytest.mark.real_permissions]


def measure(fn):
    with QueryCounter() as q:
        resp = fn()
    return resp, q


def test_crear_denuncia_dins_del_pressupost(client, world):
    r = world[0]
    key = media_key_for(r)
    make_media(r, 'u1', key=key)
    resp, q = measure(lambda: api_post(client, REPORTS, user_claims('u2'),
                                       {'refuge_id': str(r.pk), 'media_key': key, 'reason': 'hate_speech'}))
    assert resp.status_code == 201 and q.count <= 8, q.queries


def test_crear_denuncia_amb_ocultacio_i_avis_dins_del_pressupost(client, world):
    r = world[0]
    key = media_key_for(r)
    make_media(r, 'u1', key=key)
    resp, q = measure(lambda: api_post(client, REPORTS, user_claims('u2'),
                                       {'refuge_id': str(r.pk), 'media_key': key, 'reason': 'my_image'}))
    assert resp.status_code == 201 and resp.json()['media_hidden'] is True and q.count <= 8, q.queries


def test_crear_denuncia_es_constant_amb_moltes_denuncies_previes(client, world):
    r = world[0]
    key = media_key_for(r)
    make_media(r, 'u1', key=key)
    body = {'refuge_id': str(r.pk), 'media_key': key, 'reason': 'hate_speech'}
    resp, q1 = measure(lambda: api_post(client, REPORTS, user_claims('u2'), body))
    assert resp.status_code == 201
    for i in range(30):
        make_report(r, f'altres/{i}', 'u3', creator='u1', minutes=i)
    resp, q2 = measure(lambda: api_post(client, REPORTS, user_claims('u4'), body))
    assert resp.status_code == 201 and q1.count == q2.count, (q1.queries, q2.queries)


def test_llista_buida_dins_del_pressupost(client, world):
    resp, q = measure(lambda: api_get(client, ADMIN_REPORTS, admin_claims('adm')))
    assert resp.status_code == 200 and q.count <= 3, q.queries


def test_llista_constant_amb_n(client, world):
    r = world[0]
    for i in range(2):
        key = media_key_for(r, f'a{i}')
        make_media(r, 'u1', key=key, minutes=i)
        make_report(r, key, 'u2', creator='u1', minutes=i)
    _, q1 = measure(lambda: api_get(client, ADMIN_REPORTS, admin_claims('adm')))
    for i in range(40):
        key = media_key_for(r, f'b{i}')
        make_media(r, 'u1', key=key, minutes=100 + i, thumb_key=key.replace('.webp', '_t.webp'))
        make_report(r, key, 'u3', creator='u1', minutes=100 + i)
    resp, q2 = measure(lambda: api_get(client, ADMIN_REPORTS, admin_claims('adm')))
    assert len(resp.json()['reports']) == 42
    assert q1.count == q2.count <= 3, (q1.queries, q2.queries)


def test_resoldre_es_constant_amb_el_nombre_de_denuncies_relacionades(client, world):
    r = world[0]
    k1, k2 = media_key_for(r, 'x1'), media_key_for(r, 'x2')
    make_media(r, 'u1', key=k1)
    make_media(r, 'u1', key=k2)
    only = make_report(r, k1, 'u2', creator='u1')
    many = make_report(r, k2, 'u2', creator='u1')
    for uid in ('u3', 'u4', 'u5'):
        make_report(r, k2, uid, creator='u1', minutes=1)
    resp1, q1 = measure(lambda: api_patch(client, resolve_url(only), admin_claims('adm'),
                                          {'action': 'remove_and_strike', 'statement': 'x'}))
    resp2, q2 = measure(lambda: api_patch(client, resolve_url(many), admin_claims('adm'),
                                          {'action': 'remove_and_strike', 'statement': 'x'}))
    assert resp1.status_code == resp2.status_code == 200
    assert len(resp2.json()['resolved_report_ids']) == 4
    assert q1.count == q2.count, (q1.queries, q2.queries)
