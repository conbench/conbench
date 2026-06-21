package prodclone

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestRenderCompatibilityReportIncludesRequiredSections(t *testing.T) {
	dir := t.TempDir()
	writeReportJSON(t, filepath.Join(dir, "preflight.json"), map[string]any{
		"target": map[string]any{
			"database":                      "conbench_prod",
			"user":                          "conbench_readonly",
			"host":                          "clone-db.example",
			"port":                          5432,
			"superuser":                     false,
			"default_transaction_read_only": true,
			"schema_tables":                 []string{"benchmark_result", "case", "context"},
			"writable_table_counts": map[string]int64{
				"public.benchmark_result": 100,
			},
		},
		"policy": map[string]any{
			"expected_database":       "conbench_prod",
			"expected_hosts":          []string{"clone-db.example", "192.0.2.10"},
			"expected_port":           5432,
			"development_role":        "conbench_writer",
			"expected_read_only_role": "conbench_readonly",
			"require_read_only_role":  true,
			"allow_dev_role":          false,
		},
		"valid":                 true,
		"acceptance_eligible":   true,
		"raw_benchmark_payload": "do-not-render",
	})
	writeReportJSON(t, filepath.Join(dir, "samples.json"), SampleManifest{
		GeneratedAt: time.Date(2026, 6, 15, 14, 0, 0, 0, time.UTC),
		Categories: map[string]SampleCategory{
			"long_history": {
				ResultID:           "result-long",
				HistoryFingerprint: "fp-long",
				PointCount:         120,
			},
			"recent_result": {
				ResultID:           "result-recent",
				HistoryFingerprint: "fp-recent",
				PointCount:         4,
			},
		},
		Compare: &CompareSample{
			BaselineResultID:   "baseline-result",
			ContenderResultID:  "contender-result",
			HistoryFingerprint: "fp-long",
		},
	})
	writeReportJSON(t, filepath.Join(dir, "api-probes.json"), CompatibilityProbeArtifact{
		Passed: true,
		Probes: []CompatibilityProbeResult{
			{Surface: "API", Name: "ListSeries", Operation: "GET /api/series", Passed: true, StatusCode: 200, DurationMS: 12.5},
			{Surface: "API", Name: "GetBenchmarkResult", Operation: "GET /api/benchmark-results/{id}", Passed: true, StatusCode: 200, DurationMS: 8},
		},
	})
	writeReportJSON(t, filepath.Join(dir, "cli-probes.json"), CompatibilityProbeArtifact{
		Passed: false,
		Probes: []CompatibilityProbeResult{
			{Surface: "CLI", Name: "conbench series list", Operation: "series list", Passed: false, Error: "invalid JSON"},
		},
	})
	writeReportJSON(t, filepath.Join(dir, "sdk-smoke.json"), CompatibilityProbeArtifact{
		Passed: true,
		Probes: []CompatibilityProbeResult{
			{Surface: "SDK", Name: "pytest sdk smoke", Operation: "test_smoke.py", Passed: true},
		},
	})
	writeReportJSON(t, filepath.Join(dir, "log-scan.json"), LogScanArtifact{
		Passed:   true,
		Findings: []LogFinding{},
	})
	writeReportFile(t, filepath.Join(dir, "timings", "http.jsonl"),
		`{"surface":"API","name":"ListSeries","operation":"GET /api/series","method":"GET","path":"/api/series","status_code":200,"duration_ms":12.5,"passed":true}`+"\n"+
			`{"surface":"API","name":"GetBenchmarkResult","operation":"GET /api/benchmark-results/{id}","method":"GET","path":"/api/benchmark-results/result-recent","status_code":200,"duration_ms":8,"passed":true}`+"\n")

	report, err := RenderCompatibilityReport(dir)

	require.NoError(t, err)
	text := string(report)
	assert.Contains(t, text, "# Conbench Prod Clone Compatibility Report")
	assert.Contains(t, text, "## Environment and Clone")
	assert.Contains(t, text, "conbench_prod")
	assert.Contains(t, text, "clone-db.example:5432")
	assert.Contains(t, text, "## Read-only Role and Connection Safety")
	assert.Contains(t, text, "conbench_readonly")
	assert.Contains(t, text, "default_transaction_read_only: true")
	assert.Contains(t, text, "## Sample Manifest")
	assert.Contains(t, text, "long_history")
	assert.Contains(t, text, "result-long")
	assert.Contains(t, text, "fp-long")
	assert.Contains(t, text, "## Compatibility Results")
	assert.Contains(t, text, "| API | ListSeries | PASS | 200 |")
	assert.Contains(t, text, "| CLI | conbench series list | FAIL |")
	assert.Contains(t, text, "invalid JSON")
	assert.Contains(t, text, "| SDK | pytest sdk smoke | PASS |")
	assert.Contains(t, text, "## Blocked-write Log Scan")
	assert.Contains(t, text, "0 blocked-write findings")
	assert.Contains(t, text, "## Latency")
	assert.Contains(t, text, "| API | ListSeries | GET | /api/series | 200 | 12.50 |")
	assert.NotContains(t, text, "do-not-render")
}

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

func TestRenderCompatibilityReportListsProbeFailuresAsRisks(t *testing.T) {
	dir := t.TempDir()
	writeReportJSON(t, filepath.Join(dir, "api-probes.json"), CompatibilityProbeArtifact{
		Passed: false,
		Probes: []CompatibilityProbeResult{
			{Surface: "API", Name: "ListSeries", Operation: "GET /api/series", Passed: false, Error: "boom"},
		},
	})

	report, err := RenderCompatibilityReport(dir)

	require.NoError(t, err)
	text := string(report)
	assert.Contains(t, text, "Investigate failed API, CLI, or SDK compatibility probes")
	assert.NotContains(t, text, "No compatibility-report risk entries")
}

func TestRenderCompatibilityReportLinksProfilePlans(t *testing.T) {
	dir := t.TempDir()
	writeReportFile(t, filepath.Join(dir, "timings", "sql.jsonl"),
		`{"surface":"SQL profile","name":"SeriesBrowseDefault","operation":"series browse default","duration_ms":50,"row_count":5,"explain_file":"series-browse-default.json","passed":true}`+"\n"+
			`{"surface":"SQL profile","name":"HistoryLong","operation":"history long","duration_ms":75,"row_count":120,"explain_file":"history-long.json","passed":true}`+"\n")
	writeReportJSON(t, filepath.Join(dir, "relation-sizes.json"), []RelationSize{
		{Table: "public.benchmark_result", TotalBytes: 1000, TableBytes: 600, IndexBytes: 400},
	})

	report, err := RenderCompatibilityReport(dir)

	require.NoError(t, err)
	text := string(report)
	assert.Contains(t, text, "| HistoryLong | 75.00 | 120 | PASS | [`history-long.json`](explain/history-long.json) |")
	assert.Contains(t, text, "### Relation Sizes")
	assert.Contains(t, text, "public.benchmark_result")
	assert.NotContains(t, text, "SQL plan profiling has not been collected")
}

func TestRenderCompatibilityReportMissingMandatoryArtifactsAreRisks(t *testing.T) {
	report, err := RenderCompatibilityReport(t.TempDir())

	require.NoError(t, err)
	text := string(report)
	assert.Contains(t, text, "Collect mandatory compatibility artifacts")
	assert.Contains(t, text, "preflight.json")
	assert.Contains(t, text, "samples.json")
	assert.Contains(t, text, "api-probes.json")
	assert.NotContains(t, text, "No compatibility-report risk entries")
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

func TestRenderCompatibilityReportSampleWarningsAndMissingCompareAreRisks(t *testing.T) {
	dir := t.TempDir()
	writeReportJSON(t, filepath.Join(dir, "samples.json"), SampleManifest{
		Categories: map[string]SampleCategory{
			"recent_result": {ResultID: "result-recent", HistoryFingerprint: "fp-recent", PointCount: 1},
		},
		Warnings: []string{"compare sample was not found for long_history"},
	})

	report, err := RenderCompatibilityReport(dir)

	require.NoError(t, err)
	text := string(report)
	assert.Contains(t, text, "Review sample manifest warnings before Phase 5")
	assert.Contains(t, text, "Restore or triage compare coverage before Phase 5")
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
