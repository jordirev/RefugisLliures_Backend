# Deep dive — Esborrat d'usuari: criteris, abast i manteniment

> **[FET]** comprovat al codi · **[INFERÈNCIA]** deducció · **[NO VERIFICAT]** depèn de config externa.
> Document pare: [flux 1 — Perfil d'usuari](../flows/01-user-profile.md#esborrat-en-cascada--diagrama) (diagrama i taula dels 11 passos amb línies de codi). Aquí: **per què** cada pas, què toca i com mantenir-ho.

Punt d'entrada: `UserController.delete_user(uid) -> (success, error)` (`api/controllers/user_controller.py:125-276`), cridat per `DELETE /api/users/{uid}/`.

## Criteri per tipus de dada
| Dada | Tractament | Motiu |
|---|---|---|
| Experiències, dubtes, respostes | **Esborrar** | Contingut personal sense valor si desapareix l'autor |
| Propostes de refugi | **Anonimitzar** (`creator_uid='unknown'`) | Formen part de l'historial del refugi |
| Renovations vigents creades per l'usuari | **Esborrar** | Ningú les podria gestionar |
| Renovations passades creades per l'usuari | **Anonimitzar** (`creator_uid='unknown'`, `group_link=None`) | Historial de manteniment; el `group_link` apunta a un grup privat i s'elimina per privacitat |
| Participacions i expulsions en renovations | `ArrayRemove` de `participants_uids` / `expelled_uids` | No deixar UIDs penjats |
| Fotos pujades (R2 + `media_metadata` + `media_keys` d'experiències) | **Esborrar** | Dades personals |
| Avatar | **Esborrar** | Dada personal |
| `visitors` dels refugis visitats i entrades a `refuge_visits` | Treure l'UID / l'entrada | No deixar referències |
| `users/{uid}` | **Esborrar** (últim) | — |

Per permetre l'anonimització, el model `Renovation` accepta `group_link=None` quan `creator_uid=='unknown'` (`api/models/renovation.py:36-38`) i el serializer d'update té `allow_null=True` a `group_link`.

## Abast
| Col·lecció / sistema | Operació |
|---|---|
| `experiences` | DELETE |
| `doubts` i `doubts/{id}/answers` (via `collection_group('answers')`) | DELETE + recompte d'`answers_count` |
| `refuges_proposals` | UPDATE `creator_uid` |
| `renovations` | DELETE (vigents) / UPDATE (passades, participants, expulsats) |
| `data_refugis_lliures` | UPDATE `visitors`, `media_metadata` |
| `experiences` d'altres usuaris | UPDATE `media_keys` (si hi havia fotos de l'usuari) |
| `refuge_visits` | UPDATE `visitors`, `total_visitors` |
| `users` | DELETE |
| R2 | DELETE fotos (`refugis-lliures/{refuge_id}/...`, agrupades per refugi) i avatar |
| Firebase Auth | **cap** — el compte no s'esborra al backend |

## Estratègia d'errors
**Fail-fast**: cada pas que falla retorna `(False, "Error ...")` i atura el procés — inclosos fotos i avatar **[FET]**. Única excepció tolerada: un refugi de `uploaded_photos_keys` que ja no existeix (warning i continua).

Com que no hi ha transaccions, "aturar" **no desfà** els passos anteriors: un error al pas 7 deixa experiències i dubtes ja esborrats i l'usuari encara existent. Reintentar el DELETE és segur en la majoria de passos (consultes per `creator_uid` que ja no troben res) **[INFERÈNCIA]**. La vista retorna sempre 404 en cas d'error ([TECH_DEBT M10](../TECH_DEBT.md)).

Bugs coneguts del procés: decrement de `total_visitors` en 1 i no en `num_visitors` ([TECH_DEBT M3](../TECH_DEBT.md)); `delete_file` de R2 no llança i amaga fallades ([TECH_DEBT A4](../TECH_DEBT.md)); escriptures no atòmiques ([TECH_DEBT A6](../TECH_DEBT.md)).

## Privacitat (dret a l'oblit)
- S'eliminen totes les dades identificables de l'usuari al backend.
- Allò que cal conservar per integritat (propostes, renovations passades) s'anonimitza.
- Pendent: esborrar el compte de **Firebase Auth** (s'espera que ho faci el client) **[INFERÈNCIA]**.

## Manteniment
Si s'afegeix una col·lecció o relació amb `creator_uid` o UIDs d'usuari:
1. Decideix el criteri (esborrar vs anonimitzar) segons la taula de dalt.
2. Afegeix mètodes `*_by_creator` al DAO i al controller del domini.
3. Afegeix el pas a `UserController.delete_user` respectant l'ordre (dependents abans que l'usuari; fotos d'experiències abans d'esborrar les seves claus).
4. Invalida la cache de detall i de llistes afectades.
5. Actualitza aquesta taula i la del [flux 1](../flows/01-user-profile.md). Vegeu també [recipes/add-model.md §6](../recipes/add-model.md).
