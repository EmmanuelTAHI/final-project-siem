"""
Configuration Celery + Celery Beat pour Argus.
PFE Argus — TAHI Ezan Franck Emmanuel — 2025-2026
"""
import os
from datetime import timedelta

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = Celery("argus")

app.config_from_object("django.conf:settings", namespace="CELERY")

app.autodiscover_tasks()

app.conf.beat_schedule = {
    # Collecte Microsoft 365 — toutes les 5 minutes
    "collect-microsoft-logs": {
        "task": "apps.collectors.tasks.collect_all_microsoft_connectors",
        "schedule": crontab(minute="*/5"),
    },
    # Collecte Google Workspace — toutes les 5 minutes
    "collect-google-logs": {
        "task": "apps.collectors.tasks.collect_all_google_connectors",
        "schedule": crontab(minute="*/5"),
    },
    # Collecte Wazuh — toutes les 2 minutes
    "collect-wazuh-logs": {
        "task": "apps.collectors.tasks.collect_all_wazuh_connectors",
        "schedule": crontab(minute="*/2"),
    },
    # Normalisation syslog — toutes les 2 minutes (push-based : logs déjà en RawLog)
    "normalize-syslog-logs": {
        "task": "apps.collectors.tasks.collect_all_syslog_connectors",
        "schedule": crontab(minute="*/2"),
    },
    # Moteur de corrélation — toutes les 20s (crontab ne descend pas sous la
    # minute, on utilise donc un timedelta pour un quasi temps-réel côté SOC).
    "run-correlation-engine": {
        "task": "apps.correlation.tasks.run_correlation_engine",
        "schedule": timedelta(seconds=20),
    },
    # Inférence ML — toutes les 10 minutes
    "run-ml-inference": {
        "task": "apps.ml.tasks.run_anomaly_detection_on_new_logs",
        "schedule": crontab(minute="*/10"),
    },
    # Entraînement ML — chaque dimanche à 02h00 UTC
    "train-ml-model": {
        "task": "apps.ml.tasks.train_isolation_forest",
        "schedule": crontab(day_of_week="sunday", hour=2, minute=0),
    },
    # Nettoyage des RawLog anciens (> 90 jours) — chaque jour à 03h00
    "cleanup-old-raw-logs": {
        "task": "apps.logs.tasks.cleanup_old_raw_logs",
        "schedule": crontab(hour=3, minute=0),
    },
    # Rafraîchissement des tokens OAuth expirés — toutes les heures
    "refresh-oauth-tokens": {
        "task": "apps.collectors.tasks.refresh_expiring_tokens",
        "schedule": crontab(minute=0),
    },
    # Enrichissement CTI — toutes les 15 minutes
    "enrich-logs-with-cti": {
        "task": "apps.threat_intel.tasks.enrich_logs_with_cti",
        "schedule": crontab(minute="*/15"),
    },
    # Nettoyage indicateurs CTI anciens — chaque lundi à 04h00
    "cleanup-old-indicators": {
        "task": "apps.threat_intel.tasks.cleanup_old_indicators",
        "schedule": crontab(day_of_week="monday", hour=4, minute=0),
    },
    # Déclenchement SOAR — toutes les 5 minutes
    "check-soar-playbooks": {
        "task": "apps.soar.tasks.check_and_trigger_playbooks",
        "schedule": crontab(minute="*/5"),
    },
    # Feedback ML (faux positifs → ajustement contamination) — chaque jour à 01h00
    "ml-false-positive-feedback": {
        "task": "apps.ml.tasks.retrain_on_false_positives",
        "schedule": crontab(hour=1, minute=0),
    },
    # Scores de risque utilisateurs — chaque heure
    "compute-user-risk-scores": {
        "task": "apps.ml.tasks.compute_user_risk_scores",
        "schedule": crontab(minute=30),
    },
    # Polling des comptes liés (Google / Microsoft / GitHub) — toutes les 5 minutes
    "poll-linked-accounts": {
        "task": "apps.authentication.tasks.poll_linked_accounts",
        "schedule": crontab(minute="*/5"),
    },
    # Expiration des LoginConfirmation pending — chaque heure
    "expire-login-confirmations": {
        "task": "apps.authentication.tasks.expire_login_confirmations",
        "schedule": crontab(minute=15),
    },
}

app.conf.timezone = "UTC"
