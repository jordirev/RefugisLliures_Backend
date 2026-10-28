"""
Neteja del codi legacy de Firestore de la moderació (chunk 9; D40 (6)): sense BD.

- `apps/moderation`, `apps/audit` i les vistes de moderació ja no importen `RefugiLliureDAO` ni els DAOs/models/
  controllers legacy (`MediaReportController`, `MediaReportDAO`, `ModerationNoticeDAO`, `api.models.media_report`,
  `api.models.moderation_notice`), ni `firestore_service`/`cache_service`.
- `api.services.audit_log_service` desapareix (el servei viu a `apps.audit.services`).
- `apps/uploads` ja no importa els DAOs legacy de moderació.
- Les rutes de moderació continuen a `/api/media/reports/`, `/api/admin/media-reports/` i
  `/api/users/<uid>/moderation-notices/` (els mateixos `name=`).
"""
import ast
import re
from pathlib import Path

import pytest
from django.urls import resolve, reverse

ROOT = Path(__file__).resolve().parents[3]
FORBIDDEN = ('refugi_lliure_dao', 'RefugiLliureDAO', 'media_report_controller', 'media_report_dao',
             'moderation_notice_dao', 'api.models.media_report', 'api.models.moderation_notice',
             'api.services.audit_log_service', 'firestore_service', 'cache_service')


def python_files(*parts):
    base = ROOT.joinpath(*parts)
    return [p for p in base.rglob('*.py') if '/tests/' not in p.as_posix() and '\\tests\\' not in str(p)]


def imports_of(path):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            mod = ('.' * node.level) + (node.module or '')
            found.append(mod)
            found += [f'{mod}.{a.name}' for a in node.names]
    return found


@pytest.mark.parametrize('app', ['moderation', 'audit'])
def test_les_apps_noves_no_depenen_del_legacy(app):
    files = python_files('apps', app)
    assert any(f.name == 'services.py' for f in files), f'apps/{app}/services.py ha d\'existir'
    for f in files:
        text = f.read_text(encoding='utf-8')
        names = ' '.join(imports_of(f))
        for bad in FORBIDDEN:
            assert bad not in names, f'{f.relative_to(ROOT)} importa {bad}'
        assert not re.search(r'FirestoreService|firebase_admin\.firestore|cache_service', text), f.relative_to(ROOT)


def test_moderacio_no_importa_el_dao_de_refugis():
    for f in python_files('apps', 'moderation'):
        assert 'RefugiLliureDAO' not in f.read_text(encoding='utf-8'), f


def test_uploads_ja_no_importa_els_daos_legacy_de_moderacio():
    text = (ROOT / 'apps' / 'uploads' / 'services.py').read_text(encoding='utf-8')
    for bad in ('media_report_dao', 'moderation_notice_dao', 'api.models.media_report', 'api.models.moderation_notice',
                'api.services.audit_log_service', 'MediaReportDAO', 'ModerationNoticeDAO'):
        assert bad not in text, bad


@pytest.mark.parametrize('rel', ['apps/accounts/services.py', 'apps/refuges/services.py', 'apps/refuges/views.py',
                                 'apps/uploads/services.py', 'apps/uploads/views.py'])
def test_els_crida_dors_d_auditoria_usen_apps_audit(rel):
    text = (ROOT / rel).read_text(encoding='utf-8')
    assert 'api.services import audit_log_service' not in text and 'api.services.audit_log_service' not in text, rel


def test_el_servei_d_auditoria_legacy_i_el_controller_de_moderacio_ja_no_existeixen():
    for rel in ('api/services/audit_log_service.py', 'api/controllers/media_report_controller.py',
                'api/daos/media_report_dao.py', 'api/daos/moderation_notice_dao.py', 'api/models/media_report.py',
                'api/models/moderation_notice.py'):
        assert not (ROOT / rel).exists(), f'{rel} s\'ha d\'eliminar'


def test_les_rutes_de_moderacio_es_mantenen():
    assert reverse('media_reports') == '/api/media/reports/'
    assert reverse('admin_media_reports') == '/api/admin/media-reports/'
    assert reverse('admin_media_report_detail', kwargs={'id': 'abc'}) == '/api/admin/media-reports/abc/'
    assert reverse('user_moderation_notices', kwargs={'uid': 'u1'}) == '/api/users/u1/moderation-notices/'
    assert resolve('/api/media/reports/').func.view_class.__module__.startswith('apps.moderation')
    assert resolve('/api/admin/media-reports/x/').func.view_class.__module__.startswith('apps.moderation')
    assert resolve('/api/users/u1/moderation-notices/').func.view_class.__module__.startswith('apps.moderation')


def test_les_apps_estan_a_installed_apps_i_els_comandes_registrats():
    from django.conf import settings
    from django.core.management import get_commands
    assert 'apps.moderation' in settings.INSTALLED_APPS and 'apps.audit' in settings.INSTALLED_APPS
    commands = get_commands()
    assert commands['load_hash_blocklist'] == 'apps.moderation' and commands['purge_moderation'] == 'apps.moderation'
    assert commands['purge_audit_logs'] == 'apps.audit'
