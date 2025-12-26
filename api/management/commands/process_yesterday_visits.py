"""
Management command per processar les visites d'ahir
Afegeix els visitants a la llista de visitors del refugi i elimina visites buides
"""
import logging
from django.core.management.base import BaseCommand
from api.controllers.refuge_visit_controller import RefugeVisitController

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Processa les visites d\'ahir: afegeix visitants als refugis i elimina visites buides'

    def handle(self, *args, **options):
        """Processa les visites d'ahir"""
        self.stdout.write(self.style.NOTICE('Processant visites d\'ahir...'))
        
        try:
            controller = RefugeVisitController()
            success, stats, error = controller.process_yesterday_visits()
            
            if not success:
                self.stdout.write(self.style.ERROR(f'Error processant visites: {error}'))
                return
            
            # Mostra estadístiques
            self.stdout.write(self.style.SUCCESS('\n' + '=' * 80))
            self.stdout.write(self.style.SUCCESS('Visites d\'ahir processades correctament'))
            self.stdout.write(self.style.SUCCESS('=' * 80))
            self.stdout.write(f'\nVisites processades: {stats["processed_visits"]}')
            self.stdout.write(f'Visites buides eliminades: {stats["deleted_visits"]}')
            self.stdout.write(f'Refugis actualitzats: {stats["updated_refuges"]}')
            self.stdout.write(f'Total visitants afegits: {stats["total_visitors_added"]}\n')
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error inesperat: {str(e)}'))
            logger.error(f'Error en process_yesterday_visits command: {str(e)}')
