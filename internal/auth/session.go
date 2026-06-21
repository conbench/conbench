package auth

import (
	"errors"
	"strconv"
	"strings"
	"time"
)

// SessionCookieName is the name of the stateless session cookie.
const SessionCookieName = "conbench_session"

// SessionMaxAge is how long a freshly minted session is valid.
const SessionMaxAge = 30 * 24 * time.Hour

// ErrInvalidSession is returned when a session value is malformed or expired.
var ErrInvalidSession = errors.New("invalid session")

// SessionSigner mints and verifies stateless session cookie values carrying a
// user id and an expiry (Unix seconds), HMAC-signed. No server-side state.
type SessionSigner struct {
	signer *Signer
}

// NewSessionSigner builds a SessionSigner over the given secret.
func NewSessionSigner(secret string) *SessionSigner {
	return &SessionSigner{signer: NewSigner(secret)}
}

// Sign returns a signed session value for userID valid until expires.
func (s *SessionSigner) Sign(userID string, expires time.Time) string {
	return s.signer.Sign([]byte(userID + "|" + strconv.FormatInt(expires.Unix(), 10)))
}

// Verify checks the signature and expiry (against now) and returns the user id.
func (s *SessionSigner) Verify(value string, now time.Time) (string, error) {
	payload, err := s.signer.Verify(value)
	if err != nil {
		return "", err
	}
	userID, expStr, ok := strings.Cut(string(payload), "|")
	if !ok || userID == "" {
		return "", ErrInvalidSession
	}
	exp, err := strconv.ParseInt(expStr, 10, 64)
	if err != nil {
		return "", ErrInvalidSession
	}
	if now.After(time.Unix(exp, 0)) {
		return "", ErrInvalidSession
	}
	return userID, nil
}
