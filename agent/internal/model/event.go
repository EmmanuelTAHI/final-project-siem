// Package model définit le format d'événement partagé par tous les collecteurs
// (Linux, Windows) et envoyé tel quel (NDJSON) à l'endpoint d'ingestion Log+.
package model

import "time"

// Event est une ligne de log structurée. Chaque champ correspond à ce que
// backend/apps/logs/normalizer.py::_map_agent_event sait lire côté serveur.
type Event struct {
	Message     string                 `json:"message"`
	Hostname    string                 `json:"hostname,omitempty"`
	Severity    string                 `json:"severity,omitempty"`
	Source      string                 `json:"source"` // "linuxlog" | "wineventlog" | "syslog_relay"
	EventID     int                    `json:"event_id,omitempty"`
	Provider    string                 `json:"provider,omitempty"`
	Channel     string                 `json:"channel,omitempty"`
	Computer    string                 `json:"computer,omitempty"`
	// Pointeur, pas time.Time : la valeur zéro d'un struct n'est jamais
	// omise par `omitempty` (contrairement à une chaîne/un nombre), donc un
	// time.Time{} non renseigné se serait sérialisé en "0001-01-01T...",
	// une date invalide silencieusement acceptée côté backend. nil = non
	// renseigné (ex: sources Linux, qui n'ont pas d'horodatage natif fiable
	// distinct de la réception) ; seul le collecteur Windows le remplit.
	TimeCreated *time.Time             `json:"time_created,omitempty"`
	RawFields   map[string]interface{} `json:"raw_fields,omitempty"`
}
