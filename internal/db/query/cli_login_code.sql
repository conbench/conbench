-- name: DeleteExpiredCLILoginCodes :exec
DELETE FROM cli_login_code WHERE expires_at < $1;

-- name: InsertCLILoginCode :exec
INSERT INTO cli_login_code (code_hash, user_id, created_at, expires_at)
VALUES ($1, $2, $3, $4);

-- name: RedeemCLILoginCode :one
UPDATE cli_login_code
SET redeemed_at = $2
WHERE code_hash = $1
  AND redeemed_at IS NULL
  AND expires_at >= $2
RETURNING user_id;
