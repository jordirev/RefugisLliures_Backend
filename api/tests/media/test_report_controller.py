"""
Tests de MediaReportController: denúncies, autoocultació, resolució, strikes i bloqueig.
"""
from unittest.mock import MagicMock, call

import pytest

from api.controllers.media_report_controller import (
    MediaReportController, ERROR_OWN_MEDIA, ERROR_ALREADY_REPORTED, ERROR_ALREADY_RESOLVED,
    ERROR_REPORT_NOT_FOUND, ERROR_MEDIA_NOT_FOUND, ERROR_REFUGE_NOT_FOUND,
)
from api.daos.media_report_dao import DUPLICATE_REPORT_ERROR
from api.models.media_report import MediaReport, build_report_id
from api.tests.media.helpers import fake_r2_service

KEY = 'refugis-lliures/ref_1/abc.webp'


@pytest.fixture
def ctrl():
    controller = MediaReportController()
    controller.report_dao = MagicMock()
    controller.notice_dao = MagicMock()
    controller.refugi_dao = MagicMock()
    controller.user_dao = MagicMock()
    controller.experience_dao = MagicMock()
    controller.media_service = fake_r2_service()
    controller.refugi_dao.get_media_entry.return_value = (True, {'creator_uid': 'author', 'status': 'visible'})
    controller.report_dao.create_report.return_value = (True, None)
    controller.report_dao.count_distinct_pending_reporters.return_value = 1
    controller.report_dao.resolve_reports.return_value = True
    controller.refugi_dao.update_media_status.return_value = True
    controller.user_dao.set_blocked.return_value = True
    return controller


def pending_report(reason='hate_speech', reporter='rep_1', **kw):
    return MediaReport(id=build_report_id('ref_1', KEY, reporter), refuge_id='ref_1', media_key=KEY,
                       reporter_uid=reporter, reason=reason, media_creator_uid='author',
                       details='d' if reason == 'other' else None, created_at='2025-01-01T00:00:00', **kw)


@pytest.mark.controllers
class TestCreateReport:
    def test_author_cannot_report_own_media(self, ctrl):
        data, error = ctrl.create_report('author', 'ref_1', KEY, 'hate_speech')
        assert data is None and error == ERROR_OWN_MEDIA
        ctrl.report_dao.create_report.assert_not_called()

    def test_duplicate_report(self, ctrl):
        ctrl.report_dao.create_report.return_value = (False, DUPLICATE_REPORT_ERROR)
        data, error = ctrl.create_report('rep_1', 'ref_1', KEY, 'hate_speech')
        assert error == ERROR_ALREADY_REPORTED

    def test_refuge_or_media_not_found(self, ctrl):
        ctrl.refugi_dao.get_media_entry.return_value = (False, None)
        assert ctrl.create_report('r', 'ref_1', KEY, 'hate_speech')[1] == ERROR_REFUGE_NOT_FOUND
        ctrl.refugi_dao.get_media_entry.return_value = (True, None)
        assert ctrl.create_report('r', 'ref_1', KEY, 'hate_speech')[1] == ERROR_MEDIA_NOT_FOUND

    def test_deterministic_id_per_reporter(self, ctrl):
        ctrl.create_report('rep_1', 'ref_1', KEY, 'hate_speech')
        report = ctrl.report_dao.create_report.call_args.args[0]
        assert report.id == build_report_id('ref_1', KEY, 'rep_1')
        assert report.media_creator_uid == 'author'
        assert report.priority == 'normal'

    @pytest.mark.parametrize('reason', ['child_sexual_abuse', 'child_endangerment', 'sexual_nonconsensual',
                                        'terrorism_extremism', 'my_image'])
    def test_auto_hide_reasons_hide_immediately_with_high_priority(self, ctrl, reason):
        data, error = ctrl.create_report('rep_1', 'ref_1', KEY, reason)

        assert error is None
        assert data['media_hidden'] is True
        assert data['priority'] == 'high'
        ctrl.refugi_dao.update_media_status.assert_called_once_with(
            'ref_1', KEY, 'hidden_pending_review', only_if_status=['visible'])
        ctrl.report_dao.count_distinct_pending_reporters.assert_not_called()
        notice = ctrl.notice_dao.create_notice.call_args.args[0]
        assert notice['uid'] == 'author' and notice['type'] == 'content_hidden' and notice['automated'] is True

    def test_other_reasons_hide_from_three_distinct_reporters(self, ctrl):
        ctrl.report_dao.count_distinct_pending_reporters.return_value = 2
        data, _ = ctrl.create_report('rep_2', 'ref_1', KEY, 'fraud_scam_spam')
        assert data['media_hidden'] is False
        ctrl.refugi_dao.update_media_status.assert_not_called()

        ctrl.report_dao.count_distinct_pending_reporters.return_value = 3
        data, _ = ctrl.create_report('rep_3', 'ref_1', KEY, 'fraud_scam_spam')
        assert data['media_hidden'] is True
        ctrl.refugi_dao.update_media_status.assert_called_once()

    def test_already_hidden_does_not_notify_again(self, ctrl):
        ctrl.refugi_dao.update_media_status.return_value = False
        data, _ = ctrl.create_report('rep_1', 'ref_1', KEY, 'my_image')
        assert data['media_hidden'] is False
        ctrl.notice_dao.create_notice.assert_not_called()

    def test_other_requires_details(self, ctrl):
        data, error = ctrl.create_report('rep_1', 'ref_1', KEY, 'other', details='   ')
        assert data is None and error.startswith('invalid:')


@pytest.mark.controllers
class TestResolveReport:
    def test_not_found_and_already_resolved(self, ctrl):
        ctrl.report_dao.get_report.return_value = None
        assert ctrl.resolve_report('x', 'dismiss', 's', 'admin')[1] == ERROR_REPORT_NOT_FOUND
        ctrl.report_dao.get_report.return_value = pending_report(status='resolved')
        assert ctrl.resolve_report('x', 'dismiss', 's', 'admin')[1] == ERROR_ALREADY_RESOLVED

    def test_dismiss_restores_visibility_and_resolves_all_pending(self, ctrl):
        report = pending_report()
        other = pending_report(reporter='rep_2')
        ctrl.report_dao.get_report.return_value = report
        ctrl.report_dao.list_reports_for_media.return_value = [report, other]

        result, error = ctrl.resolve_report(report.id, 'dismiss', 'No incompleix les normes', 'admin')

        assert error is None
        assert result['media_status'] == 'visible'
        assert set(result['resolved_report_ids']) == {report.id, other.id}
        ctrl.refugi_dao.update_media_status.assert_called_once_with(
            'ref_1', KEY, 'visible', only_if_status=['hidden_pending_review'])
        updates = ctrl.report_dao.resolve_reports.call_args.args[1]
        assert updates['status'] == 'resolved' and updates['action'] == 'dismiss'
        assert updates['resolved_by'] == 'admin' and updates['statement'] == 'No incompleix les normes'
        assert ctrl.notice_dao.create_notice.call_args.args[0]['type'] == 'content_restored'
        ctrl.user_dao.increment_moderation_strikes.assert_not_called()

    def test_remove_sets_removed_and_notifies(self, ctrl):
        ctrl.report_dao.get_report.return_value = pending_report()
        ctrl.report_dao.list_reports_for_media.return_value = []
        result, _ = ctrl.resolve_report('r', 'remove', 'Contingut d\'odi', 'admin')
        assert result['media_status'] == 'removed'
        ctrl.refugi_dao.update_media_status.assert_called_once_with('ref_1', KEY, 'removed')
        notice = ctrl.notice_dao.create_notice.call_args.args[0]
        assert notice['type'] == 'content_removed' and notice['statement'] == 'Contingut d\'odi'
        assert result['user_blocked'] is False

    def test_strike_below_threshold_does_not_block(self, ctrl):
        ctrl.report_dao.get_report.return_value = pending_report()
        ctrl.report_dao.list_reports_for_media.return_value = []
        ctrl.user_dao.increment_moderation_strikes.return_value = 2
        result, _ = ctrl.resolve_report('r', 'remove_and_strike', 'Motiu', 'admin')
        assert result['strikes'] == 2 and result['user_blocked'] is False
        ctrl.user_dao.set_blocked.assert_not_called()

    def test_three_strikes_blocks_user(self, ctrl):
        ctrl.report_dao.get_report.return_value = pending_report()
        ctrl.report_dao.list_reports_for_media.return_value = []
        ctrl.user_dao.increment_moderation_strikes.return_value = 3

        result, error = ctrl.resolve_report('r', 'remove_and_strike', 'Tercera infracció', 'admin')

        assert error is None
        assert result['strikes'] == 3 and result['user_blocked'] is True
        assert ctrl.user_dao.set_blocked.call_args.args[:2] == ('author', True)
        assert ctrl.user_dao.set_blocked.call_args.kwargs['reason'] == 'strikes'
        types = [c.args[0]['type'] for c in ctrl.notice_dao.create_notice.call_args_list]
        assert types == ['strike', 'account_blocked']

    def test_confirmed_csam_blocks_immediately_and_holds_media(self, ctrl):
        report = pending_report(reason='child_sexual_abuse')
        ctrl.report_dao.get_report.return_value = report
        ctrl.report_dao.list_reports_for_media.return_value = [report]
        thumb = KEY.replace('.webp', '_thumb.webp')
        ctrl.media_service.store.update({KEY: b'img', thumb: b'thumb'})
        ctrl.refugi_dao.delete_media_metadata.return_value = (True, {
            'creator_uid': 'author', 'thumb_key': thumb, 'experience_id': 'exp_1'})

        result, error = ctrl.resolve_report(report.id, 'remove', 'CSAM confirmat', 'admin')

        assert error is None
        assert result['user_blocked'] is True and result['media_status'] == 'held'
        ctrl.user_dao.increment_moderation_strikes.assert_not_called()
        assert ctrl.user_dao.set_blocked.call_args.kwargs['reason'] == 'csam_confirmed'
        store = ctrl.media_service.store
        assert KEY not in store and thumb not in store
        assert store[f'moderation-hold/{KEY}'] == b'img'
        assert store[f'moderation-hold/{thumb}'] == b'thumb'
        ctrl.experience_dao.remove_media_key.assert_called_once_with('exp_1', KEY)
        ctrl.user_dao.remove_uploaded_photos_keys.assert_called_once_with('author', [KEY])

    def test_resolve_persistence_failure(self, ctrl):
        ctrl.report_dao.get_report.return_value = pending_report()
        ctrl.report_dao.list_reports_for_media.return_value = []
        ctrl.report_dao.resolve_reports.return_value = False
        result, error = ctrl.resolve_report('r', 'dismiss', 's', 'admin')
        assert result is None and 'Error intern' in error


@pytest.mark.controllers
class TestListReportsAndNotices:
    def test_list_with_media_preview(self, ctrl):
        hold = MediaReport(id='h', refuge_id='refuge', media_key='moderation-hold/u/up', reporter_uid='system',
                           reason='child_sexual_abuse', priority='high')
        ctrl.report_dao.list_reports.return_value = [hold, pending_report()]
        ctrl.refugi_dao.get_raw_media_metadata.return_value = {
            KEY: {'creator_uid': 'author', 'status': 'hidden_pending_review', 'thumb_key': 'refugis-lliures/ref_1/abc_thumb.webp'}}

        reports, error = ctrl.list_reports('pending', 'admin')

        assert error is None
        assert reports[0]['media'] is None  # l'evidència retinguda mai es previsualitza
        media = reports[1]['media']
        assert media['key'] == KEY and media['status'] == 'hidden_pending_review'
        assert 'abc_thumb.webp' in media['thumb_url']
        ctrl.refugi_dao.get_raw_media_metadata.assert_called_once_with('ref_1')

    def test_user_notices(self, ctrl):
        notice = MagicMock()
        notice.to_dict.return_value = {'id': 'n1'}
        ctrl.notice_dao.list_by_uid.return_value = [notice]
        assert ctrl.get_user_notices('u') == ([{'id': 'n1'}], None)
        ctrl.notice_dao.list_by_uid.side_effect = Exception('boom')
        assert ctrl.get_user_notices('u')[0] is None
