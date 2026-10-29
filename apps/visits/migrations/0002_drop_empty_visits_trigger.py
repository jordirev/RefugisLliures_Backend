"""
Una visita sense participants s'esborra sola (decisió del PO): trigger `AFTER DELETE` de
`activity.refuge_visit_participants` + bloqueig assessor per `(refugi, data)` (docs/design/postgres-schema.md §2.10, §4.1).

- `activity.fn_visit_lock(refugi, data)`: `pg_advisory_xact_lock` sobre la clau de la visita. El criden `create_visit` i
  `remove_visitor` (rol `app`, per això porta `GRANT EXECUTE`) i el trigger. Serialitza «algú s'apunta» amb «se'n va l'últim»
  sense dependre de la fila de la visita (que pot no existir encara o ser esborrada entre mig) ni de privilegis de `app`
  (no té `UPDATE`, i `FOR SHARE/UPDATE` el demana). Compatible amb PgBouncer en mode transacció.
- `activity.fn_visit_drop_if_empty()`: `SECURITY DEFINER` (propietari `migrator`, salta la RLS: `app` només pot esborrar
  visites com a sistema) amb `search_path` fixat; **per sentència** (taula de transició `old_rows`): una sola execució per
  `DELETE`, també a la cascada `users.users` -> participants, amb els bloqueigs agafats en ordre `(refugi, data)` perquè
  dos esborrats concurrents amb visites en comú no es facin deadlock. Només mira les visites que encara existeixen: a
  la cascada visita -> participants (purga de 12 mesos, esborrat de refugi) no troba res i no fa res.
- Neteja única: les visites buides que ja hi ha (abans esborrades pel job diari) s'esborren ara.
"""
from django.db import migrations

from apps.core.migration_utils import PostgresRunSQL

FN_LOCK = """CREATE FUNCTION activity.fn_visit_lock(p_refuge uuid, p_date date) RETURNS void
  LANGUAGE sql SET search_path = pg_catalog AS $$
  SELECT pg_advisory_xact_lock(hashtextextended('visit:' || p_refuge::text || ':' || to_char(p_date, 'YYYY-MM-DD'), 0)) $$"""

FN_DROP_EMPTY = """CREATE FUNCTION activity.fn_visit_drop_if_empty() RETURNS trigger
  LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, activity AS $$
DECLARE v record;
BEGIN
  FOR v IN
    SELECT id, refuge_id, visit_date FROM activity.refuge_visits
     WHERE id IN (SELECT visit_id FROM old_rows)
     ORDER BY refuge_id, visit_date
  LOOP
    PERFORM activity.fn_visit_lock(v.refuge_id, v.visit_date);
    -- sentència nova després del bloqueig: veu els participants que acaben de comprometre els qui s'apuntaven
    DELETE FROM activity.refuge_visits r
     WHERE r.id = v.id
       AND NOT EXISTS (SELECT 1 FROM activity.refuge_visit_participants p WHERE p.visit_id = v.id);
  END LOOP;
  RETURN NULL;
END $$"""

FORWARD_SQL = [
    FN_LOCK,
    'REVOKE ALL ON FUNCTION activity.fn_visit_lock(uuid, date) FROM PUBLIC',
    'GRANT EXECUTE ON FUNCTION activity.fn_visit_lock(uuid, date) TO app',
    FN_DROP_EMPTY,
    'REVOKE ALL ON FUNCTION activity.fn_visit_drop_if_empty() FROM PUBLIC',
    'CREATE TRIGGER participants_drop_empty_visit AFTER DELETE ON activity.refuge_visit_participants '
    'REFERENCING OLD TABLE AS old_rows FOR EACH STATEMENT EXECUTE FUNCTION activity.fn_visit_drop_if_empty()',
    # Neteja única de les visites que ja són buides (el job diari deixa de fer-ho).
    'DELETE FROM activity.refuge_visits v WHERE NOT EXISTS '
    '(SELECT 1 FROM activity.refuge_visit_participants p WHERE p.visit_id = v.id)',
]

REVERSE_SQL = [
    'DROP TRIGGER participants_drop_empty_visit ON activity.refuge_visit_participants',
    'DROP FUNCTION activity.fn_visit_drop_if_empty()',
    'DROP FUNCTION activity.fn_visit_lock(uuid, date)',
]


class Migration(migrations.Migration):

    dependencies = [
        ('visits', '0001_initial'),
    ]

    operations = [
        PostgresRunSQL(sql=FORWARD_SQL, reverse_sql=REVERSE_SQL),
    ]
