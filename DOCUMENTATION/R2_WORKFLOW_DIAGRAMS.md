# Flux de Treball del Servei R2 Media

## Arquitectura General

```
┌─────────────────┐
│   Frontend      │
│   (Client)      │
└────────┬────────┘
         │
         │ HTTP Request
         ▼
┌─────────────────────────────────────────┐
│         Django Backend                  │
│                                         │
│  ┌──────────────────────────────────┐  │
│  │   refugi_media_views.py         │  │
│  │   (API Endpoints)               │  │
│  └──────────┬───────────────────────┘  │
│             │                           │
│             ▼                           │
│  ┌──────────────────────────────────┐  │
│  │   r2_media_service.py           │  │
│  │   (Business Logic)              │  │
│  │   ┌──────────────────────────┐  │  │
│  │   │ MediaPathStrategy        │  │  │
│  │   │  ├─ RefugiMediaStrategy  │  │  │
│  │   │  └─ UserAvatarStrategy   │  │  │
│  │   └──────────────────────────┘  │  │
│  └──────────┬───────────────────────┘  │
│             │                           │
└─────────────┼───────────────────────────┘
              │
      ┌───────┴────────┐
      │                │
      ▼                ▼
┌─────────────┐  ┌──────────────┐
│ Cloudflare  │  │  Firestore   │
│     R2      │  │  (metadata)  │
│  (storage)  │  │              │
└─────────────┘  └──────────────┘
```

## Flux d'Upload de Mitjans

```
┌────────┐
│ Client │
└───┬────┘
    │
    │ POST /api/refuges/{id}/media/
    │ files: [image1.jpg, video1.mp4]
    │ Authorization: Bearer <token>
    ▼
┌────────────────────────┐
│ RefugiMediaAPIView     │
│ 1. Validate auth       │
│ 2. Check permissions   │
└───────┬────────────────┘
        │
        │ For each file:
        ▼
┌────────────────────────────┐
│ R2MediaService             │
│ 1. Validate content type   │
│ 2. Generate filename (UUID)│
│ 3. Build path:             │
│    refugis-lliures/{id}/   │
└───────┬────────────────────┘
        │
        │ boto3 PUT request
        │ + AWS Signature v4
        ▼
┌─────────────────────┐
│ Cloudflare R2       │
│ Store file          │
└───────┬─────────────┘
        │
        │ Success
        ▼
┌────────────────────────────┐
│ Generate Presigned URL     │
│ Expiration: 1 hour         │
└───────┬────────────────────┘
        │
        │ Return {key, url}
        ▼
┌────────────────────────────┐
│ Update Firestore           │
│ refugis/{id}               │
│   media_keys += [new_keys] │
└───────┬────────────────────┘
        │
        │ Response
        ▼
┌────────┐
│ Client │
│ Receive URLs               │
└────────┘
```

## Flux de Consulta de Refugi (GET)

```
┌────────┐
│ Client │
└───┬────┘
    │
    │ GET /api/refuges/{id}/
    ▼
┌──────────────────────────┐
│ RefugiLliureDetailAPIView│
└───────┬──────────────────┘
        │
        ▼
┌─────────────────────────────┐
│ RefugiLliureController      │
│ 1. Get refugi from DAO      │
└───────┬─────────────────────┘
        │
        │ Query document
        ▼
┌──────────────────────┐
│ Firestore            │
│ Returns:             │
│  - id, name, ...     │
│  - media_keys: [     │
│      "refugis-       │
│       lliures/123/   │
│       image1.jpg"    │
│    ]                 │
└───────┬──────────────┘
        │
        │ For each media_key:
        ▼
┌────────────────────────────┐
│ R2MediaService             │
│ generate_presigned_urls()  │
│                            │
│ For each key:              │
│   boto3.generate_presigned │
│   _url('get_object')       │
└───────┬────────────────────┘
        │
        │ URLs with signatures
        ▼
┌─────────────────────────────┐
│ Refugi Model                │
│  - id: "123"                │
│  - name: "Colomers"         │
│  - media_keys: [keys]       │
│  - images_urls: [           │
│      "https://r2.../image1  │
│       ?signature=..."       │
│    ]                        │
└───────┬─────────────────────┘
        │
        │ Serialize
        ▼
┌────────┐
│ Client │
│ Display images from URLs   │
└────────┘
```

## Flux d'Eliminació de Mitjans

```
┌────────┐
│ Client │
└───┬────┘
    │
    │ DELETE /api/refuges/{id}/media/delete/
    │ body: { urls: [presigned_urls] }
    │ Authorization: Bearer <token>
    ▼
┌────────────────────────────┐
│ RefugiMediaDeleteAPIView   │
│ 1. Validate auth (admin)   │
└───────┬────────────────────┘
        │
        │ For each URL:
        ▼
┌────────────────────────────┐
│ R2MediaService             │
│ 1. Extract key from URL    │
│    Parse presigned URL     │
│    Extract path component  │
└───────┬────────────────────┘
        │
        │ boto3 DELETE request
        │ + AWS Signature v4
        ▼
┌─────────────────────┐
│ Cloudflare R2       │
│ Delete file         │
└───────┬─────────────┘
        │
        │ Success
        ▼
┌────────────────────────────┐
│ Update Firestore           │
│ refugis/{id}               │
│   media_keys -= [deleted]  │
└───────┬────────────────────┘
        │
        │ Response
        ▼
┌────────┐
│ Client │
│ {deleted: [...],           │
│  failed: []}               │
└────────┘
```

## Estratègies de Path

```
┌─────────────────────────┐
│  MediaPathStrategy      │
│  (Abstract)             │
│                         │
│  + get_base_path()      │
│  + get_allowed_types()  │
│  + validate_file()      │
└────────┬────────────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌───────────────┐  ┌──────────────────┐
│RefugiMedia    │  │UserAvatar        │
│Strategy       │  │Strategy          │
│               │  │                  │
│Path:          │  │Path:             │
│refugis-lliures│  │users-avatars/{uid│
│/{id}/         │  │}/                │
│               │  │                  │
│Allowed:       │  │Allowed:          │
│- Images       │  │- Images only     │
│- Videos       │  │                  │
└───────────────┘  └──────────────────┘
```

## Cicle de Vida d'una URL Prefirmada

```
Time: 0s
┌────────────────────────────────────┐
│ URL generada amb signature         │
│ Expiration: 3600s (1 hora)         │
│                                    │
│ https://r2.cloudflare.com/bucket/  │
│ key?X-Amz-Signature=...            │
│ &X-Amz-Expires=3600                │
└────────────────────────────────────┘
         │
         │ Client pot accedir
         ▼
Time: 0s - 3600s
┌────────────────────────────────────┐
│ ✅ URL vàlida                      │
│ Client pot:                        │
│  - Descarregar fitxer              │
│  - Mostrar en <img>                │
│  - Reproduir en <video>            │
└────────────────────────────────────┘
         │
         ▼
Time: 3601s
┌────────────────────────────────────┐
│ ❌ URL expirada                    │
│ Error: 403 Forbidden               │
│                                    │
│ Solució:                           │
│ - Tornar a fer GET refugi          │
│ - Nova URL generada automàticament │
└────────────────────────────────────┘
```

## Diagrama de Components

```
┌──────────────────────────────────────────────────┐
│                    API Layer                     │
│                                                  │
│  ┌────────────────────┐  ┌───────────────────┐  │
│  │RefugiMediaAPIView  │  │RefugiMediaDelete  │  │
│  │                    │  │APIView            │  │
│  │POST /media/        │  │DELETE /media/     │  │
│  └─────────┬──────────┘  └──────┬────────────┘  │
└────────────┼────────────────────┼───────────────┘
             │                    │
             ▼                    ▼
┌──────────────────────────────────────────────────┐
│                 Service Layer                    │
│                                                  │
│  ┌──────────────────────────────────────────┐   │
│  │         R2MediaService                   │   │
│  │                                          │   │
│  │  + upload_file()                         │   │
│  │  + generate_presigned_url()              │   │
│  │  + generate_presigned_urls()             │   │
│  │  + delete_file()                         │   │
│  │  + delete_files()                        │   │
│  │  + delete_files_by_presigned_urls()      │   │
│  │  + list_files()                          │   │
│  │  + delete_all_files()                    │   │
│  └──────────────────────────────────────────┘   │
└──────────────┬───────────────────────────────────┘
               │
        ┌──────┴────────┐
        │               │
        ▼               ▼
┌───────────────┐  ┌──────────────┐
│  boto3 S3     │  │  Firestore   │
│  Client       │  │  Service     │
│               │  │              │
│ AWS Signature │  │  Update      │
│ v4            │  │  media_keys  │
└───────┬───────┘  └──────┬───────┘
        │                 │
        ▼                 ▼
┌───────────────┐  ┌──────────────┐
│ Cloudflare R2 │  │  Firestore   │
│               │  │  Database    │
└───────────────┘  └──────────────┘
```

## Flux de Dades

### Upload
```
File Upload
    │
    ├─► Validation (content type, size)
    │
    ├─► Generate unique filename (UUID)
    │
    ├─► Upload to R2 (boto3)
    │   └─► Path: strategy.get_base_path(entity_id)/filename
    │
    ├─► Generate presigned URL
    │
    ├─► Update Firestore
    │   └─► Add key to media_keys array
    │
    └─► Return {key, url} to client
```

### Retrieve
```
GET Refugi
    │
    ├─► Query Firestore
    │   └─► Get document with media_keys
    │
    ├─► For each media_key:
    │   └─► Generate presigned URL (boto3)
    │
    ├─► Add images_urls to refugi model
    │
    └─► Return refugi with presigned URLs
```

### Delete
```
Delete Media
    │
    ├─► Extract keys from presigned URLs
    │
    ├─► For each key:
    │   └─► Delete from R2 (boto3)
    │
    ├─► Update Firestore
    │   └─► Remove keys from media_keys array
    │
    └─► Return {deleted, failed}
```

## Gestió d'Errors

```
┌─────────────────────┐
│ Client Request      │
└──────────┬──────────┘
           │
           ▼
    ┌──────────────┐
    │ Try Upload   │
    └──────┬───────┘
           │
    ┌──────┴──────────────────────┐
    │                             │
    ▼                             ▼
┌─────────────┐           ┌──────────────┐
│ Validation  │           │ Upload to R2 │
│ Error       │           └──────┬───────┘
│             │                  │
│ Return 400  │           ┌──────┴────────────┐
│ {error: ... │           │                   │
└─────────────┘           ▼                   ▼
                  ┌───────────────┐   ┌────────────────┐
                  │ Success       │   │ R2 Error       │
                  └───────┬───────┘   │                │
                          │           │ Log error      │
                          │           │ Return 500     │
                          │           └────────────────┘
                          ▼
                  ┌────────────────┐
                  │ Try Update     │
                  │ Firestore      │
                  └───────┬────────┘
                          │
                  ┌───────┴────────────┐
                  │                    │
                  ▼                    ▼
          ┌──────────────┐    ┌─────────────────┐
          │ Success      │    │ Firestore Error │
          │              │    │                 │
          │ Return 200   │    │ Log warning     │
          │ {uploaded:[]}│    │ Still return    │
          └──────────────┘    │ 200 (file       │
                              │ uploaded)       │
                              └─────────────────┘
```

## Seguretat en Cada Capa

```
┌─────────────────────────────────────────┐
│ Client Layer                            │
│ - HTTPS only                            │
│ - Firebase Auth token required          │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│ API Layer                               │
│ - Token validation (Firebase)           │
│ - Permission checks (IsAdminUser)       │
│ - Content type validation               │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│ Service Layer                           │
│ - File type validation                  │
│ - Size limits (Django settings)         │
│ - Path sanitization                     │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│ Storage Layer                           │
│ - AWS Signature v4                      │
│ - Presigned URLs (time-limited)         │
│ - Private bucket (no public access)     │
└─────────────────────────────────────────┘
```
