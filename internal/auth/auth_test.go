package auth_test

import (
	"context"
	"errors"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/conbench/conbench/internal/auth"
	"github.com/conbench/conbench/internal/db"
	"github.com/conbench/conbench/internal/dbtest"
	"github.com/conbench/conbench/internal/storage"
)

func TestAuthenticateDisabledAllowsEverything(t *testing.T) {
	a := auth.New("", true, nil, nil) // disabled, no token
	for _, h := range []string{"", "Bearer anything", "garbage"} {
		assert.NoError(t, a.Authenticate(context.Background(), h, ""), "disabled Authenticate(%q) want nil", h)
	}
}

func TestAuthenticateEnabledChecksBearerToken(t *testing.T) {
	a := auth.New("s3cret", false, nil, nil)
	require.NoError(t, a.Authenticate(context.Background(), "Bearer s3cret", ""), "correct token rejected")
	for _, h := range []string{"", "s3cret", "Bearer wrong", "Bearer ", "bearer s3cret"} {
		assert.ErrorIs(t, a.Authenticate(context.Background(), h, ""), auth.ErrUnauthorized, "Authenticate(%q) want ErrUnauthorized", h)
	}
}

// TestAuthenticateFailsClosedWithoutToken pins the spec stance: when auth is not
// disabled but no token is configured, every request is rejected.
func TestAuthenticateFailsClosedWithoutToken(t *testing.T) {
	a := auth.New("", false, nil, nil)
	assert.ErrorIs(t, a.Authenticate(context.Background(), "Bearer anything", ""), auth.ErrUnauthorized, "fail-closed Authenticate want ErrUnauthorized")
}

func TestAuthenticateSessionCookie(t *testing.T) {
	sessions := auth.NewSessionSigner("sek")
	a := auth.New("", false, nil, sessions)
	ctx := context.Background()

	valid := sessions.Sign("user-1", time.Now().UTC().Add(time.Hour))
	require.NoError(t, a.Authenticate(ctx, "", valid), "valid session authorizes")

	expired := sessions.Sign("user-1", time.Now().UTC().Add(-time.Hour))
	require.ErrorIs(t, a.Authenticate(ctx, "", expired), auth.ErrUnauthorized, "expired session rejected")

	require.ErrorIs(t, a.Authenticate(ctx, "", "garbage"), auth.ErrUnauthorized, "malformed session rejected")
	assert.ErrorIs(t, a.Authenticate(ctx, "", ""), auth.ErrUnauthorized, "no credential rejected")
}

func TestAuthenticateNilSessionSigner(t *testing.T) {
	a := auth.New("static", false, nil, nil)
	ctx := context.Background()
	// With no session signer, a cookie value can never authorize; the static
	// token still does.
	require.ErrorIs(t, a.Authenticate(ctx, "", "anything"), auth.ErrUnauthorized)
	require.NoError(t, a.Authenticate(ctx, "Bearer static", ""))
}

// mintToken creates a user and a token row, returning the plaintext and id.
func mintToken(t *testing.T, ctx context.Context, store *db.Store, pool *pgxpool.Pool) (string, string) {
	t.Helper()
	userID := dbtest.SeedUser(t, ctx, pool)
	tok, err := auth.GenerateToken()
	require.NoError(t, err)
	id, err := store.CreateAPIToken(ctx, storage.InsertAPITokenParams{
		UserID: userID, Name: "test", TokenHash: tok.Hash, TokenPrefix: tok.Prefix,
		CreatedAt: time.Now().UTC(),
	})
	require.NoError(t, err)
	return tok.Plaintext, id
}

func TestAuthenticateDBToken(t *testing.T) {
	pool, ctx := dbtest.NewPool(t)
	store := db.NewStore(pool)
	plaintext, _ := mintToken(t, ctx, store, pool)
	a := auth.New("static-token", false, store, nil)

	require.NoError(t, a.Authenticate(ctx, "Bearer "+plaintext, ""), "db token rejected")
	assert.NoError(t, a.Authenticate(ctx, "Bearer static-token", ""), "static token must keep working")
	assert.ErrorIs(t, a.Authenticate(ctx, "Bearer cb_notarealtoken", ""), auth.ErrUnauthorized)
}

// erroringTokenStore returns a generic (non-ErrNotFound) error from the hash
// lookup, simulating a database outage.
type erroringTokenStore struct{}

func (erroringTokenStore) GetAPITokenByHash(context.Context, string) (storage.APIToken, error) {
	return storage.APIToken{}, errors.New("connection refused")
}

func (erroringTokenStore) TouchAPITokenLastUsed(context.Context, string, time.Time) error {
	return nil
}

// TestResolvePrincipalFailsClosedOnStoreError pins that a database error during
// token lookup denies the request (fail closed) rather than authenticating.
func TestResolvePrincipalFailsClosedOnStoreError(t *testing.T) {
	a := auth.New("", false, erroringTokenStore{}, nil)
	_, err := a.ResolvePrincipal(context.Background(), "Bearer cb_anything", "")
	assert.ErrorIs(t, err, auth.ErrUnauthorized, "store error must fail closed, not authenticate")
}

func TestResolvePrincipalDBToken(t *testing.T) {
	pool, ctx := dbtest.NewPool(t)
	store := db.NewStore(pool)
	userID := dbtest.SeedUser(t, ctx, pool)
	tok, err := auth.GenerateToken()
	require.NoError(t, err)
	_, err = store.CreateAPIToken(ctx, storage.InsertAPITokenParams{
		UserID: userID, Name: "test", TokenHash: tok.Hash, TokenPrefix: tok.Prefix,
		CreatedAt: time.Now().UTC(),
	})
	require.NoError(t, err)
	a := auth.New("static-token", false, store, nil)

	p, err := a.ResolvePrincipal(ctx, "Bearer "+tok.Plaintext, "")
	require.NoError(t, err)
	assert.True(t, p.IsUser())
	assert.Equal(t, userID, p.UserID, "db token principal carries the seeded user id")
}

func TestAuthenticateRevokedDBToken(t *testing.T) {
	pool, ctx := dbtest.NewPool(t)
	store := db.NewStore(pool)
	plaintext, id := mintToken(t, ctx, store, pool)
	require.NoError(t, store.RevokeAPIToken(ctx, id, time.Now().UTC()))
	a := auth.New("", false, store, nil)

	assert.ErrorIs(t, a.Authenticate(ctx, "Bearer "+plaintext, ""), auth.ErrUnauthorized,
		"revoked token must be rejected")
}

// TestAuthenticateTouchesStaleLastUsed pins the throttle's update side: a
// token whose last_used_at is NULL gets stamped (asynchronously) on use.
func TestAuthenticateTouchesStaleLastUsed(t *testing.T) {
	pool, ctx := dbtest.NewPool(t)
	store := db.NewStore(pool)
	plaintext, _ := mintToken(t, ctx, store, pool)
	a := auth.New("", false, store, nil)

	require.NoError(t, a.Authenticate(ctx, "Bearer "+plaintext, ""))
	assert.Eventually(t, func() bool {
		row, err := store.GetAPITokenByHash(ctx, auth.HashToken(plaintext))
		return err == nil && row.LastUsedAt != nil
	}, 5*time.Second, 50*time.Millisecond, "last_used_at should be stamped fire-and-forget")
}
