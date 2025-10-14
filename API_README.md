# API de Refugis Lliures - Firestore

## Descripció

Aquesta API gestiona informació sobre refugis lliures utilitzant Google Firestore com a base de dades. L'API està construïda amb Django REST Framework i ofereix endpoints per consultar, cercar i obtenir detalls dels refugis.

## Endpoints Disponibles

### Health Check
- **URL**: `/api/health/`
- **Mètode**: GET
- **Descripció**: Comprova l'estat de l'API i la connexió amb Firestore
- **Resposta**:
  ```json
  {
    "status": "healthy",
    "message": "API is running correctly",
    "firebase": true,
    "firestore": true,
    "collections_count": 1
  }
  ```

### Llistar Refugis
- **URL**: `/api/refugis/`
- **Mètode**: GET
- **Paràmetres de consulta**:
  - `limit` (opcional): Nombre màxim de resultats (defecte: 10, màxim: 100)
- **Descripció**: Retorna una llista paginada de refugis
- **Resposta**:
  ```json
  {
    "count": 2,
    "results": [
      {
        "id": "refugi_id_1",
        "nom": "Nom del refugi",
        "altitude": 2000,
        "comarca": "Comarca",
        "coord": {
          "lat": 42.123,
          "long": 1.456
        }
      }
    ]
  }
  ```

### Detalls d'un Refugi
- **URL**: `/api/refugis/<refugi_id>/`
- **Mètode**: GET
- **Descripció**: Retorna els detalls complets d'un refugi específic
- **Resposta**: Objecte JSON amb tota la informació del refugi

### Cercar Refugis
- **URL**: `/api/refugis/search/`
- **Mètode**: GET
- **Paràmetres de consulta**:
  - `q` (opcional): Text de cerca (busca en el nom del refugi)
  - `comarca` (opcional): Filtrar per comarca
  - `limit` (opcional): Nombre màxim de resultats (defecte: 10, màxim: 100)
- **Descripció**: Cerca refugis amb filtres
- **Resposta**:
  ```json
  {
    "count": 1,
    "results": [...],
    "filters": {
      "query": "text de cerca",
      "comarca": "comarca"
    }
  }
  ```

## Estructura del Projecte

```
api/
├── views/
│   ├── __init__.py
│   └── refugi_views.py          # Vistes per als endpoints de refugis
├── services/
│   ├── __init__.py
│   └── firestore_service.py     # Servei per gestionar Firestore
├── management/
│   └── commands/
│       └── upload_refugis_to_firestore.py  # Comanda per pujar dades
├── utils/
│   └── demo_data_refugis.json   # Dades de prova
├── urls.py                      # Configuració d'URLs
└── tests.py                     # Tests unitaris
```

## Configuració

### Variables d'Entorn

L'aplicació utilitza les següents variables d'entorn configurades a `env/api-keys.env`:

- `SECRET_KEY`: Clau secreta de Django
- `DEBUG`: Mode debug (True/False)
- `ALLOWED_HOSTS`: Hosts permesos
- `CORS_ALLOW_ALL_ORIGINS`: Permetre tots els orígens CORS
- `GOOGLE_APPLICATION_CREDENTIALS`: Ruta al fitxer de credencials Firebase

### Firebase/Firestore

L'aplicació utilitza el fitxer `env/firebase-service-account.json` per autenticar-se amb Firebase. Aquest fitxer conté les credencials del compte de servei de Google Cloud.

## Instal·lació i Execució

### 1. Instal·lar dependències
```bash
pip install -r requirements.txt
```

### 2. Configurar variables d'entorn
Assegura't que tens els fitxers de configuració correctes a la carpeta `env/`.

### 3. Executar migracions
```bash
python manage.py migrate
```

### 4. Pujar dades demo (opcional)
```bash
python manage.py upload_refugis_to_firestore
```

### 5. Iniciar servidor
```bash
python manage.py runserver
```

### 6. Executar tests
```bash
python manage.py test api.tests -v 2
```

## Tests

L'aplicació inclou tests unitaris complets que cobreixen:

- Endpoint de health check
- Llistat de refugis
- Detall de refugi (existeix i no existeix)
- Cerca de refugis
- Resolució d'URLs

Els tests utilitzen mocks per simular la connexió amb Firestore, permetent proves ràpides i fiables sense dependències externes.

## Notes Tècniques

- **Base de dades**: Utilitza exclusivament Firestore, sense models Django
- **Autenticació**: Actualment permet accés anònim (`AllowAny`)
- **Paginació**: Límit de 100 resultats per consulta per evitar sobrecàrrega
- **Logging**: Configurat per registrar errors i activitats importants
- **CORS**: Configurat per permetre peticions des de diferents dominis

## Funcionalitats Implementades

✅ Connexió amb Firestore  
✅ Endpoints RESTful per a refugis  
✅ Sistema de cerca amb filtres  
✅ Gestió d'errors robusta  
✅ Tests unitaris complets  
✅ Logging i monitorització  
✅ Documentació d'API  
✅ Comando per pujar dades  
✅ Configuració per a CORS  

## Següents Passos (Opcional)

- [ ] Implementar autenticació d'usuaris
- [ ] Afegir més filtres de cerca (altitud, tipus, etc.)
- [ ] Implementar cache per millorar rendiment  
- [ ] Afegir endpoints per crear/actualitzar refugis
- [ ] Implementar geolocalització per cerca per proximitat