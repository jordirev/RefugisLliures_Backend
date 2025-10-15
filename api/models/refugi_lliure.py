"""
Model de refugi per a l'aplicació RefugisLliures
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

@dataclass
class Coordinates:
    """Model per representar coordenades"""
    long: float
    lat: float
    
    def to_dict(self) -> dict:
        return {
            'long': self.long,
            'lat': self.lat
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Coordinates':
        # Handle both formats for coordinates
        if 'longitude' in data and 'latitude' in data:
            # Format from extract_coords_to_firestore command
            return cls(
                long=data.get('longitude', 0.0),
                lat=data.get('latitude', 0.0)
            )
        else:
            # Original format
            return cls(
                long=data.get('long', 0.0),
                lat=data.get('lat', 0.0)
            )

@dataclass
class InfoComplementaria:
    """Model per representar informació complementària del refugi"""
    manque_un_mur: int = 0
    cheminee: int = 0
    poele: int = 0
    couvertures: int = 0
    latrines: int = 0
    bois: int = 0
    eau: int = 0
    matelas: int = 0
    couchage: int = 0
    bas_flancs: int = 0
    lits: int = 0
    mezzanine_etage: int = 0  # Canviat de "mezzanine/etage" per compatibilitat Python
    
    def to_dict(self) -> dict:
        return {
            'manque_un_mur': self.manque_un_mur,
            'cheminee': self.cheminee,
            'poele': self.poele,
            'couvertures': self.couvertures,
            'latrines': self.latrines,
            'bois': self.bois,
            'eau': self.eau,
            'matelas': self.matelas,
            'couchage': self.couchage,
            'bas_flancs': self.bas_flancs,
            'lits': self.lits,
            'mezzanine/etage': self.mezzanine_etage  # Mapejat de tornada al format original
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'InfoComplementaria':
        return cls(
            manque_un_mur=data.get('manque_un_mur', 0),
            cheminee=data.get('cheminee', 0),
            poele=data.get('poele', 0),
            couvertures=data.get('couvertures', 0),
            latrines=data.get('latrines', 0),
            bois=data.get('bois', 0),
            eau=data.get('eau', 0),
            matelas=data.get('matelas', 0),
            couchage=data.get('couchage', 0),
            bas_flancs=data.get('bas_flancs', 0),
            lits=data.get('lits', 0),
            mezzanine_etage=data.get('mezzanine/etage', 0)
        )

@dataclass
class Refugi:
    """Model per representar un refugi"""
    id: str
    name: str
    coord: Coordinates
    altitude: int = 0
    places: int = 0
    remarque: str = ""
    info_comp: InfoComplementaria = field(default_factory=InfoComplementaria)
    description: str = ""
    links: List[str] = field(default_factory=list)
    type: str = ""
    modified_at: str = ""
    region: Optional[str] = None
    departement: Optional[str] = None
    
    def __post_init__(self):
        """Validacions després de la inicialització"""
        if not self.id:
            raise ValueError("ID és requerit")
        if not self.name:
            raise ValueError("Name és requerit")
        if not isinstance(self.coord, Coordinates):
            raise ValueError("Coordinates han de ser del tipus Coordinates")
    
    def to_dict(self) -> dict:
        """Converteix el refugi a diccionari"""
        return {
            'id': self.id,
            'name': self.name,
            'coord': self.coord.to_dict(),
            'altitude': self.altitude,
            'places': self.places,
            'remarque': self.remarque,
            'info_comp': self.info_comp.to_dict(),
            'description': self.description,
            'links': self.links,
            'type': self.type,
            'modified_at': self.modified_at,
            'region': self.region,
            'departement': self.departement
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Refugi':
        """Crea un refugi des d'un diccionari"""
        coord_data = data.get('coord', {})
        info_comp_data = data.get('info_comp', {})
        
        return cls(
            id=str(data.get('id', '')),
            name=data.get('name', ''),
            coord=Coordinates.from_dict(coord_data),
            altitude=data.get('altitude', 0),
            places=data.get('places', 0),
            remarque=data.get('remarque', ''),
            info_comp=InfoComplementaria.from_dict(info_comp_data),
            description=data.get('description', ''),
            links=data.get('links', []),
            type=data.get('type', ''),
            modified_at=data.get('modified_at', ''),
            region=data.get('region'),
            departement=data.get('departement')
        )
    
    def __str__(self) -> str:
        """Representació textual del refugi"""
        return f"Refugi(id={self.id}, name={self.name}, type={self.type})"
    
    def __repr__(self) -> str:
        """Representació detallada del refugi"""
        return self.__str__()

@dataclass
class RefugiCoordinates:
    """Model simplificat per representar només les coordenades d'un refugi"""
    refugi_id: str
    refugi_name: str
    coordinates: Coordinates
    geohash: str = ""
    
    def to_dict(self) -> dict:
        return {
            'refugi_id': self.refugi_id,
            'refugi_name': self.refugi_name,
            'coordinates': self.coordinates.to_dict(),
            'geohash': self.geohash
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'RefugiCoordinates':
        coord_data = data.get('coordinates', {})
        
        # Handle both formats: original (long, lat) and coordinates document (longitude, latitude)
        if 'longitude' in coord_data and 'latitude' in coord_data:
            # Format from extract_coords_to_firestore command
            coordinates = Coordinates(
                long=coord_data.get('longitude', 0.0),
                lat=coord_data.get('latitude', 0.0)
            )
        else:
            # Original format or standard format
            coordinates = Coordinates.from_dict(coord_data)
        
        return cls(
            refugi_id=data.get('refugi_id', ''),
            refugi_name=data.get('refugi_name', ''),
            coordinates=coordinates,
            geohash=data.get('geohash', '')
        )

@dataclass
class RefugiSearchFilters:
    """Model per representar filtres de cerca"""
    # Text search
    query_text: str = ""
    name: str = ""
    
    # Location filters
    region: str = ""
    departement: str = ""

    # Characteristics filters
    type: str = ""
    
    # Numeric range filters
    places_min: Optional[int] = None
    places_max: Optional[int] = None
    altitude_min: Optional[int] = None
    altitude_max: Optional[int] = None
    
    # Info complementaria filters (1 = has feature, 0 or None = ignore)
    cheminee: Optional[int] = None
    poele: Optional[int] = None
    couvertures: Optional[int] = None
    latrines: Optional[int] = None
    bois: Optional[int] = None
    eau: Optional[int] = None
    matelas: Optional[int] = None
    couchage: Optional[int] = None
    lits: Optional[int] = None
    
    def __post_init__(self):
        """Validacions dels filtres"""
            