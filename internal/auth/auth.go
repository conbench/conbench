// Package auth implements write-endpoint authentication: the static operator
// token from CONBENCH_API_TOKEN and user-attributed database tokens
// (api_token rows, minted in Leaf 3c). It fails closed: every request must
// present an accepted token unless auth is explicitly disabled for local
// development (CONBENCH_AUTH_DISABLED=true).
package auth

import (
	"context"
	"crypto/subtle"
	"errors"
	"log/slog"
	"strings"
	"time"

	"github.com/conbench/conbench/internal/storage"
)

// ErrUnauthorized is returned when a request is not authenticated.
var ErrUnauthorized = errors.New("unauthorized")

// lastUsedStaleness is the throttle on last_used_at writes: the column is
// best-effort observability, not an audit log, so it is only updated when
// stale by more than this (never on every request).
const lastUsedStaleness = 5 * time.Minute

// touchTimeout bounds the fire-and-forget last_used_at write, which runs on a
// background context because the request that triggered it does not wait.
const touchTimeout = 5 * time.Second

// TokenStore is the slice of the data layer the authenticator needs for
// database tokens; *db.Store satisfies it. A nil TokenStore disables db-token
// auth (static token only).
type TokenStore interface {
	GetAPITokenByHash(ctx context.Context, tokenHash string) (storage.APIToken, error)
	TouchAPITokenLastUsed(ctx context.Context, id string, lastUsed time.Time) error
}

// Authenticator checks bearer tokens against the configured static value and
// the api_token table, and session cookies against the session signer.
type Authenticator struct {
	token    string
	disabled bool
	tokens   TokenStore
	sessions *SessionSigner
}

// New builds an Authenticator. A nil tokens disables db-token auth; a nil
// sessions disables session-cookie auth. When disabled is false with no static
// token, nil tokens, and nil sessions, every request is rejected (fail closed).
func New(token string, disabled bool, tokens TokenStore, sessions *SessionSigner) *Authenticator {
	return &Authenticator{token: token, disabled: disabled, tokens: tokens, sessions: sessions}
}

// Disabled reports whether authentication is turned off.
func (a *Authenticator) Disabled() bool { return a.disabled }

// ResolvePrincipal authorizes a request and returns its Principal. Order:
// static token, db token, session cookie. The static operator token and
// disabled mode resolve to an empty-UserID Principal (authenticated but not
// user-attributed); a db token and a session carry their user id. It returns
// ErrUnauthorized when nothing authenticates. Token and session material are
// never logged.
func (a *Authenticator) ResolvePrincipal(ctx context.Context, authHeader, sessionCookie string) (Principal, error) {
	if a.disabled {
		return Principal{}, nil
	}
	if uid, ok := a.resolveBearer(ctx, authHeader); ok {
		return Principal{UserID: uid}, nil
	}
	if uid, ok := a.resolveSession(sessionCookie); ok {
		return Principal{UserID: uid}, nil
	}
	return Principal{}, ErrUnauthorized
}

// Authenticate reports whether a request is authorized, discarding identity.
func (a *Authenticator) Authenticate(ctx context.Context, authHeader, sessionCookie string) error {
	_, err := a.ResolvePrincipal(ctx, authHeader, sessionCookie)
	return err
}

// resolveBearer checks the Authorization header against the static token then
// the api_token table. The static token authenticates with no user. Returns
// ("", false) on any miss.
func (a *Authenticator) resolveBearer(ctx context.Context, authHeader string) (string, bool) {
	const prefix = "Bearer "
	if !strings.HasPrefix(authHeader, prefix) {
		return "", false
	}
	presented := authHeader[len(prefix):]
	if presented == "" {
		return "", false
	}
	if a.token != "" &&
		subtle.ConstantTimeCompare([]byte(presented), []byte(a.token)) == 1 {
		return "", true
	}
	if a.tokens == nil {
		return "", false
	}
	return a.resolveDBToken(ctx, presented)
}

// resolveSession accepts a valid, unexpired session cookie and returns its
// user id. A nil signer or empty/invalid value is a miss.
func (a *Authenticator) resolveSession(sessionCookie string) (string, bool) {
	if a.sessions == nil || sessionCookie == "" {
		return "", false
	}
	uid, err := a.sessions.Verify(sessionCookie, time.Now().UTC())
	if err != nil {
		return "", false
	}
	return uid, true
}

// resolveDBToken verifies a presented token against the api_token table:
// lookup by hash (the unique index), constant-time hash comparison as
// defense-in-depth, revocation check, then a throttled fire-and-forget
// last_used_at stamp. On success it returns the token's user id.
func (a *Authenticator) resolveDBToken(ctx context.Context, presented string) (string, bool) {
	hash := HashToken(presented)
	row, err := a.tokens.GetAPITokenByHash(ctx, hash)
	if errors.Is(err, storage.ErrNotFound) {
		return "", false
	}
	if err != nil {
		slog.Warn("auth: token lookup failed; failing closed", "error", err)
		return "", false
	}
	if subtle.ConstantTimeCompare([]byte(hash), []byte(row.TokenHash)) != 1 {
		return "", false
	}
	if row.RevokedAt != nil {
		return "", false
	}
	if shouldTouchLastUsed(row.LastUsedAt, time.Now().UTC()) {
		go a.touchLastUsed(row.ID)
	}
	return row.UserID, true
}

// shouldTouchLastUsed decides whether a successful use warrants a last_used_at
// write: only when never recorded or stale by strictly more than the
// staleness window, so the hot path almost never writes.
func shouldTouchLastUsed(lastUsed *time.Time, now time.Time) bool {
	return lastUsed == nil || now.Sub(*lastUsed) > lastUsedStaleness
}

// touchLastUsed stamps last_used_at on a background context: the triggering
// request does not wait, and failures are logged, never propagated.
func (a *Authenticator) touchLastUsed(id string) {
	ctx, cancel := context.WithTimeout(context.Background(), touchTimeout)
	defer cancel()
	if err := a.tokens.TouchAPITokenLastUsed(ctx, id, time.Now().UTC()); err != nil {
		slog.Warn("auth: last_used_at update failed", "token_id", id, "error", err)
	}
}
