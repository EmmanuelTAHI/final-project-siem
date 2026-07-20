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
	TimeCreated time.Time              `json:"time_created,omitempty"`
	RawFields   map[string]interface{} `json:"raw_fields,omitempty"`
}
