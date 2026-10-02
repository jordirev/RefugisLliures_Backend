# Flux 2 — Avatar d'usuari

> **[FET]** comprovat al codi · **[INFERÈNCIA]** deducció · **[NO VERIFICAT]** depèn de config externa.

## Endpoints (`api/views/user_views.py`)
| Mètode | URL | Vista | Permisos | Body |
|---|---|---|---|---|
| PATCH | `/api/users/{uid}/avatar/` | `UserAvatarAPIView.patch` (L647) | IsAuthenticated + IsSameUser | multipart, camp `file` (parsers L605-606) |
| DELETE | `/api/users/{uid}/avatar/` | `.delete` (L708) | idem | — |

Emmagatzematge: R2 amb `UserAvatarStrategy` → clau `users-avatars/{uid}/{filename}`, només imatges (`api/services/r2_media_service.py:101-145`). Firestore: `users/{uid}.media_metadata = {key, uploaded_at}`.

## Diagrama — pujar avatar

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant V as UserAvatarAPIView.patch
    participant UC as UserController.upload_user_avatar
    participant D as UserDAO
    participant R2 as R2MediaService(UserAvatarStrategy)
    participant F as Firestore users/{uid}
    participant K as CacheService

    C->>V: PATCH multipart file
    V->>V: request.FILES['file'] (400 si falta)
    V->>UC: upload_user_avatar(uid, file)
    UC->>D: get_user_by_uid (404 si no existeix)
    opt ja tenia avatar
        UC->>R2: delete_file(old_key) — abans de pujar el nou
    end
    UC->>R2: upload_file(file, uid, content_type, filename=file.name)
    alt content_type no permès
        R2-->>UC: ValueError("... no permès")
        V-->>C: 400
    end
    R2-->>UC: {key, url presignada}
    UC->>D: update_avatar_metadata(uid, {key, uploaded_at})
    D->>F: update({media_metadata})
    D->>K: delete user_detail:uid:{uid}
    alt Firestore falla
        UC->>R2: delete_file(new_key) (rollback)
    end
    UC-->>V: MediaMetadata(key, url, uploaded_at)
    V-->>C: 200 {key, url, uploaded_at}
```

## Passos (`api/controllers/user_controller.py`)
1. `upload_user_avatar` (L470-533): comprova usuari, **esborra l'avatar antic primer** (L488-495), puja el nou (L503), actualitza metadades (`api/daos/user_dao.py:580-614`), rollback del fitxer nou si falla Firestore (L515-519).
2. `delete_user_avatar` (L535-571): `UserDAO.delete_avatar_metadata` (`api/daos/user_dao.py:616-652`, posa `media_metadata: None`) i després `delete_file`.

## Errors
| Cas | HTTP |
|---|---|
| Sense fitxer | 400 |
| MIME no permès | 400 (match de `'no permès'`) |
| Usuari no trobat / sense avatar (DELETE) | 404 |
| Altres | 500 |
| DELETE OK | 204 |

## Gotchas
- L'avatar antic s'esborra **abans** de pujar el nou: si la pujada falla, Firestore apunta a una clau inexistent **[FET]**.
- El rollback de DELETE (re-posar metadades si R2 falla, L557-564) no s'executa mai perquè `delete_file` retorna `False` en lloc de llançar **[FET]**.
- La clau usa el nom original del fitxer **[FET]**; per a l'avatar és menys greu (prefix per usuari).
- No hi ha límit de mida **[FET]**.
