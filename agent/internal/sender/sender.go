// Package sender envoie les batches d'événements vers l'endpoint
// d'ingestion Log+ (POST /api/ingest/agent/logs/), en NDJSON compressé
// gzip, avec une vérification TLS stricte (jamais de bypass de certificat
// en usage normal — voir Insecure ci-dessous, réservé au dev local).
package sender

import (
	"bytes"
	"compress/gzip"
	"context"
	"crypto/tls"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"strings"
	"time"

	"logplus-agent/internal/model"
)

type Sender struct {
	ingestURL string
	token     string
	client    *http.Client
	logger    *log.Logger
}

// New construit un Sender. baseURL est l'URL racine de l'instance Log+
// (ex: https://logplus.duckdns.org) ; insecure=true désactive la
// vérification du certificat TLS et autorise http:// — réservé
// explicitement au développement local (voir config.Insecure).
func New(baseURL, token string, insecure bool, logger *log.Logger) (*Sender, error) {
	if !insecure && !strings.HasPrefix(baseURL, "https://") {
		return nil, fmt.Errorf("URL %q non chiffrée refusée (utiliser https://, ou --insecure explicitement en dev)", baseURL)
	}
	transport := &http.Transport{}
	if insecure {
		transport.TLSClientConfig = &tls.Config{InsecureSkipVerify: true} //nolint:gosec // dev only, opt-in explicite
	}
	return &Sender{
		ingestURL: strings.TrimRight(baseURL, "/") + "/api/ingest/agent/logs/",
		token:     token,
		client:    &http.Client{Timeout: 30 * time.Second, Transport: transport},
		logger:    logger,
	}, nil
}

// Send envoie un batch d'événements en une requête. Ne fait AUCUNE
// tentative de retry interne : c'est le rôle de l'appelant (batcher), qui
// garde les événements dans le spool tant qu'ils ne sont pas confirmés.
func (s *Sender) Send(ctx context.Context, events []model.Event) error {
	if len(events) == 0 {
		return nil
	}
	var buf bytes.Buffer
	gz := gzip.NewWriter(&buf)
	enc := json.NewEncoder(gz)
	for _, e := range events {
		if err := enc.Encode(e); err != nil {
			return fmt.Errorf("encodage NDJSON: %w", err)
		}
	}
	if err := gz.Close(); err != nil {
		return fmt.Errorf("compression gzip: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, s.ingestURL, &buf)
	if err != nil {
		return err
	}
	req.Header.Set("Authorization", "Bearer "+s.token)
	req.Header.Set("Content-Type", "application/x-ndjson")
	req.Header.Set("Content-Encoding", "gzip")

	resp, err := s.client.Do(req)
	if err != nil {
		return fmt.Errorf("requête réseau: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusUnauthorized || resp.StatusCode == http.StatusForbidden {
		body, _ := io.ReadAll(io.LimitReader(resp.Body, 2048))
		return &AuthError{StatusCode: resp.StatusCode, Body: string(body)}
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		body, _ := io.ReadAll(io.LimitReader(resp.Body, 2048))
		return fmt.Errorf("serveur %d: %s", resp.StatusCode, string(body))
	}
	return nil
}

// AuthError signale un rejet d'authentification (token invalide/révoqué) :
// contrairement à une panne réseau, ce n'est pas transitoire — l'appelant
// peut choisir d'espacer nettement plus les tentatives plutôt que de
// marteler le serveur avec un token qui ne sera jamais accepté.
type AuthError struct {
	StatusCode int
	Body       string
}

func (e *AuthError) Error() string {
	return fmt.Sprintf("authentification refusée (%d) — le token est-il valide et actif ? %s", e.StatusCode, e.Body)
}

// TestConnection envoie un unique événement de test explicitement identifié
// comme tel, pour valider url+token avant une installation complète.
func (s *Sender) TestConnection(ctx context.Context, hostname string) error {
	return s.Send(ctx, []model.Event{{
		Message:  "Log+ agent : test de connexion (logplus-agent test-connection)",
		Hostname: hostname,
		Severity: "info",
		Source:   "agent_selftest",
	}})
}
