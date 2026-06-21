-- name: GetResultForCompare :one
-- The fields the compare endpoint needs for one result: SVS inputs (unit, data,
-- error), the history fingerprint, the run id, and the commit timestamp (for the
-- baseline ancestry cutoff). The commit is optional (LEFT JOIN).
SELECT
  br.id,
  br.run_id,
  br.history_fingerprint,
  br.unit,
  br.data,
  br.error,
  br.commit_id,
  c."timestamp" AS commit_timestamp
FROM benchmark_result br
LEFT JOIN commit c ON c.id = br.commit_id
WHERE br.id = $1;
