"""
Models de reformes (chunk 5, §2.12–§2.14, §6.4) i les seves restriccions i *triggers*, amb el rol `app`.

Contracte de models (`apps/renovations/models.py`):
- `Renovation` (`db_table 'activity"."renovations'`): `id` (UUID v7 generat per la BD: `db_default`), `refuge` (FK a
  `refuges.Refuge`, `db_column='refuge_id'`), `creator` (FK nul·la a `accounts.UserAccount`, `db_column='creator_uid'`),
  `ini_date`, `fin_date`, `description`, `materials_needed` (nul·la), `created_at` (`db_default=Now()`);
  `CheckConstraint` `renovations_dates_ck` i `ExclusionConstraint` `renovations_no_overlap`.
- `RenovationGroupLink` (`activity"."renovation_group_links`): `renovation` = `OneToOneField(primary_key=True,
  related_name='group_link_row')`, `group_link`.
- `RenovationParticipant` / `RenovationExpelled`: `pk = CompositePrimaryKey('renovation', 'user')`, `created_at` /
  `expelled_at`.
- Totes les FK són `DO_NOTHING` + `db_constraint=False` (les cascades i el `SET NULL` són del DDL, GOTCHAS #12).

Els *triggers* es proven amb SQL pla: els que són diferits (`renovations_requires_link`) es forcen amb
`SET CONSTRAINTS ALL IMMEDIATE`, perquè dins la transacció del test mai arriba el `COMMIT`.
"""
import uuid
from datetime import date

import pytest
from django.db import IntegrityError, connection, models, transaction

from apps.core.rls import rls_context, system_context
from apps.renovations.tests.helpers import (
    LINK, as_owner, constraint_name, count_renovations, day, expelled_of, link_of, make_refuge, make_renovation, make_user,
    participants_of, renovation_row, sql)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.models, pytest.mark.integration,
              pytest.mark.real_permissions]

INSERT_RENO = ('INSERT INTO activity.renovations (refuge_id, creator_uid, ini_date, fin_date, description) '
               'VALUES (%s, %s, %s, %s, %s) RETURNING id')


@pytest.fixture
def w(world):
    return world


# ----------------------------------------------- definició dels models -----------------------------------------------

@pytest.mark.parametrize('name,table', [
    ('Renovation', 'activity"."renovations'), ('RenovationGroupLink', 'activity"."renovation_group_links'),
    ('RenovationParticipant', 'activity"."renovation_participants'),
    ('RenovationExpelled', 'activity"."renovation_expelled')])
def test_db_table(RN, name, table):
    assert getattr(RN, name)._meta.db_table == table


@pytest.mark.parametrize('name', ['RenovationParticipant', 'RenovationExpelled'])
def test_pk_composta_sense_id(RN, name):
    m = getattr(RN, name)
    assert isinstance(m._meta.pk, models.CompositePrimaryKey)
    assert tuple(m._meta.pk.field_names) == ('renovation', 'user')
    assert 'id' not in {f.name for f in m._meta.get_fields()}


@pytest.mark.parametrize('name,field,column', [
    ('Renovation', 'refuge', 'refuge_id'), ('Renovation', 'creator', 'creator_uid'),
    ('RenovationGroupLink', 'renovation', 'renovation_id'),
    ('RenovationParticipant', 'renovation', 'renovation_id'), ('RenovationParticipant', 'user', 'user_uid'),
    ('RenovationExpelled', 'renovation', 'renovation_id'), ('RenovationExpelled', 'user', 'user_uid')])
def test_les_fk_son_do_nothing_sense_constraint_de_django(RN, name, field, column):
    f = getattr(RN, name)._meta.get_field(field)
    assert f.remote_field.on_delete is models.DO_NOTHING and f.db_constraint is False, f'{name}.{field}'
    assert f.column == column


def test_group_link_es_one_to_one_pk_amb_related_name(RN):
    f = RN.RenovationGroupLink._meta.get_field('renovation')
    assert isinstance(f, models.OneToOneField) and f.primary_key
    assert f.remote_field.related_name == 'group_link_row'


def test_creator_pot_ser_nul(RN):
    assert RN.Renovation._meta.get_field('creator').null is True


def test_constraints_declarades_amb_els_noms_del_disseny(RN):
    names = {c.name for c in RN.Renovation._meta.constraints}
    assert {'renovations_dates_ck', 'renovations_no_overlap'} <= names


# ----------------------------------------------- creació amb l'ORM -----------------------------------------------

def test_crear_una_reforma_usa_els_defaults_de_la_bd(w, RN):
    with system_context():
        r = RN.Renovation.objects.create(refuge_id=w.refuge.pk, creator_id='u1', ini_date=day(1), fin_date=day(2),
                                         description='Pintar')
        RN.RenovationGroupLink.objects.create(renovation_id=r.pk, group_link=LINK)
    assert isinstance(r.pk, uuid.UUID) and r.pk.version == 7
    assert r.created_at is not None and r.materials_needed is None


def test_crear_participant_i_expulsat_amb_pk_composta(w, RN):
    rid = make_renovation(w.refuge, 'u1')
    with system_context():
        RN.RenovationParticipant.objects.create(renovation_id=rid, user_id='u2')
        RN.RenovationExpelled.objects.create(renovation_id=rid, user_id='u3')
        assert RN.RenovationParticipant.objects.filter(renovation_id=rid, user_id='u2').exists()
        assert RN.RenovationExpelled.objects.filter(renovation_id=rid, user_id='u3').exists()
    assert participants_of(rid) == ['u2'] and expelled_of(rid) == ['u3']


def test_enllac_accessible_pel_related_name(w, RN):
    rid = make_renovation(w.refuge, 'u1', link='https://t.me/grup')
    with rls_context(uid='u1'):
        assert RN.Renovation.objects.get(pk=rid).group_link_row.group_link == 'https://t.me/grup'


# ----------------------------------------------- CHECK de dates i descripció -----------------------------------------------

def test_reforma_d_un_dia_es_valida(w):
    rid = make_renovation(w.refuge, 'u1', ini=day(3), fin=day(3))
    assert renovation_row(rid)['ini_date'] == renovation_row(rid)['fin_date']


def test_ini_posterior_a_fin_es_rebutjada_pel_check(w):
    with pytest.raises(IntegrityError, match='renovations_dates_ck'):
        with transaction.atomic():
            make_renovation(w.refuge, 'u1', ini=day(4), fin=day(3))
    assert count_renovations() == 0


@pytest.mark.parametrize('description', ['', '   '])
def test_descripcio_buida_o_en_blanc_es_rebutjada(w, description):
    with pytest.raises(IntegrityError, match='renovations_description_ck'):
        with transaction.atomic():
            make_renovation(w.refuge, 'u1', description=description)


def test_les_dates_no_poden_ser_nul_les(w):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            sql(INSERT_RENO, [w.refuge.pk, 'u1', None, day(3), 'x'])


# ----------------------------------------------- EXCLUDE de solapaments -----------------------------------------------

@pytest.mark.parametrize('ini,fin,overlaps', [
    (10, 15, True),         # idèntica
    (15, 20, True),         # toca l'últim dia (límits inclusius)
    (5, 10, True),          # toca el primer dia
    (12, 13, True),         # dins
    (1, 30, True),          # envolta
    (16, 20, False),        # el dia següent
    (1, 9, False),          # el dia anterior
])
def test_solapaments_amb_limits_inclusius(w, ini, fin, overlaps):
    make_renovation(w.refuge, 'u1', ini=day(10), fin=day(15))
    if overlaps:
        with pytest.raises(IntegrityError, match='renovations_no_overlap'):
            with transaction.atomic():
                make_renovation(w.refuge, 'u2', ini=day(ini), fin=day(fin))
        assert count_renovations() == 1
    else:
        make_renovation(w.refuge, 'u2', ini=day(ini), fin=day(fin))
        assert count_renovations() == 2


def test_el_mateix_dia_en_un_altre_refugi_no_se_solapa(w):
    make_renovation(w.refuge, 'u1', ini=day(10), fin=day(15))
    make_renovation(w.refuge2, 'u1', ini=day(10), fin=day(15))
    assert count_renovations() == 2


def test_una_reforma_anonima_continua_comptant_per_al_solapament(w):
    make_renovation(w.refuge, None, ini=day(-10), fin=day(-5))
    with pytest.raises(IntegrityError, match='renovations_no_overlap'):
        with transaction.atomic():
            make_renovation(w.refuge, 'u1', ini=day(-6), fin=day(-3))


def test_actualitzar_dates_a_un_rang_que_se_solapa_es_rebutjat(w):
    make_renovation(w.refuge, 'u1', ini=day(10), fin=day(15))
    b = make_renovation(w.refuge, 'u1', ini=day(20), fin=day(25))
    with pytest.raises(IntegrityError, match='renovations_no_overlap'):
        with transaction.atomic():
            sql('UPDATE activity.renovations SET ini_date = %s WHERE id = %s', [day(14), b])
    sql('UPDATE activity.renovations SET fin_date = %s WHERE id = %s', [day(30), b])          # ampliar cap a fora: ok


# ----------------------------------------------- CHECK de group_link -----------------------------------------------

@pytest.mark.parametrize('link', ['ftp://servidor/grup', 'chat.whatsapp.com/abc', 'javascript:alert(1)', '',
                                  'https://' + 'a' * 2050])
def test_group_link_invalid_es_rebutjat(w, link):
    rid = make_renovation(w.refuge, None, link=None)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            sql('INSERT INTO activity.renovation_group_links (renovation_id, group_link) VALUES (%s, %s)', [rid, link])


@pytest.mark.parametrize('link', ['https://chat.whatsapp.com/x', 'http://t.me/x', 'HTTPS://T.ME/X'])
def test_group_link_http_s_valid_sense_distingir_majuscules(w, link):
    rid = make_renovation(w.refuge, 'u2', link=link)
    assert link_of(rid) == link


def test_group_link_de_longitud_maxima_2048_es_valid(w):
    link = 'https://x.org/' + 'a' * (2048 - len('https://x.org/'))
    assert len(link) == 2048
    assert link_of(make_renovation(w.refuge, 'u2', link=link)) == link


# ----------------------------------------------- trigger: tota reforma amb creador té enllaç -----------------------------------------------

def test_reforma_amb_creador_sense_enllac_falla_al_commit(w):
    with pytest.raises(IntegrityError, match='group_link') as exc:
        with transaction.atomic():
            sql(INSERT_RENO, [w.refuge.pk, 'u1', day(1), day(2), 'x'])      # dins el mateix savepoint: es desfà
            with connection.cursor() as cur:
                cur.execute('SET CONSTRAINTS ALL IMMEDIATE')
    assert constraint_name(exc) == 'renovations_requires_group_link_ck'
    assert count_renovations() == 0


def test_reforma_amb_creador_i_enllac_a_la_mateixa_transaccio_passa(w):
    with system_context():
        with connection.cursor() as cur:
            cur.execute(INSERT_RENO, [w.refuge.pk, 'u1', day(1), day(2), 'x'])
            rid = cur.fetchone()[0]
            cur.execute('INSERT INTO activity.renovation_group_links (renovation_id, group_link) VALUES (%s, %s)',
                        [rid, LINK])
            cur.execute('SET CONSTRAINTS ALL IMMEDIATE')                      # no ha de fallar


def test_reforma_creada_i_esborrada_a_la_mateixa_transaccio_no_exigeix_enllac(w):
    """El *trigger* diferit ha de mirar l'estat actual de la fila: una reforma ja esborrada (o anonimitzada) abans del
    `COMMIT` no pot fer fallar la transacció (altrament, p. ex., la verificació de final de cada test de Django)."""
    rid = make_renovation(w.refuge, 'u1')
    sql('DELETE FROM activity.renovations WHERE id = %s', [rid])
    sql('SET CONSTRAINTS ALL IMMEDIATE')


def test_reforma_creada_i_anonimitzada_a_la_mateixa_transaccio_no_exigeix_enllac(w):
    rid = make_renovation(w.refuge, 'u1')
    sql('UPDATE activity.renovations SET creator_uid = NULL WHERE id = %s', [rid])      # el trigger esborra l'enllaç
    sql('SET CONSTRAINTS ALL IMMEDIATE')


def test_reforma_anonima_no_necessita_enllac(w):
    with system_context():
        with connection.cursor() as cur:
            cur.execute(INSERT_RENO, [w.refuge.pk, None, day(1), day(2), 'x'])
            cur.execute('SET CONSTRAINTS ALL IMMEDIATE')


# ----------------------------------------------- trigger: anonimització esborra l'enllaç -----------------------------------------------

def test_anonimitzar_el_creador_esborra_l_enllac(w):
    a = make_renovation(w.refuge, 'u1', ini=day(1), fin=day(2), participants=['u2'])
    b = make_renovation(w.refuge2, 'u3', ini=day(1), fin=day(2))
    sql('UPDATE activity.renovations SET creator_uid = NULL WHERE id = %s', [a])
    assert link_of(a) is None and link_of(b) == LINK
    assert participants_of(a) == ['u2']                                       # els participants es conserven


def test_canviar_un_altre_camp_no_esborra_l_enllac(w):
    a = make_renovation(w.refuge, 'u1')
    sql("UPDATE activity.renovations SET description = 'nova' WHERE id = %s", [a])
    assert link_of(a) == LINK


def test_esborrar_l_usuari_creador_anonimitza_les_passades_i_esborra_l_enllac(w):
    past = make_renovation(w.refuge, 'u1', ini=day(-10), fin=day(-5), participants=['u2'], expelled=['u3'])
    with rls_context(uid='u1'):
        with connection.cursor() as cur:
            cur.execute('DELETE FROM users.users WHERE uid = %s', ['u1'])
    row = renovation_row(past)
    assert row is not None and row['creator_uid'] is None
    assert link_of(past) is None
    assert participants_of(past) == ['u2'] and expelled_of(past) == ['u3']


# ----------------------------------------------- trigger de guarda de participants i expulsats -----------------------------------------------

def test_un_expulsat_no_pot_ser_participant(w):
    rid = make_renovation(w.refuge, 'u1', expelled=['u3'])
    with pytest.raises(IntegrityError) as exc:
        with transaction.atomic():
            sql('INSERT INTO activity.renovation_participants (renovation_id, user_uid) VALUES (%s, %s)', [rid, 'u3'])
    assert constraint_name(exc) == 'renovation_participants_not_expelled_ck'
    assert participants_of(rid) == []


def test_el_creador_no_pot_ser_participant(w):
    rid = make_renovation(w.refuge, 'u1')
    with pytest.raises(IntegrityError) as exc:
        with transaction.atomic():
            sql('INSERT INTO activity.renovation_participants (renovation_id, user_uid) VALUES (%s, %s)', [rid, 'u1'])
    assert constraint_name(exc) == 'renovation_participants_not_creator_ck'


def test_no_es_pot_expulsar_qui_encara_es_participant(w):
    rid = make_renovation(w.refuge, 'u1', participants=['u2'])
    with pytest.raises(IntegrityError) as exc:
        with transaction.atomic():
            sql('INSERT INTO activity.renovation_expelled (renovation_id, user_uid) VALUES (%s, %s)', [rid, 'u2'])
    assert constraint_name(exc) == 'renovation_expelled_not_participant_ck'


def test_expulsar_despres_de_treure_de_participants_a_la_mateixa_transaccio(w):
    rid = make_renovation(w.refuge, 'u1', participants=['u2'])
    with system_context():
        with connection.cursor() as cur:
            cur.execute('DELETE FROM activity.renovation_participants WHERE renovation_id = %s AND user_uid = %s',
                        [rid, 'u2'])
            cur.execute('INSERT INTO activity.renovation_expelled (renovation_id, user_uid) VALUES (%s, %s)',
                        [rid, 'u2'])
    assert participants_of(rid) == [] and expelled_of(rid) == ['u2']


def test_participant_duplicat_viola_la_pk_i_on_conflict_do_nothing_ho_tolera(w):
    """A3: ja no hi ha carrera de lectura-modificació-escriptura; la PK ho resol."""
    rid = make_renovation(w.refuge, 'u1', participants=['u2'])
    with pytest.raises(IntegrityError, match='renovation_participants_pk'):
        with transaction.atomic():
            sql('INSERT INTO activity.renovation_participants (renovation_id, user_uid) VALUES (%s, %s)', [rid, 'u2'])
    with system_context():
        with connection.cursor() as cur:
            cur.execute('INSERT INTO activity.renovation_participants (renovation_id, user_uid) VALUES (%s, %s) '
                        'ON CONFLICT DO NOTHING', [rid, 'u2'])
            assert cur.rowcount == 0
    assert participants_of(rid) == ['u2']


def test_expulsat_duplicat_viola_la_pk(w):
    rid = make_renovation(w.refuge, 'u1', expelled=['u3'])
    with pytest.raises(IntegrityError, match='renovation_expelled_pk'):
        with transaction.atomic():
            sql('INSERT INTO activity.renovation_expelled (renovation_id, user_uid) VALUES (%s, %s)', [rid, 'u3'])


def test_participant_d_un_usuari_inexistent_viola_la_fk(w):
    rid = make_renovation(w.refuge, 'u1')
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            sql('INSERT INTO activity.renovation_participants (renovation_id, user_uid) VALUES (%s, %s)',
                [rid, 'fantasma'])
            sql('SET CONSTRAINTS ALL IMMEDIATE')


# ----------------------------------------------- cascades -----------------------------------------------

def test_esborrar_la_reforma_cascadeja_enllac_participants_i_expulsats(w):
    rid = make_renovation(w.refuge, 'u1', participants=['u2'], expelled=['u3'])
    keep = make_renovation(w.refuge2, 'u1', participants=['u2'], expelled=['u3'])
    sql('DELETE FROM activity.renovations WHERE id = %s', [rid])
    assert (link_of(rid), participants_of(rid), expelled_of(rid)) == (None, [], [])
    assert link_of(keep) == LINK and participants_of(keep) == ['u2'] and expelled_of(keep) == ['u3']


def test_esborrar_un_refugi_cascadeja_les_seves_reformes(w):
    rid = make_renovation(w.refuge, 'u1', participants=['u2'])
    keep = make_renovation(w.refuge2, 'u1')
    with as_owner():
        with connection.cursor() as cur:
            cur.execute('DELETE FROM refuges.refuges WHERE id = %s', [w.refuge.pk])
    assert renovation_row(rid) is None and participants_of(rid) == [] and link_of(rid) is None
    assert renovation_row(keep) is not None


def test_esborrar_un_usuari_treu_les_seves_participacions_i_expulsions(w):
    rid = make_renovation(w.refuge, 'u1', participants=['u2', 'u3'], expelled=['u4'])
    other = make_renovation(w.refuge2, 'u1', participants=['u2'], expelled=['u4'])
    for uid in ('u2', 'u4'):
        with rls_context(uid=uid):
            with connection.cursor() as cur:
                cur.execute('DELETE FROM users.users WHERE uid = %s', [uid])
    assert participants_of(rid) == ['u3'] and expelled_of(rid) == []
    assert participants_of(other) == [] and expelled_of(other) == []
    assert renovation_row(rid)['creator_uid'] == 'u1'


def test_les_dates_es_desen_com_a_date_sense_hora(w):
    rid = make_renovation(w.refuge, 'u1', ini=day(2), fin=day(4))
    row = renovation_row(rid)
    assert type(row['ini_date']) is date and type(row['fin_date']) is date
