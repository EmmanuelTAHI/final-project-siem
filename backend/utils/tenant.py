"""
Isolation multi-tenant — Couche 1 (voir plan multi-tenant, §2.1).

OrganizationFilterBackend est ajouté en premier dans
REST_FRAMEWORK["DEFAULT_FILTER_BACKENDS"] : comme DRF's get_object() appelle
filter_queryset(get_queryset()), ce backend couvre automatiquement list(),
retrieve(), update() et destroy() pour tout ViewSet dont le modèle porte un
champ `organization`.

Ce n'est qu'UNE des 3 couches d'isolation (voir aussi utils.models et
utils.permissions.IsSameOrganization) — ne jamais s'y fier seule.
"""
from rest_framework.filters import BaseFilterBackend


class OrganizationFilterBackend(BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        model = queryset.model
        if not hasattr(model, "organization_id"):
            # Modèle explicitement hors périmètre tenant (ex: ThreatIndicator,
            # Organization elle-même, User quand géré par IsPlatformStaff...).
            return queryset

        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return queryset.none()

        if user.is_superuser and getattr(view, "allow_cross_org_for_platform_staff", False):
            return queryset

        if user.organization_id is None:
            # Staff plateforme (is_superuser) qui tape un endpoint métier
            # normal, non marqué allow_cross_org_for_platform_staff : ne voit
            # rien plutôt que de tout voir par accident.
            return queryset.none()

        return queryset.filter(organization_id=user.organization_id)
