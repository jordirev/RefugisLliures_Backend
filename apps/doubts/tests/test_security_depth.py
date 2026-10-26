"""Seguretat: arbres de respostes absurdament profunds (DoS per recursió a la cascada de la BD o en serialitzar)."""
import pytest

from apps.doubts.tests.helpers import (
    DOUBTS, answer_ids, answer_url, api_delete, api_get, doubt_ids, doubt_url, list_url, make_doubt, sql, user_claims)

pytestmark = [pytest.mark.django_db, pytest.mark.integration, pytest.mark.real_permissions]

DEPTH = 5000


def _deep_chain(doubt_id, depth=DEPTH):
    """Cadena de `depth` respostes (cada una filla de l'anterior) amb un sol INSERT."""
    ids = [str(r[0]) for r in sql('SELECT uuidv7() FROM generate_series(1, %s)', [depth])]
    sql('''INSERT INTO activity.answers (id, doubt_id, creator_uid, parent_answer_id, message)
           SELECT t.id, %s, 'u2', t.parent, 'm'
           FROM unnest(%s::uuid[], %s::uuid[]) AS t(id, parent)''',
        [doubt_id, ids, [None] + ids[:-1]])
    return ids


def test_llistar_un_arbre_molt_profund_no_recursiona(client, world):
    d = make_doubt(world[0], 'u1')
    _deep_chain(d)
    r = api_get(client, list_url(world[0].pk), user_claims('u1'))
    assert r.status_code == 200 and len(r.json()[0]['answers']) == DEPTH


def test_esborrar_un_arbre_molt_profund_no_dona_500(client, world):
    d = make_doubt(world[0], 'u1')
    ids = _deep_chain(d)
    r = api_delete(client, answer_url(d, ids[0]), user_claims('u2'))
    assert r.status_code == 204 and answer_ids(d) == []
    d2 = make_doubt(world[0], 'u1')
    _deep_chain(d2)
    assert api_delete(client, doubt_url(d2), user_claims('u1')).status_code == 204
    assert d2 not in doubt_ids()


# ---------- entrades estranyes al cos ----------

def test_surrogat_solitari_al_missatge_no_dona_500(client, world):
    from apps.doubts.tests.helpers import api_post
    d = make_doubt(world[0], 'u1')
    for url, body in ((DOUBTS, {'refuge_id': str(world[0].pk), 'message': 'a\ud800b'}),
                      (f'{DOUBTS}{d}/answers/', {'message': 'a\ud800b'})):
        r = api_post(client, url, user_claims('u2'), body)
        assert r.status_code < 500, r.content
    assert answer_ids(d) == []


def test_cos_enorme_es_rebutja_sense_500(client, world):
    from apps.doubts.tests.helpers import api_post
    d = make_doubt(world[0], 'u1')
    r = api_post(client, f'{DOUBTS}{d}/answers/', user_claims('u2'), {'message': 'x' * 5_000_000})
    assert 400 <= r.status_code < 500 and answer_ids(d) == []
