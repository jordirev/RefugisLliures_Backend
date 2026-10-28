"""
Retenció de la moderació (§8.3): esborra les denúncies i els avisos caducats en lots de 5.000 (denúncies no `legal_hold`:
24 mesos després de resoldre's; `legal_hold`: 5 anys; avisos: 24 mesos, tret dels lligats a una denúncia `legal_hold`
vigent). Surt amb codi != 0 (`CommandError`) si falla (com D28). **No està planificada** (TECH_DEBT R18).
"""
import logging

from django.core.management.base import BaseCommand, CommandError

from apps.moderation import services

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Esborra les denúncies i els avisos de moderació caducats'

    def handle(self, *args, **options):
        try:
            purged = services.purge_expired()
        except Exception as exc:
            logger.exception('Error en purgar la moderació')
            raise CommandError('Error en purgar la moderació') from exc
        self.stdout.write(f"Denúncies purgades: {purged['reports']}")
        self.stdout.write(f"Avisos purgats: {purged['notices']}")
