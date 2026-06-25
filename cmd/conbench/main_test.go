package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"maps"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/jackc/pgx/v5"

	"github.com/conbench/conbench/internal/api"
	"github.com/conbench/conbench/internal/auth"
	"github.com/conbench/conbench/internal/commit"
	"github.com/conbench/conbench/internal/commit/githubtest"
	"github.com/conbench/conbench/internal/commitrepair"
	"github.com/conbench/conbench/internal/db"
	"github.com/conbench/conbench/internal/dbtest"
	"github.com/conbench/conbench/internal/server"
	"github.com/conbench/conbench/internal/service"
	"github.com/conbench/conbench/internal/storage"
	"github.com/conbench/conbench/sdk/go/conbench"
)

const testToken = "secret"

// noAuthHandler builds an auth handler with no live OIDC client or DB, for the
// server wiring used by the client-binary tests (which exercise writes, not login).
func noAuthHandler() *api.AuthHandler {
	return api.NewAuthHandler(nil, nil, auth.NewSessionSigner(""), auth.NewSigner(""), false, "", api.NewCodeStore(), false)
}

func TestNewCLIHTTPClientKeepsSubmitConnectionsWarm(t *testing.T) {
	client := newCLIHTTPClient()
	require.NotNil(t, client)
	transport, ok := client.Transport.(*http.Transport)
	require.True(t, ok)
	assert.GreaterOrEqual(t, transport.MaxIdleConnsPerHost, defaultSubmitJobs)
	assert.GreaterOrEqual(t, transport.MaxIdleConns, transport.MaxIdleConnsPerHost)
	assert.NotSame(t, http.DefaultTransport, transport)
}

func TestUsageErrorsExitTwo(t *testing.T) {
	tests := []struct {
		name string
		args []string
	}{
		{name: "empty args", args: nil},
		{name: "incomplete results", args: []string{"results"}},
		{name: "incomplete results submit", args: []string{"results", "submit"}},
		{name: "missing server on submit", args: []string{"results", "submit", "fixture.json"}},
		{name: "missing id on results get", args: []string{"results", "get", "--server", "http://h"}},
		{name: "extra id on results get", args: []string{"results", "get", "id1", "id2", "--server", "http://h"}},
		{name: "missing server on results get", args: []string{"results", "get", "id1"}},
		{name: "missing server flag value on results get", args: []string{"results", "get", "id1", "--server"}},
		{name: "missing token flag value on submit", args: []string{"results", "submit", "fixture.json", "--server", "http://h", "--token"}},
		{name: "bad compare threshold", args: []string{"compare", "baseline", "contender", "--server", "http://h", "--threshold", "nope"}},
		{name: "missing series page size flag value", args: []string{"series", "list", "--server", "http://h", "--page-size"}},
		{name: "bad series page size", args: []string{"series", "list", "--server", "http://h", "--page-size", "nope"}},
		{name: "missing history output flag value", args: []string{"history", "export", "id1", "--server", "http://h", "--output"}},
		{name: "incomplete ci", args: []string{"ci"}},
		{name: "missing ci report selector", args: []string{"ci", "report", "--server", "http://h"}},
		{name: "missing ci report commit", args: []string{"ci", "report", "--server", "http://h", "--repository", "https://github.com/org/repo"}},
		{name: "missing auth token subcommand", args: []string{"auth", "token"}},
		{name: "missing server on auth token list", args: []string{"auth", "token", "list"}},
		{name: "unknown auth token subcommand", args: []string{"auth", "token", "rotate", "--server", "http://h"}},
		{name: "missing id on auth token revoke", args: []string{"auth", "token", "revoke", "--server", "http://h"}},
		{name: "missing admin token email", args: []string{"admin", "tokens", "create", "--token-name", "buildkite"}},
		{name: "invalid admin token email", args: []string{"admin", "tokens", "create", "--email", "Buildkite <ci@example.com>", "--token-name", "buildkite"}},
		{name: "missing admin token name", args: []string{"admin", "tokens", "create", "--email", "ci@example.com"}},
		{name: "unknown command", args: []string{"unknown"}},
		{name: "unknown help topic", args: []string{"help", "does-not-exist"}},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			var stdout, stderr bytes.Buffer
			code := run(tt.args, &stdout, &stderr)

			assert.Equal(t, 2, code)
			assert.Empty(t, stdout.String())
			assert.Contains(t, stderr.String(), "Usage:")
		})
	}
}

func TestUsageErrorsUseCommandSpecificCobraUsage(t *testing.T) {
	tests := []struct {
		name       string
		args       []string
		want       []string
		wantAbsent []string
	}{
		{
			name: "result get shows result-get usage only",
			args: []string{"results", "get", "--server", "http://h"},
			want: []string{
				"missing benchmark result id",
				"Usage:",
				"conbench results get <id>",
				"--server",
			},
			wantAbsent: []string{
				"conbench ci report",
				"conbench admin repair-commits",
			},
		},
		{
			name: "admin alert delivery shows delivery flags only",
			args: []string{"admin", "alerts", "deliver", "--format", "xml"},
			want: []string{
				"--format must be text or json",
				"Usage:",
				"conbench admin alerts deliver",
				"--retry-after",
				"--timeout",
			},
			wantAbsent: []string{
				"conbench results submit",
				"conbench history export",
			},
		},
		{
			name: "unknown series flag shows series-list usage",
			args: []string{"series", "list", "--server", "http://h", "--nope"},
			want: []string{
				"unknown flag: --nope",
				"Usage:",
				"conbench series list",
				"--page-size",
			},
			wantAbsent: []string{
				"conbench ci report",
				"conbench auth login",
			},
		},
		{
			name: "unknown nested command shows parent usage",
			args: []string{"series", "unknown"},
			want: []string{
				"unknown command \"unknown\"",
				"Usage:",
				"conbench series",
				"Available Commands:",
				"list",
			},
			wantAbsent: []string{
				"conbench admin repair-commits",
				"conbench auth login",
			},
		},
		{
			name: "prod clone missing required flags shows Cobra usage",
			args: []string{"admin", "prod-clone", "profile"},
			want: []string{
				"--server is required",
				"Usage:",
				"conbench admin prod-clone profile",
				"--samples",
			},
			wantAbsent: []string{
				"usage: conbench admin prod-clone profile",
			},
		},
		{
			name: "prod clone empty required flag shows Cobra usage",
			args: []string{"admin", "prod-clone", "profile", "--server", "", "--samples", "samples.json"},
			want: []string{
				"--server is required",
				"Usage:",
				"conbench admin prod-clone profile",
			},
			wantAbsent: []string{
				"usage: conbench admin prod-clone profile",
			},
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			var stdout, stderr bytes.Buffer
			code := run(tt.args, &stdout, &stderr)

			assert.Equal(t, 2, code)
			assert.Empty(t, stdout.String())
			got := stderr.String()
			for _, want := range tt.want {
				assert.Contains(t, got, want)
			}
			for _, absent := range tt.wantAbsent {
				assert.NotContains(t, got, absent)
			}
			assert.Equal(t, 1, strings.Count(got, "Usage:"), "usage errors should include exactly one Cobra usage block")
		})
	}
}

func TestCobraHelpExitsZero(t *testing.T) {
	tests := []struct {
		name     string
		args     []string
		contains []string
	}{
		{name: "root", args: []string{"--help"}, contains: []string{"results", "compare", "serve"}},
		{name: "root help command", args: []string{"help"}, contains: []string{"results", "compare", "serve"}},
		{name: "results group", args: []string{"results", "--help"}, contains: []string{"submit", "get"}},
		{name: "results help command", args: []string{"help", "results"}, contains: []string{"submit", "get"}},
		{name: "compare leaf", args: []string{"compare", "--help"}, contains: []string{"Compare two benchmark results", "--server", "--threshold", "--threshold-z"}},
		{name: "compare help command", args: []string{"help", "compare"}, contains: []string{"Compare two benchmark results", "--server", "--threshold", "--threshold-z"}},
		{name: "submit leaf", args: []string{"results", "submit", "--help"}, contains: []string{"Submit benchmark result JSON", "--server", "--token", "--jobs"}},
		{name: "result get leaf", args: []string{"results", "get", "--help"}, contains: []string{"Fetch a benchmark result by id", "--server"}},
		{name: "series list leaf", args: []string{"series", "list", "--help"}, contains: []string{"List benchmark series", "--server", "--q", "--page-size"}},
		{name: "history export leaf", args: []string{"history", "export", "--help"}, contains: []string{"Export benchmark history as CSV", "--server", "--token", "--output"}},
		{name: "ci report leaf", args: []string{"ci", "report", "--help"}, contains: []string{"Generate a CI benchmark report", "--server", "--run-ids", "--format", "--output"}},
		{name: "openapi leaf", args: []string{"openapi", "--help"}, contains: []string{"Emit the Conbench OpenAPI document", "--downgrade"}},
		{name: "auth login leaf", args: []string{"auth", "login", "--help"}, contains: []string{"Run loopback browser login", "--server"}},
		{name: "auth token list leaf", args: []string{"auth", "token", "list", "--help"}, contains: []string{"List API tokens", "--server", "--token"}},
		{name: "auth token revoke leaf", args: []string{"auth", "token", "revoke", "--help"}, contains: []string{"Revoke an API token", "--server", "--token"}},
		{name: "admin tokens create leaf", args: []string{"admin", "tokens", "create", "--help"}, contains: []string{"Mint an API token", "--email", "--token-name"}},
		{name: "admin repair leaf", args: []string{"admin", "repair-commits", "--help"}, contains: []string{"Repair stored unknown commit rows", "--repository", "--limit", "--dry-run", "--format"}},
		{name: "admin alerts evaluate leaf", args: []string{"admin", "alerts", "evaluate", "--help"}, contains: []string{"Evaluate server-side alert rules", "--format"}},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			var stdout, stderr bytes.Buffer
			code := run(tt.args, &stdout, &stderr)

			assert.Equal(t, 0, code)
			assert.Empty(t, stderr.String())
			for _, want := range tt.contains {
				assert.Contains(t, stdout.String(), want)
			}
		})
	}
}

func TestProdCloneMigrationHelpersAreHiddenFromGeneralHelp(t *testing.T) {
	var stdout, stderr bytes.Buffer
	code := run([]string{"admin", "--help"}, &stdout, &stderr)

	assert.Equal(t, 0, code)
	assert.Empty(t, stderr.String())
	assert.NotContains(t, stdout.String(), "prod-clone")

	stdout.Reset()
	stderr.Reset()
	code = run([]string{"admin", "prod-clone", "--help"}, &stdout, &stderr)
	assert.Equal(t, 0, code)
	assert.Empty(t, stderr.String())
	assert.Contains(t, stdout.String(), "temporary migration-only")
	assert.Contains(t, stdout.String(), "Available Commands:")
	assert.Contains(t, stdout.String(), "samples")
	assert.Contains(t, stdout.String(), "report")
}

func TestProdCloneLegacyHelpPseudoCommandIsNotRegistered(t *testing.T) {
	var stdout, stderr bytes.Buffer
	code := run([]string{"admin", "prod-clone", "help"}, &stdout, &stderr)

	assert.Equal(t, 2, code)
	assert.Empty(t, stdout.String())
	assert.Contains(t, stderr.String(), `unknown command "help"`)
	assert.Contains(t, stderr.String(), "Usage:")
	assert.NotContains(t, stderr.String(), "usage: conbench admin prod-clone <safe-db-url")
}

func TestPackageCommentUsesCobraProdCloneHelpSurface(t *testing.T) {
	source, err := os.ReadFile("main.go")
	require.NoError(t, err)

	text := string(source)
	assert.NotContains(t, text, "conbench admin prod-clone --help")
	assert.NotContains(t, text, "conbench admin prod-clone samples --help")
	assert.NotContains(t, text, "conbench admin prod-clone <safe-db-url")
}

func TestOpenAPICommandEmitsCanonicalSpec(t *testing.T) {
	want, err := server.OpenAPISpec()
	require.NoError(t, err)
	var stdout, stderr bytes.Buffer

	code := run([]string{"openapi"}, &stdout, &stderr)

	require.Equal(t, 0, code)
	assert.Empty(t, stderr.String())
	assert.Equal(t, string(want), stdout.String())
	assert.Contains(t, stdout.String(), "openapi: 3.1")
}

func TestOpenAPICommandEmitsDowngradedSpec(t *testing.T) {
	want, err := server.OpenAPISpec30()
	require.NoError(t, err)
	var stdout, stderr bytes.Buffer

	code := run([]string{"openapi", "--downgrade"}, &stdout, &stderr)

	require.Equal(t, 0, code)
	assert.Empty(t, stderr.String())
	assert.Equal(t, string(want), stdout.String())
	assert.Contains(t, stdout.String(), "openapi: 3.0.3")
}

func TestLeafHelpDoesNotConsumeFlagValues(t *testing.T) {
	srv := newCLITestServer(t)

	var stdout, stderr bytes.Buffer
	code := run([]string{
		"series", "list",
		"--q", "-h",
		"--server", srv.URL,
	}, &stdout, &stderr)

	require.Equal(t, 0, code, "stderr=%s", stderr.String())
	assert.Empty(t, stderr.String())
	assert.NotContains(t, stdout.String(), "List benchmark series")
	var page struct {
		Series []json.RawMessage `json:"series"`
	}
	require.NoError(t, json.Unmarshal(stdout.Bytes(), &page))
	assert.NotNil(t, page.Series)
}

func TestServeUsageErrorsExitTwo(t *testing.T) {
	var stdout, stderr bytes.Buffer
	code := run([]string{"serve", "extra"}, &stdout, &stderr)
	assert.Equal(t, 2, code)
	assert.Empty(t, stdout.String())
	assert.Contains(t, stderr.String(), "Usage:")
}

func TestServeStartupErrorExitOneAndNoStdout(t *testing.T) {
	old := serveRunner
	serveRunner = func(context.Context) error { return errors.New("missing db") }
	t.Cleanup(func() { serveRunner = old })

	var stdout, stderr bytes.Buffer
	code := run([]string{"serve"}, &stdout, &stderr)
	assert.Equal(t, 1, code)
	assert.Empty(t, stdout.String())
	assert.Contains(t, stderr.String(), "conbench: missing db")
}

func TestServeSuccessExitZeroAndNoStdout(t *testing.T) {
	old := serveRunner
	serveRunner = func(context.Context) error { return nil }
	t.Cleanup(func() { serveRunner = old })

	var stdout, stderr bytes.Buffer
	code := run([]string{"serve"}, &stdout, &stderr)
	assert.Equal(t, 0, code)
	assert.Empty(t, stdout.String())
	assert.Empty(t, stderr.String())
}

func TestAdminRepairUsageAndConfigErrors(t *testing.T) {
	mismatchCursor, err := commitrepair.EncodeCursor(commitrepair.Cursor{
		Repository: "https://github.com/org/repo",
		Sha:        "abc123",
	})
	require.NoError(t, err)

	tests := []struct {
		name           string
		args           []string
		dbURL          string
		token          string
		wantCode       int
		wantStderr     string
		wantNoStdout   bool
		wantUsageFlags []string
	}{
		{
			name:         "missing admin subcommand",
			args:         []string{"admin"},
			dbURL:        "postgres://db",
			token:        "abcde",
			wantCode:     2,
			wantStderr:   "Usage:",
			wantNoStdout: true,
		},
		{
			name:         "zero limit",
			args:         []string{"admin", "repair-commits", "--limit", "0"},
			dbURL:        "postgres://db",
			token:        "abcde",
			wantCode:     2,
			wantStderr:   "limit",
			wantNoStdout: true,
		},
		{
			name:         "malformed cursor",
			args:         []string{"admin", "repair-commits", "--cursor", "not-base64"},
			dbURL:        "postgres://db",
			token:        "abcde",
			wantCode:     2,
			wantStderr:   "cursor",
			wantNoStdout: true,
		},
		{
			name:           "bad format",
			args:           []string{"admin", "repair-commits", "--format", "xml"},
			dbURL:          "postgres://db",
			token:          "abcde",
			wantCode:       2,
			wantStderr:     "--format must be text or json",
			wantNoStdout:   true,
			wantUsageFlags: []string{"--format string", "--backfill-timeout duration", "--github-timeout duration"},
		},
		{
			name:           "zero backfill timeout",
			args:           []string{"admin", "repair-commits", "--backfill-timeout", "0"},
			dbURL:          "postgres://db",
			token:          "abcde",
			wantCode:       2,
			wantStderr:     "--backfill-timeout must be greater than 0",
			wantNoStdout:   true,
			wantUsageFlags: []string{"--backfill-timeout duration", "--github-timeout duration"},
		},
		{
			name:           "negative backfill timeout",
			args:           []string{"admin", "repair-commits", "--backfill-timeout", "-1s"},
			dbURL:          "postgres://db",
			token:          "abcde",
			wantCode:       2,
			wantStderr:     "--backfill-timeout must be greater than 0",
			wantNoStdout:   true,
			wantUsageFlags: []string{"--backfill-timeout duration", "--github-timeout duration"},
		},
		{
			name:           "zero github timeout",
			args:           []string{"admin", "repair-commits", "--github-timeout", "0"},
			dbURL:          "postgres://db",
			token:          "abcde",
			wantCode:       2,
			wantStderr:     "--github-timeout must be greater than 0",
			wantNoStdout:   true,
			wantUsageFlags: []string{"--backfill-timeout duration", "--github-timeout duration"},
		},
		{
			name:           "negative github timeout",
			args:           []string{"admin", "repair-commits", "--github-timeout", "-1s"},
			dbURL:          "postgres://db",
			token:          "abcde",
			wantCode:       2,
			wantStderr:     "--github-timeout must be greater than 0",
			wantNoStdout:   true,
			wantUsageFlags: []string{"--backfill-timeout duration", "--github-timeout duration"},
		},
		{
			name: "repository cursor mismatch",
			args: []string{
				"admin", "repair-commits",
				"--repository", "https://github.com/org/other",
				"--cursor", mismatchCursor,
			},
			dbURL:        "postgres://db",
			token:        "abcde",
			wantCode:     2,
			wantStderr:   "does not match",
			wantNoStdout: true,
		},
		{
			name:         "missing db url",
			args:         []string{"admin", "repair-commits"},
			token:        "abcde",
			wantCode:     1,
			wantStderr:   "CONBENCH_DB_URL",
			wantNoStdout: true,
		},
		{
			name:         "missing github token",
			args:         []string{"admin", "repair-commits"},
			dbURL:        "postgres://db",
			wantCode:     1,
			wantStderr:   "GITHUB_API_TOKEN",
			wantNoStdout: true,
		},
		{
			name:         "invalid github token",
			args:         []string{"admin", "repair-commits"},
			dbURL:        "postgres://db",
			token:        "bad",
			wantCode:     1,
			wantStderr:   "GITHUB_API_TOKEN",
			wantNoStdout: true,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Setenv("CONBENCH_DB_URL", tt.dbURL)
			t.Setenv("GITHUB_API_TOKEN", tt.token)

			var stdout, stderr bytes.Buffer
			code := run(tt.args, &stdout, &stderr)

			assert.Equal(t, tt.wantCode, code)
			if tt.wantNoStdout {
				assert.Empty(t, stdout.String())
			}
			assert.Contains(t, stderr.String(), tt.wantStderr)
			for _, flag := range tt.wantUsageFlags {
				assert.Contains(t, stderr.String(), flag)
			}
			assert.NotContains(t, stdout.String(), tt.wantStderr, "diagnostics must stay off stdout")
			if tt.dbURL != "" {
				assert.NotContains(t, stderr.String(), tt.dbURL, "diagnostics must not leak database URLs")
			}
			if tt.token != "" {
				assert.NotContains(t, stderr.String(), tt.token, "diagnostics must not leak tokens")
			}
		})
	}
}

func TestAdminRepairRunnerConfig(t *testing.T) {
	cursor, err := commitrepair.EncodeCursor(commitrepair.Cursor{
		Repository: "https://github.com/org/repo",
		Sha:        "abc123",
	})
	require.NoError(t, err)

	var got adminRepairConfig
	runAdminRepair = func(_ context.Context, cfg adminRepairConfig, _ io.Writer, _ io.Writer) (commitrepair.Summary, error) {
		got = cfg
		return commitrepair.Summary{Scanned: 1}, nil
	}
	t.Cleanup(func() { runAdminRepair = runAdminRepairReal })
	t.Setenv("CONBENCH_DB_URL", "postgres://user:pass@db/conbench")
	t.Setenv("GITHUB_API_TOKEN", "abcde")

	var stdout, stderr bytes.Buffer
	code := run([]string{
		"admin", "repair-commits",
		"--dry-run",
		"--repository", "git@github.com:org/repo",
		"--cursor", cursor,
		"--backfill-timeout", "1ms",
	}, &stdout, &stderr)

	require.Equal(t, 0, code, "stderr=%s", stderr.String())
	require.NotNil(t, got.Repository)
	assert.Equal(t, "https://github.com/org/repo", *got.Repository)
	require.NotNil(t, got.Cursor)
	assert.Equal(t, commitrepair.Cursor{Repository: "https://github.com/org/repo", Sha: "abc123"}, *got.Cursor)
	assert.True(t, got.DryRun)
	assert.Equal(t, 100, got.Limit)
	assert.Equal(t, time.Millisecond, got.BackfillTimeout)
	assert.Equal(t, 20*time.Second, got.GitHubTimeout)
	assert.Equal(t, "text", got.Format)
	assert.Empty(t, stderr.String())
	assert.NotContains(t, stdout.String(), "user:pass")
	assert.NotContains(t, stdout.String(), "abcde")
}

func TestAdminAlertsEvaluateUsageAndConfigErrors(t *testing.T) {
	tests := []struct {
		name         string
		args         []string
		dbURL        string
		wantCode     int
		wantStderr   string
		wantNoStdout bool
	}{
		{
			name:         "missing alerts subcommand",
			args:         []string{"admin", "alerts"},
			dbURL:        "postgres://db",
			wantCode:     2,
			wantStderr:   "Usage:",
			wantNoStdout: true,
		},
		{
			name:         "bad alerts subcommand",
			args:         []string{"admin", "alerts", "send"},
			dbURL:        "postgres://db",
			wantCode:     2,
			wantStderr:   "Usage:",
			wantNoStdout: true,
		},
		{
			name:         "bad format",
			args:         []string{"admin", "alerts", "evaluate", "--format", "xml"},
			dbURL:        "postgres://db",
			wantCode:     2,
			wantStderr:   "--format must be text or json",
			wantNoStdout: true,
		},
		{
			name:         "unexpected positional",
			args:         []string{"admin", "alerts", "evaluate", "extra"},
			dbURL:        "postgres://db",
			wantCode:     2,
			wantStderr:   "unexpected argument",
			wantNoStdout: true,
		},
		{
			name:         "missing db url",
			args:         []string{"admin", "alerts", "evaluate"},
			wantCode:     1,
			wantStderr:   "CONBENCH_DB_URL",
			wantNoStdout: true,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Setenv("CONBENCH_DB_URL", tt.dbURL)

			var stdout, stderr bytes.Buffer
			code := run(tt.args, &stdout, &stderr)

			assert.Equal(t, tt.wantCode, code)
			if tt.wantNoStdout {
				assert.Empty(t, stdout.String())
			}
			assert.Contains(t, stderr.String(), tt.wantStderr)
			if tt.dbURL != "" {
				assert.NotContains(t, stderr.String(), tt.dbURL, "diagnostics must not leak database URLs")
			}
		})
	}
}

func TestAdminAlertsEvaluateRunnerConfigAndJSONOutput(t *testing.T) {
	var got adminAlertsEvaluateConfig
	runAdminAlertsEvaluate = func(
		_ context.Context,
		cfg adminAlertsEvaluateConfig,
		_ io.Writer,
		_ io.Writer,
	) (service.AlertEvaluationSummary, error) {
		got = cfg
		return service.AlertEvaluationSummary{
			Rules: 2, Evaluated: 2, Opened: 1, Unchanged: 1,
			Events: []storage.AlertEvent{{
				ID: "event-1", RuleID: "rule-1", Kind: storage.AlertEventKindOpened,
				Status: string(service.CIReportStatusFailure), StatusReason: "regressions detected",
				Repository: "https://github.com/org/repo",
				ReportURL:  "https://conbench.example/ci/report?run_ids=run-1",
				Summary:    []byte(`{"regressions":1}`),
				CreatedAt:  time.Date(2026, 6, 18, 13, 0, 0, 0, time.UTC),
			}},
		}, nil
	}
	t.Cleanup(func() { runAdminAlertsEvaluate = runAdminAlertsEvaluateReal })
	t.Setenv("CONBENCH_DB_URL", "postgres://user:pass@db/conbench")
	t.Setenv("CONBENCH_INTENDED_BASE_URL", "https://conbench.example")

	var stdout, stderr bytes.Buffer
	code := run([]string{"admin", "alerts", "evaluate", "--format", "json"}, &stdout, &stderr)

	require.Equal(t, 0, code, "stderr=%s", stderr.String())
	assert.Equal(t, "postgres://user:pass@db/conbench", got.DatabaseURL)
	assert.Equal(t, "https://conbench.example", got.PublicBaseURL)
	assert.Equal(t, "json", got.Format)
	assert.Empty(t, stderr.String())
	assert.NotContains(t, stdout.String(), "user:pass")
	var summary struct {
		Rules  int `json:"rules"`
		Opened int `json:"opened"`
		Events []struct {
			Summary struct {
				Regressions int `json:"regressions"`
			} `json:"summary"`
		} `json:"events"`
	}
	require.NoError(t, json.Unmarshal(stdout.Bytes(), &summary))
	assert.Equal(t, 2, summary.Rules)
	assert.Equal(t, 1, summary.Opened)
	require.Len(t, summary.Events, 1)
	assert.Equal(t, 1, summary.Events[0].Summary.Regressions)
}

func TestAdminAlertsEvaluatePrintsSummaryWhenRunnerReturnsError(t *testing.T) {
	runAdminAlertsEvaluate = func(
		context.Context,
		adminAlertsEvaluateConfig,
		io.Writer,
		io.Writer,
	) (service.AlertEvaluationSummary, error) {
		return service.AlertEvaluationSummary{
			Rules:  1,
			Failed: 1,
			Failures: []service.AlertRuleFailure{{
				RuleID: "rule-1",
				Error:  "select latest run: permission denied",
			}},
		}, errors.New("one or more alert rules failed to evaluate")
	}
	t.Cleanup(func() { runAdminAlertsEvaluate = runAdminAlertsEvaluateReal })
	t.Setenv("CONBENCH_DB_URL", "postgres://db")

	var stdout, stderr bytes.Buffer
	code := run([]string{"admin", "alerts", "evaluate", "--format", "json"}, &stdout, &stderr)

	assert.Equal(t, 1, code)
	assert.Contains(t, stdout.String(), `"failed": 1`)
	assert.Contains(t, stdout.String(), "rule-1")
	assert.Contains(t, stderr.String(), "one or more alert rules failed to evaluate")
}

func TestAdminAlertsDeliverUsageAndConfigErrors(t *testing.T) {
	tests := []struct {
		name         string
		args         []string
		dbURL        string
		webhookURL   string
		slackURL     string
		githubRepo   string
		githubToken  string
		emailSMTP    string
		emailFrom    string
		emailTo      string
		emailUser    string
		emailPass    string
		wantCode     int
		wantStderr   string
		wantNoStdout bool
	}{
		{
			name:         "missing db url",
			args:         []string{"admin", "alerts", "deliver", "--webhook-url", "https://hooks.example/conbench"},
			wantCode:     1,
			wantStderr:   "CONBENCH_DB_URL",
			wantNoStdout: true,
		},
		{
			name:         "missing webhook url",
			args:         []string{"admin", "alerts", "deliver"},
			dbURL:        "postgres://db",
			wantCode:     2,
			wantStderr:   "--webhook-url or CONBENCH_ALERT_WEBHOOK_URL is required",
			wantNoStdout: true,
		},
		{
			name:         "bad webhook url",
			args:         []string{"admin", "alerts", "deliver", "--webhook-url", "ftp://hooks.example/conbench"},
			dbURL:        "postgres://db",
			wantCode:     2,
			wantStderr:   "--webhook-url must be an http or https URL",
			wantNoStdout: true,
		},
		{
			name:         "bad channel",
			args:         []string{"admin", "alerts", "deliver", "--channel", "pager"},
			dbURL:        "postgres://db",
			wantCode:     2,
			wantStderr:   "--channel must be webhook, slack, github-check, github-comment, or email",
			wantNoStdout: true,
		},
		{
			name:         "missing email smtp address",
			args:         []string{"admin", "alerts", "deliver", "--channel", "email"},
			dbURL:        "postgres://db",
			wantCode:     2,
			wantStderr:   "--email-smtp-addr or CONBENCH_ALERT_EMAIL_SMTP_ADDR is required",
			wantNoStdout: true,
		},
		{
			name:         "missing email from",
			args:         []string{"admin", "alerts", "deliver", "--channel", "email"},
			dbURL:        "postgres://db",
			emailSMTP:    "smtp.example:587",
			wantCode:     2,
			wantStderr:   "--email-from or CONBENCH_ALERT_EMAIL_FROM is required",
			wantNoStdout: true,
		},
		{
			name:         "missing email recipients",
			args:         []string{"admin", "alerts", "deliver", "--channel", "email"},
			dbURL:        "postgres://db",
			emailSMTP:    "smtp.example:587",
			emailFrom:    "alerts@example.com",
			wantCode:     2,
			wantStderr:   "--email-to or CONBENCH_ALERT_EMAIL_TO is required",
			wantNoStdout: true,
		},
		{
			name:         "bad email recipients",
			args:         []string{"admin", "alerts", "deliver", "--channel", "email"},
			dbURL:        "postgres://db",
			emailSMTP:    "smtp.example:587",
			emailFrom:    "alerts@example.com",
			emailTo:      "not an address",
			wantCode:     2,
			wantStderr:   "email recipients are invalid",
			wantNoStdout: true,
		},
		{
			name:         "incomplete email credentials",
			args:         []string{"admin", "alerts", "deliver", "--channel", "email"},
			dbURL:        "postgres://db",
			emailSMTP:    "smtp.example:587",
			emailFrom:    "alerts@example.com",
			emailTo:      "ops@example.com",
			emailUser:    "smtp-user",
			wantCode:     2,
			wantStderr:   "CONBENCH_ALERT_EMAIL_USERNAME and CONBENCH_ALERT_EMAIL_PASSWORD must be set together",
			wantNoStdout: true,
		},
		{
			name:         "missing github repository",
			args:         []string{"admin", "alerts", "deliver", "--channel", "github-check"},
			dbURL:        "postgres://db",
			githubToken:  "ghs_secret",
			wantCode:     2,
			wantStderr:   "--github-repository or CONBENCH_ALERT_GITHUB_REPOSITORY is required",
			wantNoStdout: true,
		},
		{
			name:         "missing github token",
			args:         []string{"admin", "alerts", "deliver", "--channel", "github-check", "--github-repository", "https://github.com/org/repo"},
			dbURL:        "postgres://db",
			wantCode:     2,
			wantStderr:   "--github-token, CONBENCH_ALERT_GITHUB_TOKEN, GITHUB_TOKEN, or GITHUB_API_TOKEN is required",
			wantNoStdout: true,
		},
		{
			name:         "bad github repository",
			args:         []string{"admin", "alerts", "deliver", "--channel", "github-check", "--github-repository", "https://gitlab.example/org/repo"},
			dbURL:        "postgres://db",
			githubToken:  "ghs_secret",
			wantCode:     2,
			wantStderr:   "--github-repository must be a github.com repository URL",
			wantNoStdout: true,
		},
		{
			name:         "missing slack webhook url",
			args:         []string{"admin", "alerts", "deliver", "--channel", "slack"},
			dbURL:        "postgres://db",
			wantCode:     2,
			wantStderr:   "--slack-webhook-url or CONBENCH_ALERT_SLACK_WEBHOOK_URL is required",
			wantNoStdout: true,
		},
		{
			name:         "bad slack webhook url",
			args:         []string{"admin", "alerts", "deliver", "--channel", "slack", "--slack-webhook-url", "slack://hooks.example/conbench"},
			dbURL:        "postgres://db",
			wantCode:     2,
			wantStderr:   "--slack-webhook-url must be an http or https URL",
			wantNoStdout: true,
		},
		{
			name:         "bad limit",
			args:         []string{"admin", "alerts", "deliver", "--webhook-url", "https://hooks.example/conbench", "--limit", "0"},
			dbURL:        "postgres://db",
			wantCode:     2,
			wantStderr:   "--limit must be greater than 0",
			wantNoStdout: true,
		},
		{
			name:         "bad format",
			args:         []string{"admin", "alerts", "deliver", "--webhook-url", "https://hooks.example/conbench", "--format", "xml"},
			dbURL:        "postgres://db",
			wantCode:     2,
			wantStderr:   "--format must be text or json",
			wantNoStdout: true,
		},
		{
			name:         "retry window must exceed webhook timeout",
			args:         []string{"admin", "alerts", "deliver", "--webhook-url", "https://hooks.example/conbench", "--retry-after", "5s", "--timeout", "5s"},
			dbURL:        "postgres://db",
			wantCode:     2,
			wantStderr:   "--retry-after must be greater than --timeout",
			wantNoStdout: true,
		},
		{
			name:         "unexpected positional",
			args:         []string{"admin", "alerts", "deliver", "--webhook-url", "https://hooks.example/conbench", "extra"},
			dbURL:        "postgres://db",
			wantCode:     2,
			wantStderr:   "unexpected argument",
			wantNoStdout: true,
		},
		{
			name:         "env webhook url accepted",
			args:         []string{"admin", "alerts", "deliver"},
			dbURL:        "postgres://db",
			webhookURL:   "https://hooks.example/from-env",
			wantCode:     0,
			wantNoStdout: false,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			runAdminAlertsDeliver = func(
				_ context.Context,
				_ adminAlertsDeliverConfig,
				_ io.Writer,
				_ io.Writer,
			) (service.AlertDeliverySummary, error) {
				return service.AlertDeliverySummary{}, nil
			}
			t.Cleanup(func() { runAdminAlertsDeliver = runAdminAlertsDeliverReal })
			t.Setenv("CONBENCH_DB_URL", tt.dbURL)
			t.Setenv("CONBENCH_ALERT_WEBHOOK_URL", tt.webhookURL)
			t.Setenv("CONBENCH_ALERT_SLACK_WEBHOOK_URL", tt.slackURL)
			t.Setenv("CONBENCH_ALERT_GITHUB_REPOSITORY", tt.githubRepo)
			t.Setenv("GITHUB_TOKEN", tt.githubToken)
			t.Setenv("CONBENCH_ALERT_EMAIL_SMTP_ADDR", tt.emailSMTP)
			t.Setenv("CONBENCH_ALERT_EMAIL_FROM", tt.emailFrom)
			t.Setenv("CONBENCH_ALERT_EMAIL_TO", tt.emailTo)
			t.Setenv("CONBENCH_ALERT_EMAIL_USERNAME", tt.emailUser)
			t.Setenv("CONBENCH_ALERT_EMAIL_PASSWORD", tt.emailPass)

			var stdout, stderr bytes.Buffer
			code := run(tt.args, &stdout, &stderr)

			assert.Equal(t, tt.wantCode, code)
			if tt.wantNoStdout {
				assert.Empty(t, stdout.String())
			}
			if tt.wantStderr != "" {
				assert.Contains(t, stderr.String(), tt.wantStderr)
			}
			if tt.dbURL != "" {
				assert.NotContains(t, stderr.String(), tt.dbURL, "diagnostics must not leak database URLs")
			}
		})
	}
}

func TestAdminAlertsDeliverSlackChannelConfig(t *testing.T) {
	var got adminAlertsDeliverConfig
	runAdminAlertsDeliver = func(
		_ context.Context,
		cfg adminAlertsDeliverConfig,
		_ io.Writer,
		_ io.Writer,
	) (service.AlertDeliverySummary, error) {
		got = cfg
		return service.AlertDeliverySummary{Enqueued: 1, Attempted: 1, Delivered: 1}, nil
	}
	t.Cleanup(func() { runAdminAlertsDeliver = runAdminAlertsDeliverReal })
	t.Setenv("CONBENCH_DB_URL", "postgres://db")
	t.Setenv("CONBENCH_ALERT_SLACK_WEBHOOK_URL", "https://hooks.slack.test/services/T000/B000/XXX")

	var stdout, stderr bytes.Buffer
	code := run([]string{
		"admin", "alerts", "deliver",
		"--channel", "slack",
		"--format", "json",
	}, &stdout, &stderr)

	require.Equal(t, 0, code, "stderr=%s", stderr.String())
	assert.Equal(t, service.AlertDeliveryChannelSlack, got.Channel)
	assert.Equal(t, "https://hooks.slack.test/services/T000/B000/XXX", got.Target)
	assert.Empty(t, stderr.String())
	assert.NotContains(t, stdout.String(), "hooks.slack.test")
}

func TestAdminAlertsDeliverGitHubCheckChannelConfig(t *testing.T) {
	var got adminAlertsDeliverConfig
	runAdminAlertsDeliver = func(
		_ context.Context,
		cfg adminAlertsDeliverConfig,
		_ io.Writer,
		_ io.Writer,
	) (service.AlertDeliverySummary, error) {
		got = cfg
		return service.AlertDeliverySummary{Enqueued: 1, Attempted: 1, Delivered: 1}, nil
	}
	t.Cleanup(func() { runAdminAlertsDeliver = runAdminAlertsDeliverReal })
	t.Setenv("CONBENCH_DB_URL", "postgres://db")
	t.Setenv("CONBENCH_ALERT_GITHUB_REPOSITORY", "git@github.com:org/repo")
	t.Setenv("GITHUB_TOKEN", "ghs_secret")
	t.Setenv("CONBENCH_ALERT_GITHUB_API_URL", "https://api.github.test")

	var stdout, stderr bytes.Buffer
	code := run([]string{
		"admin", "alerts", "deliver",
		"--channel", "github-check",
		"--format", "json",
	}, &stdout, &stderr)

	require.Equal(t, 0, code, "stderr=%s", stderr.String())
	assert.Equal(t, service.AlertDeliveryChannelGitHubCheck, got.Channel)
	assert.Equal(t, "https://github.com/org/repo", got.Target)
	assert.Equal(t, "https://github.com/org/repo", got.GitHubRepository)
	assert.Equal(t, "ghs_secret", got.GitHubToken)
	assert.Equal(t, "https://api.github.test", got.GitHubAPIURL)
	assert.Empty(t, stderr.String())
	assert.NotContains(t, stdout.String(), "ghs_secret")
}

func TestAdminAlertsDeliverGitHubCommentChannelConfig(t *testing.T) {
	var got adminAlertsDeliverConfig
	runAdminAlertsDeliver = func(
		_ context.Context,
		cfg adminAlertsDeliverConfig,
		_ io.Writer,
		_ io.Writer,
	) (service.AlertDeliverySummary, error) {
		got = cfg
		return service.AlertDeliverySummary{Enqueued: 1, Attempted: 1, Delivered: 1}, nil
	}
	t.Cleanup(func() { runAdminAlertsDeliver = runAdminAlertsDeliverReal })
	t.Setenv("CONBENCH_DB_URL", "postgres://db")
	t.Setenv("CONBENCH_ALERT_GITHUB_REPOSITORY", "git@github.com:org/repo")
	t.Setenv("GITHUB_TOKEN", "ghs_secret")
	t.Setenv("CONBENCH_ALERT_GITHUB_API_URL", "https://api.github.test")

	var stdout, stderr bytes.Buffer
	code := run([]string{
		"admin", "alerts", "deliver",
		"--channel", "github-comment",
		"--format", "json",
	}, &stdout, &stderr)

	require.Equal(t, 0, code, "stderr=%s", stderr.String())
	assert.Equal(t, service.AlertDeliveryChannelGitHubComment, got.Channel)
	assert.Equal(t, "https://github.com/org/repo", got.Target)
	assert.Equal(t, "https://github.com/org/repo", got.GitHubRepository)
	assert.Equal(t, "ghs_secret", got.GitHubToken)
	assert.Equal(t, "https://api.github.test", got.GitHubAPIURL)
	assert.Empty(t, stderr.String())
	assert.NotContains(t, stdout.String(), "ghs_secret")
}

func TestAdminAlertsDeliverEmailChannelConfig(t *testing.T) {
	var got adminAlertsDeliverConfig
	runAdminAlertsDeliver = func(
		_ context.Context,
		cfg adminAlertsDeliverConfig,
		_ io.Writer,
		_ io.Writer,
	) (service.AlertDeliverySummary, error) {
		got = cfg
		return service.AlertDeliverySummary{Enqueued: 1, Attempted: 1, Delivered: 1}, nil
	}
	t.Cleanup(func() { runAdminAlertsDeliver = runAdminAlertsDeliverReal })
	t.Setenv("CONBENCH_DB_URL", "postgres://db")
	t.Setenv("CONBENCH_ALERT_EMAIL_SMTP_ADDR", "smtp.example:587")
	t.Setenv("CONBENCH_ALERT_EMAIL_FROM", "Conbench Alerts <alerts@example.com>")
	t.Setenv("CONBENCH_ALERT_EMAIL_TO", "ops@example.com, dev@example.com")
	t.Setenv("CONBENCH_ALERT_EMAIL_USERNAME", "smtp-user")
	t.Setenv("CONBENCH_ALERT_EMAIL_PASSWORD", "smtp-secret")

	var stdout, stderr bytes.Buffer
	code := run([]string{
		"admin", "alerts", "deliver",
		"--channel", "email",
		"--format", "json",
	}, &stdout, &stderr)

	require.Equal(t, 0, code, "stderr=%s", stderr.String())
	assert.Equal(t, service.AlertDeliveryChannelEmail, got.Channel)
	assert.Equal(t, "ops@example.com,dev@example.com", got.Target)
	assert.Equal(t, "smtp.example:587", got.EmailSMTPAddr)
	assert.Equal(t, "Conbench Alerts <alerts@example.com>", got.EmailFrom)
	assert.Equal(t, "ops@example.com,dev@example.com", got.EmailTo)
	assert.Equal(t, "smtp-user", got.EmailUsername)
	assert.Equal(t, "smtp-secret", got.EmailPassword)
	assert.Empty(t, stderr.String())
	assert.NotContains(t, stdout.String(), "smtp-secret")
	assert.NotContains(t, stdout.String(), "smtp-user")
	assert.NotContains(t, stdout.String(), "ops@example.com")
}

func TestAdminAlertsDeliverGitHubCheckUsesFirstTokenFromGitHubAPITokenPool(t *testing.T) {
	var got adminAlertsDeliverConfig
	runAdminAlertsDeliver = func(
		_ context.Context,
		cfg adminAlertsDeliverConfig,
		_ io.Writer,
		_ io.Writer,
	) (service.AlertDeliverySummary, error) {
		got = cfg
		return service.AlertDeliverySummary{Enqueued: 1, Attempted: 1, Delivered: 1}, nil
	}
	t.Cleanup(func() { runAdminAlertsDeliver = runAdminAlertsDeliverReal })
	t.Setenv("CONBENCH_DB_URL", "postgres://db")
	t.Setenv("CONBENCH_ALERT_GITHUB_REPOSITORY", "https://github.com/org/repo")
	t.Setenv("GITHUB_API_TOKEN", "bad, ghs_pooltoken")

	var stdout, stderr bytes.Buffer
	code := run([]string{
		"admin", "alerts", "deliver",
		"--channel", "github-check",
	}, &stdout, &stderr)

	require.Equal(t, 0, code, "stderr=%s", stderr.String())
	assert.Equal(t, "ghs_pooltoken", got.GitHubToken)
	assert.Empty(t, stderr.String())
	assert.NotContains(t, stdout.String(), "ghs_pooltoken")
	assert.NotContains(t, stdout.String(), "bad, ghs_pooltoken")
}

func TestAdminAlertsDeliverRunnerConfigAndJSONOutput(t *testing.T) {
	var got adminAlertsDeliverConfig
	runAdminAlertsDeliver = func(
		_ context.Context,
		cfg adminAlertsDeliverConfig,
		_ io.Writer,
		_ io.Writer,
	) (service.AlertDeliverySummary, error) {
		got = cfg
		return service.AlertDeliverySummary{Enqueued: 2, Attempted: 1, Delivered: 1}, nil
	}
	t.Cleanup(func() { runAdminAlertsDeliver = runAdminAlertsDeliverReal })
	t.Setenv("CONBENCH_DB_URL", "postgres://user:pass@db/conbench")

	var stdout, stderr bytes.Buffer
	code := run([]string{
		"admin", "alerts", "deliver",
		"--webhook-url", "https://user:secret@hooks.example/conbench",
		"--limit", "12",
		"--retry-after", "3m",
		"--timeout", "4s",
		"--format", "json",
	}, &stdout, &stderr)

	require.Equal(t, 0, code, "stderr=%s", stderr.String())
	assert.Equal(t, "postgres://user:pass@db/conbench", got.DatabaseURL)
	assert.Equal(t, "https://user:secret@hooks.example/conbench", got.WebhookURL)
	assert.Equal(t, int32(12), got.Limit)
	assert.Equal(t, 3*time.Minute, got.RetryAfter)
	assert.Equal(t, 4*time.Second, got.Timeout)
	assert.Equal(t, "json", got.Format)
	assert.Empty(t, stderr.String())
	assert.NotContains(t, stdout.String(), "user:secret")
	assert.NotContains(t, stdout.String(), "user:pass")
	var summary service.AlertDeliverySummary
	require.NoError(t, json.Unmarshal(stdout.Bytes(), &summary))
	assert.Equal(t, 2, summary.Enqueued)
	assert.Equal(t, 1, summary.Delivered)
}

func TestAdminTokensCreateRequiresDatabaseURL(t *testing.T) {
	var stdout, stderr bytes.Buffer
	code := run([]string{
		"admin", "tokens", "create",
		"--email", "ci@example.com",
		"--token-name", "buildkite",
	}, &stdout, &stderr)

	assert.Equal(t, 1, code)
	assert.Empty(t, stdout.String())
	assert.Contains(t, stderr.String(), "CONBENCH_DB_URL is required")
	assert.NotContains(t, stderr.String(), "Usage:")
}

func TestAdminTokensCreateRunnerConfigAndJSONOutput(t *testing.T) {
	now := time.Date(2026, time.June, 24, 12, 0, 0, 0, time.UTC)
	var got adminTokenCreateConfig
	runAdminTokenCreate = func(
		_ context.Context,
		cfg adminTokenCreateConfig,
		_ io.Writer,
		_ io.Writer,
	) (adminTokenCreateOutput, error) {
		got = cfg
		return adminTokenCreateOutput{
			UserID:    "user123",
			TokenID:   "token123",
			Email:     cfg.Email,
			UserName:  cfg.UserName,
			TokenName: cfg.TokenName,
			Token:     "cb_secret",
			Prefix:    "cb_secre",
			CreatedAt: now,
		}, nil
	}
	t.Cleanup(func() { runAdminTokenCreate = runAdminTokenCreateReal })
	t.Setenv("CONBENCH_DB_URL", "postgres://user:pass@db/conbench")

	var stdout, stderr bytes.Buffer
	code := run([]string{
		"admin", "tokens", "create",
		"--email", "ci@example.com",
		"--user-name", "Buildkite Reporter",
		"--token-name", "buildkite",
	}, &stdout, &stderr)

	require.Equal(t, 0, code, "stderr=%s", stderr.String())
	assert.Equal(t, "postgres://user:pass@db/conbench", got.DatabaseURL)
	assert.Equal(t, "ci@example.com", got.Email)
	assert.Equal(t, "Buildkite Reporter", got.UserName)
	assert.Equal(t, "buildkite", got.TokenName)
	assert.Empty(t, stderr.String())
	assert.NotContains(t, stderr.String(), "cb_secret")
	var out adminTokenCreateOutput
	require.NoError(t, json.Unmarshal(stdout.Bytes(), &out))
	assert.Equal(t, "user123", out.UserID)
	assert.Equal(t, "token123", out.TokenID)
	assert.Equal(t, "ci@example.com", out.Email)
	assert.Equal(t, "Buildkite Reporter", out.UserName)
	assert.Equal(t, "buildkite", out.TokenName)
	assert.Equal(t, "cb_secret", out.Token)
	assert.Equal(t, "cb_secre", out.Prefix)
	assert.Equal(t, now, out.CreatedAt)
}

func TestAdminTokensCreateDefaultsUserNameToEmail(t *testing.T) {
	var got adminTokenCreateConfig
	runAdminTokenCreate = func(
		_ context.Context,
		cfg adminTokenCreateConfig,
		_ io.Writer,
		_ io.Writer,
	) (adminTokenCreateOutput, error) {
		got = cfg
		return adminTokenCreateOutput{UserID: "user123", TokenID: "token123", Token: "cb_secret", Prefix: "cb_secre"}, nil
	}
	t.Cleanup(func() { runAdminTokenCreate = runAdminTokenCreateReal })
	t.Setenv("CONBENCH_DB_URL", "postgres://db")

	var stdout, stderr bytes.Buffer
	code := run([]string{
		"admin", "tokens", "create",
		"--email", "ci@example.com",
		"--token-name", "buildkite",
	}, &stdout, &stderr)

	require.Equal(t, 0, code, "stderr=%s", stderr.String())
	assert.Equal(t, "ci@example.com", got.UserName)
	assert.Empty(t, stderr.String())
}

func TestAdminTokensCreateRealPostgresMintsUsableBearerToken(t *testing.T) {
	pool, ctx := dbtest.NewPool(t)
	store := db.NewStore(pool)
	t.Setenv("CONBENCH_DB_URL", pool.Config().ConnString())

	var stdout, stderr bytes.Buffer
	code := run([]string{
		"admin", "tokens", "create",
		"--email", "ci@example.com",
		"--user-name", "Buildkite Reporter",
		"--token-name", "buildkite",
	}, &stdout, &stderr)

	require.Equal(t, 0, code, "stderr=%s", stderr.String())
	assert.Empty(t, stderr.String())
	var out adminTokenCreateOutput
	require.NoError(t, json.Unmarshal(stdout.Bytes(), &out))
	assert.Equal(t, "ci@example.com", out.Email)
	assert.Equal(t, "Buildkite Reporter", out.UserName)
	assert.Equal(t, "buildkite", out.TokenName)
	assert.NotEmpty(t, out.UserID)
	assert.NotEmpty(t, out.TokenID)
	assert.NotEmpty(t, out.CreatedAt)
	assert.True(t, strings.HasPrefix(out.Token, "cb_"))
	assert.Equal(t, out.Token[:8], out.Prefix)

	row, err := store.GetAPITokenByHash(ctx, auth.HashToken(out.Token))
	require.NoError(t, err)
	assert.Equal(t, out.TokenID, row.ID)
	assert.Equal(t, out.UserID, row.UserID)
	assert.Equal(t, "buildkite", row.Name)
	assert.Equal(t, out.Prefix, row.TokenPrefix)

	user, err := store.GetUserByID(ctx, out.UserID)
	require.NoError(t, err)
	assert.Equal(t, "ci@example.com", user.Email)
	assert.Equal(t, "Buildkite Reporter", user.Name)

	principal, err := auth.New("", false, store, nil).ResolvePrincipal(ctx, "Bearer "+out.Token, "")
	require.NoError(t, err)
	assert.Equal(t, out.UserID, principal.UserID)

	var secondStdout, secondStderr bytes.Buffer
	secondCode := run([]string{
		"admin", "tokens", "create",
		"--email", "ci@example.com",
		"--user-name", "Renamed Reporter",
		"--token-name", "buildkite rerun",
	}, &secondStdout, &secondStderr)

	require.Equal(t, 0, secondCode, "stderr=%s", secondStderr.String())
	var second adminTokenCreateOutput
	require.NoError(t, json.Unmarshal(secondStdout.Bytes(), &second))
	assert.Equal(t, out.UserID, second.UserID)
	assert.Equal(t, "Buildkite Reporter", second.UserName)
	assert.Equal(t, "buildkite rerun", second.TokenName)
}

func TestAdminRepairJSONSummaryOutput(t *testing.T) {
	runAdminRepair = func(_ context.Context, _ adminRepairConfig, _ io.Writer, _ io.Writer) (commitrepair.Summary, error) {
		return commitrepair.Summary{Scanned: 2, Repaired: 1, WouldRepair: 1}, nil
	}
	t.Cleanup(func() { runAdminRepair = runAdminRepairReal })
	t.Setenv("CONBENCH_DB_URL", "postgres://db")
	t.Setenv("GITHUB_API_TOKEN", "abcde")

	var stdout, stderr bytes.Buffer
	code := run([]string{"admin", "repair-commits", "--format", "json"}, &stdout, &stderr)

	require.Equal(t, 0, code, "stderr=%s", stderr.String())
	assert.Empty(t, stderr.String())
	var got commitrepair.Summary
	require.NoError(t, json.Unmarshal(stdout.Bytes(), &got))
	assert.Equal(t, 2, got.Scanned)
	assert.Equal(t, 1, got.Repaired)
	assert.Equal(t, 1, got.WouldRepair)
	assert.Contains(t, stdout.String(), "\n  \"scanned\": 2")
}

func TestAdminRepairPreScanErrorDoesNotPrintEmptySummary(t *testing.T) {
	runAdminRepair = func(_ context.Context, _ adminRepairConfig, _ io.Writer, _ io.Writer) (commitrepair.Summary, error) {
		return commitrepair.Summary{}, errors.New("connect database failed")
	}
	t.Cleanup(func() { runAdminRepair = runAdminRepairReal })
	t.Setenv("CONBENCH_DB_URL", "postgres://db")
	t.Setenv("GITHUB_API_TOKEN", "abcde")

	var stdout, stderr bytes.Buffer
	code := run([]string{"admin", "repair-commits", "--format", "json"}, &stdout, &stderr)

	assert.Equal(t, 1, code)
	assert.Empty(t, stdout.String())
	assert.Contains(t, stderr.String(), "connect database failed")
}

func TestAdminRepairPrintsSummaryWhenRunnerReturnsError(t *testing.T) {
	runAdminRepair = func(_ context.Context, _ adminRepairConfig, _ io.Writer, _ io.Writer) (commitrepair.Summary, error) {
		return commitrepair.Summary{Scanned: 1, BackfillTimedOut: true}, errors.New("backfill shutdown timed out")
	}
	t.Cleanup(func() { runAdminRepair = runAdminRepairReal })
	t.Setenv("CONBENCH_DB_URL", "postgres://db")
	t.Setenv("GITHUB_API_TOKEN", "abcde")

	var stdout, stderr bytes.Buffer
	code := run([]string{"admin", "repair-commits", "--format", "json"}, &stdout, &stderr)

	assert.Equal(t, 1, code)
	assert.Contains(t, stdout.String(), `"backfill_timed_out": true`)
	assert.Contains(t, stderr.String(), "backfill shutdown timed out")
}

func TestAdminRepairAuthWideFailuresExitNonZeroWithSummary(t *testing.T) {
	runAdminRepair = func(_ context.Context, _ adminRepairConfig, _ io.Writer, _ io.Writer) (commitrepair.Summary, error) {
		return commitrepair.Summary{
			Scanned:             1,
			Failed:              1,
			AuthOrQuotaFailures: 1,
			Failures: []commitrepair.Failure{{
				Repository: "https://github.com/org/repo",
				Sha:        "abc123",
				Error:      "fetch commit metadata: unexpected github response 401 for https://api.github.com/repos/org/repo/commits/abc123: bad credentials",
			}},
		}, nil
	}
	t.Cleanup(func() { runAdminRepair = runAdminRepairReal })
	t.Setenv("CONBENCH_DB_URL", "postgres://db")
	t.Setenv("GITHUB_API_TOKEN", "abcde")

	var stdout, stderr bytes.Buffer
	code := run([]string{"admin", "repair-commits", "--format", "json"}, &stdout, &stderr)

	assert.Equal(t, 1, code)
	var summary commitrepair.Summary
	require.NoError(t, json.Unmarshal(stdout.Bytes(), &summary))
	assert.Equal(t, 1, summary.Failed)
	assert.Contains(t, stderr.String(), "abc123")
	assert.Contains(t, stderr.String(), "bad credentials")
	assert.Contains(t, stderr.String(), "GitHub authentication or quota failure")
}

func TestAdminRepairAuthWideFailuresExcludeUnsupportedRows(t *testing.T) {
	runAdminRepair = func(_ context.Context, _ adminRepairConfig, _ io.Writer, _ io.Writer) (commitrepair.Summary, error) {
		return commitrepair.Summary{
			Scanned:               2,
			UnsupportedRepository: 1,
			Failed:                1,
			AuthOrQuotaFailures:   1,
			Failures: []commitrepair.Failure{{
				Repository: "https://github.com/org/repo",
				Sha:        "abc",
				Error:      "fetch commit metadata: unexpected github response 401 for https://api.github.com/repos/org/repo/commits/abc: bad credentials",
			}},
		}, nil
	}
	t.Cleanup(func() { runAdminRepair = runAdminRepairReal })
	t.Setenv("CONBENCH_DB_URL", "postgres://db")
	t.Setenv("GITHUB_API_TOKEN", "abcde")

	var stdout, stderr bytes.Buffer
	code := run([]string{"admin", "repair-commits", "--format", "json"}, &stdout, &stderr)

	assert.Equal(t, 1, code)
	var summary commitrepair.Summary
	require.NoError(t, json.Unmarshal(stdout.Bytes(), &summary))
	assert.Equal(t, 2, summary.Scanned)
	assert.Equal(t, 1, summary.UnsupportedRepository)
	assert.Equal(t, 1, summary.Failed)
	assert.Contains(t, stderr.String(), "GitHub authentication or quota failure")
}

func TestAdminRepairNotFoundFailuresRemainNonFatal(t *testing.T) {
	runAdminRepair = func(_ context.Context, _ adminRepairConfig, _ io.Writer, _ io.Writer) (commitrepair.Summary, error) {
		return commitrepair.Summary{
			Scanned: 1,
			Failed:  1,
			Failures: []commitrepair.Failure{{
				Repository: "https://github.com/org/repo",
				Sha:        "missing",
				Error:      "fetch commit metadata: unexpected github response 404 for https://api.github.com/repos/org/repo/commits/missing: not found",
			}},
		}, nil
	}
	t.Cleanup(func() { runAdminRepair = runAdminRepairReal })
	t.Setenv("CONBENCH_DB_URL", "postgres://db")
	t.Setenv("GITHUB_API_TOKEN", "abcde")

	var stdout, stderr bytes.Buffer
	code := run([]string{"admin", "repair-commits", "--format", "json"}, &stdout, &stderr)

	assert.Equal(t, 0, code)
	var summary commitrepair.Summary
	require.NoError(t, json.Unmarshal(stdout.Bytes(), &summary))
	assert.Equal(t, 1, summary.Failed)
	assert.Contains(t, stderr.String(), "missing")
	assert.Contains(t, stderr.String(), "not found")
	assert.NotContains(t, stderr.String(), "GitHub authentication or quota failure")
}

func TestAdminRepairBoundedAuthFailureSampleRemainsNonFatal(t *testing.T) {
	failures := make([]commitrepair.Failure, 0, 10)
	for i := range 10 {
		failures = append(failures, commitrepair.Failure{
			Repository: "https://github.com/org/repo",
			Sha:        fmt.Sprintf("sha-%02d", i),
			Error:      "fetch commit metadata: unexpected github response 401 for https://api.github.com/repos/org/repo/commits/sha: bad credentials",
		})
	}
	runAdminRepair = func(_ context.Context, _ adminRepairConfig, _ io.Writer, _ io.Writer) (commitrepair.Summary, error) {
		return commitrepair.Summary{
			Scanned:             11,
			Failed:              11,
			AuthOrQuotaFailures: 10,
			Failures:            failures,
		}, nil
	}
	t.Cleanup(func() { runAdminRepair = runAdminRepairReal })
	t.Setenv("CONBENCH_DB_URL", "postgres://db")
	t.Setenv("GITHUB_API_TOKEN", "abcde")

	var stdout, stderr bytes.Buffer
	code := run([]string{"admin", "repair-commits", "--format", "json"}, &stdout, &stderr)

	assert.Equal(t, 0, code)
	var summary commitrepair.Summary
	require.NoError(t, json.Unmarshal(stdout.Bytes(), &summary))
	assert.Equal(t, 11, summary.Failed)
	assert.NotContains(t, stderr.String(), "GitHub authentication or quota failure")
}

func TestAdminRepairBoundedAuthFailuresExitNonZeroWhenAllClassified(t *testing.T) {
	failures := make([]commitrepair.Failure, 0, 10)
	for i := range 10 {
		failures = append(failures, commitrepair.Failure{
			Repository: "https://github.com/org/repo",
			Sha:        fmt.Sprintf("sha-%02d", i),
			Error:      "fetch commit metadata: unexpected github response 401 for https://api.github.com/repos/org/repo/commits/sha: bad credentials",
		})
	}
	runAdminRepair = func(_ context.Context, _ adminRepairConfig, _ io.Writer, _ io.Writer) (commitrepair.Summary, error) {
		return commitrepair.Summary{
			Scanned:             11,
			Failed:              11,
			AuthOrQuotaFailures: 11,
			Failures:            failures,
		}, nil
	}
	t.Cleanup(func() { runAdminRepair = runAdminRepairReal })
	t.Setenv("CONBENCH_DB_URL", "postgres://db")
	t.Setenv("GITHUB_API_TOKEN", "abcde")

	var stdout, stderr bytes.Buffer
	code := run([]string{"admin", "repair-commits", "--format", "json"}, &stdout, &stderr)

	assert.Equal(t, 1, code)
	var summary commitrepair.Summary
	require.NoError(t, json.Unmarshal(stdout.Bytes(), &summary))
	assert.Equal(t, 11, summary.Failed)
	assert.Contains(t, stderr.String(), "GitHub authentication or quota failure")
}

func TestAdminRepairFailureWarningsGoToStderr(t *testing.T) {
	runAdminRepair = func(_ context.Context, _ adminRepairConfig, _ io.Writer, _ io.Writer) (commitrepair.Summary, error) {
		return commitrepair.Summary{
			Scanned: 1,
			Failed:  1,
			Failures: []commitrepair.Failure{{
				Repository: "https://github.com/org/repo",
				Sha:        "abc123",
				Error:      "boom",
			}},
		}, nil
	}
	t.Cleanup(func() { runAdminRepair = runAdminRepairReal })
	t.Setenv("CONBENCH_DB_URL", "postgres://db")
	t.Setenv("GITHUB_API_TOKEN", "abcde")

	var stdout, stderr bytes.Buffer
	code := run([]string{"admin", "repair-commits"}, &stdout, &stderr)

	assert.Equal(t, 0, code)
	assert.Contains(t, stderr.String(), "abc123")
	assert.Contains(t, stderr.String(), "boom")
	assert.NotContains(t, stdout.String(), "abc123")
	assert.NotContains(t, stdout.String(), "boom")
}

func TestAdminRepairRealPostgresDryRunAndRepair(t *testing.T) {
	pool, ctx := dbtest.NewPool(t)
	store := db.NewStore(pool)
	repo := "https://github.com/org/repo"
	commitID, err := store.GetOrCreateCommit(ctx, storage.InsertCommitParams{
		Sha:        adminRepairChildSha,
		Repository: repo,
	})
	require.NoError(t, err)

	srv := githubtest.NewServer(t)
	fakeAdminRepairRepo(t, srv)
	newAdminGitHubClient = func(tokenEnv string) *commit.GitHubClient {
		return commit.NewGitHubClient(tokenEnv, srv.URL)
	}
	t.Cleanup(func() { newAdminGitHubClient = newAdminGitHubClientReal })
	t.Setenv("CONBENCH_DB_URL", pool.Config().ConnString())
	t.Setenv("GITHUB_API_TOKEN", "abcde")

	var dryStdout, dryStderr bytes.Buffer
	dryCode := run([]string{"admin", "repair-commits", "--format", "json", "--dry-run"}, &dryStdout, &dryStderr)
	require.Equal(t, 0, dryCode, "stderr=%s", dryStderr.String())
	assert.Empty(t, dryStderr.String())
	var drySummary commitrepair.Summary
	require.NoError(t, json.Unmarshal(dryStdout.Bytes(), &drySummary))
	assert.Equal(t, 1, drySummary.WouldRepair)
	assert.Equal(t, 0, drySummary.Repaired)
	assertAdminRepairUnknownCommit(t, ctx, pool, commitID, adminRepairChildSha)

	var stdout, stderr bytes.Buffer
	code := run([]string{"admin", "repair-commits", "--format", "json"}, &stdout, &stderr)
	require.Equal(t, 0, code, "stderr=%s", stderr.String())
	assert.Empty(t, stderr.String())
	var summary commitrepair.Summary
	require.NoError(t, json.Unmarshal(stdout.Bytes(), &summary))
	assert.Equal(t, 1, summary.Repaired)
	assert.Equal(t, 0, summary.WouldRepair)
	assertAdminRepairRepairedCommit(t, ctx, pool, commitID, adminRepairChildSha)
}

const adminRepairChildSha = "02addad336ba19a654f9c857ede546331be7b631"

func fakeAdminRepairRepo(t *testing.T, srv *githubtest.Server) {
	t.Helper()
	srv.HandleJSON("/repos/org/repo/commits/"+adminRepairChildSha, githubtest.Fixture(t, "github_child.json"))
	srv.HandleJSON("/repos/org/repo", []byte(`{"fork":false,"owner":{"login":"org"},"default_branch":"main"}`))
	srv.HandleJSON("/repos/org/repo/compare/org:main..."+adminRepairChildSha,
		[]byte(`{"merge_base_commit":{"sha":"`+adminRepairChildSha+`"}}`))
}

func assertAdminRepairUnknownCommit(t *testing.T, ctx context.Context, pool dbtestPool, id, sha string) {
	t.Helper()
	var got struct {
		Sha          string
		Timestamp    *time.Time
		ForkPointSha *string
	}
	err := pool.QueryRow(ctx, `SELECT sha, timestamp, fork_point_sha FROM commit WHERE id = $1`, id).
		Scan(&got.Sha, &got.Timestamp, &got.ForkPointSha)
	require.NoError(t, err)
	assert.Equal(t, sha, got.Sha)
	assert.Nil(t, got.Timestamp)
	assert.Nil(t, got.ForkPointSha)
}

func assertAdminRepairRepairedCommit(t *testing.T, ctx context.Context, pool dbtestPool, id, sha string) {
	t.Helper()
	var got struct {
		Sha          string
		Timestamp    *time.Time
		ForkPointSha *string
	}
	err := pool.QueryRow(ctx, `SELECT sha, timestamp, fork_point_sha FROM commit WHERE id = $1`, id).
		Scan(&got.Sha, &got.Timestamp, &got.ForkPointSha)
	require.NoError(t, err)
	assert.Equal(t, sha, got.Sha)
	require.NotNil(t, got.Timestamp)
	require.NotNil(t, got.ForkPointSha)
	assert.Equal(t, sha, *got.ForkPointSha)
}

type dbtestPool interface {
	QueryRow(context.Context, string, ...any) pgx.Row
}

func TestCIReportParseArgs(t *testing.T) {
	got, err := parseCIReportArgs([]string{
		"--server", "http://h",
		"--token", "tok",
		"--repository", "https://github.com/org/repo",
		"--commit", "abc",
		"--run-ids", "run-a,run-b",
		"--baseline-run-ids", "base-a,base-b",
		"--threshold", "2.5",
		"--threshold-z", "4",
		"--format", "markdown",
		"--output", "report.md",
		"--github-check",
		"--github-pr-comment",
		"--github-token", "ghs_secret",
		"--github-api-url", "https://api.github.test",
		"--github-pr-number", "48886",
		"--github-external-id", "buildkite-123",
		"--build-url", "https://buildkite.com/org/pipeline/builds/123",
	})
	require.NoError(t, err)
	assert.Equal(t, ciReportConfig{
		server:           "http://h",
		token:            "tok",
		repository:       "https://github.com/org/repo",
		commit:           "abc",
		runIDs:           "run-a,run-b",
		baselineRunIDs:   "base-a,base-b",
		threshold:        "2.5",
		thresholdSet:     true,
		thresholdZ:       "4",
		thresholdZSet:    true,
		format:           "markdown",
		output:           "report.md",
		githubCheck:      true,
		githubPRComment:  true,
		githubToken:      "ghs_secret",
		githubAPIURL:     "https://api.github.test",
		githubPRNumber:   "48886",
		githubExternalID: "buildkite-123",
		buildURL:         "https://buildkite.com/org/pipeline/builds/123",
	}, got)
}

func TestPublishCIReportGitHubCreatesCheckAndPRComment(t *testing.T) {
	ctx := context.Background()
	sha := "abc123def456"
	runReason := "commit"
	compareLink := "/compare?baseline=base-result&contender=result-1"
	resultTime := time.Date(2026, 6, 19, 12, 48, 38, 0, time.UTC)
	report := &conbench.CIReport{
		Repository:   "https://github.com/org/repo",
		CommitSha:    &sha,
		Status:       conbench.CIReportStatusFailure,
		StatusReason: "regressions detected",
		ReportUrl:    "https://conbench.example/ci/report?run_ids=run-1",
		Summary: conbench.CIReportSummary{
			Runs:             1,
			ContenderResults: 1,
			Compared:         1,
			Analyzed:         1,
			Regressions:      1,
		},
		Runs: &[]conbench.CIReportRun{{
			RunId:     "run-1",
			RunReason: &runReason,
			Comparisons: &[]conbench.CIReportComparison{{
				Status:   "regressed",
				Name:     "tpch",
				Tags:     map[string]any{"name": "tpch", "query_id": "TPCH-13", "language": "R"},
				Hardware: conbench.Hardware{Name: "test-mac-arm"},
				Contender: conbench.CIReportSide{
					ResultId:        "result-1",
					RunId:           "run-1",
					ResultTimestamp: resultTime,
				},
				Links: conbench.CIReportRowLinks{
					Result:  "/results/result-1",
					Compare: &compareLink,
					Series:  "/series/fp-1",
				},
			}},
		}},
	}
	var checkBody map[string]any
	var commentBody map[string]any
	var paths []string
	gh := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		paths = append(paths, r.Method+" "+r.URL.Path)
		assert.Equal(t, "Bearer ghs_secret", r.Header.Get("Authorization"))
		switch r.URL.Path {
		case "/repos/org/repo/check-runs":
			if !assert.NoError(t, json.NewDecoder(r.Body).Decode(&checkBody)) {
				w.WriteHeader(http.StatusBadRequest)
				return
			}
			assert.NoError(t, json.NewEncoder(w).Encode(map[string]any{
				"html_url": "https://github.com/org/repo/runs/82397297966",
			}))
		case "/repos/org/repo/commits/abc123def456/pulls":
			assert.NoError(t, json.NewEncoder(w).Encode([]map[string]any{{"number": 48886}}))
		case "/repos/org/repo/issues/48886/comments":
			if !assert.NoError(t, json.NewDecoder(r.Body).Decode(&commentBody)) {
				w.WriteHeader(http.StatusBadRequest)
				return
			}
			assert.NoError(t, json.NewEncoder(w).Encode(map[string]any{
				"html_url": "https://github.com/org/repo/pull/48886#issuecomment-1",
			}))
		default:
			http.NotFound(w, r)
		}
	}))
	t.Cleanup(gh.Close)

	err := publishCIReportGitHub(ctx, ciReportConfig{
		repository:       "https://github.com/org/repo",
		commit:           sha,
		githubCheck:      true,
		githubPRComment:  true,
		githubToken:      "ghs_secret",
		githubAPIURL:     gh.URL,
		githubExternalID: "buildkite-123",
		buildURL:         "https://buildkite.com/org/pipeline/builds/123",
	}, report)

	require.NoError(t, err)
	assert.Equal(t, []string{
		"POST /repos/org/repo/check-runs",
		"GET /repos/org/repo/commits/abc123def456/pulls",
		"POST /repos/org/repo/issues/48886/comments",
	}, paths)
	assert.Equal(t, "Conbench performance report", checkBody["name"])
	assert.Equal(t, sha, checkBody["head_sha"])
	assert.Equal(t, "failure", checkBody["conclusion"])
	assert.Equal(t, "buildkite-123", checkBody["external_id"])
	assert.Equal(t, report.ReportUrl, checkBody["details_url"])
	output, ok := checkBody["output"].(map[string]any)
	require.True(t, ok)
	assert.Contains(t, output["summary"], "regressions detected")
	assert.Contains(t, output["summary"], "https://buildkite.com/org/pipeline/builds/123")
	body, ok := commentBody["body"].(string)
	require.True(t, ok)
	assert.Contains(t, body, "Conbench analyzed the 1 benchmark run on commit `abc123de`.")
	assert.Contains(t, body, "There was 1 benchmark result indicating a performance regression:")
	assert.Contains(t, body, "Commit Run on `test-mac-arm`")
	assert.Contains(t, body, "[`tpch` with language=R, query_id=TPCH-13](https://conbench.example/compare?baseline=base-result&contender=result-1)")
	assert.Contains(t, body, "The [full Conbench report](https://github.com/org/repo/runs/82397297966) has more details.")
}

func TestCIReportGitHubClientPrefersAppCredentialsOverFallbackToken(t *testing.T) {
	t.Setenv("GITHUB_API_TOKEN", "ghs_fallback")
	t.Setenv("CONBENCH_CI_GITHUB_APP_ID", "12345")
	t.Setenv("CONBENCH_CI_GITHUB_APP_PRIVATE_KEY", "not a pem")

	_, err := newCIReportGitHubClient(context.Background(), ciReportConfig{})

	require.Error(t, err)
	assert.Contains(t, err.Error(), "parse github app private key")
}

func TestCIReportGitHubClientPartialAppConfigDoesNotFallbackToToken(t *testing.T) {
	t.Setenv("GITHUB_API_TOKEN", "ghs_fallback")
	t.Setenv("CONBENCH_CI_GITHUB_APP_ID", "12345")

	_, err := newCIReportGitHubClient(context.Background(), ciReportConfig{})

	require.Error(t, err)
	assert.Contains(t, err.Error(), "github app private key is required")
}

func TestCIReportParseArgsErrors(t *testing.T) {
	tests := []struct {
		name string
		args []string
	}{
		{name: "missing server", args: []string{"--run-ids", "run-a"}},
		{name: "missing selector", args: []string{"--server", "http://h"}},
		{name: "repo without commit", args: []string{"--server", "http://h", "--repository", "https://github.com/org/repo"}},
		{name: "commit without repo", args: []string{"--server", "http://h", "--commit", "abc"}},
		{name: "bad baseline", args: []string{"--server", "http://h", "--run-ids", "run-a", "--baseline", "bad"}},
		{name: "baseline run ids without run ids", args: []string{"--server", "http://h", "--baseline-run-ids", "base-a"}},
		{name: "baseline selector with baseline run ids", args: []string{"--server", "http://h", "--run-ids", "run-a", "--baseline", "parent", "--baseline-run-ids", "base-a"}},
		{name: "baseline run id count mismatch", args: []string{"--server", "http://h", "--run-ids", "run-a,run-b", "--baseline-run-ids", "base-a"}},
		{name: "bad format", args: []string{"--server", "http://h", "--run-ids", "run-a", "--format", "xml"}},
		{name: "zero threshold", args: []string{"--server", "http://h", "--run-ids", "run-a", "--threshold", "0"}},
		{name: "nan threshold z", args: []string{"--server", "http://h", "--run-ids", "run-a", "--threshold-z", "NaN"}},
		{name: "positional", args: []string{"--server", "http://h", "--run-ids", "run-a", "extra"}},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := parseCIReportArgs(tt.args)
			assert.Error(t, err)
		})
	}
}

func TestResultsGetParseArgs(t *testing.T) {
	tests := []struct {
		name string
		args []string
		want resultGetConfig
	}{
		{
			name: "positional first then flags",
			args: []string{"result-id", "--server", "http://h"},
			want: resultGetConfig{id: "result-id", server: "http://h"},
		},
		{
			name: "flags first then positional",
			args: []string{"--server", "http://h", "result-id"},
			want: resultGetConfig{id: "result-id", server: "http://h"},
		},
		{
			name: "equals form",
			args: []string{"result-id", "--server=http://h"},
			want: resultGetConfig{id: "result-id", server: "http://h"},
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := parseResultGetArgs(tt.args)
			require.NoError(t, err)
			assert.Equal(t, tt.want, got)
		})
	}
}

func TestResultsGetParseArgsErrors(t *testing.T) {
	tests := []struct {
		name string
		args []string
	}{
		{name: "missing id", args: []string{"--server", "http://h"}},
		{name: "extra id", args: []string{"id1", "id2", "--server", "http://h"}},
		{name: "missing server", args: []string{"id1"}},
		{name: "unknown flag", args: []string{"id1", "--server", "http://h", "--nope"}},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := parseResultGetArgs(tt.args)
			assert.Error(t, err)
		})
	}
}

func TestCompareCommandParseArgs(t *testing.T) {
	tests := []struct {
		name string
		args []string
		want compareConfig
	}{
		{
			name: "valid minimal",
			args: []string{"baseline-id", "contender-id", "--server", "http://h"},
			want: compareConfig{baseline: "baseline-id", contender: "contender-id", server: "http://h"},
		},
		{
			name: "flags first then positionals",
			args: []string{"--server", "http://h", "baseline-id", "contender-id"},
			want: compareConfig{baseline: "baseline-id", contender: "contender-id", server: "http://h"},
		},
		{
			name: "flags between positionals",
			args: []string{"baseline-id", "--server", "http://h", "contender-id"},
			want: compareConfig{baseline: "baseline-id", contender: "contender-id", server: "http://h"},
		},
		{
			name: "custom thresholds",
			args: []string{
				"baseline-id",
				"contender-id",
				"--server", "http://h",
				"--threshold", "2",
				"--threshold-z", "3",
			},
			want: compareConfig{
				baseline:      "baseline-id",
				contender:     "contender-id",
				server:        "http://h",
				threshold:     2,
				thresholdSet:  true,
				thresholdZ:    3,
				thresholdZSet: true,
			},
		},
		{
			name: "equals form",
			args: []string{
				"--server=http://h",
				"--threshold=2",
				"baseline-id",
				"--threshold-z=3",
				"contender-id",
			},
			want: compareConfig{
				baseline:      "baseline-id",
				contender:     "contender-id",
				server:        "http://h",
				threshold:     2,
				thresholdSet:  true,
				thresholdZ:    3,
				thresholdZSet: true,
			},
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := parseCompareArgs(tt.args)
			require.NoError(t, err)
			assert.Equal(t, tt.want, got)
		})
	}
}

func TestCompareCommandParseArgsErrors(t *testing.T) {
	tests := []struct {
		name string
		args []string
	}{
		{name: "missing baseline", args: []string{"--server", "http://h"}},
		{name: "missing contender", args: []string{"baseline-id", "--server", "http://h"}},
		{name: "extra id", args: []string{"baseline-id", "contender-id", "extra-id", "--server", "http://h"}},
		{name: "missing server", args: []string{"baseline-id", "contender-id"}},
		{name: "unknown flag", args: []string{"baseline-id", "contender-id", "--server", "http://h", "--nope"}},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := parseCompareArgs(tt.args)
			assert.Error(t, err)
		})
	}
}

func TestCompareCommandUsageErrorsExitTwo(t *testing.T) {
	tests := []struct {
		name string
		args []string
	}{
		{name: "missing baseline", args: []string{"compare", "--server", "http://h"}},
		{name: "missing contender", args: []string{"compare", "baseline-id", "--server", "http://h"}},
		{name: "extra id", args: []string{"compare", "baseline-id", "contender-id", "extra-id", "--server", "http://h"}},
		{name: "missing server", args: []string{"compare", "baseline-id", "contender-id"}},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			var stdout, stderr bytes.Buffer
			code := run(tt.args, &stdout, &stderr)

			assert.Equal(t, 2, code)
			assert.Empty(t, stdout.String())
			assert.Contains(t, stderr.String(), "Usage:")
		})
	}
}

func TestSeriesListCommandParseArgs(t *testing.T) {
	tests := []struct {
		name string
		args []string
		want seriesListConfig
	}{
		{
			name: "server only",
			args: []string{"--server", "http://h"},
			want: seriesListConfig{server: "http://h"},
		},
		{
			name: "all filters",
			args: []string{
				"--server", "http://h",
				"--q", "case",
				"--hardware", "runner",
				"--repository", "https://github.com/conbench/demo",
				"--fingerprint", "fp",
				"--active-since", "2024-01-01T00:00:00Z",
				"--active-until", "2024-01-31T00:00:00Z",
				"--cursor", "next",
				"--page-size", "5",
			},
			want: seriesListConfig{
				server:      "http://h",
				q:           "case",
				hardware:    "runner",
				repository:  "https://github.com/conbench/demo",
				fingerprint: "fp",
				activeSince: "2024-01-01T00:00:00Z",
				activeUntil: "2024-01-31T00:00:00Z",
				cursor:      "next",
				pageSize:    5,
				pageSizeSet: true,
			},
		},
		{
			name: "equals form",
			args: []string{
				"--server=http://h",
				"--q=case",
				"--hardware=runner",
				"--repository=https://github.com/conbench/demo",
				"--fingerprint=fp",
				"--active-since=2024-01-01T00:00:00Z",
				"--active-until=2024-01-31T00:00:00Z",
				"--cursor=next",
				"--page-size=5",
			},
			want: seriesListConfig{
				server:      "http://h",
				q:           "case",
				hardware:    "runner",
				repository:  "https://github.com/conbench/demo",
				fingerprint: "fp",
				activeSince: "2024-01-01T00:00:00Z",
				activeUntil: "2024-01-31T00:00:00Z",
				cursor:      "next",
				pageSize:    5,
				pageSizeSet: true,
			},
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := parseSeriesListArgs(tt.args)
			require.NoError(t, err)
			assert.Equal(t, tt.want, got)
		})
	}
}

func TestSeriesListCommandParseArgsErrors(t *testing.T) {
	tests := []struct {
		name string
		args []string
	}{
		{name: "missing server", args: nil},
		{name: "positional arg", args: []string{"unexpected", "--server", "http://h"}},
		{name: "unknown flag", args: []string{"--server", "http://h", "--nope"}},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := parseSeriesListArgs(tt.args)
			assert.Error(t, err)
		})
	}
}

func TestSeriesListCommandUsageErrorsExitTwo(t *testing.T) {
	tests := []struct {
		name string
		args []string
	}{
		{name: "missing subcommand", args: []string{"series"}},
		{name: "unknown subcommand", args: []string{"series", "unknown", "--server", "http://h"}},
		{name: "missing server", args: []string{"series", "list"}},
		{name: "positional arg", args: []string{"series", "list", "unexpected", "--server", "http://h"}},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			var stdout, stderr bytes.Buffer
			code := run(tt.args, &stdout, &stderr)

			assert.Equal(t, 2, code)
			assert.Empty(t, stdout.String())
			assert.Contains(t, stderr.String(), "Usage:")
		})
	}
}

func TestHistoryExportParseArgs(t *testing.T) {
	tests := []struct {
		name string
		args []string
		want historyExportConfig
	}{
		{
			name: "positional first",
			args: []string{"result-id", "--server", "http://h"},
			want: historyExportConfig{resultID: "result-id", server: "http://h"},
		},
		{
			name: "flags first",
			args: []string{"--server", "http://h", "--output", "history.csv", "result-id"},
			want: historyExportConfig{resultID: "result-id", server: "http://h", output: "history.csv"},
		},
		{
			name: "equals form",
			args: []string{"--server=http://h", "--token=tok", "--output=history.csv", "result-id"},
			want: historyExportConfig{resultID: "result-id", server: "http://h", token: "tok", output: "history.csv"},
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := parseHistoryExportArgs(tt.args)
			require.NoError(t, err)
			assert.Equal(t, tt.want, got)
		})
	}
}

func TestHistoryExportParseArgsErrors(t *testing.T) {
	tests := []struct {
		name string
		args []string
	}{
		{name: "missing result", args: []string{"--server", "http://h"}},
		{name: "extra result", args: []string{"id1", "id2", "--server", "http://h"}},
		{name: "missing server", args: []string{"id1"}},
		{name: "unknown flag", args: []string{"id1", "--server", "http://h", "--nope"}},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := parseHistoryExportArgs(tt.args)
			assert.Error(t, err)
		})
	}
}

func TestHistoryExportCommandUsageErrorsExitTwo(t *testing.T) {
	tests := []struct {
		name string
		args []string
	}{
		{name: "missing subcommand", args: []string{"history"}},
		{name: "unknown subcommand", args: []string{"history", "unknown", "--server", "http://h"}},
		{name: "missing result", args: []string{"history", "export", "--server", "http://h"}},
		{name: "missing server", args: []string{"history", "export", "result-id"}},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			var stdout, stderr bytes.Buffer
			code := run(tt.args, &stdout, &stderr)

			assert.Equal(t, 2, code)
			assert.Empty(t, stdout.String())
			assert.Contains(t, stderr.String(), "Usage:")
		})
	}
}

func TestRenderHistoryCSVPreservesFractionalCommitTimestamps(t *testing.T) {
	mean := 1.25
	unit := "s"
	early := time.Date(2024, 1, 1, 12, 0, 0, 123456789, time.UTC)
	late := time.Date(2024, 1, 1, 12, 0, 0, 987654321, time.UTC)
	samples := []conbench.HistorySample{
		{
			BenchmarkResultId:      "late-result",
			CommitHash:             "late-commit",
			CommitTimestamp:        &late,
			SingleValueSummary:     2,
			SingleValueSummaryType: "min",
			Mean:                   &mean,
			Unit:                   &unit,
		},
		{
			BenchmarkResultId:      "early-result",
			CommitHash:             "early-commit",
			CommitTimestamp:        &early,
			SingleValueSummary:     1,
			SingleValueSummaryType: "min",
			Mean:                   &mean,
			Unit:                   &unit,
		},
	}
	series := &conbench.HistorySeries{HistoryFingerprint: "fingerprint", Samples: &samples}

	out, err := renderHistoryCSV("late-result", series)
	require.NoError(t, err)

	csvLines := nonCommentCSVLines(string(out))
	require.Len(t, csvLines, 3, "CSV output:\n%s", out)
	assert.Equal(t, "commit_time,result_id,commit_hash,svs,mean,unit,svs_type", csvLines[0])
	assert.Equal(t, "2024-01-01T12:00:00.123456789Z,early-result,early-commit,1,1.25,s,min", csvLines[1])
	assert.Equal(t, "2024-01-01T12:00:00.987654321Z,late-result,late-commit,2,1.25,s,min", csvLines[2])
}

// TestParseSubmitArgs pins the interspersed-flag parsing: the fixture positional
// may appear before, after, or between the flags (the kata shape puts it first,
// which Go's stdlib flag package does not handle without a loop).
func TestParseSubmitArgs(t *testing.T) {
	tests := []struct {
		name string
		args []string
		want submitConfig
	}{
		{
			name: "positional first then flags (kata shape)",
			args: []string{"fixture.json", "--server", "http://h", "--token", "secret"},
			want: submitConfig{fixtures: []string{"fixture.json"}, server: "http://h", token: "secret", jobs: defaultSubmitJobs},
		},
		{
			name: "flags first then positional",
			args: []string{"--server", "http://h", "--token", "secret", "fixture.json"},
			want: submitConfig{fixtures: []string{"fixture.json"}, server: "http://h", token: "secret", jobs: defaultSubmitJobs},
		},
		{
			name: "positional between flags",
			args: []string{"--server", "http://h", "fixture.json", "--token", "secret"},
			want: submitConfig{fixtures: []string{"fixture.json"}, server: "http://h", token: "secret", jobs: defaultSubmitJobs},
		},
		{
			name: "equals form",
			args: []string{"fixture.json", "--server=http://h", "--token=secret"},
			want: submitConfig{fixtures: []string{"fixture.json"}, server: "http://h", token: "secret", jobs: defaultSubmitJobs},
		},
		{
			name: "token optional",
			args: []string{"fixture.json", "--server", "http://h"},
			want: submitConfig{fixtures: []string{"fixture.json"}, server: "http://h", token: "", jobs: defaultSubmitJobs},
		},
		{
			name: "multiple files",
			args: []string{"a.json", "b.json", "--server", "http://h", "--token", "secret", "--jobs", "4"},
			want: submitConfig{fixtures: []string{"a.json", "b.json"}, server: "http://h", token: "secret", jobs: 4},
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := parseSubmitArgs(tt.args)
			require.NoError(t, err)
			assert.Equal(t, tt.want, got)
		})
	}
}

// TestParseSubmitArgsErrors covers the rejected invocations: a clear error to
// stderr beats silently defaulting or panicking.
func TestParseSubmitArgsErrors(t *testing.T) {
	tempDir := t.TempDir()
	tests := []struct {
		name string
		args []string
	}{
		{name: "missing files", args: []string{"--server", "http://h"}},
		{name: "missing server", args: []string{"fixture.json"}},
		{name: "unknown flag", args: []string{"fixture.json", "--server", "http://h", "--nope"}},
		{name: "zero jobs", args: []string{"fixture.json", "--server", "http://h", "--jobs", "0"}},
		{name: "malformed glob", args: []string{"[", "--server", "http://h"}},
		{name: "glob matching no files", args: []string{filepath.Join(tempDir, "*.json"), "--server", "http://h"}},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := parseSubmitArgs(tt.args)
			assert.Error(t, err)
		})
	}
}

// TestDecodeFixtureRequests pins local payload decoding: one JSON object remains
// one submit request, a JSON array becomes many submit requests, and trailing
// data is rejected instead of silently submitting only the first value.
func TestDecodeFixtureRequests(t *testing.T) {
	tests := []struct {
		name      string
		content   string
		wantCount int
		wantErr   bool
	}{
		{name: "single object", content: `{"run_id": "r1"}`, wantCount: 1},
		{name: "array of objects", content: `[{"run_id": "r1"}, {"run_id": "r2"}]`, wantCount: 2},
		{name: "trailing whitespace", content: "{\"run_id\": \"r1\"}\n\t ", wantCount: 1},
		{name: "second JSON object", content: `{"run_id": "r1"}{"run_id": "r2"}`, wantErr: true},
		{name: "trailing garbage", content: `{"run_id": "r1"} trailing`, wantErr: true},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			path := filepath.Join(t.TempDir(), "result.json")
			require.NoError(t, os.WriteFile(path, []byte(tt.content), 0o600))
			got, err := decodeFixtureRequests(path)
			if tt.wantErr {
				assert.ErrorContains(t, err, "trailing data")
			} else {
				require.NoError(t, err)
				assert.Len(t, got, tt.wantCount)
			}
		})
	}
}

// TestSubmitIntegration drives the full CLI submit path against the real HTTP
// handler over real Postgres: the generated client posts the fixture, the server
// ingests it, and the CLI prints the result identity. It covers both clean
// samples and a fixture with a null sample value (an errored/partial result),
// exercising the nullable `data` element through the generated request model. It
// skips without Docker and under `go test -short` via dbtest.NewPool.
func TestSubmitIntegration(t *testing.T) {
	pool, _ := dbtest.NewPool(t)
	store := db.NewStore(pool)
	srv := httptest.NewServer(server.New(store, auth.New(testToken, false, store, nil), commit.LocalProvider{}, noAuthHandler()))
	t.Cleanup(srv.Close)

	tests := []struct {
		name    string
		fixture string
	}{
		{name: "clean samples", fixture: "result.json"},
		{name: "nullable samples", fixture: "result_nullable.json"},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			var stdout, stderr bytes.Buffer
			code := run([]string{
				"results", "submit",
				filepath.Join("testdata", tt.fixture),
				"--server", srv.URL,
				"--token", testToken,
			}, &stdout, &stderr)
			require.Equal(t, 0, code, "exit code; stderr=%s", stderr.String())
			require.Empty(t, stderr.String(), "stderr must be empty on success")

			var out struct {
				ID                 string `json:"id"`
				HistoryFingerprint string `json:"history_fingerprint"`
			}
			require.NoError(t, json.Unmarshal(stdout.Bytes(), &out))
			assert.NotEmpty(t, out.ID, "id")
			assert.NotEmpty(t, out.HistoryFingerprint, "history_fingerprint")

			// Pin the exact stdout contract: one line, only these two keys, id
			// first. Downstream tooling (CI, the keystone e2e) parses this.
			want := fmt.Sprintf("{\"id\":%q,\"history_fingerprint\":%q}\n", out.ID, out.HistoryFingerprint)
			assert.Equal(t, want, stdout.String())
		})
	}
}

func TestSubmitMultipleResultsUsesWorkerConcurrency(t *testing.T) {
	tempDir := t.TempDir()
	for _, name := range []string{"a.json", "b.json"} {
		raw, err := os.ReadFile(filepath.Join("testdata", "result.json"))
		require.NoError(t, err)
		require.NoError(t, os.WriteFile(filepath.Join(tempDir, name), raw, 0o600))
	}

	var inFlight atomic.Int32
	var maxInFlight atomic.Int32
	var requestCount atomic.Int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		assert.Equal(t, "/api/results", r.URL.Path)
		current := inFlight.Add(1)
		for {
			observed := maxInFlight.Load()
			if current <= observed || maxInFlight.CompareAndSwap(observed, current) {
				break
			}
		}
		time.Sleep(100 * time.Millisecond)
		inFlight.Add(-1)
		n := requestCount.Add(1)
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusCreated)
		_, err := fmt.Fprintf(w, `{"id":"result-%d","history_fingerprint":"fp-%d"}`, n, n)
		assert.NoError(t, err)
	}))
	t.Cleanup(srv.Close)

	var stdout bytes.Buffer
	err := runSubmitConfig(context.Background(), submitConfig{
		fixtures: []string{filepath.Join(tempDir, "a.json"), filepath.Join(tempDir, "b.json")},
		server:   srv.URL,
		jobs:     2,
	}, &stdout)

	require.NoError(t, err)
	assert.Equal(t, int32(2), requestCount.Load())
	assert.GreaterOrEqual(t, maxInFlight.Load(), int32(2), "submissions should overlap when --jobs allows it")
}

func TestSubmitStreamsDecodedWorkBeforeReadingAllFixtures(t *testing.T) {
	firstPath := "first.json"
	secondPath := "second.json"
	firstSubmitStarted := make(chan struct{})
	var firstSubmitSignal atomic.Bool

	decode := func(path string, yield func(submitRequestBody) error) error {
		switch path {
		case firstPath:
			return yield(submitRequestBody{File: path, Body: []byte(`{"run_id":"first"}`)})
		case secondPath:
			select {
			case <-firstSubmitStarted:
			case <-time.After(time.Second):
				return errors.New("decoded second fixture before submitting first fixture")
			}
			return yield(submitRequestBody{File: path, Body: []byte(`{"run_id":"second"}`)})
		default:
			return fmt.Errorf("unexpected fixture %s", path)
		}
	}
	submit := func(_ context.Context, body submitRequestBody) (submitResultLine, error) {
		if body.File == firstPath && firstSubmitSignal.CompareAndSwap(false, true) {
			close(firstSubmitStarted)
		}
		return submitResultLine{
			File:               body.File,
			Index:              body.Index,
			OK:                 true,
			ID:                 "id-" + body.File,
			HistoryFingerprint: "fp-" + body.File,
		}, nil
	}

	got, err := streamSubmitWork(
		context.Background(),
		[]string{firstPath, secondPath},
		1,
		decode,
		submit,
	)

	require.NoError(t, err)
	require.Len(t, got.lines, 2)
	assert.Equal(t, firstPath, got.lines[0].File)
	assert.Equal(t, secondPath, got.lines[1].File)
}

func TestSubmitArrayFileSubmitsEachResult(t *testing.T) {
	path := filepath.Join(t.TempDir(), "results.json")
	raw, err := os.ReadFile(filepath.Join("testdata", "result.json"))
	require.NoError(t, err)
	require.NoError(t, os.WriteFile(path, []byte("["+string(raw)+","+string(raw)+"]"), 0o600))

	var requestCount atomic.Int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		assert.Equal(t, "/api/results", r.URL.Path)
		n := requestCount.Add(1)
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusCreated)
		_, err := fmt.Fprintf(w, `{"id":"result-%d","history_fingerprint":"fp-%d"}`, n, n)
		assert.NoError(t, err)
	}))
	t.Cleanup(srv.Close)

	var stdout bytes.Buffer
	err = runSubmitConfig(context.Background(), submitConfig{
		fixtures: []string{path},
		server:   srv.URL,
		jobs:     2,
	}, &stdout)

	require.NoError(t, err)
	assert.Equal(t, int32(2), requestCount.Load())
	lines := strings.Split(strings.TrimSpace(stdout.String()), "\n")
	require.Len(t, lines, 2)
	for idx, rawLine := range lines {
		var got submitResultLine
		require.NoError(t, json.Unmarshal([]byte(rawLine), &got))
		assert.True(t, got.OK)
		assert.Equal(t, path, got.File)
		require.NotNil(t, got.Index)
		assert.Equal(t, idx, *got.Index)
	}
}

func TestSubmitPreservesExplicitNullError(t *testing.T) {
	pool, _ := dbtest.NewPool(t)
	store := db.NewStore(pool)
	srv := httptest.NewServer(server.New(store, auth.New(testToken, false, store, nil), commit.LocalProvider{}, noAuthHandler()))
	t.Cleanup(srv.Close)

	raw, err := os.ReadFile(filepath.Join("testdata", "result.json"))
	require.NoError(t, err)
	var body map[string]any
	require.NoError(t, json.Unmarshal(raw, &body))
	body["error"] = nil
	fixture := writeResultFixture(t, body)

	var stdout, stderr bytes.Buffer
	code := run([]string{
		"results", "submit",
		fixture,
		"--server", srv.URL,
		"--token", testToken,
	}, &stdout, &stderr)

	require.Equal(t, 1, code, "stdout=%s stderr=%s", stdout.String(), stderr.String())
	assert.Empty(t, stdout.String())
	assert.Contains(t, stderr.String(), "error: null is not allowed")
}

func TestResultsGetIntegration(t *testing.T) {
	pool, _ := dbtest.NewPool(t)
	store := db.NewStore(pool)
	srv := httptest.NewServer(server.New(store, auth.New(testToken, false, store, nil), commit.LocalProvider{}, noAuthHandler()))
	t.Cleanup(srv.Close)

	var submitStdout, submitStderr bytes.Buffer
	submitCode := run([]string{
		"results", "submit",
		filepath.Join("testdata", "result.json"),
		"--server", srv.URL,
		"--token", testToken,
	}, &submitStdout, &submitStderr)
	require.Equal(t, 0, submitCode, "exit code; stderr=%s", submitStderr.String())

	var submitted struct {
		ID                 string `json:"id"`
		HistoryFingerprint string `json:"history_fingerprint"`
	}
	require.NoError(t, json.Unmarshal(submitStdout.Bytes(), &submitted))
	require.NotEmpty(t, submitted.ID)

	var stdout, stderr bytes.Buffer
	code := run([]string{
		"results", "get",
		submitted.ID,
		"--server", srv.URL,
	}, &stdout, &stderr)
	require.Equal(t, 0, code, "exit code; stderr=%s", stderr.String())
	require.Empty(t, stderr.String(), "stderr must be empty on success")

	var got struct {
		ID                 string `json:"id"`
		HistoryFingerprint string `json:"history_fingerprint"`
	}
	require.NoError(t, json.Unmarshal(stdout.Bytes(), &got))
	assert.Equal(t, submitted.ID, got.ID)
	assert.Equal(t, submitted.HistoryFingerprint, got.HistoryFingerprint)
	assert.True(t, strings.HasSuffix(stdout.String(), "\n"), "stdout should be one JSON line")
}

func TestCompareCommandIntegration(t *testing.T) {
	srv := newCLITestServer(t)

	baselineID, _ := submitCLIResult(t, srv.URL, filepath.Join("testdata", "result.json"))
	contenderFixture := writeResultFixture(t, map[string]any{
		"run_id":    "cli-run-2",
		"run_name":  "cli-nightly",
		"batch_id":  "cli-batch-2",
		"timestamp": "2024-01-03T12:00:00Z",
		"github": map[string]any{
			"commit":     "cli-commit-02",
			"repository": "https://github.com/conbench/demo",
		},
		"stats": map[string]any{"data": []any{1.01, 1.03, 1.05}, "unit": "s"},
	})
	contenderID, _ := submitCLIResult(t, srv.URL, contenderFixture)

	tests := []struct {
		name string
		args []string
	}{
		{
			name: "default thresholds",
			args: []string{"compare", baselineID, contenderID, "--server", srv.URL},
		},
		{
			name: "custom thresholds",
			args: []string{"compare", baselineID, contenderID, "--server", srv.URL, "--threshold", "2", "--threshold-z", "3"},
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			var stdout, stderr bytes.Buffer
			code := run(tt.args, &stdout, &stderr)
			require.Equal(t, 0, code, "exit code; stderr=%s", stderr.String())
			require.Empty(t, stderr.String(), "stderr must be empty on success")

			var out struct {
				Baseline struct {
					BenchmarkResultID string `json:"benchmark_result_id"`
				} `json:"baseline"`
				Contender struct {
					BenchmarkResultID string `json:"benchmark_result_id"`
				} `json:"contender"`
			}
			require.NoError(t, json.Unmarshal(stdout.Bytes(), &out))
			assert.Equal(t, baselineID, out.Baseline.BenchmarkResultID)
			assert.Equal(t, contenderID, out.Contender.BenchmarkResultID)
			assert.True(t, strings.HasSuffix(stdout.String(), "\n"), "stdout should be one JSON line")
		})
	}
}

func TestSeriesListCommandIntegration(t *testing.T) {
	srv := newCLITestServer(t)

	_, fingerprint := submitCLIResult(t, srv.URL, filepath.Join("testdata", "result.json"))

	var fingerprintStdout, fingerprintStderr bytes.Buffer
	fingerprintCode := run([]string{
		"series", "list",
		"--server", srv.URL,
		"--fingerprint", fingerprint,
	}, &fingerprintStdout, &fingerprintStderr)
	require.Equal(t, 0, fingerprintCode, "exit code; stderr=%s", fingerprintStderr.String())
	require.Empty(t, fingerprintStderr.String(), "stderr must be empty on success")

	var fingerprintPage struct {
		Series []seriesListItem `json:"series"`
	}
	require.NoError(t, json.Unmarshal(fingerprintStdout.Bytes(), &fingerprintPage))
	require.NotEmpty(t, fingerprintPage.Series)
	assert.Contains(t, seriesFingerprints(fingerprintPage.Series), fingerprint)
	assert.True(t, strings.HasSuffix(fingerprintStdout.String(), "\n"), "stdout should be one JSON line")

	var qStdout, qStderr bytes.Buffer
	qCode := run([]string{
		"series", "list",
		"--server", srv.URL,
		"--q", "cli-demo",
		"--page-size", "5",
	}, &qStdout, &qStderr)
	require.Equal(t, 0, qCode, "exit code; stderr=%s", qStderr.String())
	require.Empty(t, qStderr.String(), "stderr must be empty on success")

	var qPage struct {
		Series []json.RawMessage `json:"series"`
	}
	require.NoError(t, json.Unmarshal(qStdout.Bytes(), &qPage))
	assert.NotNil(t, qPage.Series)
}

func TestHistoryExportCommandIntegration(t *testing.T) {
	srv := newCLITestServer(t)

	repo := "https://github.com/conbench/demo"
	newerFixture := writeResultFixture(t, map[string]any{
		"run_id":    "history-run-new",
		"timestamp": "2024-01-02T12:00:00Z",
		"github": map[string]any{
			"commit":     "history-commit-02",
			"repository": repo,
		},
		"stats": map[string]any{"data": []any{2.0, 2.5}, "unit": "s"},
	})
	olderFixture := writeResultFixture(t, map[string]any{
		"run_id":    "history-run-old",
		"timestamp": "2024-01-01T12:00:00Z",
		"github": map[string]any{
			"commit":     "history-commit-01",
			"repository": repo,
		},
		"stats": map[string]any{"data": []any{1.0, 1.5}, "unit": "s"},
	})
	newerID, fingerprint := submitCLIResult(t, srv.URL, newerFixture)
	olderID, _ := submitCLIResult(t, srv.URL, olderFixture)

	var stdout, stderr bytes.Buffer
	code := run([]string{
		"history", "export",
		newerID,
		"--server", srv.URL,
	}, &stdout, &stderr)
	require.Equal(t, 0, code, "exit code; stderr=%s", stderr.String())
	require.Empty(t, stderr.String())

	out := stdout.String()
	assert.Contains(t, out, "# generated by conbench CLI")
	assert.Contains(t, out, "# for result "+newerID)
	assert.Contains(t, out, "# history fingerprint: "+fingerprint)
	lines := strings.Split(strings.TrimSpace(out), "\n")
	var csvLines []string
	for _, line := range lines {
		if strings.HasPrefix(line, "#") {
			continue
		}
		csvLines = append(csvLines, line)
	}
	require.Len(t, csvLines, 3, "CSV lines:\n%s", out)
	assert.Equal(t, "commit_time,result_id,commit_hash,svs,mean,unit,svs_type", csvLines[0])
	assert.Contains(t, csvLines[1], olderID)
	assert.Contains(t, csvLines[1], ",history-commit-01,1,1.25,s,min")
	assert.Contains(t, csvLines[2], newerID)
	assert.Contains(t, csvLines[2], ",history-commit-02,2,2.25,s,min")
}

func nonCommentCSVLines(output string) []string {
	lines := strings.Split(strings.TrimSpace(output), "\n")
	var csvLines []string
	for _, line := range lines {
		if strings.HasPrefix(line, "#") {
			continue
		}
		csvLines = append(csvLines, line)
	}
	return csvLines
}

func TestHistoryExportCommandOutputFile(t *testing.T) {
	srv := newCLITestServer(t)
	resultID, _ := submitCLIResult(t, srv.URL, filepath.Join("testdata", "result.json"))
	output := filepath.Join(t.TempDir(), "history.csv")

	var stdout, stderr bytes.Buffer
	code := run([]string{
		"history", "export",
		resultID,
		"--server", srv.URL,
		"--output", output,
	}, &stdout, &stderr)
	require.Equal(t, 0, code, "exit code; stderr=%s", stderr.String())
	assert.Empty(t, stdout.String(), "stdout should be empty when --output is used")
	require.Empty(t, stderr.String())

	raw, err := os.ReadFile(output)
	require.NoError(t, err)
	assert.Contains(t, string(raw), "commit_time,result_id,commit_hash,svs,mean,unit,svs_type\n")
	assert.Contains(t, string(raw), resultID)
}

func TestCIReportCommandIntegration(t *testing.T) {
	pool, ctx := dbtest.NewPool(t)
	store := db.NewStore(pool)
	srv := httptest.NewServer(server.New(store, auth.New(testToken, false, store, nil), commit.LocalProvider{}, noAuthHandler(), "https://conbench.example"))
	t.Cleanup(srv.Close)
	repo := "https://github.com/conbench/demo"

	for _, fixture := range []string{
		writeResultFixture(t, map[string]any{
			"run_id": "main-run",
			"github": map[string]any{
				"commit":     "c1",
				"repository": repo,
			},
			"timestamp": "2024-01-01T12:00:00Z",
			"stats":     map[string]any{"data": []any{10.0}, "unit": "s"},
		}),
		writeResultFixture(t, map[string]any{
			"run_id": "main-run",
			"github": map[string]any{
				"commit":     "c2",
				"repository": repo,
			},
			"timestamp": "2024-01-02T12:00:00Z",
			"stats":     map[string]any{"data": []any{20.0}, "unit": "s"},
		}),
		writeResultFixture(t, map[string]any{
			"run_id": "explicit-baseline",
			"github": map[string]any{
				"commit":     "c3",
				"repository": repo,
			},
			"timestamp": "2024-01-03T12:00:00Z",
			"stats":     map[string]any{"data": []any{30.0}, "unit": "s"},
		}),
		writeResultFixture(t, map[string]any{
			"run_id": "ci-stable",
			"github": map[string]any{
				"commit":     "c4",
				"repository": repo,
			},
			"timestamp": "2024-01-04T12:00:00Z",
			"stats":     map[string]any{"data": []any{20.0}, "unit": "s"},
		}),
		writeResultFixture(t, map[string]any{
			"run_id": "ci-regressed",
			"github": map[string]any{
				"commit":     "c5",
				"repository": repo,
			},
			"timestamp": "2024-01-04T13:00:00Z",
			"stats":     map[string]any{"data": []any{100.0}, "unit": "s"},
		}),
	} {
		submitCLIResult(t, srv.URL, fixture)
	}
	_, err := pool.Exec(ctx, `UPDATE commit SET parent = $1, fork_point_sha = $2 WHERE repository = $3 AND sha = ANY($4::text[])`,
		"c3", "c3", repo, []string{"c4", "c5"})
	require.NoError(t, err)

	var stableStdout, stableStderr bytes.Buffer
	stableCode := run([]string{
		"ci", "report",
		"--server", srv.URL,
		"--repository", repo,
		"--commit", "c4",
		"--run-ids", "ci-stable",
	}, &stableStdout, &stableStderr)
	require.Equal(t, 0, stableCode, "stderr=%s", stableStderr.String())
	require.Empty(t, stableStderr.String())
	var stableReport struct {
		Status    string `json:"status"`
		ReportURL string `json:"report_url"`
	}
	require.NoError(t, json.Unmarshal(stableStdout.Bytes(), &stableReport))
	assert.Equal(t, "success", stableReport.Status)
	assert.True(t, strings.HasPrefix(stableReport.ReportURL, "https://conbench.example/ci/report?"))

	var failStdout, failStderr bytes.Buffer
	failCode := run([]string{
		"ci", "report",
		"--server", srv.URL,
		"--repository", repo,
		"--commit", "c5",
		"--run-ids", "ci-regressed",
		"--format", "markdown",
	}, &failStdout, &failStderr)
	require.Equal(t, 1, failCode, "stderr=%s", failStderr.String())
	require.Empty(t, failStderr.String())
	assert.Contains(t, failStdout.String(), "Status: failure")
	assert.Contains(t, failStdout.String(), "ci-regressed")

	var explicitStdout, explicitStderr bytes.Buffer
	explicitCode := run([]string{
		"ci", "report",
		"--server", srv.URL,
		"--run-ids", "ci-regressed",
		"--baseline-run-ids", "explicit-baseline",
	}, &explicitStdout, &explicitStderr)
	require.Equal(t, 1, explicitCode, "stderr=%s", explicitStderr.String())
	require.Empty(t, explicitStderr.String())
	var explicitReport struct {
		Baseline  string `json:"baseline"`
		ReportURL string `json:"report_url"`
		Runs      []struct {
			BaselineRunID *string `json:"baseline_run_id"`
		} `json:"runs"`
	}
	require.NoError(t, json.Unmarshal(explicitStdout.Bytes(), &explicitReport))
	assert.Equal(t, "explicit_run", explicitReport.Baseline)
	assert.Contains(t, explicitReport.ReportURL, "baseline_run_ids=explicit-baseline")
	require.Len(t, explicitReport.Runs, 1)
	assert.Equal(t, "explicit-baseline", *explicitReport.Runs[0].BaselineRunID)
}

func TestResultsGetNotFound(t *testing.T) {
	pool, _ := dbtest.NewPool(t)
	store := db.NewStore(pool)
	srv := httptest.NewServer(server.New(store, auth.New(testToken, false, store, nil), commit.LocalProvider{}, noAuthHandler()))
	t.Cleanup(srv.Close)

	var stdout, stderr bytes.Buffer
	code := run([]string{
		"results", "get",
		"missing-result-id",
		"--server", srv.URL,
	}, &stdout, &stderr)

	assert.Equal(t, 1, code)
	assert.Empty(t, stdout.String())
	assert.Contains(t, stderr.String(), "404")
}

func TestSubmitMultiFileIntegration(t *testing.T) {
	pool, _ := dbtest.NewPool(t)
	store := db.NewStore(pool)
	srv := httptest.NewServer(server.New(store, auth.New(testToken, false, store, nil), commit.LocalProvider{}, noAuthHandler()))
	t.Cleanup(srv.Close)

	tempDir := t.TempDir()
	fixtureCopies := map[string]string{
		"a_result.json":   filepath.Join("testdata", "result.json"),
		"b_nullable.json": filepath.Join("testdata", "result_nullable.json"),
	}
	for name, source := range fixtureCopies {
		raw, err := os.ReadFile(source)
		require.NoError(t, err)
		require.NoError(t, os.WriteFile(filepath.Join(tempDir, name), raw, 0o600))
	}
	invalidPath := filepath.Join(tempDir, "0_invalid.json")
	require.NoError(t, os.WriteFile(invalidPath, []byte(`{"run_id":`), 0o600))

	pattern := filepath.Join(tempDir, "*.json")
	matched, err := filepath.Glob(pattern)
	require.NoError(t, err)
	require.Len(t, matched, 3)

	var stdout, stderr bytes.Buffer
	code := run([]string{
		"results", "submit",
		pattern,
		"--server", srv.URL,
		"--token", testToken,
	}, &stdout, &stderr)
	require.Equal(t, 1, code, "exit code; stdout=%s stderr=%s", stdout.String(), stderr.String())
	require.Empty(t, stderr.String(), "stderr must be empty for per-file submit failures")
	assert.NotContains(t, stdout.String(), testToken)
	assert.NotContains(t, stderr.String(), testToken)

	type line struct {
		File               string `json:"file"`
		OK                 bool   `json:"ok"`
		ID                 string `json:"id"`
		HistoryFingerprint string `json:"history_fingerprint"`
		Error              string `json:"error"`
	}
	rawLines := strings.Split(strings.TrimSuffix(stdout.String(), "\n"), "\n")
	require.Len(t, rawLines, len(matched))

	byFile := make(map[string]line, len(rawLines))
	for _, rawLine := range rawLines {
		var got line
		require.NoError(t, json.Unmarshal([]byte(rawLine), &got))
		byFile[got.File] = got
	}
	require.Len(t, byFile, len(matched))
	for _, file := range matched {
		got, ok := byFile[file]
		require.True(t, ok, "missing JSONL result for %s", file)
		if file == invalidPath {
			assert.False(t, got.OK)
			assert.Empty(t, got.ID)
			assert.Empty(t, got.HistoryFingerprint)
			assert.NotEmpty(t, got.Error)
			assert.NotContains(t, got.Error, testToken)
			continue
		}
		assert.True(t, got.OK)
		assert.NotEmpty(t, got.ID, "id for %s", file)
		assert.NotEmpty(t, got.HistoryFingerprint, "history_fingerprint for %s", file)
		assert.Empty(t, got.Error)
	}
}

func TestSubmitPartialFailureDoesNotMasqueradeAsLoginFailure(t *testing.T) {
	assert.NotErrorIs(t, submitPartialFailure{}, errLoginFailed)
}

// TestSubmitRejectsBadAuth checks the CLI surfaces a server rejection as a
// non-zero exit with the problem detail on stderr and nothing on stdout.
func TestSubmitRejectsBadAuth(t *testing.T) {
	pool, _ := dbtest.NewPool(t)
	store := db.NewStore(pool)
	srv := httptest.NewServer(server.New(store, auth.New(testToken, false, store, nil), commit.LocalProvider{}, noAuthHandler()))
	t.Cleanup(srv.Close)

	var stdout, stderr bytes.Buffer
	code := run([]string{
		"results", "submit",
		filepath.Join("testdata", "result.json"),
		"--server", srv.URL,
		"--token", "wrong-token",
	}, &stdout, &stderr)
	require.Equal(t, 1, code)
	assert.Empty(t, stdout.String(), "no stdout on failure")
	assert.Contains(t, stderr.String(), "401")
}

func newCLITestServer(t *testing.T) *httptest.Server {
	t.Helper()
	pool, _ := dbtest.NewPool(t)
	store := db.NewStore(pool)
	srv := httptest.NewServer(server.New(store, auth.New(testToken, false, store, nil), commit.LocalProvider{}, noAuthHandler()))
	t.Cleanup(srv.Close)
	return srv
}

func submitCLIResult(t *testing.T, serverURL, fixture string) (string, string) {
	t.Helper()
	var stdout, stderr bytes.Buffer
	code := run([]string{
		"results", "submit",
		fixture,
		"--server", serverURL,
		"--token", testToken,
	}, &stdout, &stderr)
	require.Equal(t, 0, code, "exit code; stderr=%s", stderr.String())
	require.Empty(t, stderr.String(), "stderr must be empty on submit success")

	var submitted struct {
		ID                 string `json:"id"`
		HistoryFingerprint string `json:"history_fingerprint"`
	}
	require.NoError(t, json.Unmarshal(stdout.Bytes(), &submitted))
	require.NotEmpty(t, submitted.ID)
	require.NotEmpty(t, submitted.HistoryFingerprint)
	return submitted.ID, submitted.HistoryFingerprint
}

func writeResultFixture(t *testing.T, overrides map[string]any) string {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join("testdata", "result.json"))
	require.NoError(t, err)
	var body map[string]any
	require.NoError(t, json.Unmarshal(raw, &body))
	maps.Copy(body, overrides)
	encoded, err := json.MarshalIndent(body, "", "  ")
	require.NoError(t, err)
	path := filepath.Join(t.TempDir(), "result.json")
	require.NoError(t, os.WriteFile(path, encoded, 0o600))
	return path
}

type seriesListItem struct {
	HistoryFingerprint string `json:"history_fingerprint"`
}

func seriesFingerprints(series []seriesListItem) []string {
	fingerprints := make([]string, 0, len(series))
	for _, item := range series {
		fingerprints = append(fingerprints, item.HistoryFingerprint)
	}
	return fingerprints
}
