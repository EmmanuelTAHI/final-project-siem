"""
Vues pour la gestion des utilisateurs SOC.
"""
import logging

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from utils.permissions import IsAdmin
from utils.response import created_response, error_response, no_content_response, success_response
from utils.tenant import OrganizationFilterBackend

from .models import AuditTrail, User
from .serializers import (
    AuditTrailSerializer,
    ChangePasswordSerializer,
    UserCreateSerializer,
    UserSerializer,
    UserUpdateSerializer,
)

logger = logging.getLogger(__name__)


def get_client_ip(request) -> str:
    """Extrait l'adresse IP depuis la requête HTTP."""
    x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded:
        return x_forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


class UserViewSet(ModelViewSet):
    """
    ViewSet complet pour la gestion des utilisateurs.
    GET/POST /api/users/           → admin seulement pour création
    GET/PUT  /api/users/{id}/      → lecture pour tous, écriture admin
    DELETE   /api/users/{id}/      → admin seulement
    GET/PATCH /api/users/me/       → utilisateur connecté
    """

    queryset = User.objects.all().order_by("-created_at")
    filter_backends = [
        OrganizationFilterBackend, DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter,
    ]
    filterset_fields = ["role", "is_active"]
    search_fields = ["email", "first_name", "last_name"]
    ordering_fields = ["created_at", "email", "role"]

    def get_serializer_class(self):
        if self.action == "create":
            return UserCreateSerializer
        if self.action in ("update", "partial_update"):
            return UserUpdateSerializer
        return UserSerializer

    def get_permissions(self):
        if self.action in ("list", "create", "destroy"):
            return [IsAdmin()]
        if self.action in ("update", "partial_update"):
            return [IsAdmin()]
        return [IsAuthenticated()]

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return success_response(data=serializer.data, message="Liste des utilisateurs.")

    def create(self, request, *args, **kwargs):
        serializer = UserCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                message="Données invalides.",
                errors=serializer.errors,
                http_status=status.HTTP_400_BAD_REQUEST,
            )
        user = serializer.save(organization=request.user.organization)
        AuditTrail.log(
            action="user_create",
            user=request.user,
            target_model="User",
            target_id=user.id,
            ip_address=get_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT"),
        )
        return created_response(
            data=UserSerializer(user).data,
            message="Utilisateur créé avec succès.",
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = UserUpdateSerializer(instance, data=request.data, partial=partial)
        if not serializer.is_valid():
            return error_response(message="Données invalides.", errors=serializer.errors)
        user = serializer.save()
        AuditTrail.log(
            action="user_update",
            user=request.user,
            target_model="User",
            target_id=user.id,
            ip_address=get_client_ip(request),
        )
        return success_response(data=UserSerializer(user).data, message="Utilisateur mis à jour.")

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance == request.user:
            return error_response(
                message="Vous ne pouvez pas supprimer votre propre compte.",
                http_status=status.HTTP_400_BAD_REQUEST,
            )
        user_id = str(instance.id)
        AuditTrail.log(
            action="user_delete",
            user=request.user,
            target_model="User",
            target_id=user_id,
            ip_address=get_client_ip(request),
        )
        instance.delete()
        return no_content_response("Utilisateur supprimé.")

    @action(detail=False, methods=["get", "patch"], permission_classes=[IsAuthenticated])
    def me(self, request):
        """Retourne ou met à jour le profil de l'utilisateur connecté."""
        if request.method == "GET":
            serializer = UserSerializer(request.user)
            return success_response(data=serializer.data, message="Profil utilisateur.")

        serializer = UserUpdateSerializer(request.user, data=request.data, partial=True)
        if not serializer.is_valid():
            return error_response(message="Données invalides.", errors=serializer.errors)
        serializer.save()
        return success_response(
            data=UserSerializer(request.user).data,
            message="Profil mis à jour.",
        )

    @action(
        detail=False,
        methods=["post"],
        url_path="me/change-password",
        permission_classes=[IsAuthenticated],
    )
    def change_password(self, request):
        """Change le mot de passe de l'utilisateur connecté."""
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            return error_response(message="Données invalides.", errors=serializer.errors)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save()
        AuditTrail.log(
            action="password_change",
            user=request.user,
            target_model="User",
            target_id=request.user.id,
            ip_address=get_client_ip(request),
        )
        return success_response(message="Mot de passe changé avec succès.")


class AuditTrailViewSet(ReadOnlyModelViewSet):
    """
    Audit trail — lecture seule, admin uniquement.
    GET /api/users/audit-trail/
    """

    queryset = AuditTrail.objects.select_related("user").all()
    serializer_class = AuditTrailSerializer
    permission_classes = [IsAdmin]
    filter_backends = [OrganizationFilterBackend, DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["action", "target_model", "user"]
    ordering_fields = ["timestamp"]
    ordering = ["-timestamp"]
