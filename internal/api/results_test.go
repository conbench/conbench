package api_test

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"net/http"
	"testing"
	"time"

	"github.com/danielgtaylor/huma/v2/humatest"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/conbench/conbench/internal/api"
	"github.com/conbench/conbench/internal/auth"
	"github.com/conbench/conbench/internal/commit"
	"github.com/conbench/conbench/internal/db"
	"github.com/conbench/conbench/internal/dbtest"
	"github.com/conbench/conbench/internal/service"
	"github.com/conbench/conbench/internal/storage"
)

const testToken = "test-token"

func newAPI(t *testing.T) (humatest.TestAPI, *db.Store, context.Context) {
	t.Helper()
	pool, ctx := dbtest.NewPool(t)
	store := db.NewStore(pool)
	h := api.NewHandler(service.NewIngester(store, commit.LocalProvider{}), service.NewReader(store), auth.New(testToken, false, store, nil))
	_, tapi := humatest.New(t)
	h.Register(tapi)
	return tapi, store, ctx
}

func canonicalBodySHA256(t *testing.T, body map[string]any) string {
	t.Helper()
	payload, err := json.Marshal(body)
	require.NoError(t, err)
	var req service.SubmitRequest
	require.NoError(t, json.Unmarshal(payload, &req))
	req.SubmissionKey = ""
	req.SubmissionPayloadSHA256 = ""
	canonical, err := json.Marshal(req)
	require.NoError(t, err)
	digest := sha256.Sum256(canonical)
	return hex.EncodeToString(digest[:])
}

// validBody is a well-formed result payload that passes huma schema validation,
// so the service layer (not huma) decides the outcome.
func validBody() map[string]any {
	return map[string]any{
		"tags":    map[string]any{"name": "bench", "source": "test"},
		"context": map[string]any{"compiler": "gcc"},
		"info":    map[string]any{"build": "release"},
		"machine_info": map[string]any{
			"name": "m1", "architecture_name": "x86_64",
			"cpu_core_count": 8, "cpu_thread_count": 16,
			"memory_bytes": 17179869184, "gpu_count": 0,
		},
		"github":    map[string]any{"commit": "abc123", "repository": "https://github.com/org/repo"},
		"run_id":    "run-1",
		"batch_id":  "batch-1",
		"timestamp": "2024-01-02T03:04:05Z",
		"stats":     map[string]any{"data": []float64{1, 2, 3}, "unit": "s"},
	}
}

func TestPostResultsCreates(t *testing.T) {
	tapi, store, ctx := newAPI(t)

	resp := tapi.Post("/api/results", "Authorization: Bearer "+testToken, validBody())
	require.Equal(t, http.StatusCreated, resp.Code, "body = %s", resp.Body.String())
	var out struct {
		ID                 string `json:"id"`
		RunID              string `json:"run_id"`
		HistoryFingerprint string `json:"history_fingerprint"`
	}
	require.NoError(t, json.Unmarshal(resp.Body.Bytes(), &out))
	require.NotEmpty(t, out.ID, "missing fields in response: %s", resp.Body.String())
	assert.Equal(t, "run-1", out.RunID)
	require.NotEmpty(t, out.HistoryFingerprint, "missing fields in response: %s", resp.Body.String())

	// The result actually landed in the frozen schema.
	row, err := store.GetBenchmarkResultByID(ctx, out.ID)
	require.NoError(t, err)
	if row.Unit == nil || *row.Unit != "s" || len(row.Data) != 3 || row.CommitID == nil {
		assert.Failf(t, "stored row mismatch", "unit=%v data=%v commit=%v", row.Unit, row.Data, row.CommitID)
	}
}

func TestPostResultsSubmissionConflictReturns409(t *testing.T) {
	tapi, _, _ := newAPI(t)
	body := validBody()
	body["submission_key"] = "publisher-0000000000000001"
	body["submission_payload_sha256"] = canonicalBodySHA256(t, body)
	first := tapi.Post("/api/results", "Authorization: Bearer "+testToken, body)
	require.Equal(t, http.StatusCreated, first.Code, "body = %s", first.Body.String())

	changed := validBody()
	changed["submission_key"] = body["submission_key"]
	changed["stats"] = map[string]any{"data": []float64{4, 5, 6}, "unit": "s"}
	changed["submission_payload_sha256"] = canonicalBodySHA256(t, changed)
	conflict := tapi.Post("/api/results", "Authorization: Bearer "+testToken, changed)
	assert.Equal(t, http.StatusConflict, conflict.Code, "body = %s", conflict.Body.String())
}

// TestPostResultsGithubBranchAndPRNumber pins the new wire fields: explicit
// nulls are accepted (legacy allows null for both), and a stringified
// pr_number is a 422 (approved deviation from marshmallow's leniency).
func TestPostResultsGithubBranchAndPRNumber(t *testing.T) {
	tapi, _, _ := newAPI(t)

	body := validBody()
	body["github"] = map[string]any{
		"commit": "abc123", "repository": "https://github.com/org/repo",
		"branch": nil, "pr_number": nil,
	}
	resp := tapi.Post("/api/results", "Authorization: Bearer "+testToken, body)
	require.Equal(t, http.StatusCreated, resp.Code, "body = %s", resp.Body.String())

	body = validBody()
	body["github"] = map[string]any{
		"commit": "abc124", "repository": "https://github.com/org/repo",
		"branch": "org:feature", "pr_number": 7,
	}
	resp = tapi.Post("/api/results", "Authorization: Bearer "+testToken, body)
	require.Equal(t, http.StatusCreated, resp.Code, "body = %s", resp.Body.String())

	body = validBody()
	body["github"] = map[string]any{
		"commit": "abc125", "repository": "https://github.com/org/repo",
		"pr_number": "7",
	}
	resp = tapi.Post("/api/results", "Authorization: Bearer "+testToken, body)
	require.Equal(t, http.StatusUnprocessableEntity, resp.Code, "stringified pr_number must be rejected; body = %s", resp.Body.String())
}

func TestPostResultsRejectsBadAuth(t *testing.T) {
	tapi, _, _ := newAPI(t)

	for _, h := range []string{"", "Bearer wrong", "Basic x"} {
		args := []any{validBody()}
		if h != "" {
			args = append([]any{"Authorization: " + h}, args...)
		}
		resp := tapi.Post("/api/results", args...)
		assert.Equal(t, http.StatusUnauthorized, resp.Code, "auth %q", h)
	}
}

func TestPostResultsValidationReturns422(t *testing.T) {
	tapi, _, _ := newAPI(t)

	body := validBody()
	body["tags"] = map[string]any{"source": "test"} // missing required "name"
	resp := tapi.Post("/api/results", "Authorization: Bearer "+testToken, body)
	require.Equal(t, http.StatusUnprocessableEntity, resp.Code, "body = %s", resp.Body.String())
}

// TestSubmitErrorNullRejected422 pins that an explicit `error: null` is rejected
// at decode (legacy marshmallow refuses nulls), even though huma maps a nil map
// the same as an absent field — the JSONObject presence tracking distinguishes.
func TestSubmitErrorNullRejected422(t *testing.T) {
	tapi, _, _ := newAPI(t)

	body := validBody()
	body["error"] = nil // marshals to "error": null
	resp := tapi.Post("/api/results", "Authorization: Bearer "+testToken, body)
	require.Equal(t, http.StatusUnprocessableEntity, resp.Code, "body = %s", resp.Body.String())
	assert.Contains(t, resp.Body.String(), "error: null is not allowed")
}

// TestPostResultsAuthDisabledBypass pins the dev bypass: with auth disabled, a
// request with no token still succeeds.
func TestPostResultsAuthDisabledBypass(t *testing.T) {
	pool, _ := dbtest.NewPool(t)
	store := db.NewStore(pool)
	h := api.NewHandler(service.NewIngester(store, commit.LocalProvider{}), service.NewReader(store), auth.New("", true, store, nil))
	_, tapi := humatest.New(t)
	h.Register(tapi)

	resp := tapi.Post("/api/results", validBody())
	require.Equal(t, http.StatusCreated, resp.Code, "auth disabled; body = %s", resp.Body.String())
}

// TestPostResultsDBTokenMatrix pins the Leaf 3a acceptance set against the
// real handler stack: db token ok, revoked db token 401, static env token ok
// (the operator bootstrap path).
func TestPostResultsDBTokenMatrix(t *testing.T) {
	pool, ctx := dbtest.NewPool(t)
	store := db.NewStore(pool)
	h := api.NewHandler(service.NewIngester(store, commit.LocalProvider{}), service.NewReader(store), auth.New(testToken, false, store, nil))
	_, tapi := humatest.New(t)
	h.Register(tapi)

	userID := dbtest.SeedUser(t, ctx, pool)
	tok, err := auth.GenerateToken()
	require.NoError(t, err)
	id, err := store.CreateAPIToken(ctx, storage.InsertAPITokenParams{
		UserID: userID, Name: "matrix", TokenHash: tok.Hash, TokenPrefix: tok.Prefix,
		CreatedAt: time.Now().UTC(),
	})
	require.NoError(t, err)

	resp := tapi.Post("/api/results", "Authorization: Bearer "+tok.Plaintext, validBody())
	require.Equal(t, http.StatusCreated, resp.Code, "db token; body = %s", resp.Body.String())

	require.NoError(t, store.RevokeAPIToken(ctx, id, time.Now().UTC()))
	resp = tapi.Post("/api/results", "Authorization: Bearer "+tok.Plaintext, validBody())
	assert.Equal(t, http.StatusUnauthorized, resp.Code, "revoked db token")

	resp = tapi.Post("/api/results", "Authorization: Bearer "+testToken, validBody())
	assert.Equal(t, http.StatusCreated, resp.Code, "static env token")
}

// TestPostResultsSessionCookie pins that a valid session cookie authorizes a
// write with no Authorization header.
func TestPostResultsSessionCookie(t *testing.T) {
	pool, _ := dbtest.NewPool(t)
	store := db.NewStore(pool)
	sessions := auth.NewSessionSigner("sek")
	h := api.NewHandler(service.NewIngester(store, commit.LocalProvider{}), service.NewReader(store), auth.New("", false, store, sessions))
	_, tapi := humatest.New(t)
	h.Register(tapi)

	value := sessions.Sign("user-1", time.Now().UTC().Add(time.Hour))
	resp := tapi.Post("/api/results", "Cookie: conbench_session="+value, validBody())
	require.Equal(t, http.StatusCreated, resp.Code, "valid session; body = %s", resp.Body.String())

	expired := sessions.Sign("user-1", time.Now().UTC().Add(-time.Hour))
	resp = tapi.Post("/api/results", "Cookie: conbench_session="+expired, validBody())
	assert.Equal(t, http.StatusUnauthorized, resp.Code, "expired session")
}

// TestSubmitNullAnnotationFieldsTreatedAsAbsent pins the approved parity
// deviation: an explicit null for optional_benchmark_info, validation, or
// change_annotations is accepted as absent (legacy 400s on null; the stored
// outcome is identical), and a PUT change_annotations of null is a no-op merge.
func TestSubmitNullAnnotationFieldsTreatedAsAbsent(t *testing.T) {
	tapi, store, ctx := newAPI(t)

	body := validBody()
	body["optional_benchmark_info"] = nil
	body["validation"] = nil
	body["change_annotations"] = nil
	resp := tapi.Post("/api/results", "Authorization: Bearer "+testToken, body)
	require.Equal(t, http.StatusCreated, resp.Code, "body = %s", resp.Body.String())
	var out struct {
		ID string `json:"id"`
	}
	require.NoError(t, json.Unmarshal(resp.Body.Bytes(), &out))

	row, err := store.GetBenchmarkResultByID(ctx, out.ID)
	require.NoError(t, err)
	assert.Nil(t, row.OptionalBenchmarkInfo)
	assert.Nil(t, row.Validation)
	assert.JSONEq(t, `{}`, string(row.ChangeAnnotations))

	putResp := tapi.Put("/api/benchmark-results/"+out.ID, "Authorization: Bearer "+testToken,
		map[string]any{"change_annotations": nil})
	require.Equal(t, http.StatusOK, putResp.Code, "body = %s", putResp.Body.String())
	row, err = store.GetBenchmarkResultByID(ctx, out.ID)
	require.NoError(t, err)
	assert.JSONEq(t, `{}`, string(row.ChangeAnnotations))

	// The no-op must also hold for NON-empty stored annotations: a null PUT
	// merges nothing and must not clear existing keys.
	id2 := submitWithChangeAnnotations(t, tapi, map[string]any{"keep": "old"})
	putResp = tapi.Put("/api/benchmark-results/"+id2, "Authorization: Bearer "+testToken,
		map[string]any{"change_annotations": nil})
	require.Equal(t, http.StatusOK, putResp.Code, "body = %s", putResp.Body.String())
	row2, err := store.GetBenchmarkResultByID(ctx, id2)
	require.NoError(t, err)
	assert.JSONEq(t, `{"keep":"old"}`, string(row2.ChangeAnnotations))
}

// submitWithChangeAnnotations posts a valid result carrying the given
// change_annotations and returns its id.
func submitWithChangeAnnotations(t *testing.T, tapi humatest.TestAPI, ca map[string]any) string {
	t.Helper()
	body := validBody()
	body["change_annotations"] = ca
	resp := tapi.Post("/api/results", "Authorization: Bearer "+testToken, body)
	require.Equal(t, http.StatusCreated, resp.Code, "body = %s", resp.Body.String())
	var out struct {
		ID string `json:"id"`
	}
	require.NoError(t, json.Unmarshal(resp.Body.Bytes(), &out))
	require.NotEmpty(t, out.ID)
	return out.ID
}

func TestPutResultMergesChangeAnnotations(t *testing.T) {
	tapi, _, _ := newAPI(t)
	id := submitWithChangeAnnotations(t, tapi, map[string]any{"keep": "old", "drop": "old"})

	body := map[string]any{"change_annotations": map[string]any{"drop": nil, "new": "val"}}
	resp := tapi.Put("/api/benchmark-results/"+id, "Authorization: Bearer "+testToken, body)
	require.Equal(t, http.StatusOK, resp.Code, "body = %s", resp.Body.String())

	// The response is the FULL result detail, with the merged annotations.
	var d service.ResultDetail
	require.NoError(t, json.Unmarshal(resp.Body.Bytes(), &d))
	assert.Equal(t, id, d.ID)
	assert.Equal(t, map[string]any{"keep": "old", "new": "val"}, d.ChangeAnnotations)
}

func TestPutResultRejectsBadAuth(t *testing.T) {
	tapi, _, _ := newAPI(t)
	id := submitWithChangeAnnotations(t, tapi, map[string]any{"keep": "old"})

	body := map[string]any{"change_annotations": map[string]any{"new": "val"}}
	resp := tapi.Put("/api/benchmark-results/"+id, body)
	assert.Equal(t, http.StatusUnauthorized, resp.Code, "body = %s", resp.Body.String())
}

func TestPutResultNotFound(t *testing.T) {
	tapi, _, _ := newAPI(t)

	body := map[string]any{"change_annotations": map[string]any{"new": "val"}}
	resp := tapi.Put("/api/benchmark-results/no-such-id", "Authorization: Bearer "+testToken, body)
	assert.Equal(t, http.StatusNotFound, resp.Code, "body = %s", resp.Body.String())
}

func TestDeleteResult(t *testing.T) {
	// newReadAPI registers both the write and read handlers, so the follow-up GET
	// routes and confirms the row is gone.
	tapi, _ := newReadAPI(t)
	id, _ := submit(t, tapi)

	resp := tapi.Delete("/api/benchmark-results/"+id, "Authorization: Bearer "+testToken)
	require.Equal(t, http.StatusNoContent, resp.Code, "body = %s", resp.Body.String())
	assert.Empty(t, resp.Body.String(), "204 carries no body")

	resp = tapi.Get("/api/benchmark-results/" + id)
	assert.Equal(t, http.StatusNotFound, resp.Code, "body = %s", resp.Body.String())
}

func TestDeleteResultIdempotent404(t *testing.T) {
	tapi, _ := newReadAPI(t)
	id, _ := submit(t, tapi)

	resp := tapi.Delete("/api/benchmark-results/"+id, "Authorization: Bearer "+testToken)
	require.Equal(t, http.StatusNoContent, resp.Code, "body = %s", resp.Body.String())

	// Deleting the same id again is a 404.
	resp = tapi.Delete("/api/benchmark-results/"+id, "Authorization: Bearer "+testToken)
	assert.Equal(t, http.StatusNotFound, resp.Code, "body = %s", resp.Body.String())
}

func TestDeleteResultRejectsBadAuth(t *testing.T) {
	tapi, _ := newReadAPI(t)
	id, _ := submit(t, tapi)

	resp := tapi.Delete("/api/benchmark-results/" + id)
	require.Equal(t, http.StatusUnauthorized, resp.Code, "body = %s", resp.Body.String())

	// 401 happens before any db work: the row is still there.
	resp = tapi.Get("/api/benchmark-results/" + id)
	assert.Equal(t, http.StatusOK, resp.Code, "row should survive an unauthenticated delete; body = %s", resp.Body.String())
}
