//go:build !windows

package linuxlog

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"log"
	"os/exec"
	"time"

	"logplus-agent/internal/model"
	"logplus-agent/internal/spool"
)

const journaldCursorMetaKey = "linuxlog:journald:cursor"

// RunJournald lit le journal systemd en flux temps réel via le binaire
// `journalctl` déjà présent nativement sur toute distribution systemd —
// ce n'est pas une dépendance ajoutée par l'agent, juste un outil du
// système d'exploitation, au même titre que /var/log lui-même.
//
// Reprend après le dernier évènement traité via un cursor persistant
// (spool meta), ne relit jamais tout l'historique au redémarrage.
func RunJournald(ctx context.Context, sp *spool.Spool, logger *log.Logger, emit func(model.Event)) {
	if _, err := exec.LookPath("journalctl"); err != nil {
		logger.Printf("journalctl introuvable, lecture journald désactivée (systemd absent ?)")
		return
	}

	for {
		select {
		case <-ctx.Done():
			return
		default:
		}

		if err := runJournaldOnce(ctx, sp, logger, emit); err != nil {
			logger.Printf("journalctl interrompu, nouvelle tentative dans 5s: %v", err)
		}

		select {
		case <-ctx.Done():
			return
		case <-time.After(5 * time.Second):
		}
	}
}

func runJournaldOnce(ctx context.Context, sp *spool.Spool, logger *log.Logger, emit func(model.Event)) error {
	args := []string{"-f", "-o", "json", "--no-pager"}
	cursor, _ := sp.GetMeta(journaldCursorMetaKey)
	if len(cursor) > 0 {
		args = append(args, "--after-cursor="+string(cursor))
	} else {
		// Premier démarrage : pas de backfill de tout l'historique du journal.
		args = append(args, "-n", "0")
	}

	cmd := exec.CommandContext(ctx, "journalctl", args...)
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return fmt.Errorf("stdout pipe: %w", err)
	}
	if err := cmd.Start(); err != nil {
		return fmt.Errorf("démarrage journalctl: %w", err)
	}

	scanner := bufio.NewScanner(stdout)
	scanner.Buffer(make([]byte, 64*1024), 4<<20)
	for scanner.Scan() {
		var raw map[string]interface{}
		if err := json.Unmarshal(scanner.Bytes(), &raw); err != nil {
			continue // ligne non-JSON inattendue, on l'ignore plutôt que de crasher
		}

		message, _ := raw["MESSAGE"].(string)
		if message == "" {
			continue
		}
		provider, _ := raw["SYSLOG_IDENTIFIER"].(string)
		hostname, _ := raw["_HOSTNAME"].(string)
		priority, _ := raw["PRIORITY"].(string)

		emit(model.Event{
			Message:  message,
			Hostname: hostname,
			Source:   "linuxlog",
			Provider: provider,
			Severity: mapJournaldPriority(priority),
			RawFields: map[string]interface{}{
				"journald": raw,
			},
		})

		if cursorVal, ok := raw["__CURSOR"].(string); ok && cursorVal != "" {
			_ = sp.SetMeta(journaldCursorMetaKey, []byte(cursorVal))
		}
	}

	waitErr := cmd.Wait()
	if ctx.Err() != nil {
		return nil // arrêt normal demandé, pas une erreur
	}
	return waitErr
}

// mapJournaldPriority convertit le niveau syslog standard (0=emerg..7=debug)
// vers les choix de sévérité NormalizedLog côté backend (info/low/medium/high/critical).
func mapJournaldPriority(priority string) string {
	switch priority {
	case "0", "1", "2":
		return "critical"
	case "3":
		return "high"
	case "4":
		return "medium"
	case "5":
		return "low"
	default:
		return "info"
	}
}
