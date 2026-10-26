"""Fixtures del domini visites (chunk 4)."""
import pytest

from apps.visits.tests.helpers import visit_models


@pytest.fixture
def VM():
    """Mòdul `apps.visits.models` (falla amb ModuleNotFoundError fins que l'implementador el creï)."""
    return visit_models()


@pytest.fixture
def world():
    """Dos usuaris amb perfil (`u1`, `u2`) i dos refugis (`R1`, `R2`)."""
    from apps.visits.tests.helpers import make_refuge, make_user
    make_user('u1', username='Anna')
    make_user('u2', username='Bernat')
    return make_refuge(name='R1'), make_refuge(name='R2', lat=43.0)


@pytest.fixture
def commit_world(migrator_db):
    """Dades **comesses de debò** (connexió `migrator`, que salta la RLS) per als tests amb diversos fils/connexions.

    `pytest-django` no pot aïllar-les (cada fil té la seva connexió): s'esborren abans i després amb el propietari
    (`DELETE` de `users.users` i `refuges.refuges` cascadeja la resta). Retorna `(refuge_id, [uids])` via `seed(n)`.
    """
    def wipe():
        with migrator_db.cursor() as cur:
            cur.execute('DELETE FROM users.users')
            cur.execute('DELETE FROM refuges.refuges')

    def seed(n_users=2):
        uids = [f'c{i}' for i in range(n_users)]
        with migrator_db.cursor() as cur:
            for uid in uids:
                cur.execute('INSERT INTO users.users (uid) VALUES (%s)', [uid])
                cur.execute('INSERT INTO users.user_public_profiles (uid) VALUES (%s)', [uid])
            cur.execute("INSERT INTO refuges.refuges (name, coord, description) VALUES "
                        "('Concurrent', ST_GeogFromText('SRID=4326;POINT(1.5 42.5)'), 'd') RETURNING id")
            rid = cur.fetchone()[0]
        return rid, uids

    wipe()
    yield seed
    wipe()
