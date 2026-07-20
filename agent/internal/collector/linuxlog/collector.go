//go:build !windows

package linuxlog

import (
	"context"
	"log"
	"sync"

	"logplus-agent/internal/model"
	"logplus-agent/internal/spool"
)

// Options configure les sources activées pour ce poste.
type Options struct {
	// Sources explicites ; si vide, DefaultAuthLogPaths() est utilisé.
	Sources []string
	// Journald active la lecture temps réel du journal systemd.
	Journald bool
	// SyslogListenAddr, si non vide, active le relais syslog local (ex: "0.0.0.0:1514").
	SyslogListenAddr string
}

// Start lance toutes les sources configurées en parallèle et bloque jusqu'à
// annulation du contexte. emit est appelé pour chaque évènement collecté —
// typiquement batcher.Batcher.Add, qui persiste immédiatement dans le spool.
func Start(ctx context.Context, opts Options, sp *spool.Spool, logger *log.Logger, emit func(model.Event)) {
	var wg sync.WaitGroup

	sources := opts.Sources
	if len(sources) == 0 {
		sources = DefaultAuthLogPaths()
	}
	for _, path := range sources {
		wg.Add(1)
		go func(p string) {
			defer wg.Done()
			NewFileTailer(p, sp).Run(ctx, emit)
		}(path)
	}

	if opts.Journald {
		wg.Add(1)
		go func() {
			defer wg.Done()
			RunJournald(ctx, sp, logger, emit)
		}()
	}

	if opts.SyslogListenAddr != "" {
		wg.Add(1)
		go func() {
			defer wg.Done()
			if err := RunSyslogListener(ctx, opts.SyslogListenAddr, logger, emit); err != nil {
				logger.Printf("relais syslog local désactivé: %v", err)
			}
		}()
	}

	wg.Wait()
}
