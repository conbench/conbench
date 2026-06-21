package prodclone

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
)

const (
	sampleCategoryLongHistory      = "long_history"
	sampleCategoryShortHistory     = "short_history"
	sampleCategoryRecentResult     = "recent_result"
	sampleCategoryOldResult        = "old_result"
	sampleCategoryErroredResult    = "errored_result"
	sampleCategoryWithCommit       = "with_commit"
	sampleCategoryMissingCommit    = "missing_commit"
	sampleCategoryMixedUnit        = "mixed_unit"
	sampleCategoryHighVolumeSeries = "high_volume_series"
	sampleCategoryHistoryMember    = "history_member"

	sampleCandidateLimit        = int32(512)
	sampleCompareCandidateLimit = int32(512)
	sampleRecentCommitLimit     = int32(128)
)

var sampleCategoryNames = []string{
	sampleCategoryLongHistory,
	sampleCategoryShortHistory,
	sampleCategoryRecentResult,
	sampleCategoryOldResult,
	sampleCategoryErroredResult,
	sampleCategoryWithCommit,
	sampleCategoryMissingCommit,
	sampleCategoryMixedUnit,
	sampleCategoryHighVolumeSeries,
}

var sampleCandidateSourceQueries = []sampleCandidateSourceQuery{
	{name: "recent_timestamp", query: sampleCandidatesRecentTimestampSQL},
	{name: "old_timestamp", query: sampleCandidatesOldTimestampSQL},
	{name: "recent_id", query: sampleCandidatesRecentIDSQL},
	{name: "old_id", query: sampleCandidatesOldIDSQL},
	{name: "latest_errored", query: sampleCandidatesLatestErroredSQL},
	{name: "latest_with_commit", query: sampleCandidatesLatestWithCommitSQL},
	{name: "latest_missing_commit_id", query: sampleCandidatesLatestMissingCommitIDSQL},
	{name: "latest_null_commit_timestamp", query: sampleCandidatesLatestNullCommitTimestampSQL},
}

type SampleManifest struct {
	GeneratedAt time.Time                 `json:"generated_at"`
	Categories  map[string]SampleCategory `json:"categories"`
	Warnings    []string                  `json:"warnings,omitempty"`
	Compare     *CompareSample            `json:"compare,omitempty"`
	CIReport    *CIReportSample           `json:"ci_report,omitempty"`
}

type SampleCategory struct {
	ResultID           string `json:"result_id,omitempty"`
	HistoryFingerprint string `json:"history_fingerprint,omitempty"`
	PointCount         int64  `json:"point_count,omitempty"`
	Note               string `json:"note,omitempty"`
}

type CompareSample struct {
	BaselineResultID   string `json:"baseline_result_id"`
	ContenderResultID  string `json:"contender_result_id"`
	HistoryFingerprint string `json:"history_fingerprint"`
}

type CIReportSample struct {
	Repository         string   `json:"repository"`
	CommitSHA          string   `json:"commit_sha"`
	RunIDs             []string `json:"run_ids"`
	ResultID           string   `json:"result_id"`
	HistoryFingerprint string   `json:"history_fingerprint"`
}

type SampleQueryer interface {
	Exec(ctx context.Context, sql string, args ...any) (pgconn.CommandTag, error)
	Query(ctx context.Context, sql string, args ...any) (pgx.Rows, error)
	QueryRow(ctx context.Context, sql string, args ...any) pgx.Row
}

type sampleCandidateSourceQuery struct {
	name  string
	query string
}

type sampleCandidate struct {
	id                    string
	historyFingerprint    string
	timestamp             time.Time
	unit                  *string
	timeUnit              *string
	hasError              bool
	hasCommit             bool
	missingCommitMetadata bool
}

type sampleSeries struct {
	fingerprint        string
	totalCount         int64
	nonErroredCount    int64
	latest             sampleCandidate
	latestNonErrored   sampleCandidate
	haveLatest         bool
	haveLatestNonError bool
	unitKeys           map[string]struct{}
}

type sampleFingerprintMetadata struct {
	pointCount     int64
	unitKeyCount   int64
	latestResultID string
}

func SelectSampleManifest(ctx context.Context, db SampleQueryer, generatedAt time.Time) (SampleManifest, error) {
	candidates, warnings, err := selectSampleCandidates(ctx, db)
	if err != nil {
		return SampleManifest{}, err
	}
	metadata, metadataWarnings, err := selectCandidateFingerprintMetadata(ctx, db, candidates)
	if err != nil {
		if !optionalSampleQueryFailure(err) {
			return SampleManifest{}, err
		}
		metadata = map[string]sampleFingerprintMetadata{}
		warnings = append(warnings, fmt.Sprintf("sample metadata query failed: %v", err))
	} else {
		warnings = append(warnings, metadataWarnings...)
	}
	manifest := buildSampleManifest(generatedAt.UTC(), candidates, metadata, warnings)
	addMissingSampleCategoryWarnings(&manifest)

	if _, longOK := manifest.Categories[sampleCategoryLongHistory]; !longOK {
		if _, shortOK := manifest.Categories[sampleCategoryShortHistory]; !shortOK {
			historyMember, ok, err := selectHistoryMemberSample(ctx, db)
			if err != nil {
				if !optionalSampleQueryFailure(err) {
					return SampleManifest{}, fmt.Errorf("select history member sample: %w", err)
				}
				manifest.Warnings = append(manifest.Warnings, fmt.Sprintf("history member sample query failed: %v", err))
			} else if ok {
				manifest.Categories[sampleCategoryHistoryMember] = historyMember
			}
		}
	}

	compare, ok, compareWarnings, err := selectManifestCompareSample(ctx, db, manifest)
	manifest.Warnings = append(manifest.Warnings, compareWarnings...)
	if err != nil {
		if !optionalSampleQueryFailure(err) {
			return SampleManifest{}, fmt.Errorf("select compare sample: %w", err)
		}
		manifest.Warnings = append(manifest.Warnings, fmt.Sprintf("compare sample query failed: %v", err))
	} else if ok {
		manifest.Compare = &compare
	} else {
		manifest.Warnings = append(manifest.Warnings, "compare sample was not found for long_history")
	}

	ciReport, ok, err := selectCIReportSample(ctx, db)
	if err != nil {
		if !optionalSampleQueryFailure(err) {
			return SampleManifest{}, fmt.Errorf("select ci report sample: %w", err)
		}
		manifest.Warnings = append(manifest.Warnings, fmt.Sprintf("ci_report sample query failed: %v", err))
	} else if ok {
		manifest.CIReport = &ciReport
	} else {
		manifest.Warnings = append(manifest.Warnings, "ci_report sample was not found")
	}

	return manifest, nil
}

func selectSampleCandidates(ctx context.Context, db SampleQueryer) ([]sampleCandidate, []string, error) {
	indexByID := map[string]int{}
	var candidates []sampleCandidate
	var warnings []string

	for _, source := range sampleCandidateSourceQueries {
		sourceCandidates, err := selectSampleCandidateSource(ctx, db, source)
		if err != nil {
			if !optionalSampleQueryFailure(err) {
				return nil, nil, fmt.Errorf("select sample candidates from %s: %w", source.name, err)
			}
			warnings = append(warnings, fmt.Sprintf("sample candidate source %s failed: %v", source.name, err))
			continue
		}
		for _, candidate := range sourceCandidates {
			index, ok := indexByID[candidate.id]
			if ok {
				candidates[index] = mergeSampleCandidate(candidates[index], candidate)
				continue
			}
			indexByID[candidate.id] = len(candidates)
			candidates = append(candidates, candidate)
		}
	}

	return candidates, warnings, nil
}

func mergeSampleCandidate(existing sampleCandidate, next sampleCandidate) sampleCandidate {
	existing.hasError = existing.hasError || next.hasError
	existing.hasCommit = existing.hasCommit || next.hasCommit
	existing.missingCommitMetadata = existing.missingCommitMetadata || next.missingCommitMetadata
	return existing
}

func selectCandidateFingerprintMetadata(
	ctx context.Context,
	db SampleQueryer,
	candidates []sampleCandidate,
) (map[string]sampleFingerprintMetadata, []string, error) {
	fingerprints := candidateFingerprints(candidates)
	metadata := make(map[string]sampleFingerprintMetadata, len(fingerprints))
	if len(fingerprints) == 0 {
		return metadata, nil, nil
	}

	savepointed := beginSampleSavepoint(ctx, db)
	rows, err := db.Query(ctx, sampleFingerprintMetadataSQL, fingerprints)
	if err != nil {
		rollbackSampleSavepoint(ctx, db, savepointed)
		return nil, nil, fmt.Errorf("select sample metadata: %w", err)
	}
	defer rows.Close()

	for rows.Next() {
		var fingerprint string
		var item sampleFingerprintMetadata
		if err := rows.Scan(
			&fingerprint,
			&item.pointCount,
			&item.unitKeyCount,
			&item.latestResultID,
		); err != nil {
			rollbackSampleSavepoint(ctx, db, savepointed)
			return nil, nil, fmt.Errorf("scan sample metadata: %w", err)
		}
		metadata[fingerprint] = item
	}
	if err := rows.Err(); err != nil {
		rollbackSampleSavepoint(ctx, db, savepointed)
		return nil, nil, fmt.Errorf("select sample metadata: %w", err)
	}
	if err := releaseSampleSavepoint(ctx, db, savepointed); err != nil {
		return nil, nil, fmt.Errorf("release sample metadata savepoint: %w", err)
	}
	return metadata, nil, nil
}

func candidateFingerprints(candidates []sampleCandidate) []string {
	seen := map[string]struct{}{}
	var fingerprints []string
	for _, candidate := range candidates {
		if candidate.historyFingerprint == "" {
			continue
		}
		if _, ok := seen[candidate.historyFingerprint]; ok {
			continue
		}
		seen[candidate.historyFingerprint] = struct{}{}
		fingerprints = append(fingerprints, candidate.historyFingerprint)
	}
	return fingerprints
}

func selectSampleCandidateSource(
	ctx context.Context,
	db SampleQueryer,
	source sampleCandidateSourceQuery,
) ([]sampleCandidate, error) {
	savepointed := beginSampleSavepoint(ctx, db)
	rows, err := db.Query(ctx, source.query, sampleCandidateLimit)
	if err != nil {
		rollbackSampleSavepoint(ctx, db, savepointed)
		return nil, err
	}
	defer rows.Close()

	var candidates []sampleCandidate
	for rows.Next() {
		var candidate sampleCandidate
		if err := rows.Scan(
			&candidate.id,
			&candidate.historyFingerprint,
			&candidate.timestamp,
			&candidate.unit,
			&candidate.timeUnit,
			&candidate.hasError,
			&candidate.hasCommit,
			&candidate.missingCommitMetadata,
		); err != nil {
			rollbackSampleSavepoint(ctx, db, savepointed)
			return nil, err
		}
		candidates = append(candidates, candidate)
	}
	if err := rows.Err(); err != nil {
		rollbackSampleSavepoint(ctx, db, savepointed)
		return nil, err
	}
	if err := releaseSampleSavepoint(ctx, db, savepointed); err != nil {
		return nil, err
	}
	return candidates, nil
}

func buildSampleManifest(
	generatedAt time.Time,
	candidates []sampleCandidate,
	metadata map[string]sampleFingerprintMetadata,
	warnings []string,
) SampleManifest {
	manifest := SampleManifest{
		GeneratedAt: generatedAt.UTC(),
		Categories:  make(map[string]SampleCategory, len(sampleCategoryNames)),
		Warnings:    append([]string(nil), warnings...),
	}

	add := func(name string, category SampleCategory, ok bool) {
		if ok {
			manifest.Categories[name] = category
		}
	}

	category, ok := longHistorySample(candidates, metadata)
	add(sampleCategoryLongHistory, category, ok)
	category, ok = shortHistorySample(candidates, metadata)
	add(sampleCategoryShortHistory, category, ok)
	category, ok = recentResultSample(candidates)
	add(sampleCategoryRecentResult, category, ok)
	category, ok = oldResultSample(candidates)
	add(sampleCategoryOldResult, category, ok)
	category, ok = erroredResultSample(candidates)
	add(sampleCategoryErroredResult, category, ok)
	category, ok = withCommitSample(candidates)
	add(sampleCategoryWithCommit, category, ok)
	category, ok = missingCommitSample(candidates)
	add(sampleCategoryMissingCommit, category, ok)
	category, ok = mixedUnitSample(candidates, metadata)
	add(sampleCategoryMixedUnit, category, ok)
	category, ok = highVolumeSeriesSample(candidates, metadata)
	add(sampleCategoryHighVolumeSeries, category, ok)
	return manifest
}

func addMissingSampleCategoryWarnings(manifest *SampleManifest) {
	for _, name := range sampleCategoryNames {
		if _, ok := manifest.Categories[name]; ok {
			continue
		}
		manifest.Warnings = append(manifest.Warnings, missingSampleCategoryWarning(name))
	}
}

func longHistorySample(
	candidates []sampleCandidate,
	metadata map[string]sampleFingerprintMetadata,
) (SampleCategory, bool) {
	var best sampleSeries
	var bestMetadata sampleFingerprintMetadata
	found := false
	for _, series := range sampleSeriesByFingerprint(candidates) {
		item, ok := metadata[series.fingerprint]
		if !ok || item.pointCount == 0 {
			continue
		}
		if !found || item.pointCount > bestMetadata.pointCount ||
			(item.pointCount == bestMetadata.pointCount && series.fingerprint < best.fingerprint) {
			best = series
			bestMetadata = item
			found = true
		}
	}
	if !found {
		return SampleCategory{}, false
	}
	return sampleHistoryCategory(
		best.fingerprint,
		bestMetadata.latestResultID,
		bestMetadata.pointCount,
		"candidate fingerprint metadata: longest API history membership",
	), true
}

func shortHistorySample(
	candidates []sampleCandidate,
	metadata map[string]sampleFingerprintMetadata,
) (SampleCategory, bool) {
	var best sampleSeries
	var bestMetadata sampleFingerprintMetadata
	found := false
	for _, series := range sampleSeriesByFingerprint(candidates) {
		item, ok := metadata[series.fingerprint]
		if !ok || item.pointCount == 0 {
			continue
		}
		if !found || item.pointCount < bestMetadata.pointCount ||
			(item.pointCount == bestMetadata.pointCount && series.fingerprint < best.fingerprint) {
			best = series
			bestMetadata = item
			found = true
		}
	}
	if !found {
		return SampleCategory{}, false
	}
	return sampleHistoryCategory(
		best.fingerprint,
		bestMetadata.latestResultID,
		bestMetadata.pointCount,
		"candidate fingerprint metadata: shortest API history membership",
	), true
}

func recentResultSample(candidates []sampleCandidate) (SampleCategory, bool) {
	candidate, ok := latestCandidate(candidates, func(sampleCandidate) bool { return true })
	if !ok {
		return SampleCategory{}, false
	}
	return sampleCategory(candidate, 0, "bounded candidate sources: newest benchmark_result timestamp"), true
}

func oldResultSample(candidates []sampleCandidate) (SampleCategory, bool) {
	candidate, ok := oldestCandidate(candidates, func(sampleCandidate) bool { return true })
	if !ok {
		return SampleCategory{}, false
	}
	return sampleCategory(candidate, 0, "bounded candidate sources: oldest benchmark_result timestamp"), true
}

func erroredResultSample(candidates []sampleCandidate) (SampleCategory, bool) {
	candidate, ok := latestCandidate(candidates, func(candidate sampleCandidate) bool {
		return candidate.hasError
	})
	if !ok {
		return SampleCategory{}, false
	}
	return sampleCategory(candidate, 0, "targeted candidate source: benchmark_result with non-null error"), true
}

func withCommitSample(candidates []sampleCandidate) (SampleCategory, bool) {
	candidate, ok := latestCandidate(candidates, func(candidate sampleCandidate) bool {
		return candidate.hasCommit
	})
	if !ok {
		return SampleCategory{}, false
	}
	return sampleCategory(candidate, 0, "targeted candidate source: benchmark_result with commit_id"), true
}

func missingCommitSample(candidates []sampleCandidate) (SampleCategory, bool) {
	candidate, ok := latestCandidate(candidates, func(candidate sampleCandidate) bool {
		return candidate.missingCommitMetadata
	})
	if !ok {
		return SampleCategory{}, false
	}
	return sampleCategory(candidate, 0, "targeted candidate source: benchmark_result without usable commit metadata"), true
}

func mixedUnitSample(
	candidates []sampleCandidate,
	metadata map[string]sampleFingerprintMetadata,
) (SampleCategory, bool) {
	var best sampleSeries
	var bestMetadata sampleFingerprintMetadata
	found := false
	for _, series := range sampleSeriesByFingerprint(candidates) {
		item, ok := metadata[series.fingerprint]
		if !ok || item.unitKeyCount < 2 {
			continue
		}
		if !found || item.pointCount > bestMetadata.pointCount ||
			(item.pointCount == bestMetadata.pointCount && series.fingerprint < best.fingerprint) {
			best = series
			bestMetadata = item
			found = true
		}
	}
	if !found {
		return SampleCategory{}, false
	}
	return sampleHistoryCategory(
		best.fingerprint,
		bestMetadata.latestResultID,
		bestMetadata.pointCount,
		"candidate fingerprint metadata: API history with mixed unit or time_unit values",
	), true
}

func highVolumeSeriesSample(
	candidates []sampleCandidate,
	metadata map[string]sampleFingerprintMetadata,
) (SampleCategory, bool) {
	var best sampleSeries
	var bestMetadata sampleFingerprintMetadata
	found := false
	for _, series := range sampleSeriesByFingerprint(candidates) {
		if !series.haveLatest {
			continue
		}
		item, ok := metadata[series.fingerprint]
		if !ok {
			continue
		}
		if !found || item.pointCount > bestMetadata.pointCount ||
			(item.pointCount == bestMetadata.pointCount && series.fingerprint < best.fingerprint) {
			best = series
			bestMetadata = item
			found = true
		}
	}
	if !found {
		return SampleCategory{}, false
	}
	return sampleHistoryCategory(
		best.fingerprint,
		bestMetadata.latestResultID,
		bestMetadata.pointCount,
		"candidate fingerprint metadata: highest candidate API history membership",
	), true
}

func sampleSeriesByFingerprint(candidates []sampleCandidate) map[string]sampleSeries {
	seriesByFingerprint := map[string]sampleSeries{}
	for _, candidate := range candidates {
		if candidate.historyFingerprint == "" {
			continue
		}
		series := seriesByFingerprint[candidate.historyFingerprint]
		if series.fingerprint == "" {
			series.fingerprint = candidate.historyFingerprint
			series.unitKeys = map[string]struct{}{}
		}
		series.totalCount++
		if !series.haveLatest || newerCandidate(candidate, series.latest) {
			series.latest = candidate
			series.haveLatest = true
		}
		if !candidate.hasError {
			series.nonErroredCount++
			if !series.haveLatestNonError || newerCandidate(candidate, series.latestNonErrored) {
				series.latestNonErrored = candidate
				series.haveLatestNonError = true
			}
		}
		if key, ok := unitKey(candidate); ok {
			series.unitKeys[key] = struct{}{}
		}
		seriesByFingerprint[candidate.historyFingerprint] = series
	}
	return seriesByFingerprint
}

func latestCandidate(candidates []sampleCandidate, keep func(sampleCandidate) bool) (sampleCandidate, bool) {
	var best sampleCandidate
	found := false
	for _, candidate := range candidates {
		if !keep(candidate) {
			continue
		}
		if !found || newerCandidate(candidate, best) {
			best = candidate
			found = true
		}
	}
	return best, found
}

func oldestCandidate(candidates []sampleCandidate, keep func(sampleCandidate) bool) (sampleCandidate, bool) {
	var best sampleCandidate
	found := false
	for _, candidate := range candidates {
		if !keep(candidate) {
			continue
		}
		if !found || olderCandidate(candidate, best) {
			best = candidate
			found = true
		}
	}
	return best, found
}

func newerCandidate(left sampleCandidate, right sampleCandidate) bool {
	if !left.timestamp.Equal(right.timestamp) {
		return left.timestamp.After(right.timestamp)
	}
	return left.id > right.id
}

func olderCandidate(left sampleCandidate, right sampleCandidate) bool {
	if !left.timestamp.Equal(right.timestamp) {
		return left.timestamp.Before(right.timestamp)
	}
	return left.id < right.id
}

func sampleCategory(candidate sampleCandidate, pointCount int64, note string) SampleCategory {
	return SampleCategory{
		ResultID:           candidate.id,
		HistoryFingerprint: candidate.historyFingerprint,
		PointCount:         pointCount,
		Note:               note,
	}
}

func sampleHistoryCategory(fingerprint string, resultID string, pointCount int64, note string) SampleCategory {
	return SampleCategory{
		ResultID:           resultID,
		HistoryFingerprint: fingerprint,
		PointCount:         pointCount,
		Note:               note,
	}
}

func unitKey(candidate sampleCandidate) (string, bool) {
	if candidate.unit == nil {
		return "", false
	}
	timeUnit := ""
	if candidate.timeUnit != nil {
		timeUnit = *candidate.timeUnit
	}
	return *candidate.unit + "\x1f" + timeUnit, true
}

func selectHistoryMemberSample(ctx context.Context, db SampleQueryer) (SampleCategory, bool, error) {
	savepointed := beginSampleSavepoint(ctx, db)
	var category SampleCategory
	err := db.QueryRow(ctx, sampleHistoryMemberSQL, sampleRecentCommitLimit).Scan(
		&category.ResultID,
		&category.HistoryFingerprint,
	)
	if err != nil {
		rollbackSampleSavepoint(ctx, db, savepointed)
		if errors.Is(err, pgx.ErrNoRows) {
			return SampleCategory{}, false, nil
		}
		return SampleCategory{}, false, err
	}
	if err := releaseSampleSavepoint(ctx, db, savepointed); err != nil {
		return SampleCategory{}, false, err
	}
	category.Note = "bounded recent default-branch history member"
	return category, true, nil
}

func selectManifestCompareSample(
	ctx context.Context,
	db SampleQueryer,
	manifest SampleManifest,
) (CompareSample, bool, []string, error) {
	var warnings []string
	longHistory := manifest.Categories[sampleCategoryLongHistory]
	if longHistory.HistoryFingerprint != "" {
		compare, ok, err := selectCompareSample(ctx, db, longHistory.HistoryFingerprint)
		if err != nil {
			if !optionalSampleQueryFailure(err) {
				return CompareSample{}, false, warnings, err
			}
			warnings = append(warnings, fmt.Sprintf("long-history compare sample query failed: %v", err))
		} else if ok {
			return compare, true, warnings, nil
		}
	}

	compare, ok, err := selectRecentCompareSample(ctx, db)
	if err != nil {
		if !optionalSampleQueryFailure(err) {
			return CompareSample{}, false, warnings, err
		}
		warnings = append(warnings, fmt.Sprintf("recent-commit compare sample query failed: %v", err))
		return CompareSample{}, false, warnings, nil
	}
	return compare, ok, warnings, nil
}

func selectCompareSample(ctx context.Context, db SampleQueryer, fingerprint string) (CompareSample, bool, error) {
	if fingerprint == "" {
		return CompareSample{}, false, nil
	}
	savepointed := beginSampleSavepoint(ctx, db)
	var sample CompareSample
	err := db.QueryRow(ctx, sampleCompareSQL, fingerprint, sampleCompareCandidateLimit).Scan(
		&sample.BaselineResultID,
		&sample.ContenderResultID,
		&sample.HistoryFingerprint,
	)
	if err != nil {
		rollbackSampleSavepoint(ctx, db, savepointed)
		if errors.Is(err, pgx.ErrNoRows) {
			return CompareSample{}, false, nil
		}
		return CompareSample{}, false, err
	}
	if err := releaseSampleSavepoint(ctx, db, savepointed); err != nil {
		return CompareSample{}, false, err
	}
	return sample, true, nil
}

func selectRecentCompareSample(ctx context.Context, db SampleQueryer) (CompareSample, bool, error) {
	savepointed := beginSampleSavepoint(ctx, db)
	var sample CompareSample
	err := db.QueryRow(ctx, sampleRecentCompareSQL, sampleRecentCommitLimit).Scan(
		&sample.BaselineResultID,
		&sample.ContenderResultID,
		&sample.HistoryFingerprint,
	)
	if err != nil {
		rollbackSampleSavepoint(ctx, db, savepointed)
		if errors.Is(err, pgx.ErrNoRows) {
			return CompareSample{}, false, nil
		}
		return CompareSample{}, false, err
	}
	if err := releaseSampleSavepoint(ctx, db, savepointed); err != nil {
		return CompareSample{}, false, err
	}
	return sample, true, nil
}

func selectCIReportSample(ctx context.Context, db SampleQueryer) (CIReportSample, bool, error) {
	savepointed := beginSampleSavepoint(ctx, db)
	var sample CIReportSample
	var runID string
	err := db.QueryRow(ctx, sampleCIReportSQL).Scan(
		&sample.Repository,
		&sample.CommitSHA,
		&runID,
		&sample.ResultID,
		&sample.HistoryFingerprint,
	)
	if err != nil {
		rollbackSampleSavepoint(ctx, db, savepointed)
		if errors.Is(err, pgx.ErrNoRows) {
			return CIReportSample{}, false, nil
		}
		return CIReportSample{}, false, err
	}
	if err := releaseSampleSavepoint(ctx, db, savepointed); err != nil {
		return CIReportSample{}, false, err
	}
	sample.RunIDs = []string{runID}
	return sample, true, nil
}

func beginSampleSavepoint(ctx context.Context, db SampleQueryer) bool {
	_, err := db.Exec(ctx, "SAVEPOINT conbench_sample_query")
	return err == nil
}

func releaseSampleSavepoint(ctx context.Context, db SampleQueryer, savepointed bool) error {
	if !savepointed {
		return nil
	}
	_, err := db.Exec(ctx, "RELEASE SAVEPOINT conbench_sample_query")
	return err
}

func rollbackSampleSavepoint(ctx context.Context, db SampleQueryer, savepointed bool) {
	if !savepointed {
		return
	}
	_, _ = db.Exec(ctx, "ROLLBACK TO SAVEPOINT conbench_sample_query")
	_, _ = db.Exec(ctx, "RELEASE SAVEPOINT conbench_sample_query")
}

func optionalSampleQueryFailure(err error) bool {
	var pgErr *pgconn.PgError
	if errors.As(err, &pgErr) {
		return pgErr.Code == "57014"
	}
	return false
}

func missingSampleCategoryWarning(category string) string {
	return fmt.Sprintf("sample category %s was not found", category)
}

const sampleCandidateColumnsSQL = `
SELECT
	br.id,
	br.history_fingerprint,
	br."timestamp",
	br.unit,
	br.time_unit,
	br.error IS NOT NULL AS has_error,
	br.commit_id IS NOT NULL AS has_commit,
	br.commit_id IS NULL AS missing_commit_metadata
FROM benchmark_result br`

const sampleCandidatesRecentTimestampSQL = sampleCandidateColumnsSQL + `
ORDER BY br."timestamp" DESC, br.id DESC
LIMIT $1`

const sampleCandidatesOldTimestampSQL = sampleCandidateColumnsSQL + `
ORDER BY br."timestamp" ASC, br.id ASC
LIMIT $1`

const sampleCandidatesRecentIDSQL = sampleCandidateColumnsSQL + `
ORDER BY br.id DESC
LIMIT $1`

const sampleCandidatesOldIDSQL = sampleCandidateColumnsSQL + `
ORDER BY br.id ASC
LIMIT $1`

const sampleCandidatesLatestErroredSQL = sampleCandidateColumnsSQL + `
WHERE br.error IS NOT NULL
ORDER BY br."timestamp" DESC, br.id DESC
LIMIT $1`

const sampleCandidatesLatestWithCommitSQL = sampleCandidateColumnsSQL + `
WHERE br.commit_id IS NOT NULL
ORDER BY br."timestamp" DESC, br.id DESC
LIMIT $1`

const sampleCandidatesLatestMissingCommitIDSQL = sampleCandidateColumnsSQL + `
WHERE br.commit_id IS NULL
ORDER BY br."timestamp" DESC, br.id DESC
LIMIT $1`

const sampleCandidatesLatestNullCommitTimestampSQL = `
SELECT
	br.id,
	br.history_fingerprint,
	br."timestamp",
	br.unit,
	br.time_unit,
	br.error IS NOT NULL AS has_error,
	br.commit_id IS NOT NULL AS has_commit,
	(br.commit_id IS NULL OR c."timestamp" IS NULL) AS missing_commit_metadata
FROM benchmark_result br
JOIN commit c ON c.id = br.commit_id
WHERE c."timestamp" IS NULL
ORDER BY br."timestamp" DESC, br.id DESC
LIMIT $1`

const sampleFingerprintMetadataSQL = `
WITH requested AS (
	SELECT unnest($1::text[]) AS history_fingerprint
),
history_members AS (
	SELECT
		br.history_fingerprint,
		br.id,
		br.unit,
		br.time_unit,
		c."timestamp" AS commit_timestamp
	FROM benchmark_result br
	JOIN requested r ON r.history_fingerprint = br.history_fingerprint
	JOIN commit c ON c.id = br.commit_id
	WHERE br.error IS NULL
	  AND c.sha = c.fork_point_sha
	  AND c."timestamp" IS NOT NULL
),
counts AS (
	SELECT
		history_fingerprint,
		count(*)::bigint AS point_count,
		count(DISTINCT (unit, time_unit)) FILTER (WHERE unit IS NOT NULL)::bigint AS unit_key_count
	FROM history_members
	GROUP BY history_fingerprint
),
latest AS (
	SELECT DISTINCT ON (history_fingerprint)
		history_fingerprint,
		id
	FROM history_members
	ORDER BY history_fingerprint, commit_timestamp DESC, id DESC
)
SELECT
	counts.history_fingerprint,
	counts.point_count,
	counts.unit_key_count,
	latest.id
FROM counts
JOIN latest ON latest.history_fingerprint = counts.history_fingerprint
ORDER BY counts.history_fingerprint`

const sampleHistoryMemberSQL = `
WITH recent_commit AS MATERIALIZED (
	SELECT id, "timestamp" AS commit_timestamp
	FROM commit
	WHERE sha = fork_point_sha
	  AND "timestamp" IS NOT NULL
	ORDER BY "timestamp" DESC, id DESC
	LIMIT $1
)
SELECT br.id, br.history_fingerprint
FROM recent_commit rc
JOIN benchmark_result br ON br.commit_id = rc.id
WHERE br.error IS NULL
ORDER BY rc.commit_timestamp DESC, br.id DESC
LIMIT 1`

const sampleCIReportSQL = `
SELECT
	c.repository,
	c.sha,
	br.run_id,
	br.id,
	br.history_fingerprint
FROM benchmark_result br
JOIN commit c ON c.id = br.commit_id
WHERE br.run_id IS NOT NULL
  AND br.run_id <> ''
  AND br.history_fingerprint IS NOT NULL
  AND br.history_fingerprint <> ''
  AND c.repository IS NOT NULL
  AND c.repository <> ''
  AND c.sha IS NOT NULL
  AND c.sha <> ''
ORDER BY br."timestamp" DESC, br.id DESC
LIMIT 1`

const sampleCompareSQL = `
WITH newest AS (
	SELECT br.id, br.unit, br.time_unit, c."timestamp" AS commit_timestamp
	FROM benchmark_result br
	JOIN commit c ON c.id = br.commit_id
	WHERE br.history_fingerprint = $1
	  AND br.error IS NULL
	  AND br.unit IN ('B', 'B/s', 's', 'ns', 'i/s')
	  AND br.data IS NOT NULL
	  AND cardinality(br.data) > 0
	  AND array_position(br.data, NULL) IS NULL
	  AND c.sha = c.fork_point_sha
	  AND c."timestamp" IS NOT NULL
	ORDER BY commit_timestamp DESC, id DESC
	LIMIT $2
),
oldest AS (
	SELECT br.id, br.unit, br.time_unit, c."timestamp" AS commit_timestamp
	FROM benchmark_result br
	JOIN commit c ON c.id = br.commit_id
	WHERE br.history_fingerprint = $1
	  AND br.error IS NULL
	  AND br.unit IN ('B', 'B/s', 's', 'ns', 'i/s')
	  AND br.data IS NOT NULL
	  AND cardinality(br.data) > 0
	  AND array_position(br.data, NULL) IS NULL
	  AND c.sha = c.fork_point_sha
	  AND c."timestamp" IS NOT NULL
	ORDER BY commit_timestamp ASC, id ASC
	LIMIT $2
),
comparable AS (
	SELECT * FROM newest
	UNION
	SELECT * FROM oldest
),
unit_group AS (
	SELECT unit, count(*)::bigint AS point_count
	FROM comparable
	GROUP BY unit
	HAVING count(*) >= 2 AND min(commit_timestamp) <> max(commit_timestamp)
	ORDER BY count(*) DESC, unit ASC
	LIMIT 1
),
baseline AS (
	SELECT comparable.id, comparable.commit_timestamp
	FROM comparable
	JOIN unit_group ON comparable.unit = unit_group.unit
	ORDER BY comparable.commit_timestamp ASC, comparable.id ASC
	LIMIT 1
),
contender AS (
	SELECT comparable.id, comparable.commit_timestamp
	FROM comparable
	JOIN unit_group ON comparable.unit = unit_group.unit
	ORDER BY comparable.commit_timestamp DESC, comparable.id DESC
	LIMIT 1
)
SELECT baseline.id, contender.id, $1 AS history_fingerprint
FROM baseline, contender
WHERE baseline.commit_timestamp <> contender.commit_timestamp`

const sampleRecentCompareSQL = `
WITH recent_commit AS MATERIALIZED (
	SELECT id, "timestamp" AS commit_timestamp
	FROM commit
	WHERE sha = fork_point_sha
	  AND "timestamp" IS NOT NULL
	ORDER BY "timestamp" DESC, id DESC
	LIMIT $1
),
recent AS MATERIALIZED (
	SELECT br.id, br.history_fingerprint, br.unit, rc.commit_timestamp
	FROM recent_commit rc
	JOIN benchmark_result br ON br.commit_id = rc.id
	WHERE br.error IS NULL
	  AND br.unit IN ('B', 'B/s', 's', 'ns', 'i/s')
	  AND br.data IS NOT NULL
	  AND cardinality(br.data) > 0
	  AND array_position(br.data, NULL) IS NULL
),
unit_group AS (
	SELECT history_fingerprint, unit, count(*)::bigint AS point_count
	FROM recent
	GROUP BY history_fingerprint, unit
	HAVING count(*) >= 2 AND min(commit_timestamp) <> max(commit_timestamp)
	ORDER BY count(*) DESC, max(commit_timestamp) DESC, history_fingerprint ASC, unit ASC
	LIMIT 1
),
baseline AS (
	SELECT recent.id, recent.commit_timestamp
	FROM recent
	JOIN unit_group USING (history_fingerprint, unit)
	ORDER BY recent.commit_timestamp ASC, recent.id ASC
	LIMIT 1
),
contender AS (
	SELECT recent.id, recent.commit_timestamp
	FROM recent
	JOIN unit_group USING (history_fingerprint, unit)
	ORDER BY recent.commit_timestamp DESC, recent.id DESC
	LIMIT 1
)
SELECT baseline.id, contender.id, unit_group.history_fingerprint
FROM baseline, contender, unit_group
WHERE baseline.commit_timestamp <> contender.commit_timestamp`
