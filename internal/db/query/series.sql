-- name: SelectSeriesPage :many
-- One row per history-fingerprint, scoped to history membership (non-errored,
-- default-branch sha==fork_point_sha, commit-joined, non-null commit timestamp).
-- The membership predicates are identical to SelectHistoryForFingerprint in
-- history.sql, which is canonical for "what belongs to a series' history".
--
-- Default browse is a discovery surface, so it starts from a bounded window of
-- recent default-branch commits that actually carry benchmark results. The exact
-- global latest-per-fingerprint query is too expensive on production-sized
-- history tables; exact lookups remain available through q/fingerprint paths.
-- The seed is a raw bounded candidate window. Cursor visibility/dedup filters
-- are applied after this window so cursor pages cannot back-scan arbitrarily far
-- through already-emitted hot fingerprints.
WITH recent_commit_seed AS MATERIALIZED (
  SELECT c.id, c.sha AS commit_sha, c."timestamp" AS commit_timestamp
  FROM commit c
  WHERE c.sha = c.fork_point_sha
    AND c."timestamp" IS NOT NULL
    AND (sqlc.narg('active_since')::timestamp IS NULL OR c."timestamp" >= sqlc.narg('active_since')::timestamp)
    AND (sqlc.narg('active_until')::timestamp IS NULL OR c."timestamp" <= sqlc.narg('active_until')::timestamp)
    AND (sqlc.narg('cursor_ts')::timestamp IS NULL OR c."timestamp" < sqlc.narg('cursor_ts')::timestamp)
    AND EXISTS (
      SELECT 1
      FROM benchmark_result br
      WHERE br.commit_id = c.id
        AND br.error IS NULL
        AND (sqlc.narg('repository')::text IS NULL OR br.commit_repo_url = sqlc.narg('repository'))
        AND (
          sqlc.narg('hardware')::text IS NULL
          OR EXISTS (
            SELECT 1
            FROM hardware seed_hw
            WHERE seed_hw.id = br.hardware_id
              AND seed_hw.name = sqlc.narg('hardware')::text
          )
        )
    )
  ORDER BY c."timestamp" DESC, c.id DESC
  LIMIT sqlc.arg('search_commit_limit')::integer
),
recent_commit_boundary AS (
  SELECT min(commit_timestamp) AS min_commit_timestamp
  FROM recent_commit_seed
),
recent_commit AS MATERIALIZED (
  SELECT c.id, c.sha AS commit_sha, c."timestamp" AS commit_timestamp
  FROM commit c
  WHERE c.sha = c.fork_point_sha
    AND c."timestamp" IS NOT NULL
    AND (sqlc.narg('active_since')::timestamp IS NULL OR c."timestamp" >= sqlc.narg('active_since')::timestamp)
    AND (sqlc.narg('active_until')::timestamp IS NULL OR c."timestamp" <= sqlc.narg('active_until')::timestamp)
    AND (
      (sqlc.narg('cursor_ts')::timestamp IS NOT NULL AND c."timestamp" = sqlc.narg('cursor_ts')::timestamp)
      OR (
        (sqlc.narg('cursor_ts')::timestamp IS NULL OR c."timestamp" < sqlc.narg('cursor_ts')::timestamp)
        AND (
          (SELECT min_commit_timestamp FROM recent_commit_boundary) IS NOT NULL
          AND c."timestamp" >= (SELECT min_commit_timestamp FROM recent_commit_boundary)
        )
      )
    )
    AND EXISTS (
      SELECT 1
      FROM benchmark_result br
      WHERE br.commit_id = c.id
        AND br.error IS NULL
        AND (sqlc.narg('repository')::text IS NULL OR br.commit_repo_url = sqlc.narg('repository'))
        AND (
          sqlc.narg('hardware')::text IS NULL
          OR EXISTS (
            SELECT 1
            FROM hardware seed_hw
            WHERE seed_hw.id = br.hardware_id
              AND seed_hw.name = sqlc.narg('hardware')::text
          )
        )
    )
),
members AS MATERIALIZED (
  SELECT
    br.history_fingerprint, br.id, br."timestamp" AS result_timestamp,
    br.unit, br.data, br.case_id, br.context_id, br.hardware_id,
    br.commit_repo_url, rc.commit_sha, rc.commit_timestamp
  FROM recent_commit rc
  JOIN benchmark_result br ON br.commit_id = rc.id
  JOIN hardware hw ON hw.id = br.hardware_id
  WHERE br.error IS NULL
    AND (sqlc.narg('hardware')::text IS NULL OR hw.name = sqlc.narg('hardware'))
    AND (sqlc.narg('repository')::text IS NULL OR br.commit_repo_url = sqlc.narg('repository'))
    AND (
      sqlc.narg('cursor_ts')::timestamp IS NULL
      OR NOT EXISTS (
        SELECT 1
        FROM benchmark_result newer
        JOIN commit newer_c ON newer_c.id = newer.commit_id
        WHERE newer.history_fingerprint = br.history_fingerprint
          AND newer.error IS NULL
          AND newer_c.sha = newer_c.fork_point_sha
          AND newer_c."timestamp" IS NOT NULL
          AND (sqlc.narg('active_since')::timestamp IS NULL OR newer_c."timestamp" >= sqlc.narg('active_since')::timestamp)
          AND (sqlc.narg('active_until')::timestamp IS NULL OR newer_c."timestamp" <= sqlc.narg('active_until')::timestamp)
          AND (sqlc.narg('repository')::text IS NULL OR newer.commit_repo_url = sqlc.narg('repository'))
          AND (
            sqlc.narg('hardware')::text IS NULL
            OR EXISTS (
              SELECT 1
              FROM hardware newer_hw
              WHERE newer_hw.id = newer.hardware_id
                AND newer_hw.name = sqlc.narg('hardware')::text
            )
          )
          AND (newer_c."timestamp", newer.history_fingerprint)
             >= (sqlc.narg('cursor_ts')::timestamp, sqlc.narg('cursor_fp')::text)
      )
    )
),
latest AS (
  SELECT DISTINCT ON (history_fingerprint)
    history_fingerprint, id, result_timestamp, unit, data,
    case_id, context_id, hardware_id, commit_repo_url, commit_sha, commit_timestamp
  FROM members
  ORDER BY history_fingerprint, commit_timestamp DESC, id DESC
),
page AS MATERIALIZED (
  SELECT
    l.history_fingerprint,
    l.id AS latest_result_id,
    l.result_timestamp AS latest_result_timestamp,
    l.commit_sha AS latest_commit_sha,
    l.commit_timestamp AS latest_commit_timestamp,
    l.commit_repo_url,
    l.unit AS latest_unit,
    -- The CTE alias escapes the benchmark_result.data column override, so sqlc
    -- maps latest_data to dense []float64 — intentionally: members are
    -- non-errored, and only errored rows can hold null elements.
    l.data AS latest_data,
    cs.name AS case_name, cs.tags AS case_tags, ctx.tags AS context_tags,
    hw.id AS hardware_id, hw.name AS hardware_name, hw.type AS hardware_type, hw.hash AS hardware_hash
  FROM latest l
  JOIN "case" cs ON cs.id = l.case_id
  JOIN context ctx ON ctx.id = l.context_id
  JOIN hardware hw ON hw.id = l.hardware_id
  WHERE (sqlc.narg('hardware')::text IS NULL OR hw.name = sqlc.narg('hardware'))
    AND (sqlc.narg('repository')::text IS NULL OR l.commit_repo_url = sqlc.narg('repository'))
    AND (sqlc.narg('active_since')::timestamp IS NULL OR l.commit_timestamp >= sqlc.narg('active_since'))
    AND (sqlc.narg('active_until')::timestamp IS NULL OR l.commit_timestamp <= sqlc.narg('active_until'))
    AND (
      sqlc.narg('cursor_ts')::timestamp IS NULL
      OR (l.commit_timestamp, l.history_fingerprint)
         < (sqlc.narg('cursor_ts')::timestamp, sqlc.narg('cursor_fp')::text)
    )
  ORDER BY l.commit_timestamp DESC, l.history_fingerprint DESC
  LIMIT sqlc.arg('page_size')
),
counts AS (
  SELECT br.history_fingerprint, count(*)::bigint AS point_count
  FROM benchmark_result br
  JOIN commit c ON c.id = br.commit_id
  JOIN page p ON p.history_fingerprint = br.history_fingerprint
  WHERE br.error IS NULL
    AND c.sha = c.fork_point_sha
    AND c."timestamp" IS NOT NULL
  GROUP BY br.history_fingerprint
)
SELECT
  p.history_fingerprint,
  p.latest_result_id,
  p.latest_result_timestamp,
  p.latest_commit_sha,
  p.latest_commit_timestamp,
  p.commit_repo_url,
  p.latest_unit,
  p.latest_data,
  cnt.point_count,
  p.case_name, p.case_tags, p.context_tags,
  p.hardware_id, p.hardware_name, p.hardware_type, p.hardware_hash
FROM page p
JOIN counts cnt ON cnt.history_fingerprint = p.history_fingerprint
ORDER BY p.latest_commit_timestamp DESC, p.history_fingerprint DESC;

-- name: SelectSeriesCaseIDsForQ :many
SELECT id
FROM "case"
WHERE name ILIKE '%' || sqlc.arg('q')::text || '%'
   OR tags::text ILIKE '%' || sqlc.arg('q')::text || '%'
ORDER BY id;

-- name: SelectSeriesPageForQCaseIDs :many
-- Narrow q searches keep full historical semantics. The matching case ids are
-- resolved before this query so the benchmark_result branch can start from the
-- case_id index. The OFFSET 0 subquery is intentional: it prevents the planner
-- from reordering the branch back into a default-commit scan on large clones.
WITH matched_case(id) AS MATERIALIZED (
  SELECT unnest(sqlc.arg('case_ids')::varchar(50)[])
),
members AS MATERIALIZED (
  SELECT
    br.history_fingerprint, br.id, br."timestamp" AS result_timestamp,
    br.unit, br.data, br.case_id, br.context_id, br.hardware_id,
    br.commit_repo_url, c.sha AS commit_sha, c."timestamp" AS commit_timestamp
  FROM matched_case mc
  CROSS JOIN LATERAL (
    SELECT history_fingerprint, id, "timestamp", unit, data,
           case_id, context_id, hardware_id, commit_repo_url, commit_id
    FROM benchmark_result
    WHERE case_id = mc.id
      AND error IS NULL
      AND (sqlc.narg('repository')::text IS NULL OR commit_repo_url = sqlc.narg('repository'))
    OFFSET 0
  ) br
  JOIN commit c ON c.id = br.commit_id
  JOIN hardware hw ON hw.id = br.hardware_id
  WHERE c.sha = c.fork_point_sha
    AND c."timestamp" IS NOT NULL
    AND (sqlc.narg('hardware')::text IS NULL OR hw.name = sqlc.narg('hardware'))
    AND (sqlc.narg('active_since')::timestamp IS NULL OR c."timestamp" >= sqlc.narg('active_since'))
    AND (sqlc.narg('active_until')::timestamp IS NULL OR c."timestamp" <= sqlc.narg('active_until'))
),
latest AS (
  SELECT DISTINCT ON (history_fingerprint)
    history_fingerprint, id, result_timestamp, unit, data,
    case_id, context_id, hardware_id, commit_repo_url, commit_sha, commit_timestamp
  FROM members
  ORDER BY history_fingerprint, commit_timestamp DESC, id DESC
),
page AS MATERIALIZED (
  SELECT
    l.history_fingerprint,
    l.id AS latest_result_id,
    l.result_timestamp AS latest_result_timestamp,
    l.commit_sha AS latest_commit_sha,
    l.commit_timestamp AS latest_commit_timestamp,
    l.commit_repo_url,
    l.unit AS latest_unit,
    l.data AS latest_data,
    cs.name AS case_name, cs.tags AS case_tags, ctx.tags AS context_tags,
    hw.id AS hardware_id, hw.name AS hardware_name, hw.type AS hardware_type, hw.hash AS hardware_hash
  FROM latest l
  JOIN "case" cs ON cs.id = l.case_id
  JOIN context ctx ON ctx.id = l.context_id
  JOIN hardware hw ON hw.id = l.hardware_id
  WHERE (
      sqlc.narg('cursor_ts')::timestamp IS NULL
      OR (l.commit_timestamp, l.history_fingerprint)
         < (sqlc.narg('cursor_ts')::timestamp, sqlc.narg('cursor_fp')::text)
    )
  ORDER BY l.commit_timestamp DESC, l.history_fingerprint DESC
  LIMIT sqlc.arg('page_size')
),
counts AS (
  SELECT br.history_fingerprint, count(*)::bigint AS point_count
  FROM benchmark_result br
  JOIN commit c ON c.id = br.commit_id
  JOIN page p ON p.history_fingerprint = br.history_fingerprint
  WHERE br.error IS NULL
    AND c.sha = c.fork_point_sha
    AND c."timestamp" IS NOT NULL
  GROUP BY br.history_fingerprint
)
SELECT
  p.history_fingerprint,
  p.latest_result_id,
  p.latest_result_timestamp,
  p.latest_commit_sha,
  p.latest_commit_timestamp,
  p.commit_repo_url,
  p.latest_unit,
  p.latest_data,
  cnt.point_count,
  p.case_name, p.case_tags, p.context_tags,
  p.hardware_id, p.hardware_name, p.hardware_type, p.hardware_hash
FROM page p
JOIN counts cnt ON cnt.history_fingerprint = p.history_fingerprint
ORDER BY p.latest_commit_timestamp DESC, p.history_fingerprint DESC;

-- name: SelectSeriesPageForQRecent :many
-- Broad q searches are discovery queries, not exhaustive history rollups. When
-- q matches many case ids, full latest-per-fingerprint aggregation can exceed
-- statement_timeout on 100M-row clones, so this path searches a bounded newest
-- default-commit window and then applies the same latest/page/count shape.
WITH matched_case(id) AS MATERIALIZED (
  SELECT unnest(sqlc.arg('case_ids')::varchar(50)[])
),
recent_commit_seed AS MATERIALIZED (
  SELECT id, sha AS commit_sha, "timestamp" AS commit_timestamp
  FROM commit
  WHERE sha = fork_point_sha
    AND "timestamp" IS NOT NULL
    AND (sqlc.narg('active_until')::timestamp IS NULL OR "timestamp" <= sqlc.narg('active_until')::timestamp)
    AND (sqlc.narg('cursor_ts')::timestamp IS NULL OR "timestamp" < sqlc.narg('cursor_ts')::timestamp)
  ORDER BY "timestamp" DESC, id DESC
  LIMIT sqlc.arg('search_commit_limit')::integer
),
recent_commit_boundary AS (
  SELECT min(commit_timestamp) AS min_commit_timestamp
  FROM recent_commit_seed
),
recent_commit AS MATERIALIZED (
  SELECT id, sha AS commit_sha, "timestamp" AS commit_timestamp
  FROM commit
  WHERE sha = fork_point_sha
    AND "timestamp" IS NOT NULL
    AND (sqlc.narg('active_until')::timestamp IS NULL OR "timestamp" <= sqlc.narg('active_until')::timestamp)
    AND (
      (sqlc.narg('cursor_ts')::timestamp IS NOT NULL AND "timestamp" = sqlc.narg('cursor_ts')::timestamp)
      OR (
        (sqlc.narg('cursor_ts')::timestamp IS NULL OR "timestamp" < sqlc.narg('cursor_ts')::timestamp)
        AND (
          (SELECT min_commit_timestamp FROM recent_commit_boundary) IS NULL
          OR "timestamp" >= (SELECT min_commit_timestamp FROM recent_commit_boundary)
        )
      )
    )
),
members AS MATERIALIZED (
  SELECT
    br.history_fingerprint, br.id, br."timestamp" AS result_timestamp,
    br.unit, br.data, br.case_id, br.context_id, br.hardware_id,
    br.commit_repo_url, rc.commit_sha, rc.commit_timestamp
  FROM recent_commit rc
  JOIN benchmark_result br ON br.commit_id = rc.id
  JOIN matched_case mc ON mc.id = br.case_id
  JOIN hardware hw ON hw.id = br.hardware_id
  WHERE br.error IS NULL
    AND (sqlc.narg('hardware')::text IS NULL OR hw.name = sqlc.narg('hardware'))
    AND (sqlc.narg('repository')::text IS NULL OR br.commit_repo_url = sqlc.narg('repository'))
    AND (sqlc.narg('active_since')::timestamp IS NULL OR rc.commit_timestamp >= sqlc.narg('active_since'))
    AND (
      sqlc.narg('cursor_ts')::timestamp IS NULL
      OR NOT EXISTS (
        SELECT 1
        FROM benchmark_result newer
        JOIN commit newer_c ON newer_c.id = newer.commit_id
        WHERE newer.history_fingerprint = br.history_fingerprint
          AND newer.error IS NULL
          AND newer_c.sha = newer_c.fork_point_sha
          AND newer_c."timestamp" IS NOT NULL
          AND (newer_c."timestamp", newer.history_fingerprint)
             >= (sqlc.narg('cursor_ts')::timestamp, sqlc.narg('cursor_fp')::text)
      )
    )
),
latest AS (
  SELECT DISTINCT ON (history_fingerprint)
    history_fingerprint, id, result_timestamp, unit, data,
    case_id, context_id, hardware_id, commit_repo_url, commit_sha, commit_timestamp
  FROM members
  ORDER BY history_fingerprint, commit_timestamp DESC, id DESC
),
page AS MATERIALIZED (
  SELECT
    l.history_fingerprint,
    l.id AS latest_result_id,
    l.result_timestamp AS latest_result_timestamp,
    l.commit_sha AS latest_commit_sha,
    l.commit_timestamp AS latest_commit_timestamp,
    l.commit_repo_url,
    l.unit AS latest_unit,
    l.data AS latest_data,
    cs.name AS case_name, cs.tags AS case_tags, ctx.tags AS context_tags,
    hw.id AS hardware_id, hw.name AS hardware_name, hw.type AS hardware_type, hw.hash AS hardware_hash
  FROM latest l
  JOIN "case" cs ON cs.id = l.case_id
  JOIN context ctx ON ctx.id = l.context_id
  JOIN hardware hw ON hw.id = l.hardware_id
  WHERE (
      sqlc.narg('cursor_ts')::timestamp IS NULL
      OR (l.commit_timestamp, l.history_fingerprint)
         < (sqlc.narg('cursor_ts')::timestamp, sqlc.narg('cursor_fp')::text)
    )
  ORDER BY l.commit_timestamp DESC, l.history_fingerprint DESC
  LIMIT sqlc.arg('page_size')
),
counts AS (
  SELECT br.history_fingerprint, count(*)::bigint AS point_count
  FROM benchmark_result br
  JOIN commit c ON c.id = br.commit_id
  JOIN page p ON p.history_fingerprint = br.history_fingerprint
  WHERE br.error IS NULL
    AND c.sha = c.fork_point_sha
    AND c."timestamp" IS NOT NULL
  GROUP BY br.history_fingerprint
)
SELECT
  p.history_fingerprint,
  p.latest_result_id,
  p.latest_result_timestamp,
  p.latest_commit_sha,
  p.latest_commit_timestamp,
  p.commit_repo_url,
  p.latest_unit,
  p.latest_data,
  cnt.point_count,
  p.case_name, p.case_tags, p.context_tags,
  p.hardware_id, p.hardware_name, p.hardware_type, p.hardware_hash
FROM page p
JOIN counts cnt ON cnt.history_fingerprint = p.history_fingerprint
ORDER BY p.latest_commit_timestamp DESC, p.history_fingerprint DESC;

-- name: SelectSeriesPageForFingerprint :many
-- Fingerprint lookups use an exact query shape so production-sized clones can
-- use the history_fingerprint index immediately instead of planning the generic
-- nullable-filter browse query.
WITH members AS MATERIALIZED (
  SELECT
    br.history_fingerprint, br.id, br."timestamp" AS result_timestamp,
    br.unit, br.data, br.case_id, br.context_id, br.hardware_id,
    br.commit_repo_url, c.sha AS commit_sha, c."timestamp" AS commit_timestamp
  FROM benchmark_result br
  JOIN commit c ON c.id = br.commit_id
  WHERE br.error IS NULL
    AND br.history_fingerprint = sqlc.arg('fingerprint')::text
    AND c.sha = c.fork_point_sha
    AND c."timestamp" IS NOT NULL
    AND (sqlc.narg('active_since')::timestamp IS NULL OR c."timestamp" >= sqlc.narg('active_since')::timestamp)
    AND (sqlc.narg('active_until')::timestamp IS NULL OR c."timestamp" <= sqlc.narg('active_until')::timestamp)
    AND (
      sqlc.narg('cursor_ts')::timestamp IS NULL
      OR (c."timestamp", br.history_fingerprint)
         < (sqlc.narg('cursor_ts')::timestamp, sqlc.narg('cursor_fp')::text)
    )
),
latest AS (
  SELECT DISTINCT ON (history_fingerprint)
    history_fingerprint, id, result_timestamp, unit, data,
    case_id, context_id, hardware_id, commit_repo_url, commit_sha, commit_timestamp
  FROM members
  ORDER BY history_fingerprint, commit_timestamp DESC, id DESC
),
page AS MATERIALIZED (
  SELECT
    l.history_fingerprint,
    l.id AS latest_result_id,
    l.result_timestamp AS latest_result_timestamp,
    l.commit_sha AS latest_commit_sha,
    l.commit_timestamp AS latest_commit_timestamp,
    l.commit_repo_url,
    l.unit AS latest_unit,
    l.data AS latest_data,
    cs.name AS case_name, cs.tags AS case_tags, ctx.tags AS context_tags,
    hw.id AS hardware_id, hw.name AS hardware_name, hw.type AS hardware_type, hw.hash AS hardware_hash
  FROM latest l
  JOIN "case" cs ON cs.id = l.case_id
  JOIN context ctx ON ctx.id = l.context_id
  JOIN hardware hw ON hw.id = l.hardware_id
  WHERE (sqlc.narg('q')::text IS NULL
         OR cs.name ILIKE '%' || sqlc.narg('q') || '%'
         OR cs.tags::text ILIKE '%' || sqlc.narg('q') || '%')
    AND (sqlc.narg('hardware')::text IS NULL OR hw.name = sqlc.narg('hardware'))
    AND (sqlc.narg('repository')::text IS NULL OR l.commit_repo_url = sqlc.narg('repository'))
  ORDER BY l.commit_timestamp DESC, l.history_fingerprint DESC
  LIMIT sqlc.arg('page_size')
),
counts AS (
  SELECT br.history_fingerprint, count(*)::bigint AS point_count
  FROM benchmark_result br
  JOIN commit c ON c.id = br.commit_id
  JOIN page p ON p.history_fingerprint = br.history_fingerprint
  WHERE br.error IS NULL
    AND c.sha = c.fork_point_sha
    AND c."timestamp" IS NOT NULL
  GROUP BY br.history_fingerprint
)
SELECT
  p.history_fingerprint,
  p.latest_result_id,
  p.latest_result_timestamp,
  p.latest_commit_sha,
  p.latest_commit_timestamp,
  p.commit_repo_url,
  p.latest_unit,
  p.latest_data,
  cnt.point_count,
  p.case_name, p.case_tags, p.context_tags,
  p.hardware_id, p.hardware_name, p.hardware_type, p.hardware_hash
FROM page p
JOIN counts cnt ON cnt.history_fingerprint = p.history_fingerprint
ORDER BY p.latest_commit_timestamp DESC, p.history_fingerprint DESC;

-- name: SelectSeriesMembers :many
-- Recent membership rows (same definition as SelectHistoryForFingerprint) for a
-- set of fingerprints, for per-series status/sparkline. History/detail endpoints
-- still return full history; browse/search rows intentionally use a bounded tail
-- so high-cardinality production series cannot dominate page load time. Ordered
-- by fingerprint then commit time so the service can group in one pass.
WITH requested(fingerprint) AS MATERIALIZED (
  SELECT unnest(sqlc.arg('fingerprints')::text[])
),
members AS MATERIALIZED (
  SELECT m.*
  FROM requested req
  CROSS JOIN LATERAL (
    SELECT
      br.id,
      br.history_fingerprint,
      br."timestamp",
      br.unit,
      br.mean,
      br.data,
      br.change_annotations,
      hw.hash AS hardware_hash,
      c.sha AS commit_sha,
      c.repository AS commit_repository,
      c.message AS commit_message,
      c."timestamp" AS commit_timestamp
    FROM (
      SELECT id, history_fingerprint, "timestamp", unit, mean, data,
             change_annotations, hardware_id, commit_id
      FROM benchmark_result
      WHERE error IS NULL
        AND history_fingerprint = req.fingerprint
      OFFSET 0
    ) br
    JOIN hardware hw ON hw.id = br.hardware_id
    JOIN commit c ON c.id = br.commit_id
    WHERE c.sha = c.fork_point_sha
      AND c."timestamp" IS NOT NULL
    ORDER BY c."timestamp" DESC, br.id DESC
    LIMIT sqlc.arg('per_fingerprint_limit')::integer
  ) m
)
SELECT
  id,
  history_fingerprint,
  "timestamp",
  unit,
  mean,
  data,
  change_annotations,
  hardware_hash,
  commit_sha,
  commit_repository,
  commit_message,
  commit_timestamp
FROM members
ORDER BY history_fingerprint, commit_timestamp, id;
