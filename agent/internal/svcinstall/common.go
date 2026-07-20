package svcinstall

import (
	"io"
	"os"
)

// copySelfTo copie le binaire actuellement en cours d'exécution vers dest,
// avec permissions d'exécution — utilisé par install (Linux et Windows)
// pour ne pas dépendre du chemin depuis lequel l'utilisateur a lancé le
// binaire téléchargé (ex: /tmp, Téléchargements...).
func copySelfTo(dest string) error {
	self, err := os.Executable()
	if err != nil {
		return err
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
