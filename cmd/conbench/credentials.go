package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
)

// credentialsPathFn resolves the credentials file location. It is a package var
// so tests can point it at a temp file or force failures, keeping them hermetic
// on every OS (os.UserConfigDir is not relocatable via XDG on macOS).
var credentialsPathFn = credentialsPath

// credentialsPath returns the per-user credentials file location under the OS
// config dir (~/Library/Application Support/conbench on macOS,
// ~/.config/conbench on Linux).
func credentialsPath() (string, error) {
	dir, err := os.UserConfigDir()
	if err != nil {
		return "", fmt.Errorf("locate config dir: %w", err)
	}
	return filepath.Join(dir, "conbench", "credentials.json"), nil
}

// loadCredentials reads the server->token map. A missing file is an empty map,
// not an error.
func loadCredentials(path string) (map[string]string, error) {
	data, err := os.ReadFile(path)
	if os.IsNotExist(err) {
		return map[string]string{}, nil
	}
	if err != nil {
		return nil, fmt.Errorf("read credentials: %w", err)
	}
	if len(data) == 0 {
		return map[string]string{}, nil // empty/truncated file behaves like none
	}
	creds := map[string]string{}
	if err := json.Unmarshal(data, &creds); err != nil {
		return nil, fmt.Errorf("parse credentials %s: %w", path, err)
	}
	return creds, nil
}

// saveToken upserts the token for a server URL, writing the file 0600.
func saveToken(path, server, token string) error {
	creds, err := loadCredentials(path)
	if err != nil {
		return err
	}
	creds[server] = token
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		return fmt.Errorf("create config dir: %w", err)
	}
	data, err := json.MarshalIndent(creds, "", "  ")
	if err != nil {
		return err
	}
	if err := os.WriteFile(path, data, 0o600); err != nil {
		return fmt.Errorf("write credentials: %w", err)
	}
	// WriteFile does not tighten an existing file's mode; enforce 0600 in case
	// the file pre-existed with broader permissions.
	if err := os.Chmod(path, 0o600); err != nil {
		return fmt.Errorf("set credentials permissions: %w", err)
	}
	return nil
}

// resolveToken applies the precedence flag > CONBENCH_TOKEN env > credentials
// file (keyed by server). An unset token is "" with no error.
func resolveToken(flagToken, server, path string) (string, error) {
	if flagToken != "" {
		return flagToken, nil
	}
	if env := os.Getenv("CONBENCH_TOKEN"); env != "" {
		return env, nil
	}
	creds, err := loadCredentials(path)
	if err != nil {
		return "", err
	}
	return creds[server], nil
}

// resolveTokenFromSources applies flag/env/file precedence without resolving
// the credentials file location unless file lookup is actually needed.
func resolveTokenFromSources(flagToken, server string) (string, error) {
	if flagToken != "" {
		return flagToken, nil
	}
	if env := os.Getenv("CONBENCH_TOKEN"); env != "" {
		return env, nil
	}
	path, err := credentialsPathFn()
	if err != nil {
		return "", err
	}
	return resolveToken("", server, path)
}
