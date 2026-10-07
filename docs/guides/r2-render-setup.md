# Guia — Configurar Cloudflare R2 (Render i local)

> **[FET]** comprovat al codi · **[INFERÈNCIA]** deducció · **[NO VERIFICAT]** depèn de config externa.
> Com l'usa el codi (estratègies de path, API del servei, gotchas): [integrations/cloudflare-r2.md](../integrations/cloudflare-r2.md).

## Variables necessàries (només noms)
`R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_ENDPOINT` (format `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`), `R2_BUCKET_NAME`. Es llegeixen amb `os.getenv` a `api/r2_config.py`.

> ⚠️ Mai posis valors reals en fitxers versionats (docs, `render.yaml`, `run_process_visits.*`).

## 1. Render
1. https://dashboard.render.com/ → servei del backend → pestanya **Environment**.
2. Afegeix les 4 variables `R2_*` → **Save Changes** (Render redesplega sol).
3. Verifica:
   ```bash
   curl https://refugislliures-backend.onrender.com/api/health/
   curl -X POST "https://refugislliures-backend.onrender.com/api/refuges/<id>/media/" \
     -H "Authorization: Bearer <firebase-token>" -F "files=@test.jpg"
   ```
   El health check torna 503 si falta config R2 ([flux 11](../flows/11-admin-cache-health.md)).

## 2. GitHub Actions
El procés diari (`process-visits.yml`) necessita les mateixes `R2_*` com a **secrets** del repositori.

## 3. Local
Exporta-les a la shell abans de `runserver` (no n'hi ha prou amb `env/.env.development`): vegeu [local-setup.md §3](local-setup.md#3-exportar-les-variables-r2).

## 4. Bucket a Cloudflare
1. https://dash.cloudflare.com/ → **R2** → bucket del projecte.
2. **Public access: desactivat** — el backend serveix URLs presignades d'1 h.
3. **Access keys** amb permisos de lectura/escriptura sobre el bucket.
4. **CORS**: no cal mentre el client només descarregui per URL presignada. Si mai es puja directament des del client:
   ```json
   [{"AllowedOrigins": ["http://localhost:3000", "https://<domini>"],
     "AllowedMethods": ["GET", "PUT", "POST", "DELETE"],
     "AllowedHeaders": ["*"], "ExposeHeaders": ["ETag"], "MaxAgeSeconds": 3600}]
   ```

## 5. Rotació de credencials
1. Cloudflare: genera noves access keys i **revoca** les antigues.
2. Render i GitHub secrets: actualitza les variables (redesplegament automàtic a Render).
3. Local: torna a exportar-les i reinicia el servidor.

## 6. Monitorització
- **Logs de Render**: filtra per `Error pujant fitxer a R2`, `Error eliminant fitxer de R2`, `Error generant URL prefirmada`. Els missatges d'èxit (`Fitxer pujat correctament`…) són `logger.info` i el logger `api` només mostra `WARNING`+ ([ARCHITECTURE §8](../ARCHITECTURE.md)), així que no hi apareixen **[INFERÈNCIA]**.
- **Cloudflare → bucket → Metrics**: nombre d'objectes, espai, peticions (GET/PUT/DELETE), transferència.

## Problemes habituals
| Símptoma | Causa / solució |
|---|---|
| `R2 configuration is incomplete` | Falta alguna `R2_*` a l'entorn |
| 403 de R2 | Credencials incorrectes, bucket inexistent o key sense permisos |
| La URL d'una foto dona 403 | URL presignada caducada (1 h): torna a demanar el recurs |
| Fitxer a R2 però no a Firestore | Error en actualitzar `media_metadata`; revisa logs (el controller intenta rollback, però vegeu [TECH_DEBT A4](../TECH_DEBT.md)) |
