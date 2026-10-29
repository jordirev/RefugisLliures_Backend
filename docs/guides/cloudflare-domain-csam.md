# Guia (futur) — Domini propi a Cloudflare, Worker amb tokens HMAC i detecció de CSAM

> **[FET]** comprovat al codi · **[INFERÈNCIA]** deducció · **[NO VERIFICAT]** depèn de config externa.
> Estat: **pendent**. Avui el bucket R2 és privat i es serveix amb URLs prefirmades d'1 h (`*.r2.cloudflarestorage.com`); la moderació automàtica només té `HashBlocklistProvider` actiu ([flux 12](../flows/12-media-moderation.md)).

## Per què
- El **CSAM Scanning Tool** de Cloudflare (gratuït) només funciona sobre contingut servit per una **zona pròpia** (domini) amb proxy de Cloudflare; no s'aplica a `r2.cloudflarestorage.com` ni a URLs prefirmades S3 **[NO VERIFICAT]** (comprovar a la documentació vigent de Cloudflare).
- Un domini propi + Worker permet **cache a la vora** (URLs estables → `expo-image` amb `cacheKey` encara més eficient) i, si es vol, Image Transformations.

## 1. Domini i bucket
1. Registra o transfereix un domini a Cloudflare (p. ex. `refugislliures.cat`) i activa el proxy (núvol taronja).
2. **No** facis el bucket públic. Crea un subdomini `media.<domini>` servit per un **Worker** amb binding al bucket R2.

## 2. Worker amb tokens HMAC (substitueix les URLs prefirmades S3)
- El backend signa `HMAC_SHA256(secret, "<key>|<exp>")` i retorna `https://media.<domini>/<key>?exp=<epoch>&sig=<hex>`.
- El Worker valida `exp > now` i la signatura (comparació en temps constant), llegeix l'objecte del binding R2 i respon amb `Cache-Control: private, max-age=<restant>`.
- Rebutja qualsevol prefix que no sigui `refugis-lliures/` o `users-avatars/` (mai `quarantine/` ni `moderation-hold/`).
- Al backend: nova estratègia/funció a `R2MediaService.generate_presigned_url` (mateixa signatura) controlada per una variable d'entorn (`MEDIA_CDN_BASE_URL`, `MEDIA_HMAC_SECRET`) perquè el canvi sigui transparent per a l'app. Les claus i el contracte MediaItem **no** canvien.

## 3. Cloudflare CSAM Scanning Tool
1. Dashboard → *Caching → Configuration → CSAM Scanning Tool* → activar i indicar un correu de notificació (el de denúncies de la Política de privacitat).
2. Cloudflare compara les imatges servides per la zona amb hashes de NCMEC (fuzzy hashing); si hi ha coincidència bloqueja l'URL i envia un avís.
3. Quan arribi un avís: buscar la clau a `media_metadata`, resoldre-la amb `PATCH /api/admin/media-reports/{id}/` (`remove` sobre una denúncia `child_sexual_abuse` → el fitxer es mou a `moderation-hold/` i l'usuari queda bloquejat) i seguir el procediment legal (comunicació a les autoritats; vegeu el document legal del frontend).

## 4. PhotoDNA / NCMEC / Google Content Safety API
| Servei | Com sol·licitar-lo | On s'integra |
|---|---|---|
| Microsoft **PhotoDNA Cloud Service** | Formulari de sol·licitud a Microsoft (cal justificar el servei i acceptar condicions; aprovació manual) | `PhotoDNAProvider` (`apps/moderation/moderation_service.py`): implementar `check()` amb l'API Match i posar `enabled=True` quan hi hagi credencials |
| **NCMEC** (hash sharing / CyberTipline) | Registre com a *Electronic Service Provider* a NCMEC (orientat a EUA); a Europa, coordinació amb INCIBE / Policia / Guàrdia Civil | Importar hashes a `moderation_hash_blocklist` (camps `sha256`/`phash`, `source='ncmec'`) |
| **Google Content Safety API** | Sol·licitud a través del programa *Child Safety Toolkit* de Google | `GoogleContentSafetyProvider`: enviar els bytes processats (`ModerationInput.data`) i bloquejar per sobre d'un llindar de prioritat |

Notes:
- Els proveïdors nous han de ser **fail-closed** (si fallen, no es publica) com l'actual (`ModerationService.check` propaga l'excepció → `processing_error`).
- Cap proveïdor ha de rebre dades personals a part dels bytes/hashes del fitxer.
- Actualitza el [flux 12](../flows/12-media-moderation.md), [integrations/cloudflare-r2.md](../integrations/cloudflare-r2.md) i la Política de privacitat (encarregats del tractament) quan s'activi qualsevol d'aquests serveis.

## Checklist
- [ ] Domini a Cloudflare amb proxy.
- [ ] Worker `media.<domini>` amb validació HMAC i llista blanca de prefixos.
- [ ] Backend: URLs del Worker darrere variable d'entorn; tests del signador.
- [ ] CSAM Scanning Tool activat amb correu de notificació.
- [ ] Sol·licituds enviades: PhotoDNA, Google Content Safety; contacte INCIBE.
- [ ] Docs i Política de privacitat actualitzades.
