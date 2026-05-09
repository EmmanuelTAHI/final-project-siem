"""
Permissions par rôle pour Log+.
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
