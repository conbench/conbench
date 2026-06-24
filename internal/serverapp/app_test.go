package serverapp

import (
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestValidateSessionSecret(t *testing.T) {
	t.Run("empty is allowed", func(t *testing.T) {
		require.NoError(t, validateSessionSecret(""))
	})
	t.Run("too short is rejected", func(t *testing.T) {
		err := validateSessionSecret(strings.Repeat("a", minSessionSecretLen-1))
		require.Error(t, err)
		assert.Contains(t, err.Error(), "CONBENCH_SESSION_SECRET")
	})
	t.Run("exactly the floor is accepted", func(t *testing.T) {
		require.NoError(t, validateSessionSecret(strings.Repeat("a", minSessionSecretLen)))
	})
}

func TestValidateOIDCConfigRequiresCompleteSet(t *testing.T) {
	secret := strings.Repeat("s", minSessionSecretLen)
	require.NoError(t, validateOIDCConfig("", "", "", "", ""))
	require.NoError(t, validateOIDCConfig("https://issuer.example", "client", "secret", "https://conbench.example", secret))

	err := validateOIDCConfig("", "client", "", "", "")
	require.Error(t, err)
	assert.Contains(t, err.Error(), "CONBENCH_OIDC_ISSUER_URL")
}

func TestLoadConfigRequiresDatabaseURL(t *testing.T) {
	isolateLoadConfigEnv(t)
	t.Setenv("CONBENCH_DB_URL", "")
	t.Setenv("DATABASE_URL", "")
	_, err := loadConfig()
	require.Error(t, err)
	assert.Contains(t, err.Error(), "CONBENCH_DB_URL")
}

func TestLoadConfigFallsBackToDatabaseURL(t *testing.T) {
	isolateLoadConfigEnv(t)
	t.Setenv("CONBENCH_DB_URL", "")
	t.Setenv("DATABASE_URL", "postgres://fallback/db")
	cfg, err := loadConfig()
	require.NoError(t, err)
	assert.Equal(t, "postgres://fallback/db", cfg.databaseURL)
}

func isolateLoadConfigEnv(t *testing.T) {
	t.Helper()
	for _, key := range []string{
		"CONBENCH_BASE_URL",
		"CONBENCH_SESSION_SECRET",
		"CONBENCH_OIDC_ISSUER_URL",
		"CONBENCH_OIDC_CLIENT_ID",
		"CONBENCH_OIDC_CLIENT_SECRET",
		"CONBENCH_WEB_BASE_URL",
		"CONBENCH_STATIC_ADMIN_TOKEN",
		"GITHUB_API_TOKEN",
	} {
		t.Setenv(key, "")
	}
}

func TestSecureFromBaseURL(t *testing.T) {
	assert.False(t, secureFromBaseURL("http://localhost:8080"))
	assert.False(t, secureFromBaseURL("http://127.0.0.1:8080"))
	assert.False(t, secureFromBaseURL("http://[::1]:8080"))
	assert.True(t, secureFromBaseURL("https://conbench.example"))
	assert.True(t, secureFromBaseURL("%"))
}
