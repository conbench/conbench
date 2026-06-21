package prodclone

import (
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestScanServerLogFlagsBlockedWrites(t *testing.T) {
	log := strings.NewReader("auth: last_used_at update failed: cannot execute UPDATE in a read-only transaction\n")

	findings, err := ScanServerLog(log)
	require.NoError(t, err)
	require.Len(t, findings, 1)
	assert.Equal(t, "cannot execute", findings[0].Pattern)
	assert.Equal(t, "blocked-write marker detected: cannot execute", findings[0].Line)
}

func TestScanServerLogDoesNotRetainRawPayload(t *testing.T) {
	log := strings.NewReader(`failed payload {"authorization":"Bearer super-secret-token"} cannot execute UPDATE in a read-only transaction` + "\n")

	findings, err := ScanServerLog(log)
	require.NoError(t, err)
	require.Len(t, findings, 1)
	assert.Equal(t, "blocked-write marker detected: cannot execute", findings[0].Line)
	assert.NotContains(t, findings[0].Line, "super-secret-token")
	assert.NotContains(t, findings[0].Line, "authorization")
}

func TestScanServerLogIgnoresNormalLines(t *testing.T) {
	log := strings.NewReader("listening on :18080\nGET /api/ping 200\n")

	findings, err := ScanServerLog(log)
	require.NoError(t, err)
	assert.Empty(t, findings)
}

func TestScanServerLogMatchesPermissionAndCannotExecuteCaseInsensitively(t *testing.T) {
	log := strings.NewReader("update failed: PERMISSION DENIED for table api_token\ninsert failed: Cannot Execute INSERT in a read-only transaction\n")

	findings, err := ScanServerLog(log)
	require.NoError(t, err)
	require.Len(t, findings, 2)
	assert.Equal(t, "permission denied", findings[0].Pattern)
	assert.Equal(t, "cannot execute", findings[1].Pattern)
}

func TestScanServerLogReturnsMultipleFindings(t *testing.T) {
	log := strings.NewReader("first: read-only transaction\nnormal line\nsecond: permission denied\n")

	findings, err := ScanServerLog(log)
	require.NoError(t, err)
	require.Len(t, findings, 2)
	assert.Equal(t, 1, findings[0].LineNumber)
	assert.Equal(t, 3, findings[1].LineNumber)
}

func TestScanServerLogBoundsRetainedLineText(t *testing.T) {
	log := strings.NewReader("cannot execute " + strings.Repeat("x", 10_000) + "\n")

	findings, err := ScanServerLog(log)
	require.NoError(t, err)
	require.Len(t, findings, 1)
	assert.Contains(t, findings[0].Line, "cannot execute")
	assert.LessOrEqual(t, len(findings[0].Line), 4096)
}

func TestScanServerLogContinuesAfterVeryLongNonMatchingLine(t *testing.T) {
	log := strings.NewReader(strings.Repeat("x", 2*1024*1024) + "\nlater: read-only transaction\n")

	findings, err := ScanServerLog(log)
	require.NoError(t, err)
	require.Len(t, findings, 1)
	assert.Equal(t, 2, findings[0].LineNumber)
	assert.Equal(t, "blocked-write marker detected: read-only transaction", findings[0].Line)
}

func TestScanServerLogMatchesPatternAfterRetainedPrefix(t *testing.T) {
	log := strings.NewReader(strings.Repeat("x", 5000) + " read-only transaction\n")

	findings, err := ScanServerLog(log)
	require.NoError(t, err)
	require.Len(t, findings, 1)
	assert.Equal(t, "read-only transaction", findings[0].Pattern)
	assert.LessOrEqual(t, len(findings[0].Line), 4096)
}
