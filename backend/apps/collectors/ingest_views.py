"""
Endpoint d'ingestion HTTP authentifié par token d'agent.

Remplace, pour le déploiement SaaS multi-tenant, le flux UDP syslog global
et non authentifié (receive_syslog) : ici, chaque requête est authentifiée
par un AgentEnrollmentToken (voir authentication.py), qui résout de façon
non ambiguë l'organisation et le connecteur — jamais par un ".first()"
global ou par une IP source seule.

Formats acceptés (Content-Type) :
- application/x-ndjson ou text/plain : une ligne = un événement.
  Chaque ligne peut être soit une ligne syslog brute (RFC 3164, ex. sortie
  rsyslog omfwd), soit un objet JSON {"message": "...", ...}.
- Content-Encoding: gzip accepté (batches compressés).

Réutilise exactement le format de dict produit par
apps.collectors.management.commands.receive_syslog.parse_syslog_message()
pour que apps.logs.normalizer.LogNormalizer._map_syslog (registre "agent")
s'applique sans modification.
"""
import gzip
import logging

from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.collectors.authentication import AgentTokenAuthentication
from apps.collectors.management.commands.receive_syslog import parse_syslog_message
from apps.collectors.models import ConnectorConfig
from apps.logs.models import RawLog
from utils.response import error_response, success_response

logger = logging.getLogger(__name__)

MAX_BATCH_LINES = 5000


class AgentLogIngestView(APIView):
    """
    POST /api/ingest/agent/logs/
    Authentification : Authorization: Bearer logplus_agt_<token>
    Corps : NDJSON (une ligne syslog ou un objet JSON par ligne).
    """

    # Volontairement PAS dans DEFAULT_AUTHENTICATION_CLASSES — voir authentication.py.
    authentication_classes = [AgentTokenAuthentication]
    # La vraie porte d'entrée est AgentTokenAuthentication (lève AuthenticationFailed
    # si le token est invalide) ; AllowAny ici évite un double contrôle IsAuthenticated
    # inadapté puisque request.user n'est jamais un vrai User sur cet endpoint.
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "agent_ingest"

    def post(self, request):
        principal = getattr(request, "user", None)
        token = getattr(principal, "token", None)
        if token is None:
            return error_response(message="Authentification requise.", http_status=401)

        organization = token.organization
        connector = self._resolve_connector(token)

        body = request.body
        if request.META.get("HTTP_CONTENT_ENCODING", "").lower() == "gzip":
            try:
                body = gzip.decompress(body)
            except OSError:
                return error_response(message="Corps gzip invalide.", http_status=400)

        try:
            text = body.decode("utf-8", errors="replace")
        except Exception:
            return error_response(message="Corps de requête illisible.", http_status=400)

        lines = [line for line in text.splitlines() if line.strip()]
        if not lines:
            return error_response(message="Aucune ligne de log dans le corps de la requête.", http_status=400)
        if len(lines) > MAX_BATCH_LINES:
            return error_response(
                message=f"Batch trop volumineux (max {MAX_BATCH_LINES} lignes par requête).",
                http_status=400,
            )

        source_ip = request.META.get("REMOTE_ADDR", "")
        raw_logs = []
        for line in lines:
            parsed = parse_syslog_message(line, source_ip)
            raw_logs.append(
                RawLog(
                    source_type="agent",
                    connector=connector,
                    organization=organization,
                    raw_data=parsed,
                )
            )

        RawLog.objects.bulk_create(raw_logs)

        connector.last_collected_at = timezone.now()
        connector.save(update_fields=["last_collected_at"])

        from apps.collectors.tasks import normalize_syslog_raw_logs
        normalize_syslog_raw_logs.delay(str(connector.id))

        return success_response(
            data={"accepted": len(raw_logs)},
            message="Logs reçus.",
            http_status=201,
        )

    @staticmethod
    def _resolve_connector(token) -> ConnectorConfig:
        """
        Résout (et crée si besoin) le ConnectorConfig associé au token.
        Jamais de lookup global : le connecteur vient exclusivement du token
        authentifié, ou en est créé un dédié au premier usage.
        """
        if token.connector_id:
            return token.connector

        connector = ConnectorConfig.objects.create(
            organization=token.organization,
            name=f"Agent — {token.name}",
            source_type="agent",
            is_active=True,
        )
        token.connector = connector
        token.save(update_fields=["connector"])
        return connector
