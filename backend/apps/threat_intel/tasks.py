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
    from apps.threat_intel.services import abuseipdb, virustotal

    cutoff = timezone.now() - timedelta(hours=2)
    enriched_ids = EnrichedLog.objects.values_list("log_id", flat=True)
    logs = NormalizedLog.objects.filter(
        indexed_at__gte=cutoff, source_ip__isnull=False
    ).exclude(id__in=enriched_ids).select_related()[:200]

    enriched_count = 0
    threat_count = 0

    for log in logs:
        indicators = []

        if log.source_ip:
            abuse_data = abuseipdb.check_ip(log.source_ip)
            if abuse_data:
                score = float(abuse_data.get("abuseConfidenceScore", 0))
                indicator, _ = ThreatIndicator.objects.update_or_create(
                    indicator_type="ip",
                    value=log.source_ip,
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

            vt_data = virustotal.analyze_ip(log.source_ip)
            if vt_data:
                vt_score = virustotal.get_malicious_score(vt_data)
                indicator, _ = ThreatIndicator.objects.update_or_create(
                    indicator_type="ip",
                    value=log.source_ip,
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

        if indicators:
            enriched_log, _ = EnrichedLog.objects.get_or_create(log=log)
            enriched_log.indicators.set(indicators)
            enriched_log.compute_max_score()
            enriched_count += 1
            if enriched_log.is_threat:
                threat_count += 1
                _create_cti_alert(log, enriched_log)

    logger.info("CTI enrichissement: %d logs traités, %d menaces détectées", enriched_count, threat_count)
    return {"enriched": enriched_count, "threats": threat_count}


def _create_cti_alert(log, enriched_log):
    """Crée une alerte si une IP malveillante est confirmée par CTI."""
    from apps.alerts.models import Alert

    title = f"CTI: IP malveillante détectée — {log.source_ip}"
    if Alert.objects.filter(title=title, status__in=["open", "in_progress"]).exists():
        return

    Alert.objects.create(
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
    )
    logger.info("Alerte CTI créée pour IP %s (score=%.1f)", log.source_ip, enriched_log.max_score)


@shared_task(name="apps.threat_intel.tasks.cleanup_old_indicators")
def cleanup_old_indicators():
    """Supprime les indicateurs CTI non vus depuis plus de 30 jours."""
    from apps.threat_intel.models import ThreatIndicator

    cutoff = timezone.now() - timedelta(days=30)
    deleted, _ = ThreatIndicator.objects.filter(last_seen__lt=cutoff, is_malicious=False).delete()
    logger.info("CTI cleanup: %d indicateurs anciens supprimés", deleted)
    return {"deleted": deleted}
