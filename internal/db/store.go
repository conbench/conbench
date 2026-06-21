package db

import (
	"context"
	"encoding/hex"
	"errors"
	"fmt"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"

	"github.com/conbench/conbench/internal/storage"
)

// Store composes the generated queries into the get-or-create operations the
// ingestion path needs, and owns primary-key generation. IDs are UUIDv7 encoded
// as a 32-character lowercase hex string (no dashes), matching the legacy
// Python genprimkey behavior (uuid7().hex), so rows stay sortable by insertion
// time. The data layer owns ID generation; callers leave the ID
// fields of the params structs zero.
type Store struct {
	q *Queries
}

const (
	// Narrow q searches use complete historical latest-per-fingerprint
	// semantics. Above this case count, production clones need bounded discovery
	// instead of full matched-history aggregation.
	seriesQCompleteCaseLimit = 64
	// Broad q searches walk a capped newest-commit window. The defaults keep the
	// web's page_size=10 search comfortably below the clone statement timeout,
	// while bounding large API page-size requests.
	seriesQRecentCommitMinLimit   = int32(320)
	seriesQRecentCommitMaxLimit   = int32(512)
	seriesQRecentCommitPageFactor = int32(32)
	// Default browse starts from recent result-bearing commits rather than a
	// global latest-per-fingerprint aggregation. Keep the window large enough to
	// page past repeated runs while staying interactive on production clones.
	seriesBrowseRecentCommitMinLimit   = int32(80)
	seriesBrowseRecentCommitMaxLimit   = int32(160)
	seriesBrowseRecentCommitPageFactor = int32(3)
	// Cursor and hardware-scoped browse need extra bounded lookahead because
	// already-emitted or repeated fingerprints are filtered after the candidate
	// commit window is selected. Keep the cap explicit so the browse query
	// remains bounded on production-sized history tables.
	seriesBrowseScopedCommitLimit = int32(512)
	// Browse/search row enrichment needs enough recent points for the 100-commit
	// stats window and sparkline, but full histories remain on history endpoints.
	seriesMembersTailLimit = int32(256)
)

// NewStore wraps anything satisfying DBTX (a *pgxpool.Pool, a connection, or a
// transaction).
func NewStore(db DBTX) *Store {
	return &Store{q: New(db)}
}

// genID returns a UUIDv7 as a 32-character lowercase hex string.
func genID() (string, error) {
	u, err := uuid.NewV7()
	if err != nil {
		return "", fmt.Errorf("generate id: %w", err)
	}
	return hex.EncodeToString(u[:]), nil
}

// getOrCreate runs the legacy get-or-create algorithm: select by natural key;
// if absent, insert with a fresh id; if the insert lost an ON CONFLICT DO
// NOTHING race (no row returned), re-select the winner. sel must return
// pgx.ErrNoRows when the row is absent.
func getOrCreate(
	ctx context.Context,
	sel func(context.Context) (string, error),
	ins func(ctx context.Context, id string) (string, error),
) (string, error) {
	id, err := sel(ctx)
	if err == nil {
		return id, nil
	}
	if !errors.Is(err, pgx.ErrNoRows) {
		return "", err
	}
	newID, err := genID()
	if err != nil {
		return "", err
	}
	id, err = ins(ctx, newID)
	if err == nil {
		return id, nil
	}
	if !errors.Is(err, pgx.ErrNoRows) {
		return "", err
	}
	// ON CONFLICT DO NOTHING raced: the row now exists, written by another tx.
	return sel(ctx)
}

// GetOrCreateCase returns the id of the case with this name and tags, inserting
// it if absent. tags is raw JSON (jsonb).
func (s *Store) GetOrCreateCase(ctx context.Context, name string, tags []byte) (string, error) {
	return getOrCreate(ctx,
		func(ctx context.Context) (string, error) {
			return s.q.GetCaseByNameTags(ctx, GetCaseByNameTagsParams{Name: name, Tags: tags})
		},
		func(ctx context.Context, id string) (string, error) {
			return s.q.InsertCase(ctx, InsertCaseParams{ID: id, Name: name, Tags: tags})
		},
	)
}

// GetOrCreateUserByEmail returns the id of the user with this email, inserting
// a row (with the given display name and an unusable password marker) if
// absent. The name and password of an existing row are left untouched — first
// write wins, matching the get-or-create semantics used for the other tables.
func (s *Store) GetOrCreateUserByEmail(ctx context.Context, email, name, password string) (string, error) {
	return getOrCreate(ctx,
		func(ctx context.Context) (string, error) {
			return s.q.GetUserByEmail(ctx, email)
		},
		func(ctx context.Context, id string) (string, error) {
			return s.q.InsertUser(ctx, InsertUserParams{ID: id, Email: email, Name: name, Password: password})
		},
	)
}

// GetUserByID returns the identity fields of a user, or storage.ErrNotFound.
func (s *Store) GetUserByID(ctx context.Context, id string) (storage.User, error) {
	row, err := s.q.GetUserByID(ctx, id)
	if errors.Is(err, pgx.ErrNoRows) {
		return storage.User{}, storage.ErrNotFound
	}
	if err != nil {
		return storage.User{}, err
	}
	return storage.User{ID: row.ID, Email: row.Email, Name: row.Name}, nil
}

// DeleteExpiredCLILoginCodes removes expired one-time CLI login codes.
func (s *Store) DeleteExpiredCLILoginCodes(ctx context.Context, now time.Time) error {
	return s.q.DeleteExpiredCLILoginCodes(ctx, now)
}

// InsertCLILoginCode stores the hash of a short-lived one-time CLI login code.
func (s *Store) InsertCLILoginCode(ctx context.Context, codeHash, userID string, createdAt, expiresAt time.Time) error {
	return s.q.InsertCLILoginCode(ctx, InsertCLILoginCodeParams{
		CodeHash:  codeHash,
		UserID:    userID,
		CreatedAt: createdAt,
		ExpiresAt: expiresAt,
	})
}

// RedeemCLILoginCode marks an unexpired CLI login code as used and returns its
// user id. ok is false when the code is unknown, expired, or already redeemed.
func (s *Store) RedeemCLILoginCode(ctx context.Context, codeHash string, now time.Time) (string, bool, error) {
	userID, err := s.q.RedeemCLILoginCode(ctx, RedeemCLILoginCodeParams{CodeHash: codeHash, RedeemedAt: &now})
	if errors.Is(err, pgx.ErrNoRows) {
		return "", false, nil
	}
	if err != nil {
		return "", false, err
	}
	return userID, true, nil
}

func (s *Store) CreateAlertRule(ctx context.Context, p storage.InsertAlertRuleParams) (storage.AlertRule, error) {
	id, err := genID()
	if err != nil {
		return storage.AlertRule{}, err
	}
	row, err := s.q.InsertAlertRule(ctx, InsertAlertRuleParams{
		ID:         id,
		UserID:     p.UserID,
		Name:       p.Name,
		Repository: p.Repository,
		Baseline:   p.Baseline,
		Threshold:  p.Threshold,
		ThresholdZ: p.ThresholdZ,
		RunReason:  p.RunReason,
		Enabled:    p.Enabled,
		CreatedAt:  p.CreatedAt,
	})
	if err != nil {
		return storage.AlertRule{}, err
	}
	return alertRuleFromRow(row), nil
}

func (s *Store) GetAlertRule(ctx context.Context, id string) (storage.AlertRule, error) {
	row, err := s.q.GetAlertRule(ctx, id)
	if errors.Is(err, pgx.ErrNoRows) {
		return storage.AlertRule{}, storage.ErrNotFound
	}
	if err != nil {
		return storage.AlertRule{}, err
	}
	return alertRuleFromRow(row), nil
}

func (s *Store) ListAlertRulesByUser(ctx context.Context, userID string) ([]storage.AlertRule, error) {
	rows, err := s.q.ListAlertRulesByUser(ctx, userID)
	if err != nil {
		return nil, err
	}
	return alertRulesFromRows(rows), nil
}

func (s *Store) ListEnabledAlertRules(ctx context.Context) ([]storage.AlertRule, error) {
	rows, err := s.q.ListEnabledAlertRules(ctx)
	if err != nil {
		return nil, err
	}
	return alertRulesFromRows(rows), nil
}

func (s *Store) UpdateAlertRule(ctx context.Context, p storage.UpdateAlertRuleParams) (storage.AlertRule, error) {
	row, err := s.q.UpdateAlertRule(ctx, UpdateAlertRuleParams{
		ID:              p.ID,
		UserID:          p.UserID,
		Name:            p.Name,
		Repository:      p.Repository,
		Baseline:        p.Baseline,
		Threshold:       p.Threshold,
		ThresholdZ:      p.ThresholdZ,
		RunReason:       p.RunReason,
		Enabled:         p.Enabled,
		UpdatedAt:       p.UpdatedAt,
		ResetEvaluation: p.ResetEvaluation,
	})
	if errors.Is(err, pgx.ErrNoRows) {
		return storage.AlertRule{}, storage.ErrNotFound
	}
	if err != nil {
		return storage.AlertRule{}, err
	}
	return alertRuleFromRow(row), nil
}

func (s *Store) DeleteAlertRule(ctx context.Context, id, userID string) error {
	n, err := s.q.DeleteAlertRule(ctx, DeleteAlertRuleParams{ID: id, UserID: userID})
	if err != nil {
		return err
	}
	if n == 0 {
		return storage.ErrNotFound
	}
	return nil
}

func (s *Store) UpdateAlertRuleEvaluation(
	ctx context.Context,
	p storage.UpdateAlertRuleEvaluationParams,
) (storage.AlertRule, error) {
	row, err := s.q.UpdateAlertRuleEvaluation(ctx, UpdateAlertRuleEvaluationParams{
		ID:              p.ID,
		State:           p.State,
		LastEvaluatedAt: &p.EvaluatedAt,
	})
	if errors.Is(err, pgx.ErrNoRows) {
		return storage.AlertRule{}, storage.ErrNotFound
	}
	if err != nil {
		return storage.AlertRule{}, err
	}
	return alertRuleFromRow(row), nil
}

func (s *Store) TouchAlertRuleEvaluation(
	ctx context.Context,
	p storage.TouchAlertRuleEvaluationParams,
) (storage.AlertRuleTouch, error) {
	row, err := s.q.TouchAlertRuleEvaluation(ctx, TouchAlertRuleEvaluationParams{
		EvaluatedAt: &p.EvaluatedAt,
		ID:          p.ID,
		State:       p.State,
		Repository:  p.Repository,
		Baseline:    p.Baseline,
		Threshold:   p.Threshold,
		ThresholdZ:  p.ThresholdZ,
		RunReason:   p.RunReason,
	})
	if errors.Is(err, pgx.ErrNoRows) {
		rule, getErr := s.GetAlertRule(ctx, p.ID)
		if getErr != nil {
			return storage.AlertRuleTouch{}, getErr
		}
		return storage.AlertRuleTouch{Rule: rule}, nil
	}
	if err != nil {
		return storage.AlertRuleTouch{}, err
	}
	return storage.AlertRuleTouch{Rule: alertRuleFromRow(row), Touched: true}, nil
}

func (s *Store) CreateAlertEvent(ctx context.Context, p storage.InsertAlertEventParams) (storage.AlertEvent, error) {
	id, err := genID()
	if err != nil {
		return storage.AlertEvent{}, err
	}
	row, err := s.q.InsertAlertEvent(ctx, InsertAlertEventParams{
		ID:           id,
		RuleID:       p.RuleID,
		Kind:         p.Kind,
		Status:       p.Status,
		StatusReason: p.StatusReason,
		RunID:        p.RunID,
		CommitSha:    p.CommitSHA,
		ReportUrl:    p.ReportURL,
		Summary:      p.Summary,
		CreatedAt:    p.CreatedAt,
	})
	if err != nil {
		return storage.AlertEvent{}, err
	}
	return alertEventFromRow(row), nil
}

func (s *Store) TransitionAlertRule(
	ctx context.Context,
	p storage.TransitionAlertRuleParams,
) (storage.AlertRuleTransition, error) {
	eventID, err := genID()
	if err != nil {
		return storage.AlertRuleTransition{}, err
	}
	row, err := s.q.TransitionAlertRule(ctx, TransitionAlertRuleParams{
		ID:           p.ID,
		FromState:    p.FromState,
		ToState:      p.ToState,
		Repository:   p.Repository,
		Baseline:     p.Baseline,
		Threshold:    p.Threshold,
		ThresholdZ:   p.ThresholdZ,
		RunReason:    p.RunReason,
		EventID:      eventID,
		Kind:         p.EventKind,
		Status:       p.Status,
		StatusReason: p.StatusReason,
		RunID:        p.RunID,
		CommitSha:    p.CommitSHA,
		ReportUrl:    p.ReportURL,
		Summary:      p.Summary,
		EvaluatedAt:  &p.EvaluatedAt,
	})
	if errors.Is(err, pgx.ErrNoRows) {
		rule, getErr := s.GetAlertRule(ctx, p.ID)
		if getErr != nil {
			return storage.AlertRuleTransition{}, getErr
		}
		return storage.AlertRuleTransition{Rule: rule}, nil
	}
	if err != nil {
		return storage.AlertRuleTransition{}, err
	}
	return alertTransitionFromRow(row), nil
}

func (s *Store) ListAlertEventsByRule(
	ctx context.Context,
	p storage.ListAlertEventsParams,
) ([]storage.AlertEvent, error) {
	rows, err := s.q.ListAlertEventsByRule(ctx, ListAlertEventsByRuleParams{RuleID: p.RuleID, Limit: p.Limit})
	if err != nil {
		return nil, err
	}
	return alertEventsFromRows(rows), nil
}

func (s *Store) SelectLatestAlertRun(
	ctx context.Context,
	p storage.SelectLatestAlertRunParams,
) (storage.AlertCandidateRun, error) {
	row, err := s.q.SelectLatestAlertRun(ctx, SelectLatestAlertRunParams{
		Repository: p.Repository,
		RunReason:  p.RunReason,
	})
	if errors.Is(err, pgx.ErrNoRows) {
		return storage.AlertCandidateRun{}, storage.ErrNotFound
	}
	if err != nil {
		return storage.AlertCandidateRun{}, err
	}
	return storage.AlertCandidateRun{
		RunID:               row.RunID,
		CommitSHA:           row.CommitSha,
		LastResultTimestamp: row.LastResultTimestamp,
	}, nil
}

func (s *Store) EnqueueAlertDeliveries(
	ctx context.Context,
	p storage.EnqueueAlertDeliveriesParams,
) (int, error) {
	rows, err := s.q.SelectAlertEventsWithoutDelivery(ctx, SelectAlertEventsWithoutDeliveryParams{
		Channel: p.Channel,
		Target:  p.Target,
		Limit:   p.Limit,
	})
	if err != nil {
		return 0, err
	}
	enqueued := 0
	for _, row := range rows {
		id, err := genID()
		if err != nil {
			return enqueued, err
		}
		_, err = s.q.InsertAlertDelivery(ctx, InsertAlertDeliveryParams{
			ID:        id,
			EventID:   row.ID,
			Channel:   p.Channel,
			Target:    p.Target,
			CreatedAt: p.CreatedAt,
		})
		if errors.Is(err, pgx.ErrNoRows) {
			continue
		}
		if err != nil {
			return enqueued, err
		}
		enqueued++
	}
	return enqueued, nil
}

func (s *Store) ClaimPendingAlertDeliveries(
	ctx context.Context,
	p storage.ClaimPendingAlertDeliveriesParams,
) ([]storage.AlertDelivery, error) {
	rows, err := s.q.ClaimPendingAlertDeliveries(ctx, ClaimPendingAlertDeliveriesParams{
		Channel:    p.Channel,
		Target:     p.Target,
		Now:        &p.Now,
		LeaseUntil: &p.LeaseUntil,
		Limit:      p.Limit,
	})
	if err != nil {
		return nil, err
	}
	return alertDeliveriesFromClaimedRows(rows), nil
}

func (s *Store) MarkAlertDeliveryDelivered(
	ctx context.Context,
	p storage.MarkAlertDeliveryDeliveredParams,
) (storage.AlertDelivery, error) {
	row, err := s.q.MarkAlertDeliveryDelivered(ctx, MarkAlertDeliveryDeliveredParams{
		ID:          p.ID,
		AttemptedAt: &p.AttemptedAt,
	})
	if errors.Is(err, pgx.ErrNoRows) {
		return storage.AlertDelivery{}, storage.ErrNotFound
	}
	if err != nil {
		return storage.AlertDelivery{}, err
	}
	return alertDeliveryFromRow(row), nil
}

func (s *Store) MarkAlertDeliveryFailed(
	ctx context.Context,
	p storage.MarkAlertDeliveryFailedParams,
) (storage.AlertDelivery, error) {
	row, err := s.q.MarkAlertDeliveryFailed(ctx, MarkAlertDeliveryFailedParams{
		ID:            p.ID,
		AttemptedAt:   &p.AttemptedAt,
		NextAttemptAt: &p.NextAttemptAt,
		LastError:     &p.Error,
	})
	if errors.Is(err, pgx.ErrNoRows) {
		return storage.AlertDelivery{}, storage.ErrNotFound
	}
	if err != nil {
		return storage.AlertDelivery{}, err
	}
	return alertDeliveryFromRow(row), nil
}

// GetOrCreateContext returns the id of the context with these tags.
func (s *Store) GetOrCreateContext(ctx context.Context, tags []byte) (string, error) {
	return getOrCreate(ctx,
		func(ctx context.Context) (string, error) {
			return s.q.GetContextByTags(ctx, tags)
		},
		func(ctx context.Context, id string) (string, error) {
			return s.q.InsertContext(ctx, InsertContextParams{ID: id, Tags: tags})
		},
	)
}

// GetOrCreateInfo returns the id of the info with these tags. info has no unique
// index, so a concurrent race may duplicate (the legacy code tolerates this).
func (s *Store) GetOrCreateInfo(ctx context.Context, tags []byte) (string, error) {
	return getOrCreate(ctx,
		func(ctx context.Context) (string, error) {
			return s.q.GetInfoByTags(ctx, tags)
		},
		func(ctx context.Context, id string) (string, error) {
			return s.q.InsertInfo(ctx, InsertInfoParams{ID: id, Tags: tags})
		},
	)
}

// GetOrCreateHardware returns the id of the hardware identified by the natural
// columns of p (everything except ID and Hash), inserting it if absent. The
// caller supplies the computed Hash; ID is generated here.
func (s *Store) GetOrCreateHardware(ctx context.Context, p storage.InsertHardwareParams) (string, error) {
	dbp := toInsertHardwareParams(p)
	sel := GetHardwareByNaturalKeyParams{
		Type:              dbp.Type,
		Name:              dbp.Name,
		ArchitectureName:  dbp.ArchitectureName,
		KernelName:        dbp.KernelName,
		OsName:            dbp.OsName,
		OsVersion:         dbp.OsVersion,
		CpuModelName:      dbp.CpuModelName,
		CpuL1dCacheBytes:  dbp.CpuL1dCacheBytes,
		CpuL1iCacheBytes:  dbp.CpuL1iCacheBytes,
		CpuL2CacheBytes:   dbp.CpuL2CacheBytes,
		CpuL3CacheBytes:   dbp.CpuL3CacheBytes,
		CpuCoreCount:      dbp.CpuCoreCount,
		CpuThreadCount:    dbp.CpuThreadCount,
		CpuFrequencyMaxHz: dbp.CpuFrequencyMaxHz,
		MemoryBytes:       dbp.MemoryBytes,
		GpuCount:          dbp.GpuCount,
		GpuProductNames:   dbp.GpuProductNames,
		Info:              dbp.Info,
		OptionalInfo:      dbp.OptionalInfo,
	}
	return getOrCreate(ctx,
		func(ctx context.Context) (string, error) {
			return s.q.GetHardwareByNaturalKey(ctx, sel)
		},
		func(ctx context.Context, id string) (string, error) {
			dbp.ID = id
			return s.q.InsertHardware(ctx, dbp)
		},
	)
}

// GetOrCreateCommit returns the id of the commit with p's (sha, repository),
// inserting it if absent. ID is generated here.
func (s *Store) GetOrCreateCommit(ctx context.Context, p storage.InsertCommitParams) (string, error) {
	dbp := toInsertCommitParams(p)
	return getOrCreate(ctx,
		func(ctx context.Context) (string, error) {
			return s.q.GetCommitByShaRepo(ctx, GetCommitByShaRepoParams{Sha: dbp.Sha, Repository: dbp.Repository})
		},
		func(ctx context.Context, id string) (string, error) {
			dbp.ID = id
			return s.q.InsertCommit(ctx, dbp)
		},
	)
}

// GetCommitID returns the id of the commit with (sha, repository), or
// storage.ErrNotFound when no such row exists.
func (s *Store) GetCommitID(ctx context.Context, sha, repository string) (string, error) {
	id, err := s.q.GetCommitByShaRepo(ctx, GetCommitByShaRepoParams{Sha: sha, Repository: repository})
	if errors.Is(err, pgx.ErrNoRows) {
		return "", storage.ErrNotFound
	}
	return id, err
}

// SelectUnknownCommitRepairCandidates returns commit rows that still need Git
// metadata repair. Repository and cursor values are matched exactly as supplied.
func (s *Store) SelectUnknownCommitRepairCandidates(
	ctx context.Context,
	p storage.UnknownCommitCandidateParams,
) ([]storage.UnknownCommitCandidate, error) {
	rows, err := s.q.SelectUnknownCommitRepairCandidates(ctx, SelectUnknownCommitRepairCandidatesParams{
		Repository:      p.Repository,
		AfterRepository: p.AfterRepository,
		AfterSha:        p.AfterSha,
		LimitPlusOne:    p.LimitPlusOne,
	})
	if err != nil {
		return nil, err
	}
	out := make([]storage.UnknownCommitCandidate, 0, len(rows))
	for _, row := range rows {
		out = append(out, storage.UnknownCommitCandidate{
			ID:         row.ID,
			Sha:        row.Sha,
			Repository: row.Repository,
		})
	}
	return out, nil
}

// UpdateUnknownCommit fills metadata for one still-unknown commit row and
// returns the affected row count. A row repaired by another worker is left
// untouched and reports zero rows affected.
func (s *Store) UpdateUnknownCommit(ctx context.Context, p storage.UpdateUnknownCommitParams) (int64, error) {
	return s.q.UpdateUnknownCommit(ctx, UpdateUnknownCommitParams{
		ID:           p.ID,
		Parent:       p.Parent,
		Message:      p.Message,
		AuthorName:   p.AuthorName,
		AuthorLogin:  p.AuthorLogin,
		AuthorAvatar: p.AuthorAvatar,
		Timestamp:    &p.Timestamp,
		Branch:       p.Branch,
		ForkPointSha: p.ForkPointSha,
	})
}

// LatestCommitTimestampOnBranch returns the newest commit timestamp on the
// given branch of the repository strictly before `before`, or nil when the
// branch has no tracked commits yet. The ancestry backfiller uses it as the
// `since` bound.
func (s *Store) LatestCommitTimestampOnBranch(ctx context.Context, repository, branch string, before time.Time) (*time.Time, error) {
	ts, err := s.q.GetLatestCommitTimestampOnBranch(ctx, GetLatestCommitTimestampOnBranchParams{
		Repository: repository, Branch: &branch, Timestamp: &before,
	})
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	return ts, err
}

// InsertBenchmarkResult inserts a result with a freshly generated id and returns
// it. Unlike the get-or-create helpers, every call inserts a new row.
func (s *Store) InsertBenchmarkResult(ctx context.Context, p storage.InsertBenchmarkResultParams) (string, error) {
	id, err := genID()
	if err != nil {
		return "", err
	}
	dbp := toInsertBenchmarkResultParams(p)
	dbp.ID = id
	return s.q.InsertBenchmarkResult(ctx, dbp)
}

// UpdateBenchmarkResultChangeAnnotations replaces the change_annotations
// column; the service computes the merged object. Missing row -> ErrNotFound.
func (s *Store) UpdateBenchmarkResultChangeAnnotations(ctx context.Context, id string, changeAnnotations []byte) error {
	_, err := s.q.UpdateBenchmarkResultChangeAnnotations(ctx, UpdateBenchmarkResultChangeAnnotationsParams{
		ID: id, ChangeAnnotations: changeAnnotations,
	})
	if errors.Is(err, pgx.ErrNoRows) {
		return storage.ErrNotFound
	}
	return err
}

// DeleteBenchmarkResult hard-deletes one result row. Missing row -> ErrNotFound.
func (s *Store) DeleteBenchmarkResult(ctx context.Context, id string) error {
	_, err := s.q.DeleteBenchmarkResult(ctx, id)
	if errors.Is(err, pgx.ErrNoRows) {
		return storage.ErrNotFound
	}
	return err
}

// GetBenchmarkResultByID returns the stored result row, or storage.ErrNotFound
// when no result has that id.
func (s *Store) GetBenchmarkResultByID(ctx context.Context, id string) (storage.BenchmarkResult, error) {
	row, err := s.q.GetBenchmarkResultByID(ctx, id)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return storage.BenchmarkResult{}, storage.ErrNotFound
		}
		return storage.BenchmarkResult{}, err
	}
	return benchmarkResultFromRow(row), nil
}

// CountBenchmarkResults returns the number of stored results. The seed uses it to
// stay idempotent (skip when the database already holds results).
func (s *Store) CountBenchmarkResults(ctx context.Context) (int64, error) {
	return s.q.CountBenchmarkResults(ctx)
}

// GetBenchmarkResultDetail returns the result joined to its case, context, info,
// hardware, and (optional) commit, for the result-detail read endpoint, or
// storage.ErrNotFound when no result has that id.
func (s *Store) GetBenchmarkResultDetail(ctx context.Context, id string) (storage.ResultDetailRow, error) {
	row, err := s.q.GetBenchmarkResultDetail(ctx, id)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return storage.ResultDetailRow{}, storage.ErrNotFound
		}
		return storage.ResultDetailRow{}, err
	}
	return resultDetailFromRow(row), nil
}

// SelectHistoryForFingerprint returns the history membership series for a
// fingerprint (non-errored, default-branch, commit-joined).
func (s *Store) SelectHistoryForFingerprint(ctx context.Context, fingerprint string) ([]storage.HistoryRow, error) {
	rows, err := s.q.SelectHistoryForFingerprint(ctx, fingerprint)
	if err != nil {
		return nil, err
	}
	return historyRowsFromRows(rows), nil
}

// SelectHistoryForFingerprintAsOf returns the baseline-distribution window: the
// membership series restricted to commits at or before asOf.
func (s *Store) SelectHistoryForFingerprintAsOf(ctx context.Context, fingerprint string, asOf time.Time) ([]storage.HistoryRow, error) {
	rows, err := s.q.SelectHistoryForFingerprintAsOf(ctx, SelectHistoryForFingerprintAsOfParams{
		HistoryFingerprint: fingerprint,
		AsOf:               &asOf,
	})
	if err != nil {
		return nil, err
	}
	return historyAsOfRowsFromRows(rows), nil
}

// GetResultForCompare returns one result's compare fields, or storage.ErrNotFound
// when no result has that id.
func (s *Store) GetResultForCompare(ctx context.Context, id string) (storage.CompareResultRow, error) {
	row, err := s.q.GetResultForCompare(ctx, id)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return storage.CompareResultRow{}, storage.ErrNotFound
		}
		return storage.CompareResultRow{}, err
	}
	return compareResultFromRow(row), nil
}

// SelectBenchmarkResults returns the filtered, cursor-paginated result list.
func (s *Store) SelectBenchmarkResults(ctx context.Context, p storage.ListResultsParams) ([]storage.ResultListRow, error) {
	rows, err := s.q.SelectBenchmarkResults(ctx, SelectBenchmarkResultsParams{
		RunID:     p.RunID,
		BatchID:   p.BatchID,
		RunReason: p.RunReason,
		Earliest:  p.Earliest,
		Latest:    p.Latest,
		Cursor:    p.Cursor,
		PageSize:  p.PageSize,
	})
	if err != nil {
		return nil, err
	}
	return resultListRowsFromRows(rows), nil
}

// SelectRecentRuns returns grouped run summaries for the landing page.
func (s *Store) SelectRecentRuns(ctx context.Context, p storage.RecentRunsParams) ([]storage.RecentRunRow, error) {
	rows, err := s.q.SelectRecentRuns(ctx, SelectRecentRunsParams{
		CandidateResultCount: p.CandidateResultCount,
		PageSize:             p.PageSize,
	})
	if err != nil {
		return nil, err
	}
	return recentRunRowsFromRows(rows), nil
}

// SelectSeriesPage returns the filtered, cursor-paginated series list: one row
// per history fingerprint with its newest-commit member and point count.
func (s *Store) SelectSeriesPage(ctx context.Context, p storage.SeriesListParams) ([]storage.SeriesPageRow, error) {
	if p.Fingerprint != nil {
		rows, err := s.q.SelectSeriesPageForFingerprint(ctx, SelectSeriesPageForFingerprintParams{
			Fingerprint: *p.Fingerprint,
			ActiveSince: p.ActiveSince,
			ActiveUntil: p.ActiveUntil,
			CursorTs:    p.CursorTs,
			CursorFp:    p.CursorFp,
			Q:           p.Q,
			Hardware:    p.Hardware,
			Repository:  p.Repository,
			PageSize:    p.PageSize,
		})
		if err != nil {
			return nil, err
		}
		return seriesPageRowsFromFingerprintRows(rows), nil
	}
	if p.Q != nil && *p.Q != "" {
		caseIDs, err := s.q.SelectSeriesCaseIDsForQ(ctx, *p.Q)
		if err != nil {
			return nil, err
		}
		if len(caseIDs) == 0 {
			return nil, nil
		}
		if len(caseIDs) <= seriesQCompleteCaseLimit || seriesQNeedsCompleteSearch(p) {
			rows, err := s.q.SelectSeriesPageForQCaseIDs(ctx, SelectSeriesPageForQCaseIDsParams{
				CaseIds:     caseIDs,
				Repository:  p.Repository,
				Hardware:    p.Hardware,
				ActiveSince: p.ActiveSince,
				ActiveUntil: p.ActiveUntil,
				CursorTs:    p.CursorTs,
				CursorFp:    p.CursorFp,
				PageSize:    p.PageSize,
			})
			if err != nil {
				return nil, err
			}
			return seriesPageRowsFromQCaseIDRows(rows), nil
		}
		rows, err := s.q.SelectSeriesPageForQRecent(ctx, SelectSeriesPageForQRecentParams{
			CaseIds:           caseIDs,
			ActiveUntil:       p.ActiveUntil,
			CursorTs:          p.CursorTs,
			SearchCommitLimit: seriesQRecentCommitLimit(p.PageSize),
			Hardware:          p.Hardware,
			Repository:        p.Repository,
			ActiveSince:       p.ActiveSince,
			CursorFp:          p.CursorFp,
			PageSize:          p.PageSize,
		})
		if err != nil {
			return nil, err
		}
		return seriesPageRowsFromQRecentRows(rows), nil
	}

	rows, err := s.q.SelectSeriesPage(ctx, SelectSeriesPageParams{
		ActiveSince:       p.ActiveSince,
		ActiveUntil:       p.ActiveUntil,
		CursorTs:          p.CursorTs,
		Repository:        p.Repository,
		SearchCommitLimit: seriesBrowseRecentCommitLimit(p),
		Hardware:          p.Hardware,
		CursorFp:          p.CursorFp,
		PageSize:          p.PageSize,
	})
	if err != nil {
		return nil, err
	}
	return seriesPageRowsFromRows(rows), nil
}

func seriesQNeedsCompleteSearch(p storage.SeriesListParams) bool {
	return p.Hardware != nil || p.Repository != nil || p.ActiveSince != nil || p.ActiveUntil != nil
}

func seriesQRecentCommitLimit(pageSize int32) int32 {
	limit := pageSize * seriesQRecentCommitPageFactor
	if limit < seriesQRecentCommitMinLimit {
		return seriesQRecentCommitMinLimit
	}
	if limit > seriesQRecentCommitMaxLimit {
		return seriesQRecentCommitMaxLimit
	}
	return limit
}

func seriesBrowseRecentCommitLimit(p storage.SeriesListParams) int32 {
	limit := min(max(p.PageSize*seriesBrowseRecentCommitPageFactor, seriesBrowseRecentCommitMinLimit), seriesBrowseRecentCommitMaxLimit)
	if p.CursorTs != nil || p.Hardware != nil {
		return max(limit, seriesBrowseScopedCommitLimit)
	}
	return limit
}

// CreateAPIToken mints an api_token row with a generated id and returns the
// id. last_used_at and revoked_at start NULL.
func (s *Store) CreateAPIToken(ctx context.Context, p storage.InsertAPITokenParams) (string, error) {
	id, err := genID()
	if err != nil {
		return "", err
	}
	return s.q.InsertAPIToken(ctx, InsertAPITokenParams{
		ID: id, UserID: p.UserID, Name: p.Name,
		TokenHash: p.TokenHash, TokenPrefix: p.TokenPrefix, CreatedAt: p.CreatedAt,
	})
}

// GetAPITokenByHash returns the token row with the given hash, or
// storage.ErrNotFound. The unique index on token_hash makes this the
// verification lookup.
func (s *Store) GetAPITokenByHash(ctx context.Context, tokenHash string) (storage.APIToken, error) {
	row, err := s.q.GetAPITokenByHash(ctx, tokenHash)
	if errors.Is(err, pgx.ErrNoRows) {
		return storage.APIToken{}, storage.ErrNotFound
	}
	if err != nil {
		return storage.APIToken{}, err
	}
	return apiTokenFromRow(row), nil
}

// ListAPITokensByUser returns a user's tokens, newest first (secrets included
// at this layer; the handler omits the hash). An empty result is not an error.
func (s *Store) ListAPITokensByUser(ctx context.Context, userID string) ([]storage.APIToken, error) {
	rows, err := s.q.ListAPITokensByUser(ctx, userID)
	if err != nil {
		return nil, err
	}
	out := make([]storage.APIToken, 0, len(rows))
	for _, r := range rows {
		out = append(out, apiTokenFromRow(r))
	}
	return out, nil
}

// GetAPITokenByID returns one token row, or storage.ErrNotFound.
func (s *Store) GetAPITokenByID(ctx context.Context, id string) (storage.APIToken, error) {
	row, err := s.q.GetAPITokenByID(ctx, id)
	if errors.Is(err, pgx.ErrNoRows) {
		return storage.APIToken{}, storage.ErrNotFound
	}
	if err != nil {
		return storage.APIToken{}, err
	}
	return apiTokenFromRow(row), nil
}

// apiTokenFromRow maps a generated ApiToken row to the storage DTO.
func apiTokenFromRow(r ApiToken) storage.APIToken {
	return storage.APIToken{
		ID: r.ID, UserID: r.UserID, Name: r.Name,
		TokenHash: r.TokenHash, TokenPrefix: r.TokenPrefix,
		CreatedAt: r.CreatedAt, LastUsedAt: r.LastUsedAt, RevokedAt: r.RevokedAt,
	}
}

// TouchAPITokenLastUsed records a successful use of the token. Best-effort
// callers throttle and fire-and-forget; this is a plain update.
func (s *Store) TouchAPITokenLastUsed(ctx context.Context, id string, lastUsed time.Time) error {
	return s.q.TouchAPITokenLastUsed(ctx, TouchAPITokenLastUsedParams{ID: id, LastUsedAt: &lastUsed})
}

// RevokeAPIToken sets revoked_at, after which verification rejects the token.
// Idempotent for an existing row (a second call overwrites the timestamp);
// returns storage.ErrNotFound when no row has the id, so callers can
// distinguish a revoke from a typo.
func (s *Store) RevokeAPIToken(ctx context.Context, id string, revokedAt time.Time) error {
	rows, err := s.q.RevokeAPIToken(ctx, RevokeAPITokenParams{ID: id, RevokedAt: &revokedAt})
	if err != nil {
		return err
	}
	if rows == 0 {
		return storage.ErrNotFound
	}
	return nil
}

// SelectSeriesMembers returns the recent history membership tail of each
// fingerprint, grouped by fingerprint and ordered oldest commit first within
// each returned tail. Full history remains available through
// SelectHistoryForFingerprint.
func (s *Store) SelectSeriesMembers(ctx context.Context, fingerprints []string) ([]storage.HistoryRow, error) {
	rows, err := s.q.SelectSeriesMembers(ctx, SelectSeriesMembersParams{
		Fingerprints:        fingerprints,
		PerFingerprintLimit: seriesMembersTailLimit,
	})
	if err != nil {
		return nil, err
	}
	return seriesMembersRowsFromRows(rows), nil
}

// SelectCIReportRunsByCommit returns distinct runs for a normalized repository
// and commit SHA, with contender commit metadata for baseline resolution.
func (s *Store) SelectCIReportRunsByCommit(ctx context.Context, repository, sha string) ([]storage.CIReportRunRow, error) {
	rows, err := s.q.SelectCIReportRunsByCommit(ctx, SelectCIReportRunsByCommitParams{
		Repository: repository,
		Sha:        sha,
	})
	if err != nil {
		return nil, err
	}
	return ciReportRunRowsFromCommitRows(rows), nil
}

// SelectCIReportRunsByIDs returns distinct runs found for runIDs. Missing IDs
// simply contribute no rows; the service diagnoses them against the request.
func (s *Store) SelectCIReportRunsByIDs(ctx context.Context, runIDs []string) ([]storage.CIReportRunRow, error) {
	rows, err := s.q.SelectCIReportRunsByIDs(ctx, runIDs)
	if err != nil {
		return nil, err
	}
	return ciReportRunRowsFromIDRows(rows), nil
}

// GetCIReportCommit returns one commit's metadata, or storage.ErrNotFound.
func (s *Store) GetCIReportCommit(ctx context.Context, repository, sha string) (storage.CIReportCommitRow, error) {
	row, err := s.q.GetCIReportCommit(ctx, GetCIReportCommitParams{Repository: repository, Sha: sha})
	if errors.Is(err, pgx.ErrNoRows) {
		return storage.CIReportCommitRow{}, storage.ErrNotFound
	}
	if err != nil {
		return storage.CIReportCommitRow{}, err
	}
	return ciReportCommitFromGetRow(row), nil
}

// SelectLatestDefaultCommit returns the newest known default-branch commit for
// repository, using sha=fork_point_sha and timestamp/sha DESC ordering.
func (s *Store) SelectLatestDefaultCommit(ctx context.Context, repository string) (storage.CIReportCommitRow, error) {
	row, err := s.q.SelectLatestDefaultCommit(ctx, repository)
	if errors.Is(err, pgx.ErrNoRows) {
		return storage.CIReportCommitRow{}, storage.ErrNotFound
	}
	if err != nil {
		return storage.CIReportCommitRow{}, err
	}
	return ciReportCommitFromLatestRow(row), nil
}

// SelectCIReportBaselineAncestry returns the starting commit and same-repository
// parents up to limit rows, in ancestry order.
func (s *Store) SelectCIReportBaselineAncestry(
	ctx context.Context,
	repository string,
	sha string,
	limit int32,
) ([]storage.CIReportCommitRow, error) {
	rows, err := s.q.SelectCIReportBaselineAncestry(ctx, SelectCIReportBaselineAncestryParams{
		Repository:    repository,
		Sha:           sha,
		AncestorLimit: limit,
	})
	if err != nil {
		return nil, err
	}
	return ciReportCommitRowsFromAncestryRows(rows), nil
}

// CountCIReportRows counts contender result rows before full report assembly.
func (s *Store) CountCIReportRows(ctx context.Context, runs []storage.CIReportRunKey) (int64, error) {
	runIDs, commitIDs := ciReportRunKeyArrays(runs)
	return s.q.CountCIReportRows(ctx, CountCIReportRowsParams{
		RunIds:    runIDs,
		CommitIds: commitIDs,
	})
}

// SelectCIReportRows returns all selected contender rows plus one deterministic
// baseline row per selected baseline run/commit/history fingerprint.
func (s *Store) SelectCIReportRows(ctx context.Context, runs []storage.CIReportRunKey, baselineRuns []storage.CIReportRunKey) ([]storage.CIReportResultRow, error) {
	runIDs, commitIDs := ciReportRunKeyArrays(runs)
	baselineRunIDs, baselineCommitIDs := ciReportRunKeyArrays(baselineRuns)
	rows, err := s.q.SelectCIReportRows(ctx, SelectCIReportRowsParams{
		ContenderRunIds:    runIDs,
		ContenderCommitIds: commitIDs,
		BaselineRunIds:     baselineRunIDs,
		BaselineCommitIds:  baselineCommitIDs,
	})
	if err != nil {
		return nil, err
	}
	return ciReportResultRowsFromRows(rows), nil
}

func ciReportRunKeyArrays(keys []storage.CIReportRunKey) ([]string, []string) {
	runIDs := make([]string, len(keys))
	commitIDs := make([]string, len(keys))
	for i, key := range keys {
		runIDs[i] = key.RunID
		commitIDs[i] = key.CommitID
	}
	return runIDs, commitIDs
}
