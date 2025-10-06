from django.core.exceptions import ValidationError
from django.db import transaction
from rest_framework import status
from rest_framework.response import Response
from ..models import RefugiLliure
from ..serializers import RefugiLliureSerializer


class RefugiLliureController:
    """
    Controlador per gestionar la lògica de negoci del model RefugiLliure
    """
    
    @staticmethod
    def get_all_refugis(queryset=None):
        """
        Retorna tots els refugis disponibles
        """
        try:
            if queryset is None:
                queryset = RefugiLliure.objects.all()
            
            return {
                'success': True,
                'data': queryset,
                'message': 'Refugis obtinguts correctament'
            }
        except Exception as e:
            return {
                'success': False,
                'data': None,
                'message': f'Error obtenint els refugis: {str(e)}'
            }
    
    @staticmethod
    def get_refugi_by_id(refugi_id):
        """
        Retorna un refugi específic per ID
        """
        try:
            refugi = RefugiLliure.objects.get(id=refugi_id)
            return {
                'success': True,
                'data': refugi,
                'message': 'Refugi obtingut correctament'
            }
        except RefugiLliure.DoesNotExist:
            return {
                'success': False,
                'data': None,
                'message': 'Refugi no trobat',
                'error_code': 'REFUGI_NOT_FOUND'
            }
        except Exception as e:
            return {
                'success': False,
                'data': None,
                'message': f'Error obtenint el refugi: {str(e)}'
            }
    
    @staticmethod
    def filter_refugis_by_region(regio):
        """
        Filtra refugis per regió
        """
        try:
            refugis = RefugiLliure.objects.filter(regio=regio)
            return {
                'success': True,
                'data': refugis,
                'message': f'Refugis de la regió {regio} obtinguts correctament'
            }
        except Exception as e:
            return {
                'success': False,
                'data': None,
                'message': f'Error filtrant per regió: {str(e)}'
            }
    
    @staticmethod
    def filter_available_refugis():
        """
        Retorna només els refugis disponibles (oberts i no tancats)
        """
        try:
            refugis = RefugiLliure.objects.filter(estat='obert', tancat=False)
            return {
                'success': True,
                'data': refugis,
                'message': 'Refugis disponibles obtinguts correctament'
            }
        except Exception as e:
            return {
                'success': False,
                'data': None,
                'message': f'Error obtenint refugis disponibles: {str(e)}'
            }
    
    @staticmethod
    def validate_refugi_data(data):
        """
        Valida les dades d'un refugi abans de crear o actualitzar
        """
        errors = []
        
        # Validacions personalitzades
        if 'altitud' in data and data['altitud'] < 0:
            errors.append('L\'altitud no pot ser negativa')
        
        if 'capacitat' in data and data['capacitat'] <= 0:
            errors.append('La capacitat ha de ser major que 0')
        
        return {
            'is_valid': len(errors) == 0,
            'errors': errors
        }