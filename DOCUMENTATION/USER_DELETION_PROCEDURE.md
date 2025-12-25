# Procediment d'Eliminació d'Usuaris

Aquest document detalla el procediment complet per eliminar un usuari del sistema RefugisLliures, incloent totes les dades i relacions associades.

## Visió General

Quan s'elimina un usuari, cal gestionar correctament totes les seves dades distribuïdes per diferents col·leccions de Firestore i el sistema d'emmagatzematge R2. El procés segueix un ordre específic per garantir la integritat de les dades i evitar referències trencades.

## Ordre d'Execució

El procediment d'eliminació segueix aquest ordre específic per garantir la coherència de les dades:

### 1. Eliminar Experiències
**Funció:** `ExperienceController.delete_experiences_by_creator(uid)`

- **Què fa:** Elimina totes les experiències on `creator_uid == uid`
- **Col·lecció afectada:** `experiences`
- **Implementació:**
  - Query: `experiences` WHERE `creator_uid == uid`
  - Per cada experiència:
    - Elimina el document
    - Invalida cache de detall (`experience_detail`)
    - Recopila `refuge_id` per invalidar cache de llistes
  - Invalida cache de llistes per cada refugi afectat (`experience_list:refuge_id:{refuge_id}:*`)

**Fitxers modificats:**
- `api/daos/experience_dao.py`: `delete_experiences_by_creator()`
- `api/controllers/experience_controller.py`: `delete_experiences_by_creator()`

---

### 2. Eliminar Dubtes
**Funció:** `DoubtController.delete_doubts_by_creator(uid)`

- **Què fa:** Elimina tots els dubtes on `creator_uid == uid`
- **Col·lecció afectada:** `doubts`
- **Implementació:**
  - Query: `doubts` WHERE `creator_uid == uid`
  - Per cada dubte:
    - Elimina totes les respostes de la subcol·lecció `answers`
    - Elimina el document del dubte
    - Invalida cache de detall (`doubt_detail`)
    - Recopila `refuge_id` per invalidar cache de llistes
  - Invalida cache de llistes per cada refugi afectat (`doubt_list:refuge_id:{refuge_id}`)

**Fitxers modificats:**
- `api/daos/doubt_dao.py`: `delete_doubts_by_creator()`
- `api/controllers/doubt_controller.py`: `delete_doubts_by_creator()`

---

### 3. Eliminar Respostes a Dubtes
**Funció:** `DoubtController.delete_answers_by_creator(uid)`

- **Què fa:** Elimina totes les respostes que ha creat l'usuari en dubtes d'altres usuaris
- **Col·lecció afectada:** `doubts/{doubt_id}/answers` (subcol·lecció)
- **Implementació:**
  - Utilitza `collection_group('answers')` per cercar a totes les subcol·leccions
  - Query: `collection_group('answers')` WHERE `creator_uid == uid`
  - Per cada resposta:
    - Obté el `doubt_id` del path del document
    - Elimina la resposta
    - Recopila `doubt_id` per actualitzar comptadors
  - Per cada dubte afectat:
    - Recompta respostes restants
    - Actualitza `answers_count`
    - Invalida cache

**Fitxers modificats:**
- `api/daos/doubt_dao.py`: `delete_answers_by_creator()`
- `api/controllers/doubt_controller.py`: `delete_answers_by_creator()`

---

### 4. Anonimitzar Proposals
**Funció:** `RefugeProposalController.anonymize_proposals_by_creator(uid)`

- **Què fa:** Anonimitza les proposals canviant `creator_uid` a `'unknown'`
- **Col·lecció afectada:** `refuge_proposals`
- **Raó:** Les proposals són importants per a l'historial del refugi
- **Implementació:**
  - Query: `refuge_proposals` WHERE `creator_uid == uid`
  - Per cada proposta:
    - Actualitza `creator_uid = 'unknown'`
    - Invalida cache de detall (`proposal_detail`)
  - Invalida cache de llistes (`proposal_list:*`)

**Fitxers modificats:**
- `api/daos/refuge_proposal_dao.py`: `anonymize_proposals_by_creator()`
- `api/controllers/refuge_proposal_controller.py`: `anonymize_proposals_by_creator()`

---

### 5. Anonimitzar Renovations
**Funció:** `RenovationController.anonymize_renovations_by_creator(uid)`

- **Què fa:** Anonimitza les renovations canviant `creator_uid` a `'unknown'` i `group_link` a `null`
- **Col·lecció afectada:** `renovations`
- **Raó:** Les renovations són importants per a l'historial de manteniment del refugi, però els enllaços als grups privats s'han d'eliminar per privacitat
- **Implementació:**
  - Query: `renovations` WHERE `creator_uid == uid`
  - Per cada renovation:
    - Actualitza `creator_uid = 'unknown'` i `group_link = null`
    - Recopila `refuge_id` per invalidar cache
    - Invalida cache de detall (`renovation_detail`)
  - Invalida cache de llistes (`renovation_list:*`)
  - Invalida cache de llistes per refugi (`renovation_refuge:{refuge_id}:*`)

**Fitxers modificats:**
- `api/daos/renovation_dao.py`: `anonymize_renovations_by_creator()`
- `api/controllers/renovation_controller.py`: `anonymize_renovations_by_creator()`
- `api/models/renovation.py`: Modificat per permetre `group_link = None` quan `creator_uid = 'unknown'`
- `api/serializers/renovation_serializer.py`: Afegit `allow_null=True` al camp `group_link` del serializer d'actualització

---

### 6. Eliminar Participacions en Renovations
**Funció:** `RenovationController.remove_user_from_participations(uid)`

- **Què fa:** Elimina l'usuari de `participants_uids` de totes les renovations on ha participat
- **Col·lecció afectada:** `renovations`
- **Implementació:**
  - Query: `renovations` WHERE `participants_uids` ARRAY_CONTAINS `uid`
  - Per cada renovation:
    - Utilitza `ArrayRemove([uid])` per eliminar de `participants_uids`
    - Recopila `refuge_id` per invalidar cache
    - Invalida cache de detall i llistes

**Fitxers modificats:**
- `api/daos/renovation_dao.py`: `remove_user_from_participations()`
- `api/controllers/renovation_controller.py`: `remove_user_from_participations()`

---

### 7. Eliminar Fotos Penjades
**Funció:** `RefugiLliureController.delete_multiple_refugi_media(refuge_id, keys)` (per cada refugi)

- **Què fa:** Elimina totes les fotos que l'usuari ha penjat als refugis
- **Dades utilitzades:** `user.uploaded_photos_keys`
- **Emmagatzematge afectat:** R2 Cloudflare
- **Implementació:**
  - Obté `uploaded_photos_keys` de l'usuari
  - Agrupa les keys per refugi (format: `refugis-lliures/{refuge_id}/{filename}`)
  - Per cada refugi:
    - Crida `delete_multiple_refugi_media(refuge_id, keys)`
    - Aquesta funció:
      - Elimina metadades de `media_metadata` a Firestore
      - Elimina fitxers de R2
      - Elimina keys de les experiències associades
  - Si alguna operació falla, es registra un warning però continua

**Fitxers utilitzats:**
- `api/controllers/refugi_lliure_controller.py`: `delete_multiple_refugi_media()`
- `api/daos/refugi_lliure_dao.py`: `delete_multiple_media_metadata()`

---

### 8. Eliminar Avatar
**Funció:** `UserController.delete_user_avatar(uid)`

- **Què fa:** Elimina l'avatar de l'usuari
- **Dades utilitzades:** `user.avatar_metadata`
- **Emmagatzematge afectat:** R2 Cloudflare
- **Implementació:**
  - Obté `avatar_metadata` de l'usuari
  - Elimina metadades de Firestore
  - Elimina fitxer de R2 utilitzant la `key`
  - Si l'eliminació de R2 falla, restaura les metadades a Firestore

**Fitxers utilitzats:**
- `api/controllers/user_controller.py`: `delete_user_avatar()`
- `api/daos/user_dao.py`: `delete_avatar_metadata()`

---

### 9. Eliminar de Visitors dels Refugis
**Funció:** `RefugiLliureDAO.remove_visitor_from_all_refuges(uid, visited_refuges)`

- **Què fa:** Elimina l'usuari de la llista `visitors` de tots els refugis que ha visitat
- **Dades utilitzades:** `user.visited_refuges`
- **Col·lecció afectada:** `data_refugis_lliures`
- **Implementació:**
  - Per cada `refuge_id` a `visited_refuges`:
    - Utilitza `ArrayRemove([uid])` per eliminar de `visitors`
    - Invalida cache del refugi (`refugi_detail`)
  - Si un refugi no existeix, registra un warning però continua

**Fitxers modificats:**
- `api/daos/refugi_lliure_dao.py`: `remove_visitor_from_all_refuges()`

---

### 10. Eliminar de Refuge Visits
**Funció:** `RefugeVisitController.remove_user_from_all_visits(uid)`

- **Què fa:** Elimina l'usuari de `visitors` i decrementa `total_visitors` de totes les visites (actuals i passades)
- **Col·lecció afectada:** `refuge_visits`
- **Implementació:**
  - Obté totes les visites de l'usuari amb `get_user_visits(uid)`
  - Per cada visita:
    - Busca l'usuari a la llista `visitors`
    - Elimina l'objecte `UserVisit` de la llista
    - Decrementa `total_visitors` (mínim 0)
    - Actualitza el document
    - Invalida cache de la visita

**Fitxers modificats:**
- `api/daos/refuge_visit_dao.py`: `remove_user_from_all_visits()`
- `api/controllers/refuge_visit_controller.py`: `remove_user_from_all_visits()`

---

### 11. Eliminar Usuari
**Funció:** `UserDAO.delete_user(uid)`

- **Què fa:** Elimina el document de l'usuari de Firestore
- **Col·lecció afectada:** `users`
- **Implementació:**
  - Elimina el document amb ID = `uid`
  - Invalida cache de l'usuari

**Fitxers utilitzats:**
- `api/daos/user_dao.py`: `delete_user()`

---

## Gestió d'Errors

El procediment segueix una estratègia de **fail-fast**: si qualsevol pas falla, el procés s'atura i retorna un error específic. Això garanteix que:

1. No es deixen dades inconsistents
2. L'usuari no s'elimina si no s'han pogut netejar totes les seves dades
3. Es pot identificar exactament on ha fallat el procés

**Excepcions:**
- Eliminació de fotos: Si falla l'eliminació de fotos d'un refugi, es registra un warning però continua amb els altres refugis
- Eliminació d'avatar: Si falla, es registra un warning però continua amb el procés
- Eliminació de visitors de refugis: Si un refugi no existeix, es registra un warning però continua

## Invalidació de Cache

Cada operació invalida la cache corresponent per garantir que les dades es reflecteixin immediatament:

- **Cache de detall:** S'invalida quan s'elimina o modifica un document específic
- **Cache de llistes:** S'invalida quan es modifica qualsevol element d'una llista
- **Patrons de cache:** S'utilitza `delete_pattern()` per invalidar múltiples claus relacionades

## Col·leccions Afectades

| Col·lecció | Operació | Camp Afectat |
|------------|----------|--------------|
| `experiences` | DELETE | - |
| `doubts` | DELETE | - |
| `doubts/{id}/answers` | DELETE | - |
| `refuge_proposals` | UPDATE | `creator_uid` → `'unknown'` |
| `renovations` | UPDATE | `creator_uid` → `'unknown'`, `group_link` → `null` |
| `renovations` | UPDATE | `participants_uids` (elimina uid) |
| `data_refugis_lliures` | UPDATE | `visitors` (elimina uid), `media_metadata` (elimina keys) |
| `refuge_visits` | UPDATE | `visitors` (elimina objecte), `total_visitors` (decrementa) |
| `users` | DELETE | - |

## Sistemes d'Emmagatzematge Afectats

| Sistema | Operació | Dades Eliminades |
|---------|----------|------------------|
| Firestore | DELETE/UPDATE | Documents i camps segons la taula anterior |
| R2 Cloudflare | DELETE | Fotos de refugis (`uploaded_photos_keys`) |
| R2 Cloudflare | DELETE | Avatar de l'usuari (`avatar_metadata.key`) |

## Punt d'Entrada

La funció principal és `UserController.delete_user(uid)`, que orquestra tot el procés.

**Ubicació:** `api/controllers/user_controller.py`

```python
def delete_user(self, uid: str) -> tuple[bool, Optional[str]]:
    """
    Elimina un usuari i totes les seves dades associades
    
    Returns:
        tuple: (success, error_message)
    """
```

## Exemple d'Ús

```python
from api.controllers.user_controller import UserController

controller = UserController()
success, error = controller.delete_user("user_uid_123")

if success:
    print("Usuari eliminat correctament")
else:
    print(f"Error: {error}")
```

## Logging

Cada pas del procés genera logs informatius:

- **INFO:** Confirmació d'operacions exitoses
- **WARNING:** Operacions que fallen però no aturen el procés
- **ERROR:** Errors crítics que aturen el procés

Exemple de logs:
```
INFO: Experiències eliminades per a l'usuari uid_123
INFO: Dubtes eliminats per a l'usuari uid_123
INFO: Respostes eliminades per a l'usuari uid_123
INFO: Proposals anonimitzades per a l'usuari uid_123
INFO: Renovations anonimitzades per a l'usuari uid_123
INFO: Participacions eliminades per a l'usuari uid_123
INFO: Fotos eliminades per a l'usuari uid_123
INFO: Avatar eliminat per a l'usuari uid_123
INFO: Eliminat de refugis visitats per a l'usuari uid_123
INFO: Eliminat de visites per a l'usuari uid_123
INFO: Usuari eliminat correctament amb UID: uid_123
```

## Consideracions de Rendiment

- Les operacions utilitzen queries de Firestore per obtenir dades relacionades
- La invalidació de cache és essencial per evitar dades obsoletes
- L'eliminació de fitxers de R2 pot ser costosa si l'usuari té moltes fotos
- El procés és seqüencial per garantir la integritat, però podria optimitzar-se amb batch operations en el futur

## Consideracions de Privacitat

Aquest procediment compleix amb els requisits de privacitat i GDPR:

1. **Dret a l'oblit:** Elimina totes les dades personals identificables
2. **Anonimització:** Les dades que cal mantenir per integritat (proposals, renovations) s'anonimitzen
3. **Eliminació d'enllaços privats:** Els `group_link` de les renovations s'eliminen per evitar que tercers puguin accedir a grups privats de l'usuari eliminat
4. **Completesa:** No es deixen referències trencades ni dades òrfenes

## Manteniment Futur

Si s'afegeixen noves col·leccions o relacions que involucrin usuaris, caldrà:

1. Afegir el pas corresponent al procediment `delete_user`
2. Actualitzar aquesta documentació
3. Crear les funcions necessàries als DAOs i Controllers corresponents
4. Mantenir l'ordre lògic d'eliminació per evitar referències trencades
