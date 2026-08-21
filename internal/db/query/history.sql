-- name: SelectHistoryForFingerprint :many
-- History membership, ported from history.py:get_history_for_fingerprint. The
-- four filters define the series: non-errored, on the default branch
-- (sha == fork_point_sha), joined to a commit (the INNER JOIN drops results with
-- no commit), and joined to a commit with a non-null timestamp. Also selects
-- change_annotations, from which the service derives begins_distribution_change
-- for the rolling-statistics (zscorestats) computation in internal/stats.
--
-- This query and SelectHistoryForFingerprintAsOf share one membership
-- definition; both require a non-null commit timestamp because the series is
-- time-ordered by it (a null would sort as the zero time and corrupt the
-- rolling-statistics window).
SELECT
  br.id,
  br.history_fingerprint,
  br."timestamp",
  br.unit,
  br.mean,
  br.data,
  br.run_tags,
  inf.tags AS info_tags,
  br.change_annotations,
  hw.hash AS hardware_hash,
  c.sha AS commit_sha,
  c.repository AS commit_repository,
  c.message AS commit_message,
  c."timestamp" AS commit_timestamp
FROM benchmark_result br
JOIN info inf ON inf.id = br.info_id
JOIN hardware hw ON hw.id = br.hardware_id
JOIN commit c ON c.id = br.commit_id
WHERE br.error IS NULL
  AND br.history_fingerprint = $1
  AND c.sha = c.fork_point_sha
  AND c."timestamp" IS NOT NULL
ORDER BY c."timestamp", br.id;

-- name: SelectHistoryForFingerprintAsOf :many
-- The baseline-distribution window for compare: the same default-branch
-- membership as SelectHistoryForFingerprint, restricted to commits at or before
-- a cutoff timestamp. The timestamp cutoff approximates git ancestry (Phase-2;
-- true ancestry is Phase 4). Columns match SelectHistoryForFingerprint so both
-- map to storage.HistoryRow.
--
-- Both queries share one membership definition and require a non-null commit
-- timestamp for time-ordering. The `c."timestamp" <= as_of` bound already
-- excludes nulls; the explicit IS NOT NULL predicate keeps the two queries'
-- membership identical and the intent visible.
SELECT
  br.id,
  br.history_fingerprint,
  br."timestamp",
  br.unit,
  br.mean,
  br.data,
  br.run_tags,
  inf.tags AS info_tags,
  br.change_annotations,
  hw.hash AS hardware_hash,
  c.sha AS commit_sha,
  c.repository AS commit_repository,
  c.message AS commit_message,
  c."timestamp" AS commit_timestamp
FROM benchmark_result br
JOIN info inf ON inf.id = br.info_id
JOIN hardware hw ON hw.id = br.hardware_id
JOIN commit c ON c.id = br.commit_id
WHERE br.error IS NULL
  AND br.history_fingerprint = sqlc.arg('history_fingerprint')
  AND c.sha = c.fork_point_sha
  AND c."timestamp" IS NOT NULL
  AND c."timestamp" <= sqlc.arg('as_of')
ORDER BY c."timestamp", br.id;
