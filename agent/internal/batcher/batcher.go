// Package batcher relie le spool (file persistante) et le sender (envoi
// HTTP) : flush périodique ou par seuil de taille, avec backoff exponentiel
// quand le serveur est injoignable — pour ne jamais marteler un serveur en
// panne, tout en restituant les logs dès qu'il redevient disponible.
package batcher

import (
	"context"
	"encoding/json"
	"errors"
	"log"
	"time"

	"logplus-agent/internal/model"
	"logplus-agent/internal/sender"
	"logplus-agent/internal/spool"
)

const (
	minBackoff = 5 * time.Second
	maxBackoff = 5 * time.Minute
)

type Batcher struct {
	spool         *spool.Spool
	sender        *sender.Sender
	logger        *log.Logger
	flushInterval time.Duration
	maxLines      int
	maxBytes      int

	consecutiveFailures int
}

func New(sp *spool.Spool, sd *sender.Sender, logger *log.Logger, flushInterval time.Duration, maxLines, maxBytes int) *Batcher {
	if maxLines <= 0 {
		maxLines = 500
	}
	if maxBytes <= 0 {
		maxBytes = 1 << 20
	}
	return &Batcher{spool: sp, sender: sd, logger: logger, flushInterval: flushInterval, maxLines: maxLines, maxBytes: maxBytes}
}

// Add place un événement dans le spool persistant (jamais perdu à partir
// de cet instant, même si l'agent crashe avant le prochain flush).
func (b *Batcher) Add(e model.Event) error {
	return b.spool.Push(e)
}

// Run boucle jusqu'à annulation du contexte, en flushant régulièrement.
// Effectue un dernier flush best-effort avant de retourner (arrêt propre).
func (b *Batcher) Run(ctx context.Context) {
	ticker := time.NewTicker(b.flushInterval)
	defer ticker.Stop()

	backoffUntil := time.Time{}

	for {
		select {
		case <-ctx.Done():
			flushCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
			if err := b.flushOnce(flushCtx); err != nil {
				b.logger.Printf("flush final échoué (logs conservés dans le spool pour le prochain démarrage): %v", err)
			}
			cancel()
			return
		case <-ticker.C:
			if time.Now().Before(backoffUntil) {
				continue
			}
			if err := b.flushOnce(ctx); err != nil {
				delay := b.nextBackoff()
				backoffUntil = time.Now().Add(delay)
				b.logger.Printf("échec d'envoi, nouvelle tentative dans %s: %v", delay, err)
			} else {
				b.consecutiveFailures = 0
				backoffUntil = time.Time{}
			}
		}
	}
}

// nextBackoff double le délai à chaque échec consécutif, plafonné à
// maxBackoff, réinitialisé au prochain succès (voir Run).
func (b *Batcher) nextBackoff() time.Duration {
	b.consecutiveFailures++
	shift := b.consecutiveFailures - 1
	if shift > 10 { // largement suffisant pour dépasser maxBackoff, évite tout risque de décalage excessif
		return maxBackoff
	}
	delay := minBackoff << shift
	if delay > maxBackoff || delay <= 0 {
		return maxBackoff
	}
	return delay
}

// flushOnce vide le spool par sous-lots respectant maxLines ET maxBytes,
// et ne les acquitte (suppression du spool) qu'après confirmation serveur.
func (b *Batcher) flushOnce(ctx context.Context) error {
	ids, events, err := b.spool.PopBatch(b.maxLines)
	if err != nil {
		return err
	}
	if len(events) == 0 {
		return nil
	}

	var (
		subIDs    [][]byte
		subEvents []model.Event
		subBytes  int
		firstErr  error
	)
	flushSub := func() error {
		if len(subEvents) == 0 {
			return nil
		}
		if sendErr := b.sender.Send(ctx, subEvents); sendErr != nil {
			var authErr *sender.AuthError
			if errors.As(sendErr, &authErr) {
				b.logger.Printf("token rejeté par le serveur — vérifiez qu'il est actif: %v", authErr)
			}
			return sendErr
		}
		return b.spool.Ack(subIDs)
	}

	for i, e := range events {
		raw, _ := json.Marshal(e)
		if subBytes+len(raw) > b.maxBytes && len(subEvents) > 0 {
			if err := flushSub(); err != nil {
				return err
			}
			subIDs, subEvents, subBytes = nil, nil, 0
		}
		subIDs = append(subIDs, ids[i])
		subEvents = append(subEvents, e)
		subBytes += len(raw)
	}
	if err := flushSub(); err != nil {
		firstErr = err
	}
	return firstErr
}
