#!/usr/bin/env bash
# Scan quotidien rkhunter + ClamAV sur l'hôte VPS (hors Docker).
# Lancé par cron (voir argus-security-scan.cron), jamais manuellement en
# production sauf pour un test ponctuel.
#
# Choix volontaire : `clamscan` (mono-exécution, charge la base de
# signatures en mémoire seulement le temps du scan) plutôt que
# `clamdscan`/`clamav-daemon` (démon qui garde ~800Mo-1Go résident en
# permanence) -- le VPS n'a que 3.7Go de RAM et AUCUN swap configuré, un
# démon clamd permanent risquerait de faire OOM-killer le reste de la
# stack (Postgres/Redis/Django) en heures de pointe. Le scan périodique
# (nice/ionice, heure creuse) est le compromis mémoire/CPU adapté à cette
# taille de machine.
set -uo pipefail

RKHUNTER_LOG=/var/log/rkhunter-argus.log
CLAMAV_LOG=/var/log/clamav-argus.log

echo "=== rkhunter $(date -u +%FT%TZ) ===" >> "$RKHUNTER_LOG"
nice -n 19 ionice -c3 rkhunter --check --skip-keypress --report-warnings-only >> "$RKHUNTER_LOG" 2>&1

echo "=== clamscan $(date -u +%FT%TZ) ===" >> "$CLAMAV_LOG"
# Périmètre volontairement restreint : /var/lib/docker (couches d'images,
# souvent plusieurs Go) est exclu -- redondant (les conteneurs ne sont pas
# le vecteur visé par ce scan hôte) et beaucoup trop lent/lourd pour un
# scan quotidien sur cette machine.
nice -n 19 ionice -c3 clamscan -r --infected --exclude-dir="^/proc|^/sys|^/dev|^/var/lib/docker" \
    /root /home /etc /opt /var/www /tmp 2>/dev/null >> "$CLAMAV_LOG" 2>&1
