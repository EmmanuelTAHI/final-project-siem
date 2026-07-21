"""
Permissions par rôle pour Argus.
Rôles : admin, analyst, viewer
"""
from rest_framework.permissions import BasePermission


class IsAdmin(BasePermission):
    """Seuls les utilisateurs avec le rôle 'admin' ont accès."""

    message = "Seuls les administrateurs peuvent effectuer cette action."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == "admin"
        )


class IsAnalyst(BasePermission):
    """Accès pour les analystes et les administrateurs."""

    message = "Seuls les analystes et administrateurs peuvent effectuer cette action."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in ("admin", "analyst")
        )


class IsViewer(BasePermission):
    """Accès en lecture pour tous les rôles authentifiés."""

    message = "Vous devez être authentifié pour accéder à cette ressource."

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated


class IsAdminOrReadOnly(BasePermission):
    """Lecture pour tous, écriture uniquement pour les admins."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return request.user.role == "admin"


class IsAnalystOrReadOnly(BasePermission):
    """Lecture pour tous, écriture pour les analystes et admins."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return request.user.role in ("admin", "analyst")


class IsOwnerOrAdmin(BasePermission):
    """Accès uniquement au propriétaire de la ressource ou à un admin."""

    def has_object_permission(self, request, view, obj):
        if request.user.role == "admin":
            return True
        return obj == request.user or getattr(obj, "user", None) == request.user


class IsPlatformStaff(BasePermission):
    """
    Staff plateforme (super-admin) uniquement — voit toutes les organisations.
    Utilisée exclusivement par les ViewSets marqués
    `allow_cross_org_for_platform_staff = True` (voir utils.tenant), qui sont
    le SEUL endroit du code où ce bypass cross-org doit apparaître.
    """

    message = "Réservé au staff de la plateforme."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_superuser)


class IsSameOrganization(BasePermission):
    """
    Isolation multi-tenant — Couche 3 (défense en profondeur pour les routes
    de détail). OrganizationFilterBackend (couche 1) pré-filtre déjà le
    queryset avant get_object(), mais cette permission protège contre tout
    ViewSet qui surchargerait get_queryset() d'une façon qui court-circuite
    la chaîne de filter_backends par accident.
    """

    message = "Cette ressource appartient à une autre organisation."

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.is_superuser and getattr(view, "allow_cross_org_for_platform_staff", False):
            return True
        org = getattr(obj, "organization", None)
        return org is not None and org.id == user.organization_id
