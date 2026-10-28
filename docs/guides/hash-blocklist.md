# Guia — Llista de hashes prohibits i purgues de moderació

> **[FET]** comprovat al codi · **[INFERÈNCIA]** deducció · **[NO VERIFICAT]** depèn de config externa.

Des del chunk 9 la llista de hashes CSAM és la taula `moderation.moderation_hash_blocklist` (PostgreSQL). Comença **buida** (PO, 28/10: a Firestore només hi havia dades de prova). El rol `app` **no la pot llegir ni escriure**: l'aplicació només la consulta amb `moderation.fn_hash_match` ([flux 12](../flows/12-media-moderation.md), [disseny §2.22](../design/postgres-schema.md)). S'alimenta amb una comanda de gestió que fa servir el rol propietari `migrator`.

## `load_hash_blocklist`

```bash
python manage.py load_hash_blocklist hashes.csv [--database migrator]
```

Requereix l'àlies `migrator` (variable d'URL de `migrator` a l'entorn, com per a `migrate`). Pot ser un fitxer que et passi una organització (NCMEC, IWF…); **no el versionis**.

### Format del CSV
UTF-8 (accepta BOM i salts de línia CRLF d'Excel), amb aquesta capçalera exacta:

```csv
sha256,phash,category,source
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855,,csam,ncmec-2026-10
,f0f0f0f0f0f0f0f0,csam,iwf
9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08,00ff00ff00ff00ff,other,intern
```

| Columna | Regla |
|---|---|
| `sha256` | 64 hexadecimals (majúscules o minúscules; es desa en minúscules). Pot ser buida si hi ha `phash` |
| `phash` | 1–16 hexadecimals (64 bits; es desa com a `bigint` amb signe). Pot ser buida si hi ha `sha256`. Cal almenys un dels dos |
| `category` | `csam` o `other`; buida = `csam` |
| `source` | obligatori, ≤ 100 caràcters (origen de la llista) |

### Comportament
- **Tot o res**: tot el fitxer es valida abans de tocar la BD i s'escriu en una sola transacció. Qualsevol fila invàlida és un `CommandError` amb el **número de línia** i no s'escriu res.
- **Idempotent**: una entrada ja present (mateix `sha256`, o mateix `phash` sense `sha256`) no es duplica; es pot tornar a executar amb el mateix fitxer. Surt `Entrades afegides: N` i `Ja existents: M`.
- Les línies en blanc s'ignoren. El nom del fitxer i el seu contingut no es registren enlloc.
- La coincidència a les pujades és sha256 exacte **o** pHash amb distància de Hamming ≤ 6; efectes: [flux 12](../flows/12-media-moderation.md) i [flux 3](../flows/03-refuge-media-upload.md).

### Verificar
Només amb el rol `migrator` (o un superusuari): `SELECT count(*) FROM moderation.moderation_hash_blocklist;`. Amb `app` retorna un error de permisos, que és el comportament esperat.

## Purgues de retenció (sense planificar)
Dues comandes de retenció, ambdues amb `system_context()`, lots de 5.000 i `CommandError` (codi ≠ 0) si fallen. **No estan planificades a cap workflow** ([TECH_DEBT R18](../TECH_DEBT.md)): fins que es planifiquin (GitHub Actions o Cloud Run Job), s'han d'executar a mà o amb un cron.

| Comanda | Què esborra | Freqüència prevista |
|---|---|---|
| `python manage.py purge_audit_logs` | `audit.audit_logs` amb `expire_at < now()` (365 dies; 5 anys si `legal_hold`) | diària |
| `python manage.py purge_moderation` | denúncies resoltes fa més de 24 mesos (`legal_hold`: 5 anys) i avisos de 24 mesos (tret dels lligats a una denúncia `legal_hold` vigent) | mensual |

Totes dues escriuen les xifres a la sortida estàndard. Necessiten la BD `default` (rol `app`); no cal `migrator`.
