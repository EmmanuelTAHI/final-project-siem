//go:build windows

package config

import (
	"encoding/base64"
	"fmt"
	"unsafe"

	"golang.org/x/sys/windows"
)

// Sur Windows, le token est chiffré au repos via DPAPI (CryptProtectData),
// sans entropie supplémentaire fournie explicitement : la clé est dérivée
// par Windows à partir des secrets de la machine (le service tourne en
// LocalSystem), donc le blob n'est déchiffrable que sur cette machine, par
// ce compte de service — un fichier de config copié ailleurs est inutile.

func encryptToken(plaintext string) (string, error) {
	if plaintext == "" {
		return "", nil
	}
	plainBytes := []byte(plaintext)
	in := windows.DataBlob{
		Size: uint32(len(plainBytes)),
		Data: &plainBytes[0],
	}
	var out windows.DataBlob
	if err := windows.CryptProtectData(&in, nil, nil, 0, nil, windows.CRYPTPROTECT_LOCAL_MACHINE, &out); err != nil {
		return "", fmt.Errorf("CryptProtectData: %w", err)
	}
	defer windows.LocalFree(windows.Handle(unsafe.Pointer(out.Data)))
	cipher := unsafe.Slice(out.Data, out.Size)
	return base64.StdEncoding.EncodeToString(cipher), nil
}

func decryptToken(stored string) (string, error) {
	if stored == "" {
		return "", nil
	}
	cipher, err := base64.StdEncoding.DecodeString(stored)
	if err != nil {
		return "", fmt.Errorf("token stocké invalide (base64): %w", err)
	}
	in := windows.DataBlob{
		Size: uint32(len(cipher)),
		Data: &cipher[0],
	}
	var out windows.DataBlob
	if err := windows.CryptUnprotectData(&in, nil, nil, 0, nil, windows.CRYPTPROTECT_LOCAL_MACHINE, &out); err != nil {
		return "", fmt.Errorf("CryptUnprotectData (le token a-t-il été chiffré sur une autre machine ?): %w", err)
	}
	defer windows.LocalFree(windows.Handle(unsafe.Pointer(out.Data)))
	plain := unsafe.Slice(out.Data, out.Size)
	return string(plain), nil
}
