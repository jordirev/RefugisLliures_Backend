"""`core.0002`: el rol `app` pot llegir `public.django_migrations`.

`runserver` (i `showmigrations`/`migrate --check`) consulten aquesta taula amb la connexió `default` (rol `app`)
per avisar de migracions pendents; sense el grant, `runserver` no arrenca (`permission denied`). Només lectura:
`app` continua sense DDL ni escriptura a les taules internes de Django (§7.2). Trobat a l'e2e del chunk 1.
"""
from django.db import migrations

from domain.core.migration_utils import PostgresRunSQL


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        PostgresRunSQL(
            sql='GRANT SELECT ON public.django_migrations TO app',
            reverse_sql='REVOKE SELECT ON public.django_migrations FROM app',
        ),
    ]
