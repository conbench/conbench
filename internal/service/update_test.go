package service_test

import (
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/conbench/conbench/internal/service"
	"github.com/conbench/conbench/internal/storage"
)

func TestUpdateChangeAnnotationsMergeAndDelete(t *testing.T) {
	ing, store, _, ctx := newIngester(t)

	req := machineReq(samples(1, 2, 3), "s")
	req.ChangeAnnotations = map[string]any{"keep": "old", "drop": "old", "begins_distribution_change": true}
	res, err := ing.Submit(ctx, req)
	require.NoError(t, err)

	err = ing.UpdateChangeAnnotations(ctx, res.ID, map[string]any{
		"drop": nil,   // null deletes the key
		"new":  "val", // new keys merge in
		"keep": "new", // given wins over stored
	})
	require.NoError(t, err)

	row, err := store.GetBenchmarkResultByID(ctx, res.ID)
	require.NoError(t, err)
	assert.JSONEq(t, `{"keep":"new","new":"val","begins_distribution_change":true}`, string(row.ChangeAnnotations))
}

func TestUpdateChangeAnnotationsEmptyBodyIsNoOp(t *testing.T) {
	ing, store, _, ctx := newIngester(t)

	req := machineReq(samples(1, 2, 3), "s")
	req.ChangeAnnotations = map[string]any{"a": 1.0}
	res, err := ing.Submit(ctx, req)
	require.NoError(t, err)

	require.NoError(t, ing.UpdateChangeAnnotations(ctx, res.ID, nil))

	row, err := store.GetBenchmarkResultByID(ctx, res.ID)
	require.NoError(t, err)
	assert.JSONEq(t, `{"a":1}`, string(row.ChangeAnnotations))
}

func TestUpdateChangeAnnotationsNotFound(t *testing.T) {
	ing, _, _, ctx := newIngester(t)
	err := ing.UpdateChangeAnnotations(ctx, "no-such-id", map[string]any{"x": 1.0})
	require.ErrorIs(t, err, service.ErrNotFound)
}

func TestDeleteResultRowOnlyAndHistoryRecomputes(t *testing.T) {
	ing, store, _, ctx := newIngester(t)
	reader := service.NewReader(store)

	req1 := machineReq(samples(1, 2, 3), "s")
	req1.GitHub.Commit = "sha-del-1"
	res1, err := ing.Submit(ctx, req1)
	require.NoError(t, err)

	req2 := machineReq(samples(4, 5, 6), "s")
	req2.GitHub.Commit = "sha-del-2"
	res2, err := ing.Submit(ctx, req2)
	require.NoError(t, err)
	require.Equal(t, res1.HistoryFingerprint, res2.HistoryFingerprint)

	hist, err := reader.History(ctx, res1.HistoryFingerprint)
	require.NoError(t, err)
	require.Len(t, hist.Samples, 2)

	require.NoError(t, ing.DeleteResult(ctx, res1.ID))

	_, err = store.GetBenchmarkResultByID(ctx, res1.ID)
	require.ErrorIs(t, err, storage.ErrNotFound)

	// blast radius: the second result and its related entities are intact
	detail, err := reader.ResultDetail(ctx, res2.ID)
	require.NoError(t, err)
	require.NotNil(t, detail.Commit) // commit rows not cascaded away

	// history recomputes: only the surviving member remains
	hist, err = reader.History(ctx, res2.HistoryFingerprint)
	require.NoError(t, err)
	require.Len(t, hist.Samples, 1)
	assert.Equal(t, res2.ID, hist.Samples[0].BenchmarkResultID)
}

func TestDeleteResultNotFound(t *testing.T) {
	ing, _, _, ctx := newIngester(t)
	require.ErrorIs(t, ing.DeleteResult(ctx, "no-such-id"), service.ErrNotFound)
}
