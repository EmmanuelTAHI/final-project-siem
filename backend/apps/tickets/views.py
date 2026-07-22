"""
Vues pour la gestion des tickets SOC (incidents / tâches de suivi).
"""
import logging

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.viewsets import ModelViewSet

from apps.users.models import AuditTrail, User
from utils.permissions import IsAdmin, IsAnalyst
from utils.response import created_response, error_response, no_content_response, success_response
from utils.tenant import OrganizationFilterBackend

from .models import Ticket, TicketActivity, TicketComment
from .serializers import (
    TicketCommentCreateSerializer,
    TicketCommentSerializer,
    TicketCreateSerializer,
    TicketListSerializer,
    TicketSerializer,
    TicketUpdateSerializer,
    TicketUserBriefSerializer,
)

logger = logging.getLogger(__name__)


def _get_client_ip(request) -> str:
    x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded:
        return x_forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


class TicketViewSet(ModelViewSet):
    """
    Gestion des tickets SOC (incidents/tâches de suivi).
    GET    /api/tickets/
    POST   /api/tickets/
    GET    /api/tickets/{id}/
    PATCH  /api/tickets/{id}/
    DELETE /api/tickets/{id}/                  (admin uniquement)
    GET/POST /api/tickets/{id}/comments/
    GET    /api/tickets/stats/
    GET    /api/tickets/assignable-users/
    """

    queryset = (
        Ticket.objects
        .select_related("reporter", "assignee", "alert")
        .prefetch_related("comments__author", "activities__actor", "linked_alerts")
        .all()
    )
    filter_backends = [
        OrganizationFilterBackend, DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter,
    ]
    filterset_fields = ["status", "priority", "assignee", "alert"]
    search_fields = ["title", "description"]
    ordering_fields = ["created_at", "updated_at", "priority", "status", "due_date", "number"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.action == "create":
            return TicketCreateSerializer
        if self.action == "partial_update":
            return TicketUpdateSerializer
        return TicketSerializer

    def get_permissions(self):
        if self.action == "destroy":
            return [IsAdmin()]
        return [IsAnalyst()]

    def get_queryset(self):
        queryset = super().get_queryset()
        unassigned = self.request.query_params.get("unassigned")
        if unassigned in ("1", "true", "True"):
            queryset = queryset.filter(assignee__isnull=True)
        overdue = self.request.query_params.get("overdue")
        if overdue in ("1", "true", "True"):
            queryset = queryset.filter(
                due_date__isnull=False, due_date__lt=timezone.now(),
            ).exclude(status__in=Ticket.CLOSED_STATUSES)
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = TicketListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = TicketListSerializer(queryset, many=True)
        return success_response(data=serializer.data, message="Liste des tickets.")

    def retrieve(self, request, *args, **kwargs):
        ticket = self.get_object()
        return success_response(data=TicketSerializer(ticket).data)

    def create(self, request, *args, **kwargs):
        serializer = TicketCreateSerializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            return error_response(message="Données invalides.", errors=serializer.errors)

        organization = request.user.organization
        with transaction.atomic():
            last = (
                Ticket.objects.select_for_update()
                .filter(organization=organization)
                .order_by("-number")
                .first()
            )
            next_number = (last.number + 1) if last else 1
            ticket = serializer.save(
                organization=organization,
                reporter=request.user,
                number=next_number,
            )
            TicketActivity.objects.create(
                ticket=ticket, actor=request.user, action="created",
                to_value=ticket.get_status_display(),
            )

        AuditTrail.log(
            action="ticket_create", user=request.user, target_model="Ticket", target_id=ticket.id,
            ip_address=_get_client_ip(request),
            extra_data={"alert_id": str(ticket.alert_id) if ticket.alert_id else None},
        )
        fresh = self.get_queryset().get(pk=ticket.pk)
        return created_response(data=TicketSerializer(fresh).data, message=f"Ticket {ticket.display_id} créé.")

    def partial_update(self, request, *args, **kwargs):
        ticket = self.get_object()
        old_status, old_priority, old_assignee = ticket.status, ticket.priority, ticket.assignee

        serializer = TicketUpdateSerializer(ticket, data=request.data, partial=True, context={"request": request})
        if not serializer.is_valid():
            return error_response(message="Données invalides.", errors=serializer.errors)

        new_status = serializer.validated_data.get("status", old_status)
        update_fields = {}
        if "status" in serializer.validated_data:
            if new_status in Ticket.CLOSED_STATUSES and old_status not in Ticket.CLOSED_STATUSES:
                if new_status == "resolved" and not ticket.resolved_at:
                    update_fields["resolved_at"] = timezone.now()
                if new_status == "closed" and not ticket.closed_at:
                    update_fields["closed_at"] = timezone.now()
            if new_status not in Ticket.CLOSED_STATUSES:
                # Réouverture : on efface les horodatages de clôture précédents.
                update_fields["resolved_at"] = None
                update_fields["closed_at"] = None

        updated = serializer.save(**update_fields)

        activities = []
        if "status" in serializer.validated_data and old_status != updated.status:
            activities.append(TicketActivity(
                ticket=ticket, actor=request.user, action="status_changed",
                from_value=dict(Ticket.STATUS_CHOICES).get(old_status, old_status),
                to_value=updated.get_status_display(),
            ))
        if "priority" in serializer.validated_data and old_priority != updated.priority:
            activities.append(TicketActivity(
                ticket=ticket, actor=request.user, action="priority_changed",
                from_value=dict(Ticket.PRIORITY_CHOICES).get(old_priority, old_priority),
                to_value=updated.get_priority_display(),
            ))
        if "assignee" in serializer.validated_data and old_assignee != updated.assignee:
            activities.append(TicketActivity(
                ticket=ticket, actor=request.user, action="assigned",
                from_value=old_assignee.email if old_assignee else "Non assigné",
                to_value=updated.assignee.email if updated.assignee else "Non assigné",
            ))
        if activities:
            TicketActivity.objects.bulk_create(activities)
        elif set(serializer.validated_data.keys()) - {"status", "priority", "assignee"}:
            TicketActivity.objects.create(ticket=ticket, actor=request.user, action="updated")

        AuditTrail.log(
            action="ticket_update", user=request.user, target_model="Ticket", target_id=ticket.id,
            ip_address=_get_client_ip(request),
            extra_data={"changes": request.data},
        )
        fresh = self.get_queryset().get(pk=ticket.pk)
        return success_response(data=TicketSerializer(fresh).data, message=f"Ticket {ticket.display_id} mis à jour.")

    def destroy(self, request, *args, **kwargs):
        ticket = self.get_object()
        display_id = ticket.display_id
        ticket.delete()
        AuditTrail.log(
            action="ticket_delete", user=request.user, target_model="Ticket", target_id=ticket.id,
            ip_address=_get_client_ip(request),
        )
        return no_content_response(message=f"Ticket {display_id} supprimé.")

    @action(detail=True, methods=["get", "post"], url_path="comments")
    def comments(self, request, pk=None):
        """GET/POST /api/tickets/{id}/comments/"""
        ticket = self.get_object()

        if request.method == "GET":
            qs = ticket.comments.select_related("author").order_by("created_at")
            page = self.paginate_queryset(qs)
            if page is not None:
                serializer = TicketCommentSerializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            return success_response(data=TicketCommentSerializer(qs, many=True).data, message="Commentaires du ticket.")

        serializer = TicketCommentCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(message="Données invalides.", errors=serializer.errors)
        TicketComment.objects.create(ticket=ticket, author=request.user, content=serializer.validated_data["content"])
        TicketActivity.objects.create(ticket=ticket, actor=request.user, action="commented")

        fresh = self.get_queryset().get(pk=ticket.pk)
        return success_response(
            data=TicketSerializer(fresh).data, message="Commentaire ajouté.", http_status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="link-alert")
    def link_alert(self, request, pk=None):
        """
        POST /api/tickets/{id}/link-alert/ {"alert_id": "<uuid>"}
        Rattache une alerte supplémentaire au ticket (case management :
        regrouper plusieurs alertes corrélées d'un même incident).
        """
        from apps.alerts.models import Alert

        ticket = self.get_object()
        alert_id = request.data.get("alert_id")
        alert = Alert.objects.filter(id=alert_id, organization_id=request.user.organization_id).first()
        if not alert:
            return error_response(message="Alerte introuvable dans votre organisation.", http_status=status.HTTP_404_NOT_FOUND)

        ticket.linked_alerts.add(alert)
        TicketActivity.objects.create(
            ticket=ticket, actor=request.user, action="updated",
            to_value=f"Alerte liée : {alert.title[:100]}",
        )
        fresh = self.get_queryset().get(pk=ticket.pk)
        return success_response(data=TicketSerializer(fresh).data, message="Alerte liée au ticket.")

    @action(detail=True, methods=["post"], url_path="unlink-alert")
    def unlink_alert(self, request, pk=None):
        """POST /api/tickets/{id}/unlink-alert/ {"alert_id": "<uuid>"}"""
        ticket = self.get_object()
        alert_id = request.data.get("alert_id")
        removed = ticket.linked_alerts.filter(id=alert_id)
        alert_title = removed.first().title[:100] if removed.exists() else None
        ticket.linked_alerts.remove(*removed)
        if alert_title:
            TicketActivity.objects.create(
                ticket=ticket, actor=request.user, action="updated",
                to_value=f"Alerte déliée : {alert_title}",
            )
        fresh = self.get_queryset().get(pk=ticket.pk)
        return success_response(data=TicketSerializer(fresh).data, message="Alerte déliée du ticket.")

    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request):
        """GET /api/tickets/stats/ — Métriques de ticketing (scopées à l'organisation)."""
        org_id = request.user.organization_id
        tickets = Ticket.objects.filter(organization_id=org_id)

        by_status = tickets.values("status").annotate(count=Count("id"))
        by_priority = tickets.values("priority").annotate(count=Count("id"))

        resolved = tickets.filter(resolved_at__isnull=False)
        resolution_hours = [
            (t.resolved_at - t.created_at).total_seconds() / 3600 for t in resolved
        ]
        mttr_avg = round(sum(resolution_hours) / len(resolution_hours), 2) if resolution_hours else None

        overdue_count = tickets.filter(
            due_date__isnull=False, due_date__lt=timezone.now(),
        ).exclude(status__in=Ticket.CLOSED_STATUSES).count()

        unassigned_count = tickets.filter(
            assignee__isnull=True,
        ).exclude(status__in=Ticket.CLOSED_STATUSES).count()

        open_count = tickets.filter(status__in=Ticket.OPEN_STATUSES).count()

        return success_response(
            data={
                "by_status": {item["status"]: item["count"] for item in by_status},
                "by_priority": {item["priority"]: item["count"] for item in by_priority},
                "mttr_hours": mttr_avg,
                "overdue_count": overdue_count,
                "unassigned_count": unassigned_count,
                "open_count": open_count,
                "total": tickets.count(),
            },
            message="Statistiques des tickets.",
        )

    @action(detail=False, methods=["get"], url_path="assignable-users")
    def assignable_users(self, request):
        """
        GET /api/tickets/assignable-users/
        Liste légère des membres de l'organisation pour peupler le sélecteur
        d'assignation — /api/users/ (liste) est réservé à IsAdmin, ce qui
        empêcherait un simple analyst d'assigner un ticket à un collègue.
        """
        users = (
            User.objects
            .filter(organization_id=request.user.organization_id, is_active=True)
            .order_by("first_name", "last_name")
        )
        return success_response(
            data=TicketUserBriefSerializer(users, many=True).data,
            message="Membres assignables.",
        )
