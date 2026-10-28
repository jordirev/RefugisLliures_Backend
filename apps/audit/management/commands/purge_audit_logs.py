"""
Job diari: esborra les entrades d'`audit.audit_logs` caducades (`expire_at < now()`, §2.24, §8.3) en lots de 5.000. Surt
amb codi != 0 (`CommandError`) si falla, perquè el job ho detecti (com D28). **No està planificada** (TECH_DEBT R18).
"""
import logging

from django.core.management.base import BaseCommand, CommandError

from apps.audit import services

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Esborra les entrades d'auditoria caducades (365 dies; 5 anys si legal_hold)"

    def handle(self, *args, **options):
        try:
            purged = services.purge_expired()
        except Exception as exc:
            logger.exception("Error en purgar el registre d'auditoria")
            raise CommandError("Error en purgar el registre d'auditoria") from exc
        self.stdout.write(f"Entrades d'auditoria purgades: {purged}")
