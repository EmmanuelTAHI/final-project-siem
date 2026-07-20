//go:build !windows

package config

// Sur Linux, le token n'est pas chiffré au repos : la protection vient des
// permissions du fichier de config (0600, propriétaire root — l'agent ne
// s'installe qu'en root, voir svcinstall). Chiffrer avec une clé stockée sur
// la même machine n'apporterait pas de sécurité supplémentaire réelle contre
// un attaquant qui a déjà les droits root nécessaires pour lire le fichier.

func encryptToken(plaintext string) (string, error) { return plaintext, nil }
func decryptToken(stored string) (string, error)    { return stored, nil }
