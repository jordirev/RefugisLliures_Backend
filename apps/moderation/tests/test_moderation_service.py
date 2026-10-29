"""
Tests de `ModerationService` (proveïdors de moderació automàtica: stubs desactivats, primer proveïdor que bloqueja).
"""
from unittest.mock import MagicMock

import pytest

from apps.moderation.moderation_service import (
    ModerationService, PhotoDNAProvider, GoogleContentSafetyProvider, ModerationInput, ModerationResult,
)


@pytest.mark.unit
class TestModerationService:
    def test_disabled_stubs_are_skipped(self):
        assert PhotoDNAProvider().enabled is False
        assert GoogleContentSafetyProvider().enabled is False
        service = ModerationService([PhotoDNAProvider(), GoogleContentSafetyProvider()])
        assert service.check(ModerationInput(sha256='x')).blocked is False

    def test_first_blocking_provider_wins(self):
        clean, dirty = MagicMock(enabled=True), MagicMock(enabled=True)
        clean.check.return_value = ModerationResult(False)
        dirty.check.return_value = ModerationResult(True, 'p', 'csam', 'sha256')
        result = ModerationService([clean, dirty]).check(ModerationInput(sha256='x'))
        assert result.blocked and result.provider == 'p'

    def test_provider_error_propagates(self):
        bad = MagicMock(enabled=True)
        bad.check.side_effect = RuntimeError('down')
        with pytest.raises(RuntimeError):
            ModerationService([bad]).check(ModerationInput(sha256='x'))
