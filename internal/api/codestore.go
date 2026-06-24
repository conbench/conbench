package api

import (
	"context"
	"errors"
	"fmt"
	"sync"
	"time"

	"github.com/conbench/conbench/internal/auth"
)

// codeTTL bounds an unredeemed CLI login code. It is deliberately short: the
// CLI redeems it over its own connection within seconds of the loopback
// redirect.
const codeTTL = 60 * time.Second

type codeEntry struct {
	userID  string
	expires time.Time
}

// CLICodeStore issues and consumes the short-lived one-time codes used by the
// CLI loopback login exchange.
type CLICodeStore interface {
	Issue(ctx context.Context, userID string) (string, error)
	Redeem(ctx context.Context, code string) (string, bool, error)
}

// CodeStore is an in-process map of one-time CLI login codes to user ids.
// Codes are single-use (deleted on redeem) and short-lived. Production uses
// DBCodeStore; this implementation is for tests and schema/spec-only wiring.
type CodeStore struct {
	mu      sync.Mutex
	entries map[string]codeEntry
}

func newCodeStore() *CodeStore {
	return &CodeStore{entries: make(map[string]codeEntry)}
}

// NewCodeStore builds an empty code store.
func NewCodeStore() *CodeStore { return newCodeStore() }

// Issue mints a fresh single-use code for the user, valid for codeTTL.
func (c *CodeStore) Issue(_ context.Context, userID string) (string, error) {
	return c.issueAt(userID, time.Now().UTC()), nil
}

func (c *CodeStore) issueAt(userID string, now time.Time) string {
	code := auth.RandomToken()
	c.mu.Lock()
	c.sweepLocked(now)
	c.entries[code] = codeEntry{userID: userID, expires: now.Add(codeTTL)}
	c.mu.Unlock()
	return code
}

// sweepLocked deletes expired entries. The caller must hold c.mu. Sweeping on
// every issue bounds the map to the codes issued within one codeTTL window, so
// abandoned (never-redeemed) logins cannot leak memory indefinitely.
func (c *CodeStore) sweepLocked(now time.Time) {
	for code, e := range c.entries {
		if now.After(e.expires) {
			delete(c.entries, code)
		}
	}
}

// Redeem consumes a code and returns its user id, or ("", false) when the code
// is unknown, expired, or already used.
func (c *CodeStore) Redeem(_ context.Context, code string) (string, bool, error) {
	userID, ok := c.redeemAt(code, time.Now().UTC())
	return userID, ok, nil
}

func (c *CodeStore) redeemAt(code string, now time.Time) (string, bool) {
	c.mu.Lock()
	defer c.mu.Unlock()
	e, ok := c.entries[code]
	if !ok {
		return "", false
	}
	delete(c.entries, code) // single use, even if expired
	if now.After(e.expires) {
		return "", false
	}
	return e.userID, true
}

// SharedCodeStore is the DB surface DBCodeStore needs. *db.Store satisfies it.
type SharedCodeStore interface {
	DeleteExpiredCLILoginCodes(ctx context.Context, now time.Time) error
	InsertCLILoginCode(ctx context.Context, codeHash, userID string, createdAt, expiresAt time.Time) error
	RedeemCLILoginCode(ctx context.Context, codeHash string, now time.Time) (string, bool, error)
}

// DBCodeStore stores one-time CLI login codes in Postgres so cli-start and
// cli-exchange can land on different server replicas.
type DBCodeStore struct {
	store SharedCodeStore
}

// NewDBCodeStore builds a shared code store backed by the app database.
func NewDBCodeStore(store SharedCodeStore) *DBCodeStore { return &DBCodeStore{store: store} }

// Issue mints a fresh plaintext code, stores only its hash, and sweeps expired
// codes from prior abandoned login attempts.
func (s *DBCodeStore) Issue(ctx context.Context, userID string) (string, error) {
	if s == nil || s.store == nil {
		return "", errors.New("CLI code store is not configured")
	}
	now := time.Now().UTC()
	if err := s.store.DeleteExpiredCLILoginCodes(ctx, now); err != nil {
		return "", fmt.Errorf("sweep expired CLI login codes: %w", err)
	}
	code := auth.RandomToken()
	if err := s.store.InsertCLILoginCode(ctx, auth.HashToken(code), userID, now, now.Add(codeTTL)); err != nil {
		return "", fmt.Errorf("store CLI login code: %w", err)
	}
	return code, nil
}

// Redeem consumes a code and returns its user id, or ("", false, nil) when the
// code is unknown, expired, or already redeemed.
func (s *DBCodeStore) Redeem(ctx context.Context, code string) (string, bool, error) {
	if s == nil || s.store == nil {
		return "", false, errors.New("CLI code store is not configured")
	}
	userID, ok, err := s.store.RedeemCLILoginCode(ctx, auth.HashToken(code), time.Now().UTC())
	if err != nil {
		return "", false, fmt.Errorf("redeem CLI login code: %w", err)
	}
	return userID, ok, nil
}
