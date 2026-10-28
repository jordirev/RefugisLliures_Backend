"""
Esborrat d'usuari i de refugi i dades de moderació (chunk 9; §2.1, §2.20, §2.21, §8.4, §8.5; decisions del PO).

Usuari (`DELETE /api/users/{uid}/`, Firebase i R2 mockats):
- denúncies on és **denunciant**: les no `legal_hold` s'esborren (cascada); les `legal_hold` (CSAM) es desvinculen
  (`reporter_uid` NULL, `anonymized_at` = ara) i **conserven `details`** (decisió del PO, 28/10), `status`, `source='user'`,
  `legal_hold` i `media_key`;
- denúncies on és **autor del mitjà**: es conserven amb `media_creator_uid` NULL (i el mitjà, que és seu, s'esborra);
- avisos: s'esborren els seus; els dels altres es conserven; el `report_id` dels avisos d'altri queda NULL si la denúncia
  s'esborra;
- `resolved_by` d'un admin esborrat queda NULL; si Firebase falla (després del commit, D42) les dades ja són anonimitzades.
El pas 2 de §8.4 (mitjans ocults només per denúncies seves) és al chunk 10: `apps/accounts/tests/test_user_deletion_procedure.py`.

Refugi (aprovar una proposta `delete`, chunk 8): les denúncies no `legal_hold` cauen en cascada; les `legal_hold` queden
amb `refuge_id` NULL (conserven `media_key`); els avisos queden amb `refuge_id` NULL; la retenció de `moderation-hold/`
(R2) no es toca.
"""
import pytest

from apps.moderation.tests.helpers import (
    ADMIN_REPORTS, HIDDEN, admin_claims, api_delete, api_get, api_post, count_reports, make_media, make_notice,
    make_report, media_key_for, media_row, notice_rows, report_row, report_rows, sql, user_claims)
from apps.proposals.tests.helpers import approve_url, make_proposal

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration,
              pytest.mark.real_permissions]


def delete_user(client, uid):
    return api_delete(client, f'/api/users/{uid}/', user_claims(uid))


# =================================== usuari: denunciant ===================================

def test_reporter_esborrat_les_denuncies_normals_s_esborren_i_les_dels_altres_es_queden(client, world):
    r = world[0]
    mine = make_report(r, 'k1', 'u2', 'hate_speech', creator='u1')
    mine_resolved = make_report(r, 'k2', 'u2', 'hate_speech', creator='u1', status='resolved')
    theirs = make_report(r, 'k1', 'u3', 'hate_speech', creator='u1')
    assert delete_user(client, 'u2').status_code == 204
    assert report_row(mine) is None and report_row(mine_resolved) is None
    assert report_row(theirs)['reporter_uid'] == 'u3'


@pytest.mark.parametrize('status', ['pending', 'resolved'])
def test_reporter_esborrat_la_denuncia_legal_hold_es_desvincula_i_conserva_details(client, world, status):
    r = world[0]
    rid = make_report(r, 'k1', 'u2', 'child_sexual_abuse', creator='u1', status=status,
                      details='Descripció de l\'evidència que cal conservar')
    before = report_row(rid)
    assert delete_user(client, 'u2').status_code == 204
    row = report_row(rid)
    assert row['reporter_uid'] is None and row['anonymized_at'] is not None
    assert row['anonymized_at'] > before['created_at']
    assert row['details'] == "Descripció de l'evidència que cal conservar"            # decisió del PO (28/10)
    assert (row['legal_hold'], row['source'], row['status'], row['media_key'], row['reason']) == (
        True, 'user', status, 'k1', 'child_sexual_abuse')
    assert (row['refuge_id'], row['media_creator_uid'], row['priority'], row['created_at']) == (
        before['refuge_id'], before['media_creator_uid'], before['priority'], before['created_at'])
    assert row['resolved_at'] == before['resolved_at'] and row['statement'] == before['statement']


def test_dos_denunciants_csam_del_mateix_mitja_esborrats_coexisteixen_anonimitzats(client, world):
    r = world[0]
    a = make_report(r, 'k1', 'u2', 'child_sexual_abuse', creator='u1', details='a')
    b = make_report(r, 'k1', 'u3', 'child_sexual_abuse', creator='u1', details='b')
    assert delete_user(client, 'u2').status_code == 204 and delete_user(client, 'u3').status_code == 204
    rows = report_rows()
    assert {x['id'] for x in rows} == {a, b} and all(x['reporter_uid'] is None for x in rows)
    assert {x['details'] for x in rows} == {'a', 'b'}


def test_l_admin_veu_la_denuncia_anonimitzada_com_a_unknown(client, world):
    make_report(world[0], 'k1', 'u2', 'child_sexual_abuse', creator='u1', details='evidència')
    delete_user(client, 'u2')
    [rep] = api_get(client, ADMIN_REPORTS, admin_claims('adm')).json()['reports']
    assert rep['reporter_uid'] == 'unknown' and rep['details'] == 'evidència' and rep['source'] == 'user'


def test_una_denuncia_anonimitzada_encara_es_pot_resoldre(client, world):
    from apps.moderation.tests.helpers import api_patch, resolve_url
    rid = make_report(world[0], 'k1', 'u2', 'child_sexual_abuse', creator='u1')
    delete_user(client, 'u2')
    resp = api_patch(client, resolve_url(rid), admin_claims('adm'), {'action': 'dismiss', 'statement': 'revisat'})
    assert resp.status_code == 200 and report_row(rid)['status'] == 'resolved'


def test_firebase_falla_l_anonimitzacio_i_l_esborrat_ja_son_ferms(client, world, firebase_accounts):
    """D42: Firebase va després del commit; si falla, 500 però les dades ja són anonimitzades/esborrades."""
    r = world[0]
    hold = make_report(r, 'k1', 'u2', 'child_sexual_abuse', creator='u1')
    plain = make_report(r, 'k2', 'u2', 'hate_speech', creator='u1')
    make_notice('u2')
    firebase_accounts.delete_user.side_effect = RuntimeError('firebase caigut')
    assert delete_user(client, 'u2').status_code == 500
    assert report_row(hold)['reporter_uid'] is None and report_row(hold)['anonymized_at'] is not None
    assert report_row(plain) is None
    assert notice_rows('u2') == []


# =================================== usuari: autor del mitjà ===================================

def test_autor_esborrat_les_denuncies_es_conserven_amb_media_creator_uid_null(client, world):
    r = world[0]
    make_media(r, 'u1', key='k1')
    pending = make_report(r, 'k1', 'u2', 'hate_speech', creator='u1', details=None)
    resolved = make_report(r, 'k2', 'u3', 'hate_speech', creator='u1', status='resolved')
    assert delete_user(client, 'u1').status_code == 204
    for rid in (pending, resolved):
        row = report_row(rid)
        assert row is not None and row['media_creator_uid'] is None and row['reporter_uid'] in ('u2', 'u3')
    assert report_row(pending)['status'] == 'pending' and report_row(resolved)['status'] == 'resolved'
    assert media_row('k1') is None                                      # els mitjans de l'usuari cauen amb ell (D22)


def test_autor_esborrat_la_denuncia_pendent_surt_a_la_llista_sense_previsualitzacio(client, world):
    r = world[0]
    key = media_key_for(r)
    make_media(r, 'u1', key=key)
    make_report(r, key, 'u2', 'hate_speech', creator='u1')
    delete_user(client, 'u1')
    [rep] = api_get(client, ADMIN_REPORTS, admin_claims('adm')).json()['reports']
    assert rep['media'] is None and rep['media_creator_uid'] is None and rep['reporter_uid'] == 'u2'


def test_autor_esborrat_d_una_denuncia_csam_en_retencio_no_perd_l_evidencia(client, world, r2store):
    r = world[0]
    held = 'moderation-hold/refugis-lliures/x/y.webp'
    r2store.store[held] = b'evidencia'
    rid = make_report(r, held, 'u2', 'child_sexual_abuse', creator='u1', status='resolved')
    delete_user(client, 'u1')
    assert report_row(rid)['media_creator_uid'] is None and report_row(rid)['legal_hold'] is True
    assert r2store.store[held] == b'evidencia'                            # `moderation-hold/` es conserva (fora de la BD)


def test_l_usuari_bloquejat_per_csam_pot_esborrar_el_compte_i_no_es_perd_la_denuncia(client, world):
    rid = make_report(world[0], 'moderation-hold/a', None, 'child_sexual_abuse', source='automatic', creator='u1')
    sql("UPDATE users.users SET is_blocked = true, blocked_reason = 'csam_confirmed', blocked_at = now() WHERE uid = 'u1'")
    assert delete_user(client, 'u1').status_code == 204
    row = report_row(rid)
    assert row['media_creator_uid'] is None and row['source'] == 'automatic' and row['legal_hold'] is True


# =================================== usuari: avisos i admin ===================================

def test_els_avisos_de_l_usuari_s_esborren_i_els_dels_altres_es_queden(client, world):
    make_notice('u1', 'strike')
    make_notice('u1', 'account_blocked')
    keep = make_notice('u3')
    delete_user(client, 'u1')
    assert [n['id'] for n in notice_rows()] == [keep]


def test_un_avis_d_un_altre_lligat_a_una_denuncia_esborrada_perd_el_report_id(client, world):
    rid = make_report(world[0], 'k1', 'u2', 'hate_speech', creator='u1')
    nid = make_notice('u1', report_id=rid)
    other = make_notice('u3', report_id=rid)
    delete_user(client, 'u2')                                              # el denunciant: la denúncia cau
    assert report_row(rid) is None
    [n] = [x for x in notice_rows() if x['id'] == other]
    assert n['report_id'] is None
    assert nid in [x['id'] for x in notice_rows()]


def test_admin_esborrat_resolved_by_queda_null_i_la_resolucio_es_conserva(client, world):
    rid = make_report(world[0], 'k1', 'u2', 'hate_speech', creator='u1', status='resolved', resolved_by='adm2',
                      statement='Motiu de la decisió')
    delete_user(client, 'adm2')
    row = report_row(rid)
    assert (row['status'], row['resolved_by'], row['statement'], row['action']) == ('resolved', None, 'Motiu de la decisió', 'remove')


def test_delete_user_no_toca_firestore_per_moderacio(client, world):
    """Sense cap mock: el conftest arrel prohibeix Firestore. Cap pas de Firestore de moderació."""
    from pathlib import Path
    from apps.accounts import services
    assert '_firestore_steps' not in Path(services.__file__).read_text(encoding='utf-8')
    make_report(world[0], 'k1', 'u2', 'hate_speech', creator='u1')
    make_notice('u1')
    assert delete_user(client, 'u1').status_code == 204


# =================================== refugi ===================================

def approve_delete(client, refuge):
    pid = make_proposal('delete', refuge=refuge)
    return api_post(client, approve_url(pid), admin_claims('adm'))


def test_esborrar_el_refugi_cascadeja_les_denuncies_normals_i_desvincula_les_legal_hold(client, world):
    r, keep = world
    normal = make_report(r, 'k1', 'u2', 'hate_speech', creator='u1')
    normal_resolved = make_report(r, 'k2', 'u3', 'hate_speech', creator='u1', status='resolved')
    hold = make_report(r, 'k3', 'u2', 'child_sexual_abuse', creator='u1', details='evidència')
    auto = make_report(r, 'moderation-hold/z', None, 'child_sexual_abuse', source='automatic', creator='u1')
    other = make_report(keep, 'k9', 'u2', 'hate_speech', creator='u1')
    resp = approve_delete(client, r)
    assert resp.status_code == 200, resp.content
    assert report_row(normal) is None and report_row(normal_resolved) is None
    for rid, key in ((hold, 'k3'), (auto, 'moderation-hold/z')):
        row = report_row(rid)
        assert row is not None and row['refuge_id'] is None and row['media_key'] == key and row['legal_hold'] is True
    assert report_row(hold)['details'] == 'evidència' and report_row(hold)['reporter_uid'] == 'u2'
    assert report_row(other)['refuge_id'] == str(keep.pk)


def test_esborrar_el_refugi_deixa_els_avisos_amb_refuge_id_null(client, world):
    r, keep = world
    a = make_notice('u1', refuge=r, media_key='k1', report_id=None)
    b = make_notice('u1', refuge=keep, media_key='k2')
    approve_delete(client, r)
    rows = {n['id']: n for n in notice_rows('u1')}
    assert rows[a]['refuge_id'] is None and rows[a]['media_key'] == 'k1' and rows[b]['refuge_id'] == str(keep.pk)


def test_esborrar_el_refugi_no_toca_la_retencio_a_r2_ni_l_auditoria(client, world, r2store):
    r, _ = world
    held = 'moderation-hold/refugis-lliures/x/y.webp'
    r2store.store[held] = b'evidencia'
    make_report(r, held, 'u2', 'child_sexual_abuse', creator='u1')
    make_media(r, 'u1', key=f'refugis-lliures/{r.pk}/a.webp')
    approve_delete(client, r)
    assert r2store.store[held] == b'evidencia' and held not in r2store.deletes
    assert f'refugis-lliures/{r.pk}/a.webp' in r2store.deletes


def test_un_refugi_amb_una_denuncia_legal_hold_i_un_mitja_ocult_es_pot_esborrar(client, world):
    r, _ = world
    make_media(r, 'u1', key='k1', status=HIDDEN)
    rid = make_report(r, 'k1', 'u2', 'child_sexual_abuse', creator='u1')
    assert approve_delete(client, r).status_code == 200
    assert report_row(rid)['refuge_id'] is None and media_row('k1') is None
    assert count_reports() == 1
