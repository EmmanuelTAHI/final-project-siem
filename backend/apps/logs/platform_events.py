"""
Ingestion des événements générés par la plateforme Log+ elle-même (login au
SOC, indépendamment des connecteurs M365/Google/Wazuh/syslog) dans le pipeline
NormalizedLog, pour que le moteur de corrélation (impossible travel, etc.) et
la page Logs les traitent comme n'importe quel autre événement d'auth.
"""
from django.utils import timezone

from .models import NormalizedLog, RawLog


def record_platform_login(
    *,
    user_email: str,
    success: bool,
    ip_address: str | None = None,
    geo_country: str | None = None,
    geo_city: str | None = None,
    user_agent: str | None = None,
) -> NormalizedLog:
    """Journalise un login (réussi ou échoué) à la plateforme Log+ elle-même."""
    raw_log = RawLog.objects.create(
        source_type="logplus",
        raw_data={
            "user_email": user_email,
            "success": success,
            "ip_address": ip_address,
            "geo_country": geo_country,
            "geo_city": geo_city,
        },
        is_normalized=True,
    )
    return NormalizedLog.objects.create(
        raw_log=raw_log,
        event_time=timezone.now(),
        source_ip=ip_address or None,
        user_email=user_email,
        action="login_success" if success else "login_failure",
        outcome="success" if success else "failure",
        resource="Log+ SOC platform",
        geo_country=geo_country or None,
        geo_city=geo_city or None,
        user_agent=user_agent or None,
        severity="info" if success else "medium",
        source_type="logplus",
    )
