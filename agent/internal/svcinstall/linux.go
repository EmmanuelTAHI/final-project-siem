//go:build !windows

// Package svcinstall gère l'installation/désinstallation de l'agent comme
// service natif de l'OS — systemd sur Linux (ce fichier), Service Control
// Manager sur Windows (svcinstall_windows.go).
package svcinstall

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"

	"logplus-agent/internal/config"
)

const (
	serviceName = "logplus-agent"
	unitPath    = "/etc/systemd/system/logplus-agent.service"
)

const unitTemplate = `[Unit]
Description=Log+ Agent — collecte de logs vers Log+
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=%s run
Restart=always
RestartSec=5
User=root
WorkingDirectory=%s

[Install]
WantedBy=multi-user.target
`

// Install copie le binaire courant dans le répertoire de l'agent, écrit la
// config avec permissions restrictives, installe et démarre le service
// systemd. Doit être appelé en root — sinon échoue explicitement (jamais de
// contournement silencieux d'un besoin de privilège).
func Install(cfg config.Config) error {
	if os.Geteuid() != 0 {
		return fmt.Errorf("l'installation nécessite les droits root (relancez avec sudo)")
	}

	dir := config.Dir()
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return fmt.Errorf("création %s: %w", dir, err)
	}

	binDest := filepath.Join(dir, serviceName)
	if err := copySelfTo(binDest); err != nil {
		return fmt.Errorf("copie du binaire: %w", err)
	}

	if err := config.Save(cfg); err != nil {
		return fmt.Errorf("écriture config: %w", err)
	}

	unit := fmt.Sprintf(unitTemplate, binDest, dir)
	if err := os.WriteFile(unitPath, []byte(unit), 0o644); err != nil {
		return fmt.Errorf("écriture unité systemd: %w", err)
	}

	if err := runSystemctl("daemon-reload"); err != nil {
		return err
	}
	if err := runSystemctl("enable", "--now", serviceName); err != nil {
		return err
	}
	return nil
}

// Uninstall arrête, désactive et supprime proprement tous les fichiers
// installés (service + binaire + config + spool).
func Uninstall() error {
	if os.Geteuid() != 0 {
		return fmt.Errorf("la désinstallation nécessite les droits root (relancez avec sudo)")
	}
	_ = runSystemctl("stop", serviceName)
	_ = runSystemctl("disable", serviceName)
	_ = os.Remove(unitPath)
	_ = runSystemctl("daemon-reload")
	return os.RemoveAll(config.Dir())
}

// Status renvoie l'état actif/inactif du service (pour `logplus-agent status`).
func Status() (string, error) {
	out, err := exec.Command("systemctl", "is-active", serviceName).CombinedOutput()
	return string(out), err
}

func runSystemctl(args ...string) error {
	cmd := exec.Command("systemctl", args...)
	out, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("systemctl %v: %w (%s)", args, err, string(out))
	}
	return nil
}
