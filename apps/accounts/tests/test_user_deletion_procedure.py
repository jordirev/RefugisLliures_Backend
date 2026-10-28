"""
Procediment únic d'esborrat d'usuari (chunk 10; D42, §8.4, §8.5): `DELETE /api/users/{uid}/`. Rol `app` + RLS reals;
Firebase Auth i R2 mockats (fixtures `firebase_accounts` i `r2`). Cap Firestore.

CONTRACTE per a l'implementador (`apps/accounts/services.py` i `views.py`):
- `delete_user(uid, media_service=None)` és autosuficient: obre la seva pròpia transacció (`transaction.atomic()` /
  `rls_context`) i fixa el seu context de RLS (no depèn del hook de la petició). Fa, dins UNA transacció i en aquest ordre:
  (1) `SELECT ... FOR UPDATE` de la fila de `users.users` (primera sentència de contingut); si no hi és, no fa res i salta
  directament a Firebase (camí idempotent: sense auditoria ni R2); (2) recull les claus d'R2 (avatar+miniatura, mitjans
  propis+miniatures, mitjans de les seves experiències, `quarantine/<upload_id>` dels seus intents `pending`) amb un nombre
  constant de consultes; (3) reformes vigents fora; (4) pas 2 de §8.4 (denúncia automàtica); (5) `comment` de les propostes
  a NULL; (6) esborra les claus a R2 (`delete_files`/`delete_file`; qualsevol fallada → `UserDeletionError`, tot desfet);
  (7) `DELETE users.users`; (8) auditoria `user.deleted` (actor/subjecte/target NULL, `metadata {}`).
  Després de la transacció (COMMIT real) crida Firebase Auth `delete_user(uid)`; `UserNotFoundError` = èxit; altre error →
  `UserDeletionError` (les dades ja són esborrades i firmes).
- Opció escollida (D42 «després del COMMIT»): la vista DELETE és `@transaction.non_atomic_requests` i `delete_user` crida
  Firebase quan ha sortit del seu `atomic()`. (Un `transaction.on_commit` no es veuria als tests normals, que van dins la
  transacció de pytest-django; el COMMIT real el comproven `test_user_deletion_commit.py` i `..._concurrency.py`.)
- La vista DELETE usa `[IsAuthenticated, IsSameUser]` (sense `HasProfile`); GET i PATCH no canvien. Els errors
  (`UserDeletionError`, qualsevol excepció) → `server_error(...)` = 500 `{error, error_id}`; `UserNotFound` ja no s'usa
  a la vista (mai 404).
- `_firestore_steps` desapareix i `services.py` no importa Firestore.
"""
import re
from pathlib import Path

import pytest
from firebase_admin import auth as firebase_auth

from apps.accounts.tests.helpers import QueryCounter
from apps.moderation.tests.helpers import (
    HIDDEN, admin_claims, api_delete, api_get, api_patch, audit_rows, make_avatar, make_intent,
    make_media, make_notice, make_refuge, make_report, make_user, report_row, report_rows, sql, user_claims)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration,
              pytest.mark.real_permissions]

URL = '/api/users/{}/'


def delete(client, uid, claims=None, **kw):
    """Els helpers d'accounts no creen el perfil de qui fa la petició (`ensure` no existeix)."""
    kw.pop('ensure', None)
    return api_delete(client, URL.format(uid), claims or user_claims(uid), **kw)


def user_exists(uid):
    return sql('SELECT count(*) FROM users.users WHERE uid = %s', [uid])[0][0] == 1


def r2_deleted(r2):
    keys = [c.args[0] for c in r2.delete_file.call_args_list]
    for c in r2.delete_files.call_args_list:
        keys += list(c.args[0])
    return keys


def fail_r2(r2):
    r2.delete_files.side_effect = lambda keys: {'deleted': [], 'failed': list(keys)}
    r2.delete_file.return_value = False


@pytest.fixture
def world():
    for uid in ('u1', 'u2', 'u3', 'u4', 'adm'):
        make_user(uid, username=uid)
    return make_refuge(name='Refugi A'), make_refuge(name='Refugi B', lat=43.0)


# =================================== permisos ===================================

def test_anonim_401_i_no_toca_res(client, world, firebase_accounts):
    assert api_delete(client, URL.format('u1')).status_code == 401
    assert user_exists('u1')
    firebase_accounts.delete_user.assert_not_called()


@pytest.mark.parametrize('claims', [user_claims('u2'), admin_claims('adm')])
def test_d_un_altre_403_tambe_per_a_admin_i_no_toca_res(client, world, r2, firebase_accounts, claims):
    make_media(world[0], 'u1', key='k/u1.webp')
    assert delete(client, 'u1', claims).status_code == 403
    assert user_exists('u1') and sql('SELECT count(*) FROM refuges.refuge_media')[0][0] == 1
    assert r2_deleted(r2) == []
    firebase_accounts.delete_user.assert_not_called()


def test_sense_fila_amb_uid_d_un_altre_tambe_403(client, world):
    """`IsSameUser` abans de qualsevol altra cosa: un UID inexistent d'un altre no és 204 ni 404."""
    assert delete(client, 'fantasma', user_claims('u2')).status_code == 403


def test_un_bloquejat_pot_esborrar_el_compte(client, world, firebase_accounts):
    sql("UPDATE users.users SET is_blocked = true, blocked_reason = 'strikes', blocked_at = now() WHERE uid = 'u1'")
    assert delete(client, 'u1').status_code == 204
    assert not user_exists('u1')
    firebase_accounts.delete_user.assert_called_once_with('u1')


def test_un_admin_pot_esborrar_el_seu_propi_compte(client, world, firebase_accounts):
    assert delete(client, 'adm', admin_claims('adm')).status_code == 204
    assert not user_exists('adm')
    firebase_accounts.delete_user.assert_called_once_with('adm')


def test_un_menor_sense_edat_confirmada_pot_esborrar_el_compte(client, world):
    """El DELETE no exigeix `IsAgeConfirmed` (`make_user` del món no confirma l'edat)."""
    assert delete(client, 'u3').status_code == 204


def test_get_i_patch_continuen_exigint_perfil(client):
    r = api_patch(client, URL.format('n1'), user_claims('n1'), {'username': 'x'})
    assert r.status_code == 403 and r.json()['error'] == 'profile_required'
    assert api_get(client, URL.format('n1'), user_claims('n1')).status_code == 403


# =================================== idempotència (sense fila a users.users) ===================================

def test_sense_perfil_el_delete_propi_esborra_el_compte_de_firebase_i_dona_204(client, r2, firebase_accounts):
    resp = delete(client, 'n1', ensure=False)
    assert resp.status_code == 204 and resp.content == b''
    firebase_accounts.delete_user.assert_called_once_with('n1')
    assert r2_deleted(r2) == []


def test_sense_perfil_i_firebase_ja_sense_compte_es_204(client, firebase_accounts):
    firebase_accounts.delete_user.side_effect = firebase_auth.UserNotFoundError('no hi és')
    assert delete(client, 'n1', ensure=False).status_code == 204


def test_sense_perfil_i_firebase_falla_500_amb_error_id(client, firebase_accounts):
    firebase_accounts.delete_user.side_effect = RuntimeError('firebase caigut amb detalls')
    resp = delete(client, 'n1', ensure=False)
    assert resp.status_code == 500 and set(resp.json()) == {'error', 'error_id'}
    assert 'firebase caigut' not in resp.content.decode()


@pytest.mark.real_audit_log
def test_sense_perfil_no_afegeix_cap_entrada_d_auditoria_ni_toca_altres_usuaris(client, world):
    before = audit_rows()
    assert delete(client, 'n1', ensure=False).status_code == 204
    assert audit_rows() == before
    assert user_exists('u1')


def test_reintent_despres_d_un_firebase_fallit_acaba_amb_204(client, world, firebase_accounts):
    """D42: Firebase falla després del commit → 500, dades fora, compte viu; el mateix token pot reintentar."""
    make_media(world[0], 'u1', key='k/u1.webp')
    firebase_accounts.delete_user.side_effect = RuntimeError('firebase caigut')
    first = delete(client, 'u1')
    assert first.status_code == 500 and set(first.json()) == {'error', 'error_id'}
    assert not user_exists('u1')
    firebase_accounts.delete_user.side_effect = None
    firebase_accounts.delete_user.reset_mock()
    assert delete(client, 'u1', ensure=False).status_code == 204          # ja no hi ha fila: no és 404 ni profile_required
    firebase_accounts.delete_user.assert_called_once_with('u1')


def test_delete_dues_vegades_la_segona_es_204_idempotent(client, world, firebase_accounts):
    assert delete(client, 'u1').status_code == 204
    assert delete(client, 'u1', ensure=False).status_code == 204
    assert firebase_accounts.delete_user.call_count == 2


def test_el_token_encara_vigent_no_pot_recrear_el_mateix_uid_despres_d_esborrar(client, world, firebase_accounts):
    """Camí 1 d'U7: DELETE i POST amb el mateix token. Després del DELETE el compte de Firebase ja no existeix."""
    deleted = set()
    firebase_accounts.delete_user.side_effect = deleted.add

    def get_user(uid):
        if uid in deleted:
            raise firebase_auth.UserNotFoundError('esborrat')
    firebase_accounts.get_user.side_effect = get_user
    assert delete(client, 'u1').status_code == 204
    from apps.accounts.tests.helpers import USERS, api_post
    assert api_post(client, USERS, user_claims('u1'), {}).status_code == 401
    assert not user_exists('u1')


# =================================== Firebase: després de les dades ===================================

def test_204_i_firebase_cridat_un_sol_cop_amb_l_uid(client, world, firebase_accounts):
    resp = delete(client, 'u1')
    assert resp.status_code == 204 and resp.content == b''
    firebase_accounts.delete_user.assert_called_once_with('u1')
    assert not user_exists('u1')


def test_firebase_es_crida_quan_la_fila_i_el_contingut_ja_no_hi_son(client, world, firebase_accounts):
    r = world[0]
    make_media(r, 'u1', key='k/u1.webp')
    seen = {}

    def spy(uid):
        seen['user'] = user_exists(uid)
        seen['media'] = sql('SELECT count(*) FROM refuges.refuge_media')[0][0]
    firebase_accounts.delete_user.side_effect = spy
    assert delete(client, 'u1').status_code == 204
    assert seen == {'user': False, 'media': 0}


def test_firebase_falla_500_error_id_sense_detalls_i_les_dades_ja_estan_esborrades(client, world, firebase_accounts):
    r = world[0]
    make_avatar('u1', key='a/u1.webp')
    make_media(r, 'u1', key='k/u1.webp')
    firebase_accounts.delete_user.side_effect = RuntimeError('firebase caigut amb detalls')
    resp = delete(client, 'u1')
    assert resp.status_code == 500 and set(resp.json()) == {'error', 'error_id'}
    assert 'firebase caigut' not in resp.content.decode()
    assert not user_exists('u1')
    assert sql('SELECT count(*) FROM refuges.refuge_media')[0][0] == 0
    assert sql('SELECT count(*) FROM users.user_avatars')[0][0] == 0


def test_firebase_user_not_found_es_exit(client, world, firebase_accounts):
    firebase_accounts.delete_user.side_effect = firebase_auth.UserNotFoundError('no hi és')
    assert delete(client, 'u1').status_code == 204
    assert not user_exists('u1')


def test_si_falla_r2_no_es_toca_firebase(client, world, r2, firebase_accounts):
    make_media(world[0], 'u1', key='k/u1.webp')
    fail_r2(r2)
    assert delete(client, 'u1').status_code == 500
    firebase_accounts.delete_user.assert_not_called()


# =================================== R2: claus i atomicitat ===================================

def test_claus_esborrades_a_r2_avatar_mitjans_experiencies_i_quarantine_dels_pendents(client, world, r2):
    from apps.experiences.tests.helpers import make_exp_media, make_experience
    r = world[0]
    make_avatar('u1', key='a/u1.webp', thumb_key='a/u1_t.webp')
    make_media(r, 'u1', key='k/own.webp', thumb_key='k/own_t.webp')
    make_media(r, 'u1', key='k/own-hidden.webp', status=HIDDEN, minutes=1)
    e = make_experience(r, 'u1')
    make_exp_media(r, 'adm', e, key='k/adm-in-exp.webp', thumb_key='k/adm-in-exp_t.webp', minutes=2)
    make_exp_media(r, 'u1', e, key='k/own-in-exp.webp', minutes=3)
    pending = make_intent('u1', 'avatar')
    pending_ref = make_intent('u1', 'refuge', refuge=r)
    other_pending = make_intent('u2', 'avatar')
    make_media(r, 'u2', key='k/other.webp', minutes=4)
    make_avatar('u2', key='a/u2.webp')
    other_exp = make_experience(r, 'u2', minutes=5)
    make_exp_media(r, 'adm', other_exp, key='k/adm-in-other-exp.webp', minutes=6)
    assert delete(client, 'u1').status_code == 204
    expected = {'a/u1.webp', 'a/u1_t.webp', 'k/own.webp', 'k/own_t.webp', 'k/own-hidden.webp', 'k/adm-in-exp.webp',
                'k/adm-in-exp_t.webp', 'k/own-in-exp.webp', f'quarantine/{pending}', f'quarantine/{pending_ref}'}
    deleted = r2_deleted(r2)
    assert set(deleted) == expected and len(deleted) == len(expected)           # sense duplicats ni claus buides
    assert f'quarantine/{other_pending}' not in deleted


def test_no_s_esborra_res_a_moderation_hold(client, world, r2):
    held = 'moderation-hold/refugis-lliures/x/y.webp'
    make_report(world[0], held, 'u1', 'child_sexual_abuse', creator='u2', status='resolved')
    make_media(world[0], 'u1', key='k/u1.webp')
    assert delete(client, 'u1').status_code == 204
    assert held not in r2_deleted(r2)


def test_sense_fitxers_no_es_crida_r2(client, world, r2):
    assert delete(client, 'u1').status_code == 204
    assert r2_deleted(r2) == []


@pytest.mark.parametrize('how', ['failed', 'raises', 'false'])
def test_qualsevol_fallada_d_r2_es_500_i_es_desfa_tot(client, world, r2, firebase_accounts, how):
    from apps.experiences.tests.helpers import make_exp_media, make_experience
    r = world[0]
    make_avatar('u1', key='a/u1.webp')
    make_media(r, 'u1', key='k/u1.webp')
    e = make_experience(r, 'u1')
    make_exp_media(r, 'u1', e, key='k/e.webp', minutes=1)
    make_intent('u1', 'avatar')
    pid = _proposal_with_comment('u1')
    make_media(r, 'u3', key='k/h.webp', status=HIDDEN, minutes=2)
    make_report(r, 'k/h.webp', 'u1', 'hate_speech', creator='u3')
    if how == 'failed':
        fail_r2(r2)
    elif how == 'raises':
        boom = RuntimeError('r2 caigut amb host intern')
        r2.delete_files.side_effect = boom
        r2.delete_file.side_effect = boom
    else:
        r2.delete_files.side_effect = lambda keys: {'deleted': list(keys[:-1]), 'failed': [keys[-1]]}
    resp = delete(client, 'u1')
    assert resp.status_code == 500 and set(resp.json()) == {'error', 'error_id'}
    assert 'r2 caigut' not in resp.content.decode() and 'host intern' not in resp.content.decode()
    assert user_exists('u1')
    assert sql('SELECT count(*) FROM refuges.refuge_media WHERE creator_uid = %s', ['u1'])[0][0] == 2
    assert sql('SELECT count(*) FROM users.user_avatars')[0][0] == 1
    assert sql('SELECT count(*) FROM moderation.upload_intents WHERE user_uid = %s', ['u1'])[0][0] == 1
    assert sql('SELECT comment FROM proposals.refuge_proposals WHERE id = %s', [pid])[0][0] == 'comentari'
    assert sql("SELECT count(*) FROM moderation.media_reports WHERE source = 'automatic'")[0][0] == 0
    assert report_rows(reporter_uid='u1') != []
    assert audit_rows('user.deleted') == []
    firebase_accounts.delete_user.assert_not_called()


def test_si_falla_r2_es_conserven_les_reformes_vigents(client, world, r2):
    from apps.renovations.tests.helpers import day, make_renovation, renovation_row
    rid = make_renovation(world[0], 'u1', ini=day(2), fin=day(6))
    make_media(world[0], 'u1', key='k/u1.webp')
    fail_r2(r2)
    assert delete(client, 'u1').status_code == 500
    assert renovation_row(rid) is not None


def test_el_bloqueig_de_la_fila_precedeix_la_recollida_de_claus_i_r2(client, world, r2):
    """D42 (1): `FOR UPDATE` de `users.users` abans de llegir cap mitjà i abans d'esborrar a R2."""
    from django.db import connection
    from django.test.utils import CaptureQueriesContext
    make_avatar('u1', key='a/u1.webp')
    make_media(world[0], 'u1', key='k/u1.webp')
    seen = []

    def spy(keys):
        seen.append(list(ctx.captured_queries))
        return {'deleted': list(keys), 'failed': []}
    r2.delete_files.side_effect = spy
    r2.delete_file.side_effect = lambda key: seen.append(list(ctx.captured_queries)) or True
    with CaptureQueriesContext(connection) as ctx:
        assert delete(client, 'u1').status_code == 204
    assert seen, 'R2 no s\'ha cridat'
    before_r2 = [q['sql'] for q in seen[0]]
    lock = [i for i, s in enumerate(before_r2) if 'FOR UPDATE' in s and '"users"."users"' in s]
    assert lock, "cap SELECT ... FOR UPDATE de users.users abans d'R2"
    first_media = [i for i, s in enumerate(before_r2) if 'refuge_media' in s or 'user_avatars' in s]
    assert first_media and lock[0] < first_media[0]


# =================================== pas 2 de §8.4: denúncia automàtica (R23) ===================================

def _auto_reports():
    return report_rows(source='automatic')


def test_mitja_ocult_nomes_per_denuncies_de_l_usuari_torna_a_la_cua_com_a_automatica(client, world):
    r = world[0]
    make_media(r, 'u3', key='k/h.webp', status=HIDDEN)
    mine = make_report(r, 'k/h.webp', 'u1', 'hate_speech', creator='u3')
    assert delete(client, 'u1').status_code == 204
    assert report_row(mine) is None                                        # la seva denúncia cau (cascada)
    [auto] = _auto_reports()
    assert (auto['source'], auto['reason'], auto['details'], auto['priority'], auto['reporter_uid']) == (
        'automatic', 'other', 'reporter_account_deleted', 'high', None)
    assert (auto['status'], auto['media_key'], auto['refuge_id'], auto['media_creator_uid']) == (
        'pending', 'k/h.webp', str(r.pk), 'u3')
    assert auto['legal_hold'] is False and auto['resolved_at'] is None
    assert sql("SELECT status FROM refuges.refuge_media WHERE key = 'k/h.webp'") == [(HIDDEN,)]


def test_amb_un_altre_denunciant_pendent_no_es_crea_cap_automatica(client, world):
    r = world[0]
    make_media(r, 'u3', key='k/h.webp', status=HIDDEN)
    make_report(r, 'k/h.webp', 'u1', 'hate_speech', creator='u3')
    other = make_report(r, 'k/h.webp', 'u2', 'hate_speech', creator='u3', minutes=1)
    assert delete(client, 'u1').status_code == 204
    assert _auto_reports() == [] and report_row(other)['status'] == 'pending'


def test_una_denuncia_de_l_altre_ja_resolta_no_compta_com_a_pendent(client, world):
    r = world[0]
    make_media(r, 'u3', key='k/h.webp', status=HIDDEN)
    make_report(r, 'k/h.webp', 'u1', 'hate_speech', creator='u3')
    make_report(r, 'k/h.webp', 'u2', 'hate_speech', creator='u3', status='resolved', action='dismiss', minutes=1)
    assert delete(client, 'u1').status_code == 204
    assert len(_auto_reports()) == 1


def test_mitja_visible_o_amb_denuncia_resolta_de_l_usuari_no_genera_automatica(client, world):
    r = world[0]
    make_media(r, 'u3', key='k/visible.webp')
    make_report(r, 'k/visible.webp', 'u1', 'hate_speech', creator='u3')
    make_media(r, 'u3', key='k/h2.webp', status=HIDDEN, minutes=1)
    make_report(r, 'k/h2.webp', 'u1', 'hate_speech', creator='u3', status='resolved', action='dismiss')
    assert delete(client, 'u1').status_code == 204
    assert _auto_reports() == []


def test_mitja_ocult_de_la_propia_usuaria_s_esborra_i_no_genera_automatica(client, world):
    r = world[0]
    make_media(r, 'u1', key='k/mine.webp', status=HIDDEN)
    make_report(r, 'k/mine.webp', 'u2', 'hate_speech', creator='u1')
    assert delete(client, 'u1').status_code == 204
    assert _auto_reports() == []


def test_automatica_ja_existent_no_es_duplica_ni_falla(client, world):
    """`UNIQUE (refuge, media_key) WHERE source = 'automatic'` + `ON CONFLICT DO NOTHING`, encara que estigui resolta."""
    r = world[0]
    make_media(r, 'u3', key='k/h.webp', status=HIDDEN)
    make_report(r, 'k/h.webp', 'u1', 'hate_speech', creator='u3')
    old = make_report(r, 'k/h.webp', None, 'other', creator='u3', source='automatic', status='resolved',
                      action='dismiss', details='reporter_account_deleted', minutes=-5)
    assert delete(client, 'u1').status_code == 204
    assert [x['id'] for x in _auto_reports()] == [old]


def test_diversos_mitjans_ocults_cada_un_amb_la_seva_automatica(client, world):
    r1, r2_ = world
    for i, ref in enumerate((r1, r1, r2_)):
        make_media(ref, 'u3', key=f'k/h{i}.webp', status=HIDDEN, minutes=i)
        make_report(ref, f'k/h{i}.webp', 'u1', 'hate_speech', creator='u3', minutes=i)
    assert delete(client, 'u1').status_code == 204
    assert sorted(x['media_key'] for x in _auto_reports()) == ['k/h0.webp', 'k/h1.webp', 'k/h2.webp']


# =================================== propostes, reformes, auditoria ===================================

def _proposal_with_comment(uid):
    from apps.proposals.tests.helpers import make_proposal
    return make_proposal(creator=uid, comment='comentari')


def test_el_comentari_de_les_propostes_passa_a_null_i_el_dels_altres_es_conserva(client, world):
    from apps.proposals.tests.helpers import make_proposal, proposal_row
    mine = make_proposal(creator='u1', comment='el meu', minutes=0)
    other = make_proposal(creator='u2', comment="d'un altre", minutes=1)
    assert delete(client, 'u1').status_code == 204
    assert proposal_row(mine)['comment'] is None and proposal_row(mine)['creator_uid'] is None
    assert proposal_row(other)['comment'] == "d'un altre"


def test_les_reformes_vigents_surten_i_les_passades_queden_anonimes(client, world):
    from apps.renovations.tests.helpers import day, link_of, make_renovation, renovation_row
    current = make_renovation(world[0], 'u1', ini=day(2), fin=day(6), participants=['u2'])
    past = make_renovation(world[1], 'u1', ini=day(-30), fin=day(-10), participants=['u2'])
    assert delete(client, 'u1').status_code == 204
    assert renovation_row(current) is None
    assert renovation_row(past)['creator_uid'] is None and link_of(past) is None


@pytest.mark.real_audit_log
def test_entrada_user_deleted_sense_cap_identificador(client, world):
    make_media(world[0], 'u1', key='k/u1.webp')
    before = len(audit_rows())
    assert delete(client, 'u1').status_code == 204
    rows = audit_rows('user.deleted')
    assert len(rows) == 1 and len(audit_rows()) == before + 1
    [row] = rows
    assert row['actor_uid'] is None and row['subject_uid'] is None and row['target_id'] is None
    assert row['metadata'] == {}
    assert row['legal_hold'] is False and row['expire_at'] is not None
    assert 'u1' not in str(sql('SELECT row_to_json(a)::text FROM audit.audit_logs a WHERE action = %s', ['user.deleted']))


@pytest.mark.real_audit_log
def test_l_entrada_d_auditoria_es_conserva_encara_que_firebase_falli(client, world, firebase_accounts):
    firebase_accounts.delete_user.side_effect = RuntimeError('firebase caigut')
    assert delete(client, 'u1').status_code == 500
    assert len(audit_rows('user.deleted')) == 1


@pytest.mark.real_audit_log
def test_no_hi_entrada_d_auditoria_si_falla_r2(client, world, r2):
    make_media(world[0], 'u1', key='k/u1.webp')
    fail_r2(r2)
    assert delete(client, 'u1').status_code == 500
    assert audit_rows('user.deleted') == []


# =================================== mapa d'impacte complet (§8.5) ===================================

@pytest.mark.real_audit_log
def test_mapa_d_impacte_complet_un_usuari_amb_contingut_a_tots_els_dominis(client, world, r2):
    from apps.doubts.tests.helpers import answer_ids, doubt_ids, make_answer, make_doubt
    from apps.experiences.tests.helpers import exp_ids, make_exp_media, make_experience
    from apps.proposals.tests.helpers import make_proposal, proposal_row
    from apps.accounts.tests.helpers import FAV, VIS, add_list_row, list_rows
    from apps.renovations.tests.helpers import (
        day, expelled_of, link_of, make_renovation, participants_of, renovation_row)
    from apps.visits.tests.helpers import make_visit, participant_rows
    from apps.moderation.tests.helpers import notice_rows
    r1, r2_ = world
    # --- usuaris / llistes
    make_avatar('u1', key='a/u1.webp', thumb_key='a/u1_t.webp')
    add_list_row(FAV, 'u1', r1)
    add_list_row(VIS, 'u1', r1)
    add_list_row(FAV, 'u2', r1)
    # --- visites
    v = make_visit(r1, day(3), {'u1': 2, 'u2': 1})
    # --- reformes: pròpia vigent, pròpia passada, participant i expulsat en alienes
    cur = make_renovation(r1, 'u1', ini=day(2), fin=day(6), participants=['u2'], expelled=['u3'])
    past = make_renovation(r2_, 'u1', ini=day(-30), fin=day(-10), participants=['u2'])
    alien = make_renovation(r2_, 'u2', ini=day(11), fin=day(13), participants=['u1', 'u3'])
    alien2 = make_renovation(r2_, 'u2', ini=day(8), fin=day(9), participants=['u3'], expelled=['u1'])
    # --- experiències + mitjans (un pujat per l'admin) i condició del refugi
    e = make_experience(r1, 'u1', condition=3)
    make_exp_media(r1, 'adm', e, key='k/adm-exp.webp')
    eo = make_experience(r1, 'u2', condition=1, minutes=1)
    # --- mitjans propis i d'altri
    make_media(r1, 'u1', key='k/u1.webp', thumb_key='k/u1_t.webp', minutes=2)
    make_media(r1, 'u2', key='k/u2.webp', minutes=3)
    make_media(r1, 'u3', key='k/h.webp', status=HIDDEN, minutes=4)
    # --- dubtes i respostes (cascada: dubte → respostes d'altres; resposta pròpia → fills d'altres)
    d_own = make_doubt(r1, 'u1')
    a_by_u2_in_own = make_answer(d_own, 'u2')
    d_other = make_doubt(r1, 'u2', minutes=1)
    a_own = make_answer(d_other, 'u1')
    a_child = make_answer(d_other, 'u3', parent=a_own, minutes=1)
    a_keep = make_answer(d_other, 'u3', minutes=2)
    # --- propostes (creador i revisor)
    p_creator = make_proposal(creator='u1', comment='meu')
    p_reviewer = make_proposal(creator='u2', status='approved', reviewer='u1', comment='seu', minutes=1)
    # --- intents de pujada
    i_pending = make_intent('u1', 'avatar')
    i_done = make_intent('u1', 'avatar', status='confirmed', result_key='a/u1.webp')
    i_other = make_intent('u2', 'avatar')
    # --- moderació: denunciant (normal i CSAM), autor del mitjà, resolutor, avisos
    rep_normal = make_report(r1, 'k/u2.webp', 'u1', 'hate_speech', creator='u2')
    rep_csam = make_report(r1, 'k/x.webp', 'u1', 'child_sexual_abuse', creator='u2', details='evidència', minutes=1)
    rep_hidden = make_report(r1, 'k/h.webp', 'u1', 'hate_speech', creator='u3', minutes=2)
    rep_about_u1 = make_report(r1, 'k/u1.webp', 'u2', 'hate_speech', creator='u1', minutes=3)
    rep_resolved_by = make_report(r1, 'k/u2.webp', 'u4', 'hate_speech', creator='u2', status='resolved',
                                  resolved_by='u1', minutes=4)
    n_own = make_notice('u1', 'strike')
    n_other = make_notice('u2', 'strike')
    # --- auditoria: normal i legal_hold
    sql("INSERT INTO audit.audit_logs (actor_uid, subject_uid, action, metadata, legal_hold, expire_at) VALUES "
        "('u1', NULL, 'media.list', '{}', false, now() + interval '1 year'), "
        "('u1', 'u1', 'user.age_confirmed', '{}', true, now() + interval '5 years'), "
        "('u2', NULL, 'media.list', '{}', false, now() + interval '1 year')")
    assert delete(client, 'u1').status_code == 204

    # cascada
    assert not user_exists('u1')
    assert sql("SELECT count(*) FROM users.user_public_profiles WHERE uid = 'u1'")[0][0] == 0
    assert sql("SELECT count(*) FROM users.user_avatars WHERE user_uid = 'u1'")[0][0] == 0
    assert list_rows(FAV, 'u1') == [] and list_rows(VIS, 'u1') == [] and len(list_rows(FAV, 'u2')) == 1
    assert participant_rows(v) == {'u2': 1}
    assert renovation_row(cur) is None and participants_of(cur) == [] and expelled_of(cur) == []
    assert participants_of(alien) == ['u3'] and expelled_of(alien2) == [] and participants_of(alien2) == ['u3']
    assert exp_ids() == [eo]
    assert sql("SELECT key FROM refuges.refuge_media ORDER BY key") == [('k/h.webp',), ('k/u2.webp',)]
    assert doubt_ids() == [d_other]
    assert sorted(answer_ids()) == sorted([a_keep])                       # resposta pròpia i el seu fill cauen
    assert a_by_u2_in_own not in answer_ids() and a_child not in answer_ids()
    assert [str(x[0]) for x in sql('SELECT id FROM moderation.upload_intents')] == [i_other]
    assert i_pending and i_done
    # SET NULL / anonimització
    assert renovation_row(past)['creator_uid'] is None and link_of(past) is None
    assert renovation_row(alien)['creator_uid'] == 'u2' and link_of(alien) is not None
    assert proposal_row(p_creator)['creator_uid'] is None and proposal_row(p_creator)['comment'] is None
    assert proposal_row(p_reviewer)['reviewer_uid'] is None and proposal_row(p_reviewer)['comment'] == 'seu'
    # moderació
    assert report_row(rep_normal) is None and report_row(rep_hidden) is None
    csam = report_row(rep_csam)
    assert csam['reporter_uid'] is None and csam['anonymized_at'] is not None and csam['details'] == 'evidència'
    assert report_row(rep_about_u1)['media_creator_uid'] is None
    assert report_row(rep_resolved_by)['resolved_by'] is None
    assert [n['id'] for n in notice_rows()] == [n_other] and n_own
    [auto] = [x for x in report_rows(source='automatic')]
    assert auto['media_key'] == 'k/h.webp' and auto['details'] == 'reporter_account_deleted'
    # auditoria: normals de u1 fora, legal_hold desvinculada, la d'altri intacta, + user.deleted sense identificador
    dump = audit_rows()
    assert sorted(x['action'] for x in dump) == ['media.list', 'user.age_confirmed', 'user.deleted']
    for x in dump:
        assert 'u1' not in (x['actor_uid'], x['subject_uid']) and 'u1' not in str(x['metadata'])
    [hold] = [x for x in dump if x['action'] == 'user.age_confirmed']
    assert hold['legal_hold'] is True and hold['actor_uid'] is None and hold['subject_uid'] is None
    # R2
    assert set(r2_deleted(r2)) == {'a/u1.webp', 'a/u1_t.webp', 'k/adm-exp.webp', 'k/u1.webp', 'k/u1_t.webp',
                                   f'quarantine/{i_pending}'}
    assert sql('SELECT count(*) FROM refuges.refuges')[0][0] == 2


def test_mitjana_de_condicio_del_refugi_no_es_toca(client, world):
    from apps.experiences.tests.helpers import make_experience, refuge_state
    r = world[0]
    make_experience(r, 'u1', condition=3)
    make_experience(r, 'u2', condition=0, minutes=1)
    state = refuge_state(r)
    assert delete(client, 'u1').status_code == 204
    assert refuge_state(r) == state


# =================================== pressupost de consultes ===================================

def _populate(n, r):
    from apps.experiences.tests.helpers import make_exp_media, make_experience
    for i in range(n):
        make_media(r, 'u1', key=f'k/m{i}.webp', thumb_key=f'k/m{i}_t.webp', minutes=i)
        e = make_experience(r, 'u1', minutes=100 + i)
        make_exp_media(r, 'adm', e, key=f'k/e{i}.webp', minutes=200 + i)
        make_intent('u1', 'avatar')


def test_pressupost_de_consultes_del_delete_amb_contingut(client, world):
    _populate(2, world[0])
    make_avatar('u1', key='a/u1.webp')
    with QueryCounter() as q:
        assert delete(client, 'u1').status_code == 204
    assert q.count <= 25, (q.count, q.queries)


def test_cap_n_mes_1_a_la_recollida_de_claus(client, world):
    counts = []
    for uid, n in (('u1', 1), ('u2', 12)):
        for i in range(n):
            make_media(world[0], uid, key=f'k/{uid}-{i}.webp', thumb_key=f'k/{uid}-{i}_t.webp', minutes=i)
        from apps.experiences.tests.helpers import make_exp_media, make_experience
        for i in range(n):
            e = make_experience(world[1], uid, minutes=50 + i)
            make_exp_media(world[1], 'adm', e, key=f'k/e-{uid}-{i}.webp', minutes=80 + i)
            make_intent(uid, 'avatar')
        with QueryCounter() as q:
            assert delete(client, uid).status_code == 204
        counts.append(q.count)
    assert counts[0] == counts[1], counts


# =================================== estructura del codi ===================================

def test_firestore_steps_ha_desaparegut_i_services_no_importa_firestore():
    from apps.accounts import services
    text = Path(services.__file__).read_text(encoding='utf-8')
    assert not hasattr(services, '_firestore_steps') and '_firestore_steps' not in text
    imports = re.findall(r'^\s*(?:from|import)\s+.*$', text, re.M)
    assert not [i for i in imports if re.search(r'firestore|api\.controllers|api\.daos', i, re.I)], imports


def test_la_vista_delete_no_usa_has_profile():
    from rest_framework.test import APIRequestFactory
    from apps.accounts.views import UserDetailAPIView
    view = UserDetailAPIView()
    view.request = APIRequestFactory().delete('/api/users/u1/')
    view.request.method = 'DELETE'
    names = [type(p).__name__ for p in view.get_permissions()]
    assert names == ['IsAuthenticated', 'IsSameUser']
    view.request.method = 'GET'
    assert 'HasProfile' in [type(p).__name__ for p in view.get_permissions()]
