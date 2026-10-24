"""Ajudes de test compartides pels dos arbres de tests (`api/tests` i `apps/*/tests`)."""


def fetch_all(conn, sql, params=None):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def fetch_one(conn, sql, params=None):
    rows = fetch_all(conn, sql, params)
    return rows[0] if rows else None
