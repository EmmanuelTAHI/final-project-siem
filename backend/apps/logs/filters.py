"""
Filtres DRF avancés pour les logs normalisés et bruts.
"""
import django_filters
from django.db.models import CharField, Q
from django.db.models.functions import Cast

from .models import NormalizedLog, RawLog


class RawLogFilter(django_filters.FilterSet):
    date_from = django_filters.DateTimeFilter(field_name="received_at", lookup_expr="gte")
    date_to = django_filters.DateTimeFilter(field_name="received_at", lookup_expr="lte")

    class Meta:
        model = RawLog
        fields = ["source_type", "connector", "is_normalized"]


class NormalizedLogFilter(django_filters.FilterSet):
    event_time_from = django_filters.DateTimeFilter(field_name="event_time", lookup_expr="gte")
    event_time_to = django_filters.DateTimeFilter(field_name="event_time", lookup_expr="lte")
    search = django_filters.CharFilter(method="filter_search")

    # Champs texte en correspondance partielle (icontains) plutôt qu'exacte :
    # permet de taper "wazuh" pour matcher "wazuh", de filtrer "login" pour
    # matcher "login_failure"/"login_success", etc. — comportement attendu
    # par la barre de recherche façon Splunk/Kibana (source_type:wazuh).
    source_type = django_filters.CharFilter(field_name="source_type", lookup_expr="icontains")
    action = django_filters.CharFilter(field_name="action", lookup_expr="icontains")
    geo_country = django_filters.CharFilter(field_name="geo_country", lookup_expr="icontains")
    user_email = django_filters.CharFilter(field_name="user_email", lookup_expr="icontains")

    # Sévérité multi-sélection : ?severity=high&severity=critical (OU logique),
    # remplace l'ancien exact-match qui n'acceptait qu'une seule valeur alors
    # que l'UI permet de cocher plusieurs pastilles de sévérité à la fois.
    severity = django_filters.MultipleChoiceFilter(
        field_name="severity", choices=NormalizedLog.SEVERITY_CHOICES,
    )
    outcome = django_filters.MultipleChoiceFilter(
        field_name="outcome", choices=NormalizedLog.OUTCOME_CHOICES,
    )

    # IP source : recherche partielle. GenericIPAddressField (inet en
    # Postgres) ne supporte pas nativement __icontains, d'où le cast en texte.
    source_ip = django_filters.CharFilter(method="filter_source_ip")

    class Meta:
        model = NormalizedLog
        fields = [
            "source_type",
            "action",
            "outcome",
            "severity",
            "user_email",
            "geo_country",
            "source_ip",
        ]

    @staticmethod
    def _with_source_ip_str(queryset):
        """Annote source_ip_str une seule fois (search ET source_ip peuvent
        toutes deux être actives simultanément — évite une double annotation
        du même nom, que Django refuse)."""
        if "source_ip_str" in queryset.query.annotations:
            return queryset
        return queryset.annotate(source_ip_str=Cast("source_ip", CharField()))

    def filter_search(self, queryset, name, value):
        """Recherche full-text sur user_email, source_ip, action, resource."""
        queryset = self._with_source_ip_str(queryset)
        return queryset.filter(
            Q(user_email__icontains=value)
            | Q(source_ip_str__icontains=value)
            | Q(action__icontains=value)
            | Q(resource__icontains=value)
            | Q(geo_city__icontains=value)
        )

    def filter_source_ip(self, queryset, name, value):
        queryset = self._with_source_ip_str(queryset)
        return queryset.filter(source_ip_str__icontains=value)
