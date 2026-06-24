package auth_test

import (
	"context"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/conbench/conbench/internal/auth"
)

func TestResolvePrincipalStaticTokenHasNoUser(t *testing.T) {
	a := auth.New("static", false, nil, nil)
	p, err := a.ResolvePrincipal(context.Background(), "Bearer static", "")
	require.NoError(t, err)
	assert.False(t, p.IsUser(), "static operator token is not user-attributed")
	assert.Empty(t, p.UserID)
}

func TestResolvePrincipalSession(t *testing.T) {
	sessions := auth.NewSessionSigner("sek")
	a := auth.New("", false, nil, sessions)
	val := sessions.Sign("user-9", time.Now().UTC().Add(time.Hour))

	p, err := a.ResolvePrincipal(context.Background(), "", val)
	require.NoError(t, err)
	assert.True(t, p.IsUser())
	assert.Equal(t, "user-9", p.UserID)
}

func TestResolvePrincipalUnauthenticated(t *testing.T) {
	a := auth.New("static", false, nil, auth.NewSessionSigner("sek"))
	_, err := a.ResolvePrincipal(context.Background(), "", "")
	assert.ErrorIs(t, err, auth.ErrUnauthorized)
}

func TestResolvePrincipalDisabledHasNoUser(t *testing.T) {
	a := auth.New("", true, nil, nil)
	p, err := a.ResolvePrincipal(context.Background(), "", "")
	require.NoError(t, err)
	assert.False(t, p.IsUser(), "auth-disabled has no attributable user")
}
