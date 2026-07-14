"""
Management command : récepteur syslog UDP.
Lance un serveur UDP sur SYSLOG_PORT pour recevoir les logs des équipements réseau
(firewalls, routeurs, switches, serveurs Linux) de la PME.

Usage Docker  : lancé automatiquement par le service 'syslog_receiver' dans docker-compose.yml
Usage manuel  : python manage.py receive_syslog [--port 5140]

Configuration réseau PME :
  - Les équipements doivent envoyer leur syslog vers l'IP du serveur SIEM, port 514 UDP.
  - Docker redirige le port 514 (hôte) vers 5140 (conteneur).
"""
import logging
import re
import select
import socket
import time
from datetime import datetime, timezone

from django.conf import settings
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)

# RFC 3164 : <priorité>message
SYSLOG_PRI_RE = re.compile(r"^<(\d+)>(.*)$", re.DOTALL)

# Niveau Wazuh (0-7) → sévérité SIEM
SEVERITY_MAP = {
    0: "critical",   # Emergency : système inutilisable
    1: "critical",   # Alert     : action immédiate requise
    2: "critical",   # Critical  : conditions critiques
    3: "high",       # Error     : conditions d'erreur
    4: "medium",     # Warning   : conditions d'avertissement
    5: "medium",     # Notice    : condition normale mais significative
    6: "low",        # Informational
    7: "info",       # Debug
}

FACILITY_MAP = {
    0: "kernel", 1: "user", 2: "mail", 3: "daemon", 4: "auth",
    5: "syslog", 6: "lpr", 7: "news", 8: "uucp", 9: "cron",
    10: "authpriv", 11: "ftp",
    16: "local0", 17: "local1", 18: "local2", 19: "local3",
    20: "local4", 21: "local5", 22: "local6", 23: "local7",
}


def parse_syslog_message(raw: str, source_ip: str) -> dict:
    """
    Parse un message syslog RFC 3164 en dict structuré.
    Extrait la priorité (facilité + sévérité) et le message brut.
    """
    data = {
        "raw_message": raw[:2000],  # limite taille
        "source_ip": source_ip,
        "received_at": datetime.now(tz=timezone.utc).isoformat(),
    }

    match = SYSLOG_PRI_RE.match(raw.strip())
    if match:
        priority = int(match.group(1))
        facility_code = priority >> 3
        severity_code = priority & 0x07
        data["facility"] = FACILITY_MAP.get(facility_code, f"facility_{facility_code}")
        data["severity_code"] = severity_code
        data["severity"] = SEVERITY_MAP.get(severity_code, "info")
        data["message"] = match.group(2).strip()
    else:
        data["message"] = raw.strip()
        data["facility"] = "unknown"
        data["severity_code"] = 6
        data["severity"] = "info"

    return data


class Command(BaseCommand):
    help = "Lance le récepteur syslog UDP (SYSLOG_PORT, défaut : 5140)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--host",
            default="0.0.0.0",
            help="Adresse IP d'écoute (défaut : 0.0.0.0)",
        )
        parser.add_argument(
            "--port",
            type=int,
            default=int(getattr(settings, "SYSLOG_PORT", 5140)),
            help="Port UDP d'écoute (défaut : 5140 — Docker mappe 514→5140)",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=50,
            help="Nombre de logs reçus avant déclenchement de la normalisation (défaut : 50)",
        )

    def handle(self, *args, **options):
        from django.conf import settings

        if not getattr(settings, "SYSLOG_RECEIVER_ENABLED", True):
            self.stdout.write(
                self.style.WARNING(
                    "SYSLOG_RECEIVER_ENABLED=False — récepteur syslog UDP désactivé "
                    "(profil SaaS : utilisez l'ingestion HTTP par token d'agent)."
                )
            )
            return

        host = options["host"]
        port = options["port"]
        batch_size = options["batch_size"]

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"[Syslog Receiver] Démarrage écoute UDP sur {host}:{port} "
                "— mode self-host : IP source vérifiée contre allowlist par connecteur."
            )
        )
        logger.warning(
            "receive_syslog : mode UDP non chiffré, non authentifié au-delà de "
            "l'allowlist IP. Réservé à un déploiement self-host mono-organisation "
            "sur réseau privé — jamais recommandé sur une instance SaaS mutualisée."
        )

        connectors = self._load_syslog_connectors()
        if not connectors:
            self.stderr.write(
                self.style.WARNING(
                    "Aucun connecteur syslog actif avec allowlist IP configurée. "
                    "Les paquets reçus seront ignorés jusqu'à configuration."
                )
            )

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError as exc:
            self.stderr.write(self.style.ERROR(f"Impossible de binder {host}:{port} — {exc}"))
            raise SystemExit(1)

        sock.setblocking(False)
        self.stdout.write(
            self.style.SUCCESS(f"Récepteur syslog actif — UDP {host}:{port}")
        )

        pending_by_connector = {}  # {connector_id: count}
        reload_counter = 0  # recharge la liste de connecteurs toutes les N itérations sans message
        # Flush temporel : normalise les logs en attente même sous le seuil de
        # batch, pour que les alertes (brute force…) sortent en quelques secondes
        # au lieu d'attendre l'accumulation de `batch_size` messages.
        FLUSH_INTERVAL = 5.0  # secondes
        RELOAD_INTERVAL = 30  # ~60s d'inactivité (2s de select() par itération)
        last_flush = time.monotonic()

        try:
            while True:
                readable, _, _ = select.select([sock], [], [], 2.0)

                # Flush périodique des logs en attente, connecteur par connecteur
                if pending_by_connector and (time.monotonic() - last_flush) >= FLUSH_INTERVAL:
                    for connector_id in list(pending_by_connector):
                        self._trigger_normalization(connector_id)
                    pending_by_connector.clear()
                    last_flush = time.monotonic()

                if not readable:
                    reload_counter += 1
                    if reload_counter % RELOAD_INTERVAL == 0:
                        connectors = self._load_syslog_connectors()
                    continue

                data_bytes, addr = sock.recvfrom(65535)
                source_ip = addr[0]

                try:
                    raw_message = data_bytes.decode("utf-8", errors="replace")
                except Exception:
                    raw_message = repr(data_bytes)

                parsed = parse_syslog_message(raw_message, source_ip)

                connector = self._resolve_connector_by_ip(connectors, source_ip)

                if connector:
                    self._store_raw_log(connector, parsed)
                    pending_by_connector[connector.id] = pending_by_connector.get(connector.id, 0) + 1
                    logger.debug(
                        "Syslog reçu de %s [%s] → connecteur %s : %s",
                        source_ip,
                        parsed.get("facility", "?"),
                        connector.name,
                        parsed.get("message", "")[:120],
                    )

                    if pending_by_connector[connector.id] >= batch_size:
                        self._trigger_normalization(connector.id)
                        pending_by_connector[connector.id] = 0
                        last_flush = time.monotonic()
                else:
                    # Aucune correspondance d'allowlist IP : le paquet est
                    # rejeté et JAMAIS rattaché arbitrairement à un connecteur
                    # (c'est exactement le bug corrigé par ce durcissement).
                    logger.warning(
                        "Syslog de %s rejeté — aucune allowlist IP ne correspond.",
                        source_ip,
                    )

        except KeyboardInterrupt:
            self.stdout.write("\nRécepteur syslog arrêté proprement.")
            logger.info("Récepteur syslog arrêté.")
        finally:
            sock.close()

    @staticmethod
    def _load_syslog_connectors():
        """
        Charge tous les connecteurs syslog actifs disposant d'une allowlist
        IP configurée (ceux sans allowlist sont ignorés : jamais de fallback
        global ambigu comme dans l'ancienne version).
        """
        from apps.collectors.models import ConnectorConfig
        return [
            c for c in ConnectorConfig.objects.filter(source_type="syslog", is_active=True)
            if c.allowed_source_ips
        ]

    @staticmethod
    def _resolve_connector_by_ip(connectors, source_ip: str):
        """
        Résout le connecteur dont l'allowlist contient `source_ip`. En cas de
        correspondances multiples (mauvaise config), rejette plutôt que de
        choisir arbitrairement — évite toute attribution ambiguë entre orgs.
        """
        import ipaddress

        try:
            ip = ipaddress.ip_address(source_ip)
        except ValueError:
            return None

        matches = []
        for connector in connectors:
            for entry in connector.allowed_source_ips:
                try:
                    if ip in ipaddress.ip_network(entry, strict=False):
                        matches.append(connector)
                        break
                except ValueError:
                    continue

        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            logger.error(
                "IP %s correspond à l'allowlist de plusieurs connecteurs (%s) — "
                "rejet pour éviter une attribution ambiguë entre organisations.",
                source_ip, [c.id for c in matches],
            )
        return None

    @staticmethod
    def _store_raw_log(connector, parsed: dict):
        """Stocke un log syslog parsé en RawLog."""
        from apps.logs.models import RawLog
        RawLog.objects.create(
            source_type="syslog",
            connector=connector,
            organization=connector.organization,
            raw_data=parsed,
        )

    @staticmethod
    def _trigger_normalization(connector_id):
        """Déclenche la normalisation des RawLog syslog en attente via Celery."""
        try:
            from apps.collectors.tasks import normalize_syslog_raw_logs
            normalize_syslog_raw_logs.delay(str(connector_id))
        except Exception as exc:
            logger.warning("Impossible de déclencher la normalisation syslog : %s", exc)
