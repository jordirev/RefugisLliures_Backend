# Actualització: Metadades de Mitjans amb creator_uid i uploaded_at

## Resum dels Canvis

S'ha implementat un sistema complet de metadades per als mitjans (imatges i vídeos) que ara inclou informació sobre qui va pujar cada fitxer i quan.

## Canvis Implementats

### 1. **Nova Classe MediaMetadata**

**Fitxer creat:** `api/models/media_metadata.py`

Classe per representar les metadades d'un mitjà:

```python
@dataclass
class MediaMetadata:
    key: str              # Path al bucket R2
    url: str              # URL prefirmada
    creator_uid: str      # UID de l'usuari que va pujar el mitjà
    uploaded_at: str      # Data ISO 8601: "2024-12-08T10:30:00Z"
```

### 2. **Model Refugi Actualitzat**

**Fitxer modificat:** `api/models/refugi_lliure.py`

**Abans:**
```python
media_keys: List[str]           # Només keys
images_urls: List[str]          # Només URLs
```

**Després:**
```python
media_metadata: List[Dict[str, str]]      # Metadades guardades a Firestore
images_metadata: List[MediaMetadata]      # Metadades amb URLs (generades dinàmicament)
```

### 3. **Serializer Actualitzat**

**Fitxer modificat:** `api/serializers/refugi_lliure_serializer.py`

**Afegit:**
```python
class MediaMetadataSerializer(serializers.Serializer):
    key = serializers.CharField()
    url = serializers.URLField()
    creator_uid = serializers.CharField()
    uploaded_at = serializers.CharField()

class RefugiSerializer(serializers.Serializer):
    # ...
    media_metadata = serializers.ListField(child=serializers.DictField())
    images_metadata = MediaMetadataSerializer(many=True)
```

### 4. **Servei R2 Ampliat**

**Fitxer modificat:** `api/services/r2_media_service.py`

**Nous mètodes:**
```python
def generate_media_metadata_from_dict(metadata_dict, expiration=3600) -> MediaMetadata
    """Genera MediaMetadata amb URL prefirmada des d'un diccionari"""

def generate_media_metadata_list(metadata_list, expiration=3600) -> List[MediaMetadata]
    """Genera llista de MediaMetadata amb URLs prefirmades"""
```

### 5. **Controller Actualitzat**

**Fitxer modificat:** `api/controllers/refugi_lliure_controller.py`

**Abans:**
```python
refugi.images_urls = self.media_service.generate_presigned_urls(refugi.media_keys)
```

**Després:**
```python
refugi.images_metadata = self.media_service.generate_media_metadata_list(refugi.media_metadata)
```

Ara genera objectes `MediaMetadata` complets en comptes de només URLs.

### 6. **Views Actualitzades**

**Fitxer modificat:** `api/views/refugi_media_views.py`

#### POST /api/refuges/{id}/media/

**Abans:**
- Només pujava fitxers i guardava keys

**Després:**
- Captura `creator_uid` de l'usuari autenticat
- Genera `uploaded_at` amb timestamp ISO 8601
- Guarda metadades completes a Firestore

```python
media_metadata = {
    'key': result['key'],
    'creator_uid': creator_uid,
    'uploaded_at': uploaded_at  # "2024-12-08T10:30:00Z"
}
```

**Resposta:**
```json
{
  "uploaded": [
    {
      "filename": "photo1.jpg",
      "key": "refugis-lliures/refuge123/uuid.jpg",
      "url": "https://presigned-url...",
      "creator_uid": "user123",
      "uploaded_at": "2024-12-08T10:30:00Z"
    }
  ],
  "failed": []
}
```

#### GET /api/refuges/{id}/media/

**Abans:**
- Llistava fitxers de R2 i generava URLs

**Després:**
- Obté `media_metadata` de Firestore
- Genera URLs prefirmades per cada mitjà
- Retorna metadades completes

**Resposta:**
```json
{
  "media": [
    {
      "key": "refugis-lliures/refuge123/photo1.jpg",
      "url": "https://presigned-url...",
      "creator_uid": "user123",
      "uploaded_at": "2024-12-08T10:30:00Z"
    }
  ]
}
```

#### DELETE /api/refuges/{id}/media/delete/

**Abans:**
- Eliminava fitxers i actualitzava `media_keys`

**Després:**
- Elimina fitxers i actualitza `media_metadata`
- Filtra les metadades per key eliminat

### 7. **GET /api/refuges/{id}/**

**Abans:**
```json
{
  "id": "refuge123",
  "name": "Refugi Colomers",
  "images_urls": [
    "https://presigned-url1...",
    "https://presigned-url2..."
  ]
}
```

**Després:**
```json
{
  "id": "refuge123",
  "name": "Refugi Colomers",
  "images_metadata": [
    {
      "key": "refugis-lliures/refuge123/photo1.jpg",
      "url": "https://presigned-url...",
      "creator_uid": "user123",
      "uploaded_at": "2024-12-08T10:30:00Z"
    }
  ]
}
```

## Estructura a Firestore

### Abans:
```json
{
  "id": "refuge123",
  "name": "Refugi Colomers",
  "media_keys": [
    "refugis-lliures/refuge123/photo1.jpg",
    "refugis-lliures/refuge123/video1.mp4"
  ]
}
```

### Després:
```json
{
  "id": "refuge123",
  "name": "Refugi Colomers",
  "media_metadata": [
    {
      "key": "refugis-lliures/refuge123/photo1.jpg",
      "creator_uid": "user123",
      "uploaded_at": "2024-12-08T10:30:00Z"
    },
    {
      "key": "refugis-lliures/refuge123/video1.mp4",
      "creator_uid": "user456",
      "uploaded_at": "2024-12-08T14:20:00Z"
    }
  ]
}
```

## Flux de Dades

### Upload:
```
1. Client puja fitxer → POST /api/refuges/{id}/media/
2. Backend captura creator_uid del token Firebase
3. Backend genera uploaded_at (timestamp UTC)
4. Backend puja fitxer a R2
5. Backend guarda metadata a Firestore:
   {key, creator_uid, uploaded_at}
6. Backend retorna resposta amb totes les metadades
```

### Retrieve:
```
1. Client demana refugi → GET /api/refuges/{id}/
2. Backend llegeix media_metadata de Firestore
3. Backend genera URLs prefirmades per cada key
4. Backend construeix MediaMetadata objects
5. Backend retorna refugi amb images_metadata completes
```

### Delete:
```
1. Client envia URLs a eliminar → DELETE /api/refuges/{id}/media/delete/
2. Backend extreu keys de les URLs
3. Backend elimina fitxers de R2
4. Backend filtra media_metadata per keys eliminats
5. Backend actualitza Firestore amb metadata filtrada
```

## Migració de Dades Existents

Si ja tens refugis amb `media_keys` antigues, caldrà migrar-les a `media_metadata`:

```python
# Script de migració (exemple)
for refugi in refugis:
    if 'media_keys' in refugi and 'media_metadata' not in refugi:
        media_metadata = []
        for key in refugi['media_keys']:
            media_metadata.append({
                'key': key,
                'creator_uid': 'unknown',  # O deixar buit
                'uploaded_at': '2024-01-01T00:00:00Z'  # Data per defecte
            })
        refugi['media_metadata'] = media_metadata
        del refugi['media_keys']
        # Actualitzar Firestore
```

## Beneficis

✅ **Traçabilitat**: Saps qui va pujar cada fitxer  
✅ **Auditoria**: Pots veure quan es van pujar els mitjans  
✅ **Gestió**: Pots filtrar/ordenar per data o usuari  
✅ **Seguretat**: Pots implementar permisos basats en creator_uid  
✅ **UI/UX**: Pots mostrar informació útil a l'usuari  

## Exemples d'Ús al Frontend

### Mostrar qui va pujar la foto:
```jsx
<img src={media.url} alt="Refugi" />
<p>Pujada per: {media.creator_uid}</p>
<p>Data: {new Date(media.uploaded_at).toLocaleDateString()}</p>
```

### Filtrar fotos per usuari:
```javascript
const myPhotos = refugi.images_metadata.filter(
  m => m.creator_uid === currentUser.uid
);
```

### Ordenar per data:
```javascript
const sortedMedia = refugi.images_metadata.sort(
  (a, b) => new Date(b.uploaded_at) - new Date(a.uploaded_at)
);
```

## Testing

### Provar Upload:
```bash
curl -X POST "http://localhost:8000/api/refuges/refuge123/media/" \
  -H "Authorization: Bearer <firebase-token>" \
  -F "files=@photo.jpg"
```

**Resposta esperada:**
```json
{
  "uploaded": [{
    "filename": "photo.jpg",
    "key": "refugis-lliures/refuge123/uuid.jpg",
    "url": "https://...",
    "creator_uid": "user123",
    "uploaded_at": "2024-12-08T15:30:00Z"
  }],
  "failed": []
}
```

### Provar GET:
```bash
curl "http://localhost:8000/api/refuges/refuge123/" \
  -H "Authorization: Bearer <firebase-token>"
```

**Resposta esperada:**
```json
{
  "id": "refuge123",
  "name": "Refugi Colomers",
  "images_metadata": [
    {
      "key": "refugis-lliures/refuge123/photo1.jpg",
      "url": "https://...",
      "creator_uid": "user123",
      "uploaded_at": "2024-12-08T15:30:00Z"
    }
  ]
}
```

## Compatibilitat

- ✅ **Backwards compatible**: Els refugis sense `media_metadata` retornaran array buit
- ✅ **Forward compatible**: El sistema està preparat per afegir més metadades en el futur
- ⚠️ **Migració necessària**: Els refugis existents amb `media_keys` hauran de ser migrats

## Notes Importants

1. **creator_uid** es captura del token Firebase del request
2. **uploaded_at** es genera en format ISO 8601 UTC
3. Les **URLs** NO es guarden a Firestore (són temporals)
4. Les **metadades** sí es guarden a Firestore (són permanents)
5. Els camps `media_metadata` i `images_metadata` són diferents:
   - `media_metadata`: Diccionaris guardats a Firestore (sense URL)
   - `images_metadata`: Objectes MediaMetadata amb URL (generades dinàmicament)
