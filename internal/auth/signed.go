package auth

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"errors"
	"strings"
)

// ErrBadSignature is returned when a signed blob fails HMAC verification or is
// malformed.
var ErrBadSignature = errors.New("bad signature")

// Signer signs and verifies short, tamper-evident blobs with HMAC-SHA256. It
// carries no expiry of its own; callers embed any expiry in the payload. The
// encoding is base64url(payload) + "." + base64url(HMAC(base64url(payload))).
type Signer struct {
	secret []byte
}

// NewSigner builds a Signer over the given secret key.
func NewSigner(secret string) *Signer {
	return &Signer{secret: []byte(secret)}
}

// Sign returns the signed token for payload.
func (s *Signer) Sign(payload []byte) string {
	body := base64.RawURLEncoding.EncodeToString(payload)
	return body + "." + base64.RawURLEncoding.EncodeToString(s.mac(body))
}

// Verify checks the signature and returns the original payload, or
// ErrBadSignature.
func (s *Signer) Verify(token string) ([]byte, error) {
	body, sig, ok := strings.Cut(token, ".")
	if !ok {
		return nil, ErrBadSignature
	}
	want := base64.RawURLEncoding.EncodeToString(s.mac(body))
	if !hmac.Equal([]byte(sig), []byte(want)) {
		return nil, ErrBadSignature
	}
	payload, err := base64.RawURLEncoding.DecodeString(body)
	if err != nil {
		return nil, ErrBadSignature
	}
	return payload, nil
}

func (s *Signer) mac(body string) []byte {
	h := hmac.New(sha256.New, s.secret)
	h.Write([]byte(body))
	return h.Sum(nil)
}
