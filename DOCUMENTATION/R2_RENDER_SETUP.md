# Guia de Configuració R2 per Render

## Passos per Configurar les Variables d'Entorn a Render

### 1. Accedir al Dashboard de Render

1. Ves a https://dashboard.render.com/
2. Selecciona el teu servei (RefugisLliures Backend)
3. Fes clic a la pestanya **"Environment"**

### 2. Afegir Variables d'Entorn R2

Afegeix les següents variables:

```
R2_ACCESS_KEY_ID=b2737df8dd35950b4c80a62df55424ff
R2_SECRET_ACCESS_KEY=1b685c4dbffd190aa3076c9fd9cbaf96ce5dbed9c4e9e0d44539aa8a2bc3104f
R2_ENDPOINT=https://e0c55e2f7b13e7548afed9db64268f83.r2.cloudflarestorage.com
R2_BUCKET_NAME=refugis-lliures-media
```

### 3. Guardar i Redesplegar

1. Fes clic a **"Save Changes"**
2. Render redesplegarà automàticament el servei amb les noves variables

### 4. Verificar la Configuració

Un cop redesplegar:

```bash
# Test health check endpoint
curl https://refugislliures-backend.onrender.com/api/health/

# Test upload (amb token Firebase vàlid)
curl -X POST "https://refugislliures-backend.onrender.com/api/refuges/{id}/media/" \
  -H "Authorization: Bearer <firebase-token>" \
  -F "files=@test-image.jpg"
```

## Configuració del Bucket R2

### Accedir a Cloudflare Dashboard

1. Ves a https://dash.cloudflare.com/
2. Selecciona **R2** al menú lateral
3. Selecciona el bucket `refugis-lliures-media`

### Configurar CORS (si cal)

Si necessites accés directe des del frontend, afegeix aquesta configuració CORS:

```json
[
  {
    "AllowedOrigins": [
      "http://localhost:3000",
      "https://yourdomain.com"
    ],
    "AllowedMethods": [
      "GET",
      "PUT",
      "POST",
      "DELETE"
    ],
    "AllowedHeaders": [
      "*"
    ],
    "ExposeHeaders": [
      "ETag"
    ],
    "MaxAgeSeconds": 3600
  }
]
```

**Nota:** Amb URLs prefirmades, no necessites CORS si accedeix el backend.

### Permisos del Bucket

Assegura't que el bucket té els permisos correctes:
- **Public Access:** Desactivat (usem URLs prefirmades)
- **Access Keys:** Configurades amb permisos de lectura/escriptura

## Instal·lar Dependències

Si estàs desplegant per primera vegada o has actualitzat requirements.txt:

```bash
pip install -r requirements.txt
```

Render ho farà automàticament durant el desplegament.

## Testing en Local

### 1. Configurar Variables d'Entorn

Copia les variables d'entorn al fitxer `.env.development`:

```bash
cd env/
# Les variables ja estan configurades a .env.development
```

### 2. Instal·lar boto3

```bash
pip install boto3
```

### 3. Executar el Servidor

```bash
python manage.py runserver
```

### 4. Test amb Postman o curl

**Upload:**
```bash
curl -X POST "http://localhost:8000/api/refuges/refuge123/media/" \
  -H "Authorization: Bearer <firebase-token>" \
  -F "files=@test.jpg"
```

**List:**
```bash
curl "http://localhost:8000/api/refuges/refuge123/media/list/" \
  -H "Authorization: Bearer <firebase-token>"
```

**Delete:**
```bash
curl -X DELETE "http://localhost:8000/api/refuges/refuge123/media/delete/" \
  -H "Authorization: Bearer <firebase-token>" \
  -H "Content-Type: application/json" \
  -d '{"urls": ["https://presigned-url..."]}'
```

## Troubleshooting

### Error: "R2 configuration is incomplete"

**Solució:** Verifica que totes les variables d'entorn estiguin configurades:
```bash
# En local
echo $R2_ACCESS_KEY_ID
echo $R2_SECRET_ACCESS_KEY
echo $R2_ENDPOINT
echo $R2_BUCKET_NAME

# A Render, comprova la pestanya Environment
```

### Error 403 Forbidden

**Possible causa:** Credencials incorrectes o bucket no accessible

**Solució:**
1. Verifica les credencials a Cloudflare
2. Comprova que el bucket existeix
3. Assegura't que l'access key té permisos adequats

### URLs prefirmades no funcionen

**Possible causa:** URLs expirades

**Solució:** Regenera les URLs o augmenta el temps d'expiració:
```python
url = service.generate_presigned_url(key, expiration=7200)  # 2 hores
```

### Fitxers no apareixen a Firestore

**Possible causa:** Error d'actualització (però el fitxer està a R2)

**Solució:** Comprova els logs del servidor:
```bash
# A Render
Logs > filtra per "media_keys"
```

## Monitorització

### Logs a Render

Pots veure els logs de pujada/eliminació de fitxers:
1. Ves al Dashboard de Render
2. Selecciona el teu servei
3. Fes clic a **"Logs"**
4. Filtra per:
   - "Fitxer pujat correctament"
   - "Fitxer eliminat correctament"
   - "Error pujant fitxer"

### Mètriques de R2

A Cloudflare Dashboard:
1. Selecciona el bucket
2. Ves a **"Metrics"**
3. Monitoritza:
   - Nombre de fitxers
   - Espai utilitzat
   - Peticions (GET, PUT, DELETE)
   - Transferència de dades

## Seguretat

### Rotació de Credencials

Si necessites canviar les credencials:

1. **Cloudflare:**
   - Genera noves access keys
   - Revoca les antigues

2. **Render:**
   - Actualitza les variables d'entorn
   - Redesplega el servei

3. **Local:**
   - Actualitza `.env.development`
   - Reinicia el servidor

### Límits de Taxa

Cloudflare R2 té límits de taxa. Per producció:
- Implementa retry logic
- Utilitza rate limiting al backend
- Cache d'URLs prefirmades quan sigui possible

## Següents Passos

1. ✅ Variables d'entorn configurades
2. ⬜ Tests d'integració creats
3. ⬜ Frontend integrat amb nous endpoints
4. ⬜ Monitorització configurada
5. ⬜ Backup strategy implementada
6. ⬜ CDN configurat (opcional, per millor performance)

## Recursos Addicionals

- [Documentació R2 de Cloudflare](https://developers.cloudflare.com/r2/)
- [Boto3 Documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)
- [Django REST Framework - File Upload](https://www.django-rest-framework.org/api-guide/parsers/#fileuploadparser)
- [AWS Signature v4](https://docs.aws.amazon.com/general/latest/gr/signature-version-4.html)
