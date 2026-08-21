-- name: InsertBenchmarkResult :one
INSERT INTO benchmark_result (
  id, case_id, context_id, info_id, hardware_id,
  run_id, run_tags, run_reason, commit_id, commit_repo_url, history_fingerprint,
  "timestamp", unit, time_unit, batch_id, iterations, error,
  data, times, mean, min, max, median, q1, q3, stdev, iqr,
  validation, optional_benchmark_info, change_annotations,
  submission_key, submission_payload_sha256
)
VALUES (
  $1, $2, $3, $4, $5,
  $6, $7, $8, $9, $10, $11,
  $12, $13, $14, $15, $16, $17,
  $18, $19, $20, $21, $22, $23, $24, $25, $26, $27,
  $28, $29, $30, $31, $32
)
RETURNING id;

-- name: UpdateBenchmarkResultChangeAnnotations :one
UPDATE benchmark_result SET change_annotations = $2 WHERE id = $1 RETURNING id;

-- name: DeleteBenchmarkResult :one
DELETE FROM benchmark_result WHERE id = $1 RETURNING id;

-- name: CountBenchmarkResults :one
SELECT count(*) FROM benchmark_result;

-- name: GetBenchmarkResultByID :one
SELECT
  id, case_id, context_id, info_id, hardware_id,
  run_id, run_tags, run_reason, commit_id, commit_repo_url, history_fingerprint,
  "timestamp", unit, time_unit, batch_id, iterations, error,
  data, times, mean, min, max, median, q1, q3, stdev, iqr,
  validation, optional_benchmark_info, change_annotations,
  submission_key, submission_payload_sha256
FROM benchmark_result
WHERE id = $1;

-- name: GetBenchmarkResultBySubmissionKey :one
SELECT id, run_id, history_fingerprint, submission_payload_sha256
FROM benchmark_result
WHERE submission_key = $1;

-- name: GetBenchmarkResultDetail :one
-- The persisted result joined to its related entities, for the result-detail
-- read endpoint. Case/context/info/hardware are NOT NULL FKs (INNER JOIN); the
-- commit is optional (LEFT JOIN), so its columns are null for a commitless result.
SELECT
  br.id, br.run_id, br.run_tags, br.run_reason, br.batch_id,
  br."timestamp", br.commit_repo_url, br.history_fingerprint,
  br.unit, br.time_unit, br.iterations, br.error, br.data, br.times,
  br.mean, br.min, br.max, br.median, br.q1, br.q3, br.stdev, br.iqr,
  br.validation, br.optional_benchmark_info, br.change_annotations,
  cs.name AS case_name,
  cs.tags AS case_tags,
  ctx.tags AS context_tags,
  inf.tags AS info_tags,
  hw.id AS hardware_id,
  hw.type AS hardware_type,
  hw.name AS hardware_name,
  hw.hash AS hardware_hash,
  c.id AS commit_id,
  c.sha AS commit_sha,
  c.repository AS commit_repository,
  c.message AS commit_message,
  c."timestamp" AS commit_timestamp
FROM benchmark_result br
JOIN "case" cs ON cs.id = br.case_id
JOIN context ctx ON ctx.id = br.context_id
JOIN info inf ON inf.id = br.info_id
JOIN hardware hw ON hw.id = br.hardware_id
LEFT JOIN commit c ON c.id = br.commit_id
WHERE br.id = $1;

-- name: SelectBenchmarkResults :many
-- Minimal list/search: optional run_id/batch_id/run_reason/timestamp filters, cursor
-- pagination by UUIDv7 id (DESC, newest first), capped by page_size. The cursor
-- is the previous page's smallest id; id < cursor walks to older rows.
-- Note: the benchmark_result id/run_reason indexes are partial (predicated on a
-- timestamp lower bound from the frozen schema), so an unfiltered ORDER BY id DESC
-- falls back to a full scan; a timestamp filter lets the planner use them.
SELECT
  br.id,
  br.run_id,
  br.run_reason,
  br.run_tags,
  br.batch_id,
  br."timestamp",
  br.unit,
  br.data,
  br.error,
  br.history_fingerprint,
  cs.name AS case_name,
  cs.tags AS case_tags,
  c.sha AS commit_sha,
  c.repository AS commit_repository,
  c.message AS commit_message,
  c.author_name AS commit_author_name,
  c.author_login AS commit_author_login,
  c.author_avatar AS commit_author_avatar,
  c."timestamp" AS commit_timestamp
FROM benchmark_result br
JOIN "case" cs ON cs.id = br.case_id
LEFT JOIN commit c ON c.id = br.commit_id
WHERE (sqlc.narg('run_id')::text IS NULL OR br.run_id = sqlc.narg('run_id'))
  AND (sqlc.narg('batch_id')::text IS NULL OR br.batch_id = sqlc.narg('batch_id'))
  AND (sqlc.narg('run_reason')::text IS NULL OR br.run_reason = sqlc.narg('run_reason'))
  AND (sqlc.narg('earliest')::timestamp IS NULL OR br."timestamp" >= sqlc.narg('earliest'))
  AND (sqlc.narg('latest')::timestamp IS NULL OR br."timestamp" <= sqlc.narg('latest'))
  AND (sqlc.narg('cursor')::text IS NULL OR br.id < sqlc.narg('cursor'))
ORDER BY br.id DESC
LIMIT sqlc.arg('page_size');

-- name: SelectRecentRuns :many
-- Landing-page run summaries. Discover candidate run IDs from the newest result
-- rows using the timestamp index, then aggregate the selected run IDs exactly via
-- the run_id index. Repository filtering is applied after the bounded candidate
-- scan because commit_repo_url is not indexed in the frozen production schema.
-- This keeps the home page fast while still producing exact counts for the runs
-- shown on the page.
WITH candidate_rows AS MATERIALIZED (
  SELECT br.run_id, br."timestamp", br.commit_repo_url
  FROM benchmark_result br
  ORDER BY br."timestamp" DESC, br.id DESC
  LIMIT sqlc.arg('candidate_result_count')
),
selected_runs AS MATERIALIZED (
  SELECT cr.run_id, max(cr."timestamp") AS candidate_last_timestamp
  FROM candidate_rows cr
  WHERE (sqlc.narg('repository')::text IS NULL OR cr.commit_repo_url = sqlc.narg('repository')::text)
  GROUP BY cr.run_id
  ORDER BY max(cr."timestamp") DESC, cr.run_id DESC
  LIMIT sqlc.arg('page_size')
),
run_agg AS MATERIALIZED (
  SELECT
    br.run_id,
    min(br."timestamp")::timestamp AS first_result_at,
    max(br."timestamp")::timestamp AS last_result_at,
    count(*) AS result_count,
    count(*) FILTER (WHERE br.error IS NOT NULL) AS error_count,
    count(DISTINCT br.history_fingerprint) AS series_count,
    count(DISTINCT br.batch_id) FILTER (WHERE br.batch_id IS NOT NULL) AS batch_count
  FROM benchmark_result br
  JOIN selected_runs sr ON sr.run_id = br.run_id
  WHERE (sqlc.narg('repository')::text IS NULL OR br.commit_repo_url = sqlc.narg('repository')::text)
  GROUP BY br.run_id
)
SELECT
  a.run_id,
  a.first_result_at,
  a.last_result_at,
  a.result_count,
  a.error_count,
  a.series_count,
  a.batch_count,
  latest.id AS latest_result_id,
  latest.run_reason,
  latest.run_tags,
  latest.batch_id AS latest_batch_id,
  latest.commit_repo_url,
  c.sha AS commit_sha,
  c.repository AS commit_repository,
  c.message AS commit_message,
  c.author_name AS commit_author_name,
  c.author_login AS commit_author_login,
  c.author_avatar AS commit_author_avatar,
  c."timestamp" AS commit_timestamp
FROM run_agg a
JOIN LATERAL (
  SELECT br.id, br.run_reason, br.run_tags, br.batch_id, br.commit_repo_url, br.commit_id, br."timestamp"
  FROM benchmark_result br
  WHERE br.run_id = a.run_id
    AND (sqlc.narg('repository')::text IS NULL OR br.commit_repo_url = sqlc.narg('repository')::text)
  ORDER BY br."timestamp" DESC, br.id DESC
  LIMIT 1
) latest ON true
LEFT JOIN commit c ON c.id = latest.commit_id
ORDER BY a.last_result_at DESC, a.run_id DESC;
