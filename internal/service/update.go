package service

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"maps"

	"github.com/conbench/conbench/internal/storage"
)

// UpdateChangeAnnotations ports BenchmarkResult.update (benchmark_result.py:308):
// merge the given keys over the stored ones (given wins), then drop every
// null-valued key — that is how a key is deleted. Only change_annotations is
// updatable; everything else on the result is immutable.
func (i *Ingester) UpdateChangeAnnotations(ctx context.Context, id string, given map[string]any) error {
	row, err := i.store.GetBenchmarkResultByID(ctx, id)
	if err != nil {
		if errors.Is(err, storage.ErrNotFound) {
			return ErrNotFound
		}
		return fmt.Errorf("load result for update: %w", err)
	}

	old, err := jsonObject(row.ChangeAnnotations)
	if err != nil {
		return err
	}
	merged := make(map[string]any, len(old)+len(given))
	maps.Copy(merged, old)
	maps.Copy(merged, given)

	caJSON, err := json.Marshal(filterNullValues(merged))
	if err != nil {
		return fmt.Errorf("marshal change_annotations: %w", err)
	}
	if err := i.store.UpdateBenchmarkResultChangeAnnotations(ctx, id, caJSON); err != nil {
		if errors.Is(err, storage.ErrNotFound) {
			// Concurrent delete between the load above and this update: still a 404.
			return ErrNotFound
		}
		return fmt.Errorf("update change_annotations: %w", err)
	}
	return nil
}

// DeleteResult hard-deletes one result row. Related case/context/info/
// hardware/commit rows are shared with other results and are never cascaded
// (the FK graph points outward from benchmark_result; nothing references it).
// History, series, and compare are derived per-query, so they recompute on
// the next read.
func (i *Ingester) DeleteResult(ctx context.Context, id string) error {
	if err := i.store.DeleteBenchmarkResult(ctx, id); err != nil {
		if errors.Is(err, storage.ErrNotFound) {
			return ErrNotFound
		}
		return fmt.Errorf("delete result: %w", err)
	}
	return nil
}
