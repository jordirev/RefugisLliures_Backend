"""
Serializers de reformes (chunk 5; `apps/renovations/serializers.py`), sense accés a la BD.

Contracte:
- `RenovationCreateSerializer(data=...)`: `refuge_id` (cadena, qualsevol; que sigui un UUID existent ho decideix el
  servei → 404), `ini_date`, `fin_date` (`YYYY-MM-DD`), `description` (no buida), `group_link` (URL http/https de com a
  molt 2048 caràcters), `materials_needed` (opcional, pot ser buit o `null`). Regles de dates: `ini_date <= fin_date`
  (**reformes d'un dia vàlides**: tanca A1 i la regla del model; GOTCHAS #5) i `ini_date >= avui de Madrid`
  (`get_madrid_today`). Camps desconeguts (`creator_uid`, `participants_uids`, `expelled_uids`...) s'ignoren.
- `RenovationUpdateSerializer(data=...)`: tots els camps opcionals (`{}` és vàlid; **cap `default=`**, GOTCHAS #6).
  Cada data per separat és vàlida: la comparació amb la data desada la fa el servei (M2). `group_link` no pot ser
  `null` (la fila d'enllaç és NOT NULL; pregunta 3 de l'informe).
- `RenovationSerializer(instance).data`: surt d'una instància de `Renovation` anotada amb `participants_uids` (llista)
  i `group_link` (cadena o `None`). Claus: `id` (cadena), `creator_uid` (`'unknown'` si el creador és `NULL`),
  `refuge_id`, `ini_date`, `fin_date` (`YYYY-MM-DD`), `description`, `materials_needed`, `participants_uids`, i
  `group_link` **només si no és `None`** (RLS: creador, participants, admin). **Mai** `expelled_uids`.
"""
import uuid
from datetime import date

import pytest

from apps.renovations.tests.helpers import BASE_KEYS, FULL_KEYS, LINK, day

pytestmark = [pytest.mark.serializers, pytest.mark.unit]


@pytest.fixture
def SZ():
    import importlib
    return importlib.import_module('apps.renovations.serializers')


def valid(**over):
    data = {'refuge_id': str(uuid.uuid4()), 'ini_date': day(2).isoformat(), 'fin_date': day(4).isoformat(),
            'description': 'Canviar el sostre', 'group_link': LINK}
    data.update(over)
    return data


def create(SZ, **over):
    s = SZ.RenovationCreateSerializer(data=valid(**over))
    return s, s.is_valid()


# =============================================== creació ===============================================

def test_create_valid_i_dades_validades(SZ):
    s, ok = create(SZ, materials_needed='Pintura')
    assert ok, s.errors
    assert s.validated_data['ini_date'] == day(2) and s.validated_data['fin_date'] == day(4)
    assert s.validated_data['materials_needed'] == 'Pintura'
    assert set(s.validated_data) == {'refuge_id', 'ini_date', 'fin_date', 'description', 'group_link',
                                     'materials_needed'}


def test_create_reforma_d_un_dia_es_valida(SZ):
    """Decisió del PO #1 (tanca A1): `ini_date == fin_date`."""
    s, ok = create(SZ, ini_date=day(3).isoformat(), fin_date=day(3).isoformat())
    assert ok, s.errors


def test_create_avui_es_valid(SZ):
    s, ok = create(SZ, ini_date=day(0).isoformat(), fin_date=day(0).isoformat())
    assert ok, s.errors


def test_create_ini_posterior_a_fin_error_a_fin_date(SZ):
    s, ok = create(SZ, ini_date=day(5).isoformat(), fin_date=day(4).isoformat())
    assert not ok and 'fin_date' in s.errors


def test_create_ini_en_el_passat_error_a_ini_date(SZ):
    s, ok = create(SZ, ini_date=day(-1).isoformat(), fin_date=day(2).isoformat())
    assert not ok and 'ini_date' in s.errors


@pytest.mark.parametrize('field', ['refuge_id', 'ini_date', 'fin_date', 'description', 'group_link'])
def test_create_camps_obligatoris(SZ, field):
    data = valid()
    del data[field]
    s = SZ.RenovationCreateSerializer(data=data)
    assert not s.is_valid() and field in s.errors


@pytest.mark.parametrize('description', ['', '   ', None])
def test_create_descripcio_buida_o_nul_la(SZ, description):
    s, ok = create(SZ, description=description)
    assert not ok and 'description' in s.errors


@pytest.mark.parametrize('link', ['', 'no-es-una-url', 'chat.whatsapp.com/abc', 'ftp://servidor/grup',
                                  'javascript:alert(1)', 'https://' + 'a' * 2050 + '.org'])
def test_create_group_link_ha_de_ser_http_o_https_de_fins_a_2048(SZ, link):
    """Alineat amb el `CHECK group_link ~* '^https?://' AND char_length <= 2048`: ha de ser 400, mai 500."""
    s, ok = create(SZ, group_link=link)
    assert not ok and 'group_link' in s.errors


@pytest.mark.parametrize('link', ['https://chat.whatsapp.com/abc', 'http://t.me/grup', 'https://t.me/joinchat/AAA?x=1'])
def test_create_group_link_valid(SZ, link):
    assert create(SZ, group_link=link)[1]


@pytest.mark.parametrize('materials', [None, '', 'Pintura'])
def test_create_materials_opcional(SZ, materials):
    s, ok = create(SZ, materials_needed=materials)
    assert ok, s.errors


def test_create_sense_materials(SZ):
    s, ok = create(SZ)
    assert ok and 'materials_needed' not in s.validated_data


def test_create_refuge_id_es_una_cadena_qualsevol(SZ):
    """Un ID antic de Firestore o no UUID no és un 400 del serializer: el servei respon 404."""
    assert create(SZ, refuge_id='abc123')[1]


def test_create_ignora_camps_que_no_toquen(SZ):
    s, ok = create(SZ, creator_uid='altre', participants_uids=['x'], expelled_uids=['y'], id='z')
    assert ok
    assert not {'creator_uid', 'participants_uids', 'expelled_uids', 'id'} & set(s.validated_data)


# =============================================== actualització ===============================================

def test_update_buit_es_valid(SZ):
    s = SZ.RenovationUpdateSerializer(data={})
    assert s.is_valid() and s.validated_data == {}


def test_update_no_afegeix_defaults(SZ):
    s = SZ.RenovationUpdateSerializer(data={'description': 'Nova'})
    assert s.is_valid() and s.validated_data == {'description': 'Nova'}


@pytest.mark.parametrize('field', ['ini_date', 'fin_date'])
def test_update_una_sola_data_es_valida(SZ, field):
    """M2: el serializer no exigeix les dues; la comparació amb la data desada és del servei."""
    s = SZ.RenovationUpdateSerializer(data={field: day(6).isoformat()})
    assert s.is_valid(), s.errors
    assert s.validated_data == {field: day(6)}


def test_update_reforma_d_un_dia(SZ):
    s = SZ.RenovationUpdateSerializer(data={'ini_date': day(6).isoformat(), 'fin_date': day(6).isoformat()})
    assert s.is_valid(), s.errors


def test_update_ini_posterior_a_fin(SZ):
    s = SZ.RenovationUpdateSerializer(data={'ini_date': day(7).isoformat(), 'fin_date': day(6).isoformat()})
    assert not s.is_valid() and 'fin_date' in s.errors


def test_update_ini_en_el_passat(SZ):
    s = SZ.RenovationUpdateSerializer(data={'ini_date': day(-1).isoformat()})
    assert not s.is_valid() and 'ini_date' in s.errors


def test_update_fin_date_en_el_passat_no_es_valida_al_serializer(SZ):
    """Només `ini_date` té la regla «no passat»; `fin_date` passat sol vol dir `fin < ini` (ho veu el servei)."""
    s = SZ.RenovationUpdateSerializer(data={'fin_date': day(-1).isoformat()})
    assert s.is_valid(), s.errors


def test_update_group_link_nul_es_rebutjat(SZ):
    s = SZ.RenovationUpdateSerializer(data={'group_link': None})
    assert not s.is_valid() and 'group_link' in s.errors


def test_update_group_link_invalid(SZ):
    assert not SZ.RenovationUpdateSerializer(data={'group_link': 'ftp://x/y'}).is_valid()


def test_update_descripcio_buida(SZ):
    assert not SZ.RenovationUpdateSerializer(data={'description': '  '}).is_valid()


@pytest.mark.parametrize('materials', [None, '', 'Pintura'])
def test_update_materials_acceptats(SZ, materials):
    s = SZ.RenovationUpdateSerializer(data={'materials_needed': materials})
    assert s.is_valid(), s.errors
    assert s.validated_data == {'materials_needed': materials}


# =============================================== sortida ===============================================

def _instance(RN, participants=(), group_link=None, **over):
    fields = dict(id=uuid.uuid4(), refuge_id=uuid.uuid4(), creator_id='u1', ini_date=date(2026, 11, 3),
                  fin_date=date(2026, 11, 5), description='Pintar', materials_needed=None)
    fields.update(over)
    inst = RN.Renovation(**fields)
    inst.participants_uids = list(participants)
    inst.group_link = group_link
    return inst


def test_output_forma_completa_amb_enllac(SZ, RN):
    inst = _instance(RN, participants=['u2', 'u3'], group_link=LINK, materials_needed='Pintura')
    data = SZ.RenovationSerializer(inst).data
    assert set(data) == FULL_KEYS
    assert data['id'] == str(inst.id) and data['refuge_id'] == str(inst.refuge_id)
    assert (data['ini_date'], data['fin_date']) == ('2026-11-03', '2026-11-05')
    assert data['participants_uids'] == ['u2', 'u3'] and data['group_link'] == LINK
    assert data['creator_uid'] == 'u1' and data['materials_needed'] == 'Pintura'


def test_output_sense_enllac_omet_la_clau(SZ, RN):
    data = SZ.RenovationSerializer(_instance(RN, group_link=None)).data
    assert set(data) == BASE_KEYS and 'group_link' not in data


def test_output_creador_nul_es_unknown(SZ, RN):
    data = SZ.RenovationSerializer(_instance(RN, creator_id=None)).data
    assert data['creator_uid'] == 'unknown'


def test_output_mai_exposa_expelled_uids(SZ, RN):
    inst = _instance(RN, group_link=LINK)
    inst.expelled_uids = ['u9']
    assert 'expelled_uids' not in SZ.RenovationSerializer(inst).data


def test_output_materials_nul_es_null_i_sense_participants_llista_buida(SZ, RN):
    data = SZ.RenovationSerializer(_instance(RN)).data
    assert data['materials_needed'] is None and data['participants_uids'] == []


def test_output_many_retorna_una_llista(SZ, RN):
    data = SZ.RenovationSerializer([_instance(RN), _instance(RN, group_link=LINK)], many=True).data
    assert isinstance(data, list) and len(data) == 2
    assert 'group_link' not in data[0] and data[1]['group_link'] == LINK
