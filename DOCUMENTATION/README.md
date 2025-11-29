# RefugisLliures_Backend

Backend API for RefugisLliures project built with Django and Django REST Framework.

## Prerequisites

- Python 3.8 or higher
- pip (Python package installer)
- Virtual environment (recommended)

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/jordirev/RefugisLliures_Backend.git
cd RefugisLliures_Backend
```

### 2. Create and activate a virtual environment

**On Linux/macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**On Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables (optional)

Copy the example environment file and modify as needed:

```bash
cp .env.example .env
```

Edit `.env` file to set your configuration:
- `SECRET_KEY`: Django secret key (generate a new one for production)
- `DEBUG`: Set to False in production
- `ALLOWED_HOSTS`: Comma-separated list of allowed hosts
- `CORS_ALLOW_ALL_ORIGINS`: Set to False in production
- `CORS_ALLOWED_ORIGINS`: Comma-separated list of allowed origins

### 5. Run database migrations

```bash
python manage.py migrate
```

### 6. Create a superuser (optional)

```bash
python manage.py createsuperuser
```

### 7. Run the development server

```bash
python manage.py runserver
```

The API will be available at `http://127.0.0.1:8000/`

## API Endpoints

- `GET /api/health/` - Health check endpoint
- `GET /admin/` - Django admin panel

## Documentació Addicional

- **[CUSTOM_CLAIMS.md](CUSTOM_CLAIMS.md)** - Sistema de rols i permisos amb Custom Claims de Firebase Auth
- **[CACHE_ADMIN_ENDPOINTS.md](CACHE_ADMIN_ENDPOINTS.md)** - Endpoints d'administració de cache Redis
- **[FIREBASE_AUTH.md](FIREBASE_AUTH.md)** - Autenticació amb Firebase
- **[FIREBASE_CONFIG.md](FIREBASE_CONFIG.md)** - Configuració de Firebase
- **[TESTING_GUIDE.md](TESTING_GUIDE.md)** - Guia de testing
- **[GUIA_RAPIDA.md](GUIA_RAPIDA.md)** - Guia ràpida d'ús
- **[REFUGI_ARCHITECTURE.md](REFUGI_ARCHITECTURE.md)** - Arquitectura dels refugis
- **[USER_ARCHITECTURE.md](USER_ARCHITECTURE.md)** - Arquitectura d'usuaris
- **[RENOVATIONS.md](RENOVATIONS.md)** - Sistema de renovacions

## Project Structure

```
RefugisLliures_Backend/
├── api/                    # Main API application
│   ├── views.py           # API views
│   ├── urls.py            # API URL patterns
│   └── ...
├── refugis_lliures/       # Django project settings
│   ├── settings.py        # Project settings
│   ├── urls.py            # Main URL configuration
│   └── ...
├── manage.py              # Django management script
├── requirements.txt       # Python dependencies
├── .env.example          # Example environment variables
└── README.md             # This file
```

## Technologies Used

- **Django 5.1.12**: High-level Python web framework
- **Django REST Framework 3.15.2**: Powerful toolkit for building Web APIs
- **django-cors-headers 4.4.0**: Handle Cross-Origin Resource Sharing (CORS)
- **python-decouple 3.8**: Strict separation of settings from code

## Development

### Running tests

```bash
python manage.py test
```

### Creating a new app

```bash
python manage.py startapp <app_name>
```

Don't forget to add the new app to `INSTALLED_APPS` in `settings.py`.

### Making database changes

1. Modify your models
2. Create migrations: `python manage.py makemigrations`
3. Apply migrations: `python manage.py migrate`

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License.

