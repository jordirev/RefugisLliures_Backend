# Documentació tècnica del backend — RefugisLliures

Documentació generada a partir del **codi actual** (branca `main`, octubre 2026). Totes les rutes són relatives a l'arrel del repo (`Backend/RefugisLliures_Backend/`) i es citen com `ruta:línia`.

## Llegenda (s'aplica a tots els documents)

| Marca | Significat |
|---|---|
| **[FET]** | Comprovat llegint el codi a la ruta/línia citada. |
| **[INFERÈNCIA]** | Deducció raonada a partir del codi (comportament de llibreries, conseqüències en temps d'execució), no executada. |
| **[NO VERIFICAT]** | No s'ha pogut confirmar al codi (depèn de configuració externa: Render, Firebase console, GitHub secrets…). |

Les línies poden desplaçar-se amb canvis futurs; si una cita no quadra, busca el nom del mètode.

## Índex

- [ARCHITECTURE.md](ARCHITECTURE.md) — stack, capes, rutes, auth, cache, convencions i excepcions.
- [GOTCHAS.md](GOTCHAS.md) — què NO fer.
- [TECH_DEBT.md](TECH_DEBT.md) — bugs i deute tècnic detectat, per severitat.

### Fluxos d'usuari (amb diagrama de seqüència Mermaid)
| # | Flux | Fitxer |
|---|---|---|
| 0 | Pipeline d'autenticació d'una petició | [flows/00-auth-request-pipeline.md](flows/00-auth-request-pipeline.md) |
| 1 | Perfil d'usuari (alta, consulta, edició, esborrat en cascada) | [flows/01-user-profile.md](flows/01-user-profile.md) |
| 2 | Avatar d'usuari | [flows/02-user-avatar.md](flows/02-user-avatar.md) |
| 3 | Pujar / llistar / esborrar fotos d'un refugi | [flows/03-refuge-media-upload.md](flows/03-refuge-media-upload.md) |
| 4 | Cerca, coordenades i detall de refugis | [flows/04-refuge-search-detail.md](flows/04-refuge-search-detail.md) |
| 5 | Propostes de refugi (crear/editar/esborrar) i revisió admin | [flows/05-refuge-proposals.md](flows/05-refuge-proposals.md) |
| 6 | Visites planificades i procés diari | [flows/06-refuge-visits.md](flows/06-refuge-visits.md) |
| 7 | Renovations (reformes) i participants | [flows/07-renovations.md](flows/07-renovations.md) |
| 8 | Experiències amb fotos | [flows/08-experiences.md](flows/08-experiences.md) |
| 9 | Dubtes i respostes | [flows/09-doubts-answers.md](flows/09-doubts-answers.md) |
| 10 | Refugis preferits i visitats | [flows/10-favourite-visited.md](flows/10-favourite-visited.md) |
| 11 | Endpoints admin de cache i health check | [flows/11-admin-cache-health.md](flows/11-admin-cache-health.md) |

### Integracions externes
- [integrations/firebase-auth.md](integrations/firebase-auth.md)
- [integrations/firestore.md](integrations/firestore.md)
- [integrations/cloudflare-r2.md](integrations/cloudflare-r2.md)
- [integrations/redis-cache.md](integrations/redis-cache.md)
- [integrations/render-deploy-ci.md](integrations/render-deploy-ci.md) (Render, GitHub Actions, SonarCloud, Codecov)

### Receptes
- [recipes/add-endpoint.md](recipes/add-endpoint.md)
- [recipes/add-service.md](recipes/add-service.md)
- [recipes/add-model.md](recipes/add-model.md)

## Relació amb `DOCUMENTATION/` (documentació antiga)

La carpeta `DOCUMENTATION/` (~35 fitxers, ~8.300 línies) es manté sense canvis. És útil com a context històric, però **té afirmacions que ja no quadren amb el codi**. Contradiccions detectades:

| Fitxer antic | Afirmació | Realitat al codi |
|---|---|---|
| `DOCUMENTATION/CUSTOM_CLAIMS.md` (p. ex. L34, L70, L114) | Admin = custom claim `admin: true` | Admin = claim `role == 'admin'` (`api/permissions.py:21`, `scripts/manage_admins.py:35`) **[FET]** |
| `DOCUMENTATION/CACHE_ADMIN_ENDPOINTS.md` L68-83, L186 | Barreja `admin: True` i `role: 'admin'` | Només `role == 'admin'` **[FET]** |
| `DOCUMENTATION/CHANGE_TO_CUSTOM_CLAMIS.md` L23, L34, L193 | `IsFirebaseAdmin` comprova `admin: true` | Comprova `role == 'admin'` **[FET]** |
| `DOCUMENTATION/AUTHENTICATION_STANDARD.md` L129-246 | Exemples amb `ModelViewSet` | Totes les vistes són `APIView` o `@api_view` (`api/views/*.py`) **[FET]** |
| `DOCUMENTATION/README.md` | Python 3.8+ | CI usa Python 3.10 (`.github/workflows/django.yml:16`); `zoneinfo` requereix ≥3.9 (`api/utils/timezone_utils.py:5`) **[FET]** |

La resta de fitxers antics no s'han contrastat línia a línia → tractar-los com a **[NO VERIFICAT]**.

## Fora d'abast
- Frontend (`TFG/RefugisLliures_Frontend`) i integració frontend↔backend: es documentaran a part.
- Valors de secrets: mai es documenten. De `env/` només s'esmenten noms de variables.
