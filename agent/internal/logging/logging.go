// Package logging fournit un logger de diagnostic de l'agent lui-même,
// toujours écrit dans un fichier local (jamais seulement stdout, puisque
// l'agent tourne comme service sans console attachée) avec une rotation
// simple par taille.
package logging

import (
	"fmt"
	"io"
	"log"
	"os"
	"path/filepath"
	"sync"
)

const maxSizeBytes = 5 << 20 // 5 Mo par fichier, une seule rotation (.log -> .log.1)

type rotatingWriter struct {
	mu   sync.Mutex
	path string
	f    *os.File
	size int64
}

func newRotatingWriter(path string) (*rotatingWriter, error) {
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		return nil, err
	}
	w := &rotatingWriter{path: path}
	if err := w.open(); err != nil {
		return nil, err
	}
	return w, nil
}

func (w *rotatingWriter) open() error {
	f, err := os.OpenFile(w.path, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o600)
	if err != nil {
		return err
	}
	info, err := f.Stat()
	if err != nil {
		f.Close()
		return err
	}
	w.f = f
	w.size = info.Size()
	return nil
}

func (w *rotatingWriter) Write(p []byte) (int, error) {
	w.mu.Lock()
	defer w.mu.Unlock()

	if w.size+int64(len(p)) > maxSizeBytes {
		w.f.Close()
		_ = os.Rename(w.path, w.path+".1")
		if err := w.open(); err != nil {
			return 0, err
		}
	}
	n, err := w.f.Write(p)
	w.size += int64(n)
	return n, err
}

// New crée un *log.Logger qui écrit dans path (fichier tournant) et, si
// alsoStderr est vrai, aussi sur stderr (utile en mode `run` interactif).
func New(path string, alsoStderr bool) (*log.Logger, error) {
	w, err := newRotatingWriter(path)
	if err != nil {
		return nil, fmt.Errorf("ouverture log %s: %w", path, err)
	}
	var out io.Writer = w
	if alsoStderr {
		out = io.MultiWriter(w, os.Stderr)
	}
	return log.New(out, "", log.LstdFlags|log.Lmicroseconds), nil
}
