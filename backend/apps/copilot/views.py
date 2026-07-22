"""
API SOC Copilot — question en langage naturel sur les données de sécurité de
l'organisation, et résumé d'incident généré par IA.
"""
import logging

from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet

from utils.permissions import IsAnalyst

from .models import CopilotConversation, CopilotMessage
from .serializers import CopilotConversationBriefSerializer, CopilotConversationSerializer
from .services import agent

logger = logging.getLogger(__name__)


class CopilotAskView(APIView):
    """
    POST /api/copilot/ask/
    Body: {"question": str, "conversation_id": uuid (optionnel)}
    """

    permission_classes = [IsAnalyst]

    def post(self, request):
        question = (request.data.get("question") or "").strip()
        if not question:
            return Response({"error": "question requise"}, status=status.HTTP_400_BAD_REQUEST)

        conversation_id = request.data.get("conversation_id")
        conversation = None
        history = []

        if conversation_id:
            conversation = CopilotConversation.objects.filter(
                id=conversation_id, organization_id=request.user.organization_id
            ).first()
            if conversation:
                for msg in conversation.messages.all().order_by("created_at"):
                    history.append({"role": msg.role, "content": msg.content})

        if conversation is None:
            conversation = CopilotConversation.objects.create(
                organization=request.user.organization,
                user=request.user,
                title=question[:120],
            )

        CopilotMessage.objects.create(conversation=conversation, role="user", content=question)

        result = agent.ask(question, request.user.organization_id, history=history)

        CopilotMessage.objects.create(
            conversation=conversation,
            role="assistant",
            content=result["answer"],
            tool_calls=result["tool_calls"],
        )
        conversation.save(update_fields=["updated_at"])

        return Response({
            "conversation_id": str(conversation.id),
            "answer": result["answer"],
            "tool_calls": result["tool_calls"],
            "configured": result["configured"],
        })


class CopilotConversationViewSet(ReadOnlyModelViewSet):
    queryset = CopilotConversation.objects.all()
    permission_classes = [IsAnalyst]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return CopilotConversationSerializer
        return CopilotConversationBriefSerializer

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)


class AlertSummarizeView(APIView):
    """POST /api/copilot/alerts/{id}/summarize/ — génère un résumé IA de l'alerte."""

    permission_classes = [IsAnalyst]

    def post(self, request, alert_id):
        from apps.alerts.models import Alert

        alert = Alert.objects.filter(id=alert_id, organization_id=request.user.organization_id).first()
        if not alert:
            return Response({"error": "Alerte introuvable"}, status=status.HTTP_404_NOT_FOUND)

        result = agent.summarize_alert(alert)
        alert.ai_summary = result["summary"]
        alert.ai_recommended_actions = result["recommended_actions"]
        alert.ai_summary_generated_at = timezone.now()
        alert.save(update_fields=["ai_summary", "ai_recommended_actions", "ai_summary_generated_at"])

        return Response({
            "summary": alert.ai_summary,
            "recommended_actions": alert.ai_recommended_actions,
            "generated_at": alert.ai_summary_generated_at,
        })
