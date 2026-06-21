package prodclone

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/conbench/conbench/internal/db"
	"github.com/conbench/conbench/internal/dbtest"
	"github.com/conbench/conbench/internal/service"
	"github.com/conbench/conbench/internal/storage"
)

func TestSampleManifestJSONSerializesRepresentativeFields(t *testing.T) {
	generatedAt := time.Date(2026, 6, 15, 12, 30, 0, 0, time.UTC)
	manifest := SampleManifest{
		GeneratedAt: generatedAt,
		Categories: map[string]SampleCategory{
			"long_history": {
				ResultID:           "result-long",
				HistoryFingerprint: "fingerprint-long",
				PointCount:         42,
				Note:               "bounded candidate pool",
			},
		},
		Warnings: []string{"sample category errored_result was not found"},
		Compare: &CompareSample{
			BaselineResultID:   "baseline-result",
			ContenderResultID:  "contender-result",
			HistoryFingerprint: "fingerprint-long",
		},
		CIReport: &CIReportSample{
			Repository:         "https://github.com/conbench/prod-sample",
			CommitSHA:          "sha-recent",
			RunIDs:             []string{"sample-run"},
			ResultID:           "result-recent",
			HistoryFingerprint: "fingerprint-recent",
		},
	}

	data, err := json.Marshal(manifest)
	require.NoError(t, err)
	assert.NotContains(t, string(data), "data")
	assert.NotContains(t, string(data), "times")

	var got SampleManifest
	require.NoError(t, json.Unmarshal(data, &got))
	assert.True(t, got.GeneratedAt.Equal(generatedAt))
	assert.Equal(t, "result-long", got.Categories["long_history"].ResultID)
	assert.Equal(t, "fingerprint-long", got.Categories["long_history"].HistoryFingerprint)
	assert.Equal(t, int64(42), got.Categories["long_history"].PointCount)
	assert.Equal(t, []string{"sample category errored_result was not found"}, got.Warnings)
	require.NotNil(t, got.Compare)
	assert.Equal(t, "baseline-result", got.Compare.BaselineResultID)
	assert.Equal(t, "contender-result", got.Compare.ContenderResultID)
	assert.Equal(t, "fingerprint-long", got.Compare.HistoryFingerprint)
	require.NotNil(t, got.CIReport)
	assert.Equal(t, "https://github.com/conbench/prod-sample", got.CIReport.Repository)
	assert.Equal(t, "sha-recent", got.CIReport.CommitSHA)
	assert.Equal(t, []string{"sample-run"}, got.CIReport.RunIDs)
	assert.Equal(t, "result-recent", got.CIReport.ResultID)
	assert.Equal(t, "fingerprint-recent", got.CIReport.HistoryFingerprint)
}

func TestSampleCandidateQueriesAreBoundedAndAvoidGlobalAggregates(t *testing.T) {
	sources := append([]sampleCandidateSourceQuery(nil), sampleCandidateSourceQueries...)
	sources = append(sources, sampleCandidateSourceQuery{name: "ci_report", query: sampleCIReportSQL})
	require.NotEmpty(t, sources)
	for _, source := range sources {
		query := strings.ToUpper(source.query)
		assert.Contains(t, query, "LIMIT", source.name)
		assert.NotContains(t, query, "GROUP BY", source.name)
		assert.NotContains(t, query, "COUNT(*)", source.name)
		assert.NotContains(t, query, "MAX_PARALLEL_WORKERS_PER_GATHER", source.name)
	}
}

func TestSelectSampleManifestWarnsWhenOptionalCategoriesAreMissing(t *testing.T) {
	pool, ctx := dbtest.NewPool(t)
	generatedAt := time.Date(2026, 6, 15, 13, 0, 0, 0, time.UTC)

	manifest, err := SelectSampleManifest(ctx, pool, generatedAt)

	require.NoError(t, err)
	assert.True(t, manifest.GeneratedAt.Equal(generatedAt))
	assert.Empty(t, manifest.Categories)
	assert.Nil(t, manifest.Compare)
	assert.Nil(t, manifest.CIReport)
	assert.Contains(t, manifest.Warnings, "sample category long_history was not found")
	assert.Contains(t, manifest.Warnings, "sample category high_volume_series was not found")
	assert.Contains(t, manifest.Warnings, "compare sample was not found for long_history")
	assert.Contains(t, manifest.Warnings, "ci_report sample was not found")
}

func TestSelectSampleManifestFindsAllRepresentativeCategories(t *testing.T) {
	pool, ctx := dbtest.NewPool(t)
	store := db.NewStore(pool)
	fixture := seedSampleFixture(t, ctx, pool, store)
	generatedAt := time.Date(2026, 6, 15, 13, 30, 0, 0, time.UTC)

	manifest, err := SelectSampleManifest(ctx, pool, generatedAt)

	require.NoError(t, err)
	assert.True(t, manifest.GeneratedAt.Equal(generatedAt))
	assert.Empty(t, manifest.Warnings)

	assertCategory(t, manifest, "long_history", fixture.longNewestID, "fp-volume", 6)
	assertCategory(t, manifest, "short_history", fixture.shortResultID, "fp-000-short", 1)
	assertCategory(t, manifest, "recent_result", fixture.recentResultID, "fp-recent", 0)
	assertCategory(t, manifest, "old_result", fixture.oldResultID, "fp-old", 0)
	assertCategory(t, manifest, "errored_result", fixture.erroredResultID, "fp-volume", 0)
	assertCategory(t, manifest, "with_commit", fixture.recentResultID, "fp-recent", 0)
	assertCategory(t, manifest, "missing_commit", fixture.missingCommitID, "fp-missing-commit", 0)
	assertCategory(t, manifest, "mixed_unit", fixture.mixedNewestID, "fp-mixed-unit", 2)
	assertCategory(t, manifest, "high_volume_series", fixture.highVolumeNewestID, "fp-volume", 6)

	require.NotNil(t, manifest.Compare)
	assert.Equal(t, fixture.compareBaselineID, manifest.Compare.BaselineResultID)
	assert.Equal(t, fixture.compareContenderID, manifest.Compare.ContenderResultID)
	assert.Equal(t, "fp-volume", manifest.Compare.HistoryFingerprint)
	require.NotNil(t, manifest.CIReport)
	assert.Equal(t, "https://github.com/conbench/prod-sample", manifest.CIReport.Repository)
	assert.Equal(t, "sha-recent", manifest.CIReport.CommitSHA)
	assert.Equal(t, []string{"sample-run"}, manifest.CIReport.RunIDs)
	assert.Equal(t, fixture.recentResultID, manifest.CIReport.ResultID)
	assert.Equal(t, "fp-recent", manifest.CIReport.HistoryFingerprint)

	compare, err := service.NewReader(store).Compare(ctx, manifest.Compare.BaselineResultID, manifest.Compare.ContenderResultID, 5, 5)
	require.NoError(t, err, "manifest compare pair must be accepted by the compare service")
	assert.Equal(t, "s", compare.Unit)
}

func TestSelectSampleManifestContinuesAfterOptionalSourceTimeoutInReadOnlyTransaction(t *testing.T) {
	pool, ctx := dbtest.NewPool(t)
	store := db.NewStore(pool)
	seedSampleFixture(t, ctx, pool, store)

	oldSources := sampleCandidateSourceQueries
	sampleCandidateSourceQueries = []sampleCandidateSourceQuery{
		{name: "forced_timeout", query: `
SELECT
	'timeout-result'::text,
	'fp-timeout'::text,
	now(),
	's'::text,
	NULL::text,
	false,
	true,
	false
FROM pg_sleep(2)
LIMIT $1`},
		{name: "recent_id", query: sampleCandidatesRecentIDSQL},
	}
	t.Cleanup(func() {
		sampleCandidateSourceQueries = oldSources
	})

	tx, err := pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadOnly})
	require.NoError(t, err)
	t.Cleanup(func() {
		require.NoError(t, tx.Rollback(ctx))
	})
	_, err = tx.Exec(ctx, `SET LOCAL statement_timeout = '500ms'`)
	require.NoError(t, err)

	manifest, err := SelectSampleManifest(ctx, tx, sampleDay(20))

	require.NoError(t, err)
	assert.NotEmpty(t, manifest.Categories)
	assert.Contains(t, manifest.Warnings[0], "sample candidate source forced_timeout failed")
}

func TestSelectSampleManifestFallsBackWhenMetadataTimeoutsInReadOnlyTransaction(t *testing.T) {
	pool, ctx := dbtest.NewPool(t)
	store := db.NewStore(pool)
	seedSampleFixture(t, ctx, pool, store)

	tx, err := pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadOnly})
	require.NoError(t, err)
	t.Cleanup(func() {
		require.NoError(t, tx.Rollback(ctx))
	})
	_, err = tx.Exec(ctx, `SET LOCAL statement_timeout = '500ms'`)
	require.NoError(t, err)
	queryer := &metadataTimeoutQueryer{inner: tx}

	manifest, err := SelectSampleManifest(ctx, queryer, sampleDay(20))

	require.NoError(t, err)
	assert.True(t, queryer.timeoutTriggered)
	assert.Contains(t, strings.Join(manifest.Warnings, "\n"), "sample metadata query failed")
	historyMember, ok := manifest.Categories["history_member"]
	require.True(t, ok)
	assert.NotEmpty(t, historyMember.ResultID)
	assert.NotEmpty(t, historyMember.HistoryFingerprint)
	assert.NotEmpty(t, historyMember.Note)
	require.NotNil(t, manifest.Compare)

	compare, err := service.NewReader(store).Compare(ctx, manifest.Compare.BaselineResultID, manifest.Compare.ContenderResultID, 5, 5)
	require.NoError(t, err, "metadata fallback compare pair must be accepted by the compare service")
	assert.NotEmpty(t, compare.Unit)
}

func TestSelectSampleManifestFindsErroredAndCommittedCategoriesOutsideCandidateEdges(t *testing.T) {
	pool, ctx := dbtest.NewPool(t)
	store := db.NewStore(pool)
	seeder := newSampleSeeder(t, ctx, pool, store, "hidden-errored-committed")
	unitSeconds := "s"

	for i := range int(sampleCandidateLimit) + 1 {
		id := seeder.result(sampleResultParams{
			fingerprint: fmt.Sprintf("fp-old-missing-commit-%03d", i),
			ts:          sampleDay(i),
			unit:        &unitSeconds,
			data:        denseData(float64(i)),
		})
		rewriteResultID(t, ctx, pool, id, fmt.Sprintf("a%031d", i))
	}
	hiddenCommitID := seeder.commit("sha-hidden-errored-committed", sampleDay(600))
	hiddenID := seeder.result(sampleResultParams{
		fingerprint: "fp-hidden-errored-committed",
		ts:          sampleDay(600),
		commitID:    &hiddenCommitID,
		unit:        &unitSeconds,
		data:        denseData(600),
		error:       []byte(`{"status":"failed"}`),
	})
	hiddenID = rewriteResultID(t, ctx, pool, hiddenID, "m0000000000000000000000000000000")
	for i := range int(sampleCandidateLimit) + 1 {
		id := seeder.result(sampleResultParams{
			fingerprint: fmt.Sprintf("fp-new-missing-commit-%03d", i),
			ts:          sampleDay(700 + i),
			unit:        &unitSeconds,
			data:        denseData(float64(700 + i)),
		})
		rewriteResultID(t, ctx, pool, id, fmt.Sprintf("z%031d", i))
	}
	analyzeSampleTables(t, ctx, pool)

	manifest, err := SelectSampleManifest(ctx, pool, sampleDay(1400))

	require.NoError(t, err)
	assertCategory(t, manifest, "errored_result", hiddenID, "fp-hidden-errored-committed", 0)
	assertCategory(t, manifest, "with_commit", hiddenID, "fp-hidden-errored-committed", 0)
}

func TestSelectSampleManifestFindsMissingCommitCategoryOutsideCandidateEdges(t *testing.T) {
	pool, ctx := dbtest.NewPool(t)
	store := db.NewStore(pool)
	seeder := newSampleSeeder(t, ctx, pool, store, "hidden-missing-commit")
	unitSeconds := "s"
	commitID := seeder.commit("sha-hidden-missing-edge", sampleDay(0))

	for i := range int(sampleCandidateLimit) + 1 {
		id := seeder.result(sampleResultParams{
			fingerprint: fmt.Sprintf("fp-old-committed-%03d", i),
			ts:          sampleDay(i),
			commitID:    &commitID,
			unit:        &unitSeconds,
			data:        denseData(float64(i)),
		})
		rewriteResultID(t, ctx, pool, id, fmt.Sprintf("a%031d", i))
	}
	hiddenID := seeder.result(sampleResultParams{
		fingerprint: "fp-hidden-missing-commit",
		ts:          sampleDay(600),
		unit:        &unitSeconds,
		data:        denseData(600),
	})
	hiddenID = rewriteResultID(t, ctx, pool, hiddenID, "m0000000000000000000000000000000")
	for i := range int(sampleCandidateLimit) + 1 {
		id := seeder.result(sampleResultParams{
			fingerprint: fmt.Sprintf("fp-new-committed-%03d", i),
			ts:          sampleDay(700 + i),
			commitID:    &commitID,
			unit:        &unitSeconds,
			data:        denseData(float64(700 + i)),
		})
		rewriteResultID(t, ctx, pool, id, fmt.Sprintf("z%031d", i))
	}
	analyzeSampleTables(t, ctx, pool)

	manifest, err := SelectSampleManifest(ctx, pool, sampleDay(1400))

	require.NoError(t, err)
	assertCategory(t, manifest, "missing_commit", hiddenID, "fp-hidden-missing-commit", 0)
}

func TestSelectSampleManifestTreatsNullCommitTimestampAsMissingCommitMetadata(t *testing.T) {
	pool, ctx := dbtest.NewPool(t)
	store := db.NewStore(pool)
	seeder := newSampleSeeder(t, ctx, pool, store, "null-commit-timestamp")
	unitSeconds := "s"
	sha := "sha-null-commit-timestamp"
	commitID, err := store.GetOrCreateCommit(ctx, storage.InsertCommitParams{
		Sha:          sha,
		Repository:   "https://github.com/conbench/prod-sample",
		Message:      "sample",
		AuthorName:   "CI",
		Timestamp:    nil,
		ForkPointSha: &sha,
	})
	require.NoError(t, err)
	resultID := seeder.result(sampleResultParams{
		fingerprint: "fp-null-commit-timestamp",
		ts:          sampleDay(0),
		commitID:    &commitID,
		unit:        &unitSeconds,
		data:        denseData(1),
	})
	analyzeSampleTables(t, ctx, pool)

	manifest, err := SelectSampleManifest(ctx, pool, sampleDay(1))

	require.NoError(t, err)
	assertCategory(t, manifest, "missing_commit", resultID, "fp-null-commit-timestamp", 0)
}

func TestBuildSampleManifestUsesMetadataForErroredCandidateHistory(t *testing.T) {
	generatedAt := time.Date(2026, 6, 15, 15, 0, 0, 0, time.UTC)
	candidates := []sampleCandidate{
		{
			id:                 "errored-candidate",
			historyFingerprint: "fp-valid-history",
			timestamp:          sampleDay(10),
			hasError:           true,
		},
	}
	metadata := map[string]sampleFingerprintMetadata{
		"fp-valid-history": {
			pointCount:     3,
			latestResultID: "latest-history-member",
		},
	}

	manifest := buildSampleManifest(generatedAt, candidates, metadata, nil)

	assertCategory(t, manifest, "long_history", "latest-history-member", "fp-valid-history", 3)
	assertCategory(t, manifest, "short_history", "latest-history-member", "fp-valid-history", 3)
}

func TestSelectSampleManifestCompareAllowsDifferentTimeUnits(t *testing.T) {
	pool, ctx := dbtest.NewPool(t)
	store := db.NewStore(pool)
	seeder := newSampleSeeder(t, ctx, pool, store, "compare-time-unit")
	unitSeconds := "s"
	timeUnitNS := "ns"
	timeUnitUS := "us"

	baselineID := seeder.committedResult("fp-compare-time-unit", sampleDay(0), "sha-compare-time-a", &unitSeconds, &timeUnitNS, denseData(10))
	contenderID := seeder.committedResult("fp-compare-time-unit", sampleDay(1), "sha-compare-time-b", &unitSeconds, &timeUnitUS, denseData(11))
	analyzeSampleTables(t, ctx, pool)

	manifest, err := SelectSampleManifest(ctx, pool, sampleDay(2))

	require.NoError(t, err)
	require.NotNil(t, manifest.Compare)
	assert.Equal(t, baselineID, manifest.Compare.BaselineResultID)
	assert.Equal(t, contenderID, manifest.Compare.ContenderResultID)

	_, err = service.NewReader(store).Compare(ctx, manifest.Compare.BaselineResultID, manifest.Compare.ContenderResultID, 5, 5)
	require.NoError(t, err)
}

func TestSelectSampleManifestUsesExactPerFingerprintPointCounts(t *testing.T) {
	pool, ctx := dbtest.NewPool(t)
	store := db.NewStore(pool)
	seeder := newSampleSeeder(t, ctx, pool, store, "exact-point-counts")
	unitSeconds := "s"
	exactCount := int64(int(sampleCandidateLimit)*4 + 1)

	for i := range int(exactCount) {
		seeder.committedResult("fp-exact-count", sampleDay(i), fmt.Sprintf("sha-exact-%04d", i), &unitSeconds, nil, denseData(float64(i)))
	}
	analyzeSampleTables(t, ctx, pool)

	manifest, err := SelectSampleManifest(ctx, pool, sampleDay(int(exactCount)+1))

	require.NoError(t, err)
	assertCategory(t, manifest, "long_history", "", "fp-exact-count", exactCount)
	assertCategory(t, manifest, "high_volume_series", "", "fp-exact-count", exactCount)
}

func TestSelectSampleManifestCountsOnlyAPIHistoryMembers(t *testing.T) {
	pool, ctx := dbtest.NewPool(t)
	store := db.NewStore(pool)
	seeder := newSampleSeeder(t, ctx, pool, store, "api-history-counts")
	unitSeconds := "s"

	for i := range 8 {
		commitID := seeder.commit(fmt.Sprintf("sha-off-branch-%02d", i), sampleDay(i))
		_, err := pool.Exec(ctx, `UPDATE commit SET fork_point_sha = $1 WHERE id = $2`, "different-fork", commitID)
		require.NoError(t, err)
		seeder.result(sampleResultParams{
			fingerprint: "fp-off-branch-heavy",
			ts:          sampleDay(i),
			commitID:    &commitID,
			unit:        &unitSeconds,
			data:        denseData(float64(i)),
		})
	}
	seeder.committedResult("fp-default-branch", sampleDay(20), "sha-default-a", &unitSeconds, nil, denseData(20))
	expectedLatest := seeder.committedResult("fp-default-branch", sampleDay(21), "sha-default-b", &unitSeconds, nil, denseData(21))
	analyzeSampleTables(t, ctx, pool)

	manifest, err := SelectSampleManifest(ctx, pool, sampleDay(30))

	require.NoError(t, err)
	assertCategory(t, manifest, "long_history", expectedLatest, "fp-default-branch", 2)
	assert.NotEqual(t, "fp-off-branch-heavy", manifest.Categories["long_history"].HistoryFingerprint)
}

func TestOptionalSampleQueryFailureDoesNotTreatContextCancellationAsWarning(t *testing.T) {
	assert.False(t, optionalSampleQueryFailure(context.DeadlineExceeded))
	assert.False(t, optionalSampleQueryFailure(context.Canceled))
}

func TestOptionalSampleQueryFailureTreatsStatementTimeoutAsWarning(t *testing.T) {
	assert.True(t, optionalSampleQueryFailure(&pgconn.PgError{Code: "57014"}))
}

type metadataTimeoutQueryer struct {
	inner            SampleQueryer
	timeoutTriggered bool
}

func (q *metadataTimeoutQueryer) Exec(ctx context.Context, sql string, args ...any) (pgconn.CommandTag, error) {
	return q.inner.Exec(ctx, sql, args...)
}

func (q *metadataTimeoutQueryer) Query(ctx context.Context, sql string, args ...any) (pgx.Rows, error) {
	if !q.timeoutTriggered && strings.Contains(sql, "unit_key_count") {
		q.timeoutTriggered = true
		rows, err := q.inner.Query(ctx, "SELECT pg_sleep(2)")
		if err != nil {
			return nil, err
		}
		defer rows.Close()
		for rows.Next() {
		}
		if err := rows.Err(); err != nil {
			return nil, err
		}
		return nil, fmt.Errorf("expected forced metadata timeout")
	}
	return q.inner.Query(ctx, sql, args...)
}

func (q *metadataTimeoutQueryer) QueryRow(ctx context.Context, sql string, args ...any) pgx.Row {
	return q.inner.QueryRow(ctx, sql, args...)
}

func assertCategory(
	t *testing.T,
	manifest SampleManifest,
	name string,
	resultID string,
	fingerprint string,
	pointCount int64,
) {
	t.Helper()
	require.Contains(t, manifest.Categories, name)
	got := manifest.Categories[name]
	if resultID != "" {
		assert.Equal(t, resultID, got.ResultID, name)
	}
	assert.Equal(t, fingerprint, got.HistoryFingerprint, name)
	assert.Equal(t, pointCount, got.PointCount, name)
	assert.NotEmpty(t, got.Note, name)
}

type sampleFixture struct {
	longNewestID       string
	shortResultID      string
	oldResultID        string
	recentResultID     string
	erroredResultID    string
	missingCommitID    string
	mixedNewestID      string
	highVolumeNewestID string
	compareBaselineID  string
	compareContenderID string
}

func seedSampleFixture(
	t *testing.T,
	ctx context.Context,
	pool *pgxpool.Pool,
	store *db.Store,
) sampleFixture {
	t.Helper()
	seeder := newSampleSeeder(t, ctx, pool, store, "sample-benchmark")
	commit := seeder.commit
	result := seeder.result
	committedResult := seeder.committedResult

	unitSeconds := "s"
	unitThroughput := "B/s"
	oldResultID := committedResult("fp-old", sampleDay(0), "sha-old", &unitSeconds, nil, denseData(10))
	shortResultID := committedResult("fp-000-short", sampleDay(1), "sha-short", &unitSeconds, nil, denseData(11))

	longInvalidA := committedResult("fp-long", sampleDay(2), "sha-long-invalid-a", nil, nil, nil)
	longInvalidB := committedResult("fp-long", sampleDay(3), "sha-long-invalid-b", nil, nil, nil)
	longInvalidC := committedResult("fp-long", sampleDay(4), "sha-long-invalid-c", nil, nil, nil)
	compareBaselineID := committedResult("fp-long", sampleDay(5), "sha-long-valid-a", &unitSeconds, nil, denseData(20))
	compareContenderID := committedResult("fp-long", sampleDay(6), "sha-long-valid-b", &unitSeconds, nil, denseData(30))
	require.NotEmpty(t, longInvalidA)
	require.NotEmpty(t, longInvalidB)
	require.NotEmpty(t, longInvalidC)
	require.NotEmpty(t, compareBaselineID)
	require.NotEmpty(t, compareContenderID)

	mixedOldID := committedResult("fp-mixed-unit", sampleDay(7), "sha-mixed-a", &unitSeconds, nil, denseData(40))
	mixedTimeUnit := "ns"
	mixedNewestID := committedResult("fp-mixed-unit", sampleDay(8), "sha-mixed-b", &unitThroughput, &mixedTimeUnit, denseData(50))
	require.NotEmpty(t, mixedOldID)

	var highVolumeNewestID string
	var highVolumeOldestID string
	var erroredResultID string
	for i := range 7 {
		ts := sampleDay(9 + i)
		commitID := commit("sha-volume-"+string(rune('a'+i)), ts)
		var resultError []byte
		if i == 6 {
			resultError = []byte(`{"status":"failed"}`)
		}
		id := result(sampleResultParams{
			fingerprint: "fp-volume",
			ts:          ts,
			commitID:    &commitID,
			unit:        &unitSeconds,
			data:        denseData(float64(60 + i)),
			error:       resultError,
		})
		if i == 5 {
			highVolumeNewestID = id
		}
		if i == 0 {
			highVolumeOldestID = id
		}
		if i == 6 {
			erroredResultID = id
		}
	}

	missingCommitID := result(sampleResultParams{
		fingerprint: "fp-missing-commit",
		ts:          sampleDay(16),
		unit:        &unitSeconds,
		data:        denseData(90),
	})
	recentResultID := committedResult("fp-recent", sampleDay(17), "sha-recent", &unitSeconds, nil, denseData(100))

	analyzeSampleTables(t, ctx, pool)

	return sampleFixture{
		longNewestID:       highVolumeNewestID,
		shortResultID:      shortResultID,
		oldResultID:        oldResultID,
		recentResultID:     recentResultID,
		erroredResultID:    erroredResultID,
		missingCommitID:    missingCommitID,
		mixedNewestID:      mixedNewestID,
		highVolumeNewestID: highVolumeNewestID,
		compareBaselineID:  highVolumeOldestID,
		compareContenderID: highVolumeNewestID,
	}
}

type sampleSeeder struct {
	t          *testing.T
	ctx        context.Context
	pool       *pgxpool.Pool
	store      *db.Store
	caseID     string
	contextID  string
	infoID     string
	hardwareID string
}

func newSampleSeeder(
	t *testing.T,
	ctx context.Context,
	pool *pgxpool.Pool,
	store *db.Store,
	caseName string,
) sampleSeeder {
	t.Helper()
	caseID, err := store.GetOrCreateCase(ctx, caseName, []byte(`{}`))
	require.NoError(t, err)
	contextID, err := store.GetOrCreateContext(ctx, []byte(`{}`))
	require.NoError(t, err)
	infoID, err := store.GetOrCreateInfo(ctx, []byte(`{}`))
	require.NoError(t, err)
	hardwareID, err := store.GetOrCreateHardware(ctx, storage.InsertHardwareParams{
		Type:            "machine",
		Name:            "sample-machine",
		Hash:            "sample-machine-hash",
		GpuProductNames: []string{},
	})
	require.NoError(t, err)
	return sampleSeeder{
		t:          t,
		ctx:        ctx,
		pool:       pool,
		store:      store,
		caseID:     caseID,
		contextID:  contextID,
		infoID:     infoID,
		hardwareID: hardwareID,
	}
}

func (s sampleSeeder) commit(sha string, ts time.Time) string {
	s.t.Helper()
	id, err := s.store.GetOrCreateCommit(s.ctx, storage.InsertCommitParams{
		Sha:          sha,
		Repository:   "https://github.com/conbench/prod-sample",
		Message:      "sample",
		AuthorName:   "CI",
		Timestamp:    &ts,
		ForkPointSha: &sha,
	})
	require.NoError(s.t, err)
	return id
}

func (s sampleSeeder) result(p sampleResultParams) string {
	s.t.Helper()
	id, err := s.store.InsertBenchmarkResult(s.ctx, storage.InsertBenchmarkResultParams{
		CaseID:             s.caseID,
		ContextID:          s.contextID,
		InfoID:             s.infoID,
		HardwareID:         s.hardwareID,
		RunID:              "sample-run",
		RunTags:            []byte(`{}`),
		CommitID:           p.commitID,
		CommitRepoUrl:      "https://github.com/conbench/prod-sample",
		HistoryFingerprint: p.fingerprint,
		Timestamp:          p.ts,
		Unit:               p.unit,
		TimeUnit:           p.timeUnit,
		Data:               p.data,
		Error:              p.error,
	})
	require.NoError(s.t, err)
	return id
}

func (s sampleSeeder) committedResult(
	fingerprint string,
	ts time.Time,
	sha string,
	unit *string,
	timeUnit *string,
	data []*float64,
) string {
	s.t.Helper()
	commitID := s.commit(sha, ts)
	return s.result(sampleResultParams{
		fingerprint: fingerprint,
		ts:          ts,
		commitID:    &commitID,
		unit:        unit,
		timeUnit:    timeUnit,
		data:        data,
	})
}

func rewriteResultID(t *testing.T, ctx context.Context, pool *pgxpool.Pool, oldID string, newID string) string {
	t.Helper()
	tag, err := pool.Exec(ctx, `UPDATE benchmark_result SET id = $1 WHERE id = $2`, newID, oldID)
	require.NoError(t, err)
	require.Equal(t, int64(1), tag.RowsAffected())
	return newID
}

func analyzeSampleTables(t *testing.T, ctx context.Context, pool *pgxpool.Pool) {
	t.Helper()
	_, err := pool.Exec(ctx, `ANALYZE benchmark_result, commit`)
	require.NoError(t, err)
}

type sampleResultParams struct {
	fingerprint string
	ts          time.Time
	commitID    *string
	unit        *string
	timeUnit    *string
	data        []*float64
	error       []byte
}

func sampleDay(day int) time.Time {
	return time.Date(2024, 1, 1, 12, 0, 0, 0, time.UTC).AddDate(0, 0, day)
}

func denseData(v float64) []*float64 {
	return []*float64{&v}
}
