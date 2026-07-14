"""
Normalisation des logs bruts vers le format CEF/LEEF.
Supporte Microsoft 365, Google Workspace, Wazuh, Syslog (dont auth SSH).
"""
import logging
import re
from datetime import datetime, timezone

from django.utils.dateparse import parse_datetime

from .models import NormalizedLog, RawLog

logger = logging.getLogger(__name__)

# ─── Motifs sshd (auth Linux) ────────────────────────────────────────────────
# "Failed password for admin from 1.2.3.4 port 40222 ssh2"
# "Failed password for invalid user root from 1.2.3.4 port 40222 ssh2"
_SSH_FAILED_RE = re.compile(
    r"Failed password for (?:invalid user )?(?P<user>\S+) from (?P<ip>[0-9a-fA-F:.]+)",
    re.IGNORECASE,
)
# "Invalid user oracle from 1.2.3.4 port 40222"
_SSH_INVALID_RE = re.compile(
    r"Invalid user (?P<user>\S+) from (?P<ip>[0-9a-fA-F:.]+)",
    re.IGNORECASE,
)
# "Accepted password for user from 1.2.3.4 port 40222 ssh2"
_SSH_ACCEPTED_RE = re.compile(
    r"Accepted (?:password|publickey) for (?P<user>\S+) from (?P<ip>[0-9a-fA-F:.]+)",
    re.IGNORECASE,
)
# PAM : "authentication failure; ... rhost=1.2.3.4 user=admin"
_PAM_FAIL_RE = re.compile(
    r"authentication failure;.*?(?:rhost=(?P<ip>[0-9a-fA-F:.]+))?.*?(?:user=(?P<user>\S+))?",
    re.IGNORECASE,
)


def _parse_ssh_auth(message: str) -> dict | None:
    """
    Détecte un évènement d'authentification SSH dans un message syslog et
    en extrait l'utilisateur, l'IP source réelle et l'issue (login_failure /
    login_success), pour alimenter les règles de corrélation (brute force).
    Retourne None si le message n'est pas un évènement d'auth reconnu.
    """
    if not message:
        return None

    m = _SSH_FAILED_RE.search(message) or _SSH_INVALID_RE.search(message)
    if m:
        return {"action": "login_failure", "outcome": "failure",
                "user": m.group("user"), "ip": m.group("ip")}

    m = _SSH_ACCEPTED_RE.search(message)
    if m:
        return {"action": "login_success", "outcome": "success",
                "user": m.group("user"), "ip": m.group("ip")}

    if "authentication failure" in message.lower():
        m = _PAM_FAIL_RE.search(message)
        if m:
            return {"action": "login_failure", "outcome": "failure",
                    "user": m.group("user"), "ip": m.group("ip")}

    return None


class LogNormalizer:
    """
    Normalise les logs bruts de différentes sources vers NormalizedLog.
    Applique le mapping spécifique à chaque source.
    """

    DISPATCHER = {
        "microsoft365": "_map_microsoft",
        "google_workspace": "_map_google",
        "wazuh": "_map_wazuh",
        "syslog": "_map_syslog",
        # Les agents (rsyslog/NXLog/Fluent Bit) poussent des lignes déjà
        # parsées au même format que parse_syslog_message() — même mapper.
        "agent": "_map_syslog",
    }

    def normalize(self, raw_log: RawLog) -> NormalizedLog | None:
        """
        Normalise un RawLog et crée un NormalizedLog en base.
        Retourne None si le log ne peut pas être normalisé.
        """
        if raw_log.is_normalized:
            logger.debug("RawLog %s déjà normalisé.", raw_log.id)
            return None

        source_type = raw_log.source_type
        mapper_name = self.DISPATCHER.get(source_type)

        if not mapper_name:
            logger.warning("Aucun mapper pour la source : %s", source_type)
            return None

        try:
            mapper = getattr(self, mapper_name)
            fields = mapper(raw_log.raw_data)
            fields["raw_log"] = raw_log
            fields["source_type"] = source_type

            normalized = NormalizedLog.objects.create(**fields)
            raw_log.is_normalized = True
            raw_log.save(update_fields=["is_normalized"])
            return normalized

        except Exception as exc:
            logger.exception("Erreur normalisation RawLog %s : %s", raw_log.id, exc)
            return None

    # ─── Microsoft 365 ────────────────────────────────────────────────────────

    def _map_microsoft(self, data: dict) -> dict:
        """Mappe un log de connexion Microsoft Graph API vers les champs NormalizedLog."""
        error_code = (data.get("status") or {}).get("errorCode", -1)
        is_success = error_code == 0

        location = data.get("location") or {}
        geo_coords = location.get("geoCoordinates") or {}

        # Validation IP
        source_ip = data.get("ipAddress") or None
        if source_ip == "":
            source_ip = None

        return {
            "event_time": self._parse_datetime(data.get("createdDateTime")),
            "user_email": data.get("userPrincipalName") or None,
            "user_id": data.get("userId") or None,
            "source_ip": source_ip,
            "destination_ip": None,
            "action": "login_success" if is_success else "login_failure",
            "outcome": "success" if is_success else "failure",
            "resource": data.get("appDisplayName") or None,
            "geo_country": location.get("countryOrRegion") or None,
            "geo_city": location.get("city") or None,
            "geo_latitude": geo_coords.get("latitude") or None,
            "geo_longitude": geo_coords.get("longitude") or None,
            "user_agent": data.get("userAgent") or None,
            "severity": "info" if is_success else "medium",
            "extra_fields": {
                "client_app_used": data.get("clientAppUsed"),
                "app_display_name": data.get("appDisplayName"),
                "conditional_access_status": data.get("conditionalAccessStatus"),
                "risk_detail": data.get("riskDetail"),
                "risk_level": data.get("riskLevelAggregated"),
                "error_code": error_code,
                "failure_reason": (data.get("status") or {}).get("failureReason"),
                "mfa_detail": data.get("mfaDetail"),
            },
        }

    # ─── Google Workspace ─────────────────────────────────────────────────────

    def _map_google(self, data: dict) -> dict:
        """Mappe un log Google Admin Reports API vers les champs NormalizedLog."""
        events = data.get("events") or [{}]
        first_event = events[0] if events else {}
        event_name = first_event.get("name", "unknown")

        SUCCESS_ACTIONS = {"login_success", "logout"}
        outcome = "success" if event_name in SUCCESS_ACTIONS else "failure"

        # Sévérité selon l'action
        severity = "info"
        if event_name in ("login_failure", "suspicious_login_blocked", "login_challenge"):
            severity = "medium"
        elif event_name in ("account_disabled_hijacked", "suspicious_programmatic_login"):
            severity = "high"

        actor = data.get("actor") or {}

        # Convertir les paramètres Google (liste clé/valeur) en dict
        params_list = first_event.get("parameters") or []
        extra_params = {}
        for param in params_list:
            key = param.get("name", "")
            value = param.get("value") or param.get("boolValue") or param.get("intValue")
            extra_params[key] = value

        id_block = data.get("id") or {}

        return {
            "event_time": self._parse_datetime(id_block.get("time")),
            "user_email": actor.get("email") or None,
            "user_id": actor.get("profileId") or None,
            "source_ip": data.get("ipAddress") or None,
            "destination_ip": None,
            "action": event_name,
            "outcome": outcome,
            "resource": id_block.get("applicationName") or None,
            "geo_country": None,
            "geo_city": None,
            "geo_latitude": None,
            "geo_longitude": None,
            "user_agent": None,
            "severity": severity,
            "extra_fields": {
                "application": id_block.get("applicationName"),
                "unique_qualifier": id_block.get("uniqueQualifier"),
                "parameters": extra_params,
                "events_count": len(events),
            },
        }

    # ─── Wazuh ────────────────────────────────────────────────────────────────

    def _map_wazuh(self, data: dict) -> dict:
        """Mappe une alerte Wazuh vers les champs NormalizedLog."""
        # La sévérité Wazuh est sur une échelle 0-15
        wazuh_level = int((data.get("rule") or {}).get("level", 5))
        if wazuh_level <= 4:
            severity = "info"
        elif wazuh_level <= 7:
            severity = "low"
        elif wazuh_level <= 10:
            severity = "medium"
        elif wazuh_level <= 13:
            severity = "high"
        else:
            severity = "critical"

        agent = data.get("agent") or {}
        src_ip = (data.get("data") or {}).get("srcip") or (data.get("data") or {}).get("src_ip")

        return {
            "event_time": self._parse_datetime(data.get("timestamp")),
            "user_email": (data.get("data") or {}).get("dstuser") or None,
            "user_id": agent.get("id") or None,
            "source_ip": src_ip or None,
            "destination_ip": (data.get("data") or {}).get("dstip") or None,
            "action": (data.get("rule") or {}).get("id", "wazuh_alert"),
            "outcome": "failure",
            "resource": agent.get("name") or None,
            "geo_country": None,
            "geo_city": None,
            "geo_latitude": None,
            "geo_longitude": None,
            "user_agent": None,
            "severity": severity,
            "extra_fields": {
                "wazuh_rule_id": (data.get("rule") or {}).get("id"),
                "wazuh_rule_description": (data.get("rule") or {}).get("description"),
                "wazuh_level": wazuh_level,
                "agent_name": agent.get("name"),
                "agent_ip": agent.get("ip"),
                "groups": (data.get("rule") or {}).get("groups", []),
            },
        }

    # ─── Syslog ──────────────────────────────────────────────────────────────

    def _map_syslog(self, data: dict) -> dict:
        """Mappe un log syslog parsé (par receive_syslog) vers les champs NormalizedLog."""
        severity = data.get("severity", "info")
        facility = data.get("facility", "unknown")
        message = data.get("message") or ""

        # IP source par défaut : celle de l'émetteur du paquet syslog.
        sender_ip = data.get("source_ip") or None

        # Détection d'un évènement d'authentification SSH → alimente la règle
        # brute force (action=login_failure groupé par user_email).
        ssh = _parse_ssh_auth(message)
        if ssh:
            attacker_ip = ssh.get("ip") or sender_ip
            user = ssh.get("user")
            # Une tentative sur un compte inexistant est plus sévère qu'un simple échec.
            sev = "high" if ssh["action"] == "login_failure" else severity
            return {
                "event_time": self._parse_datetime(data.get("received_at")),
                "user_email": user,
                "user_id": None,
                "source_ip": attacker_ip,
                "destination_ip": None,
                "action": ssh["action"],
                "outcome": ssh["outcome"],
                "resource": "ssh",
                "geo_country": None,
                "geo_city": None,
                "geo_latitude": None,
                "geo_longitude": None,
                "user_agent": None,
                "severity": sev,
                "extra_fields": {
                    "facility": facility,
                    "severity_code": data.get("severity_code"),
                    "message": message[:500],
                    "raw_message": data.get("raw_message", "")[:500],
                    "detected_service": "sshd",
                },
            }

        # outcome : les events d'auth/authpriv peuvent être failure, les autres sont unknown
        if facility in ("auth", "authpriv") and "fail" in message.lower():
            outcome = "failure"
        else:
            outcome = "unknown"

        return {
            "event_time": self._parse_datetime(data.get("received_at")),
            "user_email": None,
            "user_id": None,
            "source_ip": sender_ip,
            "destination_ip": None,
            "action": f"syslog_{facility}",
            "outcome": outcome,
            "resource": sender_ip,
            "geo_country": None,
            "geo_city": None,
            "geo_latitude": None,
            "geo_longitude": None,
            "user_agent": None,
            "severity": severity,
            "extra_fields": {
                "facility": facility,
                "severity_code": data.get("severity_code"),
                "message": message[:500],
                "raw_message": data.get("raw_message", "")[:500],
            },
        }

    # ─── Utilitaires ──────────────────────────────────────────────────────────

    @staticmethod
    def _parse_datetime(dt_str: str | None) -> datetime:
        """
        Parse une chaîne datetime ISO 8601 vers un objet datetime aware (UTC).
        Retourne maintenant() si la chaîne est invalide.
        """
        if not dt_str:
            from django.utils import timezone
            return timezone.now()
        try:
            parsed = parse_datetime(dt_str)
            if parsed and parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed or datetime.now(tz=timezone.utc)
        except (ValueError, TypeError):
            from django.utils import timezone
            return timezone.now()
