"""
Esborrat d'usuari i `audit.audit_logs` (chunk 9; §2.1, §2.24, §8.5): `DELETE /api/users/{uid}/` (Firebase i R2 mockats).

- Files on l'usuari és `actor_uid` o `subject_uid`: s'esborren (cascada), **excepte** les `legal_hold`, que el *trigger*
  `users_detach_legal_hold` desvincula (`actor_uid`/`subject_uid` := NULL) i es conserven amb la resta de columnes
  intactes (`metadata` sense UID, `expire_at` a 5 anys).
- Les files d'altres usuaris no es toquen. Si Firebase falla, es desfà tot (també la desvinculació).
- El trigger funciona amb el rol `app` encara que no tingui `UPDATE` sobre la taula (`SECURITY DEFINER`).
"""
import pytest

from apps.moderation.tests.helpers import (
    api_delete, audit_rows, sql, user_claims)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration,
              pytest.mark.real_permissions]


def seed(actor, subject=None, action='media.report', legal_hold=False, metadata='{}', target_id=None):
    expire = "now() + interval '5 years'" if legal_hold else "now() + interval '365 days'"
    rows = sql(f'INSERT INTO audit.audit_logs (actor_uid, subject_uid, action, target_id, metadata, legal_hold, '
               f'expire_at) VALUES (%s, %s, %s, %s, %s::jsonb, %s, {expire}) RETURNING id',
               [actor, subject, action, target_id, metadata, legal_hold])
    return str(rows[0][0])


def ids():
    return {str(r[0]) for r in sql('SELECT id FROM audit.audit_logs')}


def row(audit_id):
    r = sql('SELECT actor_uid, subject_uid, action, target_id, metadata, legal_hold, expire_at, created_at '
            'FROM audit.audit_logs WHERE id = %s', [audit_id])
    return r[0] if r else None


def delete_user(client, uid):
    return api_delete(client, f'/api/users/{uid}/', user_claims(uid))


def test_les_files_normals_de_l_actor_i_del_subjecte_s_esborren(client, world):
    as_actor = seed('u2')
    as_subject = seed('adm', 'u2', 'moderation.user_blocked')
    both = seed('u2', 'u3', 'moderation.user_blocked')
    system_about_u2 = seed(None, 'u2', 'moderation.user_blocked')
    others = [seed('u3'), seed('adm', 'u3', 'moderation.user_blocked'), seed(None, None, 'moderation.auto_hide')]
    assert delete_user(client, 'u2').status_code == 204
    assert ids() == set(others)
    assert not {as_actor, as_subject, both, system_about_u2} & ids()


def test_les_files_legal_hold_es_desvinculen_i_es_conserven_senceres(client, world):
    meta = '{"reason": "csam_confirmed", "report_id": "abc"}'
    as_subject = seed('adm', 'u2', 'moderation.user_blocked', legal_hold=True, metadata=meta)
    as_actor = seed('u2', None, 'media.report', legal_hold=True, metadata='{"reason": "child_sexual_abuse"}',
                    target_id='refugis-lliures/x/a.webp')
    both = seed('u2', 'u2', 'user.age_confirmed', legal_hold=True)
    system_about_u2 = seed(None, 'u2', 'moderation.user_blocked', legal_hold=True, metadata=meta)
    before = {a: row(a) for a in (as_subject, as_actor, both, system_about_u2)}
    assert delete_user(client, 'u2').status_code == 204
    assert ids() == set(before)                                                   # cap fila perduda
    a = row(as_subject)
    assert (a[0], a[1]) == ('adm', None) and a[2:] == before[as_subject][2:]       # només el subjecte desvinculat
    b = row(as_actor)
    assert (b[0], b[1]) == (None, None) and b[2:] == before[as_actor][2:]
    c = row(both)
    assert (c[0], c[1]) == (None, None)
    d = row(system_about_u2)
    assert (d[0], d[1]) == (None, None) and d[4:] == before[system_about_u2][4:]


def test_barreja_legal_hold_i_normals_de_la_mateixa_persona(client, world):
    keep = seed('u2', None, 'moderation.hash_block', legal_hold=True)
    drop = seed('u2', None, 'media.list')
    delete_user(client, 'u2')
    assert ids() == {keep} and row(keep)[0] is None


def test_cap_fila_conservada_porta_l_uid_de_l_usuari_esborrat(client, world):
    seed('u2', 'u2', 'moderation.user_blocked', legal_hold=True, metadata='{"reason": "moderation_hash_match"}',
         target_id=None)
    delete_user(client, 'u2')
    dump = str(audit_rows())
    assert 'u2' not in dump


def test_les_files_d_altres_usuaris_no_es_toquen(client, world):
    mine = seed('u3', 'u3', 'user.age_confirmed', legal_hold=True)
    before = row(mine)
    seed('u2', None, 'media.report', legal_hold=True)
    delete_user(client, 'u2')
    assert row(mine) == before


def test_si_firebase_falla_es_desfa_la_desvinculacio_i_l_esborrat(client, world, firebase_accounts):
    hold = seed('u2', None, 'media.report', legal_hold=True)
    normal = seed('u2')
    firebase_accounts.delete_user.side_effect = RuntimeError('firebase caigut')
    assert delete_user(client, 'u2').status_code == 500
    assert row(hold)[0] == 'u2' and row(normal) is not None


def test_el_trigger_no_necessita_update_per_a_app(client, world):
    """`app` no té `UPDATE` sobre `audit_logs`; el trigger (propietari) sí que pot desvincular."""
    hold = seed('u2', None, 'media.report', legal_hold=True)
    assert delete_user(client, 'u2').status_code == 204
    assert row(hold)[0] is None


def test_esborrar_un_admin_desvincula_les_seves_files_legal_hold_de_moderacio(client, world):
    hold = seed('adm', 'u1', 'moderation.user_blocked', legal_hold=True, metadata='{"reason": "csam_confirmed"}')
    plain = seed('adm', None, 'moderation.reports_list')
    delete_user(client, 'adm')
    assert ids() == {hold} and row(hold)[:2] == (None, 'u1')
