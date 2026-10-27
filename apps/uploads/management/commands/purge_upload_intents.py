"""
Job horari: esborra els intents de pujada caducats (`expire_at < now()`, §2.19, §8.3) en lots de 1.000. Surt amb codi != 0
(`CommandError`) si falla, perquè el job de GitHub Actions ho detecti (com D28). No toca R2: el lifecycle de `quarantine/`
ja esborra els fitxers al cap d'1 dia.
"""
import logging

from django.core.management.base import BaseCommand, CommandError

from apps.uploads import services

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Esborra els intents de pujada caducats'

    def handle(self, *args, **options):
        try:
            purged = services.purge_expired_intents()
        except Exception as exc:
            logger.exception("Error en purgar els intents de pujada")
            raise CommandError('Error en purgar els intents de pujada') from exc
        self.stdout.write(f'Intents de pujada purgats: {purged}')
