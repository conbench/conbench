package auth

import (
	"crypto/rand"
	"encoding/base64"

	"golang.org/x/oauth2"
)

// RandomToken returns a URL-safe, 256-bit random string for use as an OIDC
// state or nonce.
func RandomToken() string {
	var b [32]byte
	_, _ = rand.Read(b[:])
	return base64.RawURLEncoding.EncodeToString(b[:])
}

// GeneratePKCEVerifier returns a fresh PKCE code verifier.
func GeneratePKCEVerifier() string {
	return oauth2.GenerateVerifier()
}
