// Package config gère le chargement/écriture de la configuration locale de
// l'agent (URL du SIEM, token, sources à surveiller). Le token est toujours
// stocké chiffré au repos sur Windows (DPAPI, voir secret_windows.go) ; sur
// Linux il est protégé par les permissions du fichier (0600, root only) —
// voir secret_linux.go pour le détail de ce choix.
package config

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
)

// Config est le format persistant du fichier de config de l'agent.
type Config struct {
	URL      string `json:"url"`
	Hostname string `json:"hostname,omitempty"`

	// TokenSecret est soit le token en clair (Linux), soit un blob chiffré
	// DPAPI encodé base64 (Windows) — voir secret_linux.go / secret_windows.go.
	TokenSecret string `json:"token_secret"`

	FlushIntervalSeconds int  `json:"flush_interval_seconds"`
	MaxBatchLines         int  `json:"max_batch_lines"`
	MaxBatchBytes         int  `json:"max_batch_bytes"`
	Insecure              bool `json:"insecure,omitempty"` // dev only : autorise http:// non chiffré

	// Linux
	LinuxSources     []string `json:"linux_sources,omitempty"`
	LinuxJournald    bool     `json:"linux_journald"`
	SyslogListenAddr string   `json:"syslog_listen_addr,omitempty"`

	// Windows
	WindowsChannels []string `json:"windows_channels,omitempty"`
}

// DefaultConfig renvoie une config avec des valeurs sûres par défaut.
func DefaultConfig() Config {
	c := Config{
		FlushIntervalSeconds: 5,
		MaxBatchLines:        500,
		MaxBatchBytes:        1 << 20, // 1 Mo
	}
	if runtime.GOOS == "windows" {
		c.WindowsChannels = []string{"Security", "System"}
	} else {
		c.LinuxJournald = true
	}
	return c
}

// Dir renvoie le répertoire où vivent la config, le spool et les logs de
// l'agent, selon l'OS.
func Dir() string {
	if runtime.GOOS == "windows" {
		programData := os.Getenv("ProgramData")
		if programData == "" {
			programData = `C:\ProgramData`
		}
		return filepath.Join(programData, "LogplusAgent")
	}
	return "/opt/logplus-agent"
}

func ConfigPath() string { return filepath.Join(Dir(), "config.json") }
func SpoolPath() string  { return filepath.Join(Dir(), "spool.db") }
func LogPath() string    { return filepath.Join(Dir(), "agent.log") }

// Load lit la config depuis disque et déchiffre le token (Token()).
func Load() (Config, error) {
	var c Config
	raw, err := os.ReadFile(ConfigPath())
	if err != nil {
		return c, fmt.Errorf("lecture config %s: %w", ConfigPath(), err)
	}
	if err := json.Unmarshal(raw, &c); err != nil {
		return c, fmt.Errorf("parsing config: %w", err)
	}
	return c, nil
}

// Token renvoie le secret en clair, en le déchiffrant si nécessaire
// (no-op sur Linux, DPAPI sur Windows).
func (c Config) Token() (string, error) {
	return decryptToken(c.TokenSecret)
}

// SetToken chiffre (si applicable) et stocke le token en clair fourni.
func (c *Config) SetToken(plaintext string) error {
	enc, err := encryptToken(plaintext)
	if err != nil {
		return err
	}
	c.TokenSecret = enc
	return nil
}

// Save écrit la config sur disque avec des permissions restrictives.
// Sur Linux : 0600 (root only, cf. install en tant que root).
// Sur Windows : ACL restreinte posée séparément par svcinstall (le fichier
// lui-même est écrit avec les permissions par défaut du répertoire parent,
// déjà verrouillé à Administrateurs/SYSTEM par l'installation du service).
func Save(c Config) error {
	if err := os.MkdirAll(Dir(), 0o700); err != nil {
		return fmt.Errorf("création %s: %w", Dir(), err)
	}
	raw, err := json.MarshalIndent(c, "", "  ")
	if err != nil {
		return err
	}
	tmp := ConfigPath() + ".tmp"
	if err := os.WriteFile(tmp, raw, 0o600); err != nil {
		return fmt.Errorf("écriture config: %w", err)
	}
	return os.Rename(tmp, ConfigPath())
}
