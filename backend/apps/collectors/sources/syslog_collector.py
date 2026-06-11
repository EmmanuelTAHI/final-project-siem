"""
Collecteur Syslog (UDP RFC 3164 / RFC 5424).
Mode PUSH : les équipements réseau (firewall, switch, routeur) envoient leurs logs au SIEM.
La réception réelle se fait via le management command 'receive_syslog'.
Cette classe fournit test_connection() et les stubs requis par BaseCollector.
"""
import logging
import socket
import time
from typing import Generator

from .base_collector import BaseCollector

logger = logging.getLogger(__name__)


class SyslogCollector(BaseCollector):
    """
    Pour le syslog, la collecte est push-based (les équipements envoient les logs).
    fetch_logs() ne s'applique pas — la réception se fait via 'receive_syslog'.
    normalize_all() reste fonctionnel pour normaliser les RawLog déjà stockés.
    """

    def fetch_logs(self) -> Generator[dict, None, None]:
        """Le syslog est push-based — pas de polling. Toujours vide."""
        return
        yield  # noqa: rend la méthode génératrice sans rien émettre

    def test_connection(self) -> dict:
        """
        Vérifie si le port syslog est accessible en tentant un bind UDP.
        - Port libre → le receiver peut démarrer
        - Port occupé (EADDRINUSE) → le receiver tourne déjà (bon signe)
        """
        from django.conf import settings

        port = int(getattr(settings, "SYSLOG_PORT", 5140))
        start = time.time()
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("0.0.0.0", port))
            sock.close()
            latency_ms = (time.time() - start) * 1000
            return {
                "reachable": True,
                "latency_ms": round(latency_ms, 2),
                "message": f"Port UDP {port} disponible — receiver syslog prêt à démarrer.",
            }
        except OSError as exc:
            latency_ms = (time.time() - start) * 1000
            if exc.errno in (98, 10048):  # EADDRINUSE (Linux / Windows)
                return {
                    "reachable": True,
                    "latency_ms": round(latency_ms, 2),
                    "message": f"Port UDP {port} déjà en écoute — receiver syslog actif.",
                }
            return {
                "reachable": False,
                "latency_ms": round(latency_ms, 2),
                "message": str(exc),
            }
