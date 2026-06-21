-- name: InsertAPIToken :one
INSERT INTO api_token (id, user_id, name, token_hash, token_prefix, created_at)
VALUES ($1, $2, $3, $4, $5, $6)
RETURNING id;

-- name: GetAPITokenByHash :one
SELECT * FROM api_token WHERE token_hash = $1;

-- name: TouchAPITokenLastUsed :exec
UPDATE api_token SET last_used_at = $2 WHERE id = $1;

-- name: RevokeAPIToken :execrows
UPDATE api_token SET revoked_at = $2 WHERE id = $1;

-- name: ListAPITokensByUser :many
SELECT * FROM api_token WHERE user_id = $1 ORDER BY created_at DESC;

-- name: GetAPITokenByID :one
SELECT * FROM api_token WHERE id = $1;
