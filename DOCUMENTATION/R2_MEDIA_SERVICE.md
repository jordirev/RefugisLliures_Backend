# R2 Media Service - Cloudflare R2 Integration

## Visió General

Aquest servei gestiona la pujada, obtenció i eliminació de mitjans (imatges i vídeos) al bucket R2 de Cloudflare. Utilitza el patró de disseny **Strategy** per proporcionar una solució reutilitzable i mantenible per a diferents tipus de mitjans.

## Arquitectura

### Patró Strategy

El servei implementa el patró Strategy per gestionar diferents tipus de mitjans:

```
MediaPathStrategy (Abstract)
├── RefugiMediaStrategy (Imatges i vídeos de refugis)
└── UserAvatarStrategy (Avatars d'usuaris - només imatges)
```

### Estructura de Carpetes a R2

```
refugis-lliures-media/
├── refugis-lliures/
│   ├── {refuge_id}/
│   │   ├── image1.jpg
│   │   ├── image2.png
│   │   └── video1.mp4
│   └── ...
└── users-avatars/
    ├── {uid}/
    │   └── avatar.jpg
    └── ...
```

## Configuració

### Variables d'Entorn

Les següents variables han de ser configurades tant a Render com als fitxers `.env`:

```env
# R2 configuration
R2_ACCESS_KEY_ID=your_access_key_id
R2_SECRET_ACCESS_KEY=your_secret_access_key
R2_ENDPOINT=https://e0c55e2f7b13e7548afed9db64268f83.r2.cloudflarestorage.com
R2_BUCKET_NAME=refugis-lliures-media
```

**Render Environment Variables:**
Afegeix aquestes mateixes variables a la secció "Environment" del teu servei a Render.

### Fitxers Modificats

1. **`api/r2_config.py`** - Configuració del client boto3 per R2
2. **`api/services/r2_media_service.py`** - Servei principal amb patró Strategy
3. **`api/views/refugi_media_views.py`** - Endpoints REST per gestió de mitjans
4. **`api/urls.py`** - Rutes dels nous endpoints
5. **`api/models/refugi_lliure.py`** - Afegits camps `media_keys` i `images_urls`
6. **`api/serializers/refugi_lliure_serializer.py`** - Serialitzadors actualitzats
7. **`api/controllers/refugi_lliure_controller.py`** - Integració amb URLs prefirmades

## Ús del Servei

### Instanciar el Servei

```python
from api.services.r2_media_service import get_refugi_media_service, get_user_avatar_service

# Per a mitjans de refugis (imatges i vídeos)
media_service = get_refugi_media_service()

# Per a avatars d'usuaris (només imatges)
avatar_service = get_user_avatar_service()
```

### Pujar Fitxers

```python
# Pujar una imatge
with open('photo.jpg', 'rb') as file:
    result = media_service.upload_file(
        file_content=file,
        entity_id='refuge123',
        content_type='image/jpeg',
        filename='photo.jpg'  # Opcional
    )
    
print(result['key'])  # refugis-lliures/refuge123/uuid.jpg
print(result['url'])  # URL prefirmada
```

### Generar URLs Prefirmades

```python
# Per a un sol fitxer
url = media_service.generate_presigned_url('refugis-lliures/refuge123/image.jpg', expiration=3600)

# Per a múltiples fitxers
keys = ['refugis-lliures/refuge123/image1.jpg', 'refugis-lliures/refuge123/image2.jpg']
urls = media_service.generate_presigned_urls(keys, expiration=3600)
```

### Eliminar Fitxers

```python
# Eliminar per key
media_service.delete_file('refugis-lliures/refuge123/image.jpg')

# Eliminar múltiples per keys
keys = ['refugis-lliures/refuge123/image1.jpg', 'refugis-lliures/refuge123/image2.jpg']
result = media_service.delete_files(keys)

# Eliminar per URLs prefirmades
urls = ['https://presigned-url1...', 'https://presigned-url2...']
result = media_service.delete_files_by_presigned_urls(urls)
```

### Llistar Fitxers

```python
# Llistar tots els fitxers d'un refugi
keys = media_service.list_files('refuge123')

# Eliminar tots els fitxers d'un refugi
result = media_service.delete_all_files('refuge123')
```

## Endpoints API

### 1. Pujar Mitjans
**POST** `/api/refuges/{id}/media/`

**Headers:**
- `Authorization: Bearer <firebase-token>`
- `Content-Type: multipart/form-data`

**Body:**
```
files: [File, File, ...]
```

**Response:**
```json
{
  "uploaded": [
    {
      "filename": "photo1.jpg",
      "key": "refugis-lliures/refuge123/uuid.jpg",
      "url": "https://presigned-url..."
    }
  ],
  "failed": []
}
```

**Permisos:** Requereix autenticació i rol d'administrador

### 2. Llistar Mitjans
**GET** `/api/refuges/{id}/media/list/`

**Query Parameters:**
- `expiration` (opcional): Temps d'expiració en segons (defecte: 3600)

**Response:**
```json
{
  "media": [
    {
      "key": "refugis-lliures/refuge123/image.jpg",
      "url": "https://presigned-url..."
    }
  ]
}
```

**Permisos:** Requereix autenticació

### 3. Eliminar Mitjans
**DELETE** `/api/refuges/{id}/media/delete/`

**Headers:**
- `Authorization: Bearer <firebase-token>`
- `Content-Type: application/json`

**Body:**
```json
{
  "urls": [
    "https://presigned-url1...",
    "https://presigned-url2..."
  ]
}
```

**Response:**
```json
{
  "deleted": ["https://presigned-url1..."],
  "failed": []
}
```

**Permisos:** Requereix autenticació i rol d'administrador

### 4. Obtenir Refugi amb Mitjans
**GET** `/api/refuges/{id}/`

Ara inclou automàticament el camp `images_urls` amb URLs prefirmades:

```json
{
  "id": "refuge123",
  "name": "Refugi Colomers",
  "images_urls": [
    "https://presigned-url1...",
    "https://presigned-url2..."
  ],
  ...
}
```

## Formats de Fitxer Suportats

### Imatges (Refugis i Avatars)
- JPEG / JPG (`image/jpeg`, `image/jpg`)
- PNG (`image/png`)
- WebP (`image/webp`)
- HEIC (`image/heic`)
- HEIF (`image/heif`)

### Vídeos (Només Refugis)
- MP4 (`video/mp4`)
- MOV (`video/quicktime`)
- AVI (`video/x-msvideo`)
- WebM (`video/webm`)

## Integració amb Firestore

El servei integra automàticament amb Firestore:

1. **En pujar mitjans**: Afegeix els `media_keys` al document del refugi
2. **En eliminar mitjans**: Elimina els `media_keys` del document del refugi
3. **En obtenir refugi**: Genera URLs prefirmades a partir dels `media_keys`

### Estructura del Document Firestore

```json
{
  "id": "refuge123",
  "name": "Refugi Colomers",
  "media_keys": [
    "refugis-lliures/refuge123/image1.jpg",
    "refugis-lliures/refuge123/video1.mp4"
  ],
  ...
}
```

**Nota:** El camp `images_urls` NO es guarda a Firestore, es genera dinàmicament quan es consulta.

## Seguretat

### AWS Signature v4
Totes les peticions al bucket R2 utilitzen AWS Signature v4 per autenticació.

### URLs Prefirmades
Les URLs generades són temporals i expiren per defecte en 1 hora (configurable).

### Permisos
- **Upload/Delete**: Només usuaris administradors
- **List/View**: Qualsevol usuari autenticat
- **GET refugi**: Públic (amb URLs prefirmades)

## Gestió d'Errors

El servei gestiona els següents errors:

1. **Content type no vàlid**: Retorna error amb tipus permesos
2. **Fitxer no trobat**: Logging i skip
3. **Error de connexió R2**: Exception amb detalls
4. **Error Firestore**: Logging (no afecta la resposta de R2)

## Testing

### Exemple amb curl

```bash
# Upload
curl -X POST "http://localhost:8000/api/refuges/refuge123/media/" \
  -H "Authorization: Bearer <token>" \
  -F "files=@photo1.jpg" \
  -F "files=@video1.mp4"

# List
curl "http://localhost:8000/api/refuges/refuge123/media/list/" \
  -H "Authorization: Bearer <token>"

# Delete
curl -X DELETE "http://localhost:8000/api/refuges/refuge123/media/delete/" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"urls": ["https://presigned-url..."]}'
```

## Consideracions de Performance

1. **Cache**: Les URLs prefirmades expiren, no es guarden en cache
2. **Batch Operations**: Suporta múltiples fitxers en una sola petició
3. **Lazy Loading**: URLs només es generen quan es consulta el refugi
4. **Parallel Uploads**: Els clients poden pujar múltiples fitxers en paral·lel

## Manteniment

### Afegir Nous Formats

Per afegir nous formats de fitxer, modifica la estratègia corresponent:

```python
class RefugiMediaStrategy(MediaPathStrategy):
    ALLOWED_IMAGE_TYPES = [
        'image/jpeg',
        # Afegeix nous tipus aquí
    ]
```

### Afegir Nova Estratègia

Per afegir un nou tipus de mitjà (ex: documents):

```python
class DocumentStrategy(MediaPathStrategy):
    def get_base_path(self, entity_id: str) -> str:
        return f"documents/{entity_id}"
    
    def get_allowed_content_types(self) -> List[str]:
        return ['application/pdf', 'application/msword']
    
    def validate_file(self, content_type: str) -> bool:
        return content_type in self.get_allowed_content_types()

# Factory function
def get_document_service() -> R2MediaService:
    return R2MediaService(DocumentStrategy())
```

## Troubleshooting

### Error: "R2 configuration is incomplete"
Verifica que totes les variables d'entorn estiguin configurades correctament.

### Error: "Content type not allowed"
Comprova que el fitxer tingui un dels formats suportats.

### URLs prefirmades no funcionen
Les URLs expiren. Torna a generar-les si ha passat el temps d'expiració.

### Fitxers no s'actualitzen a Firestore
Comprova els logs per errors de Firestore. Els fitxers es pugen igualment a R2.

## Referències

- [Cloudflare R2 Documentation](https://developers.cloudflare.com/r2/)
- [Boto3 S3 Client](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html)
- [AWS Signature v4](https://docs.aws.amazon.com/general/latest/gr/signature-version-4.html)
