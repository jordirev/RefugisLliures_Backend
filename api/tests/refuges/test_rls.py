"""
RLS del chunk 2 (§2.1, §2.2, §2.5-2.8, §7.5) provada amb el rol `app`: anònim, propi, aliè, admin i sistema.

Un `INSERT` denegat per la RLS llança error (`new row violates row-level security policy`); un `UPDATE`/`DELETE`
denegat afecta 0 files (la fila és invisible o no passa la política).
"""
import pytest
from django.contrib.gis.geos import Point
from django.db import DatabaseError, connection, transaction

from api.tests.refuges.helpers import T0, account_models, make_media, make_refuge, make_user, refuge_models
from domain.core.rls import rls_context, system_context

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.rls, pytest.mark.integration]

ANON = {}
OWN = {'uid': 'u1'}
OTHER = {'uid': 'u2'}
ADMIN = {'uid': 'adm', 'is_admin': True}
SYSTEM = {'system': True}
ALL_CTX = {'anon': ANON, 'own': OWN, 'other': OTHER, 'admin': ADMIN, 'system': SYSTEM}
WRITERS = {'admin', 'system'}          # {ADM} OR {SYS}


def _denied(fn):
    with pytest.raises(DatabaseError):
        with transaction.atomic():
            fn()


@pytest.fixture
def world(RM):
    make_user('u1')
    make_user('u2')
    r = make_refuge(name='R1', links=['https://a.org'])
    return r


# ---------- refuges / amenities / links: lectura pública, escriptura admin/sistema ----------

@pytest.mark.parametrize('ctx', ALL_CTX)
def test_lectura_publica_de_refugis_amenities_i_links(RM, world, ctx):
    with rls_context(**ALL_CTX[ctx]):
        assert RM.Refuge.objects.count() == 1
        assert RM.RefugeAmenities.objects.count() == 1
        assert RM.RefugeLink.objects.count() == 1


def test_sense_context_la_lectura_publica_funciona(RM, world):
    with connection.cursor() as cur:
        cur.execute("SELECT set_config('app.uid', '', true), set_config('app.is_admin', '', true), "
                    "set_config('app.is_system', '', true)")
    assert RM.Refuge.objects.count() == 1


@pytest.mark.parametrize('ctx', ALL_CTX)
def test_insert_de_refugi_nomes_admin_o_sistema(RM, ctx):
    def go():
        with rls_context(**ALL_CTX[ctx]):
            RM.Refuge.objects.create(name='N', coord=Point(1, 42, srid=4326))
    if ctx in WRITERS:
        go()
    else:
        _denied(go)


@pytest.mark.parametrize('ctx', ALL_CTX)
def test_insert_d_amenities_i_links_nomes_admin_o_sistema(RM, world, ctx):
    with system_context():
        other = RM.Refuge.objects.create(name='N', coord=Point(1, 42, srid=4326))

    def go_a():
        with rls_context(**ALL_CTX[ctx]):
            RM.RefugeAmenities.objects.create(refuge=other)

    def go_l():
        with rls_context(**ALL_CTX[ctx]):
            RM.RefugeLink.objects.create(refuge=other, position=0, url='https://x.org')
    for go in (go_a, go_l):
        if ctx in WRITERS:
            go()
        else:
            _denied(go)


@pytest.mark.parametrize('ctx', ALL_CTX)
def test_update_i_delete_de_refugi_nomes_admin_o_sistema(RM, world, ctx):
    with rls_context(**ALL_CTX[ctx]):
        updated = RM.Refuge.objects.filter(pk=world.pk).update(altitude=1234)
    assert updated == (1 if ctx in WRITERS else 0)
    with rls_context(**ALL_CTX[ctx]):
        deleted = RM.Refuge.objects.filter(pk=world.pk).delete()[0]
    assert deleted == (1 if ctx in WRITERS else 0)
    assert RM.Refuge.objects.count() == (0 if ctx in WRITERS else 1)


@pytest.mark.parametrize('ctx', ['anon', 'own', 'other'])
def test_un_usuari_no_pot_tocar_la_condicio_del_refugi(RM, world, ctx):
    """§2.9: només el trigger d'experiències (chunk 7) o una aprovació d'admin escriuen `condition`."""
    with rls_context(**ALL_CTX[ctx]):
        n = RM.Refuge.objects.filter(pk=world.pk).update(condition=3, num_contributed_conditions=9)
    assert n == 0
    world.refresh_from_db()
    assert world.condition is None and world.num_contributed_conditions == 0


@pytest.mark.parametrize('ctx', ['anon', 'own', 'other'])
def test_un_usuari_no_pot_modificar_amenities_ni_links(RM, world, ctx):
    with rls_context(**ALL_CTX[ctx]):
        assert RM.RefugeAmenities.objects.update(eau=True) == 0
        assert RM.RefugeLink.objects.update(url='https://hack.org') == 0
        assert RM.RefugeLink.objects.all().delete()[0] == 0
        assert RM.RefugeAmenities.objects.all().delete()[0] == 0
    assert RM.RefugeLink.objects.get().url == 'https://a.org'
    assert RM.RefugeAmenities.objects.get().eau is False


@pytest.mark.parametrize('ctx', sorted(WRITERS))
def test_admin_i_sistema_poden_editar_amenities_i_links(RM, world, ctx):
    with rls_context(**ALL_CTX[ctx]):
        assert RM.RefugeAmenities.objects.update(eau=True) == 1
        assert RM.RefugeLink.objects.update(url='https://b.org') == 1


def test_la_vista_refuge_map_es_llegeix_sense_context_i_mostra_tots_els_refugis(RM, world):
    make_refuge(name='R2', lat=43, long=2)
    with rls_context():
        pts = list(RM.RefugeMapPoint.objects.order_by('name').values('name', 'lat', 'lng'))
    assert [p['name'] for p in pts] == ['R1', 'R2']
    assert (pts[1]['lat'], pts[1]['lng']) == pytest.approx((43, 2))


# ---------- refuge_media ----------

STATUSES = ['visible', 'hidden_pending_review', 'removed']


@pytest.mark.parametrize('status', STATUSES)
@pytest.mark.parametrize('ctx,sees_hidden', [('anon', False), ('own', True), ('other', False),
                                             ('admin', True), ('system', True)])
def test_select_de_media(RM, world, status, ctx, sees_hidden):
    make_media(world, 'u1', status=status)
    with rls_context(**ALL_CTX[ctx]):
        n = RM.RefugeMedia.objects.count()
    assert n == (1 if status == 'visible' or sees_hidden else 0)


def test_insert_de_media_propi_visible_es_permet(RM, world):
    with rls_context(uid='u1'):
        RM.RefugeMedia.objects.create(key='k/own.webp', refuge=world, creator_id='u1', media_type='image',
                                      content_type='image/webp', status='visible', rights_confirmed_at=T0)
    with system_context():
        assert RM.RefugeMedia.objects.filter(key='k/own.webp').exists()


@pytest.mark.parametrize('ctx,creator,status,allowed', [
    ('own', 'u1', 'hidden_pending_review', False),      # un usuari no es pot auto-ocultar/retirar
    ('own', 'u1', 'removed', False),
    ('own', 'u2', 'visible', False),                     # no es pot pujar en nom d'un altre
    ('anon', 'u1', 'visible', False),
    ('other', 'u1', 'visible', False),
    ('admin', 'u2', 'visible', True),
    ('admin', 'u2', 'removed', True),
    ('system', 'u2', 'hidden_pending_review', True),
])
def test_insert_de_media_segons_context(RM, world, ctx, creator, status, allowed):
    def go():
        with rls_context(**ALL_CTX[ctx]):
            RM.RefugeMedia.objects.create(key=f'k/{ctx}-{status}.webp', refuge=world, creator_id=creator,
                                          media_type='image', content_type='image/webp', status=status,
                                          rights_confirmed_at=T0)
    if allowed:
        go()
    else:
        _denied(go)


@pytest.mark.parametrize('ctx', ALL_CTX)
def test_update_de_media_nomes_moderacio(RM, world, ctx):
    """El canvi d'estat és de moderació (admin/sistema); ni l'autor pot reactivar o ocultar el seu mitjà."""
    make_media(world, 'u1', key='k/m.webp')
    with rls_context(**ALL_CTX[ctx]):
        n = RM.RefugeMedia.objects.filter(pk='k/m.webp').update(status='hidden_pending_review')
    assert n == (1 if ctx in WRITERS else 0)


@pytest.mark.parametrize('ctx,allowed', [('anon', False), ('own', True), ('other', False), ('admin', True),
                                         ('system', True)])
def test_delete_de_media_autor_admin_o_sistema(RM, world, ctx, allowed):
    make_media(world, 'u1', key='k/d.webp')
    with rls_context(**ALL_CTX[ctx]):
        n = RM.RefugeMedia.objects.filter(pk='k/d.webp').delete()[0]
    assert n == (1 if allowed else 0)


def test_l_autor_pot_esborrar_el_seu_mitja_ocult_pero_un_altre_no(RM, world):
    make_media(world, 'u1', key='k/h.webp', status='hidden_pending_review')
    with rls_context(uid='u2'):
        assert RM.RefugeMedia.objects.filter(pk='k/h.webp').delete()[0] == 0
    with rls_context(uid='u1'):
        assert RM.RefugeMedia.objects.filter(pk='k/h.webp').delete()[0] == 1


# ---------- users / user_public_profiles ----------

@pytest.mark.parametrize('ctx,sees', [('anon', 0), ('own', 1), ('other', 1), ('admin', 2), ('system', 2)])
def test_select_de_users_nomes_el_propi_admin_o_sistema(world, ctx, sees):
    """`own` és u1, que només veu la seva fila; `other` és u2, que també veu només la seva."""
    am = account_models()
    with rls_context(**ALL_CTX[ctx]):
        n = am.UserAccount.objects.count()
    assert n == sees


def test_un_usuari_no_veu_la_fila_d_un_altre(world):
    am = account_models()
    with rls_context(uid='u1'):
        assert list(am.UserAccount.objects.values_list('uid', flat=True)) == ['u1']


@pytest.mark.parametrize('ctx', ALL_CTX)
def test_perfils_publics_es_llegeixen_per_tothom(world, ctx):
    am = account_models()
    with rls_context(**ALL_CTX[ctx]):
        assert am.UserPublicProfile.objects.count() == 2


@pytest.mark.parametrize('ctx,uid,allowed', [
    ('own', 'u9', True), ('own', 'altre', False), ('anon', 'u9', False), ('admin', 'u9', False),
    ('system', 'u9', True)])
def test_insert_d_usuari_nomes_el_propi_o_sistema(world, ctx, uid, allowed):
    am = account_models()
    ctx_args = dict(ALL_CTX[ctx])
    if ctx == 'own':
        ctx_args = {'uid': 'u9'}

    def go():
        with rls_context(**ctx_args):
            am.UserAccount.objects.create(uid=uid)
    if allowed:
        go()
    else:
        _denied(go)


def test_insert_d_usuari_no_pot_portar_moderacio_prefixada(world):
    am = account_models()
    for kw in ({'moderation_strikes': 2}, {'is_blocked': True, 'blocked_reason': 'strikes'}):
        _denied(lambda kw=kw: _create_as(am, 'u9', **kw))


def _create_as(am, uid, **kw):
    with rls_context(uid=uid):
        am.UserAccount.objects.create(uid=uid, **kw)


def test_un_usuari_no_pot_bloquejar_ni_donar_strikes_a_si_mateix(world):
    """`users_guard` (§2.1): les columnes de moderació només les canvia admin/sistema."""
    am = account_models()
    with rls_context(uid='u1'):
        _denied(lambda: am.UserAccount.objects.filter(pk='u1').update(is_blocked=True, blocked_reason='strikes'))
        _denied(lambda: am.UserAccount.objects.filter(pk='u1').update(moderation_strikes=5))
        assert am.UserAccount.objects.filter(pk='u1').update(language='es') == 1
    with rls_context(uid='adm', is_admin=True):
        assert am.UserAccount.objects.filter(pk='u1').update(moderation_strikes=1) == 1


def test_un_usuari_no_pot_modificar_ni_esborrar_un_altre(world):
    am = account_models()
    with rls_context(uid='u1'):
        assert am.UserAccount.objects.filter(pk='u2').update(language='fr') == 0
        assert am.UserAccount.objects.filter(pk='u2').delete()[0] == 0
        assert am.UserPublicProfile.objects.filter(pk='u2').update(username='hack') == 0


def test_admin_no_pot_esborrar_un_usuari_pero_el_sistema_si(world):
    """`users_delete`: IsSameUser sense bypass d'admin, com ara."""
    am = account_models()
    with rls_context(uid='adm', is_admin=True):
        assert am.UserAccount.objects.filter(pk='u1').delete()[0] == 0
    with rls_context(system=True):
        assert am.UserAccount.objects.filter(pk='u1').delete()[0] >= 1
    with rls_context(uid='u2'):
        assert am.UserAccount.objects.filter(pk='u2').delete()[0] >= 1


def test_perfil_public_nomes_el_modifica_el_propietari_o_el_sistema(world):
    am = account_models()
    with rls_context(uid='u1'):
        assert am.UserPublicProfile.objects.filter(pk='u1').update(username='nou') == 1
    with rls_context(uid='adm', is_admin=True):
        assert am.UserPublicProfile.objects.filter(pk='u1').update(username='admin') == 0
    with rls_context(system=True):
        assert am.UserPublicProfile.objects.filter(pk='u1').update(username='sys') == 1


def test_perfil_public_no_te_delete_per_a_app(world):
    am = account_models()
    with rls_context(system=True):
        _denied(lambda: am.UserPublicProfile.objects.filter(pk='u1').delete())
