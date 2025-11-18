# API d'Usuaris - RefugisLliures Backend

## Arquitectura Creada

S'ha creat una arquitectura completa per a la gestió d'usuaris que inclou:

### 📁 Estructura de Directoris

```
api/
├── daos/
│   ├── __init__.py
│   └── user_dao.py              # Data Access Object per Firebase
├── mappers/
│   ├── __init__.py
│   └── user_mapper.py           # Transformació de dades
├── models/
│   ├── __init__.py
│   └── user.py                  # Model d'usuari (dataclass)
├── controllers/
│   ├── __init__.py
│   └── user_controller.py       # Lògica de negoci
├── serializers/
│   ├── __init__.py
│   └── user_serializer.py       # Serialització REST API
└── views/
    └── user_views.py            # Views Django REST Framework
```

### 🏗️ Components

#### 1. **Model d'Usuari** (`api/models/user.py`)
- **Atributs**: `uid`, `username`, `email`, `avatar`
- Implementat amb `@dataclass` per simplicitat
- Validacions bàsiques incloses

#### 2. **UserDAO** (`api/daos/user_dao.py`)
- **Operacions Firebase**:
  - `create_user()`: Crea nou usuari
  - `get_user_by_uid()`: Obté usuari per UID
  - `get_user_by_email()`: Obté usuari per email
  - `update_user()`: Actualitza usuari
  - `delete_user()`: Elimina usuari
  - `list_users()`: Llista amb paginació
  - `user_exists()`: Comprova existència

#### 3. **UserMapper** (`api/mappers/user_mapper.py`)
- Transformació entre formats Firebase ↔ Django
- Neteja i validació de dades
- Mètodes de conversió bidireccionals

#### 4. **UserController** (`api/controllers/user_controller.py`)
- **Lògica de negoci**:
  - Validacions complexes
  - Gestió d'errors
  - Coordinació entre DAO i Mapper
  - Retorn consistent: `(success, data/None, error_message)`

#### 5. **Serializers** (`api/serializers/user_serializer.py`)
- `UserSerializer`: Serialització general
- `UserCreateSerializer`: Validació creació
- `UserUpdateSerializer`: Validació actualització
- `PaginationQuerySerializer`: Paràmetres paginació

#### 6. **Views** (`api/views/user_views.py`)
- Implementació Django REST Framework
- Documentació Swagger/OpenAPI automàtica
- Gestió d'errors HTTP consistent

### 🔗 Endpoints API (REST Estàndard)

| Mètode | URL | Descripció |
|--------|-----|------------|
| `GET` | `/api/users/` | Llistar usuaris (paginació) |
| `POST` | `/api/users/` | Crear usuari nou |
| `GET` | `/api/users/{uid}/` | Obtenir usuari per UID |
| `PUT` | `/api/users/{uid}/` | Actualitzar usuari |
| `DELETE` | `/api/users/{uid}/` | Eliminar usuari |
| `GET` | `/api/users/search/?email={email}` | Cercar per email |

### 📋 Exemples d'Ús

#### Crear Usuari
```bash
POST /api/users/
Content-Type: application/json

{
    "uid": "user123",
    "username": "joan_doe",
    "email": "joan@example.com",
    "avatar": "https://example.com/avatar.jpg"
}
```

#### Actualitzar Usuari
```bash
PUT /api/users/user123/
Content-Type: application/json

{
    "username": "nou_nom",
    "avatar": "https://example.com/nou_avatar.jpg"
}
```

#### Llistar Usuaris amb Paginació
```bash
GET /api/users/?limit=10&offset=0
```

#### Cercar per Email
```bash
GET /api/users/search/?email=joan@example.com
```

### ✅ Característiques

- **🔥 Firebase Integration**: Utilitza Firestore com a base de dades
- **📊 Paginació**: Suport per llistat paginat d'usuaris
- **✨ Validacions**: Validacions a múltiples nivells (model, serializer, controller)
- **🔍 Cerca**: Cerca per UID i email
- **📚 Documentació**: Swagger/OpenAPI automàtic
- **🛡️ Gestió d'Errors**: Gestió consistent d'errors i logging
- **🔄 CRUD Complet**: Create, Read, Update, Delete
- **🧹 Neteja de Dades**: Normalització i sanitització automàtica

### 🚀 Estat del Servidor

✅ **Servidor Django funcionant correctament**  
🌐 **Disponible a**: http://127.0.0.1:8000/  
📖 **Documentació API**: http://127.0.0.1:8000/swagger/

### 📝 Notes Tècniques

1. **Firebase**: Utilitza el servei `FirestoreService` existent
2. **Consistència**: Segueix els patrons establerts al projecte
3. **Logging**: Logging detallat per debugging
4. **Arquitectura Hexagonal**: Separació clara de responsabilitats
5. **Extensible**: Fàcil d'estendre per funcionalitats addicionals