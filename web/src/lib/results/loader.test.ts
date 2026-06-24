import { describe, expect, it, vi } from "vitest";

import type { createConbenchClient } from "../api/client";
import { DEFAULT_RESULT_LIST_QUERY } from "../router";
import { loadResultsPage } from "./loader";

type Client = ReturnType<typeof createConbenchClient>;

const result = (id: string, overrides: Record<string, unknown> = {}) => ({
  id,
  run_id: "run-a",
  run_reason: "nightly",
  run_tags: { arch: "x86" },
  batch_id: "batch-a",
  timestamp: "2026-01-02T00:00:00Z",
  unit: "s",
  single_value_summary: 1.25,
  single_value_summary_type: "min",
  history_fingerprint: `fp-${id}`,
  commit: {
    hash: "abcdef123456",
    repository: "https://github.com/apache/arrow",
    timestamp: "2026-01-02T00:00:00Z",
  },
  has_error: false,
  ...overrides,
});

function fakeClient(page: unknown, error: false | { detail: string } = false): {
  client: Client;
  GET: ReturnType<typeof vi.fn>;
} {
  const GET = vi.fn(async () =>
    error ? { error: { detail: error.detail } } : { data: page },
  );
  return { client: { GET } as unknown as Client, GET };
}

describe("loadResultsPage", () => {
  it("loads recent benchmark results and derives summary links", async () => {
    const { client, GET } = fakeClient({
      results: [
        result("r2", { has_error: true, run_id: "run-b", batch_id: null }),
        result("r1"),
      ],
      next_page_cursor: "cur2",
    });

    const page = await loadResultsPage(client, {
      query: DEFAULT_RESULT_LIST_QUERY,
      cursor: null,
    });

    expect(GET).toHaveBeenCalledWith("/api/benchmark-results", {
      params: { query: { page_size: 100 } },
    });
    expect(page).toMatchObject({
      loadedResults: 2,
      loadedRuns: 2,
      loadedBatches: 1,
      loadedErrors: 1,
      loadedSeries: 2,
      nextCursor: "cur2",
    });
    expect(page.rows[0]).toMatchObject({
      id: "r2",
      resultHref: "/results/r2",
      runHref: "/runs/run-b",
      batchHref: null,
      trendHref: "/series/fp-r2",
      hasError: true,
    });
  });

  it("passes filters and cursor to the API", async () => {
    const { client, GET } = fakeClient({ results: [], next_page_cursor: null });
    await loadResultsPage(client, {
      query: {
        runID: "run-a",
        batchID: "batch-a",
        runReason: "nightly",
        earliestTimestamp: "2026-01-01T00:00:00Z",
        latestTimestamp: "2026-01-02T00:00:00Z",
      },
      cursor: "cur1",
    });

    expect(GET).toHaveBeenCalledWith("/api/benchmark-results", {
      params: {
        query: {
          run_id: "run-a",
          batch_id: "batch-a",
          run_reason: "nightly",
          earliest_timestamp: "2026-01-01T00:00:00Z",
          latest_timestamp: "2026-01-02T00:00:00Z",
          page_size: 100,
          cursor: "cur1",
        },
      },
    });
  });

  it("throws endpoint detail on failure", async () => {
    const { client } = fakeClient(null, { detail: "failed to list results" });
    await expect(loadResultsPage(client, { query: DEFAULT_RESULT_LIST_QUERY, cursor: null })).rejects.toThrow(
      "failed to list results",
    );
  });
});
