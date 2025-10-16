# Gunicorn configuration file
# gunicorn.conf.py

import os

# Server socket
bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"
backlog = 2048

# Worker processes
# Mantén workers=1 para evitar problemas de concurrencia en entornos de desarrollo o con SQLite.
workers = 1  # No aumentes este valor si usas SQLite o para desarrollo local.
# worker_class puede ser "sync" (por defecto), "gevent", "eventlet", etc.
# Usa "sync" salvo que tengas necesidades específicas de concurrencia asíncrona.
worker_class = "sync"
# worker_connections solo aplica a worker_class asíncronos, pero puedes dejarlo por defecto.
worker_connections = 1000
# timeout define cuántos segundos esperar antes de reiniciar un worker que no responde.
timeout = 30  # Puedes aumentarlo si tienes peticiones largas.
# keepalive controla cuánto tiempo mantener conexiones HTTP abiertas.
keepalive = 2  # Puedes aumentarlo si esperas muchas conexiones persistentes.

# Restart workers after this many requests, to help prevent memory leaks
max_requests = 1000
max_requests_jitter = 100

# Logging
loglevel = "info"
accesslog = "-"  # Log to stdout
errorlog = "-"   # Log to stderr
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Process naming
proc_name = "refugis_lliures"

# Server mechanics
preload_app = True
daemon = False
pidfile = None
user = None
group = None
tmp_upload_dir = None

# SSL (if needed in the future)
# keyfile = None
# certfile = None