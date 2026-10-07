# Integració — Cloudflare R2 (S3-compatible)

> **[FET]** comprovat al codi · **[INFERÈNCIA]** deducció · **[NO VERIFICAT]** depèn de config externa.

Emmagatzema fotos/vídeos de refugis i avatars d'usuari. Bucket **privat**: l'accés és via URLs presignades.

## Fitxers
| Fitxer | Rol |
|---|---|
| `api/r2_config.py` | `get_r2_client()` (boto3 `s3`, `region_name='auto'`, `signature_version='s3v4'`, `addressing_style='path'`), `get_r2_bucket_name()`, `get_r2_endpoint()` |
| `api/services/r2_media_service.py` | `R2MediaService` + estratègies de path |
| `api/models/media_metadata.py` | `MediaMetadata(key, url, uploaded_at)`, `RefugeMediaMetadata(+creator_uid, experience_id)` |

## Configuració
Variables (només noms), llegides amb `os.getenv` dins `get_r2_client()` (`api/r2_config.py:12-15`): `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_ENDPOINT`, `R2_BUCKET_NAME`. Si en falta alguna → `ValueError("R2 configuration is incomplete...")` (L17-18).

On es defineixen **[FET]**:
- No apareixen a `env/.env.development`, `env/.env.production` ni `env/api-keys.env` (comprovat per noms de clau).
- GitHub Actions: secrets a `.github/workflows/process-visits.yml:29-32`.
- Tests: valors falsos a `conftest.py` i `api/tests/conftest.py`.
- `run_process_visits.sh` / `run_process_visits.bat`: placeholders.
- A Render: **[NO VERIFICAT]** (s'han de configurar al dashboard).

Dev vs prod: el codi no distingeix buckets; depèn del valor de `R2_BUCKET_NAME` a cada entorn **[FET]**.

## Estratègies de path (`api/services/r2_media_service.py`)
| Estratègia | Base path | Tipus permesos | Línies |
|---|---|---|---|
| `RefugiMediaStrategy` | `refugis-lliures/{refuge_id}` | image/jpeg, jpg, png, webp, heic, heif; video/mp4, quicktime, x-msvideo, webm | L44-98 |
| `UserAvatarStrategy` | `users-avatars/{uid}` | només imatges | L101-145 |

Factories: `get_refugi_media_service()` (L462), `get_user_avatar_service()` (L467).

## API del servei
| Mètode | Comportament | Línies |
|---|---|---|
| `__init__(strategy)` | crea client boto3 **a cada instància** | L154-164 |
| `upload_file(file, entity_id, content_type, filename=None)` | valida MIME declarat; si `filename` és buit genera `uuid4()+ext`; `put_object`; retorna `{key, url presignada}`; `ClientError` → `Exception` | L166-226 |
| `generate_presigned_url(key, expiration=3600)` | `get_object` presignat | L228-251 |
| `generate_presigned_urls`, `generate_media_metadata_from_dict`, `generate_media_metadata_list` | helpers per hidratar models | L253-320 |
| `delete_file(key)` | `delete_object`; **retorna False** en `ClientError` | L322-341 |
| `delete_files(keys)` | itera `delete_file`, retorna `{deleted, failed}` | L343-365 |
| `list_files(entity_id)` | un sol `list_objects_v2` (màx. 1000 claus, sense paginació) | L367-391 |
| `delete_all_files(entity_id)` | sense ús | L393-404 |

## Fluxos que l'usen
[Fotos de refugi](../flows/03-refuge-media-upload.md) · [Avatar](../flows/02-user-avatar.md) · [Experiències](../flows/08-experiences.md) · esborrat d'usuari i de refugi.

## Gotchas
- Tots els callers passen `filename=file.name` → claus amb el nom original i col·lisions **[FET]**.
- `delete_file` no llança → els rollbacks basats en `try/except` no funcionen **[FET]**.
- Cada hidratació de model (`Refugi.from_dict`, `User.from_dict`, `Experience.from_dict`) presigna URLs, **també quan les dades venen de cache** → la URL sempre és fresca però hi ha cost de CPU per petició **[FET]**.
- Una URL servida caduca en 1 h: el client no l'ha de desar a llarg termini **[INFERÈNCIA]**.
- Sense límit de mida i sense comprovar magic bytes **[FET]**.
- Construir un controller que crea `R2MediaService` (p. ex. `RefugiLliureController`) **falla si falta config R2**, fins i tot per a operacions que no toquen R2 (health check) **[FET]**.

## Estendre el servei
- **Nou format** a una estratègia existent: afegeix el MIME a la llista de tipus permesos de `RefugiMediaStrategy`/`UserAvatarStrategy`.
- **Nou tipus de media** (p. ex. documents): nova subclasse de `MediaPathStrategy` amb `get_base_path`, `get_allowed_content_types`, `validate_file`, `generate_media_metadata_from_dict`, i una factory `get_<x>_service()` → `R2MediaService(<X>Strategy())`. Patró: [design/patterns.md §Strategy](../design/patterns.md#strategy).

Estructura del bucket:
```
<bucket>/
├── refugis-lliures/{refuge_id}/<fitxer>   imatges i vídeos
└── users-avatars/{uid}/<fitxer>           només imatges
```

## Guia de configuració
[guides/r2-render-setup.md](../guides/r2-render-setup.md) — variables a Render/GitHub/local, bucket privat, CORS, rotació de claus.
