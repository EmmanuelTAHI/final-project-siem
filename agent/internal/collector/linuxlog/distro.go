//go:build !windows

package linuxlog

import (
	"bufio"
	"os"
	"strings"
)

// DefaultAuthLogPath détecte la distribution via /etc/os-release et renvoie
// le chemin usuel du journal d'authentification. Renvoie une liste (les deux
// chemins existent sur certains systèmes hybrides) filtrée aux fichiers qui
// existent réellement, pour ne pas configurer un tail sur un fichier absent.
func DefaultAuthLogPaths() []string {
	candidates := []string{"/var/log/auth.log", "/var/log/secure"}

	id := readOSReleaseID()
	switch id {
	case "debian", "ubuntu", "linuxmint", "raspbian":
		candidates = []string{"/var/log/auth.log", "/var/log/secure"}
	case "rhel", "centos", "fedora", "rocky", "almalinux", "amzn":
		candidates = []string{"/var/log/secure", "/var/log/auth.log"}
	}

	var existing []string
	for _, p := range candidates {
		if _, err := os.Stat(p); err == nil {
			existing = append(existing, p)
		}
	}
	return existing
}

func readOSReleaseID() string {
	f, err := os.Open("/etc/os-release")
	if err != nil {
		return ""
	}
	defer f.Close()

	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := scanner.Text()
		if strings.HasPrefix(line, "ID=") {
			return strings.Trim(strings.TrimPrefix(line, "ID="), `"`)
		}
	}
	return ""
}
