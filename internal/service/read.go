package service

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"math"
	"time"

	"github.com/conbench/conbench/internal/stats"
	"github.com/conbench/conbench/internal/storage"
	"github.com/conbench/conbench/internal/units"
)

// ErrNotFound is returned when a requested entity does not exist. The API layer
// maps it to 404.
var ErrNotFound = errors.New("not found")

// defaultSVSMode is the single-value-summary mode (config.py SVS_TYPE default).
// "best" picks the min or max by the unit's direction.
const defaultSVSMode = stats.SVSModeBest

// Reader serves the read endpoints (result detail, history) over the store. It
// computes the single value summary from persisted data; it holds no state.
type Reader struct {
	store storage.Store
}

// NewReader builds a Reader over the store.
func NewReader(store storage.Store) *Reader {
	return &Reader{store: store}
}

// Hardware is the hardware subset returned with a result.
type Hardware struct {
	ID   string `json:"id"`
	Type string `json:"type"`
	Name string `json:"name"`
	Hash string `json:"hash"`
}

// Commit is the commit subset returned with a result. It is null for a result
// submitted without a commit sha. The blank nullable marker makes huma emit the
// Commit schema itself as nullable (huma panics on `nullable:"true"` applied to
// a $ref field, so the nullability lives on this single-use type) — without it
// the contract would claim commit is a required non-null object while the API
// returns null for commitless results.
type Commit struct {
	_          struct{}   `json:"-" nullable:"true"`
	ID         string     `json:"id"`
	Sha        string     `json:"sha"`
	Repository string     `json:"repository"`
	Message    string     `json:"message"`
	Timestamp  *time.Time `json:"timestamp"`
}

// Aggregates is the persisted sample statistics block. Every field is nullable
// (an errored result has none; a result with fewer than three samples has only
// the mean).
type Aggregates struct {
	Mean   *float64 `json:"mean"`
	Min    *float64 `json:"min"`
	Max    *float64 `json:"max"`
	Median *float64 `json:"median"`
	Q1     *float64 `json:"q1"`
	Q3     *float64 `json:"q3"`
	Stdev  *float64 `json:"stdev"`
	Iqr    *float64 `json:"iqr"`
}

// ResultDetail is the GET /api/benchmark-results/{id} response: the persisted
// result with its related entities and the computed single value summary.
type ResultDetail struct {
	ID                 string         `json:"id"`
	RunID              string         `json:"run_id"`
	RunTags            map[string]any `json:"run_tags"`
	RunReason          *string        `json:"run_reason"`
	BatchID            *string        `json:"batch_id"`
	Timestamp          time.Time      `json:"timestamp"`
	CommitRepoURL      string         `json:"commit_repo_url"`
	HistoryFingerprint string         `json:"history_fingerprint"`
	Tags               map[string]any `json:"tags"`
	Context            map[string]any `json:"context"`
	Info               map[string]any `json:"info"`
	Hardware           Hardware       `json:"hardware"`
	Commit             *Commit        `json:"commit"`
	Unit               *string        `json:"unit"`
	LessIsBetter       *bool          `json:"less_is_better"`
	TimeUnit           *string        `json:"time_unit"`
	Iterations         *int32         `json:"iterations"`
	Data               []*float64     `json:"data"`
	Times              []*float64     `json:"times"`
	Stats              Aggregates     `json:"stats"`
	Error              map[string]any `json:"error" nullable:"true"`

	OptionalBenchmarkInfo map[string]any `json:"optional_benchmark_info" nullable:"true"`
	Validation            map[string]any `json:"validation" nullable:"true"`
	ChangeAnnotations     map[string]any `json:"change_annotations"`

	SVS     *float64 `json:"single_value_summary"`
	SVSType string   `json:"single_value_summary_type"`
}

// HistorySample is one point in a history series, a HistorySample subset (no
// z-score). The single value summary is the plotted value.
type HistorySample struct {
	BenchmarkResultID string       `json:"benchmark_result_id"`
	ResultTimestamp   time.Time    `json:"result_timestamp"`
	Mean              *float64     `json:"mean"`
	SVS               float64      `json:"single_value_summary"`
	SVSType           string       `json:"single_value_summary_type"`
	Unit              *string      `json:"unit"`
	HardwareHash      string       `json:"hardware_hash"`
	CommitHash        string       `json:"commit_hash"`
	CommitRepository  string       `json:"commit_repository"`
	CommitMessage     string       `json:"commit_message"`
	CommitTimestamp   *time.Time   `json:"commit_timestamp"`
	ZScoreStats       *ZScoreStats `json:"zscorestats"`
}

// ZScoreStats is the per-point rolling-statistics block (legacy
// HistorySampleZscoreStats). The four float fields are null where the engine
// returns nil: outlier rows null all four, and rolling_stddev is additionally
// null when its residual window has fewer than two points. Segment-start rows
// keep their mean fields (the engine fills them with the point's own SVS). The
// whole block is null for every sample of a mixed-unit series. The blank
// nullable marker makes huma emit this schema itself as nullable.
type ZScoreStats struct {
	_                        struct{} `json:"-" nullable:"true"`
	BeginsDistributionChange bool     `json:"begins_distribution_change"`
	IsStep                   bool     `json:"is_step"`
	IsOutlier                bool     `json:"is_outlier"`
	SegmentID                int      `json:"segment_id"`
	RollingMeanExcludingThis *float64 `json:"rolling_mean_excluding_this_commit"`
	RollingMean              *float64 `json:"rolling_mean"`
	Residual                 *float64 `json:"residual"`
	RollingStddev            *float64 `json:"rolling_stddev"`
}

func zscoreStatsFrom(rs stats.RollingStats) *ZScoreStats {
	return &ZScoreStats{
		BeginsDistributionChange: rs.BeginsDistributionChange,
		IsStep:                   rs.IsStep,
		IsOutlier:                rs.IsOutlier,
		SegmentID:                rs.SegmentID,
		RollingMeanExcludingThis: rs.RollingMeanExcludingThis,
		RollingMean:              rs.RollingMean,
		Residual:                 rs.Residual,
		RollingStddev:            rs.RollingStddev,
	}
}

// beginsDistributionChange reads the manual distribution-change flag out of a
// result's change_annotations jsonb. Ports history.py:602 (`bool(x.get(
// "begins_distribution_change", False)) if x else False`): absent column, empty
// object, or a non-boolean value all read as false.
func beginsDistributionChange(raw []byte) (bool, error) {
	if len(raw) == 0 {
		return false, nil
	}
	var m map[string]any
	if err := json.Unmarshal(raw, &m); err != nil {
		return false, fmt.Errorf("decode change_annotations: %w", err)
	}
	v, _ := m["begins_distribution_change"].(bool)
	return v, nil
}

// seriesPointFromRow builds the engine input for one membership row, using the
// caller's already-computed SVS. The membership queries require a non-null
// commit timestamp, so a member always has one; the zero-time fallback is a
// defensive guard rather than a reachable degradation.
func seriesPointFromRow(row storage.HistoryRow, svs float64) (stats.SeriesPoint, error) {
	begins, err := beginsDistributionChange(row.ChangeAnnotations)
	if err != nil {
		return stats.SeriesPoint{}, err
	}
	ct := time.Time{}
	if row.CommitTimestamp != nil {
		ct = *row.CommitTimestamp
	}
	return stats.SeriesPoint{
		CommitTimestamp:          ct,
		ResultTimestamp:          row.Timestamp,
		SVS:                      svs,
		BeginsDistributionChange: begins,
	}, nil
}

// sameUnitPtr reports whether two unit pointers are both non-nil and equal.
// A nil unit cannot anchor a single-unit series, so it is never "same".
func sameUnitPtr(a, b *string) bool {
	if a == nil || b == nil {
		return false
	}
	return *a == *b
}

// HistorySeries is the history endpoints' response: the fingerprint and its
// ordered samples (oldest commit first).
type HistorySeries struct {
	HistoryFingerprint string          `json:"history_fingerprint"`
	Samples            []HistorySample `json:"samples"`
}

// ResultDetail returns one persisted result with its related entities.
func (r *Reader) ResultDetail(ctx context.Context, id string) (*ResultDetail, error) {
	row, err := r.store.GetBenchmarkResultDetail(ctx, id)
	if err != nil {
		if errors.Is(err, storage.ErrNotFound) {
			return nil, ErrNotFound
		}
		return nil, fmt.Errorf("load result detail: %w", err)
	}

	tags, err := jsonObject(row.CaseTags)
	if err != nil {
		return nil, err
	}
	if tags == nil {
		tags = map[string]any{}
	}
	tags["name"] = row.CaseName // legacy puts the case name back into tags

	contextTags, err := jsonObject(row.ContextTags)
	if err != nil {
		return nil, err
	}
	infoTags, err := jsonObject(row.InfoTags)
	if err != nil {
		return nil, err
	}
	runTags, err := jsonObject(row.RunTags)
	if err != nil {
		return nil, err
	}
	errObj, err := jsonObject(row.Error)
	if err != nil {
		return nil, err
	}
	obi, err := jsonObject(row.OptionalBenchmarkInfo)
	if err != nil {
		return nil, err
	}
	validation, err := jsonObject(row.Validation)
	if err != nil {
		return nil, err
	}
	ca, err := jsonObject(row.ChangeAnnotations)
	if err != nil {
		return nil, err
	}
	if ca == nil {
		ca = map[string]any{} // legacy serializer: change_annotations or {}
	}

	svs, svsType, err := resultSVS(row.Unit, nonNullFloats(row.Data), row.Error != nil)
	if err != nil {
		return nil, err
	}

	return &ResultDetail{
		ID:                 row.ID,
		RunID:              row.RunID,
		RunTags:            runTags,
		RunReason:          row.RunReason,
		BatchID:            row.BatchID,
		Timestamp:          row.Timestamp,
		CommitRepoURL:      row.CommitRepoUrl,
		HistoryFingerprint: row.HistoryFingerprint,
		Tags:               tags,
		Context:            contextTags,
		Info:               infoTags,
		Hardware: Hardware{
			ID:   row.HardwareID,
			Type: row.HardwareType,
			Name: row.HardwareName,
			Hash: row.HardwareHash,
		},
		Commit:       commitFromRow(row),
		Unit:         row.Unit,
		LessIsBetter: lessIsBetterPtr(row.Unit),
		TimeUnit:     row.TimeUnit,
		Iterations:   row.Iterations,
		Data:         row.Data,
		Times:        row.Times,
		Stats: Aggregates{
			Mean: row.Mean, Min: row.Min, Max: row.Max, Median: row.Median,
			Q1: row.Q1, Q3: row.Q3, Stdev: row.Stdev, Iqr: row.Iqr,
		},
		Error:                 errObj,
		OptionalBenchmarkInfo: obi,
		Validation:            validation,
		ChangeAnnotations:     ca,
		SVS:                   svs,
		SVSType:               svsType,
	}, nil
}

// History returns the membership-filtered series for a fingerprint, each sample
// carrying its rolling-statistics block. The block is null for every sample when
// the series spans more than one unit (rolling stats across incompatible scales
// are meaningless).
func (r *Reader) History(ctx context.Context, fingerprint string) (*HistorySeries, error) {
	rows, err := r.store.SelectHistoryForFingerprint(ctx, fingerprint)
	if err != nil {
		return nil, fmt.Errorf("select history: %w", err)
	}
	samples := make([]HistorySample, 0, len(rows))
	points := make([]stats.SeriesPoint, 0, len(rows))
	singleUnit := true
	var firstUnit *string
	for i, row := range rows {
		svs, svsType, err := historySVS(row.Unit, row.Data)
		if err != nil {
			return nil, err
		}
		point, err := seriesPointFromRow(row, svs)
		if err != nil {
			return nil, err
		}
		points = append(points, point)
		samples = append(samples, HistorySample{
			BenchmarkResultID: row.ID,
			ResultTimestamp:   row.Timestamp,
			Mean:              row.Mean,
			SVS:               svs,
			SVSType:           svsType,
			Unit:              row.Unit,
			HardwareHash:      row.HardwareHash,
			CommitHash:        row.CommitSha,
			CommitRepository:  row.CommitRepository,
			CommitMessage:     row.CommitMessage,
			CommitTimestamp:   row.CommitTimestamp,
		})
		if i == 0 {
			firstUnit = row.Unit
		} else if !sameUnitPtr(firstUnit, row.Unit) {
			singleUnit = false
		}
	}
	if singleUnit && len(samples) > 0 {
		rolling := stats.RollingStatsForSeries(points, false, stats.DistributionCommitsDefault)
		for i := range samples {
			samples[i].ZScoreStats = zscoreStatsFrom(rolling[i])
		}
	}
	return &HistorySeries{HistoryFingerprint: fingerprint, Samples: samples}, nil
}

// HistoryForResult loads a result, then returns the history series for its
// fingerprint. The result itself need not be a member (it may be errored).
func (r *Reader) HistoryForResult(ctx context.Context, id string) (*HistorySeries, error) {
	row, err := r.store.GetBenchmarkResultByID(ctx, id)
	if err != nil {
		if errors.Is(err, storage.ErrNotFound) {
			return nil, ErrNotFound
		}
		return nil, fmt.Errorf("load result: %w", err)
	}
	return r.History(ctx, row.HistoryFingerprint)
}

// commitFromRow builds the commit subset, or nil when the result has no commit.
func commitFromRow(row storage.ResultDetailRow) *Commit {
	if row.CommitID == nil {
		return nil
	}
	return &Commit{
		ID:         *row.CommitID,
		Sha:        derefString(row.CommitSha),
		Repository: derefString(row.CommitRepository),
		Message:    derefString(row.CommitMessage),
		Timestamp:  row.CommitTimestamp,
	}
}

// lessIsBetterPtr derives the unit's orientation, returning nil for a null or
// unrecognized unit so an errored result with an unvalidated raw unit never 500s.
func lessIsBetterPtr(unit *string) *bool {
	if unit == nil {
		return nil
	}
	lib, err := units.LessIsBetter(*unit)
	if err != nil {
		return nil
	}
	return &lib
}

// resultSVS computes a result's single value summary. The type is always
// derivable from the unit; the value is nil for an errored result or one with no
// measurements.
func resultSVS(unit *string, data []float64, errored bool) (*float64, string, error) {
	if errored || len(data) == 0 {
		// A failed or measurement-less result has no single value. Its unit is
		// stored raw and may be unrecognized (errored results skip unit
		// validation), so a failed direction lookup must not fail the read: fall
		// back to the "n/a" type rather than returning an error.
		svsType, err := stats.SVSType(unit, defaultSVSMode)
		if err != nil {
			svsType = "n/a"
		}
		return nil, svsType, nil
	}
	svsType, err := stats.SVSType(unit, defaultSVSMode)
	if err != nil {
		return nil, "", err
	}
	v, err := stats.SingleValueSummary(data, unit, defaultSVSMode)
	if err != nil {
		return nil, "", err
	}
	return &v, svsType, nil
}

// historySVS computes a history point's single value summary. Membership
// guarantees a non-errored result with data, so the value is never null; an
// empty-data row would be a data-integrity error rather than a valid point.
func historySVS(unit *string, data []float64) (float64, string, error) {
	svsType, err := stats.SVSType(unit, defaultSVSMode)
	if err != nil {
		return 0, "", err
	}
	v, err := stats.SingleValueSummary(data, unit, defaultSVSMode)
	if err != nil {
		return 0, "", err
	}
	if math.IsNaN(v) {
		return 0, "", fmt.Errorf("history sample has no single value summary (empty data)")
	}
	return v, svsType, nil
}

// jsonObject decodes a jsonb column into a map, returning nil for a NULL column.
func jsonObject(b []byte) (map[string]any, error) {
	if len(b) == 0 {
		return nil, nil
	}
	var m map[string]any
	if err := json.Unmarshal(b, &m); err != nil {
		return nil, fmt.Errorf("decode json object: %w", err)
	}
	return m, nil
}

func derefString(s *string) string {
	if s == nil {
		return ""
	}
	return *s
}
