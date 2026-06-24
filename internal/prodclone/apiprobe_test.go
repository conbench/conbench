package prodclone

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestRunAPIProbesUsesGeneratedClientAndRecordsTimings(t *testing.T) {
	var requested []string
	var sawAuthorization bool
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requested = append(requested, r.Method+" "+r.URL.String())
		if r.Header.Get("Authorization") != "" {
			sawAuthorization = true
		}
		w.Header().Set("Content-Type", "application/json")

		switch r.URL.Path {
		case "/api/series":
			assert.Equal(t, "GET", r.Method)
			writeAPIJSON(t, w, map[string]any{"series": []any{validSeriesListItemJSON([]any{1.0})}, "next_page_cursor": nil})
		case "/api/benchmark-results":
			assert.Equal(t, "GET", r.Method)
			writeAPIJSON(t, w, map[string]any{"results": []any{validResultListItemJSON()}, "next_page_cursor": nil})
		case "/api/benchmark-results/result-recent":
			assert.Equal(t, "GET", r.Method)
			writeAPIJSON(t, w, validResultDetailJSON("result-recent", "fp-recent"))
		case "/api/history/result-recent":
			assert.Equal(t, "GET", r.Method)
			writeAPIJSON(t, w, validHistorySeriesJSON("fp-recent"))
		case "/api/history":
			assert.Equal(t, "GET", r.Method)
			assert.Equal(t, "fp-recent", r.URL.Query().Get("fingerprint"))
			writeAPIJSON(t, w, validHistorySeriesJSON("fp-recent"))
		case "/api/compare/benchmark-results":
			assert.Equal(t, "GET", r.Method)
			query := r.URL.Query()
			assert.Equal(t, "baseline-result", query.Get("baseline_result_id"))
			assert.Equal(t, "contender-result", query.Get("contender_result_id"))
			writeAPIJSON(t, w, map[string]any{
				"analysis": map[string]any{
					"pairwise": map[string]any{
						"improvement_indicated": false,
						"regression_indicated":  false,
						"percent_change":        0,
						"percent_threshold":     5,
					},
					"lookback_z_score": map[string]any{
						"improvement_indicated": false,
						"regression_indicated":  false,
						"z_score":               0,
						"z_threshold":           5,
					},
				},
				"baseline":       map[string]any{"benchmark_result_id": "baseline-result", "run_id": "run-1", "single_value_summary": 1},
				"contender":      map[string]any{"benchmark_result_id": "contender-result", "run_id": "run-2", "single_value_summary": 2},
				"less_is_better": true,
				"unit":           "s",
			})
		case "/api/ci/report":
			assert.Equal(t, "GET", r.Method)
			query := r.URL.Query()
			assert.Equal(t, "https://github.com/conbench/prod-sample", query.Get("repository"))
			assert.Equal(t, "sha-recent", query.Get("commit_sha"))
			assert.Equal(t, "sample-run", query.Get("run_ids"))
			writeAPIJSON(t, w, validCIReportJSON())
		default:
			http.NotFound(w, r)
		}
	}))
	defer server.Close()
	manifest := SampleManifest{
		Categories: map[string]SampleCategory{
			"recent_result": {ResultID: "result-recent", HistoryFingerprint: "fp-recent"},
		},
		Compare: &CompareSample{
			BaselineResultID:   "baseline-result",
			ContenderResultID:  "contender-result",
			HistoryFingerprint: "fp-recent",
		},
		CIReport: &CIReportSample{
			Repository:         "https://github.com/conbench/prod-sample",
			CommitSHA:          "sha-recent",
			RunIDs:             []string{"sample-run"},
			ResultID:           "result-recent",
			HistoryFingerprint: "fp-recent",
		},
	}

	artifact, timings, err := RunAPIProbes(context.Background(), APIProbeConfig{
		ServerURL: server.URL,
		Samples:   manifest,
	})

	require.NoError(t, err)
	assert.True(t, artifact.Passed)
	require.Len(t, artifact.Probes, 7)
	assert.Equal(t, []string{
		"ListSeries",
		"ListBenchmarkResults",
		"GetBenchmarkResult",
		"GetHistoryForResult",
		"GetHistory",
		"CompareBenchmarkResults",
		"CIReportByCommitRun",
	}, probeNames(artifact.Probes))
	assert.False(t, sawAuthorization)
	assert.Subset(t, requested, []string{
		"GET /api/series?page_size=5",
		"GET /api/benchmark-results?page_size=5",
		"GET /api/benchmark-results/result-recent",
		"GET /api/history/result-recent",
		"GET /api/history?fingerprint=fp-recent",
		"GET /api/compare/benchmark-results?baseline_result_id=baseline-result&contender_result_id=contender-result",
		"GET /api/ci/report?repository=https%3A%2F%2Fgithub.com%2Fconbench%2Fprod-sample&commit_sha=sha-recent&run_ids=sample-run",
	})
	require.Len(t, timings, 7)
	for _, timing := range timings {
		assert.True(t, timing.Passed, timing.Name)
		assert.Equal(t, "API", timing.Surface)
		assert.Equal(t, "GET", timing.Method)
		assert.GreaterOrEqual(t, timing.DurationMS, float64(0))
	}
}

func TestRunAPIProbesFailsOnUndecodableJSON200(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_, err := w.Write([]byte("{not-json"))
		assert.NoError(t, err)
	}))
	defer server.Close()

	artifact, timings, err := RunAPIProbes(context.Background(), APIProbeConfig{
		ServerURL: server.URL,
		Samples: SampleManifest{
			Categories: map[string]SampleCategory{
				"recent_result": {ResultID: "result-recent", HistoryFingerprint: "fp-recent"},
			},
		},
	})

	require.Error(t, err)
	assert.False(t, artifact.Passed)
	require.NotEmpty(t, artifact.Probes)
	assert.False(t, artifact.Probes[0].Passed)
	assert.Contains(t, artifact.Probes[0].Error, "decode")
	require.NotEmpty(t, timings)
	assert.False(t, timings[0].Passed)
}

func TestRunAPIProbesFailsOnStructurallyInvalidJSON200(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		writeAPIJSON(t, w, map[string]any{})
	}))
	defer server.Close()

	artifact, timings, err := RunAPIProbes(context.Background(), APIProbeConfig{
		ServerURL: server.URL,
		Samples: SampleManifest{
			Categories: map[string]SampleCategory{
				"recent_result": {ResultID: "result-recent", HistoryFingerprint: "fp-recent"},
			},
			Compare: &CompareSample{
				BaselineResultID:  "baseline-result",
				ContenderResultID: "contender-result",
			},
		},
	})

	require.Error(t, err)
	assert.False(t, artifact.Passed)
	require.Len(t, timings, 6)

	probes := probesByName(artifact.Probes)
	assert.Contains(t, probes["ListSeries"].Error, "missing series array")
	assert.Contains(t, probes["ListBenchmarkResults"].Error, "missing results array")
	assert.Contains(t, probes["GetBenchmarkResult"].Error, "missing required field run_id")
	assert.Contains(t, probes["GetHistoryForResult"].Error, `expected history_fingerprint "fp-recent"`)
	assert.Contains(t, probes["GetHistory"].Error, `expected history_fingerprint "fp-recent"`)
	assert.Contains(t, probes["CompareBenchmarkResults"].Error, "missing required field baseline")
}

func TestRunAPIProbesRejectsThinResultAndCompareBodies(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		switch r.URL.Path {
		case "/api/series":
			writeAPIJSON(t, w, map[string]any{"series": []any{validSeriesListItemJSON([]any{1.0})}, "next_page_cursor": nil})
		case "/api/benchmark-results":
			writeAPIJSON(t, w, map[string]any{"results": []any{validResultListItemJSON()}, "next_page_cursor": nil})
		case "/api/benchmark-results/result-recent":
			writeAPIJSON(t, w, map[string]any{
				"id":                  "result-recent",
				"history_fingerprint": "fp-recent",
			})
		case "/api/history/result-recent":
			writeAPIJSON(t, w, validHistorySeriesJSON("fp-recent"))
		case "/api/history":
			writeAPIJSON(t, w, validHistorySeriesJSON("fp-recent"))
		case "/api/compare/benchmark-results":
			writeAPIJSON(t, w, map[string]any{
				"baseline":  map[string]any{"benchmark_result_id": "baseline-result"},
				"contender": map[string]any{"benchmark_result_id": "contender-result"},
			})
		default:
			http.NotFound(w, r)
		}
	}))
	defer server.Close()

	artifact, _, err := RunAPIProbes(context.Background(), APIProbeConfig{
		ServerURL: server.URL,
		Samples: SampleManifest{
			Categories: map[string]SampleCategory{
				"recent_result": {ResultID: "result-recent", HistoryFingerprint: "fp-recent"},
			},
			Compare: &CompareSample{
				BaselineResultID:  "baseline-result",
				ContenderResultID: "contender-result",
			},
		},
	})

	require.Error(t, err)
	probes := probesByName(artifact.Probes)
	assert.Contains(t, probes["GetBenchmarkResult"].Error, "missing required field run_id")
	assert.Contains(t, probes["CompareBenchmarkResults"].Error, "missing required field baseline.run_id")
}

func TestRunAPIProbesRejectsStructurallyInvalidPageItems(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		switch r.URL.Path {
		case "/api/series":
			writeAPIJSON(t, w, map[string]any{"series": []any{map[string]any{}}, "next_page_cursor": nil})
		case "/api/benchmark-results":
			writeAPIJSON(t, w, map[string]any{"results": []any{map[string]any{}}, "next_page_cursor": nil})
		case "/api/benchmark-results/result-recent":
			writeAPIJSON(t, w, validResultDetailJSON("result-recent", "fp-recent"))
		case "/api/history/result-recent":
			writeAPIJSON(t, w, map[string]any{"history_fingerprint": "fp-recent", "samples": []any{map[string]any{}}})
		case "/api/history":
			writeAPIJSON(t, w, map[string]any{"history_fingerprint": "fp-recent", "samples": []any{map[string]any{}}})
		default:
			http.NotFound(w, r)
		}
	}))
	defer server.Close()

	artifact, _, err := RunAPIProbes(context.Background(), APIProbeConfig{
		ServerURL: server.URL,
		Samples: SampleManifest{
			Categories: map[string]SampleCategory{
				"recent_result": {ResultID: "result-recent", HistoryFingerprint: "fp-recent"},
			},
		},
	})

	require.Error(t, err)
	probes := probesByName(artifact.Probes)
	assert.Contains(t, probes["ListSeries"].Error, "missing required field series[0].history_fingerprint")
	assert.Contains(t, probes["ListBenchmarkResults"].Error, "missing required field results[0].id")
	assert.Contains(t, probes["GetHistoryForResult"].Error, "missing required field samples[0].benchmark_result_id")
	assert.Contains(t, probes["GetHistory"].Error, "missing required field samples[0].benchmark_result_id")
}

func TestRunAPIProbesRejectsStructurallyInvalidCIReport(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		switch r.URL.Path {
		case "/api/series":
			writeAPIJSON(t, w, map[string]any{"series": []any{validSeriesListItemJSON([]any{1.0})}, "next_page_cursor": nil})
		case "/api/benchmark-results":
			writeAPIJSON(t, w, map[string]any{"results": []any{validResultListItemJSON()}, "next_page_cursor": nil})
		case "/api/benchmark-results/result-recent":
			writeAPIJSON(t, w, validResultDetailJSON("result-recent", "fp-recent"))
		case "/api/history/result-recent":
			writeAPIJSON(t, w, validHistorySeriesJSON("fp-recent"))
		case "/api/history":
			writeAPIJSON(t, w, validHistorySeriesJSON("fp-recent"))
		case "/api/ci/report":
			writeAPIJSON(t, w, map[string]any{})
		default:
			http.NotFound(w, r)
		}
	}))
	defer server.Close()

	artifact, _, err := RunAPIProbes(context.Background(), APIProbeConfig{
		ServerURL: server.URL,
		Samples: SampleManifest{
			Categories: map[string]SampleCategory{
				"recent_result": {ResultID: "result-recent", HistoryFingerprint: "fp-recent"},
			},
			CIReport: &CIReportSample{
				Repository:         "https://github.com/conbench/prod-sample",
				CommitSHA:          "sha-recent",
				RunIDs:             []string{"sample-run"},
				ResultID:           "result-recent",
				HistoryFingerprint: "fp-recent",
			},
		},
	})

	require.Error(t, err)
	probes := probesByName(artifact.Probes)
	assert.Contains(t, probes["CIReportByCommitRun"].Error, "missing required field repository")
}

func TestRunAPIProbesAllowsNullableSeriesSparkline(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		switch r.URL.Path {
		case "/api/series":
			writeAPIJSON(t, w, map[string]any{
				"series":           []any{validSeriesListItemJSON(nil)},
				"next_page_cursor": nil,
			})
		case "/api/benchmark-results":
			writeAPIJSON(t, w, map[string]any{"results": []any{validResultListItemJSON()}, "next_page_cursor": nil})
		case "/api/benchmark-results/result-recent":
			writeAPIJSON(t, w, validResultDetailJSON("result-recent", "fp-recent"))
		case "/api/history/result-recent":
			writeAPIJSON(t, w, validHistorySeriesJSON("fp-recent"))
		case "/api/history":
			writeAPIJSON(t, w, validHistorySeriesJSON(r.URL.Query().Get("fingerprint")))
		default:
			http.NotFound(w, r)
		}
	}))
	defer server.Close()

	artifact, _, err := RunAPIProbes(context.Background(), APIProbeConfig{
		ServerURL: server.URL,
		Samples: SampleManifest{
			Categories: map[string]SampleCategory{
				"recent_result": {ResultID: "result-recent", HistoryFingerprint: "fp-recent"},
			},
		},
	})

	require.NoError(t, err)
	assert.True(t, artifact.Passed)
}

func TestRunAPIProbesSkipsCompareWithoutCompareSample(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		assert.NotEqual(t, "/api/compare/benchmark-results", r.URL.Path)
		assert.NotEqual(t, "/api/ci/report", r.URL.Path)
		w.Header().Set("Content-Type", "application/json")
		switch r.URL.Path {
		case "/api/series":
			writeAPIJSON(t, w, map[string]any{"series": []any{validSeriesListItemJSON([]any{1.0})}, "next_page_cursor": nil})
		case "/api/benchmark-results":
			writeAPIJSON(t, w, map[string]any{"results": []any{validResultListItemJSON()}, "next_page_cursor": nil})
		case "/api/benchmark-results/result-recent":
			writeAPIJSON(t, w, validResultDetailJSON("result-recent", "fp-recent"))
		case "/api/history/result-recent":
			writeAPIJSON(t, w, validHistorySeriesJSON("fp-recent"))
		case "/api/history":
			writeAPIJSON(t, w, validHistorySeriesJSON(r.URL.Query().Get("fingerprint")))
		default:
			http.NotFound(w, r)
		}
	}))
	defer server.Close()

	artifact, _, err := RunAPIProbes(context.Background(), APIProbeConfig{
		ServerURL: server.URL,
		Samples: SampleManifest{
			Categories: map[string]SampleCategory{
				"recent_result": {ResultID: "result-recent", HistoryFingerprint: "fp-recent"},
			},
		},
	})

	require.NoError(t, err)
	assert.True(t, artifact.Passed)
	assert.NotContains(t, probeNames(artifact.Probes), "CompareBenchmarkResults")
	assert.NotContains(t, probeNames(artifact.Probes), "CIReportByCommitRun")
}

func TestSelectReadProbeSamplePrefersHistoryMemberOverRecentResult(t *testing.T) {
	id, fingerprint, err := selectReadProbeSample(SampleManifest{
		Categories: map[string]SampleCategory{
			"recent_result":  {ResultID: "recent-result", HistoryFingerprint: "fp-recent"},
			"history_member": {ResultID: "history-result", HistoryFingerprint: "fp-history"},
		},
	})

	require.NoError(t, err)
	assert.Equal(t, "history-result", id)
	assert.Equal(t, "fp-history", fingerprint)
}

func writeAPIJSON(t *testing.T, w http.ResponseWriter, value any) {
	t.Helper()
	assert.NoError(t, json.NewEncoder(w).Encode(value))
}

func validResultDetailJSON(resultID string, historyFingerprint string) map[string]any {
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

func validSeriesListItemJSON(sparkline any) map[string]any {
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
		"sparkline":                        sparkline,
		"status":                           "stable",
		"tags":                             map[string]any{},
		"unit":                             "s",
	}
}

func validResultListItemJSON() map[string]any {
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

func validHistorySeriesJSON(historyFingerprint string) map[string]any {
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

func validCIReportJSON() map[string]any {
	return map[string]any{
		"$schema":          "https://example.com/schemas/CIReport.json",
		"baseline":         "fork_point",
		"commit_sha":       "sha-recent",
		"missing_run_ids":  []any{},
		"report_url":       "/ci/report?repository=https%3A%2F%2Fgithub.com%2Fconbench%2Fprod-sample&commit=sha-recent&run_ids=sample-run",
		"repository":       "https://github.com/conbench/prod-sample",
		"runs":             []any{},
		"selected_run_ids": []any{"sample-run"},
		"status":           "skipped",
		"status_reason":    "no baseline run was found",
		"summary": map[string]any{
			"analyzed":          0,
			"benchmark_errors":  0,
			"compared":          0,
			"contender_results": 0,
			"improvements":      0,
			"missing_baseline":  0,
			"missing_runs":      0,
			"not_comparable":    0,
			"regressions":       0,
			"runs":              1,
		},
		"threshold":   5,
		"threshold_z": 5,
	}
}

func probeNames(probes []CompatibilityProbeResult) []string {
	names := make([]string, 0, len(probes))
	for _, probe := range probes {
		names = append(names, probe.Name)
	}
	return names
}

func probesByName(probes []CompatibilityProbeResult) map[string]CompatibilityProbeResult {
	byName := make(map[string]CompatibilityProbeResult, len(probes))
	for _, probe := range probes {
		byName[probe.Name] = probe
	}
	return byName
}
