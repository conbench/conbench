-- name: GetInfoByTags :one
SELECT id FROM info WHERE tags = $1;

-- name: InsertInfo :one
-- info has no unique index (migration drop_info_index), so there is no ON
-- CONFLICT target; dedup relies on the prior SELECT. A race may duplicate, which
-- the legacy get_or_create also tolerates for unconstrained keys.
INSERT INTO info (id, tags)
VALUES ($1, $2)
RETURNING id;
