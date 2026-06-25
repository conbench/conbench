package db

import (
	"time"

	"github.com/conbench/conbench/internal/storage"
)

// Store is the Postgres adapter for the storage port.
var _ storage.Store = (*Store)(nil)

// This file maps between the storage port DTOs and the sqlc-generated params and
// rows. The mapping is mechanical (the shapes match column-for-column); it keeps
// the sqlc types inside internal/db so the service depends only on the port.

// denseFloats converts a nullable-element array column to the dense slice the
// membership consumers expect. Membership queries exclude errored results and
// only errored results can hold null elements, so a null here is a data
// integrity fault: return nil and let the service's empty-data error surface
// it loudly rather than fabricating a value.
func denseFloats(xs []*float64) []float64 {
	out := make([]float64, len(xs))
	for i, x := range xs {
		if x == nil {
			return nil
		}
		out[i] = *x
	}
	return out
}

func toInsertHardwareParams(p storage.InsertHardwareParams) InsertHardwareParams {
	return InsertHardwareParams{
		Type:              p.Type,
		Name:              p.Name,
		Hash:              p.Hash,
		ArchitectureName:  p.ArchitectureName,
		KernelName:        p.KernelName,
		OsName:            p.OsName,
		OsVersion:         p.OsVersion,
		CpuModelName:      p.CpuModelName,
		CpuL1dCacheBytes:  p.CpuL1dCacheBytes,
		CpuL1iCacheBytes:  p.CpuL1iCacheBytes,
		CpuL2CacheBytes:   p.CpuL2CacheBytes,
		CpuL3CacheBytes:   p.CpuL3CacheBytes,
		CpuCoreCount:      p.CpuCoreCount,
		CpuThreadCount:    p.CpuThreadCount,
		CpuFrequencyMaxHz: p.CpuFrequencyMaxHz,
		MemoryBytes:       p.MemoryBytes,
		GpuCount:          p.GpuCount,
		GpuProductNames:   p.GpuProductNames,
		Info:              p.Info,
		OptionalInfo:      p.OptionalInfo,
	}
}

func toInsertCommitParams(p storage.InsertCommitParams) InsertCommitParams {
	return InsertCommitParams{
		Sha:          p.Sha,
		Parent:       p.Parent,
		Repository:   p.Repository,
		Message:      p.Message,
		AuthorName:   p.AuthorName,
		AuthorLogin:  p.AuthorLogin,
		AuthorAvatar: p.AuthorAvatar,
		Timestamp:    p.Timestamp,
		Branch:       p.Branch,
		ForkPointSha: p.ForkPointSha,
	}
}

func toInsertBenchmarkResultParams(p storage.InsertBenchmarkResultParams) InsertBenchmarkResultParams {
	return InsertBenchmarkResultParams{
		CaseID:                p.CaseID,
		ContextID:             p.ContextID,
		InfoID:                p.InfoID,
		HardwareID:            p.HardwareID,
		RunID:                 p.RunID,
		RunTags:               p.RunTags,
		RunReason:             p.RunReason,
		CommitID:              p.CommitID,
		CommitRepoUrl:         p.CommitRepoUrl,
		HistoryFingerprint:    p.HistoryFingerprint,
		Timestamp:             p.Timestamp,
		Unit:                  p.Unit,
		TimeUnit:              p.TimeUnit,
		BatchID:               p.BatchID,
		Iterations:            p.Iterations,
		Error:                 p.Error,
		Data:                  p.Data,
		Times:                 p.Times,
		Mean:                  p.Mean,
		Min:                   p.Min,
		Max:                   p.Max,
		Median:                p.Median,
		Q1:                    p.Q1,
		Q3:                    p.Q3,
		Stdev:                 p.Stdev,
		Iqr:                   p.Iqr,
		Validation:            p.Validation,
		OptionalBenchmarkInfo: p.OptionalBenchmarkInfo,
		ChangeAnnotations:     p.ChangeAnnotations,
	}
}

func benchmarkResultFromRow(r GetBenchmarkResultByIDRow) storage.BenchmarkResult {
	return storage.BenchmarkResult{
		ID:                    r.ID,
		CaseID:                r.CaseID,
		ContextID:             r.ContextID,
		InfoID:                r.InfoID,
		HardwareID:            r.HardwareID,
		RunID:                 r.RunID,
		RunTags:               r.RunTags,
		RunReason:             r.RunReason,
		CommitID:              r.CommitID,
		CommitRepoUrl:         r.CommitRepoUrl,
		HistoryFingerprint:    r.HistoryFingerprint,
		Timestamp:             r.Timestamp,
		Unit:                  r.Unit,
		TimeUnit:              r.TimeUnit,
		BatchID:               r.BatchID,
		Iterations:            r.Iterations,
		Error:                 r.Error,
		Data:                  r.Data,
		Times:                 r.Times,
		Mean:                  r.Mean,
		Min:                   r.Min,
		Max:                   r.Max,
		Median:                r.Median,
		Q1:                    r.Q1,
		Q3:                    r.Q3,
		Stdev:                 r.Stdev,
		Iqr:                   r.Iqr,
		Validation:            r.Validation,
		OptionalBenchmarkInfo: r.OptionalBenchmarkInfo,
		ChangeAnnotations:     r.ChangeAnnotations,
	}
}

func alertRuleFromRow(r AlertRule) storage.AlertRule {
	return storage.AlertRule{
		ID:              r.ID,
		UserID:          r.UserID,
		Name:            r.Name,
		Repository:      r.Repository,
		Baseline:        r.Baseline,
		Threshold:       r.Threshold,
		ThresholdZ:      r.ThresholdZ,
		RunReason:       r.RunReason,
		Enabled:         r.Enabled,
		State:           r.State,
		CreatedAt:       r.CreatedAt,
		UpdatedAt:       r.UpdatedAt,
		LastEvaluatedAt: r.LastEvaluatedAt,
	}
}

func alertRulesFromRows(rows []AlertRule) []storage.AlertRule {
	out := make([]storage.AlertRule, 0, len(rows))
	for _, row := range rows {
		out = append(out, alertRuleFromRow(row))
	}
	return out
}

func alertEventFromRow(r AlertEvent) storage.AlertEvent {
	return storage.AlertEvent{
		ID:           r.ID,
		RuleID:       r.RuleID,
		Kind:         r.Kind,
		Status:       r.Status,
		StatusReason: r.StatusReason,
		RunID:        r.RunID,
		CommitSHA:    r.CommitSha,
		Repository:   r.Repository,
		ReportURL:    r.ReportUrl,
		Summary:      r.Summary,
		CreatedAt:    r.CreatedAt,
	}
}

func alertEventsFromRows(rows []AlertEvent) []storage.AlertEvent {
	out := make([]storage.AlertEvent, 0, len(rows))
	for _, row := range rows {
		out = append(out, alertEventFromRow(row))
	}
	return out
}

func alertDeliveryFromRow(r AlertDelivery) storage.AlertDelivery {
	return storage.AlertDelivery{
		ID:            r.ID,
		EventID:       r.EventID,
		Channel:       r.Channel,
		Target:        r.Target,
		Status:        r.Status,
		AttemptCount:  r.AttemptCount,
		LastAttemptAt: r.LastAttemptAt,
		NextAttemptAt: r.NextAttemptAt,
		DeliveredAt:   r.DeliveredAt,
		LastError:     r.LastError,
		CreatedAt:     r.CreatedAt,
		UpdatedAt:     r.UpdatedAt,
	}
}

func alertDeliveryFromClaimedRow(r ClaimPendingAlertDeliveriesRow) storage.AlertDelivery {
	return storage.AlertDelivery{
		ID:            r.DeliveryID,
		EventID:       r.DeliveryEventID,
		Channel:       r.DeliveryChannel,
		Target:        r.DeliveryTarget,
		Status:        r.DeliveryStatus,
		AttemptCount:  r.DeliveryAttemptCount,
		LastAttemptAt: r.DeliveryLastAttemptAt,
		NextAttemptAt: r.DeliveryNextAttemptAt,
		DeliveredAt:   r.DeliveryDeliveredAt,
		LastError:     r.DeliveryLastError,
		CreatedAt:     r.DeliveryCreatedAt,
		UpdatedAt:     r.DeliveryUpdatedAt,
		Event: storage.AlertEvent{
			ID:           r.EventID,
			RuleID:       r.EventRuleID,
			Kind:         r.EventKind,
			Status:       r.EventStatus,
			StatusReason: r.EventStatusReason,
			RunID:        r.EventRunID,
			CommitSHA:    r.EventCommitSha,
			Repository:   r.EventRepository,
			ReportURL:    r.EventReportUrl,
			Summary:      r.EventSummary,
			CreatedAt:    r.EventCreatedAt,
		},
	}
}

func alertDeliveriesFromClaimedRows(rows []ClaimPendingAlertDeliveriesRow) []storage.AlertDelivery {
	out := make([]storage.AlertDelivery, 0, len(rows))
	for _, row := range rows {
		out = append(out, alertDeliveryFromClaimedRow(row))
	}
	return out
}

func alertTransitionFromRow(r TransitionAlertRuleRow) storage.AlertRuleTransition {
	event := storage.AlertEvent{
		ID:           r.EventID,
		RuleID:       r.EventRuleID,
		Kind:         r.EventKind,
		Status:       r.EventStatus,
		StatusReason: r.EventStatusReason,
		RunID:        r.EventRunID,
		CommitSHA:    r.EventCommitSha,
		Repository:   r.EventRepository,
		ReportURL:    r.EventReportUrl,
		Summary:      r.EventSummary,
		CreatedAt:    r.EventCreatedAt,
	}
	return storage.AlertRuleTransition{
		Transitioned: true,
		Rule: storage.AlertRule{
			ID:              r.RuleID,
			UserID:          r.RuleUserID,
			Name:            r.RuleName,
			Repository:      r.RuleRepository,
			Baseline:        r.RuleBaseline,
			Threshold:       r.RuleThreshold,
			ThresholdZ:      r.RuleThresholdZ,
			RunReason:       r.RuleRunReason,
			Enabled:         r.RuleEnabled,
			State:           r.RuleState,
			CreatedAt:       r.RuleCreatedAt,
			UpdatedAt:       r.RuleUpdatedAt,
			LastEvaluatedAt: r.RuleLastEvaluatedAt,
		},
		Event: &event,
	}
}

func resultDetailFromRow(r GetBenchmarkResultDetailRow) storage.ResultDetailRow {
	return storage.ResultDetailRow{
		ID:                    r.ID,
		RunID:                 r.RunID,
		RunTags:               r.RunTags,
		RunReason:             r.RunReason,
		BatchID:               r.BatchID,
		Timestamp:             r.Timestamp,
		CommitRepoUrl:         r.CommitRepoUrl,
		HistoryFingerprint:    r.HistoryFingerprint,
		Unit:                  r.Unit,
		TimeUnit:              r.TimeUnit,
		Iterations:            r.Iterations,
		Error:                 r.Error,
		Data:                  r.Data,
		Times:                 r.Times,
		Mean:                  r.Mean,
		Min:                   r.Min,
		Max:                   r.Max,
		Median:                r.Median,
		Q1:                    r.Q1,
		Q3:                    r.Q3,
		Stdev:                 r.Stdev,
		Iqr:                   r.Iqr,
		Validation:            r.Validation,
		OptionalBenchmarkInfo: r.OptionalBenchmarkInfo,
		ChangeAnnotations:     r.ChangeAnnotations,
		CaseName:              r.CaseName,
		CaseTags:              r.CaseTags,
		ContextTags:           r.ContextTags,
		InfoTags:              r.InfoTags,
		HardwareID:            r.HardwareID,
		HardwareType:          r.HardwareType,
		HardwareName:          r.HardwareName,
		HardwareHash:          r.HardwareHash,
		CommitID:              r.CommitID,
		CommitSha:             r.CommitSha,
		CommitRepository:      r.CommitRepository,
		CommitMessage:         r.CommitMessage,
		CommitTimestamp:       r.CommitTimestamp,
	}
}

func historyRowsFromRows(rows []SelectHistoryForFingerprintRow) []storage.HistoryRow {
	out := make([]storage.HistoryRow, len(rows))
	for i, r := range rows {
		out[i] = storage.HistoryRow{
			ID:                 r.ID,
			HistoryFingerprint: r.HistoryFingerprint,
			Timestamp:          r.Timestamp,
			Unit:               r.Unit,
			Mean:               r.Mean,
			Data:               denseFloats(r.Data),
			ChangeAnnotations:  r.ChangeAnnotations,
			HardwareHash:       r.HardwareHash,
			CommitSha:          r.CommitSha,
			CommitRepository:   r.CommitRepository,
			CommitMessage:      r.CommitMessage,
			CommitTimestamp:    r.CommitTimestamp,
		}
	}
	return out
}

func compareResultFromRow(r GetResultForCompareRow) storage.CompareResultRow {
	return storage.CompareResultRow{
		ID:                 r.ID,
		RunID:              r.RunID,
		HistoryFingerprint: r.HistoryFingerprint,
		Unit:               r.Unit,
		Data:               r.Data,
		Error:              r.Error,
		CommitID:           r.CommitID,
		CommitTimestamp:    r.CommitTimestamp,
	}
}

func historyAsOfRowsFromRows(rows []SelectHistoryForFingerprintAsOfRow) []storage.HistoryRow {
	out := make([]storage.HistoryRow, len(rows))
	for i, r := range rows {
		out[i] = storage.HistoryRow{
			ID:                 r.ID,
			HistoryFingerprint: r.HistoryFingerprint,
			Timestamp:          r.Timestamp,
			Unit:               r.Unit,
			Mean:               r.Mean,
			Data:               denseFloats(r.Data),
			ChangeAnnotations:  r.ChangeAnnotations,
			HardwareHash:       r.HardwareHash,
			CommitSha:          r.CommitSha,
			CommitRepository:   r.CommitRepository,
			CommitMessage:      r.CommitMessage,
			CommitTimestamp:    r.CommitTimestamp,
		}
	}
	return out
}

// seriesMembersRowsFromRows maps the generated batched-membership rows to the
// port DTO. Members exclude errored rows; the CTE alias makes sqlc emit dense
// []float64 data for this query, so no nullable-element conversion is needed.
func seriesMembersRowsFromRows(rows []SelectSeriesMembersRow) []storage.HistoryRow {
	out := make([]storage.HistoryRow, len(rows))
	for i, r := range rows {
		out[i] = storage.HistoryRow{
			ID:                 r.ID,
			HistoryFingerprint: r.HistoryFingerprint,
			Timestamp:          r.Timestamp,
			Unit:               r.Unit,
			Mean:               r.Mean,
			Data:               r.Data,
			ChangeAnnotations:  r.ChangeAnnotations,
			HardwareHash:       r.HardwareHash,
			CommitSha:          r.CommitSha,
			CommitRepository:   r.CommitRepository,
			CommitMessage:      r.CommitMessage,
			CommitTimestamp:    r.CommitTimestamp,
		}
	}
	return out
}

func resultListRowsFromRows(rows []SelectBenchmarkResultsRow) []storage.ResultListRow {
	out := make([]storage.ResultListRow, len(rows))
	for i, r := range rows {
		out[i] = storage.ResultListRow{
			ID:                 r.ID,
			RunID:              r.RunID,
			RunReason:          r.RunReason,
			RunTags:            r.RunTags,
			BatchID:            r.BatchID,
			Timestamp:          r.Timestamp,
			Unit:               r.Unit,
			Data:               r.Data,
			Error:              r.Error,
			HistoryFingerprint: r.HistoryFingerprint,
			CaseName:           r.CaseName,
			CaseTags:           r.CaseTags,
			CommitSha:          r.CommitSha,
			CommitRepository:   r.CommitRepository,
			CommitMessage:      r.CommitMessage,
			CommitAuthorName:   r.CommitAuthorName,
			CommitAuthorLogin:  r.CommitAuthorLogin,
			CommitAuthorAvatar: r.CommitAuthorAvatar,
			CommitTimestamp:    r.CommitTimestamp,
		}
	}
	return out
}

func recentRunRowsFromRows(rows []SelectRecentRunsRow) []storage.RecentRunRow {
	out := make([]storage.RecentRunRow, len(rows))
	for i, r := range rows {
		out[i] = storage.RecentRunRow{
			RunID:              r.RunID,
			FirstResultAt:      r.FirstResultAt,
			LastResultAt:       r.LastResultAt,
			ResultCount:        r.ResultCount,
			ErrorCount:         r.ErrorCount,
			SeriesCount:        r.SeriesCount,
			BatchCount:         r.BatchCount,
			LatestResultID:     r.LatestResultID,
			RunReason:          r.RunReason,
			RunTags:            r.RunTags,
			LatestBatchID:      r.LatestBatchID,
			Repository:         r.CommitRepoUrl,
			CommitSha:          r.CommitSha,
			CommitRepository:   r.CommitRepository,
			CommitMessage:      r.CommitMessage,
			CommitAuthorName:   r.CommitAuthorName,
			CommitAuthorLogin:  r.CommitAuthorLogin,
			CommitAuthorAvatar: r.CommitAuthorAvatar,
			CommitTimestamp:    r.CommitTimestamp,
		}
	}
	return out
}

// seriesPageRowsFromRows maps the generated series-list rows to the port DTO.
// The generated LatestCommitTimestamp is *time.Time because the commit timestamp
// column is nullable, but the query's `c."timestamp" IS NOT NULL` membership
// predicate guarantees a value for every returned series, so it is dereferenced
// to the DTO's time.Time.
func seriesPageRowsFromRows(rows []SelectSeriesPageRow) []storage.SeriesPageRow {
	out := make([]storage.SeriesPageRow, len(rows))
	for i, r := range rows {
		var latestCommitTs time.Time
		if r.LatestCommitTimestamp != nil {
			latestCommitTs = *r.LatestCommitTimestamp
		}
		out[i] = storage.SeriesPageRow{
			HistoryFingerprint:    r.HistoryFingerprint,
			LatestResultID:        r.LatestResultID,
			LatestResultTimestamp: r.LatestResultTimestamp,
			LatestCommitSha:       r.LatestCommitSha,
			LatestCommitTimestamp: latestCommitTs,
			CommitRepoUrl:         r.CommitRepoUrl,
			LatestUnit:            r.LatestUnit,
			LatestData:            r.LatestData,
			PointCount:            r.PointCount,
			CaseName:              r.CaseName,
			CaseTags:              r.CaseTags,
			ContextTags:           r.ContextTags,
			HardwareID:            r.HardwareID,
			HardwareName:          r.HardwareName,
			HardwareType:          r.HardwareType,
			HardwareHash:          r.HardwareHash,
		}
	}
	return out
}

func seriesPageRowsFromFingerprintRows(rows []SelectSeriesPageForFingerprintRow) []storage.SeriesPageRow {
	out := make([]storage.SeriesPageRow, len(rows))
	for i, r := range rows {
		var latestCommitTs time.Time
		if r.LatestCommitTimestamp != nil {
			latestCommitTs = *r.LatestCommitTimestamp
		}
		out[i] = storage.SeriesPageRow{
			HistoryFingerprint:    r.HistoryFingerprint,
			LatestResultID:        r.LatestResultID,
			LatestResultTimestamp: r.LatestResultTimestamp,
			LatestCommitSha:       r.LatestCommitSha,
			LatestCommitTimestamp: latestCommitTs,
			CommitRepoUrl:         r.CommitRepoUrl,
			LatestUnit:            r.LatestUnit,
			LatestData:            r.LatestData,
			PointCount:            r.PointCount,
			CaseName:              r.CaseName,
			CaseTags:              r.CaseTags,
			ContextTags:           r.ContextTags,
			HardwareID:            r.HardwareID,
			HardwareName:          r.HardwareName,
			HardwareType:          r.HardwareType,
			HardwareHash:          r.HardwareHash,
		}
	}
	return out
}

func seriesPageRowsFromQCaseIDRows(rows []SelectSeriesPageForQCaseIDsRow) []storage.SeriesPageRow {
	out := make([]storage.SeriesPageRow, len(rows))
	for i, r := range rows {
		var latestCommitTs time.Time
		if r.LatestCommitTimestamp != nil {
			latestCommitTs = *r.LatestCommitTimestamp
		}
		out[i] = storage.SeriesPageRow{
			HistoryFingerprint:    r.HistoryFingerprint,
			LatestResultID:        r.LatestResultID,
			LatestResultTimestamp: r.LatestResultTimestamp,
			LatestCommitSha:       r.LatestCommitSha,
			LatestCommitTimestamp: latestCommitTs,
			CommitRepoUrl:         r.CommitRepoUrl,
			LatestUnit:            r.LatestUnit,
			LatestData:            r.LatestData,
			PointCount:            r.PointCount,
			CaseName:              r.CaseName,
			CaseTags:              r.CaseTags,
			ContextTags:           r.ContextTags,
			HardwareID:            r.HardwareID,
			HardwareName:          r.HardwareName,
			HardwareType:          r.HardwareType,
			HardwareHash:          r.HardwareHash,
		}
	}
	return out
}

func seriesPageRowsFromQRecentRows(rows []SelectSeriesPageForQRecentRow) []storage.SeriesPageRow {
	out := make([]storage.SeriesPageRow, len(rows))
	for i, r := range rows {
		var latestCommitTs time.Time
		if r.LatestCommitTimestamp != nil {
			latestCommitTs = *r.LatestCommitTimestamp
		}
		out[i] = storage.SeriesPageRow{
			HistoryFingerprint:    r.HistoryFingerprint,
			LatestResultID:        r.LatestResultID,
			LatestResultTimestamp: r.LatestResultTimestamp,
			LatestCommitSha:       r.LatestCommitSha,
			LatestCommitTimestamp: latestCommitTs,
			CommitRepoUrl:         r.CommitRepoUrl,
			LatestUnit:            r.LatestUnit,
			LatestData:            r.LatestData,
			PointCount:            r.PointCount,
			CaseName:              r.CaseName,
			CaseTags:              r.CaseTags,
			ContextTags:           r.ContextTags,
			HardwareID:            r.HardwareID,
			HardwareName:          r.HardwareName,
			HardwareType:          r.HardwareType,
			HardwareHash:          r.HardwareHash,
		}
	}
	return out
}

func ciReportRunRowsFromCommitRows(rows []SelectCIReportRunsByCommitRow) []storage.CIReportRunRow {
	out := make([]storage.CIReportRunRow, len(rows))
	for i, r := range rows {
		out[i] = storage.CIReportRunRow{
			RunID:              r.RunID,
			RunTags:            r.RunTags,
			RunReason:          r.RunReason,
			CommitRepoURL:      r.CommitRepoUrl,
			CommitID:           &r.CommitID,
			CommitSha:          &r.CommitSha,
			CommitRepository:   &r.CommitRepository,
			CommitParent:       r.CommitParent,
			CommitForkPointSha: r.CommitForkPointSha,
			CommitTimestamp:    r.CommitTimestamp,
		}
	}
	return out
}

func ciReportRunRowsFromIDRows(rows []SelectCIReportRunsByIDsRow) []storage.CIReportRunRow {
	out := make([]storage.CIReportRunRow, len(rows))
	for i, r := range rows {
		out[i] = storage.CIReportRunRow{
			RunID:              r.RunID,
			RunTags:            r.RunTags,
			RunReason:          r.RunReason,
			CommitRepoURL:      r.CommitRepoUrl,
			CommitID:           r.CommitID,
			CommitSha:          r.CommitSha,
			CommitRepository:   r.CommitRepository,
			CommitParent:       r.CommitParent,
			CommitForkPointSha: r.CommitForkPointSha,
			CommitTimestamp:    r.CommitTimestamp,
		}
	}
	return out
}

func ciReportCommitFromGetRow(r GetCIReportCommitRow) storage.CIReportCommitRow {
	return storage.CIReportCommitRow{
		CommitID:     r.CommitID,
		CommitSha:    r.CommitSha,
		Repository:   r.Repository,
		Parent:       r.Parent,
		ForkPointSha: r.ForkPointSha,
		Timestamp:    r.Timestamp,
		Message:      r.Message,
	}
}

func ciReportCommitFromLatestRow(r SelectLatestDefaultCommitRow) storage.CIReportCommitRow {
	return storage.CIReportCommitRow{
		CommitID:     r.CommitID,
		CommitSha:    r.CommitSha,
		Repository:   r.Repository,
		Parent:       r.Parent,
		ForkPointSha: r.ForkPointSha,
		Timestamp:    r.Timestamp,
		Message:      r.Message,
	}
}

func ciReportCommitRowsFromAncestryRows(rows []SelectCIReportBaselineAncestryRow) []storage.CIReportCommitRow {
	out := make([]storage.CIReportCommitRow, len(rows))
	for i, r := range rows {
		out[i] = storage.CIReportCommitRow{
			CommitID:     r.CommitID,
			CommitSha:    r.CommitSha,
			Repository:   r.Repository,
			Parent:       r.Parent,
			ForkPointSha: r.ForkPointSha,
			Timestamp:    r.Timestamp,
			Message:      r.Message,
		}
	}
	return out
}

func ciReportResultRowsFromRows(rows []SelectCIReportRowsRow) []storage.CIReportResultRow {
	out := make([]storage.CIReportResultRow, len(rows))
	for i, r := range rows {
		out[i] = storage.CIReportResultRow{
			ResultID:           r.ResultID,
			RunID:              r.RunID,
			ResultTimestamp:    r.ResultTimestamp,
			HistoryFingerprint: r.HistoryFingerprint,
			CaseName:           r.CaseName,
			CaseTags:           r.CaseTags,
			ContextTags:        r.ContextTags,
			InfoTags:           r.InfoTags,
			HardwareID:         r.HardwareID,
			HardwareType:       r.HardwareType,
			HardwareName:       r.HardwareName,
			HardwareHash:       r.HardwareHash,
			CommitID:           r.CommitID,
			CommitSha:          r.CommitSha,
			CommitRepository:   r.CommitRepository,
			CommitParent:       r.CommitParent,
			CommitForkPointSha: r.CommitForkPointSha,
			CommitTimestamp:    r.CommitTimestamp,
			Unit:               r.Unit,
			Data:               r.Data,
			Error:              r.Error,
		}
	}
	return out
}
