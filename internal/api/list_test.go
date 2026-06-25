package api_test

import (
	"encoding/json"
	"net/http"
	"net/url"
	"testing"
	"time"

	"github.com/danielgtaylor/huma/v2/humatest"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/conbench/conbench/internal/service"
)

func listResults(t *testing.T, tapi humatest.TestAPI, query string) service.ResultPage {
	t.Helper()
	resp := tapi.Get("/api/benchmark-results" + query)
	require.Equal(t, http.StatusOK, resp.Code, "list: %s", resp.Body.String())
	var page service.ResultPage
	require.NoError(t, json.Unmarshal(resp.Body.Bytes(), &page))
	return page
}

func TestListResultsOrderingAndFields(t *testing.T) {
	tapi, _, _ := seedAPI(t)
	a := seedResult(t, tapi, seedOpts{sha: "c1", ts: day(1), data: []float64{10}})
	_ = a
	b := seedResult(t, tapi, seedOpts{sha: "c2", ts: day(2), data: []float64{20}})

	page := listResults(t, tapi, "")
	require.Len(t, page.Results, 2)
	// id DESC: the most-recently inserted (b) is first.
	assert.Equal(t, b, page.Results[0].ID)
	first := page.Results[0]
	assert.Equal(t, "run-1", first.RunID)
	assert.Equal(t, "bench", first.CaseName)
	assert.Equal(t, map[string]any{"source": "test"}, first.CaseTags)
	require.NotNil(t, first.Unit)
	assert.Equal(t, "s", *first.Unit)
	require.NotNil(t, first.SVS)
	assert.InDelta(t, 20.0, *first.SVS, 1e-9)
	assert.Equal(t, "min", first.SVSType)
	assert.False(t, first.HasError)
	require.NotNil(t, first.Commit)
	assert.Equal(t, "c2", first.Commit.Hash)
	assert.Nil(t, page.NextPageCursor, "non-full page has no next cursor")
}

func TestListResultsRunIDFilter(t *testing.T) {
	tapi, _, _ := seedAPI(t)
	seedResult(t, tapi, seedOpts{sha: "c1", ts: day(1), data: []float64{10}, runID: "run-a"})
	want := seedResult(t, tapi, seedOpts{
		sha:       "c2",
		ts:        day(2),
		data:      []float64{20},
		runID:     "run-b",
		runReason: "pull-request",
	})

	page := listResults(t, tapi, "?run_id=run-b")
	require.Len(t, page.Results, 1)
	assert.Equal(t, want, page.Results[0].ID)

	resp := tapi.Get("/api/benchmark-results?run_id=run-b")
	require.Equal(t, http.StatusOK, resp.Code, "list: %s", resp.Body.String())
	var raw struct {
		Results []map[string]any `json:"results"`
	}
	require.NoError(t, json.Unmarshal(resp.Body.Bytes(), &raw))
	require.Len(t, raw.Results, 1)
	assert.Equal(t, "pull-request", raw.Results[0]["run_reason"])
}

func TestListResultsBatchIDFilter(t *testing.T) {
	tapi, _, _ := seedAPI(t)
	seedResult(t, tapi, seedOpts{sha: "c1", ts: day(1), data: []float64{10}, batchID: "batch-a"})
	want := seedResult(t, tapi, seedOpts{sha: "c2", ts: day(2), data: []float64{20}, batchID: "batch-b"})

	page := listResults(t, tapi, "?batch_id=batch-b")
	require.Len(t, page.Results, 1)
	assert.Equal(t, want, page.Results[0].ID)

	resp := tapi.Get("/api/benchmark-results?batch_id=batch-b")
	require.Equal(t, http.StatusOK, resp.Code, "list: %s", resp.Body.String())
	var raw struct {
		Results []map[string]any `json:"results"`
	}
	require.NoError(t, json.Unmarshal(resp.Body.Bytes(), &raw))
	require.Len(t, raw.Results, 1)
	assert.Equal(t, "batch-b", raw.Results[0]["batch_id"])
}

func TestListResultsCursorPagination(t *testing.T) {
	tapi, _, _ := seedAPI(t)
	ids := make([]string, 0, 3)
	for i := range 3 {
		ids = append(ids, seedResult(t, tapi, seedOpts{sha: shaN(i), ts: day(i), data: []float64{float64(i + 1)}}))
	}
	// Newest-first: ids[2], ids[1], ids[0].
	page1 := listResults(t, tapi, "?page_size=2")
	require.Len(t, page1.Results, 2)
	assert.Equal(t, []string{ids[2], ids[1]}, []string{page1.Results[0].ID, page1.Results[1].ID})
	require.NotNil(t, page1.NextPageCursor, "full page returns a cursor")
	assert.Equal(t, ids[1], *page1.NextPageCursor)

	page2 := listResults(t, tapi, "?page_size=2&cursor="+*page1.NextPageCursor)
	require.Len(t, page2.Results, 1)
	assert.Equal(t, ids[0], page2.Results[0].ID)
	assert.Nil(t, page2.NextPageCursor, "final partial page has no cursor")
}

func TestListResultsEmptyFinalPage(t *testing.T) {
	tapi, _, _ := seedAPI(t)
	ids := []string{
		seedResult(t, tapi, seedOpts{sha: "c1", ts: day(1), data: []float64{1}}),
		seedResult(t, tapi, seedOpts{sha: "c2", ts: day(2), data: []float64{2}}),
	}
	// Exactly page_size rows => a cursor is returned even though no rows remain.
	page1 := listResults(t, tapi, "?page_size=2")
	require.Len(t, page1.Results, 2)
	require.NotNil(t, page1.NextPageCursor)
	assert.Equal(t, ids[0], *page1.NextPageCursor)
	page2 := listResults(t, tapi, "?page_size=2&cursor="+*page1.NextPageCursor)
	assert.Empty(t, page2.Results, "one empty final page is acceptable")
	assert.Nil(t, page2.NextPageCursor)
}

func TestListResultsBadTimestampIs422(t *testing.T) {
	tapi, _, _ := seedAPI(t)
	resp := tapi.Get("/api/benchmark-results?earliest_timestamp=not-a-date")
	require.Equal(t, http.StatusUnprocessableEntity, resp.Code, "body %s", resp.Body.String())
}

func TestListResultsTimestampFilterUTCNormalized(t *testing.T) {
	tapi, _, _ := seedAPI(t)
	// Result at exactly 2026-01-01T00:00:00Z (day(0)).
	id := seedResult(t, tapi, seedOpts{sha: "c1", ts: day(0), data: []float64{10}})
	// earliest = 2026-01-01T04:00:00+05:00 == 2025-12-31T23:00:00Z, which is BEFORE
	// the result (00:00Z Jan 1), so the result must be included. Without .UTC(), the
	// naive wall-clock 04:00 would be AFTER 00:00 and wrongly exclude it.
	page := listResults(t, tapi, "?earliest_timestamp=2026-01-01T04:00:00%2B05:00")
	require.Len(t, page.Results, 1, "UTC-normalized lower bound must include the result")
	assert.Equal(t, id, page.Results[0].ID)
}

func TestListRecentRunsGroupsResultsByRun(t *testing.T) {
	tapi, pool, ctx := seedAPI(t)
	olderA := seedResult(t, tapi, seedOpts{
		sha:       "c1",
		ts:        day(1),
		data:      []float64{10},
		runID:     "run-a",
		runReason: "nightly",
		batchID:   "batch-a",
		name:      "bench-a",
	})
	newerA := seedResult(t, tapi, seedOpts{
		sha:       "c2",
		ts:        day(3),
		data:      []float64{20},
		runID:     "run-a",
		runReason: "nightly",
		batchID:   "batch-c",
		name:      "bench-b",
	})
	_ = olderA
	latestB := seedResult(t, tapi, seedOpts{
		sha:       "c3",
		ts:        day(2),
		data:      []float64{30},
		runID:     "run-b",
		runReason: "pull-request",
		batchID:   "batch-b",
		name:      "bench-c",
		repo:      "https://github.com/org/other",
	})
	authorLogin := "contributor-a"
	authorAvatar := "https://avatars.githubusercontent.com/u/12345?v=4"
	_, err := pool.Exec(ctx, `
		UPDATE commit
		SET message = $1, author_name = $2, author_login = $3, author_avatar = $4
		WHERE repository = $5 AND sha = $6
	`, "Improve vector kernels", "Contributor A", authorLogin, authorAvatar, defaultRepo, "c2")
	require.NoError(t, err)

	resp := tapi.Get("/api/runs/recent?page_size=10")
	require.Equal(t, http.StatusOK, resp.Code, "recent runs: %s", resp.Body.String())

	var page struct {
		Runs []struct {
			RunID         string  `json:"run_id"`
			RunReason     *string `json:"run_reason"`
			ResultCount   int     `json:"result_count"`
			ErrorCount    int     `json:"error_count"`
			SeriesCount   int     `json:"series_count"`
			BatchCount    int     `json:"batch_count"`
			LatestBatchID *string `json:"latest_batch_id"`
			LatestResult  string  `json:"latest_result_id"`
			Repository    string  `json:"repository"`
			CommitSHA     string  `json:"commit_sha"`
			Commit        struct {
				Hash         string  `json:"hash"`
				Repository   string  `json:"repository"`
				Message      string  `json:"message"`
				AuthorName   string  `json:"author_name"`
				AuthorLogin  *string `json:"author_login"`
				AuthorAvatar *string `json:"author_avatar"`
			} `json:"commit"`
			FirstResultAt string `json:"first_result_at"`
			LastResultAt  string `json:"last_result_at"`
		} `json:"runs"`
	}
	require.NoError(t, json.Unmarshal(resp.Body.Bytes(), &page))
	require.Len(t, page.Runs, 2)
	var raw map[string][]map[string]any
	require.NoError(t, json.Unmarshal(resp.Body.Bytes(), &raw))
	require.NotContains(t, raw["runs"][0], "batch_ids", "recent runs must not return an unbounded batch id list")

	assert.Equal(t, "run-a", page.Runs[0].RunID)
	assert.Equal(t, "nightly", *page.Runs[0].RunReason)
	assert.Equal(t, 2, page.Runs[0].ResultCount)
	assert.Equal(t, 0, page.Runs[0].ErrorCount)
	assert.Equal(t, 2, page.Runs[0].SeriesCount)
	assert.Equal(t, 2, page.Runs[0].BatchCount)
	assert.Equal(t, "batch-c", *page.Runs[0].LatestBatchID)
	assert.Equal(t, newerA, page.Runs[0].LatestResult)
	assert.Equal(t, defaultRepo, page.Runs[0].Repository)
	assert.Equal(t, "c2", page.Runs[0].CommitSHA)
	assert.Equal(t, day(1).Format(time.RFC3339), page.Runs[0].FirstResultAt)
	assert.Equal(t, day(3).Format(time.RFC3339), page.Runs[0].LastResultAt)

	assert.Equal(t, "run-b", page.Runs[1].RunID)
	assert.Equal(t, latestB, page.Runs[1].LatestResult)
	assert.Equal(t, "https://github.com/org/other", page.Runs[1].Repository)
	assert.Equal(t, "c2", page.Runs[0].Commit.Hash)
	assert.Equal(t, defaultRepo, page.Runs[0].Commit.Repository)
	assert.Equal(t, "Improve vector kernels", page.Runs[0].Commit.Message)
	assert.Equal(t, "Contributor A", page.Runs[0].Commit.AuthorName)
	if assert.NotNil(t, page.Runs[0].Commit.AuthorLogin) {
		assert.Equal(t, authorLogin, *page.Runs[0].Commit.AuthorLogin)
	}
	if assert.NotNil(t, page.Runs[0].Commit.AuthorAvatar) {
		assert.Equal(t, authorAvatar, *page.Runs[0].Commit.AuthorAvatar)
	}
}

func TestListRecentRunsCanIncludeActionableAttention(t *testing.T) {
	tapi, pool, ctx := seedAPI(t)
	seedResult(t, tapi, seedOpts{runID: "main-run", sha: "c1", ts: day(1), data: []float64{10}})
	seedResult(t, tapi, seedOpts{runID: "main-run", sha: "c2", ts: day(2), data: []float64{20}})
	seedResult(t, tapi, seedOpts{runID: "main-run", sha: "c3", ts: day(3), data: []float64{30}})
	seedResult(t, tapi, seedOpts{runID: "ci-run", runReason: "pull request", sha: "c4", ts: day(4), data: []float64{100}})

	_, err := pool.Exec(ctx, `UPDATE commit SET parent = $1, fork_point_sha = $2 WHERE repository = $3 AND sha = $4`,
		"c3", "c3", defaultRepo, "c4")
	require.NoError(t, err)

	resp := tapi.Get("/api/runs/recent?page_size=10")
	require.Equal(t, http.StatusOK, resp.Code, "recent runs: %s", resp.Body.String())
	var raw map[string][]map[string]any
	require.NoError(t, json.Unmarshal(resp.Body.Bytes(), &raw))
	require.NotContains(t, raw["runs"][0], "attention", "attention is opt-in for the home dashboard")

	resp = tapi.Get("/api/runs/recent?page_size=10&include_attention=true")
	require.Equal(t, http.StatusOK, resp.Code, "recent runs with attention: %s", resp.Body.String())
	var page struct {
		Runs []struct {
			RunID     string `json:"run_id"`
			Attention *struct {
				Status       string `json:"status"`
				StatusReason string `json:"status_reason"`
				ReportURL    string `json:"report_url"`
				Summary      struct {
					Compared        int `json:"compared"`
					Regressions     int `json:"regressions"`
					BenchmarkErrors int `json:"benchmark_errors"`
				} `json:"summary"`
			} `json:"attention"`
		} `json:"runs"`
	}
	require.NoError(t, json.Unmarshal(resp.Body.Bytes(), &page))
	require.Len(t, page.Runs, 2)
	assert.Equal(t, "ci-run", page.Runs[0].RunID)
	if assert.NotNil(t, page.Runs[0].Attention) {
		assert.Equal(t, "failure", page.Runs[0].Attention.Status)
		assert.Equal(t, "lookback regression detected", page.Runs[0].Attention.StatusReason)
		assert.Equal(t, 1, page.Runs[0].Attention.Summary.Compared)
		assert.Equal(t, 1, page.Runs[0].Attention.Summary.Regressions)
		assert.Equal(t, 0, page.Runs[0].Attention.Summary.BenchmarkErrors)
		u, err := url.Parse(page.Runs[0].Attention.ReportURL)
		require.NoError(t, err)
		assert.Equal(t, "/ci/report", u.Path)
		assert.Equal(t, "ci-run", u.Query().Get("run_ids"))
		assert.Equal(t, "fork_point", u.Query().Get("baseline"))
	}
	assert.Equal(t, "main-run", page.Runs[1].RunID)
	assert.Nil(t, page.Runs[1].Attention, "default-branch runs are not actionable CI attention")
}
