"""
ModerationService - Moderació automàtica pluggable de mitjans abans de publicar-los.

Arquitectura:
    ModerationProvider (interfície)
      ├─ HashBlocklistProvider   (ACTIU)  sha256 exacte + pHash (distància de Hamming)
      │                                  contra la col·lecció `moderation_hash_blocklist`
      ├─ PhotoDNAProvider        (stub, desactivat; cal accés de Microsoft/NCMEC)
      └─ GoogleContentSafetyProvider (stub, desactivat; cal accés a la Content Safety API)

Format d'un document de `moderation_hash_blocklist`:
    {sha256?: str (hex), phash?: str (hex de 64 bits, imagehash), category: 'csam'|...,
     source: str, added_at: ISO}

Si algun proveïdor actiu troba coincidència, el controller NO publica el fitxer, el mou a
`moderation-hold/`, bloqueja l'usuari, crea una denúncia `child_sexual_abuse` d'alta
prioritat i ho registra a l'auditoria (vegeu MediaUploadController).

Quan hi hagi domini propi a Cloudflare: docs/guides/cloudflare-domain-csam.md.
"""
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional

from .firestore_service import FirestoreService
from .cache_service import cache_service

logger = logging.getLogger(__name__)

PHASH_MAX_DISTANCE = 6  # bits de diferència (de 64) per considerar coincidència


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


def phash_distance(a: str, b: str) -> int:
    """Distància de Hamming entre dos pHash hex"""
    try:
        return bin(int(a, 16) ^ int(b, 16)).count('1')
    except (TypeError, ValueError):
        return 64


class HashBlocklistProvider(ModerationProvider):
    """Compara sha256 (exacte) i pHash (aproximat) amb una llista de hashes prohibits."""

    name = 'hash_blocklist'
    COLLECTION_NAME = 'moderation_hash_blocklist'
    CACHE_KEY = 'moderation_hash_blocklist:phashes'
    CACHE_TIMEOUT = 600

    def __init__(self):
        self.firestore_service = FirestoreService()

    @property
    def enabled(self) -> bool:
        return True

    def _load_phashes(self) -> List[dict]:
        cached = cache_service.get(self.CACHE_KEY)
        if cached is not None:
            return cached
        db = self.firestore_service.get_db()
        logger.log(23, f"Firestore READ: collection={self.COLLECTION_NAME} (phashes)")
        entries = []
        for doc in db.collection(self.COLLECTION_NAME).stream():
            data = doc.to_dict() or {}
            if data.get('phash'):
                entries.append({'id': doc.id, 'phash': data['phash'], 'category': data.get('category', 'csam')})
        cache_service.set(self.CACHE_KEY, entries, self.CACHE_TIMEOUT)
        return entries

    def check(self, media: ModerationInput) -> ModerationResult:
        db = self.firestore_service.get_db()
        if media.sha256:
            logger.log(23, f"Firestore QUERY: collection={self.COLLECTION_NAME} where sha256")
            matches = list(db.collection(self.COLLECTION_NAME).where('sha256', '==', media.sha256).limit(1).stream())
            if matches:
                data = matches[0].to_dict() or {}
                return ModerationResult(True, self.name, data.get('category', 'csam'), 'sha256',
                                        {'entry_id': matches[0].id})
        if media.phash:
            for entry in self._load_phashes():
                if phash_distance(media.phash, entry['phash']) <= PHASH_MAX_DISTANCE:
                    return ModerationResult(True, self.name, entry.get('category', 'csam'), 'phash',
                                            {'entry_id': entry['id']})
        return ModerationResult(False)


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
