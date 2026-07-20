//go:build !windows

// Package runner assemble spool + sender + batcher + collecteur(s) pour la
// plateforme courante, exposant un point d'entrée unique Run() utilisé par
// `logplus-agent run` — voir run_windows.go pour l'équivalent Windows.
package runner

import (
	"context"
	"fmt"
	"log"
	"time"

	"logplus-agent/internal/batcher"
	"logplus-agent/internal/collector/linuxlog"
	"logplus-agent/internal/config"
	"logplus-agent/internal/model"
	"logplus-agent/internal/sender"
	"logplus-agent/internal/spool"
)

func Run(ctx context.Context, cfg config.Config, logger *log.Logger) error {
	sp, err := spool.Open(config.SpoolPath())
	if err != nil {
		return fmt.Errorf("ouverture spool: %w", err)
	}
	defer sp.Close()

	token, err := cfg.Token()
	if err != nil {
		return fmt.Errorf("déchiffrement token: %w", err)
	}
	sd, err := sender.New(cfg.URL, token, cfg.Insecure, logger)
	if err != nil {
		return fmt.Errorf("initialisation sender: %w", err)
	}

	flushInterval := time.Duration(cfg.FlushIntervalSeconds) * time.Second
	if flushInterval <= 0 {
		flushInterval = 5 * time.Second
	}
	b := batcher.New(sp, sd, logger, flushInterval, cfg.MaxBatchLines, cfg.MaxBatchBytes)
	go b.Run(ctx)

	logger.Printf("agent démarré (linux) — url=%s", cfg.URL)
	linuxlog.Start(ctx, linuxlog.Options{
		Sources:           cfg.LinuxSources,
		Journald:          cfg.LinuxJournald,
		SyslogListenAddr:  cfg.SyslogListenAddr,
	}, sp, logger, func(e model.Event) {
		if err := b.Add(e); err != nil {
			logger.Printf("échec d'ajout au spool (évènement perdu): %v", err)
		}
	})

	return nil
}
