"""
Mapper per a la conversió entre dades de Firestore i models de refugi
"""
from typing import List, Dict, Any, Optional

from api.models.media_metadata import RefugeMediaMetadata
from api.services import r2_media_service
from ..models.refugi_lliure import Refugi, RefugiCoordinates, Coordinates

class RefugiLliureMapper:
    """Mapper per convertir entre dades de Firestore i models de refugi"""
    
    @staticmethod
    def firestore_to_model(data: Dict[str, Any]) -> Refugi:
        """Converteix dades de Firestore a model Refugi"""
        return Refugi.from_dict(data)
    
    @staticmethod
    def model_to_firestore(refugi: Refugi) -> Dict[str, Any]:
        """Converteix model Refugi a format Firestore"""
        refugi_dict = refugi.to_dict()
        if 'images_metadata' in refugi_dict:
            refugi_dict.pop('images_metadata')
        return refugi_dict
    
    @staticmethod
    def firestore_list_to_models(data_list: List[Dict[str, Any]]) -> List[Refugi]:
        """Converteix llista de dades de Firestore a llista de models"""
        return [RefugiLliureMapper.firestore_to_model(data) for data in data_list]
    
    @staticmethod
    def models_to_firestore_list(refugis: List[Refugi]) -> List[Dict[str, Any]]:
        """Converteix llista de models a llista de dades Firestore"""
        return [RefugiLliureMapper.model_to_firestore(refugi) for refugi in refugis]
    

    # Mappers per als objectes RefugiInfo dels favorits i visitats
    @staticmethod
    def dict_to_refugi_info_representation(data: Dict[str, Any]) -> Refugi:
        """Tornem el diccionari a mostrar a la resposta de l'API amb les URLs pre-signades de la primera foto del refugi"""
        # Extreu només els camps necessaris
        images_metadata = data.get('images_metadata', None)
        data = {
            'id': data.get('id', ''),
            'name': data.get('name', ''),
            'region': data.get('region', ''),
            'places': data.get('places', 0),
            'coord': data.get('coord', {}),
            'media_metadata': data.get('media_metadata', {}),
            'images_metadata': images_metadata
        }

        # Si ja tenim images_metadata, no cal generar la URL pre-signada
        if images_metadata:
            # Només mostrem la primera imatge
            data['images_metadata'] = [data['images_metadata'][0]]
            del data['media_metadata']
            
        else:
            # Obtenim la key de la primera imatge i generem la URL pre-signada
            media_metadata_dict = data.get('media_metadata')
            if media_metadata_dict:
                first_media_key = next(iter(media_metadata_dict))
                media_service = r2_media_service.get_refugi_media_service()
                first_media_url = media_service.generate_presigned_url(first_media_key)
                data['images_metadata'] = [RefugeMediaMetadata(first_media_key, first_media_url).to_dict()]
                del data['media_metadata']
            else:
                data['images_metadata'] = None

        return data

    @staticmethod
    def dict_list_to_refugi_info_representations(data_list: List[Dict[str, Any]]) -> List[Refugi]:
        """Converteix llista de dades de Firestore a llista de models"""
        return [RefugiLliureMapper.dict_to_refugi_info_representation(data) for data in data_list]
    
    
    @staticmethod
    def format_search_response(refugis: List[Refugi]) -> Dict[str, Any]:
        """
        Formatea la resposta de cerca
        Args:
            refugis: Llista de refugis
            include_visitors: Si True, inclou la llista de visitants. Si False, l'omet.
            include_media_metadata: Si True, inclou media_metadata i images_metadata. Si False, els omet.
        """
        results = []
        for refugi in refugis:
            refugi_dict = refugi.to_dict()
            if 'media_metadata' in refugi_dict:
                refugi_dict.pop('media_metadata', None)
            results.append(refugi.to_dict())
        
        return {
            'count': len(refugis),
            'has_filters': True,
            'results': results
        }
    
    @staticmethod
    def format_search_response_from_raw_data(refugis_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Formatea la resposta de cerca des de dades raw (per coordenades)"""
        return {
            'count': len(refugis_data),
            'has_filters': False,
            'results': refugis_data
        }
    
