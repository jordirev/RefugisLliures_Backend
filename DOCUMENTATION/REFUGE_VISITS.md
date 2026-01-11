# Sistema de Visites a Refugis - Documentació

## Descripció General

Aquest sistema permet als usuaris registrar i gestionar visites programades als refugis. Les visites es processen automàticament cada dia a les 3:00 AM, afegint els visitants a la llista permanent del refugi.

## Endpoints Implementats

### 1. GET `/refuges/{id}/visits/`
Obté totes les visites actuals i futures d'un refugi (date >= avui), ordenades ascendentment.

**Autenticació:** Requerida

**Resposta:**
```json
{
  "result": [
    {
      "date": "2025-07-18",
      "total_visitors": 12,
      "is_visitor": true,
      "num_visitors": 2
    }
  ]
}
```

**Camps de resposta:**
- `date`: Data de la visita
- `total_visitors`: Nombre total de visitants registrats
- `is_visitor`: Boolean que indica si l'usuari autenticat està registrat a aquesta visita
- `num_visitors`: Nombre de visitants que l'usuari autenticat ha registrat (0 si is_visitor és false)

### 2. GET `/users/{uid}/visits/`
Obté totes les visites d'un usuari, ordenades descendentment per data.

**Autenticació:** Requerida + IsSameUser

**Resposta:**
```json
{
  "result": [
    {
      "date": "2025-07-18",
      "refuge_id": "refuge123",
      "total_visitors": 12,
      "is_visitor": true,
      "num_visitors": 2
    }
  ]
}
```

**Camps de resposta:**
- `date`: Data de la visita
- `refuge_id`: ID del refugi
- `total_visitors`: Nombre total de visitants registrats
- `is_visitor`: Sempre true (ja que és la llista de visites de l'usuari)
- `num_visitors`: Nombre de visitants que l'usuari ha registrat

### 3. POST `/refuges/{id}/visits/{date}`
Crea una visita o afegeix un visitant a una visita existent.

**Autenticació:** Requerida

**Body:**
```json
{
  "num_visitors": 2
}
```

**Resposta:**
```json
{
  "message": "Visita creada correctament",
  "visit": {
    "date": "2025-07-18",
    "total_visitors": 2,
    "is_visitor": true,
    "num_visitors": 2
  }
}
```

### 4. PATCH `/refuges/{id}/visits/{date}`
Actualitza el nombre de visitants d'un usuari en una visita.

**Autenticació:** Requerida

**Body:**
```json
{
  "num_visitors": 3
}
```

**Resposta:**
```json
{
  "message": "Visita actualitzada correctament",
  "visit": {
    "date": "2025-07-18",
    "total_visitors": 3,
    "is_visitor": true,
    "num_visitors": 3
  }
}
```

### 5. DELETE `/refuges/{id}/visits/{date}`
Elimina un visitant d'una visita.

**Autenticació:** Requerida

**Resposta:**
```json
{
  "message": "Visitant eliminat correctament"
}
```

## Nota Important sobre Privacitat

**Per privacitat i seguretat**, les respostes HTTP **NO** retornen la llista completa de visitants amb els seus UIDs. En el seu lloc, cada resposta només inclou:
- `is_visitor`: Boolean que indica si l'usuari autenticat està registrat a la visita
- `num_visitors`: Nombre de persones que l'usuari autenticat ha registrat (només si is_visitor és true)
- `total_visitors`: Nombre total de visitants de tots els usuaris registrats

Això garanteix que cap usuari pugui veure els UIDs d'altres usuaris que han registrat visites.

## Estructura de Dades

### Model RefugeVisit
```python
@dataclass
class RefugeVisit:
    date: str              # Format ISO 8601: YYYY-MM-DD
    refuge_id: str         # ID del refugi
    visitors: list[UserVisit]  # Llista de visitants
    total_visitors: int    # Nombre total de visitants
```

### Model UserVisit
```python
@dataclass
class UserVisit:
    uid: str              # UID de l'usuari
    num_visitors: int     # Nombre de persones que visitaran
```

## Col·lecció Firestore

**Nom:** `refuge_visits`

**Estructura del document:**
- ID: Generat automàticament per Firestore
- Camps:
  - `date` (string): Data de la visita (YYYY-MM-DD)
  - `refuge_id` (string): ID del refugi
  - `visitors` (array): Llista d'objectes {uid, num_visitors}
  - `total_visitors` (number): Total de visitants

**Nota:** `date` i `refuge_id` NO es poden editar un cop assignats.

## Sistema de Cache

El DAO utilitza el servei de cache per optimitzar les consultes:
- **Cache de detall:** `refuge_visit_detail:visit_id={id}`
- **Cache de llista:** `refuge_visits_list:refuge_id={id}:from_date={date}`
- La cache s'invalida automàticament en operacions d'escriptura

## Cron Job - Processament de Visites

### Què fa?
Cada dia a les **3:00 AM** (hora de Madrid), el sistema:
1. Obté totes les visites amb data = ahir
2. Per cada visita:
   - Si té visitants: afegeix els UIDs a la llista `visitors` del refugi
   - Si està buida (total_visitors=0 i visitors=[]): elimina el document
   - Si té visitants: manté el document per a l'historial

### Configuració del Cron Job

#### 1. Instal·lar Django-crontab
El paquet ja està afegit a `requirements.txt`:
```bash
pip install -r requirements.txt
```

#### 2. Configuració a settings.py
Ja està configurat:
```python
INSTALLED_APPS = [
    ...
    'django_crontab',
    ...
]

CRONJOBS = [
    ('0 3 * * *', 'django.core.management.call_command', ['process_yesterday_visits'], {'verbosity': 1}),
]
```

#### 3. Afegir el cron job al sistema
```bash
python manage.py crontab add
```

#### 4. Comandes útils
- **Llistar cron jobs:** `python manage.py crontab show`
- **Eliminar cron jobs:** `python manage.py crontab remove`
- **Executar manualment:** `python manage.py process_yesterday_visits`

### Logs del Cron Job
El cron job genera estadístiques:
```
Visites processades: 5
Visites buides eliminades: 1
Refugis actualitzats: 4
Total visitants afegits: 12
```

## Implementació Completa

### Fitxers Creats/Modificats

1. **Model:** `api/models/refuge_visit.py` (ja existent)
2. **Mapper:** `api/mappers/refuge_visit_mapper.py`
3. **Serializers:** `api/serializers/refuge_visit_serializer.py`
4. **DAO:** `api/daos/refuge_visit_dao.py`
5. **Controller:** `api/controllers/refuge_visit_controller.py`
6. **Views:** `api/views/refuge_visit_views.py`
7. **URLs:** `api/urls.py` (modificat)
8. **Management Command:** `api/management/commands/process_yesterday_visits.py`
9. **Settings:** `refugis_lliures/settings.py` (afegit django-crontab i CRONJOBS)
10. **Requirements:** `requirements.txt` (afegit django-crontab)
11. **DAO Refugi:** `api/daos/refugi_lliure_dao.py` (afegit `update_refugi_visitors`)

## Exemples d'Ús

### Crear una visita
```bash
curl -X POST http://localhost:8000/api/refuges/ABC123/visits/2025-07-18/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"num_visitors": 2}'
```

### Actualitzar una visita
```bash
curl -X PATCH http://localhost:8000/api/refuges/ABC123/visits/2025-07-18/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"num_visitors": 3}'
```

### Eliminar-se d'una visita
```bash
curl -X DELETE http://localhost:8000/api/refuges/ABC123/visits/2025-07-18/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Veure visites d'un refugi
```bash
curl http://localhost:8000/api/refuges/ABC123/visits/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Veure les meves visites
```bash
curl http://localhost:8000/api/users/MY_UID/visits/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Validacions

- La data de visita ha de ser igual o posterior a avui
- No es pot registrar dues vegades a la mateixa visita
- No es poden editar `date` ni `refuge_id` un cop creats
- El refugi ha d'existir per crear una visita
- `num_visitors` ha de ser >= 1

## Notes Importants

- Les visites passades NO s'obtenen amb GET `/refuges/{id}/visits/`
- El cron job processa visites exactament d'ahir (no de dies anteriors)
- Els UIDs NO es duplicaran a la llista de visitors del refugi
- El document de visita NO s'elimina automàticament després de la data (només si està buit)
