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
        return cls(
            long=data.get('long'),
            lat=data.get('lat')
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
    visitors: List[str] = field(default_factory=list)
    
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
            'departement': self.departement,
            'visitors': self.visitors
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
            departement=data.get('departement'),
            visitors=data.get('visitors', [])
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
    refuge_id: str
    refugi_name: str
    coord: Coordinates
    geohash: str = ""
    
    def to_dict(self) -> dict:
        return {
            'refuge_id': self.refuge_id,
            'refugi_name': self.refugi_name,
            'coord': self.coord.to_dict(),
            'geohash': self.geohash
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'RefugiCoordinates':
        coord_data = data.get('coord', {})
        coord = Coordinates.from_dict(coord_data)

        return cls(
            refuge_id=data.get('refuge_id', ''),
            refugi_name=data.get('refugi_name', ''),
            coord=coord,
            geohash=data.get('geohash', '')
        )

@dataclass
class RefugiSearchFilters:
    """Model per representar filtres de cerca"""
    # Text search
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
        # Normalize empty strings to defaults
        if self.name is None:
            self.name = ""
        if self.region is None:
            self.region = ""
        if self.departement is None:
            self.departement = ""
        if self.type is None:
            self.type = ""

    def to_dict(self) -> dict:
        """Retorna una representació dict dels filtres.

        Aquesta representació s'utilitza per generar claus de cache
        basades en els valors dels filtres. Només incloem camps
        que siguin rellevants i establim valors normals per a None.
        """
        out: Dict[str, Any] = {}

        # Include text filters only when non-empty
        if isinstance(self.name, str) and self.name.strip():
            out['name'] = self.name.strip()
        if isinstance(self.region, str) and self.region.strip():
            out['region'] = self.region.strip()
        if isinstance(self.departement, str) and self.departement.strip():
            out['departement'] = self.departement.strip()
        if isinstance(self.type, str) and self.type.strip():
            out['type'] = self.type.strip()

        # Numeric ranges
        if self.places_min is not None:
            out['places_min'] = self.places_min
        if self.places_max is not None:
            out['places_max'] = self.places_max
        if self.altitude_min is not None:
            out['altitude_min'] = self.altitude_min
        if self.altitude_max is not None:
            out['altitude_max'] = self.altitude_max

        # Include amenity filters only when explicitly requested (== 1)
        amenity_fields = [
            'cheminee', 'poele', 'couvertures', 'latrines',
            'bois', 'eau', 'matelas', 'couchage', 'lits'
        ]
        for field_name in amenity_fields:
            value = getattr(self, field_name)
            if value == 1:
                out[field_name] = 1

        return out

    @classmethod
    def from_dict(cls, data: dict) -> 'RefugiSearchFilters':
        """Crea un RefugiSearchFilters a partir d'un dict (opcional)."""
        return cls(
            name=data.get('name', ''),
            region=data.get('region', ''),
            departement=data.get('departement', ''),
            type=data.get('type', ''),
            places_min=data.get('places_min'),
            places_max=data.get('places_max'),
            altitude_min=data.get('altitude_min'),
            altitude_max=data.get('altitude_max'),
            cheminee=data.get('cheminee'),
            poele=data.get('poele'),
            couvertures=data.get('couvertures'),
            latrines=data.get('latrines'),
            bois=data.get('bois'),
            eau=data.get('eau'),
            matelas=data.get('matelas'),
            couchage=data.get('couchage'),
            lits=data.get('lits'),
        )
            