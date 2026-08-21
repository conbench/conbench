-- name: SelectCIReportRunsByCommit :many
SELECT
  br.run_id,
  br.run_tags,
  br.run_reason,
  br.commit_repo_url,
  c.id AS commit_id,
  c.sha AS commit_sha,
  c.repository AS commit_repository,
  c.parent AS commit_parent,
  c.fork_point_sha AS commit_fork_point_sha,
  c."timestamp" AS commit_timestamp
FROM benchmark_result br
JOIN commit c ON c.id = br.commit_id
WHERE c.repository = sqlc.arg('repository')::text
  AND c.sha = sqlc.arg('sha')::text
GROUP BY
  br.run_id,
  br.run_tags,
  br.run_reason,
  br.commit_repo_url,
  c.id,
  c.sha,
  c.repository,
  c.parent,
  c.fork_point_sha,
  c."timestamp"
ORDER BY br.run_id;

-- name: SelectCIReportRunsByIDs :many
SELECT
  br.run_id,
  br.run_tags,
  br.run_reason,
  br.commit_repo_url,
  c.id AS commit_id,
  c.sha AS commit_sha,
  c.repository AS commit_repository,
  c.parent AS commit_parent,
  c.fork_point_sha AS commit_fork_point_sha,
  c."timestamp" AS commit_timestamp
FROM benchmark_result br
LEFT JOIN commit c ON c.id = br.commit_id
WHERE br.run_id = ANY(sqlc.arg('run_ids')::text[])
GROUP BY
  br.run_id,
  br.run_tags,
  br.run_reason,
  br.commit_repo_url,
  c.id,
  c.sha,
  c.repository,
  c.parent,
  c.fork_point_sha,
  c."timestamp"
ORDER BY br.run_id;

-- name: GetCIReportCommit :one
SELECT
  id AS commit_id,
  sha AS commit_sha,
  repository,
  parent,
  fork_point_sha,
  "timestamp",
  message
FROM commit
WHERE repository = sqlc.arg('repository')::text
  AND sha = sqlc.arg('sha')::text;

-- name: SelectLatestDefaultCommit :one
SELECT
  id AS commit_id,
  sha AS commit_sha,
  repository,
  parent,
  fork_point_sha,
  "timestamp",
  message
FROM commit
WHERE repository = sqlc.arg('repository')::text
  AND sha = fork_point_sha
  AND "timestamp" IS NOT NULL
ORDER BY "timestamp" DESC, sha DESC
LIMIT 1;

-- name: SelectCIReportBaselineAncestry :many
WITH RECURSIVE ancestry AS (
  SELECT
    id,
    sha,
    repository,
    parent,
    fork_point_sha,
    "timestamp",
    message,
    1::integer AS depth
  FROM commit
  WHERE repository = sqlc.arg('repository')::text
    AND sha = sqlc.arg('sha')::text
    AND sqlc.arg('ancestor_limit')::integer > 0

  UNION ALL

  SELECT
    c.id,
    c.sha,
    c.repository,
    c.parent,
    c.fork_point_sha,
    c."timestamp",
    c.message,
    ancestry.depth + 1 AS depth
  FROM ancestry
  JOIN commit c
    ON c.repository = ancestry.repository
   AND c.sha = ancestry.parent
  WHERE ancestry.depth < sqlc.arg('ancestor_limit')::integer
)
SELECT
  id AS commit_id,
  sha AS commit_sha,
  repository,
  parent,
  fork_point_sha,
  "timestamp",
  message
FROM ancestry
ORDER BY depth;

-- name: CountCIReportRows :one
WITH selected_runs AS (
  SELECT runs.run_id, commits.commit_id
  FROM unnest(sqlc.arg('run_ids')::text[]) WITH ORDINALITY AS runs(run_id, ord)
  JOIN unnest(sqlc.arg('commit_ids')::text[]) WITH ORDINALITY AS commits(commit_id, ord) USING (ord)
)
SELECT count(*)
FROM benchmark_result br
JOIN selected_runs selected
  ON selected.run_id = br.run_id
 AND selected.commit_id = br.commit_id;

-- name: SelectCIReportRows :many
WITH contender_runs AS MATERIALIZED (
  SELECT runs.run_id, commits.commit_id
  FROM unnest(sqlc.arg('contender_run_ids')::text[]) WITH ORDINALITY AS runs(run_id, ord)
  JOIN unnest(sqlc.arg('contender_commit_ids')::text[]) WITH ORDINALITY AS commits(commit_id, ord) USING (ord)
),
baseline_runs AS MATERIALIZED (
  SELECT runs.run_id, commits.commit_id
  FROM unnest(sqlc.arg('baseline_run_ids')::text[]) WITH ORDINALITY AS runs(run_id, ord)
  JOIN unnest(sqlc.arg('baseline_commit_ids')::text[]) WITH ORDINALITY AS commits(commit_id, ord) USING (ord)
),
contender_ids AS MATERIALIZED (
  SELECT
    br.id AS result_id,
    0 AS side_order
  FROM benchmark_result br
  JOIN contender_runs selected
    ON selected.run_id = br.run_id
   AND selected.commit_id = br.commit_id
),
contender_fingerprints AS MATERIALIZED (
  SELECT DISTINCT br.history_fingerprint
  FROM benchmark_result br
  JOIN contender_runs selected
    ON selected.run_id = br.run_id
   AND selected.commit_id = br.commit_id
),
baseline_ids AS MATERIALIZED (
  SELECT DISTINCT ON (br.run_id, br.commit_id, br.history_fingerprint)
    br.id AS result_id,
    1 AS side_order
  FROM benchmark_result br
  JOIN baseline_runs selected
    ON selected.run_id = br.run_id
   AND selected.commit_id = br.commit_id
  JOIN contender_fingerprints cf
    ON cf.history_fingerprint = br.history_fingerprint
  ORDER BY
    br.run_id,
    br.commit_id,
    br.history_fingerprint,
    br."timestamp" DESC,
    br.id DESC
),
selected_ids AS (
  SELECT result_id, side_order FROM contender_ids
  UNION ALL
  SELECT result_id, side_order FROM baseline_ids
)
SELECT
  br.id AS result_id,
  br.run_id,
  br."timestamp" AS result_timestamp,
  br.history_fingerprint,
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
  c.parent AS commit_parent,
  c.fork_point_sha AS commit_fork_point_sha,
  c."timestamp" AS commit_timestamp,
  br.unit,
  br.data,
  br.error,
  br.change_annotations
FROM selected_ids selected
JOIN benchmark_result br ON br.id = selected.result_id
JOIN "case" cs ON cs.id = br.case_id
JOIN context ctx ON ctx.id = br.context_id
JOIN info inf ON inf.id = br.info_id
JOIN hardware hw ON hw.id = br.hardware_id
LEFT JOIN commit c ON c.id = br.commit_id
ORDER BY selected.side_order, br.run_id, br.history_fingerprint, br."timestamp", br.id;
