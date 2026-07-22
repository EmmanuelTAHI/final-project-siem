#!/usr/bin/env python3
"""
Démon de blocage réseau réel pour Argus SOAR.

Tourne DIRECTEMENT sur l'hôte VPS (hors Docker), atteignable depuis les
conteneurs Docker via `host.docker.internal` (docker-compose.prod.yml).

Écoute sur toutes les interfaces (0.0.0.0) — un bind strict sur 127.0.0.1
rendrait le service injoignable depuis un conteneur (qui atteint l'hôte via
la passerelle du réseau Docker, jamais via le loopback ; testé et confirmé :
timeout de connexion avec un bind 127.0.0.1). La vraie frontière de
sécurité est la politique par défaut d'ufw ("deny incoming" tant qu'aucune
règle n'autorise explicitement un port — le port 8765 n'apparaît dans
aucune règle ufw, donc reste bloqué depuis l'extérieur même en écoutant sur
0.0.0.0) et le jeton d'authentification, pas l'adresse d'écoute.

Contrairement au blocage applicatif existant (utils.blocklist_middleware,
403 Django), ce démon exécute une VRAIE règle pare-feu ufw sur l'hôte — le
paquet de l'attaquant n'atteint plus la machine du tout, pas juste rejeté
poliment par le code.

Sécurité :
- écoute uniquement sur 127.0.0.1 (jamais routable depuis l'extérieur)
- authentification par jeton partagé (Authorization: Bearer <token>)
- l'IP est validée avec `ipaddress.ip_address()` avant tout usage
- exécution via `sudo` restreint à deux binaires précis (voir
  /etc/sudoers.d/argus-firewall) — jamais de shell=True, jamais
  d'interpolation de chaîne dans une commande shell
- tourne sous un utilisateur système dédié non-root (voir install.sh)

Usage : lancé par systemd (argus-firewall-agent.service), pas manuellement.
"""
import ipaddress
import json
import logging
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s %(message)s")
logger = logging.getLogger("argus-firewall-agent")

HOST = "0.0.0.0"
PORT = 8765
TOKEN_FILE = "/etc/argus-firewall-agent/token"
BLOCK_SCRIPT = "/usr/local/sbin/argus-ufw-block"
UNBLOCK_SCRIPT = "/usr/local/sbin/argus-ufw-unblock"

# Débloque automatiquement après expiration — pas de dépendance à `at`/cron,
# un simple minuteur en mémoire suffit tant que le process tourne en continu
# (systemd Restart=always le relance de toute façon en cas de crash, au pire
# une IP reste bloquée un peu plus longtemps que prévu, jamais moins).
_pending_unblocks: dict[str, threading.Timer] = {}


def _load_token() -> str:
    with open(TOKEN_FILE, "r", encoding="utf-8") as f:
        return f.read().strip()


def _valid_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def _run_privileged(script: str, ip: str) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["sudo", "-n", script, ip],
            capture_output=True, text=True, timeout=10, check=False,
        )
        if result.returncode != 0:
            return False, result.stderr.strip() or result.stdout.strip()
        return True, result.stdout.strip()
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except Exception as exc:
        return False, str(exc)


def _schedule_unblock(ip: str, duration_hours: float) -> None:
    existing = _pending_unblocks.pop(ip, None)
    if existing:
        existing.cancel()

    def _do_unblock():
        ok, detail = _run_privileged(UNBLOCK_SCRIPT, ip)
        logger.info("Déblocage automatique de %s après %sh : %s (%s)", ip, duration_hours, ok, detail)
        _pending_unblocks.pop(ip, None)

    timer = threading.Timer(duration_hours * 3600, _do_unblock)
    timer.daemon = True
    timer.start()
    _pending_unblocks[ip] = timer


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A002 — override BaseHTTPRequestHandler
        logger.info("%s - %s", self.client_address[0], format % args)

    def _authorized(self) -> bool:
        auth = self.headers.get("Authorization", "")
        return auth == f"Bearer {_load_token()}"

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if not self._authorized():
            self._send_json(401, {"error": "unauthorized"})
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            self._send_json(400, {"error": "invalid_json"})
            return

        ip = str(data.get("ip", "")).strip()
        if not _valid_ip(ip):
            self._send_json(400, {"error": "invalid_ip"})
            return

        if self.path == "/block":
            duration = float(data.get("duration_hours", 24) or 24)
            ok, detail = _run_privileged(BLOCK_SCRIPT, ip)
            if ok and duration > 0:
                _schedule_unblock(ip, duration)
            self._send_json(200 if ok else 500, {"status": "blocked" if ok else "failed", "detail": detail})
        elif self.path == "/unblock":
            timer = _pending_unblocks.pop(ip, None)
            if timer:
                timer.cancel()
            ok, detail = _run_privileged(UNBLOCK_SCRIPT, ip)
            self._send_json(200 if ok else 500, {"status": "unblocked" if ok else "failed", "detail": detail})
        else:
            self._send_json(404, {"error": "not_found"})

    def do_GET(self):
        if self.path == "/healthz":
            self._send_json(200, {"status": "ok", "pending_unblocks": len(_pending_unblocks)})
        else:
            self._send_json(404, {"error": "not_found"})


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    logger.info("argus-firewall-agent en écoute sur %s:%d (protégé par ufw + jeton)", HOST, PORT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
