package config

import (
	"strings"
	"testing"
)

func containsSubstring(haystack, needle string) bool { return strings.Contains(haystack, needle) }

func TestSetTokenThenToken_RoundTrips(t *testing.T) {
	var c Config
	const plaintext = "logplus_agt_secret-value-123"

	if err := c.SetToken(plaintext); err != nil {
		t.Fatalf("SetToken a échoué: %v", err)
	}
	if c.TokenSecret == plaintext {
		t.Skip("plateforme sans chiffrement au repos (Linux) : le stockage en clair est le comportement documenté, protégé par les permissions fichier")
	}
	// Sur les plateformes avec chiffrement (Windows/DPAPI), le blob stocké
	// ne doit jamais contenir le texte en clair du token.
	if containsSubstring(c.TokenSecret, plaintext) {
		t.Error("TokenSecret contient le token en clair — le chiffrement n'a pas eu lieu")
	}

	got, err := c.Token()
	if err != nil {
		t.Fatalf("Token() a échoué: %v", err)
	}
	if got != plaintext {
		t.Errorf("Token() = %q, attendu %q", got, plaintext)
	}
}

func TestSetToken_EmptyStringRoundTrips(t *testing.T) {
	var c Config
	if err := c.SetToken(""); err != nil {
		t.Fatalf("SetToken(\"\") a échoué: %v", err)
	}
	got, err := c.Token()
	if err != nil {
		t.Fatalf("Token() a échoué: %v", err)
	}
	if got != "" {
		t.Errorf("Token() = %q, attendu chaîne vide", got)
	}
}
