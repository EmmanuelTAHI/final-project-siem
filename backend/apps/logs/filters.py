"""
Filtres DRF avancés pour les logs normalisés et bruts.
"""
import django_filters

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

    class Meta:
        model = NormalizedLog
        fields = [
            "source_type",
            "action",
            "outcome",
            "severity",
            "user_email",
            "geo_country",
        ]

    def filter_search(self, queryset, name, value):
        """Recherche full-text sur user_email, source_ip, action, resource."""
        from django.db.models import Q
        return queryset.filter(
            Q(user_email__icontains=value)
            | Q(source_ip__icontains=value)
            | Q(action__icontains=value)
            | Q(resource__icontains=value)
            | Q(geo_city__icontains=value)
        )
