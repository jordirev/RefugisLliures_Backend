"""
Bloqueig d'una pujada que coincideix amb la llista de hashes (chunk 9; D40 (3); decisió del PO 28/10), sense mocks del
proveïdor: la coincidència surt de `fn_hash_match` (entrades escrites amb `make_hash`). Es força el hash del contingut
processat parcialment per no dependre de la determinació de la codificació WebP.

`POST /api/media/upload-intents/confirm/` -> 200 `{uploaded: [], failed: [{upload_id, reason: 'moderation_blocked'}]}` i:
- l'intent queda `failed/moderation_blocked`; no es publica res (cap `refuge_media`, cap fitxer fora de `quarantine/` i
  `moderation-hold/`);
- l'evidència es mou a `moderation-hold/<upload_id>` (la clau **no porta l'UID**: les files `legal_hold` es conserven
  anonimitzades, §2.1; decisió tècnica, abans era `moderation-hold/<uid>/<upload_id>`);
- l'usuari queda bloquejat (`moderation_hash_match`) amb `system_context()`;
- denúncia automàtica `child_sexual_abuse` (`source='automatic'`, `reporter_uid` NULL, `priority='high'`,
  `legal_hold = true`, `media_creator_uid` = l'usuari, `refuge_id` = el refugi o NULL per a un avatar, `details`
  «Coincidència automàtica (hash_blocklist/<match>, categoria <categoria>)»);
- avís `account_blocked`/`upload_blocked` (`automated`, `reason='child_sexual_abuse'`) lligat a la denúncia (`report_id`);
- auditoria `legal_hold`: `moderation.hash_block` (actor NULL, `target_type='upload'`, `target_id=<upload_id>`) i
  `moderation.user_blocked` (actor NULL, `subject_uid` = l'usuari), sense l'UID a `metadata`/`target_id`.
"""
from unittest.mock import patch

import pytest
from django.db import DatabaseError

from apps.moderation.tests.helpers import (
    REPORTS, api_post, audit_rows, make_hash, make_png, notice_rows, report_rows, user_claims, user_state)
from apps.uploads.tests.helpers import avatar_row, intent_row, refuge_media_rows
from apps.uploads.tests.test_views_confirm import assert_failed, confirm, create_intent, published_keys

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration,
              pytest.mark.real_permissions]

SHA = '5a' * 32


def force_hash(sha256=None, phash=None):
    """`ModerationService.check` real, però amb el hash del contingut substituït (el de la llista)."""
    from api.services.moderation_service import ModerationService
    original = ModerationService.check

    def check(self, media):
        if sha256 is not None:
            media.sha256 = sha256
        if phash is not None:
            media.phash = phash
        return original(self, media)

    return patch.object(ModerationService, 'check', check)


def blocked_upload(client, world, r2store, uid_claims='u1', target='refuge'):
    refuge = world[0] if target == 'refuge' else None
    upload_id = create_intent(client, r2store, make_png(), target, refuge, claims=user_claims(uid_claims),
                              content_type='image/png')
    resp = confirm(client, [upload_id], user_claims(uid_claims))
    return upload_id, resp


def test_sha256_coincident_bloqueja_la_pujada_l_usuari_i_crea_denuncia_i_avis(client, world, r2store):
    entry = make_hash(sha256=SHA, category='csam')
    with force_hash(sha256=SHA):
        upload_id, resp = blocked_upload(client, world, r2store)
    assert_failed(resp, upload_id, 'moderation_blocked')
    row = intent_row(upload_id)
    assert (row['status'], row['failure_reason']) == ('failed', 'moderation_blocked')
    assert refuge_media_rows() == [] and published_keys(r2store) == []
    st = user_state('u1')
    assert (st['is_blocked'], st['blocked_reason']) == (True, 'moderation_hash_match') and st['blocked_at']
    # evidència retinguda sense UID a la clau
    assert r2store.keys('moderation-hold/') == [f'moderation-hold/{upload_id}']
    assert f'quarantine/{upload_id}' not in r2store.store
    # denúncia automàtica
    [rep] = report_rows()
    assert (rep['source'], rep['reporter_uid'], rep['reason'], rep['priority'], rep['legal_hold']) == (
        'automatic', None, 'child_sexual_abuse', 'high', True)
    assert (rep['media_key'], rep['media_creator_uid'], rep['refuge_id'], rep['status']) == (
        f'moderation-hold/{upload_id}', 'u1', str(world[0].pk), 'pending')
    assert rep['details'] == 'Coincidència automàtica (hash_blocklist/sha256, categoria csam)'
    # avís lligat a la denúncia
    [n] = notice_rows('u1')
    assert (n['type'], n['action'], n['automated'], n['reason'], n['report_id']) == (
        'account_blocked', 'upload_blocked', True, 'child_sexual_abuse', rep['id'])
    assert n['refuge_id'] == str(world[0].pk) and 'bloquejat' in n['statement']
    assert entry                                                         # l'entrada existeix a la llista


def test_phash_proper_tambe_bloqueja(client, world, r2store):
    make_hash(phash=-0x0123456789abcdf)                                  # 64 bits amb signe
    near = format((-0x0123456789abcdf) & (2 ** 64 - 1) ^ 0b101, '016x')
    with force_hash(phash=near):
        upload_id, resp = blocked_upload(client, world, r2store)
    assert_failed(resp, upload_id, 'moderation_blocked')
    assert report_rows()[0]['details'] == 'Coincidència automàtica (hash_blocklist/phash, categoria csam)'


def test_la_categoria_other_es_reflecteix_a_la_denuncia(client, world, r2store):
    make_hash(sha256=SHA, category='other')
    with force_hash(sha256=SHA):
        blocked_upload(client, world, r2store)
    assert report_rows()[0]['details'] == 'Coincidència automàtica (hash_blocklist/sha256, categoria other)'


def test_un_avatar_bloquejat_no_te_refugi_a_la_denuncia(client, world, r2store):
    make_hash(sha256=SHA)
    with force_hash(sha256=SHA):
        upload_id, resp = blocked_upload(client, world, r2store, target='avatar')
    assert_failed(resp, upload_id, 'moderation_blocked')
    [rep] = report_rows()
    assert rep['refuge_id'] is None and rep['media_creator_uid'] == 'u1' and rep['legal_hold'] is True
    assert avatar_row('u1') is None
    [n] = notice_rows('u1')
    assert n['refuge_id'] is None and n['report_id'] == rep['id']


def test_sense_coincidencia_es_publica_amb_normalitat(client, world, r2store):
    make_hash(sha256=SHA)                                                # una altra entrada
    upload_id = create_intent(client, r2store, make_png(), 'refuge', world[0], content_type='image/png')
    resp = confirm(client, [upload_id])
    assert resp.status_code == 200 and len(resp.json()['uploaded']) == 1
    assert user_state('u1')['is_blocked'] is False and report_rows() == [] and notice_rows() == []


def test_despres_del_bloqueig_l_usuari_ja_no_pot_denunciar_ni_pujar(client, world, r2store):
    make_hash(sha256=SHA)
    with force_hash(sha256=SHA):
        upload_id, _ = blocked_upload(client, world, r2store)
    assert confirm(client, [upload_id]).status_code == 403
    resp = api_post(client, REPORTS, user_claims('u1'), {'refuge_id': str(world[0].pk), 'media_key': 'k',
                                                         'reason': 'hate_speech'})
    assert resp.status_code == 403 and resp.json()['error'] == 'user_blocked'


def test_si_la_llista_de_hashes_falla_es_fail_closed(client, world, r2store):
    upload_id = create_intent(client, r2store, make_png(), 'refuge', world[0], content_type='image/png')
    with patch('apps.moderation.selectors.hash_match', side_effect=DatabaseError('bd caiguda')):
        resp = confirm(client, [upload_id])
    assert_failed(resp, upload_id, 'processing_error')
    assert refuge_media_rows() == [] and published_keys(r2store) == []
    assert user_state('u1')['is_blocked'] is False and report_rows() == []


def test_la_denuncia_automatica_es_unica_per_clau_de_retencio(client, world, r2store):
    """Dues pujades bloquejades generen dues claus de retenció diferents (`moderation-hold/<upload_id>`)."""
    make_hash(sha256=SHA)
    with force_hash(sha256=SHA):
        first, _ = blocked_upload(client, world, r2store, 'u1')
        second, _ = blocked_upload(client, world, r2store, 'u2')
    assert {r['media_key'] for r in report_rows()} == {f'moderation-hold/{first}', f'moderation-hold/{second}'}
    assert sorted(n['user_uid'] for n in notice_rows()) == ['u1', 'u2']


@pytest.mark.real_audit_log
def test_auditoria_legal_hold_sense_uid(client, world, r2store):
    make_hash(sha256=SHA)
    with force_hash(sha256=SHA):
        upload_id, _ = blocked_upload(client, world, r2store)
    [block] = audit_rows('moderation.hash_block')
    assert block['actor_uid'] is None and block['legal_hold'] is True
    assert (block['target_type'], block['target_id']) == ('upload', upload_id)
    assert block['metadata'] == {'provider': 'hash_blocklist', 'match_type': 'sha256', 'upload_id': upload_id}
    [blocked] = audit_rows('moderation.user_blocked')
    assert blocked['actor_uid'] is None and blocked['subject_uid'] == 'u1' and blocked['legal_hold'] is True
    assert blocked['target_type'] == 'user' and blocked['target_id'] is None
    assert blocked['metadata'] == {'reason': 'moderation_hash_match'}
    for row in (block, blocked):
        assert 'u1' not in str(row['metadata']) and 'u1' not in str(row['target_id'])
        assert (row['expire_at'] - row['created_at']).days >= 1825          # 5 anys (N2)
    assert not any(r['action'] == 'moderation.hash_block' and r['subject_uid'] for r in audit_rows())
