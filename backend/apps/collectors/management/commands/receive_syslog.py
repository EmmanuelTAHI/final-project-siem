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
        host = options["host"]
        port = options["port"]
        batch_size = options["batch_size"]

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"[Syslog Receiver] Démarrage écoute UDP sur {host}:{port}"
            )
        )
        logger.info("Récepteur syslog démarré sur %s:%d", host, port)

        # Charger le connecteur syslog actif (sera rechargé si absent)
        connector = self._load_connector()
        if not connector:
            self.stderr.write(
                self.style.WARNING(
                    "Aucun connecteur syslog actif en base. "
                    "Créez-en un depuis l'interface → Collectors. "
                    "Les logs reçus seront ignorés jusqu'à création du connecteur."
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

        buffer_count = 0
        reload_counter = 0  # recharge le connecteur toutes les N itérations sans message
        # Flush temporel : normalise les logs en attente même sous le seuil de
        # batch, pour que les alertes (brute force…) sortent en quelques secondes
        # au lieu d'attendre l'accumulation de `batch_size` messages.
        FLUSH_INTERVAL = 5.0  # secondes
        last_flush = time.monotonic()

        try:
            while True:
                readable, _, _ = select.select([sock], [], [], 2.0)

                # Flush périodique des logs en attente
                if buffer_count > 0 and (time.monotonic() - last_flush) >= FLUSH_INTERVAL:
                    self._trigger_normalization(connector)
                    buffer_count = 0
                    last_flush = time.monotonic()

                if not readable:
                    reload_counter += 1
                    # Recharger le connecteur toutes les ~60s si absent
                    if not connector and reload_counter % 30 == 0:
                        connector = self._load_connector()
                        if connector:
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"Connecteur syslog chargé : {connector.name}"
                                )
                            )
                    continue

                data_bytes, addr = sock.recvfrom(65535)
                source_ip = addr[0]

                try:
                    raw_message = data_bytes.decode("utf-8", errors="replace")
                except Exception:
                    raw_message = repr(data_bytes)

                parsed = parse_syslog_message(raw_message, source_ip)

                # Recharger le connecteur si nécessaire
                if not connector:
                    connector = self._load_connector()

                if connector:
                    self._store_raw_log(connector, parsed)
                    buffer_count += 1
                    logger.debug(
                        "Syslog reçu de %s [%s] : %s",
                        source_ip,
                        parsed.get("facility", "?"),
                        parsed.get("message", "")[:120],
                    )

                    # Déclencher la normalisation dès le batch atteint
                    if buffer_count >= batch_size:
                        self._trigger_normalization(connector)
                        buffer_count = 0
                        last_flush = time.monotonic()
                else:
                    logger.debug(
                        "Log syslog de %s ignoré — pas de connecteur syslog actif.",
                        source_ip,
                    )

        except KeyboardInterrupt:
            self.stdout.write("\nRécepteur syslog arrêté proprement.")
            logger.info("Récepteur syslog arrêté.")
        finally:
            sock.close()

    @staticmethod
    def _load_connector():
        """Charge le premier connecteur syslog actif depuis la BDD."""
        from apps.collectors.models import ConnectorConfig
        return ConnectorConfig.objects.filter(
            source_type="syslog",
            is_active=True,
        ).first()

    @staticmethod
    def _store_raw_log(connector, parsed: dict):
        """Stocke un log syslog parsé en RawLog."""
        from apps.logs.models import RawLog
        RawLog.objects.create(
            source_type="syslog",
            connector=connector,
            raw_data=parsed,
        )

    @staticmethod
    def _trigger_normalization(connector):
        """Déclenche la normalisation des RawLog syslog en attente via Celery."""
        try:
            from apps.collectors.tasks import normalize_syslog_raw_logs
            normalize_syslog_raw_logs.delay(str(connector.id))
        except Exception as exc:
            logger.warning("Impossible de déclencher la normalisation syslog : %s", exc)
