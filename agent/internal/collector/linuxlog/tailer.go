//go:build !windows

// Package linuxlog collecte les logs sur Linux : tail de fichiers (avec
// reprise de position et gestion de rotation), lecture journald, et
// écoute syslog locale optionnelle. Pas de dépendance externe : polling
// stdlib uniquement (pas d'inotify), suffisant pour du texte de log et
// robuste sur tous les systèmes de fichiers.
package linuxlog

import (
	"bufio"
	"context"
	"encoding/binary"
	"fmt"
	"os"
	"strings"
	"syscall"
	"time"

	"logplus-agent/internal/model"
	"logplus-agent/internal/spool"
)

const pollInterval = 1 * time.Second

// FileTailer suit un fichier de log, reprend après la dernière position
// connue (persistée dans le spool), et détecte la rotation (changement
// d'inode) pour repartir du début du nouveau fichier.
type FileTailer struct {
	Path string
	sp   *spool.Spool
}

func NewFileTailer(path string, sp *spool.Spool) *FileTailer {
	return &FileTailer{Path: path, sp: sp}
}

func (t *FileTailer) metaKey() string { return "linuxlog:offset:" + t.Path }

func (t *FileTailer) loadOffset() (offset int64, inode uint64, ok bool) {
	raw, err := t.sp.GetMeta(t.metaKey())
	if err != nil || len(raw) != 16 {
		return 0, 0, false
	}
	offset = int64(binary.BigEndian.Uint64(raw[0:8]))
	inode = binary.BigEndian.Uint64(raw[8:16])
	return offset, inode, true
}

func (t *FileTailer) saveOffset(offset int64, inode uint64) {
	buf := make([]byte, 16)
	binary.BigEndian.PutUint64(buf[0:8], uint64(offset))
	binary.BigEndian.PutUint64(buf[8:16], inode)
	_ = t.sp.SetMeta(t.metaKey(), buf)
}

func fileInode(f *os.File) (uint64, error) {
	info, err := f.Stat()
	if err != nil {
		return 0, err
	}
	sys, ok := info.Sys().(*syscall.Stat_t)
	if !ok {
		return 0, fmt.Errorf("stat_t indisponible pour %s", f.Name())
	}
	return sys.Ino, nil
}

// Run bloque jusqu'à annulation du contexte, appelant emit() pour chaque
// nouvelle ligne. Ne fait jamais planter l'agent si le fichier est
// temporairement absent (permissions, rotation logrotate...) : réessaie au
// prochain tick.
func (t *FileTailer) Run(ctx context.Context, emit func(model.Event)) {
	ticker := time.NewTicker(pollInterval)
	defer ticker.Stop()

	savedOffset, savedInode, hadOffset := t.loadOffset()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			f, err := os.Open(t.Path)
			if err != nil {
				continue // fichier absent/inaccessible pour l'instant, on retentera
			}

			inode, err := fileInode(f)
			if err != nil {
				f.Close()
				continue
			}

			var start int64
			switch {
			case !hadOffset:
				// Premier démarrage : on ne relit pas tout l'historique,
				// seulement ce qui arrive à partir de maintenant.
				info, statErr := f.Stat()
				if statErr == nil {
					start = info.Size()
				}
				hadOffset = true
			case inode != savedInode:
				// Rotation détectée (logrotate...) : nouveau fichier, on repart du début.
				start = 0
			default:
				start = savedOffset
			}

			info, statErr := f.Stat()
			if statErr == nil && info.Size() < start {
				// Le fichier a été tronqué (ex: > file plutôt que rotation) : repartir du début.
				start = 0
			}

			if _, err := f.Seek(start, 0); err != nil {
				f.Close()
				continue
			}

			scanner := bufio.NewScanner(f)
			scanner.Buffer(make([]byte, 64*1024), 1<<20)
			var lastOffset = start
			for scanner.Scan() {
				line := scanner.Text()
				if strings.TrimSpace(line) == "" {
					continue
				}
				emit(model.Event{
					Message:  line,
					Source:   "linuxlog",
					Severity: "info",
					RawFields: map[string]interface{}{
						"file": t.Path,
					},
				})
			}
			if pos, err := f.Seek(0, 1); err == nil {
				lastOffset = pos
			}
			f.Close()

			savedOffset, savedInode = lastOffset, inode
			t.saveOffset(savedOffset, savedInode)
		}
	}
}
