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

### Receptes (canvis al codi)
- [recipes/add-endpoint.md](recipes/add-endpoint.md)
- [recipes/add-service.md](recipes/add-service.md)
- [recipes/add-model.md](recipes/add-model.md)

### Guies (passos per executar o configurar)
| Guia | Per a… |
|---|---|
| [guides/local-setup.md](guides/local-setup.md) | Posar en marxa el backend en local (venv, `env/`, R2, seeding, `runserver`) |
| [guides/testing.md](guides/testing.md) | Executar i escriure tests, coverage, per què Firebase no s'inicialitza |
| [guides/firebase-credentials.md](guides/firebase-credentials.md) | Configurar el service account (local, Render, GitHub Actions) |
| [guides/r2-render-setup.md](guides/r2-render-setup.md) | Configurar Cloudflare R2 a Render/local, bucket, rotació de claus |
| [guides/admin-management.md](guides/admin-management.md) | Fer/treure admins (custom claims) i usar els endpoints de cache |
| [guides/client-auth-usage.md](guides/client-auth-usage.md) | Cridar l'API amb token de Firebase (JS, cURL, Swagger) |
| [guides/daily-visits-process.md](guides/daily-visits-process.md) | Executar el procés diari de visites (Actions, manual, crontab) |

### Disseny
- [design/patterns.md](design/patterns.md) — patrons arquitectònics i de disseny amb diagrames (amplia [ARCHITECTURE §7](ARCHITECTURE.md)).
- [design/decisions.md](design/decisions.md) — decisions preses (APIView, autenticació DRF + middleware, custom claims) i el seu estat real.

### Deep dives (detall que no cap als fluxos)
| Document | Pare |
|---|---|
| [deep-dives/condition-average.md](deep-dives/condition-average.md) — mitjana de `condition` | [flux 5](flows/05-refuge-proposals.md) |
| [deep-dives/refuge-proposals-payload.md](deep-dives/refuge-proposals-payload.md) — validació del payload i sincronització de `coords_refugis` | [flux 5](flows/05-refuge-proposals.md) |
| [deep-dives/user-deletion.md](deep-dives/user-deletion.md) — criteris i manteniment de l'esborrat d'usuari | [flux 1](flows/01-user-profile.md) |

## Història
Fins a l'octubre de 2026 hi havia una carpeta `DOCUMENTATION/` amb documentació escrita durant el desenvolupament. S'ha fusionat aquí: les guies s'han passat a `guides/` (corregides contra el codi), les explicacions vàlides s'han integrat als fluxos, integracions o `deep-dives/`/`design/`, i la resta (resums de canvis puntuals, resultats de tests antics, prompts d'especificació) s'ha eliminat perquè estava desactualitzada. Afirmacions antigues que ja **no** són certes: admin = `admin: true` (és `role == 'admin'`), admins a `FIREBASE_ADMIN_UIDS`, camps `media_keys`/`images_urls` al refugi, endpoints `/media/list/` i `/media/delete/` amb URLs, permisos d'admin per pujar fotos, vistes `ModelViewSet`, Python 3.8.

## Fora d'abast
- Frontend (`TFG/RefugisLliures_Frontend`) i integració frontend↔backend: es documentaran a part.
- Valors de secrets: mai es documenten. De `env/` només s'esmenten noms de variables.
