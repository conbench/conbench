package main

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestCredentialsSaveLoadRoundTrip(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "credentials.json")

	require.NoError(t, saveToken(path, "https://a.example", "cb_tokenA"))
	require.NoError(t, saveToken(path, "https://b.example", "cb_tokenB"))

	info, err := os.Stat(path)
	require.NoError(t, err)
	assert.Equal(t, os.FileMode(0o600), info.Mode().Perm(), "credentials file is private")

	creds, err := loadCredentials(path)
	require.NoError(t, err)
	assert.Equal(t, "cb_tokenA", creds["https://a.example"])
	assert.Equal(t, "cb_tokenB", creds["https://b.example"])
}

func TestLoadCredentialsMissingFileIsEmpty(t *testing.T) {
	creds, err := loadCredentials(filepath.Join(t.TempDir(), "nope.json"))
	require.NoError(t, err)
	assert.Empty(t, creds)
}

func TestLoadCredentialsEmptyFileIsEmpty(t *testing.T) {
	path := filepath.Join(t.TempDir(), "credentials.json")
	require.NoError(t, os.WriteFile(path, nil, 0o600))
	creds, err := loadCredentials(path)
	require.NoError(t, err, "an empty/truncated file behaves like none")
	assert.Empty(t, creds)
}

func TestSaveTokenTightensExistingPermissions(t *testing.T) {
	path := filepath.Join(t.TempDir(), "credentials.json")
	require.NoError(t, os.WriteFile(path, []byte("{}"), 0o644))
	require.NoError(t, saveToken(path, "https://s.example", "cb_x"))
	info, err := os.Stat(path)
	require.NoError(t, err)
	assert.Equal(t, os.FileMode(0o600), info.Mode().Perm(),
		"saveToken tightens a pre-existing world-readable file")
}

func TestResolveTokenPrecedence(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "credentials.json")
	require.NoError(t, saveToken(path, "https://s.example", "from-file"))

	// flag wins over env and file
	t.Setenv("CONBENCH_TOKEN", "from-env")
	got, err := resolveToken("from-flag", "https://s.example", path)
	require.NoError(t, err)
	assert.Equal(t, "from-flag", got)

	// env wins over file
	got, err = resolveToken("", "https://s.example", path)
	require.NoError(t, err)
	assert.Equal(t, "from-env", got)

	// file is the fallback
	t.Setenv("CONBENCH_TOKEN", "")
	got, err = resolveToken("", "https://s.example", path)
	require.NoError(t, err)
	assert.Equal(t, "from-file", got)

	// nothing configured for this server -> empty, no error
	got, err = resolveToken("", "https://unknown.example", path)
	require.NoError(t, err)
	assert.Empty(t, got)
}

func TestResolveBearerExplicitSourcesDoNotNeedConfigDir(t *testing.T) {
	t.Setenv("HOME", "")
	t.Setenv("XDG_CONFIG_HOME", "")

	got, err := resolveBearer("from-flag", "https://s.example")
	require.NoError(t, err)
	assert.Equal(t, "Bearer from-flag", got)

	t.Setenv("CONBENCH_TOKEN", "from-env")
	got, err = resolveBearer("", "https://s.example")
	require.NoError(t, err)
	assert.Equal(t, "Bearer from-env", got)
}
