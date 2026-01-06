#!/bin/bash
# MAI FER COMMIT AMB DADES REALS DE LES CLAUS D'ACCÉS A R2 EN ELS FITXERS DE L'ENTORN.

# Canvia al directori del projecte
cd "$(dirname "$0")"

# Configura les variables d'entorn per R2
export R2_ACCESS_KEY_ID=example_access_key
export R2_SECRET_ACCESS_KEY=example_secret_key
export R2_ENDPOINT=example.r2.cloudflarestorage.com
export R2_BUCKET_NAME=example-bucket

# Executa el comando Django
python manage.py process_yesterday_visits --verbosity=1
