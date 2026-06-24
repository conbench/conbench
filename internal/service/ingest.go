package service

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"maps"
	"math"
	"strconv"

	"github.com/conbench/conbench/internal/commit"
	"github.com/conbench/conbench/internal/hardware"
	"github.com/conbench/conbench/internal/stats"
	"github.com/conbench/conbench/internal/storage"
	"github.com/conbench/conbench/internal/units"
)

// partialErrorStatus is the generic error Conbench records when a result's
// per-iteration data is missing or incomplete and the client gave no explicit
// error (benchmark_result.py: "Partial result: not all iterations completed").
const partialErrorStatus = "Partial result: not all iterations completed"

// ValidationError marks a request the client must fix. The API layer maps it to
// a 4xx response; everything else is treated as a server error.
type ValidationError struct {
	Message string
}

func (e *ValidationError) Error() string { return e.Message }

// Result is what a successful Submit returns: the new result's id and the
// fingerprint of the history series it belongs to.
type Result struct {
	ID                 string
	HistoryFingerprint string
}

// Ingester persists a submitted benchmark result. It composes the data layer
// (get-or-create of the related entities, the result insert), the stats/units/
// hardware ports, and a commit provider. It is the Go port of the legacy
// BenchmarkResult.create behavior.
type Ingester struct {
	store   storage.Store
	commits commit.Provider
}

// NewIngester builds an Ingester over a store and a commit provider.
func NewIngester(store storage.Store, commits commit.Provider) *Ingester {
	return &Ingester{store: store, commits: commits}
}

// Submit validates and persists one result, returning its id and history
// fingerprint. The flow mirrors the legacy create(): validate the hardware and
// stats/error presence, split the tags into the case name and the case
// permutation, resolve the stats branch (success aggregation, explicit error, or
// partial-data error), get-or-create the related entities, resolve the commit,
// compute the fingerprint, and insert the result row.
func (i *Ingester) Submit(ctx context.Context, req SubmitRequest) (*Result, error) {
	if err := validateHardware(req); err != nil {
		return nil, err
	}
	if req.Error.Present && req.Error.Null {
		return nil, &ValidationError{Message: "error: null is not allowed; omit the field or send an object"}
	}
	if req.Stats == nil && !req.Error.Present {
		return nil, &ValidationError{Message: "either stats or error field is required"}
	}

	name, caseTags, err := splitTags(req.Tags)
	if err != nil {
		return nil, err
	}
	rs, err := resolveStats(req)
	if err != nil {
		return nil, err
	}

	caseTagsJSON, err := json.Marshal(caseTags)
	if err != nil {
		return nil, fmt.Errorf("marshal case tags: %w", err)
	}
	contextJSON, err := marshalMapOrEmpty(req.Context)
	if err != nil {
		return nil, fmt.Errorf("marshal context: %w", err)
	}
	infoJSON, err := marshalMapOrEmpty(req.Info)
	if err != nil {
		return nil, fmt.Errorf("marshal info: %w", err)
	}

	caseID, err := i.store.GetOrCreateCase(ctx, name, caseTagsJSON)
	if err != nil {
		return nil, fmt.Errorf("get-or-create case: %w", err)
	}
	contextID, err := i.store.GetOrCreateContext(ctx, contextJSON)
	if err != nil {
		return nil, fmt.Errorf("get-or-create context: %w", err)
	}
	infoID, err := i.store.GetOrCreateInfo(ctx, infoJSON)
	if err != nil {
		return nil, fmt.Errorf("get-or-create info: %w", err)
	}

	hwParams, hwHash, err := buildHardware(req)
	if err != nil {
		return nil, err
	}
	hardwareID, err := i.store.GetOrCreateHardware(ctx, hwParams)
	if err != nil {
		return nil, fmt.Errorf("get-or-create hardware: %w", err)
	}

	repoURL := commit.NormalizeRepoURL(req.GitHub.Repository)
	commitID, err := i.resolveCommit(ctx, req)
	if err != nil {
		return nil, err
	}

	fingerprint := stats.HistoryFingerprint(caseID, contextID, hwHash, repoURL)

	ins, err := buildInsertParams(req, rs, insertRefs{
		caseID: caseID, contextID: contextID, infoID: infoID,
		hardwareID: hardwareID, commitID: commitID,
		repoURL: repoURL, fingerprint: fingerprint,
	})
	if err != nil {
		return nil, err
	}

	id, err := i.store.InsertBenchmarkResult(ctx, ins)
	if err != nil {
		return nil, fmt.Errorf("insert benchmark result: %w", err)
	}
	return &Result{ID: id, HistoryFingerprint: fingerprint}, nil
}

// insertRefs carries the resolved entity references the insert-params builder
// needs alongside the request and the resolved stats branch.
type insertRefs struct {
	caseID, contextID, infoID, hardwareID string
	commitID                              *string
	repoURL, fingerprint                  string
}

// buildInsertParams assembles the full column set for the result row: request
// passthroughs, the resolved stats branch, the annotation blobs, and the
// resolved entity references.
func buildInsertParams(req SubmitRequest, rs resolved, refs insertRefs) (storage.InsertBenchmarkResultParams, error) {
	var zero storage.InsertBenchmarkResultParams
	runTags, err := buildRunTags(req)
	if err != nil {
		return zero, fmt.Errorf("marshal run tags: %w", err)
	}
	validationJSON, err := marshalMapOrNil(req.Validation)
	if err != nil {
		return zero, fmt.Errorf("marshal validation: %w", err)
	}
	obiJSON, err := marshalMapOrNil(req.OptionalBenchmarkInfo)
	if err != nil {
		return zero, fmt.Errorf("marshal optional_benchmark_info: %w", err)
	}
	caJSON, err := json.Marshal(filterNullValues(req.ChangeAnnotations))
	if err != nil {
		return zero, fmt.Errorf("marshal change_annotations: %w", err)
	}

	ins := storage.InsertBenchmarkResultParams{
		CaseID:                refs.caseID,
		ContextID:             refs.contextID,
		InfoID:                refs.infoID,
		HardwareID:            refs.hardwareID,
		RunID:                 req.RunID,
		RunTags:               runTags,
		RunReason:             strOrNil(req.RunReason),
		CommitID:              refs.commitID,
		CommitRepoUrl:         refs.repoURL,
		HistoryFingerprint:    refs.fingerprint,
		Timestamp:             req.Timestamp.UTC(),
		Unit:                  rs.unit,
		TimeUnit:              rs.timeUnit,
		BatchID:               strOrNil(req.BatchID),
		Iterations:            rs.iterations,
		Error:                 rs.errorJSON,
		Data:                  rs.data,
		Times:                 rs.times,
		Validation:            validationJSON,
		OptionalBenchmarkInfo: obiJSON,
		ChangeAnnotations:     caJSON,
	}
	ins.Mean, ins.Min, ins.Max, ins.Median = rs.aggs.Mean, rs.aggs.Min, rs.aggs.Max, rs.aggs.Median
	ins.Q1, ins.Q3, ins.Stdev, ins.Iqr = rs.aggs.Q1, rs.aggs.Q3, rs.aggs.Stdev, rs.aggs.Iqr
	return ins, nil
}

// resolveCommit returns the commit row id for the request, or nil for a
// request with no sha (NULL commit_id, excluded from history). A (sha,
// repository) pair already in the database is reused with no provider call —
// known rows as-is, and previously-unknown rows stay unknown until the repair
// job (legacy parity, benchmark_result.py:1049-1056). Only on a miss does the
// provider run (and possibly hit GitHub), with the get-or-create absorbing
// insert races.
func (i *Ingester) resolveCommit(ctx context.Context, req SubmitRequest) (*string, error) {
	if req.GitHub.Commit == "" {
		return nil, nil
	}
	repoURL := commit.NormalizeRepoURL(req.GitHub.Repository)
	id, err := i.store.GetCommitID(ctx, req.GitHub.Commit, repoURL)
	if err == nil {
		return &id, nil
	}
	if !errors.Is(err, storage.ErrNotFound) {
		return nil, fmt.Errorf("look up commit: %w", err)
	}

	var branch string
	if req.GitHub.Branch != nil {
		branch = *req.GitHub.Branch
	}
	info, err := i.commits.Resolve(ctx, commit.Request{
		Commit:          req.GitHub.Commit,
		Repository:      req.GitHub.Repository,
		ResultTimestamp: req.Timestamp,
		Branch:          branch,
		PRNumber:        req.GitHub.PRNumber,
	})
	if err != nil {
		return nil, fmt.Errorf("resolve commit: %w", err)
	}
	if info == nil {
		return nil, nil
	}
	created, err := i.store.GetOrCreateCommit(ctx, storage.InsertCommitParams{
		Sha:          info.Sha,
		Parent:       info.Parent,
		Repository:   info.Repository,
		Message:      info.Message,
		AuthorName:   info.AuthorName,
		AuthorLogin:  info.AuthorLogin,
		AuthorAvatar: info.AuthorAvatar,
		Timestamp:    info.Timestamp,
		Branch:       info.Branch,
		ForkPointSha: info.ForkPointSha,
	})
	if err != nil {
		return nil, fmt.Errorf("get-or-create commit: %w", err)
	}
	return &created, nil
}

func validateHardware(req SubmitRequest) error {
	switch {
	case req.MachineInfo == nil && req.ClusterInfo == nil:
		return &ValidationError{Message: "either machine_info or cluster_info field is required"}
	case req.MachineInfo != nil && req.ClusterInfo != nil:
		return &ValidationError{Message: "machine_info and cluster_info fields can not be used at the same time"}
	}
	return nil
}

// buildHardware turns the request's machine or cluster info into insert params
// with the computed hash, ported from Machine/Cluster.generate_hash.
func buildHardware(req SubmitRequest) (storage.InsertHardwareParams, string, error) {
	if m := req.MachineInfo; m != nil {
		hash := hardware.MachineHash(m.Name, i32to64(m.GpuCount), i32to64(m.CpuCoreCount), i32to64(m.CpuThreadCount), m.MemoryBytes)
		gpuNames := m.GpuProductNames
		if gpuNames == nil {
			gpuNames = []string{} // legacy Machine.gpu_product_names defaults to []
		}
		return storage.InsertHardwareParams{
			Type:              "machine",
			Name:              m.Name,
			Hash:              hash,
			ArchitectureName:  m.ArchitectureName,
			KernelName:        m.KernelName,
			OsName:            m.OsName,
			OsVersion:         m.OsVersion,
			CpuModelName:      m.CpuModelName,
			CpuL1dCacheBytes:  m.CpuL1dCacheBytes,
			CpuL1iCacheBytes:  m.CpuL1iCacheBytes,
			CpuL2CacheBytes:   m.CpuL2CacheBytes,
			CpuL3CacheBytes:   m.CpuL3CacheBytes,
			CpuCoreCount:      m.CpuCoreCount,
			CpuThreadCount:    m.CpuThreadCount,
			CpuFrequencyMaxHz: m.CpuFrequencyMaxHz,
			MemoryBytes:       m.MemoryBytes,
			GpuCount:          m.GpuCount,
			GpuProductNames:   gpuNames,
		}, hash, nil
	}

	c := req.ClusterInfo
	infoMap := c.Info
	if infoMap == nil {
		infoMap = map[string]any{}
	}
	infoJSON, err := json.Marshal(infoMap)
	if err != nil {
		return storage.InsertHardwareParams{}, "", fmt.Errorf("marshal cluster info: %w", err)
	}
	hash, err := hardware.ClusterHash(c.Name, infoJSON)
	if err != nil {
		return storage.InsertHardwareParams{}, "", fmt.Errorf("cluster hash: %w", err)
	}
	var optJSON []byte
	if c.OptionalInfo != nil {
		optJSON, err = json.Marshal(c.OptionalInfo)
		if err != nil {
			return storage.InsertHardwareParams{}, "", fmt.Errorf("marshal cluster optional_info: %w", err)
		}
	}
	return storage.InsertHardwareParams{
		Type:         "cluster",
		Name:         c.Name,
		Hash:         hash,
		Info:         infoJSON,
		OptionalInfo: optJSON,
	}, hash, nil
}

// aggCols is the eight aggregate columns of a result row. The success path
// fills it from the computed stats; the error paths copy the user-given
// values verbatim (legacy stores the complete stats object before error
// handling, benchmark_result.py:209).
type aggCols struct {
	Mean, Min, Max, Median, Q1, Q3, Stdev, Iqr *float64
}

// resolved is the outcome of the stats/error branch: the columns to store.
// Errored and partial results keep the user's raw stats — data/times with
// null elements, unvalidated unit/time_unit, user aggregates; only the
// success path validates the unit and recomputes aggregates.
type resolved struct {
	errorJSON  []byte
	unit       *string
	timeUnit   *string
	iterations *int32
	data       []*float64
	times      []*float64
	aggs       aggCols
}

func userAggCols(s *StatsInput) aggCols {
	if s == nil {
		return aggCols{}
	}
	return aggCols{
		Mean: s.Mean, Min: s.Min, Max: s.Max, Median: s.Median,
		Q1: s.Q1, Q3: s.Q3, Stdev: s.Stdev, Iqr: s.Iqr,
	}
}

func computedAggCols(agg stats.Aggregates) aggCols {
	return aggCols{
		Mean: &agg.Mean, Min: agg.Min, Max: agg.Max, Median: agg.Median,
		Q1: agg.Q1, Q3: agg.Q3, Stdev: agg.Stdev, Iqr: agg.Iqr,
	}
}

// resolveStats ports the create() branch that decides success vs. error. The
// order matches the legacy: an explicit error key wins, then incomplete data is
// treated as a partial error, otherwise the samples are validated and aggregated.
func resolveStats(req SubmitRequest) (resolved, error) {
	var r resolved
	if req.Stats != nil {
		r.iterations = req.Stats.Iterations
		r.timeUnit = strOrNil(req.Stats.TimeUnit)
		r.data = req.Stats.Data
		r.times = req.Stats.Times
	}

	if req.Error.Present {
		errJSON, err := json.Marshal(req.Error.Value)
		if err != nil {
			return r, fmt.Errorf("marshal error: %w", err)
		}
		r.errorJSON = errJSON
		r.unit = rawUnit(req.Stats)
		r.aggs = userAggCols(req.Stats)
		return r, nil
	}

	// No explicit error means stats is present (validated by the caller).
	if looksLikeError(req.Stats.Data) {
		errJSON, err := json.Marshal(map[string]string{"status": partialErrorStatus})
		if err != nil {
			return r, fmt.Errorf("marshal partial error: %w", err)
		}
		r.errorJSON = errJSON
		r.unit = rawUnit(req.Stats)
		r.aggs = userAggCols(req.Stats)
		return r, nil
	}

	unit, err := units.LegacyConvert(req.Stats.Unit)
	if err != nil {
		return r, &ValidationError{Message: err.Error()}
	}
	r.unit = &unit

	// data is dense here (looksLikeError returned false); times stays as
	// given, nulls included — legacy stores it unvalidated even on success.
	samples := make([]float64, len(req.Stats.Data))
	for idx, d := range req.Stats.Data {
		samples[idx] = *d
	}
	agg := stats.Aggregate(samples)
	r.aggs = computedAggCols(agg)
	return r, nil
}

// looksLikeError ports do_iteration_samples_look_like_error: an empty data slice,
// or any null element, marks the result as a partial-data error.
func looksLikeError(data []*float64) bool {
	if len(data) == 0 {
		return true
	}
	for _, d := range data {
		if d == nil {
			return true
		}
	}
	return false
}

// nonNullFloats returns the slice as []float64 when every element is present,
// else nil (a null element has no single value, so the SVS callers treat the
// result as measurement-less).
func nonNullFloats(xs []*float64) []float64 {
	if len(xs) == 0 {
		return nil
	}
	out := make([]float64, len(xs))
	for i, x := range xs {
		if x == nil {
			return nil
		}
		out[i] = *x
	}
	return out
}

// rawUnit returns the user-given unit unchanged (no validation), used for errored
// results which legacy stores without unit conversion.
func rawUnit(s *StatsInput) *string {
	if s == nil {
		return nil
	}
	return strOrNil(s.Unit)
}

// splitTags ports validate_and_augment_result_tags + the create() name pop: the
// "name" tag becomes the case name and is removed from the stored permutation;
// empty/null values are dropped, primitive values are stringified Python-style,
// and array/object values are rejected.
func splitTags(tags map[string]any) (string, map[string]any, error) {
	if _, ok := tags["name"]; !ok {
		return "", nil, &ValidationError{Message: "`name` property must be present in `tags`"}
	}
	out := make(map[string]any, len(tags))
	for k, v := range tags {
		if k == "" {
			return "", nil, &ValidationError{Message: "tags: zero-length string as key is not allowed"}
		}
		s, drop, err := stringifyTagValue(k, v)
		if err != nil {
			return "", nil, err
		}
		if drop {
			continue
		}
		out[k] = s
	}
	name, ok := out["name"]
	if !ok {
		return "", nil, &ValidationError{Message: "`name` tag must be a non-empty value"}
	}
	delete(out, "name")
	return name.(string), out, nil
}

// stringifyTagValue applies the legacy tag value rules: empty string and null are
// dropped; bool/number are stringified the way Python's str() would; strings pass
// through; arrays and objects are rejected.
func stringifyTagValue(key string, v any) (string, bool, error) {
	switch x := v.(type) {
	case nil:
		return "", true, nil
	case string:
		if x == "" {
			return "", true, nil
		}
		return x, false, nil
	case bool:
		if x {
			return "True", false, nil
		}
		return "False", false, nil
	case json.Number:
		return x.String(), false, nil
	case int:
		return strconv.Itoa(x), false, nil
	case int32:
		return strconv.FormatInt(int64(x), 10), false, nil
	case int64:
		return strconv.FormatInt(x, 10), false, nil
	case float32:
		return formatNumber(float64(x)), false, nil
	case float64:
		return formatNumber(x), false, nil
	default:
		return "", false, &ValidationError{
			Message: fmt.Sprintf("tags: bad value type for key `%s`, JSON object and array is not allowed", key),
		}
	}
}

// formatNumber renders a JSON number as a tag string. Whole values format as
// integers (matching Python str(int)); fractional values use the shortest exact
// decimal. JSON decodes all numbers to float64, so an integer sent over the wire
// (the common case) round-trips as "2", not "2.0".
func formatNumber(f float64) string {
	if f == math.Trunc(f) && !math.IsInf(f, 0) && math.Abs(f) < 1e15 {
		return strconv.FormatInt(int64(f), 10)
	}
	return strconv.FormatFloat(f, 'g', -1, 64)
}

// buildRunTags merges run_name into run_tags under "name" when absent,
// matching the legacy divert. Legacy keys this on run_name presence, not
// non-emptiness (benchmark_result.py:274): an explicit empty-string run_name
// still lands. The column is NOT NULL, so an absent map becomes "{}".
func buildRunTags(req SubmitRequest) ([]byte, error) {
	rt := make(map[string]any, len(req.RunTags)+1)
	maps.Copy(rt, req.RunTags)
	if req.RunName != nil {
		if _, ok := rt["name"]; !ok {
			rt["name"] = *req.RunName
		}
	}
	return json.Marshal(rt)
}

func marshalMapOrEmpty(m map[string]any) ([]byte, error) {
	if m == nil {
		m = map[string]any{}
	}
	return json.Marshal(m)
}

// filterNullValues ports the create-time change_annotations rule
// (benchmark_result.py:283): drop null-valued keys. The caller marshals the
// result even when empty — the column always stores an object, never NULL.
func filterNullValues(m map[string]any) map[string]any {
	out := make(map[string]any, len(m))
	for k, v := range m {
		if v != nil {
			out[k] = v
		}
	}
	return out
}

// marshalMapOrNil keeps an absent object as a NULL column (contrast
// marshalMapOrEmpty, for NOT NULL jsonb columns).
func marshalMapOrNil(m map[string]any) ([]byte, error) {
	if m == nil {
		return nil, nil
	}
	return json.Marshal(m)
}

func i32to64(p *int32) *int64 {
	if p == nil {
		return nil
	}
	v := int64(*p)
	return &v
}

func strOrNil(s string) *string {
	if s == "" {
		return nil
	}
	return &s
}
