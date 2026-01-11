
""" MAI FER COMMIT AMB DADES REALS DE LES CLAUS D'ACCÉS A R2 EN ELS FITXERS DE L'ENTORN. """


@echo off
cd /d C:\Users\jordi\Desktop\UNI\TFG\Backend\RefugisLliures_Backend
set R2_ACCESS_KEY_ID=example_access_key
set R2_SECRET_ACCESS_KEY=example_secret_key
set R2_ENDPOINT=example.r2.cloudflarestorage.com
set R2_BUCKET_NAME=example-bucket
python manage.py process_yesterday_visits --verbosity=1