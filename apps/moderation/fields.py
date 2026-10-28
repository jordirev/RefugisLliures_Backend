"""Camps propis de `moderation`."""
from django.db import models


class FixedCharField(models.CharField):
    """`char(n)` de PostgreSQL (el disseny §2.22 declara `sha256 char(64)`): longitud fixa."""

    def db_type(self, connection):
        if connection.vendor != 'postgresql':
            return super().db_type(connection)
        return 'char(%d)' % self.max_length
