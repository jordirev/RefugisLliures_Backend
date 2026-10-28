# Deep dive — Esborrat d'usuari: criteris, abast i manteniment

> **[FET]** comprovat al codi · **[INFERÈNCIA]** deducció · **[NO VERIFICAT]** depèn de config externa.
> Document pare: [flux 1 — Perfil d'usuari](../flows/01-user-profile.md#esborrat--provisional-d21-d22) (diagrama). Aquí: **per què** cada pas, què toca i com mantenir-ho.

> **Chunk 3 (D21/D22): procediment provisional.** `UserController` ha desaparegut. El punt d'entrada és `apps.accounts.services.delete_user(uid)`, cridat per `DELETE /api/users/{uid}/`, que executa **(1)** els passos de Firestore dels dominis encara no migrats (**cap des del chunk 8**: `_firestore_steps` és buida; **visites, reformes, dubtes, experiències i propostes ja són SQL**), **(2)** l'esborrat a R2 d'avatar, miniatura, fotos pujades (`refuges.refuge_media.creator_uid`) **i mitjans de les seves experiències pujats per altri** (`experience.creator_uid`, D38) i **(3)** les reformes vigents del creador (`renovations.services.delete_current_by_creator`, dins el *savepoint*) i el `DELETE FROM users.users`, que cascadeja perfil, avatar, preferits, visitats, participacions en visites (`refuge_visit_participants`), participacions i expulsions de reformes, **dubtes i respostes (chunk 6, `activity.doubts`/`activity.answers` per `creator_uid`)**, **experiències (chunk 7, `activity.experiences.creator_uid`, i amb elles els seus `refuge_media` per `experience_id`)**, `upload_intents` (chunk 7, `user_uid`) i les files de `refuge_media` (FK reals `ON DELETE CASCADE`), i deixa anònimes (`SET NULL`) les reformes passades creades, i **(4)** l'esborrat del compte de Firebase Auth en el mateix *savepoint* (U7: si falla, es desfà el `DELETE`). Fail-fast: qualsevol pas que falla → `UserDeletionError` → 500 `{error, error_id}`, l'usuari es conserva i el DELETE és reintentable. El procediment únic en una transacció, amb la cua `media_deletion_queue`, és el **chunk 10**; el que segueix descriu els criteris (vàlids) i, on cal, l'estat anterior.

Punt d'entrada: `services.delete_user(uid)` (abans `UserController.delete_user`).

## Criteri per tipus de dada
| Dada | Tractament | Motiu |
|---|---|---|
| Experiències, dubtes, respostes | **Esborrar** (SQL: cascada de `DELETE users.users`) | Contingut personal sense valor si desapareix l'autor. La mitjana de condició del refugi **no** es toca (el vot es queda: no és dada personal) |
| Propostes de refugi (chunk 8) | **Anonimitzar** (FK `creator_uid`/`reviewer_uid` `ON DELETE SET NULL`; l'API emet `'unknown'`) i **anul·lar el `comment`** (`UPDATE … SET comment = NULL` amb `system_context()`, al mateix *savepoint* de `delete_user`) | Formen part de l'historial del refugi; el comentari és text lliure i pot dur dades personals (RGPD, decisió del PO 28/10) |
| Renovations vigents creades per l'usuari (`fin_date >= avui` de Madrid) | **Esborrar** (`delete_current_by_creator`; cascada a participants, expulsats i enllaç) | Ningú les podria gestionar |
| Renovations passades creades per l'usuari | **Anonimitzar**: la FK `creator_uid` `ON DELETE SET NULL` la deixa a `NULL` (l'API emet `'unknown'`) i el trigger `renovations_anonymize` n'esborra el `group_link` | Historial de manteniment; el `group_link` apunta a un grup privat i s'elimina per privacitat |
| Participacions i expulsions en renovations | **Cascada** de les FK `user_uid` `ON DELETE CASCADE` | No deixar UIDs penjats |
| Fotos pujades (R2 + fila de `refuge_media`) i mitjans de les experiències de l'usuari pujats per altri (un admin) | **Esborrar** (fitxers: `_delete_r2_media`; files: cascada per `creator_uid` i per `experience_id`) | Dades personals; els fitxers no han de quedar orfes (D38) |
| Avatar | **Esborrar** | Dada personal |
| Miniatures (`{uuid}_thumb.webp`) de les fotos i de l'avatar | **Esborrar** (via `thumb_key` de les metadades) | Dades personals; si falla l'esborrat queda orfe i es registra un warning |
| `moderation.media_reports` (chunk 9) | **Denunciant esborrat**: les denúncies no `legal_hold` cauen en **cascada**; les `legal_hold` (CSAM) es **desvinculen** (`reporter_uid` NULL + `anonymized_at`, per `users.fn_users_detach_legal_hold`, `SECURITY DEFINER`, abans de la cascada) i **conserven `details`** (decisió del PO, 28/10, RGPD: forma part de l'evidència). L'API emet `reporter_uid = 'unknown'`. **Autor del mitjà o moderador** esborrat: `media_creator_uid`/`resolved_by` → `SET NULL` | Obligacions DSA i evidència CSAM; la resta no cal conservar-la |
| `moderation.moderation_notices` (chunk 9) | **Cascada** per `user_uid` (són avisos de l'usuari esborrat); si es borra el refugi o la denúncia, `SET NULL` | Dada personal de l'usuari |
| `moderation-hold/` (R2) | **Es conserva** (clau `moderation-hold/<upload_id>` o `<clau original>`, sense l'UID) | Evidència retinguda per obligació legal |
| `audit.audit_logs` (chunk 9) | **Cascada** per `actor_uid`/`subject_uid` (FK `DEFERRABLE`), excepte les files `legal_hold` (accions CSAM): el trigger les deixa amb `actor_uid`/`subject_uid` NULL i es conserven fins a `expire_at` (5 anys). No és retroactiu (`app` no té `UPDATE`). Les altres caduquen als 365 dies (`purge_audit_logs`, sense planificar, R18) | Registre art. 32 RGPD; l'UID afectat mai és a `target_id`/`metadata` |
| `visitors` dels refugis visitats | **Cascada** (`user_visited_refuges`; ja no hi ha array `visitors`) | No deixar referències |
| Participacions en visites (`activity.refuge_visit_participants`, PostgreSQL) | **Cascada** de `DELETE users.users`; el total (vista `refuge_visit_totals`) es recalcula sol | No deixar referències |
| Preferits i visitats (`user_*_refuges`), perfil públic i avatar (PostgreSQL) | **Cascada** de `DELETE users.users` | — |
| `users.users` | **Esborrar** | — |
| Compte de Firebase Auth | **Esborrar** (últim, dins el *savepoint* del `DELETE users.users`; U7, D24) | Sense compte no es pot tornar amb el mateix UID per saltar-se un bloqueig |
| Email o identificadors per impedir un compte nou | **No es desa res** (decisió del PO, 26/10) | Un hash d'email continua sent dada personal (pseudonimitzada) i, per a un esborrat demanat, caldria justificar-ne la retenció; un email nou costa segons, així que el benefici no ho compensa |

Per permetre l'anonimització, `renovations.creator_uid` és *nullable* i el `group_link` viu en una taula a part (que esborra el trigger); el *constraint trigger* de «cal enllaç» només s'aplica a reformes amb creador (D33) **[FET]**. Els passos de Firestore de reformes, dubtes i experiències han desaparegut de `_firestore_steps` (en queda 1: propostes, `apps/accounts/services.py`).

## Abast
| Col·lecció / sistema | Operació |
|---|---|
| ~~`experiences`~~ (migrades, chunk 7) | Ara són `activity.experiences`: cascada del `DELETE users.users` (FK `creator_uid ON DELETE CASCADE`); els seus mitjans (`refuge_media.experience_id`) cauen per la FK `ON DELETE CASCADE` **[FET]** |
| PostgreSQL `moderation.upload_intents` (chunk 7) | cascada per `user_uid` |
| ~~`doubts` i `doubts/{id}/answers`~~ (migrats, chunk 6) | Ara són `activity.doubts`/`activity.answers`: cascada del `DELETE users.users` (FK `creator_uid ON DELETE CASCADE`). Les respostes d'un usuari a dubtes aliens també s'esborren, amb el seu subarbre de rèpliques, **també les d'altres usuaris** que hi penjaven (decisió del PO, 26/10: es manté l'esborrat del subarbre, coherent amb l'esborrat manual d'una resposta; no s'anonimitza) **[FET]** |
| PostgreSQL `moderation.media_reports`/`moderation_notices` i `audit.audit_logs` (chunk 9) | cascada, excepte les files `legal_hold` (trigger `fn_users_detach_legal_hold`: anonimitza i conserva `details`) |
| PostgreSQL `proposals.refuge_proposals` (chunk 8) | `SET NULL` de `creator_uid`/`reviewer_uid` + `comment = NULL` explícit |
| PostgreSQL `activity.renovations` (+ `renovation_group_links`, `renovation_participants`, `renovation_expelled`) | DELETE explícit (vigents del creador) / `SET NULL` + trigger (passades) / cascada (participacions i expulsions) |
| `data_refugis_lliures` (legacy) | ja no es toca des de l'esborrat d'usuari |
| ~~`experiences` d'altres usuaris: UPDATE `media_keys`~~ | Ja no cal: les fotes d'un usuari a experiències d'altres són files de `refuge_media` (`creator_uid`) i cauen per cascada |
| PostgreSQL `users.users` | DELETE (cascada: perfil, avatar, preferits, visitats, participacions en visites, `refuge_media`) |
| R2 | `delete_files` d'avatar + miniatura + fotos pujades + mitjans de les seves experiències (+ miniatures), en un sol lot; les claus es llegeixen amb `system_context()` en dues consultes amb índex (`creator_uid` i `experience_id IN (experiències de l'usuari)`) (un mitjà amagat d'un altre no és visible per a l'usuari sota RLS) |
| Firebase Auth | `auth.delete_user(uid)` (idempotent: `UserNotFoundError` es dona per fet) |

## Estratègia d'errors
**Fail-fast**: cada pas de Firestore que falla (`(False, error)`), o un lot d'R2 amb fitxers fallits, atura el procés amb `UserDeletionError` **[FET]**. (Ja no hi ha l'excepció de «refugi de `uploaded_photos_keys` inexistent».)

Com que no hi ha transaccions entre magatzems, "aturar" **no desfà** els passos anteriors: un error a R2 deixa l'usuari encara existent (no queda cap pas de Firestore aplicat des del chunk 8). Reintentar el DELETE és segur en la majoria de passos (consultes per `creator_uid` que ja no troben res) **[INFERÈNCIA]**. La vista retorna 500 `{error, error_id}` (404 només si l'usuari no existeix); abans retornava sempre 404 ([TECH_DEBT M10](../TECH_DEBT.md), resolt pel que fa al codi d'estat).

Bugs coneguts del procés: escriptures no atòmiques entre Firestore, R2 i PostgreSQL ([TECH_DEBT A6, U2](../TECH_DEBT.md)). L'esborrat d'R2 comprova el resultat (`delete_files` retorna `failed`; A4 resolt).

## Privacitat (dret a l'oblit)
- S'eliminen totes les dades identificables de l'usuari al backend.
- Allò que cal conservar per integritat (propostes, renovations passades) s'anonimitza.
- El compte de **Firebase Auth** l'esborra el backend després de les dades (U7); el client només tanca la sessió local **[FET]**.

## Manteniment
Si s'afegeix una col·lecció o relació amb `creator_uid` o UIDs d'usuari:
1. Decideix el criteri (esborrar vs anonimitzar) segons la taula de dalt.
2. Afegeix mètodes `*_by_creator` al DAO i al controller del domini.
3. Si el domini és a Firestore: afegeix el pas a `services._firestore_steps` d'`apps/accounts/services.py` (abans de R2 i del `DELETE users.users`). Si és a PostgreSQL: usa una FK `ON DELETE CASCADE`/`SET NULL` al DDL (no de Django) o, per anonimitzar, un pas explícit.
4. Invalida la cache de detall i de llistes afectades (dominis a Firestore).
5. Actualitza aquesta taula i el [flux 1](../flows/01-user-profile.md). Vegeu també [recipes/add-model.md §6](../recipes/add-model.md).
