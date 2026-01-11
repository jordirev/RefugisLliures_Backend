# Sistema de Propostes de Refugis

## Visió General

El sistema de propostes de refugis permet als usuaris autenticats proposar canvis a la base de dades de refugis (crear, actualitzar o eliminar refugis). Els administradors poden revisar aquestes propostes i aprovar-les o rebutjar-les.

## Arquitectura

### Components Principals

```
Views (refuge_proposal_views.py)
    ↓
Controller (refuge_proposal_controller.py)
    ↓
DAO (refuge_proposal_dao.py) + Strategies
    ↓
Firestore Collection: refuges_proposals
```

### Patró Strategy

El sistema implementa el **patró Strategy** per gestionar les diferents accions quan s'aprova una proposta:

- **CreateRefugeStrategy**: Crea un nou refugi a la col·lecció `data_refugis_lliures`
- **UpdateRefugeStrategy**: Actualitza un refugi existent
- **DeleteRefugeStrategy**: Elimina un refugi existent

Aquestes estratègies s'executen només quan un administrador aprova la proposta.

## Endpoints

### 1. POST /refuges-proposals/

**Descripció**: Crea una nova proposta de refugi.

**Autenticació**: Requereix usuari autenticat (token Firebase).

**Body**:
```json
{
  "refuge_id": "abc123",        // null per CREATE, ID del refugi per UPDATE/DELETE
  "action": "create|update|delete",
  "payload": { ... },           // Dades del refugi (requerit per CREATE i UPDATE)
  "comment": "Comentari opcional"  // Opcional
}
```

**Validacions**:
- **CREATE**: 
  - No ha de tenir `refuge_id`, però sí `payload`
  - El `payload` ha de contenir `name` (obligatori) i `coord` (obligatori)
  - El `payload` no pot contenir: `images_metadata`, `visitors`, `id`, `modified_at`
- **UPDATE**: 
  - Ha de tenir `refuge_id` i `payload`
  - El `payload` no pot contenir: `images_metadata`, `visitors`, `id`, `modified_at`
- **DELETE**: 
  - Ha de tenir `refuge_id`, no ha de tenir `payload`

**Camps permesos al payload**:
- `name` (string, obligatori per CREATE)
- `coord` (object {long, lat}, obligatori per CREATE)
- `altitude` (integer, opcional)
- `places` (integer, opcional)
- `remarque` (string, opcional)
- `info_comp` (object, opcional)
- `description` (string, opcional)
- `links` (array of URLs, opcional)
- `type` (string, opcional)
- `region` (string, opcional)
- `departement` (string, opcional)

**Resposta** (201 Created):
```json
{
  "id": "proposta123",
  "refuge_id": null,
  "action": "create",
  "payload": { ... },
  "comment": "Comentari",
  "status": "pending",
  "creator_uid": "user123",
  "created_at": "2025-12-10",
  "reviewer_uid": null,
  "reviewed_at": null,
  "rejection_reason": null
}
```

### 2. GET /refuges-proposals/

**Descripció**: Llista totes les propostes de refugis.

**Autenticació**: Només administradors (custom claim `role: admin`).

**Query Parameters**:
- `status` (opcional): Filtra per status (`pending`, `approved`, `rejected`)

**Resposta** (200 OK):
```json
[
  {
    "id": "proposta123",
    "refuge_id": null,
    "action": "create",
    "payload": { ... },
    "comment": "Comentari",
    "status": "pending",
    "creator_uid": "user123",
    "created_at": "2025-12-10",
    "reviewer_uid": null,
    "reviewed_at": null,
    "rejection_reason": null
  },
  ...
]
```

### 3. POST /refuges-proposals/{id}/approve/

**Descripció**: Aprova una proposta i executa l'acció corresponent.

**Autenticació**: Només administradors.

**Accions executades**:
- **CREATE**: Crea un nou refugi amb les dades del `payload`
- **UPDATE**: Actualitza el refugi especificat amb el `payload`
- **DELETE**: Elimina el refugi especificat

**Resposta** (200 OK):
```json
{
  "message": "Proposal approved successfully"
}
```

**Errors**:
- 404: Proposta no trobada
- 409: La proposta ja ha estat revisada
- 500: Error intern al executar l'acció

### 4. POST /refuges-proposals/{id}/reject/

**Descripció**: Rebutja una proposta sense executar cap acció sobre els refugis.

**Autenticació**: Només administradors.

**Body** (opcional):
```json
{
  "reason": "Raó del rebuig"
}
```

**Resposta** (200 OK):
```json
{
  "message": "Proposal rejected successfully"
}
```

## Model de Dades

### RefugeProposal

```python
@dataclass
class RefugeProposal:
    id: str                       # ID generat per Firestore
    refuge_id: Optional[str]      # None per CREATE, ID del refugi per UPDATE/DELETE
    action: str                   # 'create', 'update', 'delete'
    payload: Optional[Dict]       # Dades del refugi (None per DELETE)
    comment: Optional[str]        # Comentari de l'usuari
    status: str                   # 'pending', 'approved', 'rejected'
    creator_uid: str              # UID de l'usuari creador
    created_at: str               # Data de creació (ISO 8601: YYYY-MM-DD)
    reviewer_uid: Optional[str]   # UID de l'admin revisor
    reviewed_at: Optional[str]    # Data de revisió (ISO 8601: YYYY-MM-DD)
    rejection_reason: Optional[str]  # Raó del rebuig (només per rejected)
```

## Gestió de Cache

El sistema utilitza cache Redis per optimitzar les consultes:

### Timeouts de Cache

- `proposal_detail`: 5 minuts (300 segons)
- `proposal_list`: 3 minuts (180 segons)

### Invalidació de Cache

Quan s'aprova o rebutja una proposta:
- S'invalida `proposal_detail:proposal_id:{id}:*`
- S'invalida `proposal_list:*`

Quan s'aprova una proposta amb èxit (s'executa l'acció):
- S'invaliden les caches relacionades amb refugis:
  - `refugi_detail:*` (per l'ID específic)
  - `refugi_list:*`
  - `refugi_search:*`
  - `refugi_coords:*`

## Flux de Treball

### Creació de Proposta

```
1. Usuari autenticat envia POST /refuges-proposals/
2. Validació dels camps segons l'acció
3. Es guarda la proposta amb status='pending'
4. S'invalida cache de llistes de propostes
5. Es retorna la proposta creada
```

### Aprovació de Proposta

```
1. Admin envia POST /refuges-proposals/{id}/approve/
2. Es verifica que la proposta existeix i està 'pending'
3. Es selecciona l'estratègia segons l'acció:
   - CreateRefugeStrategy: 
     * Crea nou refugi a data_refugis_lliures
     * Afegeix coordenades a coords_refugis
   - UpdateRefugeStrategy: 
     * Actualitza refugi existent a data_refugis_lliures
     * Si payload conté 'coord' o 'name': actualitza coords_refugis
   - DeleteRefugeStrategy: 
     * Elimina refugi de data_refugis_lliures
     * Elimina coordenades de coords_refugis
4. S'executa l'estratègia
5. Si té èxit, s'actualitza la proposta:
   - status='approved'
   - reviewer_uid=UID_admin
   - reviewed_at=data_actual
6. S'invaliden caches de propostes i refugis
7. Es retorna missatge d'èxit
```

### Rebuig de Proposta

```
1. Admin envia POST /refuges-proposals/{id}/reject/
2. Es verifica que la proposta existeix i està 'pending'
3. S'actualitza la proposta:
   - status='rejected'
   - reviewer_uid=UID_admin
   - reviewed_at=data_actual
   - rejection_reason=raó (si es proporciona)
4. S'invaliden caches de propostes
5. No s'executa cap acció sobre refugis
6. Es retorna missatge d'èxit
```

## Permisos

### IsAuthenticated

Utilitzat per:
- POST /refuges-proposals/ (crear proposta)

Permet a qualsevol usuari autenticat crear propostes.

### IsFirebaseAdmin

Utilitzat per:
- GET /refuges-proposals/ (llistar propostes)
- POST /refuges-proposals/{id}/approve/ (aprovar proposta)
- POST /refuges-proposals/{id}/reject/ (rebutjar proposta)

Verifica que l'usuari té el custom claim `role: admin` a Firebase Auth.

## Exemples d'Ús

### Proposar un Nou Refugi

```bash
POST /refuges-proposals/
Authorization: Bearer <firebase_token>
Content-Type: application/json

{
  "action": "create",
  "payload": {
    "name": "Refugi Nou de Prova",
    "coord": {
      "long": 1.234,
      "lat": 42.567
    },
    "altitude": 1800,
    "places": 15,
    "type": "non gardé",
    "info_comp": {
      "cheminee": 1,
      "eau": 1,
      "lits": 1
    }
  },
  "comment": "He descobert aquest refugi durant una excursió"
}
```

### Proposar Actualització d'un Refugi

```bash
POST /refuges-proposals/
Authorization: Bearer <firebase_token>
Content-Type: application/json

{
  "refuge_id": "refugi_colomers",
  "action": "update",
  "payload": {
    "places": 45,
    "remarque": "Capacitat ampliada recentment"
  },
  "comment": "He visitat el refugi aquest mes i han ampliat"
}
```

### Proposar Eliminació d'un Refugi

```bash
POST /refuges-proposals/
Authorization: Bearer <firebase_token>
Content-Type: application/json

{
  "refuge_id": "refugi_antiga",
  "action": "delete",
  "comment": "Aquest refugi ja no existeix, destruït per allau"
}
```

### Aprovar una Proposta (Admin)

```bash
POST /refuges-proposals/proposta123/approve/
Authorization: Bearer <admin_firebase_token>
```

### Rebutjar una Proposta (Admin)

```bash
POST /refuges-proposals/proposta123/reject/
Authorization: Bearer <admin_firebase_token>
Content-Type: application/json

{
  "reason": "Necessitem més evidències abans d'aprovar aquest canvi"
}
```

### Llistar Propostes Pendents (Admin)

```bash
GET /refuges-proposals/?status=pending
Authorization: Bearer <admin_firebase_token>
```

## Exemples d'Errors de Validació

### Error: Camp Prohibit al Payload

```json
// Request
{
  "action": "create",
  "payload": {
    "name": "Refugi Nou",
    "coord": {"long": 1.234, "lat": 42.567},
    "images_metadata": []  // ❌ CAMP PROHIBIT
  }
}

// Response 400
{
  "error": "Invalid data",
  "details": {
    "payload": {
      "images_metadata": ["El camp 'images_metadata' no pot estar present al payload de la proposta"]
    }
  }
}
```

### Error: Falten Camps Obligatoris per CREATE

```json
// Request
{
  "action": "create",
  "payload": {
    "altitude": 1800  // ❌ Falta 'name' i 'coord'
  }
}

// Response 400
{
  "error": "Invalid data",
  "details": {
    "payload": "El camp 'name' és obligatori al payload per a l'acció 'create'"
  }
}
```

### Error: Estructura Incorrecta

```json
// Request
{
  "action": "create",
  "payload": {
    "name": "Refugi Nou",
    "coord": {"longitude": 1.234, "latitude": 42.567},  // ❌ Keys errònies (ha de ser 'long' i 'lat')
  }
}

// Response 400
{
  "error": "Invalid data",
  "details": {
    "payload": {
      "coord": {
        "long": ["This field is required."],
        "lat": ["This field is required."]
      }
    }
  }
}
```

## Errors Comuns

### 400 Bad Request

- Validació fallida (camps obligatoris, tipus incorrectes)
- Filtre de status invàlid
- **Errors del payload**:
  - Camps prohibits presents: `images_metadata`, `visitors`, `id`, `modified_at`
  - Per CREATE: falta `name` o `coord` al payload
  - Estructura incorrecta del payload (tipus de dades invàlids)
  - Camps amb keys errònies que no coincideixen amb l'estructura del refugi

### 401 Unauthorized

- Token d'autenticació absent o invàlid
- UID de l'usuari no trobat

### 403 Forbidden

- L'usuari no és administrador (per endpoints només admins)

### 404 Not Found

- Proposta no trobada
- Refugi no trobat (per UPDATE o DELETE)

### 409 Conflict

- La proposta ja ha estat revisada (approved o rejected)

### 500 Internal Server Error

- Error al executar l'estratègia d'aprovació
- Error de base de dades

## Logging

El sistema registra les següents operacions:

- **DAO_LEVEL (23)**: Operacions de Firestore (READ, WRITE, UPDATE, DELETE)
- **INFO**: Creació, aprovació i rebuig de propostes
- **ERROR**: Errors en operacions

Exemples:
```
[DAO] Firestore WRITE: collection=refuges_proposals document=abc123 (CREATE proposal)
[INFO] Refugi creat amb ID xyz789 des de la proposta abc123
[INFO] Proposta abc123 aprovada per admin_uid_123
[ERROR] Error creant refugi des de proposta abc123: Database connection failed
```

## Gestió de coords_refugis

### Sincronització Automàtica

El sistema manté automàticament sincronitzada la col·lecció `coords_refugis` que conté les coordenades de tots els refugis en un únic document per optimitzar les cerques geogràfiques.

#### Estructura de coords_refugis

```json
{
  "created_at": "timestamp",
  "last_updated": "timestamp",
  "total_refugis": 150,
  "refugis_coordinates": [
    {
      "id": "refugi_123",
      "coord": {
        "lat": 42.567,
        "long": 1.234
      },
      "geohash": "sp4g2",
      "name": "Refugi de Colomers",
      "surname": "Opcional"
    },
    ...
  ]
}
```

#### Operacions per Acció

**CREATE**:
- Afegeix una nova entrada a `refugis_coordinates[]`
- Genera `geohash` amb precisió 5
- Inclou `id`, `coord`, `name` i `surname` (si existeix)
- Actualitza `total_refugis` i `last_updated`

**UPDATE**:
- Només actualitza si el payload conté `coord` o `name`
- Busca el refugi per `id` dins de `refugis_coordinates[]`
- Actualitza només els camps presents al payload
- Regenera `geohash` si `coord` s'actualitza
- Actualitza `last_updated`

**DELETE**:
- Elimina l'entrada corresponent de `refugis_coordinates[]`
- Actualitza `total_refugis` i `last_updated`

### Generació de Geohash

S'utilitza la mateixa funció `generate_simple_geohash()` que a `extract_coords_to_firestore.py` per mantenir consistència:
- Precisió: 5 caràcters
- Base32: "0123456789bcdefghjkmnpqrstuvwxyz"
- Permet queries geogràfiques eficients

## Notes de Desenvolupament

### Estratègia vs. Lògica Directa

El patró Strategy ofereix:
- **Extensibilitat**: Fàcil afegir nous tipus d'accions
- **Separació de Responsabilitats**: Cada acció té la seva pròpia classe
- **Testabilitat**: Les estratègies es poden testar independentment
- **Mantenibilitat**: Codi més net i organitzat
- **Sincronització**: Gestió automàtica de coords_refugis en cada estratègia

### Zona Horària

S'utilitza `get_madrid_today()` de `timezone_utils` per garantir dates consistents en zona horària de Madrid (Europe/Madrid).

### Col·lecció Firestore

- Nom: `refuges_proposals`
- Sense índexs composats requerits (queries simples)
- Ordenació per defecte: `created_at` descendent

### Cache Strategy

Les propostes s'invaliden de manera proactiva:
- Quan es crea una proposta nova
- Quan s'aprova o rebutja una proposta
- Les caches de refugis s'invaliden només quan s'executa amb èxit una acció

## Testing

Per testar els endpoints:

1. **Crear proposta (autenticat)**:
   - Verificar validacions per cada tipus d'acció
   - Verificar creació correcta amb status='pending'

2. **Llistar propostes (admin)**:
   - Verificar filtre per status
   - Verificar ordre per created_at

3. **Aprovar proposta (admin)**:
   - Verificar execució de cada estratègia
   - Verificar canvi d'estat a 'approved'
   - Verificar invalidació de cache

4. **Rebutjar proposta (admin)**:
   - Verificar canvi d'estat a 'rejected'
   - Verificar raó del rebuig (opcional)
   - Verificar que no s'executa cap acció sobre refugis

## Configuració

Afegir a `.env.development` o `.env.production`:

```bash
# Cache timeouts per propostes (en segons)
CACHE_TIMEOUT_PROPOSAL_DETAIL=300   # 5 minuts
CACHE_TIMEOUT_PROPOSAL_LIST=180     # 3 minuts
```
