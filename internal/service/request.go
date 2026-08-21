// Package service holds the ingestion business logic the API and CLI sit on. It
// ports the legacy-shaped result subset over the sqlc data layer,
// stats/units/hardware ports, and the commit provider.
package service

import (
	"bytes"
	"encoding/json"
	"time"

	"github.com/danielgtaylor/huma/v2"
)

// SubmitRequest is the POST /api/results body: a subset of the legacy
// _BenchmarkResultCreateSchema, in the same shape (not a new simplified format).
type SubmitRequest struct {
	SubmissionKey string         `json:"submission_key,omitempty" maxLength:"255"`
	Tags          map[string]any `json:"tags"`
	Context       map[string]any `json:"context"`
	Info          map[string]any `json:"info,omitempty"`
	MachineInfo   *MachineInfo   `json:"machine_info,omitempty"`
	ClusterInfo   *ClusterInfo   `json:"cluster_info,omitempty"`
	GitHub        GitHubInfo     `json:"github"`
	RunID         string         `json:"run_id"`
	RunName       *string        `json:"run_name,omitempty"`
	RunTags       map[string]any `json:"run_tags,omitempty"`
	RunReason     string         `json:"run_reason,omitempty"`
	BatchID       string         `json:"batch_id,omitempty"`
	Timestamp     time.Time      `json:"timestamp"`
	Stats         *StatsInput    `json:"stats,omitempty"`
	Error         JSONObject     `json:"error,omitzero"`

	// The three annotation blobs accept an explicit null as "absent" (approved
	// deviation: legacy 400s on null, but the stored outcome is identical), so
	// the schema must advertise them as nullable or generated clients would
	// reject payloads the server accepts.
	OptionalBenchmarkInfo map[string]any `json:"optional_benchmark_info,omitempty" nullable:"true"`
	Validation            map[string]any `json:"validation,omitempty" nullable:"true"`
	ChangeAnnotations     map[string]any `json:"change_annotations,omitempty" nullable:"true"`
}

// JSONObject is an optional JSON object field that distinguishes absent,
// null, and object values. encoding/json yields a nil map for both an absent
// field and an explicit null, but the legacy API rejects `error: null`
// (marshmallow Dict refuses nulls) while treating any present object — even
// {} — as meaningful, so the request type needs the three-way distinction.
type JSONObject struct {
	Present bool
	Null    bool
	Value   map[string]any
}

// UnmarshalJSON records presence, then null-ness or the object value.
func (o *JSONObject) UnmarshalJSON(b []byte) error {
	o.Present = true
	if bytes.Equal(bytes.TrimSpace(b), []byte("null")) {
		o.Null = true
		return nil
	}
	return json.Unmarshal(b, &o.Value)
}

// MarshalJSON renders the tracked value back out (tests and tools that
// round-trip the request type).
func (o JSONObject) MarshalJSON() ([]byte, error) {
	if !o.Present || o.Null {
		return []byte("null"), nil
	}
	return json.Marshal(o.Value)
}

// Schema keeps the wire contract a plain JSON object; presence tracking is a
// decoding concern, not a schema one.
func (o JSONObject) Schema(_ huma.Registry) *huma.Schema {
	return &huma.Schema{Type: huma.TypeObject, AdditionalProperties: true}
}

// GitHubInfo is the commit context. Repository is required; Commit (the sha) is
// optional — when absent the result is stored with a NULL commit_id. Branch and
// PRNumber are hints for branch resolution: a non-empty branch wins over
// pr_number, which wins over the repo's default branch (legacy precedence,
// commit.py:445-453). Null and empty string both mean "not given".
type GitHubInfo struct {
	Commit     string  `json:"commit,omitempty"`
	Repository string  `json:"repository"`
	Branch     *string `json:"branch,omitempty" nullable:"true" doc:"Branch in org:branch form; only for non-default-branch runs outside PRs."`
	PRNumber   *int    `json:"pr_number,omitempty" nullable:"true" doc:"Pull request number; used to resolve the branch via the GitHub API."`
}

// StatsInput carries the per-iteration measurements. Data elements may be null
// (a missing iteration), which marks the result as a partial-result error.
type StatsInput struct {
	Data       []*float64 `json:"data"`
	Times      []*float64 `json:"times,omitempty"`
	Unit       string     `json:"unit,omitempty"`
	TimeUnit   string     `json:"time_unit,omitempty"`
	Iterations *int32     `json:"iterations,omitempty"`

	// User-given aggregates. The success path recomputes and ignores them
	// (validate_and_aggregate_samples nulls them, line 759); the error paths
	// store them verbatim (the |= copy, line 209).
	Min    *float64 `json:"min,omitempty"`
	Max    *float64 `json:"max,omitempty"`
	Mean   *float64 `json:"mean,omitempty"`
	Median *float64 `json:"median,omitempty"`
	Stdev  *float64 `json:"stdev,omitempty"`
	Q1     *float64 `json:"q1,omitempty"`
	Q3     *float64 `json:"q3,omitempty"`
	Iqr    *float64 `json:"iqr,omitempty"`
}

// MachineInfo mirrors the legacy machine_info object. All fields but the name
// are optional; they form the hardware dedup key and feed the machine hash.
type MachineInfo struct {
	Name              string   `json:"name"`
	ArchitectureName  *string  `json:"architecture_name,omitempty"`
	KernelName        *string  `json:"kernel_name,omitempty"`
	OsName            *string  `json:"os_name,omitempty"`
	OsVersion         *string  `json:"os_version,omitempty"`
	CpuModelName      *string  `json:"cpu_model_name,omitempty"`
	CpuL1dCacheBytes  *int32   `json:"cpu_l1d_cache_bytes,omitempty"`
	CpuL1iCacheBytes  *int32   `json:"cpu_l1i_cache_bytes,omitempty"`
	CpuL2CacheBytes   *int32   `json:"cpu_l2_cache_bytes,omitempty"`
	CpuL3CacheBytes   *int32   `json:"cpu_l3_cache_bytes,omitempty"`
	CpuCoreCount      *int32   `json:"cpu_core_count,omitempty"`
	CpuThreadCount    *int32   `json:"cpu_thread_count,omitempty"`
	CpuFrequencyMaxHz *int64   `json:"cpu_frequency_max_hz,omitempty"`
	MemoryBytes       *int64   `json:"memory_bytes,omitempty"`
	GpuCount          *int32   `json:"gpu_count,omitempty"`
	GpuProductNames   []string `json:"gpu_product_names,omitempty"`
}

// ClusterInfo mirrors the legacy cluster_info object.
type ClusterInfo struct {
	Name         string         `json:"name"`
	Info         map[string]any `json:"info"`
	OptionalInfo map[string]any `json:"optional_info,omitempty"`
}
