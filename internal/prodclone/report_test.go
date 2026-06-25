package prodclone

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestRenderCompatibilityReportShowsBlockedWriteFindings(t *testing.T) {
	dir := t.TempDir()
	writeReportJSON(t, filepath.Join(dir, "log-scan.json"), LogScanArtifact{
		Passed: false,
		Findings: []LogFinding{
			{LineNumber: 7, Pattern: "read-only transaction", Line: "ERROR secret-token cannot execute INSERT in a read-only transaction"},
		},
	})

	report, err := RenderCompatibilityReport(dir)

	require.NoError(t, err)
	text := string(report)
	assert.Contains(t, text, "1 blocked-write finding")
	assert.Contains(t, text, "line 7")
	assert.Contains(t, text, "read-only transaction")
	assert.Contains(t, text, "blocked-write marker detected: read-only transaction")
	assert.NotContains(t, text, "secret-token")
	assert.NotContains(t, text, "cannot execute INSERT")
}

func TestRenderCompatibilityReportSanitizesProbeErrors(t *testing.T) {
	dir := t.TempDir()
	writeReportJSON(t, filepath.Join(dir, "api-probes.json"), CompatibilityProbeArtifact{
		Passed: false,
		Probes: []CompatibilityProbeResult{
			{
				Surface:   "API",
				Name:      "ListSeries",
				Operation: "GET /api/series",
				Passed:    false,
				Error:     `authorization="Bearer secret-token" password=supersecret raw payload`,
			},
		},
	})

	report, err := RenderCompatibilityReport(dir)

	require.NoError(t, err)
	text := string(report)
	assert.Contains(t, text, "<redacted>")
	assert.Contains(t, text, "raw payload")
	assert.NotContains(t, text, "secret-token")
	assert.NotContains(t, text, "supersecret")
}

func TestMissingMandatoryReportArtifacts(t *testing.T) {
	dir := t.TempDir()
	writeReportJSON(t, filepath.Join(dir, "preflight.json"), map[string]any{"valid": true})
	writeReportJSON(t, filepath.Join(dir, "samples.json"), SampleManifest{Compare: &CompareSample{}})

	missing, err := MissingMandatoryReportArtifacts(dir)

	require.NoError(t, err)
	assert.Contains(t, missing, "api-probes.json")
	assert.Contains(t, missing, "cli-probes.json")
	assert.Contains(t, missing, "sdk-smoke.json")
	assert.Contains(t, missing, "counts-before.json")
	assert.Contains(t, missing, "counts-after.json")
	assert.NotContains(t, missing, "preflight.json")
	assert.NotContains(t, missing, "samples.json")
}

func TestReportValidationIssuesCanRequireProfileArtifacts(t *testing.T) {
	issues, err := ReportValidationIssuesWithOptions(t.TempDir(), ReportValidationOptions{RequireProfile: true})

	require.NoError(t, err)
	joined := strings.Join(issues, "\n")
	assert.Contains(t, joined, "SQL profile timing artifacts")
	assert.Contains(t, joined, "SQL EXPLAIN plan artifacts")
	assert.Contains(t, joined, "relation size artifacts")
}

func TestReportValidationIssuesRejectSemanticallyEmptyArtifacts(t *testing.T) {
	dir := t.TempDir()
	writeReportJSON(t, filepath.Join(dir, "preflight.json"), map[string]any{
		"valid":               true,
		"acceptance_eligible": false,
	})
	writeReportJSON(t, filepath.Join(dir, "samples.json"), SampleManifest{})
	writeReportJSON(t, filepath.Join(dir, "api-probes.json"), CompatibilityProbeArtifact{
		Passed: true,
		Probes: []CompatibilityProbeResult{},
	})
	writeReportJSON(t, filepath.Join(dir, "cli-probes.json"), CompatibilityProbeArtifact{
		Passed: true,
		Probes: []CompatibilityProbeResult{},
	})
	writeReportJSON(t, filepath.Join(dir, "sdk-smoke.json"), CompatibilityProbeArtifact{
		Passed: true,
		Probes: []CompatibilityProbeResult{},
	})
	writeReportJSON(t, filepath.Join(dir, "log-scan.json"), LogScanArtifact{
		Passed: false,
	})
	writeReportJSON(t, filepath.Join(dir, "count-delta.json"), CountComparison{Changed: false})
	writeReportJSON(t, filepath.Join(dir, "counts-before.json"), CountSnapshot{})
	writeReportJSON(t, filepath.Join(dir, "counts-after.json"), CountSnapshot{})
	writeReportFile(t, filepath.Join(dir, "timings", "http.jsonl"),
		`{"surface":"API","name":"ListSeries","operation":"GET /api/series","method":"GET","path":"/api/series","status_code":200,"duration_ms":1,"passed":true}`+"\n")

	issues, err := ReportValidationIssues(dir)

	require.NoError(t, err)
	joined := strings.Join(issues, "\n")
	assert.Contains(t, joined, "dedicated read-only role")
	assert.Contains(t, joined, "non-empty sample manifest")
	assert.Contains(t, joined, "non-empty API probe evidence")
	assert.Contains(t, joined, "missing ListSeries")
	assert.Contains(t, joined, "non-empty CLI probe evidence")
	assert.Contains(t, joined, "non-empty SDK probe evidence")
	assert.Contains(t, joined, "blocked write attempts")
	assert.Contains(t, joined, "count-delta evidence")
	assert.Contains(t, joined, "before-count evidence")
	assert.Contains(t, joined, "after-count evidence")
}

func TestReportValidationIssuesRequiresCIReportProbeWhenSampleExists(t *testing.T) {
	dir := t.TempDir()
	writeReportJSON(t, filepath.Join(dir, "samples.json"), SampleManifest{
		Categories: map[string]SampleCategory{
			"recent_result": {ResultID: "result-recent", HistoryFingerprint: "fp-recent", PointCount: 1},
		},
		CIReport: &CIReportSample{
			Repository:         "https://github.com/conbench/prod-sample",
			CommitSHA:          "sha-recent",
			RunIDs:             []string{"sample-run"},
			ResultID:           "result-recent",
			HistoryFingerprint: "fp-recent",
		},
	})
	writeReportJSON(t, filepath.Join(dir, "api-probes.json"), CompatibilityProbeArtifact{
		Passed: true,
		Probes: []CompatibilityProbeResult{
			{Surface: "API", Name: "ListSeries", Operation: "GET /api/series", Passed: true, StatusCode: 200},
			{Surface: "API", Name: "ListBenchmarkResults", Operation: "GET /api/benchmark-results", Passed: true, StatusCode: 200},
			{Surface: "API", Name: "GetBenchmarkResult", Operation: "GET /api/benchmark-results/{id}", Passed: true, StatusCode: 200},
			{Surface: "API", Name: "GetHistoryForResult", Operation: "GET /api/history/{benchmark_result_id}", Passed: true, StatusCode: 200},
			{Surface: "API", Name: "GetHistory", Operation: "GET /api/history?fingerprint=...", Passed: true, StatusCode: 200},
		},
	})

	issues, err := ReportValidationIssues(dir)

	require.NoError(t, err)
	assert.Contains(t, strings.Join(issues, "\n"), "missing CIReportByCommitRun")
}

func writeReportJSON(t *testing.T, path string, value any) {
	t.Helper()
	data, err := json.MarshalIndent(value, "", "  ")
	require.NoError(t, err)
	writeReportFile(t, path, string(data))
}

func writeReportFile(t *testing.T, path string, data string) {
	t.Helper()
	require.NoError(t, os.MkdirAll(filepath.Dir(path), 0o755))
	require.NoError(t, os.WriteFile(path, []byte(data), 0o600))
}
