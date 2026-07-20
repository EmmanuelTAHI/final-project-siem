// Command logplus-agent est l'agent de collecte de logs natif Log+
// (Linux : tail de fichiers + journald + relais syslog local ;
// Windows : Event Log natif). Sous-commandes : run, install, uninstall,
// status, test-connection.
package main

import (
	"context"
	"flag"
	"fmt"
	"io"
	"log"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"logplus-agent/internal/config"
	"logplus-agent/internal/logging"
	"logplus-agent/internal/runner"
	"logplus-agent/internal/sender"
	"logplus-agent/internal/svcinstall"
)

const usage = `logplus-agent — agent de collecte de logs natif Log+

Usage:
  logplus-agent install --url=<https://...> --token=<logplus_agt_...> [--insecure] [--linux-syslog-addr=addr]
  logplus-agent uninstall
  logplus-agent status
  logplus-agent test-connection --url=<https://...> --token=<logplus_agt_...> [--insecure]
  logplus-agent run                 (généralement lancé par le service, pas manuellement)
`

func main() {
	if len(os.Args) < 2 {
		fmt.Fprint(os.Stderr, usage)
		os.Exit(1)
	}

	var err error
	switch os.Args[1] {
	case "install":
		err = cmdInstall(os.Args[2:])
	case "uninstall":
		err = cmdUninstall()
	case "status":
		err = cmdStatus()
	case "test-connection":
		err = cmdTestConnection(os.Args[2:])
	case "run":
		err = cmdRun()
	case "-h", "--help", "help":
		fmt.Print(usage)
		return
	default:
		fmt.Fprintf(os.Stderr, "commande inconnue: %s\n\n%s", os.Args[1], usage)
		os.Exit(1)
	}

	if err != nil {
		fmt.Fprintf(os.Stderr, "erreur: %v\n", err)
		os.Exit(1)
	}
}

func cmdInstall(args []string) error {
	fs := flag.NewFlagSet("install", flag.ExitOnError)
	url := fs.String("url", "", "URL de l'instance Log+ (ex: https://logplus.duckdns.org)")
	token := fs.String("token", "", "Token d'agent (logplus_agt_...) — préférez LOGPLUS_AGENT_TOKEN en variable d'environnement, jamais visible dans la liste des process")
	insecure := fs.Bool("insecure", false, "Autorise http:// non chiffré (dev local uniquement)")
	syslogAddr := fs.String("linux-syslog-addr", "", "Active un relais syslog local sur cette adresse (ex: 0.0.0.0:1514), Linux uniquement")
	if err := fs.Parse(args); err != nil {
		return err
	}
	// La variable d'environnement est le canal privilégié : un token passé en
	// --token reste visible en clair dans la liste des process (ps/Task
	// Manager) tant que la commande install tourne. Les scripts
	// d'installation officiels (install-linux.sh / install-windows.ps1)
	// utilisent LOGPLUS_AGENT_TOKEN pour cette raison.
	if *token == "" {
		*token = os.Getenv("LOGPLUS_AGENT_TOKEN")
	}
	if *url == "" || *token == "" {
		return fmt.Errorf("--url et --token (ou la variable d'environnement LOGPLUS_AGENT_TOKEN) sont requis")
	}
	if !strings.HasPrefix(*token, "logplus_agt_") {
		return fmt.Errorf("le token ne ressemble pas à un token d'agent Log+ (préfixe logplus_agt_ attendu)")
	}

	cfg := config.DefaultConfig()
	cfg.URL = *url
	cfg.Insecure = *insecure
	cfg.SyslogListenAddr = *syslogAddr
	if err := cfg.SetToken(*token); err != nil {
		return fmt.Errorf("chiffrement du token: %w", err)
	}

	// Ne jamais installer un service cassé : on vérifie url+token avant.
	fmt.Println("Vérification de la connexion...")
	if err := testConnection(*url, *token, *insecure); err != nil {
		return fmt.Errorf("test de connexion échoué, installation annulée: %w", err)
	}
	fmt.Println("Connexion OK. Installation du service...")

	if err := svcinstall.Install(cfg); err != nil {
		return err
	}
	fmt.Println("Agent Log+ installé et démarré.")
	return nil
}

func cmdUninstall() error {
	if err := svcinstall.Uninstall(); err != nil {
		return err
	}
	fmt.Println("Agent Log+ désinstallé.")
	return nil
}

func cmdStatus() error {
	out, err := svcinstall.Status()
	fmt.Print(out)
	return err
}

func cmdTestConnection(args []string) error {
	fs := flag.NewFlagSet("test-connection", flag.ExitOnError)
	url := fs.String("url", "", "URL de l'instance Log+")
	token := fs.String("token", "", "Token d'agent")
	insecure := fs.Bool("insecure", false, "Autorise http:// non chiffré (dev local uniquement)")
	if err := fs.Parse(args); err != nil {
		return err
	}
	if *token == "" {
		*token = os.Getenv("LOGPLUS_AGENT_TOKEN")
	}
	if *url == "" || *token == "" {
		return fmt.Errorf("--url et --token (ou la variable d'environnement LOGPLUS_AGENT_TOKEN) sont requis")
	}
	if err := testConnection(*url, *token, *insecure); err != nil {
		return err
	}
	fmt.Println("Connexion réussie.")
	return nil
}

func testConnection(url, token string, insecure bool) error {
	// Le fichier de log peut être inaccessible avant l'installation
	// (répertoire pas encore créé) : on retombe sur un logger silencieux.
	logger, err := logging.New(config.LogPath(), false)
	if err != nil {
		logger = log.New(io.Discard, "", 0)
	}
	sd, err := sender.New(url, token, insecure, logger)
	if err != nil {
		return err
	}
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()
	hostname, _ := os.Hostname()
	return sd.TestConnection(ctx, hostname)
}

func cmdRun() error {
	if err := os.MkdirAll(config.Dir(), 0o700); err != nil {
		return fmt.Errorf("création %s: %w", config.Dir(), err)
	}
	logger, err := logging.New(config.LogPath(), true)
	if err != nil {
		return fmt.Errorf("initialisation logging: %w", err)
	}
	// runAgent est défini par plateforme (agent_linux.go / agent_windows.go) :
	// sur Windows, si lancé par le Service Control Manager, il faut appeler
	// svc.Run (pas juste boucler en avant-plan) pour répondre correctement
	// aux contrôles Start/Stop du SCM. runForeground (identique aux deux OS)
	// est utilisé pour Linux (systemd exec direct) et pour un test manuel
	// interactif sur Windows (`logplus-agent run` hors service).
	return runAgent(logger)
}

// runForeground charge la config et lance runner.Run jusqu'à signal
// d'arrêt (Ctrl+C / SIGTERM) — utilisé directement par Linux (systemd) et
// par Windows en mode interactif (test manuel hors SCM).
func runForeground(logger *log.Logger) error {
	cfg, err := config.Load()
	if err != nil {
		return fmt.Errorf("chargement config (agent installé ?): %w", err)
	}
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	return runner.Run(ctx, cfg, logger)
}
