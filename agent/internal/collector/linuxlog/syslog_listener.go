//go:build !windows

package linuxlog

import (
	"bufio"
	"bytes"
	"context"
	"log"
	"net"

	"logplus-agent/internal/model"
)

// RunSyslogListener écoute en UDP local (ex: 127.0.0.1:1514 ou :514) pour
// relayer les logs d'équipements réseau du LAN qui pointent vers ce poste —
// l'agent sert alors aussi de petit relais syslog, réutilisant le parsing
// RFC3164 déjà mûr côté serveur (mêmes règles que rsyslog/receive_syslog).
func RunSyslogListener(ctx context.Context, addr string, logger *log.Logger, emit func(model.Event)) error {
	udpAddr, err := net.ResolveUDPAddr("udp", addr)
	if err != nil {
		return err
	}
	conn, err := net.ListenUDP("udp", udpAddr)
	if err != nil {
		return err
	}
	go func() {
		<-ctx.Done()
		conn.Close()
	}()

	logger.Printf("relais syslog local actif sur %s", addr)
	buf := make([]byte, 64*1024)
	for {
		n, remote, err := conn.ReadFromUDP(buf)
		if err != nil {
			if ctx.Err() != nil {
				return nil
			}
			continue
		}
		// Un paquet UDP syslog peut contenir plusieurs lignes.
		scanner := bufio.NewScanner(bytes.NewReader(buf[:n]))
		for scanner.Scan() {
			line := scanner.Text()
			if line == "" {
				continue
			}
			emit(model.Event{
				Message:  line,
				Source:   "linuxlog",
				Severity: "info",
				RawFields: map[string]interface{}{
					"relay_source_ip": remote.IP.String(),
				},
			})
		}
	}
}
