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
    # Collecte Wazuh — toutes les minutes (manager local, pas d'API externe
    # à ménager — resserré depuis 2 min pour réduire la latence log → alerte)
    "collect-wazuh-logs": {
        "task": "apps.collectors.tasks.collect_all_wazuh_connectors",
        "schedule": crontab(minute="*"),
    },
    # Normalisation syslog — filet de sécurité en complément du flush temps
    # réel (5s) du récepteur syslog — resserré depuis 2 min à 30s.
    "normalize-syslog-logs": {
        "task": "apps.collectors.tasks.collect_all_syslog_connectors",
        "schedule": timedelta(seconds=30),
    },
    # Moteur de corrélation — toutes les 5s (crontab ne descend pas sous la
    # minute, on utilise donc un timedelta pour un quasi temps-réel côté SOC).
    # Requête incrémentale (depuis le dernier run) donc peu coûteuse même à
    # cette fréquence — resserré depuis 20s pour réduire la latence des
    # alertes (ex. brute force détecté quelques secondes après le scan).
    "run-correlation-engine": {
        "task": "apps.correlation.tasks.run_correlation_engine",
        "schedule": timedelta(seconds=5),
    },
    # Inférence ML — DÉSACTIVÉE à la demande de l'utilisateur (2026-07-23) :
    # trop de faux positifs / bruit, alertes "Anomalie ML" plus voulues pour
    # l'instant. Ne pas réactiver sans instruction explicite. Pour réactiver :
    # décommenter ce bloc (et son entraînement ci-dessous si besoin).
    # "run-ml-inference": {
    #     "task": "apps.ml.tasks.run_anomaly_detection_on_new_logs",
    #     "schedule": crontab(minute="*/10"),
    # },
    # Entraînement ML — DÉSACTIVÉ en même temps que l'inférence ci-dessus
    # (inutile d'entraîner un modèle dont on ne consomme plus les prédictions).
    # "train-ml-model": {
    #     "task": "apps.ml.tasks.train_isolation_forest",
    #     "schedule": crontab(day_of_week="sunday", hour=2, minute=0),
    # },
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
    # Enrichissement CTI — DÉSACTIVÉ COMPLÈTEMENT à la demande de l'utilisateur
    # (2026-07-23), pas seulement la création d'alertes qui en découlait (déjà
    # coupée avant dans apps/threat_intel/tasks.py::_create_cti_alert).
    # Effet de bord assumé : plus d'appels AbuseIPDB/VirusTotal, ET plus de
    # géolocalisation automatique des nouveaux logs (le géolookup IP était
    # fait dans cette même tâche) — "Connexions par pays" ne se peuplera plus
    # pour les nouveaux logs tant que ceci reste désactivé.
    # Pour réactiver : décommenter ce bloc.
    # "enrich-logs-with-cti": {
    #     "task": "apps.threat_intel.tasks.enrich_logs_with_cti",
    #     "schedule": crontab(minute="*/15"),
    # },
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
    # Feedback ML — DÉSACTIVÉ en même temps que l'inférence ci-dessus (ce
    # feedback ne fait que déclencher un réentraînement, inutile tant que
    # l'inférence ne tourne pas).
    # "ml-false-positive-feedback": {
    #     "task": "apps.ml.tasks.retrain_on_false_positives",
    #     "schedule": crontab(hour=1, minute=0),
    # },
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
    # CISA KEV (vulnérabilités exploitées activement) — toutes les 6 heures
    "sync-cisa-kev": {
        "task": "apps.threat_intel.tasks.sync_cisa_kev",
        "schedule": crontab(hour="*/6", minute=5),
    },
    # NVD CVE récentes — toutes les 4 heures
    "sync-nvd-cves": {
        "task": "apps.threat_intel.tasks.sync_nvd_recent_cves",
        "schedule": crontab(hour="*/4", minute=10),
    },
    # Corrélation CVE ↔ inventaire d'actifs — toutes les heures
    "correlate-cve-assets": {
        "task": "apps.threat_intel.tasks.correlate_cve_with_assets",
        "schedule": crontab(minute=20),
    },
    # Flux collaboratifs communautaires (URLhaus, Feodo Tracker) — toutes les 30 min
    "sync-community-threat-feeds": {
        "task": "apps.threat_intel.tasks.sync_community_threat_feeds",
        "schedule": crontab(minute="*/30"),
    },
}

app.conf.timezone = "UTC"
