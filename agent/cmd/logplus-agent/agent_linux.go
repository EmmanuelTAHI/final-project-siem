//go:build !windows

package main

import "log"

// Sur Linux, systemd exécute directement `logplus-agent run` comme
// processus superviseé (pas de dispatcher de service séparé) : le mode
// avant-plan standard suffit.
func runAgent(logger *log.Logger) error {
	return runForeground(logger)
}
