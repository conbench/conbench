-- name: GetCaseByNameTags :one
SELECT id FROM "case" WHERE name = $1 AND tags = $2;

-- name: InsertCase :one
-- ON CONFLICT (name, tags) DO NOTHING backstops the rare get-or-create race;
-- on conflict no row is returned and the caller re-selects.
INSERT INTO "case" (id, name, tags)
VALUES ($1, $2, $3)
ON CONFLICT (name, tags) DO NOTHING
RETURNING id;
