"""
Reformes (chunk 5): taules de l'schema `activity`, FK reals, funcions i *triggers*, RLS i grants
(docs/design/postgres-schema.md §2.12, §2.12.1, §2.13, §2.14, §6.3, §7.2).

Requereix l'extensió `btree_gist` (bootstrap del propietari de la BD, `core.0001`) per a l'`EXCLUDE` de solapaments.
"""
import django.contrib.postgres.constraints
import django.contrib.postgres.fields.ranges
import django.db.models.deletion
import django.db.models.functions.text
import django.db.models.lookups
from django.db import migrations, models

import apps.core.db_functions
from apps.core.migration_utils import PostgresRunSQL, disable_rls_sql, drop_policy_sql, enable_rls_sql
from apps.core.rls import create_policy_sql

REN, LNK, PAR, EXP = ('activity.renovations', 'activity.renovation_group_links', 'activity.renovation_participants',
                      'activity.renovation_expelled')

# ---------- Funcions i triggers (SECURITY DEFINER: llegeixen/esborren saltant la RLS, com a propietari) ----------

FN_ANONYMIZE = """
CREATE FUNCTION activity.fn_renovation_anonymize() RETURNS trigger
  LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, activity AS $$
BEGIN
  IF OLD.creator_uid IS NOT NULL AND NEW.creator_uid IS NULL THEN
    DELETE FROM activity.renovation_group_links WHERE renovation_id = NEW.id;
  END IF;
  RETURN NULL;
END $$"""

# D33: es torna a llegir la fila actual perquè una reforma creada i després esborrada o anonimitzada a la mateixa
# transacció no faci fallar el COMMIT.
FN_REQUIRES_LINK = """
CREATE FUNCTION activity.fn_renovation_requires_link() RETURNS trigger
  LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, activity AS $$
BEGIN
  IF EXISTS (SELECT 1 FROM activity.renovations r WHERE r.id = NEW.id AND r.creator_uid IS NOT NULL)
     AND NOT EXISTS (SELECT 1 FROM activity.renovation_group_links l WHERE l.renovation_id = NEW.id) THEN
    RAISE EXCEPTION 'renovation requires group_link'
      USING ERRCODE = 'check_violation', CONSTRAINT = 'renovations_requires_group_link_ck';
  END IF;
  RETURN NULL;
END $$"""

FN_MEMBER_GUARD = """
CREATE FUNCTION activity.fn_renovation_member_guard() RETURNS trigger
  LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, activity AS $$
BEGIN
  IF TG_TABLE_NAME = 'renovation_participants' THEN
    IF EXISTS (SELECT 1 FROM activity.renovation_expelled e
               WHERE e.renovation_id = NEW.renovation_id AND e.user_uid = NEW.user_uid) THEN
      RAISE EXCEPTION 'user expelled'
        USING ERRCODE = 'check_violation', CONSTRAINT = 'renovation_participants_not_expelled_ck';
    END IF;
    IF EXISTS (SELECT 1 FROM activity.renovations r
               WHERE r.id = NEW.renovation_id AND r.creator_uid = NEW.user_uid) THEN
      RAISE EXCEPTION 'creator cannot join'
        USING ERRCODE = 'check_violation', CONSTRAINT = 'renovation_participants_not_creator_ck';
    END IF;
  ELSE
    IF EXISTS (SELECT 1 FROM activity.renovation_participants p
               WHERE p.renovation_id = NEW.renovation_id AND p.user_uid = NEW.user_uid) THEN
      RAISE EXCEPTION 'participant must be removed first'
        USING ERRCODE = 'check_violation', CONSTRAINT = 'renovation_expelled_not_participant_ck';
    END IF;
  END IF;
  RETURN NEW;
END $$"""

# ---------- FK reals (ON DELETE del DDL, §6.3) ----------

FOREIGN_KEYS = [
    # (taula, columna, destí, columna destí, ON DELETE)
    (REN, 'refuge_id', 'refuges.refuges', 'id', 'CASCADE'),
    (REN, 'creator_uid', 'users.users', 'uid', 'SET NULL'),          # reformes passades anònimes
    (LNK, 'renovation_id', REN, 'id', 'CASCADE'),
    (PAR, 'renovation_id', REN, 'id', 'CASCADE'),
    (PAR, 'user_uid', 'users.users', 'uid', 'CASCADE'),
    (EXP, 'renovation_id', REN, 'id', 'CASCADE'),
    (EXP, 'user_uid', 'users.users', 'uid', 'CASCADE'),
]


def _fk_name(table, column):
    return f"{table.split('.')[1]}_{column}_fk"


# ---------- Polítiques de RLS (§2.12–§2.14); les columnes es qualifiquen per no confondre-les amb les del subquery ----------

def _creator_of(table):
    return ('EXISTS (SELECT 1 FROM activity.renovations r '
            f'WHERE r.id = {table}.renovation_id AND r.creator_uid = {{U}})')


LINK_OWNER = _creator_of('renovation_group_links')
PAR_OWNER = _creator_of('renovation_participants')
EXP_OWNER = _creator_of('renovation_expelled')

POLICIES = [
    create_policy_sql('renov_select', REN, 'SELECT', using='{U} IS NOT NULL OR {SYS}'),
    create_policy_sql('renov_insert', REN, 'INSERT', with_check='creator_uid = {U} OR {SYS}'),
    create_policy_sql('renov_update', REN, 'UPDATE', using='creator_uid = {U} OR {SYS}',
                      with_check='creator_uid = {U} OR {SYS}'),
    create_policy_sql('renov_delete', REN, 'DELETE', using='creator_uid = {U} OR {SYS}'),

    create_policy_sql(
        'rlinks_select', LNK, 'SELECT',
        using='{ADM} OR {SYS} OR ' + LINK_OWNER + ' OR EXISTS (SELECT 1 FROM activity.renovation_participants p '
              'WHERE p.renovation_id = renovation_group_links.renovation_id AND p.user_uid = {U})'),
    create_policy_sql('rlinks_insert', LNK, 'INSERT', with_check='{SYS} OR ' + LINK_OWNER),
    create_policy_sql('rlinks_update', LNK, 'UPDATE', using='{SYS} OR ' + LINK_OWNER,
                      with_check='{SYS} OR ' + LINK_OWNER),

    create_policy_sql('rparts_select', PAR, 'SELECT', using='{U} IS NOT NULL OR {SYS}'),
    create_policy_sql('rparts_insert', PAR, 'INSERT', with_check='user_uid = {U} OR {SYS}'),
    # sortir un mateix o expulsar (el creador)
    create_policy_sql('rparts_delete', PAR, 'DELETE', using='user_uid = {U} OR {SYS} OR ' + PAR_OWNER),

    create_policy_sql('rexp_select', EXP, 'SELECT', using='user_uid = {U} OR {ADM} OR {SYS} OR ' + EXP_OWNER),
    create_policy_sql('rexp_insert', EXP, 'INSERT', with_check='{SYS} OR ' + EXP_OWNER),
]
POLICY_NAMES = [('renov_select', REN), ('renov_insert', REN), ('renov_update', REN), ('renov_delete', REN),
                ('rlinks_select', LNK), ('rlinks_insert', LNK), ('rlinks_update', LNK),
                ('rparts_select', PAR), ('rparts_insert', PAR), ('rparts_delete', PAR),
                ('rexp_select', EXP), ('rexp_insert', EXP)]

GRANTS = [(REN, 'SELECT, INSERT, UPDATE, DELETE'), (LNK, 'SELECT, INSERT, UPDATE'),
          (PAR, 'SELECT, INSERT, DELETE'), (EXP, 'SELECT, INSERT')]

FORWARD_SQL = [
    # PK amb el nom del disseny (Django crea `<taula>_pkey`)
    f'ALTER TABLE {PAR} RENAME CONSTRAINT renovation_participants_pkey TO renovation_participants_pk',
    f'ALTER TABLE {EXP} RENAME CONSTRAINT renovation_expelled_pkey TO renovation_expelled_pk',
    *[f'ALTER TABLE {t} ADD CONSTRAINT {_fk_name(t, c)} FOREIGN KEY ({c}) REFERENCES {rt} ({rc}) '
      f'ON DELETE {action} DEFERRABLE INITIALLY DEFERRED' for t, c, rt, rc, action in FOREIGN_KEYS],
    FN_ANONYMIZE, FN_REQUIRES_LINK, FN_MEMBER_GUARD,
    f'CREATE TRIGGER renovations_anonymize AFTER UPDATE OF creator_uid ON {REN} '
    f'FOR EACH ROW EXECUTE FUNCTION activity.fn_renovation_anonymize()',
    f'CREATE CONSTRAINT TRIGGER renovations_requires_link AFTER INSERT ON {REN} '
    f'DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION activity.fn_renovation_requires_link()',
    f'CREATE TRIGGER renovation_participants_guard BEFORE INSERT ON {PAR} '
    f'FOR EACH ROW EXECUTE FUNCTION activity.fn_renovation_member_guard()',
    f'CREATE TRIGGER renovation_expelled_guard BEFORE INSERT ON {EXP} '
    f'FOR EACH ROW EXECUTE FUNCTION activity.fn_renovation_member_guard()',
    *[enable_rls_sql(t) for t, _ in GRANTS],
    *POLICIES,
    *[f'GRANT {privs} ON {t} TO app' for t, privs in GRANTS],
]

REVERSE_SQL = [
    *[f'REVOKE ALL ON {t} FROM app' for t, _ in reversed(GRANTS)],
    *[drop_policy_sql(n, t) for n, t in reversed(POLICY_NAMES)],
    *[disable_rls_sql(t) for t, _ in reversed(GRANTS)],
    f'DROP TRIGGER renovation_expelled_guard ON {EXP}',
    f'DROP TRIGGER renovation_participants_guard ON {PAR}',
    f'DROP TRIGGER renovations_requires_link ON {REN}',
    f'DROP TRIGGER renovations_anonymize ON {REN}',
    'DROP FUNCTION activity.fn_renovation_member_guard()',
    'DROP FUNCTION activity.fn_renovation_requires_link()',
    'DROP FUNCTION activity.fn_renovation_anonymize()',
    *[f'ALTER TABLE {t} DROP CONSTRAINT {_fk_name(t, c)}' for t, c, _, _, _ in reversed(FOREIGN_KEYS)],
    f'ALTER TABLE {EXP} RENAME CONSTRAINT renovation_expelled_pk TO renovation_expelled_pkey',
    f'ALTER TABLE {PAR} RENAME CONSTRAINT renovation_participants_pk TO renovation_participants_pkey',
]


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('core', '0001_initial'),
        ('accounts', '0002_user_lists'),
        ('refuges', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Renovation',
            fields=[
                ('id', models.UUIDField(db_default=models.Func(function='uuidv7', output_field=models.UUIDField()), editable=False, primary_key=True, serialize=False)),
                ('ini_date', models.DateField()),
                ('fin_date', models.DateField()),
                ('description', models.TextField()),
                ('materials_needed', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(db_default=apps.core.db_functions.TransactionNow())),
                ('creator', models.ForeignKey(blank=True, db_column='creator_uid', db_constraint=False, db_index=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='accounts.useraccount')),
                ('refuge', models.ForeignKey(db_column='refuge_id', db_constraint=False, db_index=False, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='refuges.refuge')),
            ],
            options={
                'db_table': 'activity"."renovations',
            },
        ),
        migrations.CreateModel(
            name='RenovationGroupLink',
            fields=[
                ('renovation', models.OneToOneField(db_column='renovation_id', db_constraint=False, on_delete=django.db.models.deletion.DO_NOTHING, primary_key=True, related_name='group_link_row', serialize=False, to='renovations.renovation')),
                ('group_link', models.TextField()),
            ],
            options={
                'db_table': 'activity"."renovation_group_links',
            },
        ),
        migrations.CreateModel(
            name='RenovationParticipant',
            fields=[
                ('pk', models.CompositePrimaryKey('renovation', 'user', blank=True, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(db_default=apps.core.db_functions.TransactionNow())),
                ('renovation', models.ForeignKey(db_column='renovation_id', db_constraint=False, db_index=False, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='renovations.renovation')),
                ('user', models.ForeignKey(db_column='user_uid', db_constraint=False, db_index=False, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='accounts.useraccount')),
            ],
            options={
                'db_table': 'activity"."renovation_participants',
            },
        ),
        migrations.CreateModel(
            name='RenovationExpelled',
            fields=[
                ('pk', models.CompositePrimaryKey('renovation', 'user', blank=True, editable=False, primary_key=True, serialize=False)),
                ('expelled_at', models.DateTimeField(db_default=apps.core.db_functions.TransactionNow())),
                ('renovation', models.ForeignKey(db_column='renovation_id', db_constraint=False, db_index=False, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='renovations.renovation')),
                ('user', models.ForeignKey(db_column='user_uid', db_constraint=False, db_index=False, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='accounts.useraccount')),
            ],
            options={
                'db_table': 'activity"."renovation_expelled',
            },
        ),
        migrations.AddIndex(
            model_name='renovation',
            index=models.Index(fields=['refuge', 'fin_date', 'ini_date'], name='renovations_refuge_fin_idx'),
        ),
        migrations.AddIndex(
            model_name='renovation',
            index=models.Index(fields=['fin_date', 'ini_date'], name='renovations_fin_ini_idx'),
        ),
        migrations.AddIndex(
            model_name='renovation',
            index=models.Index(condition=models.Q(('creator__isnull', False)), fields=['creator', 'fin_date'], name='renovations_creator_fin_idx'),
        ),
        migrations.AddIndex(
            model_name='renovationparticipant',
            index=models.Index(fields=['user', 'renovation'], name='rparts_user_reno_idx'),
        ),
        migrations.AddIndex(
            model_name='renovationexpelled',
            index=models.Index(fields=['user', 'renovation'], name='rexp_user_reno_idx'),
        ),
        migrations.AddConstraint(
            model_name='renovation',
            constraint=models.CheckConstraint(condition=models.Q(('ini_date__lte', models.F('fin_date'))), name='renovations_dates_ck'),
        ),
        migrations.AddConstraint(
            model_name='renovation',
            constraint=models.CheckConstraint(condition=models.Q(django.db.models.lookups.Exact(models.Func(models.F('description'), models.Value(' \t\n\r\x0c\x0b'), function='btrim', output_field=models.TextField()), models.Value('')), _negated=True), name='renovations_description_ck'),
        ),
        migrations.AddConstraint(
            model_name='renovation',
            constraint=django.contrib.postgres.constraints.ExclusionConstraint(expressions=[('refuge', '='), (models.Func(models.F('ini_date'), models.F('fin_date'), models.Value('[]'), function='daterange', output_field=django.contrib.postgres.fields.ranges.DateRangeField()), '&&')], name='renovations_no_overlap'),
        ),
        migrations.AddConstraint(
            model_name='renovationgrouplink',
            constraint=models.CheckConstraint(condition=models.Q(('group_link__iregex', '^https?://'), django.db.models.lookups.LessThanOrEqual(django.db.models.functions.text.Length('group_link'), 2048)), name='renovation_group_links_url_ck'),
        ),
        PostgresRunSQL(sql=FORWARD_SQL, reverse_sql=REVERSE_SQL),
    ]
