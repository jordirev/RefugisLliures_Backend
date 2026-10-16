# Integració — Cloudflare R2 (S3-compatible)

> **[FET]** comprovat al codi · **[INFERÈNCIA]** deducció · **[NO VERIFICAT]** depèn de config externa.

Emmagatzema fotos/vídeos de refugis i avatars d'usuari. Bucket **privat**: l'accés de lectura és via URLs GET presignades (1 h) i la pujada nova via URLs **PUT** presignades (10 min) a `quarantine/`.

## Fitxers
| Fitxer | Rol |
|---|---|
| `api/r2_config.py` | `get_r2_client()` (boto3 `s3`, `region_name='auto'`, `signature_version='s3v4'`, `addressing_style='path'`), `get_r2_bucket_name()`, `get_r2_endpoint()` |
| `api/services/r2_media_service.py` | `R2MediaService` + estratègies de path + `quarantine_key()` / `moderation_hold_key()` |
| `api/services/image_processing_service.py` | Processament autoritatiu abans de publicar (vegeu [flux 3](../flows/03-refuge-media-upload.md)) |
| `api/models/media_metadata.py` | `MediaMetadata` / `RefugeMediaMetadata` = forma **MediaItem** del contracte |

## Configuració
Variables (només noms), llegides amb `os.getenv` dins `get_r2_client()`: `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_ENDPOINT`, `R2_BUCKET_NAME`. Si en falta alguna → `ValueError("R2 configuration is incomplete...")`.

On es defineixen **[FET]**:
- GitHub Actions: secrets a `.github/workflows/process-visits.yml`.
- Tests: valors falsos a `conftest.py` i `api/tests/conftest.py`.
- `run_process_visits.sh` / `run_process_visits.bat`: placeholders.
- A Render: **[NO VERIFICAT]** (s'han de configurar al dashboard).

### Configuració del bucket (manual, al dashboard de Cloudflare) **[NO VERIFICAT]**
1. **CORS** (necessari perquè l'app pugi directament amb PUT i per a l'app web, si n'hi ha):
   ```json
   [
     {
       "AllowedOrigins": ["*"],
       "AllowedMethods": ["PUT", "GET", "HEAD"],
       "AllowedHeaders": ["Content-Type", "Content-Length"],
       "ExposeHeaders": ["ETag"],
       "MaxAgeSeconds": 3600
     }
   ]
   ```
   Les apps natives (React Native) no apliquen CORS, però Expo web i les eines de prova sí. Si es pot, restringeix `AllowedOrigins` als dominis reals.
2. **Lifecycle**: regla *Delete objects* amb prefix `quarantine/` i antiguitat **1 dia** (esborra pujades no confirmades o abandonades). **No** hi posis `moderation-hold/` (evidència retinguda per obligació legal).
3. El bucket ha de continuar **privat** (sense domini públic `r2.dev`). Domini propi + Worker: [guides/cloudflare-domain-csam.md](../guides/cloudflare-domain-csam.md).

Dev vs prod: el codi no distingeix buckets; depèn de `R2_BUCKET_NAME` a cada entorn **[FET]**.

## Estratègies de path
| Estratègia | Base path | Claus noves | Tipus (multipart antic, validació prèvia) |
|---|---|---|---|
| `RefugiMediaStrategy` | `refugis-lliures/{refuge_id}` | `{uuid}.webp` + `{uuid}_thumb.webp`; vídeo `{uuid}.mp4\|.mov\|.webm` + `{uuid}_thumb.webp` | image/jpeg, jpg, png, webp, heic, heif; video/mp4, quicktime, x-msvideo, webm |
| `UserAvatarStrategy` | `users-avatars/{uid}` | `{uuid}.webp` (512 px, sense miniatura) | només imatges |

La llista blanca **autoritativa** és la d'`image_processing_service` (imatges jpeg/png/webp/heic/heif ≤ 15 MB; vídeos mp4/quicktime/webm ≤ 50 MB), comprovada per magic bytes. AVI ja no s'accepta en publicar (el processament el rebutja amb `invalid_type`).

## API del servei
| Mètode | Comportament |
|---|---|
| `__init__(strategy)` | crea client boto3 **a cada instància** |
| `upload_file(file, entity_id, content_type, filename=None)` | valida MIME declarat, `put_object`; **la clau és sempre `uuid4()+ext`** (el `filename` s'ignora) |
| `generate_presigned_url(key, expiration=3600)` | GET presignat |
| `generate_presigned_put_url(key, content_type, content_length, expiration=600)` | PUT presignat amb `ContentType` i `ContentLength` signats (R2 rebutja un altre tipus o mida) |
| `build_media_key(entity_id, ext, suffix='', media_id=None)` | clau UUID dins del path de l'estratègia |
| `head_object(key)` / `get_object_bytes(key, max_bytes)` | `None` si no existeix (404/NoSuchKey); `max_bytes` llegeix com a molt `max_bytes+1` |
| `put_bytes(key, data, content_type)` | puja bytes processats amb `Cache-Control: private, max-age=31536000, immutable` |
| `copy_object(src, dst)` / `move_object(src, dst)` | retornen `bool` (no llancen) |
| `generate_media_metadata_from_dict` / `generate_media_metadata_list` | hidraten MediaItems (URL + `thumb_url` presignades; `thumb_url = url` si no hi ha `thumb_key`) |
| `delete_file(key)` | `delete_object`; **retorna False** en `ClientError` — els callers ho comproven |
| `delete_files(keys)` | `{deleted, failed}` |
| `list_files(entity_id)` | un sol `list_objects_v2` (màx. 1000 claus, sense paginació) |

## Fluxos que l'usen
[Fotos de refugi](../flows/03-refuge-media-upload.md) · [Avatar](../flows/02-user-avatar.md) · [Experiències](../flows/08-experiences.md) · [Moderació](../flows/12-media-moderation.md) · esborrat d'usuari i de refugi.

## Estructura del bucket
```
<bucket>/
├── refugis-lliures/{refuge_id}/{uuid}.webp|.mp4|.mov|.webm   publicat (+ {uuid}_thumb.webp)
│                               <nom original>                 items antics (abans de la feature)
├── users-avatars/{uid}/{uuid}.webp                            avatar actual
├── quarantine/{upload_id}                                     pujades directes pendents (lifecycle 1 dia)
└── moderation-hold/...                                        evidència retinguda (accés restringit, sense lifecycle)
```

## Gotchas
- `delete_file` no llança: comprova el booleà (els rollbacks del codi ja ho fan des de la feature *images*) **[FET]**.
- Cada hidratació de model (`Refugi.from_dict`, `User.from_dict`, `Experience.from_dict`) presigna URLs, **també quan les dades venen de cache** → URL sempre fresca però canviant: el client ha d'usar la **clau** com a `cacheKey` **[FET]**.
- Una URL servida caduca en 1 h; la PUT en 10 min **[FET]**.
- Construir un controller que crea `R2MediaService` (p. ex. `RefugiLliureController`) **falla si falta config R2**, fins i tot per a operacions que no toquen R2 **[FET]**.
- La URL PUT signa `content-length`: el client ha d'enviar exactament la mida declarada a l'intent **[FET]**.

## Estendre el servei
- **Nou format**: afegeix-lo a la llista blanca i als magic bytes d'`image_processing_service` (i, si cal, a l'estratègia per al multipart antic).
- **Nou tipus de media**: nova subclasse de `MediaPathStrategy` i factory `get_<x>_service()`. Patró: [design/patterns.md §Strategy](../design/patterns.md#strategy).

## Guia de configuració
[guides/r2-render-setup.md](../guides/r2-render-setup.md) — variables a Render/GitHub/local, bucket privat, CORS, rotació de claus.
