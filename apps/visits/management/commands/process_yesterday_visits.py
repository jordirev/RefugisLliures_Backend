"""
Job diari: passa els visitants d'ahir a `user_visited_refuges`, esborra les visites d'ahir buides i purga les de més
de 12 mesos (§8.3). Surt amb codi != 0 (`CommandError`) si falla, perquè el job de GitHub Actions ho detecti (D28).
"""
import logging

from django.core.management.base import BaseCommand, CommandError

from apps.visits import services

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Processa les visites d'ahir i purga les visites antigues (>12 mesos)"

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Processant visites d'ahir..."))
        try:
            stats = services.process_yesterday_visits()
        except Exception as exc:
            logger.exception("Error en processar les visites d'ahir")
            raise CommandError("Error en processar les visites d'ahir") from exc
        try:
            purged = services.purge_old_visits()
        except Exception as exc:
            logger.exception('Error en purgar les visites antigues')
            raise CommandError('Error en purgar les visites antigues') from exc
        self.stdout.write(self.style.SUCCESS("Visites d'ahir processades correctament"))
        self.stdout.write(f'Visites processades: {stats["processed_visits"]}')
        self.stdout.write(f'Visites buides eliminades: {stats["deleted_visits"]}')
        self.stdout.write(f'Refugis actualitzats: {stats["updated_refuges"]}')
        self.stdout.write(f'Total visitants afegits: {stats["total_visitors_added"]}')
        self.stdout.write(f'Visites antigues purgades: {purged}')
