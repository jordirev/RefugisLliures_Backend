"""
ModerationService - Moderació automàtica pluggable de mitjans abans de publicar-los.

Arquitectura:
    ModerationProvider (interfície)
      ├─ HashBlocklistProvider   (ACTIU)  sha256 exacte + pHash (distància de Hamming <= 6)
      │                                  contra la taula `moderation.moderation_hash_blocklist` de PostgreSQL
      ├─ PhotoDNAProvider        (stub, desactivat; cal accés de Microsoft/NCMEC)
      └─ GoogleContentSafetyProvider (stub, desactivat; cal accés a la Content Safety API)

La llista de hashes és il·legible per a l'aplicació (el rol `app` no hi té cap privilegi) i no es carrega mai a memòria:
la coincidència es resol a la BD amb la funció `moderation.fn_hash_match` (`apps.moderation.selectors.hash_match`). La taula
s'alimenta amb `python manage.py load_hash_blocklist <fitxer.csv>` i comença buida.

Si algun proveïdor actiu troba coincidència, la pujada NO es publica: es mou l'evidència a `moderation-hold/<upload_id>`,
es bloqueja l'usuari, es crea una denúncia `child_sexual_abuse` d'alta prioritat amb `legal_hold`, un avís i
l'auditoria (vegeu `apps.uploads.services`).

Quan hi hagi domini propi a Cloudflare: docs/guides/cloudflare-domain-csam.md.
"""
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional

from apps.moderation import selectors

logger = logging.getLogger(__name__)


@dataclass
class ModerationInput:
    sha256: str
    phash: Optional[str] = None
    media_type: str = 'image'
    data: Optional[bytes] = None  # bytes processats (per a proveïdors externs)


@dataclass
class ModerationResult:
    blocked: bool = False
    provider: Optional[str] = None
    category: Optional[str] = None
    match_type: Optional[str] = None  # 'sha256' | 'phash' | ...
    details: dict = field(default_factory=dict)


class ModerationProvider(ABC):
    """Interfície d'un proveïdor de moderació"""

    name: str = 'provider'

    @property
    @abstractmethod
    def enabled(self) -> bool:
        """Si el proveïdor s'ha d'executar"""

    @abstractmethod
    def check(self, media: ModerationInput) -> ModerationResult:
        """Retorna ModerationResult. Pot llançar excepcions (el servei les tracta)."""


class HashBlocklistProvider(ModerationProvider):
    """Compara sha256 (exacte) i pHash (aproximat) amb la llista de hashes prohibits de PostgreSQL."""

    name = 'hash_blocklist'

    @property
    def enabled(self) -> bool:
        return True

    def check(self, media: ModerationInput) -> ModerationResult:
        match = selectors.hash_match(sha256=media.sha256, phash_hex=media.phash)
        if match is None:
            return ModerationResult(False)
        return ModerationResult(True, self.name, match.category, match.match_type, {'entry_id': match.entry_id})


class PhotoDNAProvider(ModerationProvider):
    """Stub: Microsoft PhotoDNA Cloud Service (requereix aprovació). Desactivat."""

    name = 'photodna'

    @property
    def enabled(self) -> bool:
        return False

    def check(self, media: ModerationInput) -> ModerationResult:  # pragma: no cover - stub
        raise NotImplementedError("PhotoDNA no està configurat (vegeu docs/guides/cloudflare-domain-csam.md)")


class GoogleContentSafetyProvider(ModerationProvider):
    """Stub: Google Content Safety API (requereix aprovació). Desactivat."""

    name = 'google_content_safety'

    @property
    def enabled(self) -> bool:
        return False

    def check(self, media: ModerationInput) -> ModerationResult:  # pragma: no cover - stub
        raise NotImplementedError("Google Content Safety API no està configurada")


class ModerationService:
    """Executa tots els proveïdors actius; el primer que bloqueja guanya."""

    def __init__(self, providers: Optional[List[ModerationProvider]] = None):
        self.providers = providers if providers is not None else [
            HashBlocklistProvider(),
            PhotoDNAProvider(),
            GoogleContentSafetyProvider(),
        ]

    def check(self, media: ModerationInput) -> ModerationResult:
        """
        Raises:
            Exception: si un proveïdor actiu falla (fail-closed: el fitxer no es publica)
        """
        for provider in self.providers:
            if not provider.enabled:
                continue
            result = provider.check(media)
            if result.blocked:
                logger.warning(f"Moderació: coincidència del proveïdor {provider.name} ({result.match_type})")
                return result
        return ModerationResult(False)
