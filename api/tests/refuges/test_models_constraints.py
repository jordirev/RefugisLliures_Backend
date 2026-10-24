"""
Models `domain.refuges` / `domain.accounts` i restriccions de la BD (§2.5-2.8), provats amb el rol `app`
dins `system_context()` (l'escriptura de refugis és d'admin/sistema per RLS).
"""
import uuid

import pytest
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.db import IntegrityError, connection, transaction

from api.tests.refuges.helpers import (
    AMENITY_FIELDS, REFUGE_TYPES, QueryCounter, account_models, make_media, make_refuge, make_user, refuge_models)
from domain.core.rls import rls_context, system_context

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.models, pytest.mark.integration]


def _fails(fn):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            fn()


def _create(RM, **kw):
    kw.setdefault('name', 'X')
    kw.setdefault('coord', Point(1.5, 42.5, srid=4326))
    with system_context():
        return RM.Refuge.objects.create(**kw)


# ---------- Models / TextChoices ----------

def test_choices_de_tipus_coincideixen_amb_els_valors_del_codi(RM):
    assert set(RM.RefugeType.values) == set(REFUGE_TYPES)
    assert set(RM.MediaStatus.values) == {'visible', 'hidden_pending_review', 'removed'}
    assert set(RM.MediaType.values) == {'image', 'video'}


def test_pk_per_defecte_es_uuid7(RM):
    r = RM.Refuge(name='a', coord=Point(1, 42, srid=4326))
    assert isinstance(r.pk, uuid.UUID) and r.pk.version == 7
    assert RM.RefugeLink(position=0, url='https://a.b').pk.version == 7


def test_valors_per_defecte_del_refugi(RM):
    r = _create(RM)
    r.refresh_from_db()
    assert (r.type, r.remarque, r.description) == ('non gardé', '', '')
    assert r.num_contributed_conditions == 0 and r.condition is None and r.condition_reset_at is None
    assert r.altitude is None and r.places is None and r.region is None and r.surname is None
    assert r.created_at is not None


def test_coord_x_es_longitud_i_y_latitud(RM):
    r = make_refuge(lat=42.6, long=1.7)
    r = RM.Refuge.objects.get(pk=r.pk)
    assert (r.coord.x, r.coord.y) == pytest.approx((1.7, 42.6))
    assert r.coord.srid == 4326


def test_amenities_per_defecte_totes_fals(RM):
    r = make_refuge()
    a = RM.RefugeAmenities.objects.get(pk=r.pk)
    assert a.pk == r.pk and all(getattr(a, f) is False for f in AMENITY_FIELDS)
    assert RM.Refuge.objects.select_related('amenities').get(pk=r.pk).amenities.pk == r.pk


def test_dos_refugis_amb_el_mateix_nom_i_coordenades_diferents_son_permesos(RM):
    """Sense UNIQUE(name): el JSON té 8 noms repetits (B2)."""
    for i in range(3):
        make_refuge(name='Cabane de la Plagne', lat=42.0 + i / 10, long=1.0)
    assert RM.Refuge.objects.filter(name='Cabane de la Plagne').count() == 3


def test_geografia_dwithin_200_metres(RM):
    """Recepta 8 (§5.3): detecció de duplicats propers amb `ST_DWithin` sobre geography."""
    make_refuge(name='proper', lat=42.5000, long=1.5000)
    make_refuge(name='lluny', lat=42.5100, long=1.5000)         # ~1,1 km
    near = RM.Refuge.objects.filter(coord__dwithin=(Point(1.5, 42.5009, srid=4326), D(m=200)))
    assert [r.name for r in near] == ['proper']


# ---------- CHECK de refuges ----------

@pytest.mark.parametrize('kw', [
    {'condition': -0.1}, {'condition': 3.01},
    {'num_contributed_conditions': -1},
    {'num_contributed_conditions': 2, 'condition': None},          # n > 0 exigeix condition
    {'name': ''}, {'name': '   '},
    {'surname': ''}, {'surname': '  '},
    {'type': 'garde'}, {'type': 'no guardat'},
    {'altitude': -1}, {'altitude': 8849},
    {'places': -1},
    {'coord': Point(0, 0, srid=4326)},
])
def test_check_constraints_de_refuges_rebutgen(RM, kw):
    _fails(lambda: _create(RM, **kw))


@pytest.mark.parametrize('kw', [
    {'condition': 0}, {'condition': 3}, {'condition': 1.5, 'num_contributed_conditions': 3},
    {'condition': None, 'num_contributed_conditions': 0},
    {'altitude': 0}, {'altitude': 8848}, {'places': 0}, {'places': None}, {'surname': None}, {'surname': 'Alias'},
    {'coord': Point(0, 1, srid=4326)},
])
def test_check_constraints_de_refuges_accepten_els_limits(RM, kw):
    _create(RM, **kw)


@pytest.mark.parametrize('t', REFUGE_TYPES)
def test_tots_els_tipus_valids_s_accepten(RM, t):
    _create(RM, type=t)


# ---------- amenities / links ----------

def test_amenities_es_1_a_1_amb_el_refugi(RM):
    r = make_refuge()
    with system_context():
        _fails(lambda: RM.RefugeAmenities.objects.create(refuge=r))


def test_link_url_ha_de_ser_http_s_i_curta(RM):
    r = make_refuge()
    for url in ('ftp://x.org/a', 'javascript:alert(1)', 'www.x.org', '', 'https://x.org/' + 'a' * 2048):
        with system_context():
            _fails(lambda: RM.RefugeLink.objects.create(refuge=r, position=0, url=url))
    with system_context():
        RM.RefugeLink.objects.create(refuge=r, position=0, url='HTTPS://x.org/a')   # `~*`: sense distinció


def test_link_posicio_no_negativa(RM):
    r = make_refuge()
    with system_context():
        _fails(lambda: RM.RefugeLink.objects.create(refuge=r, position=-1, url='https://x.org'))


def test_link_unique_per_posicio_i_per_url(RM):
    r = make_refuge(links=['https://a.org', 'https://b.org'])
    with system_context():
        _fails(lambda: (RM.RefugeLink.objects.create(refuge=r, position=5, url='https://a.org'),
                        connection.check_constraints()))
    with system_context():
        _fails(lambda: (RM.RefugeLink.objects.create(refuge=r, position=1, url='https://c.org'),
                        connection.check_constraints()))


def test_link_posicions_es_poden_intercanviar_dins_la_transaccio(RM):
    """`UNIQUE (refuge_id, position) DEFERRABLE INITIALLY DEFERRED` (§2.7)."""
    r = make_refuge(links=['https://a.org', 'https://b.org'])
    with system_context():
        a = RM.RefugeLink.objects.get(refuge=r, position=0)
        b = RM.RefugeLink.objects.get(refuge=r, position=1)
        RM.RefugeLink.objects.filter(pk=a.pk).update(position=1)       # duplicat transitori
        RM.RefugeLink.objects.filter(pk=b.pk).update(position=0)
        with connection.cursor() as cur:
            cur.execute('SET CONSTRAINTS ALL IMMEDIATE')
    urls = list(RM.RefugeLink.objects.filter(refuge=r).order_by('position').values_list('url', flat=True))
    assert urls == ['https://b.org', 'https://a.org']


def test_mateixa_url_en_refugis_diferents_es_permesa(RM):
    make_refuge(name='a', links=['https://x.org'])
    make_refuge(name='b', lat=43, links=['https://x.org'])


# ---------- FK reals ----------

def test_amenities_amb_refugi_inexistent_falla_en_comprovar_les_fk(RM):
    with system_context():
        RM.RefugeAmenities.objects.create(refuge_id=uuid.uuid4())
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                with connection.cursor() as cur:
                    cur.execute('SET CONSTRAINTS ALL IMMEDIATE')
        with connection.cursor() as cur:
            cur.execute('SET CONSTRAINTS ALL DEFERRED')


def test_media_amb_creador_inexistent_falla(RM):
    r = make_refuge()
    make_media(r, 'fantasma')
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            with connection.cursor() as cur:
                cur.execute('SET CONSTRAINTS ALL IMMEDIATE')
    with connection.cursor() as cur:
        cur.execute('SET CONSTRAINTS ALL DEFERRED')
    with system_context():
        RM.RefugeMedia.objects.all().delete()                            # perquè el teardown no falli


# ---------- cascades del DDL amb el rol app ----------

def _count(model):
    with system_context():
        return model.objects.count()


def test_esborrar_un_refugi_cascadeja_amenities_links_i_media(RM):
    make_user('u1')
    r = make_refuge(links=['https://a.org'])
    make_media(r, 'u1')
    other = make_refuge(name='altre', lat=43, links=['https://z.org'])
    with system_context():
        RM.Refuge.objects.filter(pk=r.pk).delete()
    assert _count(RM.RefugeAmenities) == 1 and _count(RM.RefugeLink) == 1 and _count(RM.RefugeMedia) == 0
    assert RM.Refuge.objects.filter(pk=other.pk).exists()


def test_esborrar_un_usuari_cascadeja_el_perfil_i_els_seus_mitjans_sense_que_la_rls_ho_bloquegi(RM):
    am = account_models()
    make_user('u1')
    make_user('u2')
    r = make_refuge()
    make_media(r, 'u1', minutes=1)
    make_media(r, 'u2', minutes=2)
    with rls_context(uid='u1'):
        with QueryCounter() as q:
            am.UserAccount.objects.filter(pk='u1').delete()
        deletes = [s for s in q.queries if s.upper().startswith('DELETE')]
        assert len(deletes) == 1, f"un sol DELETE; la BD fa la resta (§6.3): {q.queries}"
    with system_context():
        assert list(RM.RefugeMedia.objects.values_list('creator_id', flat=True)) == ['u2']
        assert not am.UserPublicProfile.objects.filter(pk='u1').exists()
        assert am.UserPublicProfile.objects.filter(pk='u2').exists()


# ---------- CHECK de media ----------

def _media(RM, refuge, **kw):
    base = dict(key=f'k/{uuid.uuid4()}.webp', refuge=refuge, creator_id='u1', media_type='image',
                content_type='image/webp', status='visible')
    from api.tests.refuges.helpers import T0
    base.update(uploaded_at=T0, rights_confirmed_at=T0)
    base.update(kw)
    with system_context():
        return RM.RefugeMedia.objects.create(**base)


@pytest.mark.parametrize('kw', [
    {'status': 'hidden'}, {'status': 'deleted'}, {'media_type': 'audio'}, {'key': ''},
    {'width': 0}, {'height': -1}, {'size_bytes': 0},
    {'thumb_key': 'same', 'key': 'same'},
])
def test_check_constraints_de_media_rebutgen(RM, kw):
    make_user('u1')
    r = make_refuge()
    _fails(lambda: _media(RM, r, **kw))


@pytest.mark.parametrize('status', ['visible', 'hidden_pending_review', 'removed'])
@pytest.mark.parametrize('media_type', ['image', 'video'])
def test_media_estats_i_tipus_valids(RM, status, media_type):
    make_user('u1')
    _media(RM, make_refuge(), status=status, media_type=media_type)


def test_media_thumb_key_unica_nomes_si_no_es_nula(RM):
    make_user('u1')
    r = make_refuge()
    _media(RM, r, thumb_key=None)
    _media(RM, r, thumb_key=None)                                    # diversos NULL: permès
    _media(RM, r, thumb_key='t1')
    _fails(lambda: _media(RM, r, thumb_key='t1'))


def test_media_pk_es_la_clau_r2(RM):
    make_user('u1')
    r = make_refuge()
    _media(RM, r, key='refugis-lliures/x/a.webp')
    _fails(lambda: _media(RM, r, key='refugis-lliures/x/a.webp'))
    assert RM.RefugeMedia._meta.pk.name == 'key'


def test_media_requereix_rights_confirmed_at(RM):
    make_user('u1')
    r = make_refuge()
    _fails(lambda: _media(RM, r, rights_confirmed_at=None))


# ---------- accounts (mínim del chunk 2) ----------

@pytest.mark.parametrize('kw', [
    {'uid': ''}, {'uid': 'system'}, {'uid': 'unknown'}, {'uid': 'x' * 129},
    {'language': 'de'},
    {'age_confirmed_at': '2025-01-01T00:00:00Z'},                    # sense age_threshold
    {'age_threshold': 16},                                           # sense age_confirmed_at
    {'moderation_strikes': -1},
    {'blocked_reason': 'strikes'},                                   # sense is_blocked
    {'is_blocked': True, 'blocked_reason': 'altre'},
])
def test_check_constraints_d_usuaris(kw):
    am = account_models()
    kw = {'uid': 'u1', **kw}
    def go():
        with system_context():
            am.UserAccount.objects.create(**kw)
    _fails(go)


def test_usuari_per_defecte():
    make_user('u1')
    am = account_models()
    with system_context():
        u = am.UserAccount.objects.get(pk='u1')
    assert (u.language, u.moderation_strikes, u.is_blocked) == ('ca', 0, False)
    assert u.age_confirmed_at is None and u.blocked_reason is None


@pytest.mark.parametrize('username', ['a', ' a '])
def test_username_curt_rebutjat_pero_buit_permes(username):
    am = account_models()
    make_user('u1', username='')
    make_user('u2', username='ok')
    make_user('u3')
    def go():
        with system_context():
            am.UserPublicProfile.objects.filter(pk='u1').update(username=username)
    _fails(go)
