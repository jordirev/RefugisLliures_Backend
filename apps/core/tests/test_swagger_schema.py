"""
`/swagger/` i `/redoc/` han de poder generar l'esquema OpenAPI sencer.

drf-yasg falla (500) si dos serializers diferents comparteixen nom (`ref_name` implícit), cosa que passa fàcilment
mentre un serializer té àlies o subclasses buides (cas d'un àlies buit de `MediaItemSerializer`, ja eliminat). Aquest test
genera l'esquema sense BD, de manera que la CI ho detecta.
"""
from drf_yasg import openapi
from drf_yasg.generators import OpenAPISchemaGenerator


def test_l_esquema_openapi_es_genera_sencer():
    generator = OpenAPISchemaGenerator(openapi.Info(title='Refugis Lliures API', default_version='v1'))
    schema = generator.get_schema(request=None, public=True)
    assert '/refuges/' in schema['paths']
    assert schema['definitions']
