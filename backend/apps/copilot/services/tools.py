"""
Outils ("tools") exposés au SOC Copilot pour interroger les données réelles
de l'organisation. L'IA ne reçoit JAMAIS d'accès direct à la base — elle ne
peut qu'appeler ces fonctions, toujours filtrées côté serveur par
`organization_id` (jamais fourni par le modèle, toujours par la session
authentifiée). Les résultats sont plafonnés pour rester dans le budget de
tokens et éviter toute fuite massive de données brutes vers le fournisseur
d'IA — seuls des agrégats/extraits contrôlés transitent.
"""
from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

TOOL_SCHEMAS = [
    {
        "name": "query_logs",
        "description": (
            "Recherche dans les logs normalisés de l'organisation. Utilise ceci pour "
            "répondre à des questions sur des événements précis (connexions, IP, pays, "
            "actions)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source_ip": {"type": "string", "description": "Filtrer par IP source exacte"},
                "user_email": {"type": "string", "description": "Filtrer par email utilisateur (contient)"},
                "action": {"type": "string", "description": "Filtrer par action (ex: login_failure, login_success)"},
                "geo_country": {"type": "string", "description": "Code pays ISO 3166-1 alpha-2 (ex: RU, CN)"},
                "since_hours": {"type": "integer", "description": "Ne considérer que les logs des N dernières heures (défaut 24)"},
                "limit": {"type": "integer", "description": "Nombre max de résultats (défaut 15, max 50)"},
            },
        },
    },
    {
        "name": "query_alerts",
        "description": "Recherche dans les alertes SOC de l'organisation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "severity": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
                "status": {"type": "string", "enum": ["open", "in_progress", "resolved", "false_positive"]},
                "since_hours": {"type": "integer", "description": "Ne considérer que les alertes des N dernières heures"},
                "limit": {"type": "integer", "description": "Nombre max de résultats (défaut 15, max 50)"},
            },
        },
    },
    {
        "name": "lookup_threat_indicator",
        "description": "Vérifie la réputation CTI connue d'une IP, d'un domaine ou d'un hash dans le référentiel Argus.",
        "input_schema": {
            "type": "object",
            "properties": {"value": {"type": "string", "description": "IP, domaine ou hash à rechercher"}},
            "required": ["value"],
        },
    },
    {
        "name": "get_organization_stats",
        "description": "Retourne des statistiques agrégées globales (nombre d'alertes par sévérité, actifs vulnérables, etc.) pour l'organisation.",
        "input_schema": {"type": "object", "properties": {}},
    },
]


def _clamp_limit(value, default=15, hard_max=50):
    try:
        value = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(value, hard_max))


def execute_tool(name: str, tool_input: dict, organization_id) -> dict:
    """Exécute un outil, toujours scopé à `organization_id` (jamais celui fourni par l'IA)."""
    if name == "query_logs":
        return _query_logs(tool_input, organization_id)
    if name == "query_alerts":
        return _query_alerts(tool_input, organization_id)
    if name == "lookup_threat_indicator":
        return _lookup_threat_indicator(tool_input)
    if name == "get_organization_stats":
        return _get_organization_stats(organization_id)
    return {"error": f"Outil inconnu: {name}"}


def _query_logs(tool_input: dict, organization_id) -> dict:
    from apps.logs.models import NormalizedLog

    qs = NormalizedLog.objects.filter(organization_id=organization_id)
    since_hours = tool_input.get("since_hours", 24)
    qs = qs.filter(event_time__gte=timezone.now() - timedelta(hours=int(since_hours or 24)))

    if tool_input.get("source_ip"):
        qs = qs.filter(source_ip=tool_input["source_ip"])
    if tool_input.get("user_email"):
        qs = qs.filter(user_email__icontains=tool_input["user_email"])
    if tool_input.get("action"):
        qs = qs.filter(action=tool_input["action"])
    if tool_input.get("geo_country"):
        qs = qs.filter(geo_country__iexact=tool_input["geo_country"])

    limit = _clamp_limit(tool_input.get("limit"))
    total = qs.count()
    rows = list(
        qs.order_by("-event_time").values(
            "event_time", "source_ip", "user_email", "action", "outcome", "geo_country", "severity",
        )[:limit]
    )
    for row in rows:
        row["event_time"] = row["event_time"].isoformat() if row["event_time"] else None
    return {"total_matching": total, "results": rows}


def _query_alerts(tool_input: dict, organization_id) -> dict:
    from apps.alerts.models import Alert

    qs = Alert.objects.filter(organization_id=organization_id)
    since_hours = tool_input.get("since_hours")
    if since_hours:
        qs = qs.filter(created_at__gte=timezone.now() - timedelta(hours=int(since_hours)))
    if tool_input.get("severity"):
        qs = qs.filter(severity=tool_input["severity"])
    if tool_input.get("status"):
        qs = qs.filter(status=tool_input["status"])

    limit = _clamp_limit(tool_input.get("limit"))
    total = qs.count()
    rows = list(
        qs.order_by("-created_at").values(
            "id", "title", "severity", "status", "created_at",
        )[:limit]
    )
    for row in rows:
        row["id"] = str(row["id"])
        row["created_at"] = row["created_at"].isoformat() if row["created_at"] else None
    return {"total_matching": total, "results": rows}


def _lookup_threat_indicator(tool_input: dict) -> dict:
    from apps.threat_intel.models import ThreatIndicator

    value = (tool_input.get("value") or "").strip()
    if not value:
        return {"error": "value requis"}
    indicators = list(
        ThreatIndicator.objects.filter(value=value).values(
            "indicator_type", "source", "reputation_score", "is_malicious", "tags",
        )
    )
    return {"value": value, "indicators": indicators}


def _get_organization_stats(organization_id) -> dict:
    from apps.alerts.models import Alert
    from apps.threat_intel.models import Asset, AssetVulnerability

    alerts = Alert.objects.filter(organization_id=organization_id)
    return {
        "alerts_open": alerts.filter(status="open").count(),
        "alerts_critical_open": alerts.filter(status="open", severity="critical").count(),
        "alerts_by_severity": list(
            alerts.filter(status__in=["open", "in_progress"])
            .values("severity")
            .annotate(count=Count("id"))
        ),
        "assets_total": Asset.objects.filter(organization_id=organization_id).count(),
        "asset_vulnerabilities_open": AssetVulnerability.objects.filter(
            organization_id=organization_id, status="open"
        ).count(),
        "asset_vulnerabilities_kev": AssetVulnerability.objects.filter(
            organization_id=organization_id, status="open", cve__is_kev=True
        ).count(),
    }
