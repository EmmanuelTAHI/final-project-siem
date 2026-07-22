"""
Règles de corrélation par défaut, proposées à chaque nouvelle organisation.

Remplace l'ancien fixture global `fixtures/default_rules.json` (incompatible
avec le multi-tenant : les règles sont maintenant scopées par organisation,
donc il n'existe plus de jeu de PKs fixes valable pour toutes les orgs).
Utilisé à la création d'une organisation (voir
apps.authentication.views.RegisterView) et par la commande
`seed_default_rules` (pour les organisations existantes, ex. `legacy`).
"""
DEFAULT_RULES = [
    {
        "name": "Brute Force - Tentatives de connexion répétées",
        "description": "Détecte les tentatives de brute force en identifiant 5 échecs de connexion ou plus pour le même utilisateur dans une fenêtre de 5 minutes.",
        "severity": "high",
        "condition_logic": {
            "type": "threshold", "field": "user_email", "action": "login_failure",
            "count": 5, "window_seconds": 300,
        },
        "alert_title_template": "Tentative de brute force sur {user_email}",
        "mitre_tactic": "Credential Access",
        "mitre_technique": "T1110 - Brute Force",
        "compliance_controls": ["iso27001:A.5.15", "pci_dss:REQ-8", "nist_csf:PR.AC-1"],
    },
    {
        "name": "Impossible Travel - Connexion depuis deux pays simultanément",
        "description": "Détecte une connexion réussie depuis deux pays géographiquement distincts en moins de 2 heures, physiquement impossible sans voyage supersonique.",
        "severity": "critical",
        "condition_logic": {"type": "impossible_travel", "window_seconds": 7200},
        "alert_title_template": "Connexion impossible depuis {country_1} et {country_2} pour {user_email}",
        "mitre_tactic": "Initial Access",
        "mitre_technique": "T1078 - Valid Accounts",
        "compliance_controls": ["iso27001:A.5.15", "iso27001:A.8.16", "nist_csf:DE.CM"],
    },
    {
        "name": "Off-Hours Login - Connexion hors horaires de bureau",
        "description": "Détecte les connexions réussies effectuées entre 20h00 et 07h00 UTC, en dehors des horaires de bureau habituels.",
        "severity": "medium",
        "condition_logic": {
            "type": "time_based", "action": "login_success",
            "forbidden_hours_start": 20, "forbidden_hours_end": 7,
        },
        "alert_title_template": "Connexion hors horaires pour {user_email} à {hour_utc}h UTC",
        "mitre_tactic": "Initial Access",
        "mitre_technique": "T1078 - Valid Accounts",
        "compliance_controls": ["iso27001:A.8.16", "nist_csf:DE.CM"],
    },
    {
        "name": "Privilege Escalation - Élévation de privilèges détectée",
        "description": "Détecte les tentatives d'élévation de privilèges vers des rôles administrateurs via les actions privilege_change et role_assigned.",
        "severity": "high",
        "condition_logic": {
            "type": "privilege_escalation",
            "actions": ["privilege_change", "role_assigned", "admin_role_assigned"],
            "admin_keywords": ["admin", "administrator", "global", "superuser"],
        },
        "alert_title_template": "Élévation de privilèges détectée pour {user_email}",
        "mitre_tactic": "Privilege Escalation",
        "mitre_technique": "T1078.003 - Local Accounts",
        "compliance_controls": ["iso27001:A.5.15", "iso27001:A.8.2", "pci_dss:REQ-7", "nist_csf:PR.AC-4"],
    },
    {
        "name": "MFA Bypass - Contournement de l'authentification multi-facteurs",
        "description": "Détecte les connexions réussies sans utilisation du MFA (authMethod=null) ou avec un bypass explicite (MFA bypassed).",
        "severity": "critical",
        "condition_logic": {
            "type": "mfa_bypass",
            "bypass_indicators": ["MFA bypassed", "MFA skipped", "MfaSkipped"],
        },
        "alert_title_template": "Contournement MFA détecté pour {user_email}",
        "mitre_tactic": "Defense Evasion",
        "mitre_technique": "T1556.006 - Disable or Modify Cloud Firewall",
        "compliance_controls": ["iso27001:A.5.17", "pci_dss:REQ-8", "nist_csf:PR.AC-1"],
    },
    {
        "name": "Connexions suspectes bloquées répétées",
        "description": "Détecte 3 blocages de connexions suspectes ou plus pour le même utilisateur dans une fenêtre de 30 minutes (impossible travel, IP à risque, etc. bloqués automatiquement).",
        "severity": "high",
        "condition_logic": {
            "type": "threshold", "field": "user_email", "action": "suspicious_login_blocked",
            "count": 3, "window_seconds": 1800,
        },
        "alert_title_template": "Connexions suspectes répétées bloquées pour {user_email}",
        "mitre_tactic": "Credential Access",
        "mitre_technique": "T1110 - Brute Force",
        "compliance_controls": ["iso27001:A.5.15", "nist_csf:PR.AC-1"],
    },
    {
        "name": "Compte compromis - Désactivation automatique répétée",
        "description": "Détecte 2 désactivations automatiques de compte (réponse à un piratage) ou plus pour le même utilisateur dans une fenêtre de 24 heures, signe d'une compromission persistante.",
        "severity": "critical",
        "condition_logic": {
            "type": "threshold", "field": "user_email", "action": "account_disabled_hijacked",
            "count": 2, "window_seconds": 86400,
        },
        "alert_title_template": "Compromission persistante détectée sur le compte {user_email}",
        "mitre_tactic": "Persistence",
        "mitre_technique": "T1098 - Account Manipulation",
        "compliance_controls": ["iso27001:A.5.15", "iso27001:A.5.26", "nist_csf:RS.AN"],
    },
    {
        "name": "Wazuh Critical - Activité système critique (level >= 12)",
        "description": "Détecte les alertes Wazuh de niveau critique (level >= 12) : dump LSASS, ransomware, effacement de logs, exécution PowerShell malveillante.",
        "severity": "critical",
        "condition_logic": {
            "type": "wazuh_alert", "min_wazuh_level": 12,
            "wazuh_rule_ids": ["100002", "100005", "100006", "100010", "100014", "100015", "60106", "91554"],
        },
        "alert_title_template": "Wazuh CRITICAL [{wazuh_level}] {wazuh_rule_description} — {source_ip}",
        "mitre_tactic": "Execution",
        "mitre_technique": "T1059 - Command and Scripting Interpreter",
        "compliance_controls": ["iso27001:A.8.16", "pci_dss:REQ-10", "nist_csf:DE.CM"],
    },
    {
        "name": "Wazuh High - Escalade de privilèges système (level >= 9)",
        "description": "Détecte les alertes Wazuh de niveau élevé (level >= 9) : accès fichiers sensibles, processus suspects, modifications de registre, services malveillants.",
        "severity": "high",
        "condition_logic": {
            "type": "wazuh_alert", "min_wazuh_level": 9,
            "wazuh_rule_ids": ["100003", "100007", "100008", "100011", "100013", "5710", "18107"],
        },
        "alert_title_template": "Wazuh HIGH [{wazuh_level}] {wazuh_rule_description} — {source_ip}",
        "mitre_tactic": "Privilege Escalation",
        "mitre_technique": "T1548 - Abuse Elevation Control Mechanism",
        "compliance_controls": ["iso27001:A.8.16", "nist_csf:DE.CM"],
    },
    {
        "name": "Mouvement Latéral - Connexions multi-hôtes suspectes",
        "description": "Détecte un mouvement latéral lorsqu'une même IP source se connecte à 3 hôtes distincts ou plus via SMB, RDP ou SSH dans une fenêtre de 5 minutes.",
        "severity": "high",
        "condition_logic": {
            "type": "lateral_movement", "min_distinct_hosts": 3, "window_seconds": 300,
            "actions": ["smb_connect", "rdp_connect", "ssh_connect", "network_scan", "wmi_exec"],
        },
        "alert_title_template": "Mouvement latéral : {source_ip} -> {distinct_hosts_count} hôtes en {window_seconds}s",
        "mitre_tactic": "Lateral Movement",
        "mitre_technique": "T1021 - Remote Services",
        "compliance_controls": ["iso27001:A.8.20", "nist_csf:DE.CM"],
    },
    {
        "name": "C2 Beaconing - Communication régulière vers C&C",
        "description": "Détecte des communications C2 par analyse du beaconing : connexions sortantes périodiques avec faible variation d'intervalle (jitter < 30%).",
        "severity": "critical",
        "condition_logic": {
            "type": "c2_beacon", "min_beacons": 5, "window_seconds": 3600, "max_jitter_ratio": 0.3,
            "actions": ["dns_query", "http_request", "https_request", "outbound_connection", "c2_beacon"],
        },
        "alert_title_template": "Beacon C2 détecté : {source_ip} -> {destination} ({beacon_count} connexions, jitter={jitter_ratio})",
        "mitre_tactic": "Command and Control",
        "mitre_technique": "T1071 - Application Layer Protocol",
        "compliance_controls": ["iso27001:A.8.16", "nist_csf:DE.CM"],
    },
    {
        "name": "Exfiltration - Transfert de données massif",
        "description": "Détecte une exfiltration de données via actions de transfert anormales : uploads massifs, DNS tunneling, écriture USB, archivage et envoi vers l'extérieur.",
        "severity": "critical",
        "condition_logic": {
            "type": "data_exfil", "min_events": 5, "window_seconds": 600,
            "actions": ["data_exfil", "dns_exfil", "file_upload", "large_transfer", "email_forward", "archive_created", "usb_write"],
        },
        "alert_title_template": "Exfiltration de données : {source_ip} — {event_count} événements en {window_seconds}s",
        "mitre_tactic": "Exfiltration",
        "mitre_technique": "T1048 - Exfiltration Over Alternative Protocol",
        "compliance_controls": ["iso27001:A.5.14", "iso27001:A.8.12", "pci_dss:REQ-3", "gdpr:Art.32"],
    },
]


def seed_default_rules_for_organization(organization) -> int:
    """
    Crée les règles par défaut pour `organization` si elles n'existent pas
    déjà (idempotent, matché sur le nom — unique par organisation). Retourne
    le nombre de règles créées.
    """
    from apps.correlation.models import CorrelationRule

    existing_names = set(
        CorrelationRule.objects.filter(organization=organization).values_list("name", flat=True)
    )
    to_create = [
        CorrelationRule(organization=organization, **rule)
        for rule in DEFAULT_RULES
        if rule["name"] not in existing_names
    ]
    if to_create:
        CorrelationRule.objects.bulk_create(to_create)
    return len(to_create)
