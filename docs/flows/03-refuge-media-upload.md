# Flux 3 — Pujar, llistar i esborrar fotos/vídeos d'un refugi

> **[FET]** comprovat al codi · **[INFERÈNCIA]** deducció · **[NO VERIFICAT]** depèn de config externa.

## Endpoints (`api/views/refugi_media_views.py`)
| Mètode | URL | Vista | Permisos | Body |
|---|---|---|---|---|
| GET | `/api/refuges/{id}/media/` | `RefugiMediaAPIView.get` (L69) | IsAuthenticated | — |
| POST | `/api/refuges/{id}/media/` | `.post` (L138) | IsAuthenticated | multipart, llista `files` |
| DELETE | `/api/refuges/{id}/media/{key}/` | `RefugiMediaDeleteAPIView.delete` (L225) | IsAuthenticated + IsMediaUploader | — (`key` és `path:` i pot contenir `/`) |

## Model de dades [FET]
- R2: clau `refugis-lliures/{refuge_id}/{filename}` (`RefugiMediaStrategy`, `api/services/r2_media_service.py:44-98`). Tipus permesos: jpeg/jpg/png/webp/heic/heif + mp4/quicktime/x-msvideo/webm.
- Firestore, dins el document del refugi: `data_refugis_lliures/{id}.media_metadata = { "<clau R2>": {creator_uid, uploaded_at, experience_id|None} }`.
- Usuari: `users/{uid}.uploaded_photos_keys: [claus]`.
- Experiència (si n'hi ha): `experiences/{id}.media_keys: [claus]`.
- La URL **no** es desa: es presigna en llegir (3600 s). Models: `MediaMetadata`, `RefugeMediaMetadata` (`api/models/media_metadata.py:9-78`).
- Dos noms, dues coses: `media_metadata` és el **map desat a Firestore** (sense URL); `images_metadata` és la **llista que retorna l'API** (`[{key, url, creator_uid, uploaded_at, experience_id}]`), generada en llegir. Versions antigues usaven `media_keys` / `images_urls` (obsolet).
- Configurar R2: [guides/r2-render-setup.md](../guides/r2-render-setup.md).

## Diagrama — pujar

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant V as RefugiMediaAPIView.post
    participant RC as RefugiLliureController
    participant RD as RefugiLliureDAO
    participant R2 as R2MediaService(RefugiMediaStrategy)
    participant UD as UserDAO
    participant F as Firestore
    participant K as CacheService

    C->>V: POST multipart files[] + Bearer
    V->>V: 400 si no hi ha files, 401 si no hi ha user_uid
    V->>RC: upload_refugi_media(id, files, uid)
    RC->>RD: refugi_exists(id) (cache-first)
    alt no existeix
        V-->>C: 404
    end
    loop per cada fitxer
        RC->>R2: upload_file(file, id, content_type, filename=file.name)
        alt ValueError (MIME) o error
            RC->>RC: afegeix a failed[]
        else ok
            R2-->>RC: {key, url}
        end
    end
    RC->>RD: add_media_metadata(id, {key: {creator_uid, uploaded_at, experience_id}})
    RD->>F: get doc → merge map en Python → update(media_metadata sencer)
    RD->>K: delete refugi_detail:refugi_id:{id}
    alt Firestore falla
        RC->>R2: delete_files(keys pujades)
        V-->>C: 500
    end
    RC->>UD: add_uploaded_photos_keys(uid, keys) (resultat ignorat)
    V-->>C: 200 {uploaded:[...], failed:[...]}
```

## Diagrama — esborrar

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant P as IsMediaUploader
    participant V as RefugiMediaDeleteAPIView
    participant RC as RefugiLliureController
    participant RD as RefugiLliureDAO
    participant ED as ExperienceDAO
    participant R2 as R2MediaService
    participant UD as UserDAO
    participant F as Firestore

    C->>P: DELETE /api/refuges/{id}/media/{key}/
    P->>P: admin (role=admin) → permès
    P->>F: get data_refugis_lliures/{id} (directe, sense cache)
    alt key no existeix o creator_uid ≠ uid
        P-->>C: 403
    end
    P->>V: delete(id, key) → unquote(key)
    V->>RC: delete_refugi_media(id, key)
    RC->>RD: delete_media_metadata(id, key) (read-modify-write del map)
    opt metadata té experience_id
        RC->>ED: remove_media_key(experience_id, key) (ArrayRemove)
    end
    RC->>R2: delete_file(key) → bool (no llança)
    RC->>UD: remove_uploaded_photos_keys(creator_uid, [key])
    V-->>C: 200 {success, message, key}
```

## Passos (amb línies)
- Pujada: `api/views/refugi_media_views.py:143-160` → `RefugiLliureController.upload_refugi_media` (`api/controllers/refugi_lliure_controller.py:153-240`) → `RefugiLliureDAO.add_media_metadata` (`api/daos/refugi_lliure_dao.py:394-429`) → `UserDAO.add_uploaded_photos_keys` (`api/daos/user_dao.py:367-408`).
- Llistat: `RefugiLliureController.get_refugi_media` (`api/controllers/refugi_lliure_controller.py:129-151`) → `RefugiLliureDAO.get_media_metadata` (`api/daos/refugi_lliure_dao.py:361-392`), **sense cache**, presigna cada clau.
- Esborrat: `IsMediaUploader` (`api/permissions.py:192-276`) → `delete_refugi_media` (`api/controllers/refugi_lliure_controller.py:242-294`) → `delete_media_metadata` (`api/daos/refugi_lliure_dao.py:431-476`).
- Esborrat massiu intern (experiències, usuari, refugi): `delete_multiple_refugi_media` (`api/controllers/refugi_lliure_controller.py:296-370`) → `delete_multiple_media_metadata` (`api/daos/refugi_lliure_dao.py:478-539`), que retorna `(False, [])` si **cap** clau existeix.

## Errors
| Cas | HTTP |
|---|---|
| Sense fitxers | 400 |
| Refugi no trobat | 404 |
| Media inexistent o d'un altre usuari (DELETE) | **403** (no 404) |
| MIME no permès | dins `failed[]`, resposta 200 |
| Error Firestore | 500 |

## Gotchas i bugs
- **Col·lisió de claus**: el nom original del fitxer forma part de la clau → dues pujades `IMG_0001.jpg` al mateix refugi se sobreescriuen a R2 i al map **[FET]** (`api/controllers/refugi_lliure_controller.py:185`, `api/services/r2_media_service.py:196-203`).
- **Lost updates**: el map `media_metadata` i `uploaded_photos_keys` es reescriuen sencers **[FET patró / INFERÈNCIA carrera]**.
- R2 que falla en esborrar es reporta com a èxit (rollback mort, `api/controllers/refugi_lliure_controller.py:267-282`) **[FET]**.
- Només es valida el `content_type` declarat pel client; sense límit de mida **[FET]**.
- `unquote` a la vista sobre un path que Django ja ha decodificat → doble decodificació de `%25` **[INFERÈNCIA]**.
- Swagger documenta 204 per al DELETE però retorna 200 **[FET]**.
- `Refugi.to_dict()` reconstrueix `media_metadata` **sense** `experience_id` (`api/models/refugi_lliure.py:110-117`) — latent si algú torna a desar el refugi des del model **[FET]**.
