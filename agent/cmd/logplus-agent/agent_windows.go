//go:build windows

package main

import (
	"context"
	"log"

	"golang.org/x/sys/windows/svc"

	"logplus-agent/internal/config"
	"logplus-agent/internal/runner"
	"logplus-agent/internal/svcinstall"
)

// runAgent détecte si le processus a été lancé par le Service Control
// Manager (installation en service) ou manuellement (test interactif).
// Dans le premier cas, il FAUT appeler svc.Run pour répondre correctement
// aux contrôles Start/Stop du SCM — un simple bouclage en avant-plan ferait
// échouer le démarrage du service ("ne répond pas dans le délai imparti").
func runAgent(logger *log.Logger) error {
	isService, err := svc.IsWindowsService()
	if err != nil {
		return err
	}
	if !isService {
		return runForeground(logger)
	}
	return svc.Run(svcinstall.ServiceName, &windowsServiceHandler{logger: logger})
}

type windowsServiceHandler struct {
	logger *log.Logger
}

func (h *windowsServiceHandler) Execute(_ []string, r <-chan svc.ChangeRequest, changes chan<- svc.Status) (bool, uint32) {
	changes <- svc.Status{State: svc.StartPending}

	cfg, err := config.Load()
	if err != nil {
		h.logger.Printf("chargement config échoué: %v", err)
		changes <- svc.Status{State: svc.Stopped}
		return true, 1
	}

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	errCh := make(chan error, 1)
	go func() { errCh <- runner.Run(ctx, cfg, h.logger) }()

	changes <- svc.Status{State: svc.Running, Accepts: svc.AcceptStop | svc.AcceptShutdown}

	for {
		select {
		case req := <-r:
			switch req.Cmd {
			case svc.Interrogate:
				changes <- req.CurrentStatus
			case svc.Stop, svc.Shutdown:
				changes <- svc.Status{State: svc.StopPending}
				cancel()
				<-errCh
				changes <- svc.Status{State: svc.Stopped}
				return false, 0
			}
		case runErr := <-errCh:
			if runErr != nil {
				h.logger.Printf("agent arrêté avec erreur: %v", runErr)
			}
			changes <- svc.Status{State: svc.Stopped}
			return runErr != nil, boolToExitCode(runErr != nil)
		}
	}
}

func boolToExitCode(failed bool) uint32 {
	if failed {
		return 1
	}
	return 0
}
