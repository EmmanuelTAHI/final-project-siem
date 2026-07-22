"""
Référentiel de contrôles de conformité (ISO 27001, PCI DSS, NIST CSF, RGPD) et
matrice de couverture par organisation — pendant conformité de
`apps.correlation.mitre_attack`.

Contrairement aux rapports PDF générés à la demande (apps.reports.generators),
qui sont des instantanés ponctuels, cette matrice répond en continu à la
question « quels contrôles sont couverts par au moins une règle de détection
active, MAINTENANT ? » — c'est la différence entre de la conformité
documentaire et de la conformité opérationnelle continue.
"""

COMPLIANCE_CATALOG = {
    "iso27001": {
        "label": "ISO/IEC 27001:2022 — Annexe A",
        "controls": [
            {"id": "A.5.1", "title": "Politiques de sécurité de l'information"},
            {"id": "A.5.9", "title": "Inventaire des actifs informationnels"},
            {"id": "A.5.14", "title": "Transfert d'informations"},
            {"id": "A.5.15", "title": "Contrôle d'accès"},
            {"id": "A.5.16", "title": "Gestion des identités"},
            {"id": "A.5.17", "title": "Informations d'authentification"},
            {"id": "A.5.23", "title": "Sécurité des services cloud"},
            {"id": "A.5.25", "title": "Évaluation des événements de sécurité"},
            {"id": "A.5.26", "title": "Réponse aux incidents de sécurité"},
            {"id": "A.5.28", "title": "Collecte de preuves"},
            {"id": "A.5.36", "title": "Conformité aux politiques et normes"},
            {"id": "A.8.2", "title": "Droits d'accès privilégiés"},
            {"id": "A.8.12", "title": "Prévention de la fuite de données"},
            {"id": "A.8.15", "title": "Journalisation"},
            {"id": "A.8.16", "title": "Surveillance des activités"},
            {"id": "A.8.20", "title": "Sécurité des réseaux"},
        ],
    },
    "pci_dss": {
        "label": "PCI DSS v4.0",
        "controls": [
            {"id": "REQ-1", "title": "Contrôles de sécurité réseau"},
            {"id": "REQ-2", "title": "Configurations sécurisées par défaut"},
            {"id": "REQ-3", "title": "Protection des données de titulaires de carte stockées"},
            {"id": "REQ-7", "title": "Restriction de l'accès par besoin d'en connaître"},
            {"id": "REQ-8", "title": "Identification et authentification"},
            {"id": "REQ-10", "title": "Journalisation et surveillance de tous les accès"},
            {"id": "REQ-10.3", "title": "Revue des logs de sécurité"},
            {"id": "REQ-11", "title": "Tests réguliers des systèmes de sécurité"},
            {"id": "REQ-12", "title": "Politique de sécurité de l'information"},
        ],
    },
    "nist_csf": {
        "label": "NIST Cybersecurity Framework 2.0",
        "controls": [
            {"id": "ID.AM", "title": "Gestion des actifs (Identify)"},
            {"id": "PR.AC-1", "title": "Gestion des identités et des accès (Protect)"},
            {"id": "PR.AC-4", "title": "Gestion des permissions et autorisations"},
            {"id": "PR.DS", "title": "Sécurité des données (Protect)"},
            {"id": "DE.CM", "title": "Surveillance continue (Detect)"},
            {"id": "DE.AE", "title": "Anomalies et événements (Detect)"},
            {"id": "RS.RP", "title": "Planification de la réponse (Respond)"},
            {"id": "RS.AN", "title": "Analyse des incidents (Respond)"},
            {"id": "RC.RP", "title": "Planification de la reprise (Recover)"},
        ],
    },
    "gdpr": {
        "label": "RGPD (UE 2016/679)",
        "controls": [
            {"id": "Art.32", "title": "Sécurité du traitement"},
            {"id": "Art.33", "title": "Notification d'une violation de données"},
        ],
    },
}


def build_compliance_coverage(organization_id, framework: str) -> dict:
    """
    Matrice de couverture : pour chaque contrôle du référentiel, indique si
    une règle de corrélation active de l'organisation le couvre (via son
    champ `compliance_controls`, ex: "iso27001:A.5.15").
    """
    from apps.correlation.models import CorrelationRule

    catalog = COMPLIANCE_CATALOG.get(framework)
    if not catalog:
        return {}

    rules = CorrelationRule.objects.filter(organization_id=organization_id, is_active=True)
    covered_by: dict[str, list[str]] = {}
    for rule in rules:
        for entry in rule.compliance_controls or []:
            if ":" not in entry:
                continue
            fw, control_id = entry.split(":", 1)
            if fw == framework:
                covered_by.setdefault(control_id, []).append(rule.name)

    controls = []
    for control in catalog["controls"]:
        controls.append({
            **control,
            "covered": control["id"] in covered_by,
            "covering_rules": covered_by.get(control["id"], []),
        })

    covered_count = sum(1 for c in controls if c["covered"])
    return {
        "framework": framework,
        "label": catalog["label"],
        "controls": controls,
        "covered_count": covered_count,
        "total_count": len(controls),
        "coverage_percent": round((covered_count / len(controls)) * 100, 1) if controls else 0,
    }
