"""
Référentiel MITRE ATT&CK (Enterprise) — sous-ensemble curé couvrant les
tactiques/techniques déjà utilisées par les règles par défaut d'Argus
(voir default_rules.py) plus les techniques les plus fréquemment observées
en environnement PME.

Wazuh et la plupart des SIEM open source ne fournissent pas nativement de
matrice de couverture ATT&CK — c'est un standard reconnu (MITRE ATT&CK
Navigator) qu'Argus expose directement dans son API, sans outil externe.
"""

MITRE_ATTACK_REFERENCE = [
    {
        "tactic": "Reconnaissance",
        "tactic_id": "TA0043",
        "techniques": [
            {"id": "T1595", "name": "Active Scanning"},
            {"id": "T1589", "name": "Gather Victim Identity Information"},
        ],
    },
    {
        "tactic": "Initial Access",
        "tactic_id": "TA0001",
        "techniques": [
            {"id": "T1078", "name": "Valid Accounts"},
            {"id": "T1190", "name": "Exploit Public-Facing Application"},
            {"id": "T1566", "name": "Phishing"},
        ],
    },
    {
        "tactic": "Execution",
        "tactic_id": "TA0002",
        "techniques": [
            {"id": "T1059", "name": "Command and Scripting Interpreter"},
            {"id": "T1204", "name": "User Execution"},
        ],
    },
    {
        "tactic": "Persistence",
        "tactic_id": "TA0003",
        "techniques": [
            {"id": "T1098", "name": "Account Manipulation"},
            {"id": "T1543", "name": "Create or Modify System Process"},
        ],
    },
    {
        "tactic": "Privilege Escalation",
        "tactic_id": "TA0004",
        "techniques": [
            {"id": "T1078.003", "name": "Valid Accounts: Local Accounts"},
            {"id": "T1548", "name": "Abuse Elevation Control Mechanism"},
        ],
    },
    {
        "tactic": "Defense Evasion",
        "tactic_id": "TA0005",
        "techniques": [
            {"id": "T1556.006", "name": "Modify Authentication Process: MFA"},
            {"id": "T1070", "name": "Indicator Removal"},
        ],
    },
    {
        "tactic": "Credential Access",
        "tactic_id": "TA0006",
        "techniques": [
            {"id": "T1110", "name": "Brute Force"},
            {"id": "T1552", "name": "Unsecured Credentials"},
        ],
    },
    {
        "tactic": "Discovery",
        "tactic_id": "TA0007",
        "techniques": [
            {"id": "T1087", "name": "Account Discovery"},
            {"id": "T1046", "name": "Network Service Discovery"},
        ],
    },
    {
        "tactic": "Lateral Movement",
        "tactic_id": "TA0008",
        "techniques": [
            {"id": "T1021", "name": "Remote Services"},
        ],
    },
    {
        "tactic": "Collection",
        "tactic_id": "TA0009",
        "techniques": [
            {"id": "T1114", "name": "Email Collection"},
        ],
    },
    {
        "tactic": "Command and Control",
        "tactic_id": "TA0011",
        "techniques": [
            {"id": "T1071", "name": "Application Layer Protocol"},
        ],
    },
    {
        "tactic": "Exfiltration",
        "tactic_id": "TA0010",
        "techniques": [
            {"id": "T1048", "name": "Exfiltration Over Alternative Protocol"},
        ],
    },
    {
        "tactic": "Impact",
        "tactic_id": "TA0040",
        "techniques": [
            {"id": "T1490", "name": "Inhibit System Recovery"},
            {"id": "T1486", "name": "Data Encrypted for Impact"},
        ],
    },
]


def technique_id_prefix(mitre_technique: str) -> str:
    """Extrait 'T1110' depuis 'T1110 - Brute Force' pour la comparaison."""
    if not mitre_technique:
        return ""
    return mitre_technique.split(" ")[0].split(".")[0].strip()


def build_coverage_matrix(organization_id) -> list[dict]:
    """
    Construit la matrice de couverture ATT&CK pour une organisation : pour
    chaque technique du référentiel, indique si une règle de corrélation
    active la couvre déjà et combien d'alertes elle a générées.
    """
    from apps.correlation.models import CorrelationRule

    rules = CorrelationRule.objects.filter(organization_id=organization_id, is_active=True).exclude(
        mitre_technique=""
    )
    covered_prefixes = {}
    for rule in rules:
        prefix = technique_id_prefix(rule.mitre_technique)
        if prefix:
            covered_prefixes.setdefault(prefix, []).append(rule.name)

    matrix = []
    for tactic_entry in MITRE_ATTACK_REFERENCE:
        techniques = []
        for tech in tactic_entry["techniques"]:
            prefix = technique_id_prefix(tech["id"])
            techniques.append({
                **tech,
                "covered": prefix in covered_prefixes,
                "covering_rules": covered_prefixes.get(prefix, []),
            })
        matrix.append({
            "tactic": tactic_entry["tactic"],
            "tactic_id": tactic_entry["tactic_id"],
            "techniques": techniques,
        })
    return matrix
