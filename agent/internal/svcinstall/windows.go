//go:build windows

package svcinstall

import (
	"fmt"
	"os"
	"path/filepath"
	"syscall"
	"time"

	"golang.org/x/sys/windows"
	"golang.org/x/sys/windows/svc"
	"golang.org/x/sys/windows/svc/mgr"

	"logplus-agent/internal/config"
)

const ServiceName = "LogplusAgent"

// Install copie le binaire courant, écrit la config (token déjà chiffré
// DPAPI par cfg.SetToken), puis enregistre et démarre un vrai service
// Windows (démarrage automatique, redémarrage sur crash). Nécessite des
// droits administrateur — échoue explicitement sinon, jamais de
// contournement silencieux.
func Install(cfg config.Config) error {
	dir := config.Dir()
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return fmt.Errorf("création %s: %w", dir, err)
	}
	binDest := filepath.Join(dir, "logplus-agent.exe")

	m, err := mgr.Connect()
	if err != nil {
		return fmt.Errorf("connexion au gestionnaire de services échouée (droits administrateur requis, relancez le terminal \"en tant qu'administrateur\"): %w", err)
	}
	defer m.Disconnect()

	// Réinstallation : on arrête et supprime le service existant AVANT de
	// toucher au binaire — sinon la copie/le remplacement de
	// logplus-agent.exe échoue avec "Access is denied" tant que l'ancien
	// service (ou ce process-ci, si on le relance depuis son propre chemin
	// d'installation) le verrouille encore.
	if existing, err := m.OpenService(ServiceName); err == nil {
		existing.Control(svc.Stop)
		waitForStopped(existing, 10*time.Second)
		existing.Delete()
		existing.Close()
	}

	if err := copySelfTo(binDest); err != nil {
		return fmt.Errorf("copie du binaire: %w", err)
	}

	if err := config.Save(cfg); err != nil {
		return fmt.Errorf("écriture config: %w", err)
	}

	s, err := m.CreateService(ServiceName, binDest, mgr.Config{
		DisplayName:  "Log+ Agent",
		Description:  "Collecte les journaux d'événements Windows et les envoie à Log+.",
		StartType:    mgr.StartAutomatic,
		ErrorControl: mgr.ErrorNormal,
	}, "run")
	if err != nil {
		return fmt.Errorf("création du service: %w", err)
	}
	defer s.Close()

	if err := s.Start(); err != nil {
		return fmt.Errorf("démarrage du service: %w", err)
	}
	return nil
}

// Uninstall arrête, supprime le service et efface les fichiers de l'agent
// (config, spool, logs). Nécessite des droits administrateur.
func Uninstall() error {
	m, err := mgr.Connect()
	if err != nil {
		return fmt.Errorf("connexion au gestionnaire de services échouée (droits administrateur requis): %w", err)
	}
	defer m.Disconnect()

	s, err := m.OpenService(ServiceName)
	if err != nil {
		return fmt.Errorf("service non installé")
	}
	defer s.Close()

	_, _ = s.Control(svc.Stop)
	waitForStopped(s, 10*time.Second)
	if err := s.Delete(); err != nil {
		return fmt.Errorf("suppression du service: %w", err)
	}

	// `uninstall` s'exécute lui-même depuis logplus-agent.exe : Windows
	// verrouille le fichier image d'un processus tant qu'il tourne, donc CE
	// binaire ne peut pas se supprimer synchronement (contrairement à
	// Linux). On supprime tout ce qui n'est pas verrouillé immédiatement...
	dir := config.Dir()
	binPath := filepath.Join(dir, "logplus-agent.exe")
	entries, _ := os.ReadDir(dir)
	for _, e := range entries {
		if e.Name() == "logplus-agent.exe" {
			continue
		}
		_ = os.RemoveAll(filepath.Join(dir, e.Name()))
	}

	// ... puis on tente quelques fois la suppression du .exe (le verrou
	// s'ouvre généralement dès que ce processus est prêt à quitter), et en
	// dernier recours on la planifie au prochain redémarrage via l'API
	// Windows prévue pour exactement ce cas (MOVEFILE_DELAY_UNTIL_REBOOT) —
	// jamais d'échec bloquant sur ce point.
	deferredCleanup := false
	var lastErr error
	for i := 0; i < 6; i++ {
		if lastErr = os.Remove(binPath); lastErr == nil {
			break
		}
		time.Sleep(300 * time.Millisecond)
	}
	if lastErr != nil {
		if err := scheduleDeleteOnReboot(binPath); err != nil {
			return fmt.Errorf("service désinstallé, mais %s n'a pas pu être supprimé (ni immédiatement ni au prochain démarrage) : %w", binPath, err)
		}
		deferredCleanup = true
	}

	_ = os.Remove(dir) // best-effort ; échoue silencieusement si le .exe est encore là (nettoyage différé)

	if deferredCleanup {
		return fmt.Errorf("service désinstallé ; %s sera supprimé automatiquement au prochain redémarrage de la machine (verrouillé par ce processus tant qu'il tourne)", binPath)
	}
	return nil
}

// scheduleDeleteOnReboot marque path pour suppression au prochain démarrage
// de Windows — mécanisme natif (MOVEFILE_DELAY_UNTIL_REBOOT), utilisé
// quand un fichier reste verrouillé par le processus en cours (soi-même).
func scheduleDeleteOnReboot(path string) error {
	p, err := syscall.UTF16PtrFromString(path)
	if err != nil {
		return err
	}
	return windows.MoveFileEx(p, nil, windows.MOVEFILE_DELAY_UNTIL_REBOOT)
}

// waitForStopped attend que le service atteigne l'état Stopped (ou le
// délai imparti), pour éviter de tenter la suppression des fichiers tant
// que le processus n'a pas réellement fini de se terminer.
func waitForStopped(s *mgr.Service, timeout time.Duration) {
	deadline := time.Now().Add(timeout)
	for time.Now().Before(deadline) {
		status, err := s.Query()
		if err != nil || status.State == svc.Stopped {
			return
		}
		time.Sleep(200 * time.Millisecond)
	}
}

// Status renvoie l'état actuel du service (Running/Stopped/...).
func Status() (string, error) {
	m, err := mgr.Connect()
	if err != nil {
		return "", fmt.Errorf("connexion au gestionnaire de services échouée: %w", err)
	}
	defer m.Disconnect()

	s, err := m.OpenService(ServiceName)
	if err != nil {
		return "non installé", nil
	}
	defer s.Close()

	status, err := s.Query()
	if err != nil {
		return "", err
	}
	return stateString(status.State), nil
}

func stateString(state svc.State) string {
	switch state {
	case svc.Stopped:
		return "arrêté"
	case svc.StartPending:
		return "démarrage en cours"
	case svc.StopPending:
		return "arrêt en cours"
	case svc.Running:
		return "actif"
	default:
		return fmt.Sprintf("état %d", state)
	}
}
