package prodclone

import (
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestRunProfileCollectsHTTPSQLPlansAndRelationSizes(t *testing.T) {
	t.Parallel()

	var paths []string
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		paths = append(paths, r.URL.RequestURI())
		if r.URL.Path == "/api/ci/report" {
			query := r.URL.Query()
			assert.Equal(t, "https://github.com/conbench/prod-sample", query.Get("repository"))
			assert.Equal(t, "sha-recent", query.Get("commit_sha"))
			assert.Equal(t, "sample-run", query.Get("run_ids"))
		}
		w.WriteHeader(http.StatusOK)
		_, err := w.Write([]byte(`{"ok":true}`))
		assert.NoError(t, err)
	}))
	defer server.Close()
	db := &fakeProfileDB{}

	result, err := RunProfile(context.Background(), ProfileConfig{
		ServerURL: server.URL,
		Samples:   validProfileManifest(),
		DB:        db,
		WarmRuns:  1,
	})

	require.NoError(t, err)
	assert.NotEmpty(t, paths)
	assert.Contains(t, paths, "/api/series?page_size=5")
	assert.Contains(t, paths, "/api/series?page_size=10")
	assert.Contains(t, paths, "/api/series?page_size=50")
	assert.Contains(t, paths, "/api/series?page_size=10&q=BM_ReadBinaryColumn")
	assert.Contains(t, paths, "/api/series?page_size=10&q=tpch")
	assert.Contains(t, paths, "/api/ci/report?commit_sha=sha-recent&repository=https%3A%2F%2Fgithub.com%2Fconbench%2Fprod-sample&run_ids=sample-run")
	assert.NotEmpty(t, result.HTTPTimings)
	assert.Contains(t, profileHTTPNames(result.HTTPTimings), "SeriesBrowseDefaultPage5 cold")
	assert.Contains(t, profileHTTPNames(result.HTTPTimings), "SeriesBrowseDefaultPage50 cold")
	assert.Contains(t, profileHTTPNames(result.HTTPTimings), "SeriesBrowseQBroad cold")
	assert.Contains(t, profileHTTPNames(result.HTTPTimings), "SeriesBrowseDefaultPage5 warm-1")
	assert.Contains(t, profileHTTPNames(result.HTTPTimings), "CIReportByCommitRun cold")
	assert.Contains(t, profileHTTPNames(result.HTTPTimings), "CIReportByCommitRun warm-1")
	assert.NotEmpty(t, result.SQLTimings)
	assert.Contains(t, profileSQLNames(result.SQLTimings), "SeriesBrowseDefaultPage5")
	assert.Contains(t, profileSQLNames(result.SQLTimings), "SeriesBrowseDefaultPage50")
	assert.Contains(t, profileSQLNames(result.SQLTimings), "SeriesMembersForPage50")
	assert.Contains(t, profileSQLNames(result.SQLTimings), "SeriesQBroadCaseMatches")
	assert.Contains(t, profileSQLNames(result.SQLTimings), "SeriesQBroadRecentMembers")
	assert.NotContains(t, profileSQLNames(result.SQLTimings), "SeriesQBroadFilteredMembers")
	assert.Contains(t, profileSQLNames(result.SQLTimings), "RelationSizes")
	require.NotEmpty(t, result.Plans)
	for _, plan := range result.Plans {
		assert.NotContains(t, plan.Filename, "/")
		assert.True(t, strings.HasSuffix(plan.Filename, ".json"))
		assert.JSONEq(t, `[{"Plan":{"Node Type":"Result"}}]`, string(plan.PlanJSON))
	}
	require.NotEmpty(t, result.RelationSizes)
	assert.Equal(t, "public.benchmark_result", result.RelationSizes[0].Table)
	assert.Positive(t, db.explainCount)
}

func TestRunProfileRecordsHTTPFailures(t *testing.T) {
	t.Parallel()

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
	}))
	defer server.Close()

	result, err := RunProfile(context.Background(), ProfileConfig{
		ServerURL: server.URL,
		Samples:   validProfileManifest(),
		DB:        &fakeProfileDB{},
		WarmRuns:  1,
	})

	require.Error(t, err)
	assert.NotEmpty(t, result.HTTPTimings)
	assert.False(t, result.HTTPTimings[0].Passed)
	assert.Contains(t, result.HTTPTimings[0].Error, "expected 200")
}

func TestRunProfileRequiresCoreSamples(t *testing.T) {
	t.Parallel()

	_, err := RunProfile(context.Background(), ProfileConfig{
		ServerURL: "http://127.0.0.1:1",
		Samples:   SampleManifest{},
		DB:        &fakeProfileDB{},
	})

	require.Error(t, err)
	assert.Contains(t, err.Error(), "recent_result.result_id")
}

func TestSelectProfileSamplesUsesHistoryMemberWhenMetadataCategoriesAreMissing(t *testing.T) {
	t.Parallel()

	samples, err := selectProfileSamples(SampleManifest{
		Categories: map[string]SampleCategory{
			sampleCategoryRecentResult:  {ResultID: "result-recent", HistoryFingerprint: "fp-recent"},
			sampleCategoryHistoryMember: {ResultID: "result-history", HistoryFingerprint: "fp-history"},
		},
	})

	require.NoError(t, err)
	assert.Equal(t, "result-recent", samples.recentResultID)
	assert.Equal(t, "fp-history", samples.longFingerprint)
	assert.Equal(t, "fp-history", samples.shortFingerprint)
	assert.False(t, samples.haveCIReport)
	assert.NotContains(t, profileHTTPCallNames(profileHTTPCalls(samples)), "CIReportByCommitRun")
}

func TestExplainPlanFilenameIsPathSafe(t *testing.T) {
	t.Parallel()

	assert.Equal(t, "series-browse-default.json", ExplainPlanFilename("Series Browse Default"))
	assert.Equal(t, "plan.json", ExplainPlanFilename("../"))
	assert.Equal(t, "compare-history-as-of.json", ExplainPlanFilename("Compare/History: As Of"))
}

func validProfileManifest() SampleManifest {
	return SampleManifest{
		Categories: map[string]SampleCategory{
			sampleCategoryRecentResult: {ResultID: "result-recent", HistoryFingerprint: "fp-long", PointCount: 12},
			sampleCategoryOldResult:    {ResultID: "result-old", HistoryFingerprint: "fp-long", PointCount: 12},
			sampleCategoryLongHistory:  {ResultID: "result-recent", HistoryFingerprint: "fp-long", PointCount: 12},
			sampleCategoryShortHistory: {ResultID: "result-recent", HistoryFingerprint: "fp-short", PointCount: 2},
		},
		Compare: &CompareSample{
			BaselineResultID:   "baseline-result",
			ContenderResultID:  "contender-result",
			HistoryFingerprint: "fp-long",
		},
		CIReport: &CIReportSample{
			Repository:         "https://github.com/conbench/prod-sample",
			CommitSHA:          "sha-recent",
			RunIDs:             []string{"sample-run"},
			ResultID:           "result-recent",
			HistoryFingerprint: "fp-long",
		},
	}
}

func profileHTTPNames(timings []HTTPProbeTiming) []string {
	names := make([]string, 0, len(timings))
	for _, timing := range timings {
		names = append(names, timing.Name)
	}
	return names
}

func profileSQLNames(timings []SQLProfileTiming) []string {
	names := make([]string, 0, len(timings))
	for _, timing := range timings {
		names = append(names, timing.Name)
	}
	return names
}

func profileHTTPCallNames(calls []profileHTTPCall) []string {
	names := make([]string, 0, len(calls))
	for _, call := range calls {
		names = append(names, call.name)
	}
	return names
}

type fakeProfileDB struct {
	explainCount int
}

func (db *fakeProfileDB) Query(_ context.Context, sql string, _ ...any) (pgx.Rows, error) {
	trimmed := strings.TrimSpace(sql)
	switch {
	case strings.HasPrefix(trimmed, "EXPLAIN"):
		db.explainCount++
		return &fakeRows{rows: [][]any{{[]byte(`[{"Plan":{"Node Type":"Result"}}]`)}}}, nil
	case strings.Contains(trimmed, "pg_total_relation_size"):
		return &fakeRows{rows: [][]any{
			{"public.benchmark_result", int64(1000), int64(600), int64(400)},
			{"public.commit", int64(500), int64(300), int64(200)},
		}}, nil
	default:
		return &fakeRows{rows: [][]any{{"row-1"}, {"row-2"}}}, nil
	}
}

type fakeRows struct {
	rows   [][]any
	index  int
	closed bool
	err    error
}

func (r *fakeRows) Close() {
	r.closed = true
}

func (r *fakeRows) Err() error {
	return r.err
}

func (r *fakeRows) CommandTag() pgconn.CommandTag {
	return pgconn.CommandTag{}
}

func (r *fakeRows) FieldDescriptions() []pgconn.FieldDescription {
	return nil
}

func (r *fakeRows) Next() bool {
	if r.index >= len(r.rows) {
		return false
	}
	r.index++
	return true
}

func (r *fakeRows) Scan(dest ...any) error {
	if r.index == 0 || r.index > len(r.rows) {
		return errors.New("scan called without current row")
	}
	row := r.rows[r.index-1]
	if len(dest) != len(row) {
		return errors.New("scan destination count mismatch")
	}
	for i, value := range row {
		switch ptr := dest[i].(type) {
		case *[]byte:
			v, ok := value.([]byte)
			if !ok {
				return errors.New("scan []byte type mismatch")
			}
			*ptr = v
		case *string:
			v, ok := value.(string)
			if !ok {
				return errors.New("scan string type mismatch")
			}
			*ptr = v
		case *int64:
			v, ok := value.(int64)
			if !ok {
				return errors.New("scan int64 type mismatch")
			}
			*ptr = v
		default:
			return errors.New("unsupported scan destination")
		}
	}
	return nil
}

func (r *fakeRows) Values() ([]any, error) {
	if r.index == 0 || r.index > len(r.rows) {
		return nil, errors.New("values called without current row")
	}
	return r.rows[r.index-1], nil
}

func (r *fakeRows) RawValues() [][]byte {
	return nil
}

func (r *fakeRows) Conn() *pgx.Conn {
	return nil
}
