package stats

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

type fingerprintGolden struct {
	CaseID       string `json:"case_id"`
	ContextID    string `json:"context_id"`
	HardwareHash string `json:"hardware_hash"`
	RepoURL      string `json:"repo_url"`
	Fingerprint  string `json:"fingerprint"`
}

// TestHistoryFingerprintMatchesPythonGolden pins the Go port to checked-in
// references produced from the retired Python history-fingerprint behavior.
func TestHistoryFingerprintMatchesPythonGolden(t *testing.T) {
	raw, err := os.ReadFile(filepath.Join("testdata", "history_fingerprint.json"))
	require.NoError(t, err, "read golden")

	var cases []fingerprintGolden
	require.NoError(t, json.Unmarshal(raw, &cases), "parse golden")
	require.NotEmpty(t, cases, "golden file has no cases")

	for _, c := range cases {
		got := HistoryFingerprint(c.CaseID, c.ContextID, c.HardwareHash, c.RepoURL)
		assert.Equalf(t, c.Fingerprint, got, "HistoryFingerprint(%q, %q, %q, %q)",
			c.CaseID, c.ContextID, c.HardwareHash, c.RepoURL)
	}
}
