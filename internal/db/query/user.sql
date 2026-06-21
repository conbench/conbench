-- name: GetUserByEmail :one
SELECT id FROM "user" WHERE email = $1;

-- name: InsertUser :one
INSERT INTO "user" (id, email, name, password)
VALUES ($1, $2, $3, $4)
ON CONFLICT (email) DO NOTHING
RETURNING id;

-- name: GetUserByID :one
SELECT id, email, name FROM "user" WHERE id = $1;
