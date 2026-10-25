"""Funcions de BD pròpies per als `db_default` dels models."""
from django.db.models import DateTimeField, Func


class TransactionNow(Func):
    """`now()` de PostgreSQL (instant d'inici de la transacció). `Now()` de Django usa `STATEMENT_TIMESTAMP()`."""

    function = 'NOW'
    output_field = DateTimeField()
    arity = 0
