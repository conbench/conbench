package prodclone

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestSafeDBURLCommandRemovesPasswordFromStdout(t *testing.T) {
	t.Setenv("CONBENCH_PROD_CLONE_DB_URL", "postgresql://conbench_readonly:supersecret@clone-db.example:5432/conbench_prod")
	t.Setenv("CONBENCH_PROD_CLONE_CONFIRM", "read-only")
	var stdout, stderr bytes.Buffer

	code := run([]string{"safe-db-url"}, &stdout, &stderr)

	require.Equal(t, 0, code)
	assert.NotContains(t, stdout.String(), "supersecret")
	assert.Contains(t, stdout.String(), "conbench_readonly@clone-db.example:5432")
	assert.NotContains(t, stderr.String(), "supersecret")
	assert.Contains(t, stdout.String(), "default_transaction_read_only=on")
	assert.Empty(t, stderr.String())
}

func TestPreflightOpenErrorDoesNotLeakPassword(t *testing.T) {
	t.Setenv("CONBENCH_PROD_CLONE_DB_URL", "http://conbench_readonly:supersecret@clone-db.example:5432/conbench_prod")
	t.Setenv("CONBENCH_PROD_CLONE_CONFIRM", "read-only")
	var stdout, stderr bytes.Buffer

	code := run([]string{"preflight", "--out", t.TempDir()}, &stdout, &stderr)

	require.Equal(t, 1, code)
	assert.Empty(t, stdout.String())
	assert.NotContains(t, stderr.String(), "supersecret")
}

func TestSamplesSelectionErrorDoesNotLeakPassword(t *testing.T) {
	rawDBURL := "postgresql://conbench_readonly:supersecret@clone-db.example:5432/conbench_prod"
	t.Setenv("CONBENCH_PROD_CLONE_DB_URL", rawDBURL)
	t.Setenv("CONBENCH_PROD_CLONE_CONFIRM", "read-only")
	t.Setenv("CONBENCH_PROD_CLONE_READONLY_ROLE", "conbench_readonly")
	safeDBURL, err := SafeDBURL(Config{
		RawDBURL:     rawDBURL,
		Confirm:      ConfirmReadOnly,
		ReadOnlyRole: "conbench_readonly",
	})
	require.NoError(t, err)
	stubSamplesCommand(t,
		func(context.Context, string) (*pgxpool.Pool, error) { return nil, nil },
		func(context.Context, *pgxpool.Pool) (TargetInfo, error) {
			return validSamplesTargetInfo("conbench_readonly"), nil
		},
		func(context.Context, SampleQueryer, time.Time) (SampleManifest, error) {
			return SampleManifest{}, errors.New("raw " + rawDBURL + " safe " + safeDBURL + " password supersecret")
		},
	)
	var stdout, stderr bytes.Buffer

	code := run([]string{"samples", "--out", t.TempDir()}, &stdout, &stderr)

	require.Equal(t, 1, code)
	assert.Empty(t, stdout.String())
	assert.NotContains(t, stderr.String(), rawDBURL)
	assert.NotContains(t, stderr.String(), safeDBURL)
	assert.NotContains(t, stderr.String(), "supersecret")
	assert.Contains(t, stderr.String(), "<redacted>")
}

func TestRedactSensitiveErrorRemovesURLAndPassword(t *testing.T) {
	cfg := Config{
		RawDBURL: "postgresql://conbench_readonly:supersecret@clone-db.example:5432/conbench_prod",
		Confirm:  ConfirmReadOnly,
	}
	safeDBURL, err := SafeDBURL(cfg)
	require.NoError(t, err)
	err = errors.New("raw " + cfg.RawDBURL + " safe " + safeDBURL + " password supersecret")

	message := redactSensitiveError(err, cfg, safeDBURL)

	assert.NotContains(t, message, cfg.RawDBURL)
	assert.NotContains(t, message, safeDBURL)
	assert.NotContains(t, message, "supersecret")
	assert.Contains(t, message, "<redacted>")
}

func TestSamplesCommandRequiresReadOnlyRoleUnlessDevRoleAllowed(t *testing.T) {
	t.Setenv("CONBENCH_PROD_CLONE_DB_URL", "postgresql://conbench_readonly:supersecret@clone-db.example:5432/conbench_prod")
	t.Setenv("CONBENCH_PROD_CLONE_CONFIRM", "read-only")
	openCalled := false
	stubSamplesCommand(t,
		func(context.Context, string) (*pgxpool.Pool, error) {
			openCalled = true
			return nil, nil
		},
		func(context.Context, *pgxpool.Pool) (TargetInfo, error) {
			return validSamplesTargetInfo("conbench_readonly"), nil
		},
		func(context.Context, SampleQueryer, time.Time) (SampleManifest, error) {
			return SampleManifest{Categories: map[string]SampleCategory{}}, nil
		},
	)
	var stdout, stderr bytes.Buffer

	code := run([]string{"samples", "--out", t.TempDir()}, &stdout, &stderr)

	require.Equal(t, 1, code)
	assert.Empty(t, stdout.String())
	assert.Contains(t, stderr.String(), EnvReadOnlyRole)
	assert.NotContains(t, stderr.String(), "supersecret")
	assert.False(t, openCalled)
}

func TestSamplesCommandAllowsDevRoleFlag(t *testing.T) {
	t.Setenv("CONBENCH_PROD_CLONE_DB_URL", "postgresql://conbench_readonly:supersecret@clone-db.example:5432/conbench_prod")
	t.Setenv("CONBENCH_PROD_CLONE_CONFIRM", "read-only")
	stubSamplesCommand(t,
		func(context.Context, string) (*pgxpool.Pool, error) { return nil, nil },
		func(context.Context, *pgxpool.Pool) (TargetInfo, error) {
			return validSamplesTargetInfo("conbench_writer"), nil
		},
		func(_ context.Context, _ SampleQueryer, generatedAt time.Time) (SampleManifest, error) {
			return SampleManifest{
				GeneratedAt: generatedAt,
				Categories:  map[string]SampleCategory{},
			}, nil
		},
	)
	var stdout, stderr bytes.Buffer

	code := run([]string{"samples", "--allow-dev-role", "--out", t.TempDir()}, &stdout, &stderr)

	require.Equal(t, 0, code)
	assert.Empty(t, stdout.String())
	assert.Empty(t, stderr.String())
}

func TestPreflightPolicyRequiresExpectedRoleUnlessDevRoleAllowed(t *testing.T) {
	cfg := Config{
		RawDBURL: "postgresql://conbench_readonly@clone-db.example:5432/conbench_prod",
		Confirm:  ConfirmReadOnly,
	}

	_, err := preflightPolicy(cfg, preflightConfig{})
	require.Error(t, err)
	assert.Contains(t, err.Error(), EnvReadOnlyRole)

	policy, err := preflightPolicy(cfg, preflightConfig{allowDevRole: true})
	require.NoError(t, err)
	assert.True(t, policy.AllowDevRole)
	assert.Empty(t, policy.ExpectedReadOnlyRole)
}

func TestPreflightPolicyUsesExpectedRoleFromConfig(t *testing.T) {
	policy, err := preflightPolicy(Config{
		RawDBURL:     "postgresql://conbench_readonly@clone-db.example:5432/conbench_prod",
		Confirm:      ConfirmReadOnly,
		ReadOnlyRole: "conbench_readonly",
	}, preflightConfig{})
	require.NoError(t, err)

	assert.Equal(t, "conbench_prod", policy.ExpectedDatabase)
	assert.Equal(t, []string{"clone-db.example"}, policy.ExpectedHosts)
	assert.Equal(t, 5432, policy.ExpectedPort)
	assert.Equal(t, "conbench_readonly", policy.ExpectedReadOnlyRole)
	assert.True(t, policy.RequireReadOnlyRole)
}

func TestPreflightArtifactMarksDevDryRunNonAcceptance(t *testing.T) {
	info := TargetInfo{User: "conbench_writer"}
	policy := DefaultTargetPolicy()
	policy.AllowDevRole = true

	artifact := newPreflightArtifact(info, policy, nil)

	assert.True(t, artifact.Valid)
	assert.False(t, artifact.AcceptanceEligible)
}

func TestPreflightArtifactRequiresExpectedReadOnlyRoleForAcceptance(t *testing.T) {
	info := TargetInfo{User: "conbench_readonly"}
	policy := DefaultTargetPolicy()
	policy.ExpectedReadOnlyRole = "conbench_readonly"

	artifact := newPreflightArtifact(info, policy, nil)

	assert.True(t, artifact.Valid)
	assert.True(t, artifact.AcceptanceEligible)
}

func TestCompareCountsCommandExitsZeroForEqualCounts(t *testing.T) {
	dir := t.TempDir()
	before := filepath.Join(dir, "before.json")
	after := filepath.Join(dir, "after.json")
	out := filepath.Join(dir, "delta.json")
	snapshot := completeCountSnapshot()
	writeJSON(t, before, snapshot)
	writeJSON(t, after, snapshot)
	var stdout, stderr bytes.Buffer

	code := run([]string{"compare-counts", "--before", before, "--after", after, "--out", out}, &stdout, &stderr)

	require.Equal(t, 0, code)
	assert.Empty(t, stdout.String())
	assert.Empty(t, stderr.String())
	delta := readDelta(t, out)
	assert.False(t, delta.Changed)
}

func TestCompareCountsCommandExitsNonZeroForChangedCounts(t *testing.T) {
	dir := t.TempDir()
	before := filepath.Join(dir, "before.json")
	after := filepath.Join(dir, "after.json")
	out := filepath.Join(dir, "delta.json")
	beforeSnapshot := completeCountSnapshot()
	afterSnapshot := completeCountSnapshot()
	afterSnapshot.WritableTableCounts[`public."case"`] = beforeSnapshot.WritableTableCounts[`public."case"`] + 1
	writeJSON(t, before, beforeSnapshot)
	writeJSON(t, after, afterSnapshot)
	var stdout, stderr bytes.Buffer

	code := run([]string{"compare-counts", "--before", before, "--after", after, "--out", out}, &stdout, &stderr)

	require.Equal(t, 1, code)
	assert.Empty(t, stdout.String())
	assert.Contains(t, stderr.String(), "count mismatch")
	delta := readDelta(t, out)
	require.True(t, delta.Changed)
	require.Len(t, delta.Tables, 1)
	assert.Equal(t, int64(1), delta.Tables[0].Delta)
}

func TestSamplesCommandHelpMentionsOutput(t *testing.T) {
	var stdout, stderr bytes.Buffer

	code := run([]string{"samples", "--help"}, &stdout, &stderr)

	require.Equal(t, 0, code)
	assert.Contains(t, stdout.String(), "usage: conbench admin prod-clone samples")
	assert.NotContains(t, stdout.String(), "usage: conbench-prod-clone samples")
	assert.Contains(t, stdout.String(), "--out")
	assert.Contains(t, stdout.String(), "--json-out")
	assert.Contains(t, stdout.String(), "--allow-dev-role")
	assert.Empty(t, stderr.String())
}

func TestParseProfileArgsRequiresServerAndSamples(t *testing.T) {
	var stdout, stderr bytes.Buffer

	_, err := parseProfileArgs(defaultCommandName, []string{"--server", "http://127.0.0.1:18080"}, &stdout, &stderr)

	require.Error(t, err)
	assert.Contains(t, stderr.String(), "usage: conbench admin prod-clone profile")
	assert.NotContains(t, stderr.String(), "usage: conbench-prod-clone profile")
}

func TestParseProfileArgsDefaultsOutputDirectory(t *testing.T) {
	var stdout, stderr bytes.Buffer

	cfg, err := parseProfileArgs(defaultCommandName, []string{"--server", "http://127.0.0.1:18080", "--samples", "samples.json"}, &stdout, &stderr)

	require.NoError(t, err)
	assert.Equal(t, "http://127.0.0.1:18080", cfg.server)
	assert.Equal(t, "samples.json", cfg.samples)
	assert.Equal(t, defaultOutputDir, cfg.outDir)
}

func TestParseReportArgsAcceptsRequireProfile(t *testing.T) {
	var stdout, stderr bytes.Buffer

	cfg, err := parseReportArgs(defaultCommandName, []string{"--out", "var/out", "--require-profile"}, &stdout, &stderr)

	require.NoError(t, err)
	assert.Equal(t, "var/out", cfg.outDir)
	assert.True(t, cfg.requireProfile)
	assert.Empty(t, stderr.String())
}

func TestParseSamplesArgsDefaultsToSamplesJSON(t *testing.T) {
	outDir := filepath.Join(t.TempDir(), "artifacts")
	var stdout, stderr bytes.Buffer

	cfg, err := parseSamplesArgs(defaultCommandName, []string{"--out", outDir}, &stdout, &stderr)

	require.NoError(t, err)
	assert.Equal(t, outDir, cfg.outDir)
	assert.Equal(t, filepath.Join(outDir, "samples.json"), cfg.jsonOut)
	assert.Empty(t, stdout.String())
	assert.Empty(t, stderr.String())
}

func TestSamplesCommandPrintsWarningsAfterWritingManifest(t *testing.T) {
	t.Setenv("CONBENCH_PROD_CLONE_DB_URL", "postgresql://conbench_readonly:supersecret@clone-db.example:5432/conbench_prod")
	t.Setenv("CONBENCH_PROD_CLONE_CONFIRM", "read-only")
	t.Setenv("CONBENCH_PROD_CLONE_READONLY_ROLE", "conbench_readonly")
	stubSamplesCommand(t,
		func(context.Context, string) (*pgxpool.Pool, error) { return nil, nil },
		func(context.Context, *pgxpool.Pool) (TargetInfo, error) {
			return validSamplesTargetInfo("conbench_readonly"), nil
		},
		func(_ context.Context, _ SampleQueryer, generatedAt time.Time) (SampleManifest, error) {
			return SampleManifest{
				GeneratedAt: generatedAt,
				Categories:  map[string]SampleCategory{},
				Warnings:    []string{"sample category mixed_unit was not found"},
			}, nil
		},
	)
	outDir := t.TempDir()
	var stdout, stderr bytes.Buffer

	code := run([]string{"samples", "--out", outDir}, &stdout, &stderr)

	require.Equal(t, 0, code)
	assert.Empty(t, stdout.String())
	assert.Contains(t, stderr.String(), "warning: sample category mixed_unit was not found")
	assert.NotContains(t, stderr.String(), "supersecret")
	var manifest SampleManifest
	data, err := os.ReadFile(filepath.Join(outDir, "samples.json"))
	require.NoError(t, err)
	require.NoError(t, json.Unmarshal(data, &manifest))
	assert.Equal(t, []string{"sample category mixed_unit was not found"}, manifest.Warnings)
}

func TestSamplesCommandUsesReadOnlySampleQueryer(t *testing.T) {
	t.Setenv("CONBENCH_PROD_CLONE_DB_URL", "postgresql://conbench_readonly:supersecret@clone-db.example:5432/conbench_prod")
	t.Setenv("CONBENCH_PROD_CLONE_CONFIRM", "read-only")
	t.Setenv("CONBENCH_PROD_CLONE_READONLY_ROLE", "conbench_readonly")
	beginCalled := false
	stubSamplesCommand(t,
		func(context.Context, string) (*pgxpool.Pool, error) { return nil, nil },
		func(context.Context, *pgxpool.Pool) (TargetInfo, error) {
			return validSamplesTargetInfo("conbench_readonly"), nil
		},
		func(_ context.Context, _ SampleQueryer, generatedAt time.Time) (SampleManifest, error) {
			return SampleManifest{
				GeneratedAt: generatedAt,
				Categories:  map[string]SampleCategory{},
			}, nil
		},
		func(context.Context, *pgxpool.Pool) (SampleQueryer, func(context.Context) error, error) {
			beginCalled = true
			return nil, func(context.Context) error { return nil }, nil
		},
	)
	var stdout, stderr bytes.Buffer

	code := run([]string{"samples", "--out", t.TempDir()}, &stdout, &stderr)

	require.Equal(t, 0, code)
	assert.True(t, beginCalled)
	assert.Empty(t, stdout.String())
	assert.Empty(t, stderr.String())
}

func TestAPIProbeCommandWritesArtifactAndTimings(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		switch r.URL.Path {
		case "/api/series":
			writeResponseJSON(t, w, map[string]any{"series": []any{validSeriesListItemResponse()}, "next_page_cursor": nil})
		case "/api/benchmark-results":
			writeResponseJSON(t, w, map[string]any{"results": []any{validResultListItemResponse()}, "next_page_cursor": nil})
		case "/api/benchmark-results/result-recent":
			writeResponseJSON(t, w, validResultDetailResponse("result-recent", "fp-recent"))
		case "/api/history/result-recent":
			writeResponseJSON(t, w, validHistorySeriesResponse("fp-recent"))
		case "/api/history":
			writeResponseJSON(t, w, validHistorySeriesResponse(r.URL.Query().Get("fingerprint")))
		default:
			http.NotFound(w, r)
		}
	}))
	defer server.Close()
	dir := t.TempDir()
	samplesPath := filepath.Join(dir, "samples.json")
	writeJSON(t, samplesPath, SampleManifest{
		Categories: map[string]SampleCategory{
			"recent_result": {ResultID: "result-recent", HistoryFingerprint: "fp-recent"},
		},
	})
	var stdout, stderr bytes.Buffer

	code := run([]string{"api-probe", "--server", server.URL, "--samples", samplesPath, "--out", dir}, &stdout, &stderr)

	require.Equal(t, 0, code)
	assert.Empty(t, stdout.String())
	assert.Empty(t, stderr.String())
	var artifact CompatibilityProbeArtifact
	readJSON(t, filepath.Join(dir, "api-probes.json"), &artifact)
	assert.True(t, artifact.Passed)
	require.Len(t, artifact.Probes, 5)
	assert.Equal(t, os.FileMode(0o600), fileMode(t, filepath.Join(dir, "api-probes.json")))
	timingsPath := filepath.Join(dir, "timings", "http.jsonl")
	timings, err := os.ReadFile(timingsPath)
	require.NoError(t, err)
	assert.Contains(t, string(timings), `"name":"ListSeries"`)
	assert.Equal(t, os.FileMode(0o600), fileMode(t, timingsPath))
}

func TestAPIProbeCommandReplacesTimingsAndTightensExistingModes(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		switch r.URL.Path {
		case "/api/series":
			writeResponseJSON(t, w, map[string]any{"series": []any{validSeriesListItemResponse()}, "next_page_cursor": nil})
		case "/api/benchmark-results":
			writeResponseJSON(t, w, map[string]any{"results": []any{validResultListItemResponse()}, "next_page_cursor": nil})
		case "/api/benchmark-results/result-recent":
			writeResponseJSON(t, w, validResultDetailResponse("result-recent", "fp-recent"))
		case "/api/history/result-recent":
			writeResponseJSON(t, w, validHistorySeriesResponse("fp-recent"))
		case "/api/history":
			writeResponseJSON(t, w, validHistorySeriesResponse(r.URL.Query().Get("fingerprint")))
		default:
			http.NotFound(w, r)
		}
	}))
	defer server.Close()
	dir := t.TempDir()
	samplesPath := filepath.Join(dir, "samples.json")
	writeJSON(t, samplesPath, SampleManifest{
		Categories: map[string]SampleCategory{
			"recent_result": {ResultID: "result-recent", HistoryFingerprint: "fp-recent"},
		},
	})
	apiPath := filepath.Join(dir, "api-probes.json")
	timingsPath := filepath.Join(dir, "timings", "http.jsonl")
	require.NoError(t, os.MkdirAll(filepath.Dir(timingsPath), 0o755))
	require.NoError(t, os.WriteFile(apiPath, []byte("old api"), 0o644))
	require.NoError(t, os.WriteFile(timingsPath, []byte("old timing\n"), 0o644))
	var stdout, stderr bytes.Buffer

	code := run([]string{"api-probe", "--server", server.URL, "--samples", samplesPath, "--out", dir}, &stdout, &stderr)

	require.Equal(t, 0, code)
	assert.Empty(t, stdout.String())
	assert.Empty(t, stderr.String())
	assert.Equal(t, os.FileMode(0o600), fileMode(t, apiPath))
	assert.Equal(t, os.FileMode(0o600), fileMode(t, timingsPath))
	timings, err := os.ReadFile(timingsPath)
	require.NoError(t, err)
	assert.NotContains(t, string(timings), "old timing")
	assert.Contains(t, string(timings), `"name":"ListSeries"`)
}

func TestAPIProbeCommandReplacesStaleArtifactWhenSamplesUnreadable(t *testing.T) {
	dir := t.TempDir()
	apiPath := filepath.Join(dir, "api-probes.json")
	writeJSON(t, apiPath, CompatibilityProbeArtifact{
		Passed: true,
		Probes: []CompatibilityProbeResult{
			{Surface: "API", Name: "stale", Passed: true},
		},
	})
	var stdout, stderr bytes.Buffer

	code := run([]string{"api-probe", "--server", "http://127.0.0.1:1", "--samples", filepath.Join(dir, "missing.json"), "--out", dir}, &stdout, &stderr)

	require.Equal(t, 1, code)
	assert.Empty(t, stdout.String())
	assert.Contains(t, stderr.String(), "read samples artifact")
	var artifact CompatibilityProbeArtifact
	readJSON(t, apiPath, &artifact)
	assert.False(t, artifact.Passed)
	require.Len(t, artifact.Probes, 1)
	assert.Equal(t, "ReadSampleManifest", artifact.Probes[0].Name)
	assert.False(t, artifact.Probes[0].Passed)
	assert.Equal(t, os.FileMode(0o600), fileMode(t, apiPath))
}

func TestLogScanCommandWritesArtifactAndFailsOnFindings(t *testing.T) {
	dir := t.TempDir()
	logPath := filepath.Join(dir, "server.log")
	require.NoError(t, os.WriteFile(logPath, []byte("ERROR: permission denied for table benchmark_result\n"), 0o600))
	var stdout, stderr bytes.Buffer

	code := run([]string{"log-scan", "--log", logPath, "--out", dir}, &stdout, &stderr)

	require.Equal(t, 1, code)
	assert.Empty(t, stdout.String())
	assert.Contains(t, stderr.String(), "blocked-write findings")
	var artifact LogScanArtifact
	readJSON(t, filepath.Join(dir, "log-scan.json"), &artifact)
	assert.False(t, artifact.Passed)
	require.Len(t, artifact.Findings, 1)
	assert.Equal(t, "permission denied", artifact.Findings[0].Pattern)
	assert.Equal(t, os.FileMode(0o600), fileMode(t, filepath.Join(dir, "log-scan.json")))
}

func TestLogScanCommandReplacesStaleArtifactWhenLogUnreadable(t *testing.T) {
	dir := t.TempDir()
	logScanPath := filepath.Join(dir, "log-scan.json")
	writeJSON(t, logScanPath, LogScanArtifact{Passed: true})
	var stdout, stderr bytes.Buffer

	code := run([]string{"log-scan", "--log", filepath.Join(dir, "missing.log"), "--out", dir}, &stdout, &stderr)

	require.Equal(t, 1, code)
	assert.Empty(t, stdout.String())
	assert.Contains(t, stderr.String(), "open server log")
	var artifact LogScanArtifact
	readJSON(t, logScanPath, &artifact)
	assert.False(t, artifact.Passed)
	assert.Contains(t, artifact.Error, "open server log")
	assert.Equal(t, os.FileMode(0o600), fileMode(t, logScanPath))
}

func TestReportCommandWritesCompatReport(t *testing.T) {
	dir := t.TempDir()
	writeCompleteReportArtifacts(t, dir)
	reportPath := filepath.Join(dir, "compat-report.md")
	require.NoError(t, os.WriteFile(reportPath, []byte("old report"), 0o644))
	var stdout, stderr bytes.Buffer

	code := run([]string{"report", "--out", dir}, &stdout, &stderr)

	require.Equal(t, 0, code)
	assert.Empty(t, stdout.String())
	assert.Empty(t, stderr.String())
	report, err := os.ReadFile(reportPath)
	require.NoError(t, err)
	assert.NotEmpty(t, report)
	assert.Equal(t, os.FileMode(0o600), fileMode(t, reportPath))
}

func TestReportCommandFailsAfterWritingReportWhenMandatoryArtifactsAreMissing(t *testing.T) {
	dir := t.TempDir()
	reportPath := filepath.Join(dir, "compat-report.md")
	var stdout, stderr bytes.Buffer

	code := run([]string{"report", "--out", dir}, &stdout, &stderr)

	require.Equal(t, 1, code)
	assert.Empty(t, stdout.String())
	assert.Contains(t, stderr.String(), "report validation failed")
	report, err := os.ReadFile(reportPath)
	require.NoError(t, err)
	assert.NotEmpty(t, report)
	assert.Equal(t, os.FileMode(0o600), fileMode(t, reportPath))
}

func TestReportCommandFailsAfterWritingReportWhenArtifactsAreSemanticallyInvalid(t *testing.T) {
	dir := t.TempDir()
	writeCompleteReportArtifacts(t, dir)
	writeJSON(t, filepath.Join(dir, "preflight.json"), map[string]any{
		"valid":               true,
		"acceptance_eligible": false,
	})
	reportPath := filepath.Join(dir, "compat-report.md")
	var stdout, stderr bytes.Buffer

	code := run([]string{"report", "--out", dir}, &stdout, &stderr)

	require.Equal(t, 1, code)
	assert.Empty(t, stdout.String())
	assert.Contains(t, stderr.String(), "report validation failed")
	assert.Contains(t, stderr.String(), "dedicated read-only role")
	report, err := os.ReadFile(reportPath)
	require.NoError(t, err)
	assert.NotEmpty(t, report)
	assert.Equal(t, os.FileMode(0o600), fileMode(t, reportPath))
}

func TestWriteFile0600TightensModeBeforeWriting(t *testing.T) {
	path := filepath.Join(t.TempDir(), "artifact.json")
	require.NoError(t, os.WriteFile(path, []byte("old"), 0o400))

	err := writeFile0600(path, []byte("new"))

	require.NoError(t, err)
	data, err := os.ReadFile(path)
	require.NoError(t, err)
	assert.Equal(t, "new", string(data))
	assert.Equal(t, os.FileMode(0o600), fileMode(t, path))
}

func TestTopLevelHelpMentionsReadCompatibilityCommands(t *testing.T) {
	var stdout, stderr bytes.Buffer

	code := run([]string{"--help"}, &stdout, &stderr)

	require.Equal(t, 0, code)
	assert.Contains(t, stdout.String(), "api-probe")
	assert.Contains(t, stdout.String(), "profile")
	assert.Contains(t, stdout.String(), "log-scan")
	assert.Contains(t, stdout.String(), "report")
	assert.Empty(t, stderr.String())
}

func TestUsageErrorsExitTwo(t *testing.T) {
	var stdout, stderr bytes.Buffer

	code := run([]string{"compare-counts", "--before", "before.json"}, &stdout, &stderr)

	require.Equal(t, 2, code)
	assert.Empty(t, stdout.String())
	assert.Contains(t, stderr.String(), "usage:")
}

func stubSamplesCommand(
	t *testing.T,
	open func(context.Context, string) (*pgxpool.Pool, error),
	probe func(context.Context, *pgxpool.Pool) (TargetInfo, error),
	selectManifest func(context.Context, SampleQueryer, time.Time) (SampleManifest, error),
	begin ...func(context.Context, *pgxpool.Pool) (SampleQueryer, func(context.Context) error, error),
) {
	t.Helper()
	oldOpen := openPGPool
	oldProbe := probeTarget
	oldSelect := selectSampleManifest
	oldBegin := beginSampleReadOnlyQueryer
	oldNow := sampleManifestGeneratedAt
	beginSampleReadOnlyQueryer = func(context.Context, *pgxpool.Pool) (SampleQueryer, func(context.Context) error, error) {
		return nil, func(context.Context) error { return nil }, nil
	}
	if len(begin) > 0 {
		beginSampleReadOnlyQueryer = begin[0]
	}
	openPGPool = open
	probeTarget = probe
	selectSampleManifest = selectManifest
	sampleManifestGeneratedAt = func() time.Time {
		return time.Date(2026, 6, 15, 14, 0, 0, 0, time.UTC)
	}
	t.Cleanup(func() {
		openPGPool = oldOpen
		probeTarget = oldProbe
		selectSampleManifest = oldSelect
		beginSampleReadOnlyQueryer = oldBegin
		sampleManifestGeneratedAt = oldNow
	})
}

func validSamplesTargetInfo(user string) TargetInfo {
	return TargetInfo{
		Database:                   "conbench_prod",
		User:                       user,
		Host:                       "clone-db.example",
		Port:                       5432,
		DefaultTransactionReadOnly: true,
		SchemaTables: []string{
			"benchmark_result",
			"case",
			"context",
			"info",
			"hardware",
			"commit",
			"api_token",
			"user",
		},
		WritableTablePrivileges: map[string][]string{},
	}
}

func writeJSON(t *testing.T, path string, value any) {
	t.Helper()
	data, err := json.Marshal(value)
	require.NoError(t, err)
	require.NoError(t, os.MkdirAll(filepath.Dir(path), 0o755))
	require.NoError(t, os.WriteFile(path, data, 0o600))
}

func writeTextFile(t *testing.T, path string, value string) {
	t.Helper()
	require.NoError(t, os.MkdirAll(filepath.Dir(path), 0o755))
	require.NoError(t, os.WriteFile(path, []byte(value), 0o600))
}

func writeCompleteReportArtifacts(t *testing.T, dir string) {
	t.Helper()
	writeJSON(t, filepath.Join(dir, "preflight.json"), map[string]any{
		"target": map[string]any{
			"database":                      "conbench_prod",
			"user":                          "conbench_readonly",
			"host":                          "clone-db.example",
			"port":                          5432,
			"default_transaction_read_only": true,
			"schema_tables":                 []string{"benchmark_result", "case", "context", "info", "hardware", "commit", "api_token", "user"},
			"writable_table_privileges":     map[string][]string{},
		},
		"policy": map[string]any{
			"expected_read_only_role": "conbench_readonly",
		},
		"valid":               true,
		"acceptance_eligible": true,
	})
	writeJSON(t, filepath.Join(dir, "samples.json"), SampleManifest{
		Categories: map[string]SampleCategory{
			"recent_result": {ResultID: "result-recent", HistoryFingerprint: "fp-recent", PointCount: 1},
		},
		Compare: &CompareSample{
			BaselineResultID:   "baseline-result",
			ContenderResultID:  "contender-result",
			HistoryFingerprint: "fp-recent",
		},
	})
	writeJSON(t, filepath.Join(dir, "api-probes.json"), CompatibilityProbeArtifact{
		Passed: true,
		Probes: []CompatibilityProbeResult{
			{Surface: "API", Name: "ListSeries", Operation: "GET /api/series", Passed: true, StatusCode: 200},
			{Surface: "API", Name: "ListBenchmarkResults", Operation: "GET /api/benchmark-results", Passed: true, StatusCode: 200},
			{Surface: "API", Name: "GetBenchmarkResult", Operation: "GET /api/benchmark-results/{id}", Passed: true, StatusCode: 200},
			{Surface: "API", Name: "GetHistoryForResult", Operation: "GET /api/history/{benchmark_result_id}", Passed: true, StatusCode: 200},
			{Surface: "API", Name: "GetHistory", Operation: "GET /api/history?fingerprint=...", Passed: true, StatusCode: 200},
			{Surface: "API", Name: "CompareBenchmarkResults", Operation: "GET /api/compare/benchmark-results", Passed: true, StatusCode: 200},
		},
	})
	writeJSON(t, filepath.Join(dir, "cli-probes.json"), CompatibilityProbeArtifact{
		Passed: true,
		Probes: []CompatibilityProbeResult{
			{Surface: "CLI", Name: "conbench results get", Operation: "results get", Passed: true},
			{Surface: "CLI", Name: "conbench series list", Operation: "series list", Passed: true},
			{Surface: "CLI", Name: "conbench compare", Operation: "compare", Passed: true},
		},
	})
	writeJSON(t, filepath.Join(dir, "sdk-smoke.json"), CompatibilityProbeArtifact{
		Passed: true,
		Probes: []CompatibilityProbeResult{{Surface: "SDK", Name: "pytest sdk smoke", Operation: "tests/test_smoke.py", Passed: true}},
	})
	writeJSON(t, filepath.Join(dir, "log-scan.json"), LogScanArtifact{
		Passed:   true,
		Findings: []LogFinding{},
	})
	counts := completeCountSnapshot()
	writeJSON(t, filepath.Join(dir, "counts-before.json"), counts)
	writeJSON(t, filepath.Join(dir, "counts-after.json"), counts)
	writeJSON(t, filepath.Join(dir, "count-delta.json"), CountComparison{Changed: false, Tables: []TableCountDelta{}})
	writeTextFile(t, filepath.Join(dir, "timings", "http.jsonl"), `{"surface":"API","name":"ListSeries","operation":"GET /api/series","method":"GET","path":"/api/series","status_code":200,"duration_ms":1,"passed":true}`+"\n")
}

func validResultDetailResponse(resultID string, historyFingerprint string) map[string]any {
	return map[string]any{
		"batch_id":                  nil,
		"change_annotations":        map[string]any{},
		"commit":                    nil,
		"commit_repo_url":           "",
		"context":                   map[string]any{},
		"data":                      []any{},
		"error":                     nil,
		"hardware":                  map[string]any{"id": "hardware-1", "hash": "hash-1", "name": "host", "type": "machine"},
		"history_fingerprint":       historyFingerprint,
		"id":                        resultID,
		"info":                      map[string]any{},
		"iterations":                nil,
		"less_is_better":            nil,
		"optional_benchmark_info":   nil,
		"run_id":                    "run-1",
		"run_reason":                nil,
		"run_tags":                  map[string]any{"name": "run"},
		"single_value_summary":      1.0,
		"single_value_summary_type": "best",
		"stats":                     map[string]any{},
		"tags":                      map[string]any{"name": "benchmark"},
		"time_unit":                 nil,
		"times":                     []any{},
		"timestamp":                 "2026-06-15T00:00:00Z",
		"unit":                      "s",
		"validation":                nil,
	}
}

func validSeriesListItemResponse() map[string]any {
	return map[string]any{
		"context":                          map[string]any{},
		"hardware":                         map[string]any{"id": "hardware-1", "hash": "hash-1", "name": "host", "type": "machine"},
		"history_fingerprint":              "fp-recent",
		"latest_commit_sha":                "commit-sha",
		"latest_commit_timestamp":          "2026-06-14T00:00:00Z",
		"latest_result_id":                 "result-recent",
		"latest_result_timestamp":          "2026-06-15T00:00:00Z",
		"latest_single_value_summary":      1.0,
		"latest_single_value_summary_type": "best",
		"less_is_better":                   true,
		"name":                             "benchmark",
		"point_count":                      1,
		"repository":                       "https://github.com/org/repo",
		"sparkline":                        []any{1.0},
		"status":                           "stable",
		"tags":                             map[string]any{},
		"unit":                             "s",
	}
}

func validResultListItemResponse() map[string]any {
	return map[string]any{
		"id":                        "result-recent",
		"run_id":                    "run-1",
		"run_tags":                  map[string]any{"name": "run"},
		"timestamp":                 "2026-06-15T00:00:00Z",
		"unit":                      "s",
		"single_value_summary":      1.0,
		"single_value_summary_type": "best",
		"history_fingerprint":       "fp-recent",
		"has_error":                 false,
		"commit":                    map[string]any{"sha": "commit-sha", "repository": "https://github.com/org/repo"},
	}
}

func validHistorySeriesResponse(historyFingerprint string) map[string]any {
	return map[string]any{
		"history_fingerprint": historyFingerprint,
		"samples": []any{
			map[string]any{
				"benchmark_result_id":       "result-recent",
				"commit_hash":               "commit-sha",
				"commit_message":            "",
				"commit_repository":         "https://github.com/org/repo",
				"commit_timestamp":          "2026-06-14T00:00:00Z",
				"hardware_hash":             "hardware-hash",
				"mean":                      1.0,
				"result_timestamp":          "2026-06-15T00:00:00Z",
				"single_value_summary":      1.0,
				"single_value_summary_type": "best",
				"unit":                      "s",
				"zscorestats":               nil,
			},
		},
	}
}

func readJSON(t *testing.T, path string, value any) {
	t.Helper()
	data, err := os.ReadFile(path)
	require.NoError(t, err)
	require.NoError(t, json.Unmarshal(data, value))
}

func writeResponseJSON(t *testing.T, w http.ResponseWriter, value any) {
	t.Helper()
	require.NoError(t, json.NewEncoder(w).Encode(value))
}

func fileMode(t *testing.T, path string) os.FileMode {
	t.Helper()
	info, err := os.Stat(path)
	require.NoError(t, err)
	return info.Mode().Perm()
}

func readDelta(t *testing.T, path string) CountComparison {
	t.Helper()
	data, err := os.ReadFile(path)
	require.NoError(t, err)
	var delta CountComparison
	require.NoError(t, json.Unmarshal(data, &delta))
	return delta
}

func completeCountSnapshot() CountSnapshot {
	return CountSnapshot{
		WritableTableCounts: map[string]int64{
			`public."case"`:    1,
			"public.context":   2,
			"public.info":      3,
			"public.hardware":  4,
			"public.commit":    5,
			"public.api_token": 6,
			`public."user"`:    7,
		},
	}
}
