"""
Tests per als models de metadades de mitjans
"""
import pytest
from api.models.media_metadata import MediaMetadata, RefugeMediaMetadata

@pytest.mark.models
class TestMediaMetadata:
    """Tests per al model MediaMetadata"""
    
    def test_create_media_metadata(self):
        """Test creació bàsica de MediaMetadata"""
        media = MediaMetadata(
            key="path/to/file.jpg",
            url="https://example.com/file.jpg",
            uploaded_at="2024-12-08T10:30:00Z"
        )
        
        assert media.key == "path/to/file.jpg"
        assert media.url == "https://example.com/file.jpg"
        assert media.uploaded_at == "2024-12-08T10:30:00Z"
        assert media.uploaded_at == "2024-12-08T10:30:00Z"
        # Revisa el model: MediaMetadata no té creator_uid en la definició de classe base en el fitxer que he llegit?
        # Línia 21: key: str, url: str, uploaded_at: str = None. 
        # Però el docstring diu "creator_uid: UID de l'usuari". 
        # Sembla que el docstring no coincideix amb la definició de la classe base, o potser m'he perdut alguna cosa.
        # En RefugeMediaMetadata sí que hi és.
    
    def test_to_dict(self):
        """Test conversió a diccionari"""
        media = MediaMetadata(
            key="path/to/file.jpg",
            url="https://example.com/file.jpg",
            uploaded_at="2024-12-08T10:30:00Z"
        )
        
        data = media.to_dict()
        assert data['key'] == "path/to/file.jpg"
        assert data['url'] == "https://example.com/file.jpg"
        assert data['uploaded_at'] == "2024-12-08T10:30:00Z"
    
    def test_from_dict(self):
        """Test creació des de diccionari"""
        data = {
            'key': "path/to/file.jpg",
            'url': "https://example.com/file.jpg",
            'uploaded_at': "2024-12-08T10:30:00Z"
        }
        
        media = MediaMetadata.from_dict(data)
        assert isinstance(media, MediaMetadata)
        assert media.key == "path/to/file.jpg"
        assert media.url == "https://example.com/file.jpg"
        assert media.uploaded_at == "2024-12-08T10:30:00Z"

@pytest.mark.models
class TestRefugeMediaMetadata:
    """Tests per al model RefugeMediaMetadata"""
    
    def test_create_refuge_media_metadata(self):
        """Test creació de RefugeMediaMetadata"""
        media = RefugeMediaMetadata(
            key="path/to/file.jpg",
            url="https://example.com/file.jpg",
            uploaded_at="2024-12-08T10:30:00Z",
            creator_uid="user_123",
            experience_id="exp_456"
        )
        
        assert media.key == "path/to/file.jpg"
        assert media.creator_uid == "user_123"
        assert media.experience_id == "exp_456"
    
    def test_to_dict(self):
        """Test conversió a diccionari"""
        media = RefugeMediaMetadata(
            key="path/to/file.jpg",
            url="https://example.com/file.jpg",
            uploaded_at="2024-12-08T10:30:00Z",
            creator_uid="user_123",
            experience_id="exp_456"
        )
        
        data = media.to_dict()
        assert data['key'] == "path/to/file.jpg"
        assert data['creator_uid'] == "user_123"
        assert data['experience_id'] == "exp_456"
    
    def test_to_dict_without_experience(self):
        """Test conversió a diccionari sense experience_id"""
        media = RefugeMediaMetadata(
            key="path/to/file.jpg",
            url="https://example.com/file.jpg",
            uploaded_at="2024-12-08T10:30:00Z",
            creator_uid="user_123"
        )
        
        data = media.to_dict()
        assert 'experience_id' not in data
    
    def test_from_dict(self):
        """Test creació des de diccionari"""
        data = {
            'key': "path/to/file.jpg",
            'url': "https://example.com/file.jpg",
            'uploaded_at': "2024-12-08T10:30:00Z",
            'creator_uid': "user_123",
            'experience_id': "exp_456"
        }
        
        media = RefugeMediaMetadata.from_dict(data)
        assert isinstance(media, RefugeMediaMetadata)
        assert media.key == "path/to/file.jpg"
        assert media.creator_uid == "user_123"
        assert media.experience_id == "exp_456"
