"""
Respostes d'error reutilitzables per a la documentació Swagger/OpenAPI
Aquestes respostes reflecteixen el format real que retornen els endpoints en cas d'error
"""
from drf_yasg import openapi


# ========== SCHEMAS REUTILITZABLES PER A ERRORS ==========

# Schema bàsic d'error amb un sol camp "error"
ERROR_SCHEMA_SIMPLE = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        'error': openapi.Schema(type=openapi.TYPE_STRING, description="Missatge d'error")
    },
    required=['error']
)

# Schema d'error 401 amb error i message
ERROR_SCHEMA_401 = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        'error': openapi.Schema(type=openapi.TYPE_STRING, description="Missatge d'error"),
        'message': openapi.Schema(type=openapi.TYPE_STRING, description="Detall del problema d'autenticació")
    },
    required=['error', 'message']
)

# Schema d'error amb detalls de validació
ERROR_SCHEMA_WITH_DETAILS = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        'error': openapi.Schema(type=openapi.TYPE_STRING, description="Missatge d'error general"),
        'details': openapi.Schema(
            type=openapi.TYPE_OBJECT,
            description="Detalls específics dels errors de validació per camp",
            additional_properties=openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Schema(type=openapi.TYPE_STRING)
            )
        )
    },
    required=['error']
)

# Schema d'error amb camp "detail" addicional
ERROR_SCHEMA_WITH_DETAIL = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        'error': openapi.Schema(type=openapi.TYPE_STRING, description="Missatge d'error"),
        'detail': openapi.Schema(type=openapi.TYPE_STRING, description="Informació tècnica addicional")
    },
    required=['error']
)

# Schema per a error 409 amb renovation solapada
ERROR_SCHEMA_OVERLAP = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        'error': openapi.Schema(type=openapi.TYPE_STRING, description="Missatge d'error"),
        'overlapping_renovation': openapi.Schema(
            type=openapi.TYPE_OBJECT,
            description="Informació de la renovation que solapa",
            properties={
                'id': openapi.Schema(type=openapi.TYPE_STRING),
                'creator_uid': openapi.Schema(type=openapi.TYPE_STRING),
                'refuge_id': openapi.Schema(type=openapi.TYPE_STRING),
                'ini_date': openapi.Schema(type=openapi.TYPE_STRING, format='date'),
                'fin_date': openapi.Schema(type=openapi.TYPE_STRING, format='date'),
                'description': openapi.Schema(type=openapi.TYPE_STRING),
                'materials_needed': openapi.Schema(type=openapi.TYPE_STRING),
                'group_link': openapi.Schema(type=openapi.TYPE_STRING, format='uri'),
                'participants_uids': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(type=openapi.TYPE_STRING)
                )
            }
        )
    },
    required=['error', 'overlapping_renovation']
)

# Schema per a health check unhealthy
ERROR_SCHEMA_HEALTH = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        'status': openapi.Schema(type=openapi.TYPE_STRING, enum=['healthy', 'unhealthy']),
        'message': openapi.Schema(type=openapi.TYPE_STRING),
        'firebase': openapi.Schema(type=openapi.TYPE_BOOLEAN)
    },
    required=['status', 'firebase']
)


# ========== ERRORS GENERALS ==========

ERROR_400_INVALID_DATA = openapi.Response(
    description="Dades invàlides",
    schema=ERROR_SCHEMA_WITH_DETAILS,
    examples={
        "application/json": {
            "error": "Dades invàlides",
            "details": {
                "language": ["Idioma no vàlid. Opcions vàlides: ca, es, en, fr"]
            }
        }
    }
)

ERROR_400_INVALID_PARAMS = openapi.Response(
    description="Paràmetres de consulta invàlids",
    schema=ERROR_SCHEMA_WITH_DETAILS,
    examples={
        "application/json": {
            "error": "Invalid query parameters",
            "details": {
                "altitude_min": ["altitude_min ha de ser un enter positiu"],
                "places_max": ["places_max ha de ser menor o igual que places_min"]
            }
        }
    }
)

ERROR_400_MISSING_ID = openapi.Response(
    description="ID requerit",
    schema=ERROR_SCHEMA_SIMPLE,
    examples={
        "application/json": {
            "error": "ID de renovation requerit"
        }
    }
)

ERROR_400_MISSING_PATTERN = openapi.Response(
    description="Patró no proporcionat",
    schema=ERROR_SCHEMA_SIMPLE,
    examples={
        "application/json": {
            "error": "Patró no proporcionat"
        }
    }
)

ERROR_400_ALREADY_EXISTS = openapi.Response(
    description="El recurs ja existeix",
    schema=ERROR_SCHEMA_SIMPLE,
    examples={
        "application/json": {
            "error": "El refugi ja és als preferits de l'usuari"
        }
    }
)

ERROR_400_ALREADY_PARTICIPANT = openapi.Response(
    description="L'usuari ja és participant d'aquesta renovation",
    schema=ERROR_SCHEMA_SIMPLE,
    examples={
        "application/json": {
            "error": "L'usuari ja és participant d'aquesta renovation"
        }
    }
)

ERROR_400_CREATOR_CANNOT_JOIN = openapi.Response(
    description="El creador no pot unir-se com a participant",
    schema=ERROR_SCHEMA_SIMPLE,
    examples={
        "application/json": {
            "error": "El creador no pot unir-se a la seva pròpia renovation"
        }
    }
)

ERROR_403_EXPELLED = openapi.Response(
    description="Usuari expulsat - No pot tornar a unir-se",
    schema=ERROR_SCHEMA_SIMPLE,
    examples={
        "application/json": {
            "error": "Aquest usuari ha estat expulsat d'aquesta renovation i no pot tornar a unir-se"
        }
    }
)

ERROR_401_UNAUTHORIZED = openapi.Response(
    description="No autenticat - Token d'autenticació invàlid o absent",
    schema=ERROR_SCHEMA_401,
    examples={
        "application/json": {
            "error": "No autenticat",
            "message": "Token d'autenticació no proporcionat"
        }
    }
)

ERROR_403_FORBIDDEN = openapi.Response(
    description="Permís denegat",
    schema=ERROR_SCHEMA_SIMPLE,
    examples={
        "application/json": {
            "error": "No tens permís per realitzar aquesta acció"
        }
    }
)

ERROR_403_NOT_CREATOR = openapi.Response(
    description="Només el creador pot realitzar aquesta acció",
    schema=ERROR_SCHEMA_SIMPLE,
    examples={
        "application/json": {
            "error": "Només el creador pot editar aquesta renovation"
        }
    }
)

ERROR_403_ADMIN_ONLY = openapi.Response(
    description="Només administradors",
    schema=ERROR_SCHEMA_SIMPLE,
    examples={
        "application/json": {
            "error": "Permís denegat - només administradors"
        }
    }
)

ERROR_404_USER_NOT_FOUND = openapi.Response(
    description="Usuari no trobat",
    schema=ERROR_SCHEMA_SIMPLE,
    examples={
        "application/json": {
            "error": "Usuari no trobat"
        }
    }
)

ERROR_404_REFUGI_NOT_FOUND = openapi.Response(
    description="Refugi no trobat",
    schema=ERROR_SCHEMA_SIMPLE,
    examples={
        "application/json": {
            "error": "Refugi not found"
        }
    }
)

ERROR_404_RENOVATION_NOT_FOUND = openapi.Response(
    description="Renovation no trobada",
    schema=ERROR_SCHEMA_SIMPLE,
    examples={
        "application/json": {
            "error": "Renovation no trobada"
        }
    }
)

ERROR_404_USER_OR_REFUGI = openapi.Response(
    description="Usuari o refugi no trobat",
    schema=ERROR_SCHEMA_SIMPLE,
    examples={
        "application/json": {
            "error": "Refugi no trobat"
        }
    }
)

ERROR_404_DOUBT_NOT_FOUND = openapi.Response(
    description="Dubte no trobat",
    schema=ERROR_SCHEMA_SIMPLE,
    examples={
        "application/json": {
            "error": "Dubte no trobat"
        }
    }
)

ERROR_404_ANSWER_NOT_FOUND = openapi.Response(
    description="Resposta no trobada",
    schema=ERROR_SCHEMA_SIMPLE,
    examples={
        "application/json": {
            "error": "Resposta no trobada"
        }
    }
)

ERROR_409_USER_EXISTS = openapi.Response(
    description="L'usuari ja existeix",
    schema=ERROR_SCHEMA_SIMPLE,
    examples={
        "application/json": {
            "error": "L'usuari ja existeix"
        }
    }
)

ERROR_409_OVERLAP = openapi.Response(
    description="Solapament temporal amb altra renovation",
    schema=ERROR_SCHEMA_OVERLAP,
    examples={
        "application/json": {
            "error": "Hi ha un solapament temporal amb una altra renovation del mateix refugi",
            "overlapping_renovation": {
                "id": "renovation_1",
                "creator_uid": "uid_abc123",
                "refuge_id": "refugi_colomers",
                "ini_date": "2025-12-15",
                "fin_date": "2025-12-20",
                "description": "Reparació del sostre i millora de l'aïllament",
                "materials_needed": "Teules, aïllant tèrmic, cargols",
                "group_link": "https://wa.me/group/abc123",
                "participants_uids": ["uid_def456", "uid_ghi789"]
            }
        }
    }
)

ERROR_500_INTERNAL_ERROR = openapi.Response(
    description="Error intern del servidor",
    schema=ERROR_SCHEMA_SIMPLE,
    examples={
        "application/json": {
            "error": "Error intern del servidor"
        }
    }
)

ERROR_500_CACHE_ERROR = openapi.Response(
    description="Error de cache",
    schema=ERROR_SCHEMA_WITH_DETAIL,
    examples={
        "application/json": {
            "error": "Error netejant la cache",
            "detail": "Connection refused"
        }
    }
)

ERROR_503_SERVICE_UNAVAILABLE = openapi.Response(
    description="Servei no disponible",
    schema=ERROR_SCHEMA_HEALTH,
    examples={
        "application/json": {
            "status": "unhealthy",
            "message": "Error connecting to Firebase",
            "firebase": False
        }
    }
)

# ========== RESPOSTES D'ÈXIT ESPECIALS ==========

SUCCESS_204_NO_CONTENT = openapi.Response(
    description="Recurs eliminat correctament"
)

SUCCESS_200_CACHE_CLEARED = openapi.Response(
    description="Cache netejada correctament",
    schema=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'message': openapi.Schema(type=openapi.TYPE_STRING)
        }
    ),
    examples={
        "application/json": {
            "message": "Cache netejada correctament"
        }
    }
)

SUCCESS_200_CACHE_INVALIDATED = openapi.Response(
    description="Claus eliminades correctament",
    schema=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'message': openapi.Schema(type=openapi.TYPE_STRING)
        }
    ),
    examples={
        "application/json": {
            "message": "Claus amb patró \"refugi_*\" eliminades correctament"
        }
    }
)

# ========== ERRORS ESPECÍFICS DE MITJANS ==========

ERROR_400_INVALID_FILE_TYPE = openapi.Response(
    description="Tipus de fitxer no permès",
    schema=ERROR_SCHEMA_SIMPLE,
    examples={
        "application/json": {
            "error": "Content type 'application/pdf' no permès. Tipus permesos: ['image/jpeg', 'image/jpg', 'image/png', 'image/webp', 'image/heic', 'image/heif']"
        }
    }
)

ERROR_400_NO_FILES = openapi.Response(
    description="No s'han proporcionat fitxers",
    schema=ERROR_SCHEMA_SIMPLE,
    examples={
        "application/json": {
            "error": "No s'han proporcionat fitxers"
        }
    }
)

ERROR_404_MEDIA_NOT_FOUND = openapi.Response(
    description="Mitjà no trobat",
    schema=ERROR_SCHEMA_SIMPLE,
    examples={
        "application/json": {
            "error": "Mitjà no trobat"
        }
    }
)

ERROR_404_AVATAR_NOT_FOUND = openapi.Response(
    description="Avatar no trobat",
    schema=ERROR_SCHEMA_SIMPLE,
    examples={
        "application/json": {
            "error": "L'usuari no té cap avatar"
        }
    }
)

ERROR_403_NOT_MEDIA_OWNER = openapi.Response(
    description="No tens permís per eliminar aquest mitjà",
    schema=ERROR_SCHEMA_SIMPLE,
    examples={
        "application/json": {
            "error": "No tens permís per eliminar aquest mitjà"
        }
    }
)

# ========== ERRORS ESPECÍFICS PER PROPOSTES DE REFUGIS ==========

ERROR_404_PROPOSAL_NOT_FOUND = openapi.Response(
    description='Proposta no trobada',
    schema=ERROR_SCHEMA_SIMPLE,
    examples={
        'application/json': {
            'error': 'Proposal not found'
        }
    }
)

ERROR_409_PROPOSAL_ALREADY_REVIEWED = openapi.Response(
    description='La proposta ja ha estat revisada',
    schema=ERROR_SCHEMA_SIMPLE,
    examples={
        'application/json': {
            'error': 'Proposal is already approved'
        }
    }
)
