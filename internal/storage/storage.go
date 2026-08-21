// Package storage defines the persistence port the service layer depends on: the
// Store interface, its data-transfer types, and the not-found sentinel. The
// service speaks these port types and never imports the concrete adapter or its
// driver, so the analysis core stays independent of the storage backend.
// internal/db is the Postgres/sqlc adapter that implements Store.
//
// The DTOs are deliberately persistence-shaped, not API-shaped: jsonb columns
// are raw []byte, related entities are flat columns, and absent values are
// nil pointers. The service assembles the API responses (decoding JSON,
// computing the single value summary, nesting hardware/commit) from these rows.
package storage

import (
	"context"
	"errors"
	"time"
)

// ErrNotFound is returned by the single-row lookups when the requested row does
// not exist. The adapter maps its driver's no-rows signal to this sentinel so
// the service never sees a backend-specific error; the service maps it in turn
// to its own not-found error for the API layer.
var ErrNotFound = errors.New("storage: entity not found")

// ErrConflict marks a unique submission-key race that the service resolves by lookup.
var ErrConflict = errors.New("storage: entity conflict")

// Store is the persistence port: the get-or-create operations and reads the
// ingestion and read services need. Implementations own primary-key generation,
// so the insert-params types below carry no ID.
type Store interface {
	GetOrCreateCase(ctx context.Context, name string, tags []byte) (string, error)
	GetOrCreateContext(ctx context.Context, tags []byte) (string, error)
	GetOrCreateInfo(ctx context.Context, tags []byte) (string, error)
	GetOrCreateHardware(ctx context.Context, p InsertHardwareParams) (string, error)
	GetOrCreateCommit(ctx context.Context, p InsertCommitParams) (string, error)
	// GetCommitID returns the id of the commit row with the given sha and
	// (normalized) repository URL. Missing row -> ErrNotFound. The ingester
	// uses it to short-circuit GitHub enrichment for known commits.
	GetCommitID(ctx context.Context, sha, repository string) (string, error)
	InsertBenchmarkResult(ctx context.Context, p InsertBenchmarkResultParams) (string, error)
	GetBenchmarkResultBySubmissionKey(ctx context.Context, key string) (SubmissionResult, error)
	// UpdateBenchmarkResultChangeAnnotations replaces the change_annotations
	// column with the service-computed merged object. Missing row -> ErrNotFound.
	UpdateBenchmarkResultChangeAnnotations(ctx context.Context, id string, changeAnnotations []byte) error
	// DeleteBenchmarkResult hard-deletes one result row. Missing row -> ErrNotFound.
	DeleteBenchmarkResult(ctx context.Context, id string) error
	GetBenchmarkResultByID(ctx context.Context, id string) (BenchmarkResult, error)
	GetBenchmarkResultDetail(ctx context.Context, id string) (ResultDetailRow, error)
	SelectHistoryForFingerprint(ctx context.Context, fingerprint string) ([]HistoryRow, error)
	SelectHistoryForFingerprintAsOf(ctx context.Context, fingerprint string, asOf time.Time) ([]HistoryRow, error)
	GetResultForCompare(ctx context.Context, id string) (CompareResultRow, error)
	SelectBenchmarkResults(ctx context.Context, p ListResultsParams) ([]ResultListRow, error)
	SelectRecentRuns(ctx context.Context, p RecentRunsParams) ([]RecentRunRow, error)
	SelectRecentRunRepositories(ctx context.Context) ([]RecentRunRepositoryRow, error)
	SelectSeriesPage(ctx context.Context, p SeriesListParams) ([]SeriesPageRow, error)
	SelectSeriesMembers(ctx context.Context, fingerprints []string) ([]HistoryRow, error)
	SelectCIReportRunsByCommit(ctx context.Context, repository, sha string) ([]CIReportRunRow, error)
	SelectCIReportRunsByIDs(ctx context.Context, runIDs []string) ([]CIReportRunRow, error)
	GetCIReportCommit(ctx context.Context, repository, sha string) (CIReportCommitRow, error)
	SelectLatestDefaultCommit(ctx context.Context, repository string) (CIReportCommitRow, error)
	SelectCIReportBaselineAncestry(ctx context.Context, repository, sha string, limit int32) ([]CIReportCommitRow, error)
	CountCIReportRows(ctx context.Context, runs []CIReportRunKey) (int64, error)
	SelectCIReportRows(ctx context.Context, runs []CIReportRunKey, baselineRuns []CIReportRunKey) ([]CIReportResultRow, error)
	CountBenchmarkResults(ctx context.Context) (int64, error)
}

// InsertHardwareParams is the natural-key and payload columns for get-or-create
// of a hardware row. The caller supplies the precomputed Hash; the adapter
// generates the primary key.
type InsertHardwareParams struct {
	Type              string
	Name              string
	Hash              string
	ArchitectureName  *string
	KernelName        *string
	OsName            *string
	OsVersion         *string
	CpuModelName      *string
	CpuL1dCacheBytes  *int32
	CpuL1iCacheBytes  *int32
	CpuL2CacheBytes   *int32
	CpuL3CacheBytes   *int32
	CpuCoreCount      *int32
	CpuThreadCount    *int32
	CpuFrequencyMaxHz *int64
	MemoryBytes       *int64
	GpuCount          *int32
	GpuProductNames   []string
	Info              []byte
	OptionalInfo      []byte
}

// InsertCommitParams is the columns for get-or-create of a commit row, keyed on
// (Sha, Repository). The adapter generates the primary key.
type InsertCommitParams struct {
	Sha          string
	Parent       *string
	Repository   string
	Message      string
	AuthorName   string
	AuthorLogin  *string
	AuthorAvatar *string
	Timestamp    *time.Time
	Branch       *string
	ForkPointSha *string
}

// UnknownCommitCandidateParams bounds the repair scan for commit rows that were
// first inserted without Git metadata. Repository and cursor values are already
// normalized by callers; the storage adapter matches stored values exactly.
type UnknownCommitCandidateParams struct {
	Repository      *string
	AfterRepository *string
	AfterSha        *string
	LimitPlusOne    int32
}

// UnknownCommitCandidate is the minimal key material needed by the repair
// worker to look up commit metadata externally.
type UnknownCommitCandidate struct {
	ID         string
	Sha        string
	Repository string
}

// UpdateUnknownCommitParams is the metadata payload for defensively filling an
// unknown commit row. The adapter only updates rows that are still unknown.
type UpdateUnknownCommitParams struct {
	ID           string
	Parent       *string
	Message      string
	AuthorName   string
	AuthorLogin  *string
	AuthorAvatar *string
	Timestamp    time.Time
	Branch       *string
	ForkPointSha *string
}

// InsertBenchmarkResultParams is the columns for a new benchmark_result row.
// The adapter generates the primary key, so callers leave it out.
type InsertBenchmarkResultParams struct {
	CaseID                  string
	ContextID               string
	InfoID                  string
	HardwareID              string
	RunID                   string
	RunTags                 []byte
	RunReason               *string
	CommitID                *string
	CommitRepoUrl           string
	HistoryFingerprint      string
	Timestamp               time.Time
	Unit                    *string
	TimeUnit                *string
	BatchID                 *string
	Iterations              *int32
	Error                   []byte
	Data                    []*float64
	Times                   []*float64
	Mean                    *float64
	Min                     *float64
	Max                     *float64
	Median                  *float64
	Q1                      *float64
	Q3                      *float64
	Stdev                   *float64
	Iqr                     *float64
	Validation              []byte
	OptionalBenchmarkInfo   []byte
	ChangeAnnotations       []byte
	SubmissionKey           *string
	SubmissionPayloadSHA256 *string
}

// SubmissionResult is the replay identity stored for an idempotency key.
type SubmissionResult struct {
	ID                 string
	RunID              string
	HistoryFingerprint string
	PayloadSHA256      string
}

// APIToken is a row of the api_token table: a user-attributed write-auth
// credential. Only the SHA-256 hash and the 8-char display prefix of the
// secret are stored; the plaintext exists only at mint time.
type APIToken struct {
	ID          string
	UserID      string
	Name        string
	TokenHash   string
	TokenPrefix string
	CreatedAt   time.Time
	LastUsedAt  *time.Time
	RevokedAt   *time.Time
}

// InsertAPITokenParams is the columns for minting a token row. The adapter
// generates the primary key; revoked_at and last_used_at start NULL.
type InsertAPITokenParams struct {
	UserID      string
	Name        string
	TokenHash   string
	TokenPrefix string
	CreatedAt   time.Time
}

const (
	AlertRuleStateInactive = "inactive"
	AlertRuleStateOpen     = "open"

	AlertEventKindOpened   = "opened"
	AlertEventKindResolved = "resolved"

	AlertDeliveryStatusPending   = "pending"
	AlertDeliveryStatusDelivered = "delivered"
	AlertDeliveryStatusFailed    = "failed"
)

// AlertRule is a user-owned scheduled alert configuration. Evaluation reuses
// CI-report baseline and threshold semantics; delivery integrations are kept
// outside this first persisted state model.
type AlertRule struct {
	ID              string
	UserID          string
	Name            string
	Repository      string
	Baseline        string
	Threshold       float64
	ThresholdZ      float64
	RunReason       *string
	Enabled         bool
	State           string
	CreatedAt       time.Time
	UpdatedAt       time.Time
	LastEvaluatedAt *time.Time
}

// InsertAlertRuleParams is the column payload for creating an alert rule. The
// data layer generates ID; State starts inactive and LastEvaluatedAt starts nil.
type InsertAlertRuleParams struct {
	UserID     string
	Name       string
	Repository string
	Baseline   string
	Threshold  float64
	ThresholdZ float64
	RunReason  *string
	Enabled    bool
	CreatedAt  time.Time
}

// UpdateAlertRuleParams replaces the editable fields of a user-owned rule.
// Missing or wrong-owner rows map to ErrNotFound.
type UpdateAlertRuleParams struct {
	ID         string
	UserID     string
	Name       string
	Repository string
	Baseline   string
	Threshold  float64
	ThresholdZ float64
	RunReason  *string
	Enabled    bool
	UpdatedAt  time.Time
	// ResetEvaluation clears stale state when the selector or thresholds change.
	ResetEvaluation bool
}

// UpdateAlertRuleEvaluationParams records an evaluation timestamp and current
// state after the evaluator has decided whether an alert is open or inactive.
type UpdateAlertRuleEvaluationParams struct {
	ID          string
	State       string
	EvaluatedAt time.Time
}

// TouchAlertRuleEvaluationParams records an evaluation timestamp only when the
// evaluator's rule snapshot still matches the persisted enabled rule.
type TouchAlertRuleEvaluationParams struct {
	ID          string
	State       string
	Repository  string
	Baseline    string
	Threshold   float64
	ThresholdZ  float64
	RunReason   *string
	EvaluatedAt time.Time
}

type AlertRuleTouch struct {
	Rule    AlertRule
	Touched bool
}

// AlertEvent records alert state transitions for audit/history and future
// notification delivery. It intentionally stores a compact summary rather than
// the full CI report payload.
type AlertEvent struct {
	ID           string
	RuleID       string
	Kind         string
	Status       string
	StatusReason string
	RunID        *string
	CommitSHA    *string
	Repository   string
	ReportURL    string
	Summary      []byte
	CreatedAt    time.Time
}

// InsertAlertEventParams is the column payload for an alert state-transition
// event. The adapter generates ID.
type InsertAlertEventParams struct {
	RuleID       string
	Kind         string
	Status       string
	StatusReason string
	RunID        *string
	CommitSHA    *string
	ReportURL    string
	Summary      []byte
	CreatedAt    time.Time
}

// TransitionAlertRuleParams atomically changes a rule state and records the
// state-transition event only if the rule is still in FromState.
type TransitionAlertRuleParams struct {
	ID           string
	FromState    string
	ToState      string
	Repository   string
	Baseline     string
	Threshold    float64
	ThresholdZ   float64
	RunReason    *string
	EventKind    string
	Status       string
	StatusReason string
	RunID        *string
	CommitSHA    *string
	ReportURL    string
	Summary      []byte
	EvaluatedAt  time.Time
}

type AlertRuleTransition struct {
	Rule         AlertRule
	Event        *AlertEvent
	Transitioned bool
}

type ListAlertEventsParams struct {
	RuleID string
	Limit  int32
}

type SelectLatestAlertRunParams struct {
	Repository string
	RunReason  *string
}

// AlertCandidateRun is the newest run selected for an enabled rule.
type AlertCandidateRun struct {
	RunID               string
	CommitSHA           string
	LastResultTimestamp time.Time
}

// AlertDelivery is the durable delivery ledger row for one alert event and one
// delivery target. The joined Event payload lets channel workers send without a
// second lookup.
type AlertDelivery struct {
	ID            string
	EventID       string
	Event         AlertEvent
	Channel       string
	Target        string
	Status        string
	AttemptCount  int32
	LastAttemptAt *time.Time
	NextAttemptAt *time.Time
	DeliveredAt   *time.Time
	LastError     *string
	CreatedAt     time.Time
	UpdatedAt     time.Time
}

// EnqueueAlertDeliveriesParams creates missing delivery rows for stored alert
// events and a single channel/target pair. Existing rows are left untouched so
// retries and delivered state remain idempotent.
type EnqueueAlertDeliveriesParams struct {
	Channel   string
	Target    string
	Limit     int32
	CreatedAt time.Time
}

// ClaimPendingAlertDeliveriesParams selects due deliveries and leases them in a
// single atomic statement. LeaseUntil is the timestamp claimed rows are hidden
// until; a sender that crashes before recording an outcome leaves the row
// re-eligible once the lease passes.
type ClaimPendingAlertDeliveriesParams struct {
	Channel    string
	Target     string
	Now        time.Time
	LeaseUntil time.Time
	Limit      int32
}

type MarkAlertDeliveryDeliveredParams struct {
	ID          string
	AttemptedAt time.Time
}

type MarkAlertDeliveryFailedParams struct {
	ID            string
	Error         string
	AttemptedAt   time.Time
	NextAttemptAt time.Time
}

// User is the subset of a "user" row the auth layer reads: identity for the
// session, never the password hash. Created on first OIDC login, matched by
// email thereafter.
type User struct {
	ID    string
	Email string
	Name  string
}

// BenchmarkResult is a stored result row read by primary key, with its foreign
// keys but no joins. The read service uses its history fingerprint to resolve a
// result's series; the persistence round-trip is also verified against it.
type BenchmarkResult struct {
	ID                      string
	CaseID                  string
	ContextID               string
	InfoID                  string
	HardwareID              string
	RunID                   string
	RunTags                 []byte
	RunReason               *string
	CommitID                *string
	CommitRepoUrl           string
	HistoryFingerprint      string
	Timestamp               time.Time
	Unit                    *string
	TimeUnit                *string
	BatchID                 *string
	Iterations              *int32
	Error                   []byte
	Data                    []*float64
	Times                   []*float64
	Mean                    *float64
	Min                     *float64
	Max                     *float64
	Median                  *float64
	Q1                      *float64
	Q3                      *float64
	Stdev                   *float64
	Iqr                     *float64
	Validation              []byte
	OptionalBenchmarkInfo   []byte
	ChangeAnnotations       []byte
	SubmissionKey           *string
	SubmissionPayloadSHA256 *string
}

// ResultDetailRow is a stored result joined to its case, context, info,
// hardware, and (optional) commit, for the result-detail read endpoint.
// Case/context/info/hardware are NOT NULL foreign keys; the commit columns are
// nil for a result submitted without a commit.
type ResultDetailRow struct {
	ID                    string
	RunID                 string
	RunTags               []byte
	RunReason             *string
	BatchID               *string
	Timestamp             time.Time
	CommitRepoUrl         string
	HistoryFingerprint    string
	Unit                  *string
	TimeUnit              *string
	Iterations            *int32
	Error                 []byte
	Data                  []*float64
	Times                 []*float64
	Mean                  *float64
	Min                   *float64
	Max                   *float64
	Median                *float64
	Q1                    *float64
	Q3                    *float64
	Stdev                 *float64
	Iqr                   *float64
	Validation            []byte
	OptionalBenchmarkInfo []byte
	ChangeAnnotations     []byte
	CaseName              string
	CaseTags              []byte
	ContextTags           []byte
	InfoTags              []byte
	HardwareID            string
	HardwareType          string
	HardwareName          string
	HardwareHash          string
	CommitID              *string
	CommitSha             *string
	CommitRepository      *string
	CommitMessage         *string
	CommitTimestamp       *time.Time
}

// HistoryRow is one member of a fingerprint's history series: a non-errored,
// default-branch, commit-joined result. The read service computes the plotted
// single value summary from Unit and Data. Data is dense ([]float64, not the
// nullable-element storage shape): membership excludes errored results, and only
// errored results can hold null elements.
type HistoryRow struct {
	ID                 string
	HistoryFingerprint string
	Timestamp          time.Time
	Unit               *string
	Mean               *float64
	Data               []float64
	ChangeAnnotations  []byte
	HardwareHash       string
	CommitSha          string
	CommitRepository   string
	CommitMessage      string
	CommitTimestamp    *time.Time
}

// CompareResultRow is the per-result input to the compare endpoint: SVS inputs,
// the history fingerprint, the run id, and the optional commit timestamp used as
// the baseline ancestry cutoff. CommitID/CommitTimestamp are nil for a result
// submitted without a commit.
type CompareResultRow struct {
	ID                 string
	RunID              string
	HistoryFingerprint string
	Unit               *string
	Data               []*float64
	Error              []byte
	CommitID           *string
	CommitTimestamp    *time.Time
}

// ListResultsParams is the filter + pagination input for the list endpoint. Nil
// filters are unconstrained; Cursor bounds id < Cursor; PageSize caps the rows.
type ListResultsParams struct {
	RunID     *string
	BatchID   *string
	RunReason *string
	Earliest  *time.Time
	Latest    *time.Time
	Cursor    *string
	PageSize  int32
}

// ResultListRow is the minimal per-item row for the list endpoint. The service
// computes the single value summary and has_error from Unit/Data/Error; the
// commit columns are nil for a result without a commit.
type ResultListRow struct {
	ID                 string
	RunID              string
	RunReason          *string
	RunTags            []byte
	BatchID            *string
	Timestamp          time.Time
	Unit               *string
	Data               []*float64
	Error              []byte
	HistoryFingerprint string
	CaseName           string
	CaseTags           []byte
	CommitSha          *string
	CommitRepository   *string
	CommitMessage      *string
	CommitAuthorName   *string
	CommitAuthorLogin  *string
	CommitAuthorAvatar *string
	CommitTimestamp    *time.Time
}

// RecentRunsParams bounds the landing-page run summary. CandidateResultCount
// is the number of newest benchmark_result rows to scan for run IDs before
// exact aggregation of the selected runs.
type RecentRunsParams struct {
	CandidateResultCount int32
	PageSize             int32
	Repository           *string
}

// RecentRunRepositoryRow is one repository with benchmark results for the home
// page project selector.
type RecentRunRepositoryRow struct {
	Repository string
}

// RecentRunRow is one grouped run for the landing dashboard. Counts are exact
// for the returned run IDs; commit columns are nil when the latest result in the
// run was submitted without commit metadata.
type RecentRunRow struct {
	RunID              string
	FirstResultAt      time.Time
	LastResultAt       time.Time
	ResultCount        int64
	ErrorCount         int64
	SeriesCount        int64
	BatchCount         int64
	LatestResultID     string
	RunReason          *string
	RunTags            []byte
	LatestBatchID      *string
	Repository         string
	CommitSha          *string
	CommitRepository   *string
	CommitMessage      *string
	CommitAuthorName   *string
	CommitAuthorLogin  *string
	CommitAuthorAvatar *string
	CommitTimestamp    *time.Time
}

// SeriesListParams filters and paginates the series list. Nil filters are
// unconstrained; the cursor bounds the (commit timestamp, fingerprint) pair
// under the list's (timestamp DESC, fingerprint DESC) total order.
type SeriesListParams struct {
	Q           *string
	Hardware    *string
	Repository  *string
	Fingerprint *string
	ActiveSince *time.Time
	ActiveUntil *time.Time
	CursorTs    *time.Time
	CursorFp    *string
	PageSize    int32
}

// SeriesPageRow is one series in the list: identity plus the newest-commit
// member of its history. Membership is the same as HistoryRow (non-errored,
// default-branch, commit-joined with a non-null commit timestamp), so
// LatestCommitTimestamp is always present. CaseTags/ContextTags are raw jsonb.
// LatestData/LatestUnit feed the latest single value summary; PointCount counts
// the members. The service derives status and assembles the API shape.
// LatestData is dense ([]float64, not the nullable-element storage shape):
// membership excludes errored results, and only errored results can hold null
// elements.
type SeriesPageRow struct {
	HistoryFingerprint    string
	LatestResultID        string
	LatestResultTimestamp time.Time
	LatestCommitSha       string
	LatestCommitTimestamp time.Time
	CommitRepoUrl         string
	LatestUnit            *string
	LatestData            []float64
	PointCount            int64
	CaseName              string
	CaseTags              []byte
	ContextTags           []byte
	HardwareID            string
	HardwareName          string
	HardwareType          string
	HardwareHash          string
}

// CIReportRunRow is one distinct benchmark run selected for PR/CI reporting,
// with the contender commit metadata needed to resolve baseline candidates.
type CIReportRunRow struct {
	RunID              string
	RunTags            []byte
	RunReason          *string
	CommitRepoURL      string
	CommitID           *string
	CommitSha          *string
	CommitRepository   *string
	CommitParent       *string
	CommitForkPointSha *string
	CommitTimestamp    *time.Time
}

// CIReportRunKey identifies the selected result rows for a run on one exact
// commit. run_id alone is not unique across commits in existing Conbench data.
type CIReportRunKey struct {
	RunID    string
	CommitID string
}

// CIReportCommitRow is commit metadata used while resolving CI report baseline
// candidates. Timestamp stays nullable because unknown commits are persisted.
type CIReportCommitRow struct {
	CommitID     string
	CommitSha    string
	Repository   string
	Parent       *string
	ForkPointSha *string
	Timestamp    *time.Time
	Message      string
}

// CIReportResultRow is a report result joined to display identity, hardware,
// and optional commit metadata. The service compares rows by run_id and
// history_fingerprint, decodes JSON, and computes single value summaries.
type CIReportResultRow struct {
	ResultID           string
	RunID              string
	ResultTimestamp    time.Time
	HistoryFingerprint string
	CaseName           string
	CaseTags           []byte
	ContextTags        []byte
	InfoTags           []byte
	HardwareID         string
	HardwareType       string
	HardwareName       string
	HardwareHash       string
	CommitID           *string
	CommitSha          *string
	CommitRepository   *string
	CommitParent       *string
	CommitForkPointSha *string
	CommitTimestamp    *time.Time
	Unit               *string
	Data               []*float64
	Error              []byte
}
