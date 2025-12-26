@echo off
cd /d C:\Users\jordi\Desktop\UNI\TFG\Backend\RefugisLliures_Backend
set R2_ACCESS_KEY_ID=b2737df8dd35950b4c80a62df55424ff
set R2_SECRET_ACCESS_KEY=1b685c4dbffd190aa3076c9fd9cbaf96ce5dbed9c4e9e0d44539aa8a2bc3104f
set R2_ENDPOINT=https://e0c55e2f7b13e7548afed9db64268f83.r2.cloudflarestorage.com
set R2_BUCKET_NAME=refugis-lliures-media
python manage.py process_yesterday_visits --verbosity=1