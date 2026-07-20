package svcinstall

import (
	"io"
	"os"
	"path/filepath"
	"runtime"
	"strings"
)

// copySelfTo copie le binaire actuellement en cours d'exécution vers dest,
// avec permissions d'exécution — utilisé par install (Linux et Windows)
// pour ne pas dépendre du chemin depuis lequel l'utilisateur a lancé le
// binaire téléchargé (ex: /tmp, Téléchargements...).
//
// Si dest est déjà le binaire en cours d'exécution (ex: `install` relancé
// directement depuis le chemin où l'agent est déjà installé, plutôt que
// depuis le script d'installation), on ne fait rien : Windows interdit de
// remplacer l'image d'un process qui tourne, la copie échouerait de toute
// façon avec "Access is denied" — et de toute façon rien à copier puisque
// c'est déjà le bon binaire au bon endroit.
func copySelfTo(dest string) error {
	self, err := os.Executable()
	if err != nil {
		return err
	}

	if selfAbs, err := filepath.Abs(self); err == nil {
		if destAbs, err := filepath.Abs(dest); err == nil && samePath(selfAbs, destAbs) {
			return nil
		}
	}

	src, err := os.Open(self)
	if err != nil {
		return err
	}
	defer src.Close()

	tmp := dest + ".tmp"
	out, err := os.OpenFile(tmp, os.O_CREATE|os.O_TRUNC|os.O_WRONLY, 0o755)
	if err != nil {
		return err
	}
	if _, err := io.Copy(out, src); err != nil {
		out.Close()
		os.Remove(tmp)
		return err
	}
	if err := out.Close(); err != nil {
		return err
	}
	return os.Rename(tmp, dest)
}

func samePath(a, b string) bool {
	if runtime.GOOS == "windows" {
		return strings.EqualFold(a, b)
	}
	return a == b
}
