"""
Tâches Celery — enrichissement CTI des logs normalisés.
"""
import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="apps.threat_intel.tasks.enrich_logs_with_cti")
def enrich_logs_with_cti():
    """
    Enrichit les NormalizedLog récents avec les données CTI (AbuseIPDB + VirusTotal).
    Traite les logs des dernières 2 heures non encore enrichis.
    """
    from apps.logs.models import NormalizedLog
    from apps.threat_intel.models import EnrichedLog, ThreatIndicator
    from apps.threat_intel.services import abuseipdb, ip_enrichment, virustotal

    cutoff = timezone.now() - timedelta(hours=2)
    enriched_ids = EnrichedLog.objects.values_list("log_id", flat=True)
    logs = list(
        NormalizedLog.objects.filter(indexed_at__gte=cutoff, source_ip__isnull=False)
        .exclude(id__in=enriched_ids)
        .select_related()[:200]
    )

    # Une IP attaquante apparaît souvent dans des dizaines de logs sur la même
    # fenêtre (brute force). Sans déduplication, on interrogeait les APIs
    # externes une fois PAR LOG au lieu d'une fois par IP — le quota gratuit
    # VirusTotal (4 req/min) était grillé en quelques secondes (429), et la
    # quasi-totalité des enrichissements échouaient silencieusement.
    unique_ips = {log.source_ip for log in logs if log.source_ip}
    indicators_by_ip: dict[str, list] = {}
    geo_tagged = 0

    for ip in unique_ips:
        indicators = []

        # Géolocalisation (ip-api.com, gratuite) — les logs syslog/agent (SSH,
        # nginx...) n'ont jamais de geo_country renseigné par le normaliseur
        # (contrairement à M365/Google qui le fournissent déjà). On comble ce
        # trou ICI, au moment où l'IP est de toute façon déjà interrogée pour
        # le CTI, plutôt que de faire un appel réseau séparé par log — et on
        # rattrape TOUS les logs historiques de cette IP encore sans pays,
        # pas seulement le lot en cours de traitement (le tableau de bord
        # Trafic & IP en profite immédiatement).
        geo = ip_enrichment.geo_lookup(ip)
        country_code = geo.get("countryCode")
        if country_code:
            updated = (
                NormalizedLog.objects.filter(source_ip=ip, geo_country__isnull=True)
                .update(geo_country=country_code, geo_city=geo.get("city") or None)
            )
            geo_tagged += updated

        abuse_data = abuseipdb.check_ip(ip)
        if abuse_data:
            score = float(abuse_data.get("abuseConfidenceScore", 0))
            indicator, _ = ThreatIndicator.objects.update_or_create(
                indicator_type="ip",
                value=ip,
                source="abuseipdb",
                defaults={
                    "reputation_score": score,
                    "confidence": min(score / 100, 1.0),
                    "is_malicious": score >= 50,
                    "raw_data": abuse_data,
                    "tags": abuse_data.get("usageType", "").split(",") if abuse_data.get("usageType") else [],
                    "last_seen": timezone.now(),
                },
            )
            indicators.append(indicator)

        vt_data = virustotal.analyze_ip(ip)
        if vt_data:
            vt_score = virustotal.get_malicious_score(vt_data)
            indicator, _ = ThreatIndicator.objects.update_or_create(
                indicator_type="ip",
                value=ip,
                source="virustotal",
                defaults={
                    "reputation_score": vt_score,
                    "confidence": min(vt_score / 100, 1.0),
                    "is_malicious": vt_score >= 30,
                    "raw_data": vt_data.get("attributes", {}),
                    "last_seen": timezone.now(),
                },
            )
            indicators.append(indicator)

        indicators_by_ip[ip] = indicators

    enriched_count = 0
    threat_count = 0

    for log in logs:
        indicators = indicators_by_ip.get(log.source_ip, [])
        if indicators:
            enriched_log, _ = EnrichedLog.objects.get_or_create(log=log)
            enriched_log.indicators.set(indicators)
            enriched_log.compute_max_score()
            enriched_count += 1
            if enriched_log.is_threat:
                threat_count += 1
                # Génération d'alerte désactivée à la demande de l'utilisateur
                # (2026-07-23) — trop de bruit, comme pour les alertes ML.
                # L'enrichissement (score, indicateurs) reste actif : la page
                # Threat Intelligence et le pivot IP en ont toujours besoin.
                # Pour réactiver : décommenter la ligne ci-dessous.
                # _create_cti_alert(log, enriched_log)

    logger.info(
        "CTI enrichissement: %d logs traités (%d IP uniques interrogées), %d menaces détectées, %d logs géolocalisés",
        enriched_count, len(unique_ips), threat_count, geo_tagged,
    )
    return {"enriched": enriched_count, "unique_ips": len(unique_ips), "threats": threat_count, "geo_tagged": geo_tagged}


def _create_cti_alert(log, enriched_log):
    """
    Crée une alerte si une IP malveillante est confirmée par CTI — ou
    rattache le log à l'alerte déjà ouverte pour cette IP si elle existe
    (même logique que le moteur de corrélation : une activité qui continue
    ne doit jamais devenir invisible / rester à "0 évènement").
    """
    from apps.alerts.models import Alert

    title = f"CTI: IP malveillante détectée — {log.source_ip}"
    existing = Alert.objects.filter(
        title=title, status__in=["open", "in_progress"], organization=log.organization
    ).first()

    if existing:
        existing.source_logs.add(log)
        existing.save(update_fields=["updated_at"])
        logger.info("Alerte CTI existante enrichie pour IP %s (+1 log)", log.source_ip)
        return

    alert = Alert.objects.create(
        title=title,
        description=(
            f"L'IP source {log.source_ip} a un score de réputation CTI de "
            f"{enriched_log.max_score:.1f}/100.\n"
            f"Source: AbuseIPDB + VirusTotal\n"
            f"Utilisateur: {log.user_email or 'inconnu'}\n"
            f"Action: {log.action}"
        ),
        severity="high" if enriched_log.max_score >= 75 else "medium",
        status="open",
        organization=log.organization,
    )
    alert.source_logs.add(log)
    logger.info("Alerte CTI créée pour IP %s (score=%.1f)", log.source_ip, enriched_log.max_score)


@shared_task(name="apps.threat_intel.tasks.cleanup_old_indicators")
def cleanup_old_indicators():
    """Supprime les indicateurs CTI non vus depuis plus de 30 jours."""
    from apps.threat_intel.models import ThreatIndicator

    cutoff = timezone.now() - timedelta(days=30)
    deleted, _ = ThreatIndicator.objects.filter(last_seen__lt=cutoff, is_malicious=False).delete()
    logger.info("CTI cleanup: %d indicateurs anciens supprimés", deleted)
    return {"deleted": deleted}


@shared_task(name="apps.threat_intel.tasks.sync_cisa_kev")
def sync_cisa_kev():
    """
    Synchronise le catalogue CISA KEV (vulnérabilités EXPLOITÉES ACTIVEMENT
    dans la nature). C'est le signal de priorisation le plus fort qui existe
    en threat intel gratuite : contrairement à une liste brute de CVE, KEV ne
    contient QUE des vulnérabilités confirmées comme exploitées en conditions
    réelles.
    """
    from datetime import datetime

    from django.utils.dateparse import parse_datetime
    from django.utils.timezone import make_aware, is_naive

    from apps.threat_intel.models import CVERecord
    from apps.threat_intel.services import cisa_kev

    entries = cisa_kev.fetch_kev_catalog()
    synced = 0

    def _parse(value):
        if not value:
            return None
        try:
            dt = parse_datetime(value) or datetime.strptime(value, "%Y-%m-%d")
        except (ValueError, TypeError):
            return None
        if dt and is_naive(dt):
            dt = make_aware(dt)
        return dt

    for entry in entries:
        cve_id = entry.get("cveID")
        if not cve_id:
            continue

        CVERecord.objects.update_or_create(
            cve_id=cve_id,
            defaults={
                "vendor_project": entry.get("vendorProject", "")[:255],
                "product": entry.get("product", "")[:255],
                "description": entry.get("shortDescription", ""),
                "severity": "critical",
                "is_kev": True,
                "kev_date_added": _parse(entry.get("dateAdded")),
                "kev_due_date": _parse(entry.get("dueDate")),
                "kev_ransomware_use": entry.get("knownRansomwareCampaignUse", "Unknown") == "Known",
                "kev_required_action": entry.get("requiredAction", ""),
                "raw_data": entry,
            },
        )
        synced += 1

    logger.info("CISA KEV: %d vulnérabilités exploitées activement synchronisées", synced)
    return {"synced": synced}


@shared_task(name="apps.threat_intel.tasks.sync_nvd_recent_cves")
def sync_nvd_recent_cves():
    """
    Synchronise les CVE publiées/modifiées récemment depuis le NVD (NIST).
    Alimente le référentiel CVERecord en continu, sans intervention humaine —
    c'est ce qui manque à une solution purement basée sur des règles écrites
    à l'avance : dès qu'une CVE sort, elle est en base en quelques heures.
    """
    from datetime import datetime

    from django.utils.dateparse import parse_datetime
    from django.utils.timezone import make_aware, is_naive

    from apps.threat_intel.models import CVERecord
    from apps.threat_intel.services import nvd

    def _parse_date(value):
        if not value:
            return None
        try:
            dt = datetime.strptime(value, "%Y-%m-%d")
        except (ValueError, TypeError):
            return None
        return make_aware(dt) if is_naive(dt) else dt

    def _parse_nvd_timestamp(value):
        """NVD renvoie des timestamps ISO sans offset explicite (toujours UTC)."""
        if not value:
            return None
        parsed = parse_datetime(value)
        if parsed is None:
            return None
        return make_aware(parsed) if is_naive(parsed) else parsed

    items = nvd.fetch_recent_cves(days=2)
    synced = 0
    for item in items:
        cve = item.get("cve", {})
        cve_id = cve.get("id")
        if not cve_id:
            continue

        descriptions = cve.get("descriptions", [])
        desc_en = next((d["value"] for d in descriptions if d.get("lang") == "en"), "")
        score = nvd.extract_cvss_score(cve)
        vendor, product = nvd.extract_vendor_product(cve)

        # NVD expose directement les champs CISA KEV (cisaExploitAdd...) sur
        # chaque CVE quand elle est exploitée activement — source de secours
        # fiable si le flux JSON CISA brut est bloqué (WAF anti-datacenter,
        # fréquent sur IP de VPS/cloud).
        is_kev = bool(cve.get("cisaExploitAdd"))
        existing = CVERecord.objects.filter(cve_id=cve_id).first()

        defaults = {
            "description": desc_en[:4000],
            "cvss_score": score,
            "severity": nvd.score_to_severity(score) or (existing.severity if existing else ""),
            "vendor_project": vendor[:255],
            "product": product[:255],
            "published_date": _parse_nvd_timestamp(cve.get("published")),
            "modified_date": _parse_nvd_timestamp(cve.get("lastModified")),
            "raw_data": {"id": cve_id, "sourceIdentifier": cve.get("sourceIdentifier")},
        }
        if is_kev:
            defaults.update({
                "is_kev": True,
                "severity": "critical",
                "kev_date_added": _parse_date(cve.get("cisaExploitAdd")),
                "kev_due_date": _parse_date(cve.get("cisaActionDue")),
                "kev_required_action": cve.get("cisaRequiredAction", ""),
            })
        elif existing and existing.is_kev:
            # Ne jamais rétrograder un statut KEV déjà connu (ex: via le sync CISA direct).
            defaults["is_kev"] = True

        CVERecord.objects.update_or_create(cve_id=cve_id, defaults=defaults)
        synced += 1

    logger.info("NVD: %d CVE synchronisées", synced)
    return {"synced": synced}


@shared_task(name="apps.threat_intel.tasks.correlate_cve_with_assets")
def correlate_cve_with_assets():
    """
    Corrèle automatiquement le référentiel CVE/KEV avec l'inventaire d'actifs
    de chaque organisation. C'est LE point que Wazuh ne fait pas de façon
    proactive : au lieu d'attendre qu'un analyste consulte une liste de CVE,
    Argus notifie automatiquement dès qu'un actif connu est concerné par une
    vulnérabilité exploitée activement (CISA KEV) ou critique.
    """
    from django.db.models import Q

    from apps.alerts.models import Alert
    from apps.threat_intel.models import Asset, AssetVulnerability, CVERecord

    priority_cves = CVERecord.objects.filter(Q(is_kev=True) | Q(severity__in=["high", "critical"]))
    matched = 0
    new_alerts = 0

    for asset in Asset.objects.select_related("organization").exclude(vendor="", product=""):
        candidates = priority_cves.none()
        if asset.product:
            candidates = priority_cves.filter(product__icontains=asset.product)
        if asset.vendor:
            candidates = candidates | priority_cves.filter(vendor_project__icontains=asset.vendor)

        for cve in candidates.distinct()[:100]:
            link, created = AssetVulnerability.objects.get_or_create(
                asset=asset,
                cve=cve,
                defaults={
                    "organization": asset.organization,
                    "matched_reason": "Correspondance éditeur/produit avec l'inventaire d'actifs",
                },
            )
            if not created:
                continue
            matched += 1

            if cve.is_kev:
                title = f"Vulnérabilité EXPLOITÉE ACTIVEMENT (CISA KEV) : {cve.cve_id} sur {asset.name}"
                severity = "critical"
            else:
                title = f"Vulnérabilité critique détectée : {cve.cve_id} sur {asset.name}"
                severity = "high"

            if not Alert.objects.filter(
                title=title, organization=asset.organization, status__in=["open", "in_progress"]
            ).exists():
                Alert.objects.create(
                    title=title,
                    description=(
                        f"L'actif « {asset.name} » ({asset.vendor} {asset.product} {asset.version}) "
                        f"est concerné par {cve.cve_id} (CVSS {cve.cvss_score or '?'}).\n\n"
                        f"{cve.description[:800]}\n\n"
                        + (
                            f"⚠ Cette vulnérabilité est activement exploitée dans la nature "
                            f"(CISA KEV, ajoutée le {cve.kev_date_added}). "
                            f"Action requise : {cve.kev_required_action}"
                            if cve.is_kev
                            else "Vulnérabilité critique/élevée, non encore confirmée comme exploitée activement."
                        )
                    ),
                    severity=severity,
                    status="open",
                    organization=asset.organization,
                )
                new_alerts += 1

    logger.info(
        "Corrélation CVE/actifs : %d nouvelles expositions détectées, %d alertes créées",
        matched, new_alerts,
    )
    return {"matched": matched, "alerts_created": new_alerts}


@shared_task(name="apps.threat_intel.tasks.sync_community_threat_feeds")
def sync_community_threat_feeds():
    """
    Synchronise des flux de threat intel COLLABORATIFS et gratuits (abuse.ch
    URLhaus + Feodo Tracker) — même principe que la blocklist communautaire
    de CrowdSec (une IP/domaine signalé par la communauté profite à tout le
    monde), mais intégré nativement au moteur d'alerting du SIEM au lieu de
    nécessiter un outil séparé.
    """
    from apps.threat_intel.models import ThreatIndicator
    from apps.threat_intel.services import community_feeds

    now = timezone.now()
    synced = 0

    for ip in community_feeds.fetch_feodo_ipblocklist():
        ThreatIndicator.objects.update_or_create(
            indicator_type="ip",
            value=ip,
            source="feodotracker",
            defaults={
                "reputation_score": 95.0,
                "confidence": 0.9,
                "is_malicious": True,
                "tags": ["botnet_c2", "community_feed"],
                "last_seen": now,
            },
        )
        synced += 1

    for entry in community_feeds.fetch_urlhaus_recent():
        host = entry.get("host")
        if not host:
            continue
        indicator_type = "ip" if community_feeds.is_ip(host) else "domain"
        ThreatIndicator.objects.update_or_create(
            indicator_type=indicator_type,
            value=host,
            source="urlhaus",
            defaults={
                "reputation_score": 90.0,
                "confidence": 0.85,
                "is_malicious": True,
                "tags": ["malware_distribution", "community_feed", entry.get("threat", "")],
                "raw_data": entry,
                "last_seen": now,
            },
        )
        synced += 1

    logger.info("Flux communautaires (URLhaus + Feodo Tracker) : %d indicateurs synchronisés", synced)
    return {"synced": synced}
