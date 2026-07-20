//go:build windows

package runner

import (
	"context"
	"fmt"
	"log"
	"time"

	"logplus-agent/internal/batcher"
	"logplus-agent/internal/collector/wineventlog"
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

	logger.Printf("agent démarré (windows) — url=%s", cfg.URL)
	channels := cfg.WindowsChannels
	if len(channels) == 0 {
		channels = []string{"Security", "System"}
	}
	wineventlog.Start(ctx, channels, sp, logger, func(e model.Event) {
		if err := b.Add(e); err != nil {
			logger.Printf("échec d'ajout au spool (évènement perdu): %v", err)
		}
	})

	return nil
}
