"""
Exemples reutilitzables per a la documentació Swagger/OpenAPI
"""

# ========== EXEMPLES D'USUARIS ==========

EXAMPLE_USER_BASIC = {
    'uid': 'uid_123abc',
    'username': 'joan_muntanyenc',
    'avatar': 'https://example.com/avatar.jpg',
    'language': 'ca',
    'favourite_refuges': [],
    'visited_refuges': [],
    'num_uploaded_photos': 0,
    'num_shared_experiences': 0,
    'num_renovated_refuges': 0,
    'created_at': '2025-11-29T10:30:00Z'
}

EXAMPLE_USER_WITH_DATA = {
    'uid': 'uid_456def',
    'username': 'joan_muntanyenc',
    'avatar': 'https://example.com/avatar.jpg',
    'language': 'ca',
    'favourite_refuges': ['refugi_1', 'refugi_2'],
    'visited_refuges': ['refugi_1', 'refugi_3'],
    'num_uploaded_photos': 15,
    'num_shared_experiences': 8,
    'num_renovated_refuges': 2,
    'created_at': '2024-06-15T09:20:00Z'
}

EXAMPLE_USER_UPDATED = {
    'uid': 'uid_789ghi',
    'username': 'joan_muntanyenc_updated',
    'avatar': 'https://example.com/new_avatar.jpg',
    'language': 'es',
    'favourite_refuges': ['refugi_1', 'refugi_2'],
    'visited_refuges': ['refugi_1', 'refugi_3'],
    'num_uploaded_photos': 15,
    'num_shared_experiences': 8,
    'num_renovated_refuges': 2,
    'created_at': '2024-06-15T09:20:00Z'
}

# ========== EXEMPLES DE REFUGIS ==========

EXAMPLE_REFUGI_COLOMERS = {
    'id': 'refugi_colomers',
    'name': 'Refugi de Colomers',
    'coord': {
        'long': 0.9833,
        'lat': 42.6667
    },
    'altitude': 2135,
    'places': 40,
    'remarque': 'Refugi guardat a la Vall d\'Aran',
    'info_comp': {
        'manque_un_mur': 0,
        'cheminee': 1,
        'poele': 1,
        'couvertures': 1,
        'latrines': 1,
        'bois': 1,
        'eau': 1,
        'matelas': 1,
        'couchage': 1,
        'bas_flancs': 0,
        'lits': 1,
        'mezzanine_etage': 1
    },
    'description': 'Refugi molt ben equipat amb vistes espectaculars',
    'links': ['https://www.feec.cat/refugis/colomers'],
    'type': 'non gardé',
    'modified_at': '2025-11-15T14:30:00Z',
    'region': 'Val d\'Aran',
    'departement': 'Lleida',
    'condition': 3
}

EXAMPLE_REFUGI_COLOMERS_DETAILED = {
    'id': 'refugi_colomers',
    'name': 'Refugi de Colomers',
    'coord': {
        'long': 0.9833,
        'lat': 42.6667
    },
    'altitude': 2135,
    'places': 40,
    'remarque': 'Refugi guardat a la Vall d\'Aran',
    'info_comp': {
        'manque_un_mur': 0,
        'cheminee': 1,
        'poele': 1,
        'couvertures': 1,
        'latrines': 1,
        'bois': 1,
        'eau': 1,
        'matelas': 1,
        'couchage': 1,
        'bas_flancs': 0,
        'lits': 1,
        'mezzanine_etage': 1
    },
    'description': 'Refugi molt ben equipat amb vistes espectaculars als Estanys de Colomers. Ideal per a excursions familiars i de diversos dies.',
    'links': [
        'https://www.feec.cat/refugis/colomers',
        'https://www.camptocamp.org/waypoints/123456'
    ],
    'type': 'non gardé',
    'modified_at': '2025-11-15T14:30:00Z',
    'region': 'Val d\'Aran',
    'departement': 'Lleida',
    'condition': 3
}

EXAMPLE_REFUGI_RESTANCA = {
    'id': 'refugi_restanca',
    'name': 'Refugi de Restanca',
    'coord': {
        'long': 0.8167,
        'lat': 42.6500
    },
    'altitude': 2010,
    'places': 36,
    'remarque': '',
    'info_comp': {
        'manque_un_mur': 0,
        'cheminee': 1,
        'poele': 0,
        'couvertures': 1,
        'latrines': 1,
        'bois': 0,
        'eau': 1,
        'matelas': 0,
        'couchage': 1,
        'bas_flancs': 1,
        'lits': 0,
        'mezzanine_etage': 0
    },
    'description': 'Refugi situat prop del llac de Restanca',
    'links': [],
    'type': 'non gardé',
    'modified_at': '2025-10-20T10:15:00Z',
    'region': 'Val d\'Aran',
    'departement': 'Lleida',
    'condition': 2
}

EXAMPLE_REFUGI_INFO_COLOMERS = {
    'id': 'refugi_1',
    'name': 'Refugi de Colomers',
    'region': 'Val d\'Aran',
    'places': 40,
    'coord': {
        'long': 0.9833,
        'lat': 42.6667
    }
}

EXAMPLE_REFUGI_INFO_VENTOSA = {
    'id': 'refugi_2',
    'name': 'Refugi de Ventosa i Calvell',
    'region': 'Pallars Sobirà',
    'places': 30,
    'coord': {
        'long': 1.1500,
        'lat': 42.5833
    }
}

EXAMPLE_REFUGI_INFO_RESTANCA = {
    'id': 'refugi_3',
    'name': 'Refugi de Restanca',
    'region': 'Val d\'Aran',
    'places': 36,
    'coord': {
        'long': 0.8167,
        'lat': 42.6500
    }
}

EXAMPLE_REFUGI_INFO_SABOREDO = {
    'id': 'refugi_5',
    'name': 'Refugi de Saboredo',
    'region': 'Val d\'Aran',
    'places': 80,
    'coord': {
        'long': 0.9500,
        'lat': 42.6333
    }
}

# ========== EXEMPLES DE RENOVATIONS ==========

EXAMPLE_RENOVATION_1 = {
    'id': 'renovation_1',
    'creator_uid': 'uid_abc123',
    'refuge_id': 'refugi_colomers',
    'ini_date': '2025-12-15',
    'fin_date': '2025-12-20',
    'description': 'Reparació del sostre i millora de l\'aïllament',
    'materials_needed': 'Teules, aïllant tèrmic, cargols',
    'group_link': 'https://wa.me/group/abc123',
    'participants_uids': ['uid_def456', 'uid_ghi789']
}

EXAMPLE_RENOVATION_2 = {
    'id': 'renovation_2',
    'creator_uid': 'uid_jkl012',
    'refuge_id': 'refugi_restanca',
    'ini_date': '2026-01-10',
    'fin_date': '2026-01-15',
    'description': 'Pintura exterior i arranjament de finestres',
    'materials_needed': 'Pintura, brotxes, segellant finestres',
    'group_link': 'https://t.me/+xyz456',
    'participants_uids': ['uid_mno345']
}

EXAMPLE_RENOVATION_CREATE = {
    'id': 'renovation_3',
    'creator_uid': 'uid_pqr678',
    'refuge_id': 'refugi_ventosa',
    'ini_date': '2025-12-01',
    'fin_date': '2025-12-10',
    'description': 'Renovació completa de la cuina i instal·lació d\'estanteries',
    'materials_needed': 'Fusta, claus, estanteries, eines diverses',
    'group_link': 'https://wa.me/group/def789',
    'participants_uids': []
}

EXAMPLE_RENOVATION_UPDATED = {
    'id': 'renovation_1',
    'creator_uid': 'uid_bcd890',
    'refuge_id': 'refugi_colomers',
    'ini_date': '2025-12-16',
    'fin_date': '2025-12-22',
    'description': 'Reparació del sostre, millora de l\'aïllament i pintura interior',
    'materials_needed': 'Teules, aïllant tèrmic, cargols, pintura',
    'group_link': 'https://wa.me/group/abc123',
    'participants_uids': ['uid_efg123', 'uid_hij456']
}

EXAMPLE_RENOVATION_WITH_PARTICIPANTS = {
    'id': 'renovation_1',
    'creator_uid': 'uid_klm789',
    'refuge_id': 'refugi_colomers',
    'ini_date': '2025-12-15',
    'fin_date': '2025-12-20',
    'description': 'Reparació del sostre i millora de l\'aïllament',
    'materials_needed': 'Teules, aïllant tèrmic, cargols',
    'group_link': 'https://wa.me/group/abc123',
    'participants_uids': ['uid_nop012', 'uid_qrs345', 'uid_tuv678']
}

EXAMPLE_RENOVATION_PARTICIPANT_REMOVED = {
    'id': 'renovation_1',
    'creator_uid': 'uid_wxy901',
    'refuge_id': 'refugi_colomers',
    'ini_date': '2025-12-15',
    'fin_date': '2025-12-20',
    'description': 'Reparació del sostre i millora de l\'aïllament',
    'materials_needed': 'Teules, aïllant tèrmic, cargols',
    'group_link': 'https://wa.me/group/abc123',
    'participants_uids': ['uid_zab234']
}

# ========== EXEMPLES DE REQUEST BODY ==========

EXAMPLE_USER_CREATE_REQUEST = {
    'username': 'joan_muntanyenc',
    'avatar': 'https://example.com/avatar.jpg',
    'language': 'ca'
}

EXAMPLE_USER_UPDATE_REQUEST = {
    'username': 'joan_muntanyenc_updated',
    'language': 'es'
}

EXAMPLE_USER_REFUGI_REQUEST = {
    'refuge_id': 'refugi_restanca'
}

EXAMPLE_USER_REFUGI_VISITED_REQUEST = {
    'refuge_id': 'refugi_saboredo'
}

EXAMPLE_RENOVATION_CREATE_REQUEST = {
    'refuge_id': 'refugi_ventosa',
    'ini_date': '2025-12-01',
    'fin_date': '2025-12-10',
    'description': 'Renovació completa de la cuina i instal·lació d\'estanteries',
    'materials_needed': 'Fusta, claus, estanteries, eines diverses',
    'group_link': 'https://wa.me/group/def789'
}

EXAMPLE_RENOVATION_UPDATE_REQUEST = {
    'ini_date': '2025-12-16',
    'fin_date': '2025-12-22',
    'description': 'Reparació del sostre, millora de l\'aïllament i pintura interior',
    'materials_needed': 'Teules, aïllant tèrmic, cargols, pintura'
}

# ========== EXEMPLES DE RESPOSTES COMPOSTES ==========

EXAMPLE_USER_REFUGI_INFO_RESPONSE_2 = {
    'count': 2,
    'results': [
        EXAMPLE_REFUGI_INFO_COLOMERS,
        EXAMPLE_REFUGI_INFO_VENTOSA
    ]
}

EXAMPLE_USER_REFUGI_INFO_RESPONSE_3 = {
    'count': 3,
    'results': [
        EXAMPLE_REFUGI_INFO_COLOMERS,
        EXAMPLE_REFUGI_INFO_VENTOSA,
        EXAMPLE_REFUGI_INFO_RESTANCA
    ]
}

EXAMPLE_USER_REFUGI_INFO_RESPONSE_1 = {
    'count': 1,
    'results': [
        EXAMPLE_REFUGI_INFO_COLOMERS
    ]
}

EXAMPLE_USER_VISITED_REFUGI_INFO_RESPONSE_2 = {
    'count': 2,
    'results': [
        EXAMPLE_REFUGI_INFO_COLOMERS,
        EXAMPLE_REFUGI_INFO_RESTANCA
    ]
}

EXAMPLE_USER_VISITED_REFUGI_INFO_RESPONSE_3 = {
    'count': 3,
    'results': [
        EXAMPLE_REFUGI_INFO_COLOMERS,
        EXAMPLE_REFUGI_INFO_RESTANCA,
        EXAMPLE_REFUGI_INFO_SABOREDO
    ]
}

EXAMPLE_REFUGI_SEARCH_RESPONSE = {
    'count': 2,
    'results': [
        EXAMPLE_REFUGI_COLOMERS,
        EXAMPLE_REFUGI_RESTANCA
    ]
}

EXAMPLE_RENOVATIONS_LIST = [
    EXAMPLE_RENOVATION_1,
    EXAMPLE_RENOVATION_2
]

EXAMPLE_CACHE_STATS = {
    'connected': True,
    'keys': 145,
    'memory_used': '2.5 MB',
    'hits': 2340,
    'misses': 156
}

EXAMPLE_CACHE_CLEAR_RESPONSE = {
    'message': 'Cache netejada correctament'
}

EXAMPLE_CACHE_INVALIDATE_RESPONSE = {
    'message': 'Claus amb patró "refugi_*" eliminades correctament'
}

EXAMPLE_HEALTH_CHECK_RESPONSE = {
    'status': 'healthy',
    'message': 'OK',
    'firebase': True,
    'firestore': True,
    'collections_count': 5
}

EXAMPLE_HEALTH_CHECK_UNHEALTHY = {
    'status': 'unhealthy',
    'message': 'Error connecting to Firebase',
    'firebase': False
}

# ========== EXEMPLES D'AVATAR ==========

EXAMPLE_AVATAR_UPLOAD_RESPONSE = {
    'message': 'Avatar pujat correctament',
    'avatar_metadata': {
        'key': 'users-avatars/uid_123abc/avatar.jpg',
        'url': 'https://r2-bucket.example.com/users-avatars/uid_123abc/avatar.jpg?presigned=true',
        'creator_uid': 'uid_123abc',
        'uploaded_at': '2025-12-09T14:30:00Z'
    }
}

# ========== EXEMPLES DE MITJANS (REFUGIS) ==========

EXAMPLE_REFUGI_MEDIA_LIST = {
    'media': [
        {
            'key': 'refugis-lliures/refugi_colomers/photo1.jpg',
            'url': 'https://r2-bucket.example.com/refugis-lliures/refugi_colomers/photo1.jpg?presigned=true',
            'creator_uid': 'uid_123abc',
            'uploaded_at': '2025-12-08T10:30:00Z'
        },
        {
            'key': 'refugis-lliures/refugi_colomers/photo2.jpg',
            'url': 'https://r2-bucket.example.com/refugis-lliures/refugi_colomers/photo2.jpg?presigned=true',
            'creator_uid': 'uid_456def',
            'uploaded_at': '2025-12-09T12:15:00Z'
        }
    ]
}

EXAMPLE_REFUGI_MEDIA_UPLOAD_RESPONSE = {
    'uploaded': [
        {
            'key': 'refugis-lliures/refugi_colomers/photo3.jpg',
            'url': 'https://r2-bucket.example.com/refugis-lliures/refugi_colomers/photo3.jpg?presigned=true',
            'creator_uid': 'uid_123abc',
            'uploaded_at': '2025-12-09T14:45:00Z'
        },
        {
            'key': 'refugis-lliures/refugi_colomers/video1.mp4',
            'url': 'https://r2-bucket.example.com/refugis-lliures/refugi_colomers/video1.mp4?presigned=true',
            'creator_uid': 'uid_123abc',
            'uploaded_at': '2025-12-09T14:46:00Z'
        }
    ],
    'falied': [
        {
            'key': 'refugis-lliures/refugi_colomers/photo3.jpg',
            'url': 'https://r2-bucket.example.com/refugis-lliures/refugi_colomers/photo3.jpg?presigned=true',
            'creator_uid': 'uid_123abc',
            'uploaded_at': '2025-12-09T14:45:00Z'
        },
        {
            'key': 'refugis-lliures/refugi_colomers/video1.mp4',
            'url': 'https://r2-bucket.example.com/refugis-lliures/refugi_colomers/video1.mp4?presigned=true',
            'creator_uid': 'uid_123abc',
            'uploaded_at': '2025-12-09T14:46:00Z'
        }
    ]
}

# ========== EXEMPLES DE PROPOSTES DE REFUGIS ==========

EXAMPLE_REFUGE_PROPOSAL_CREATE = {
    'action': 'create',
    'payload': {
        'name': 'Refugi Nou de Prova',
        'coord': {
            'long': 1.234,
            'lat': 42.567
        },
        'altitude': 1800,
        'places': 15,
        'remarque': 'Refugi en bon estat',
        'info_comp': {
            'manque_un_mur': 0,
            'cheminee': 1,
            'poele': 0,
            'couvertures': 1,
            'latrines': 1,
            'bois': 1,
            'eau': 1,
            'matelas': 0,
            'couchage': 1,
            'bas_flancs': 0,
            'lits': 1,
            'mezzanine_etage': 0
        },
        'description': 'Refugi de muntanya amb bones condicions',
        'links': [],
        'type': 'non gardé',
        'region': 'Pirineus',
        'departement': 'Lleida',
        'condition': 2
    },
    'comment': 'He visitat aquest refugi recentment i crec que hauria d\'estar a la base de dades'
}

EXAMPLE_REFUGE_PROPOSAL_UPDATE = {
    'refuge_id': 'refugi_colomers',
    'action': 'update',
    'payload': {
        'places': 45,
        'remarque': 'Refugi guardat a la Vall d\'Aran - Actualització de capacitat',
        'description': 'Refugi molt ben equipat amb vistes espectaculars. Recentment ampliat.'
    },
    'comment': 'He estat al refugi aquest mes i han ampliat la capacitat'
}

EXAMPLE_REFUGE_PROPOSAL_DELETE = {
    'refuge_id': 'refugi_antiga',
    'action': 'delete',
    'comment': 'Aquest refugi ja no existeix, va ser destruït per una allau'
}

EXAMPLE_REFUGE_PROPOSAL_RESPONSE = {
    'id': 'proposal_abc123',
    'refuge_id': None,
    'action': 'create',
    'payload': {
        'name': 'Refugi Nou de Prova',
        'coord': {
            'long': 1.234,
            'lat': 42.567
        },
        'altitude': 1800,
        'places': 15,
        'remarque': 'Refugi en bon estat',
        'info_comp': {
            'manque_un_mur': 0,
            'cheminee': 1,
            'poele': 0,
            'couvertures': 1,
            'latrines': 1,
            'bois': 1,
            'eau': 1,
            'matelas': 0,
            'couchage': 1,
            'bas_flancs': 0,
            'lits': 1,
            'mezzanine_etage': 0
        },
        'description': 'Refugi de muntanya amb bones condicions',
        'links': [],
        'type': 'non gardé',
        'region': 'Pirineus',
        'departement': 'Lleida',
        'condition': 2
    },
    'comment': 'He visitat aquest refugi recentment i crec que hauria d\'estar a la base de dades',
    'status': 'pending',
    'creator_uid': 'uid_123abc',
    'created_at': '2025-12-10',
    'reviewer_uid': None,
    'reviewed_at': None,
    'rejection_reason': None
}

EXAMPLE_REFUGE_PROPOSALS_LIST = [
    {
        'id': 'proposal_abc123',
        'refuge_id': None,
        'action': 'create',
        'payload': {
            'name': 'Refugi Nou de Prova',
            'coord': {'long': 1.234, 'lat': 42.567},
            'altitude': 1800,
            'places': 15,
            'remarque': 'Refugi en bon estat',
            'info_comp': {
                'manque_un_mur': 0,
                'cheminee': 1,
                'poele': 0,
                'couvertures': 1,
                'latrines': 1,
                'bois': 1,
                'eau': 1,
                'matelas': 0,
                'couchage': 1,
                'bas_flancs': 0,
                'lits': 1,
                'mezzanine_etage': 0
            },
            'description': 'Refugi de muntanya amb bones condicions',
            'links': [],
            'type': 'non gardé',
            'region': 'Pirineus',
            'departement': 'Lleida',
            'condition': 2
        },
        'comment': 'Nou refugi descobert',
        'status': 'pending',
        'creator_uid': 'uid_123abc',
        'created_at': '2025-12-10',
        'reviewer_uid': None,
        'reviewed_at': None,
        'rejection_reason': None
    },
    {
        'id': 'proposal_def456',
        'refuge_id': 'refugi_colomers',
        'action': 'update',
        'payload': {
            'places': 45,
            'remarque': 'Capacitat actualitzada'
        },
        'comment': 'Ampliació recent del refugi',
        'status': 'approved',
        'creator_uid': 'uid_456def',
        'created_at': '2025-12-08',
        'reviewer_uid': 'admin_uid_789',
        'reviewed_at': '2025-12-09',
        'rejection_reason': None
    },
    {
        'id': 'proposal_ghi789',
        'refuge_id': 'refugi_antiga',
        'action': 'delete',
        'payload': None,
        'comment': 'Refugi destruït per allau',
        'status': 'rejected',
        'creator_uid': 'uid_789ghi',
        'created_at': '2025-12-07',
        'reviewer_uid': 'admin_uid_789',
        'reviewed_at': '2025-12-08',
        'rejection_reason': 'Necessitem més evidències abans d\'eliminar el refugi'
    }
]


# ========== EXEMPLES DE DOUBTS I ANSWERS ==========

EXAMPLE_ANSWER_DETAIL = {
    'id': 'answer_abc123',
    'creator_uid': 'uid_456def',
    'message': 'Sí, hi ha una font d\'aigua potable a uns 100 metres del refugi.',
    'created_at': '2025-12-20T10:30:00+01:00',
    'parent_answer_id': None
}

EXAMPLE_ANSWER_REPLY = {
    'id': 'answer_def456',
    'creator_uid': 'uid_789ghi',
    'message': 'Gràcies per la informació! És potable tot l\'any?',
    'created_at': '2025-12-20T11:15:00+01:00',
    'parent_answer_id': 'answer_abc123'
}

EXAMPLE_DOUBT_DETAIL = {
    'id': 'doubt_123abc',
    'refuge_id': 'refugi_colomers',
    'creator_uid': 'uid_123abc',
    'message': 'Hi ha aigua potable prop del refugi?',
    'created_at': '2025-12-20T09:45:00+01:00',
    'answers_count': 0,
    'answers': []
}

EXAMPLE_DOUBT_WITH_ANSWERS = {
    'id': 'doubt_456def',
    'refuge_id': 'refugi_colomers',
    'creator_uid': 'uid_123abc',
    'message': 'Quin és l\'estat de les cobertes actualmente?',
    'created_at': '2025-12-19T14:20:00+01:00',
    'answers_count': 3,
    'answers': [
        {
            'id': 'answer_ghi789',
            'creator_uid': 'uid_456def',
            'message': 'Hi ha suficients cobertes, però estan una mica desgastades.',
            'created_at': '2025-12-19T15:10:00+01:00',
            'parent_answer_id': None
        },
        {
            'id': 'answer_jkl012',
            'creator_uid': 'uid_789ghi',
            'message': 'Jo hi vaig anar la setmana passada i n\'hi havia unes 20.',
            'created_at': '2025-12-19T16:30:00+01:00',
            'parent_answer_id': None
        },
        {
            'id': 'answer_mno345',
            'creator_uid': 'uid_123abc',
            'message': 'Perfecte, gràcies a tots per la informació!',
            'created_at': '2025-12-19T17:00:00+01:00',
            'parent_answer_id': 'answer_ghi789'
        }
    ]
}

EXAMPLE_DOUBT_LIST = [
    {
        'id': 'doubt_789xyz',
        'refuge_id': 'refugi_colomers',
        'creator_uid': 'uid_abc123',
        'message': 'Es pot arribar amb cotxe fins al refugi?',
        'created_at': '2025-12-21T08:00:00+01:00',
        'answers_count': 2,
        'answers': [
            {
                'id': 'answer_pqr678',
                'creator_uid': 'uid_def456',
                'message': 'No, cal fer una caminata d\'aproximadament 2 hores des del pàrquing més proper.',
                'created_at': '2025-12-21T09:30:00+01:00',
                'parent_answer_id': None
            },
            {
                'id': 'answer_stu901',
                'creator_uid': 'uid_ghi789',
                'message': 'El pàrquing està al final de la carretera de Conangles.',
                'created_at': '2025-12-21T10:15:00+01:00',
                'parent_answer_id': 'answer_pqr678'
            }
        ]
    },
    {
        'id': 'doubt_456def',
        'refuge_id': 'refugi_colomers',
        'creator_uid': 'uid_123abc',
        'message': 'Quin és l\'estat de les cobertes actualmente?',
        'created_at': '2025-12-19T14:20:00+01:00',
        'answers_count': 3,
        'answers': [
            {
                'id': 'answer_ghi789',
                'creator_uid': 'uid_456def',
                'message': 'Hi ha suficients cobertes, però estan una mica desgastades.',
                'created_at': '2025-12-19T15:10:00+01:00',
                'parent_answer_id': None
            },
            {
                'id': 'answer_jkl012',
                'creator_uid': 'uid_789ghi',
                'message': 'Jo hi vaig anar la setmana passada i n\'hi havia unes 20.',
                'created_at': '2025-12-19T16:30:00+01:00',
                'parent_answer_id': None
            },
            {
                'id': 'answer_mno345',
                'creator_uid': 'uid_123abc',
                'message': 'Perfecte, gràcies a tots per la informació!',
                'created_at': '2025-12-19T17:00:00+01:00',
                'parent_answer_id': 'answer_ghi789'
            }
        ]
    }
]
