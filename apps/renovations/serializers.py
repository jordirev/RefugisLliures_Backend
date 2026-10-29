"""
Serializers de `renovations` (contracte JSON d'abans: docs/design/postgres-schema.md §5.2).

Entrada: `RenovationCreateSerializer` (tots els camps obligatoris llevat de `materials_needed`) i
`RenovationUpdateSerializer` (tots opcionals, **sense `default=`**: GOTCHAS #6). Les regles són les mateixes que les
del model i la BD (`ini_date <= fin_date`: reformes d'un sol dia vàlides, GOTCHAS #5; `group_link` http/https de com a
molt 2048 caràcters). La comparació d'una data nova amb la desada (M2) la fa el servei.

Sortida: `RenovationSerializer(instance)`; la instància duu les anotacions `participants_uids` i `group_link` dels
selectors. `group_link` només s'emet si no és `None` (la RLS el deixa a `None` a qui no hi té dret) i
`expelled_uids` no s'emet mai.
"""
from django.core.validators import URLValidator
from rest_framework import serializers

from apps.core.timezone_utils import get_madrid_today

GROUP_LINK_MAX_LENGTH = 2048
_http_url = URLValidator(schemes=['http', 'https'])


class DateValidationMixin:
    """Validacions de dates compartides pel serializer de creació i el d'actualització."""

    @staticmethod
    def validate_dates(ini_date, fin_date):
        if ini_date > fin_date:
            raise serializers.ValidationError({
                'fin_date': "La data de finalització no pot ser anterior a la data d'inici"
            })

    @staticmethod
    def validate_ini_date_is_current_or_future(ini_date):
        madrid_today = get_madrid_today()
        if ini_date < madrid_today:
            raise serializers.ValidationError({
                'ini_date': f"La data d'inici ha de ser igual o posterior a la data actual ({madrid_today.isoformat()})"
            })


def _date_field(**kwargs):
    return serializers.DateField(format='%Y-%m-%d', input_formats=['%Y-%m-%d', 'iso-8601'], **kwargs)


def _group_link_field(**kwargs):
    return serializers.CharField(max_length=GROUP_LINK_MAX_LENGTH, validators=[_http_url],
                                 help_text='Enllaç al grup de coordinació (WhatsApp/Telegram), http o https', **kwargs)


class RenovationCreateSerializer(DateValidationMixin, serializers.Serializer):
    """Cos de `POST /renovations/`. Camps desconeguts (`creator_uid`, `participants_uids`...) s'ignoren."""

    refuge_id = serializers.CharField(max_length=255, help_text='ID del refugi a reformar')
    ini_date = _date_field(help_text="Data d'inici (inclosa)")
    fin_date = _date_field(help_text='Data de finalització (inclosa)')
    description = serializers.CharField(help_text='Descripció de la reforma')
    materials_needed = serializers.CharField(required=False, allow_blank=True, allow_null=True,
                                             help_text='Materials necessaris')
    group_link = _group_link_field()

    def validate(self, data):
        self.validate_dates(data['ini_date'], data['fin_date'])
        self.validate_ini_date_is_current_or_future(data['ini_date'])
        return data


class RenovationUpdateSerializer(DateValidationMixin, serializers.Serializer):
    """Cos de `PATCH /renovations/{id}/`: només els camps enviats; `group_link` no pot ser `null`."""

    ini_date = _date_field(required=False, help_text="Data d'inici (inclosa)")
    fin_date = _date_field(required=False, help_text='Data de finalització (inclosa)')
    description = serializers.CharField(required=False, help_text='Descripció de la reforma')
    materials_needed = serializers.CharField(required=False, allow_blank=True, allow_null=True,
                                             help_text='Materials necessaris')
    group_link = _group_link_field(required=False)

    def validate(self, data):
        if 'ini_date' in data and 'fin_date' in data:
            self.validate_dates(data['ini_date'], data['fin_date'])
        if 'ini_date' in data:
            self.validate_ini_date_is_current_or_future(data['ini_date'])
        return data


class RenovationSerializer(serializers.Serializer):
    """Sortida d'una reforma (`many=True` per a les llistes)."""

    def to_representation(self, instance):
        data = {
            'id': str(instance.pk),
            'creator_uid': instance.creator_id or 'unknown',     # creador esborrat → reforma passada anònima
            'refuge_id': str(instance.refuge_id),
            'ini_date': instance.ini_date.isoformat(),
            'fin_date': instance.fin_date.isoformat(),
            'description': instance.description,
            'materials_needed': instance.materials_needed,
            'participants_uids': list(getattr(instance, 'participants_uids', None) or []),
        }
        group_link = getattr(instance, 'group_link', None)
        if group_link is not None:
            data['group_link'] = group_link
        return data
