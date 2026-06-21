-- name: GetContextByTags :one
SELECT id FROM context WHERE tags = $1;

-- name: InsertContext :one
INSERT INTO context (id, tags)
VALUES ($1, $2)
ON CONFLICT (tags) DO NOTHING
RETURNING id;
